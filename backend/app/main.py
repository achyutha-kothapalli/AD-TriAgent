from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.collaboration.dispatcher import SlackNotifier
from app.config import get_settings
from app.graph.store import KnowledgeGraph
from app.models import CaseReview, CommentCreate, RuleApproval
from app.scenarios.repository import ScenarioRepository
from app.services.cases import CaseStore, now
from app.services.evidence import EvidenceExtractor
from app.services.narrator import TriageNarrator
from app.services.observability import WorkflowObserver
from app.services.rules import RuleMiner
from app.workflows.triage import TriageWorkflow


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.runtime_path.mkdir(parents=True, exist_ok=True)
    checkpoint_path = settings.runtime_path / "langgraph_checkpoints.sqlite"
    async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path)) as checkpointer:
        await checkpointer.setup()
        app.state.scenarios = ScenarioRepository(settings.scenario_path)
        app.state.cases = CaseStore(settings.runtime_path / "cases.json")
        app.state.graph = KnowledgeGraph(settings.runtime_path / "rule_graph.json")
        app.state.extractor = EvidenceExtractor()
        app.state.rules = RuleMiner(app.state.extractor)
        app.state.narrator = TriageNarrator(settings)
        app.state.observer = WorkflowObserver(settings.runtime_path / "workflow_events.jsonl")
        app.state.triage_workflow = TriageWorkflow(
            app.state.scenarios,
            app.state.cases,
            app.state.graph,
            app.state.extractor,
            app.state.narrator,
            app.state.observer,
            checkpointer,
        )
        app.state.notifications = SlackNotifier(settings)
        yield


settings = get_settings()
app = FastAPI(title="Autonomous Driving Triage Agent", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
def _service(request: Request, name: str):
    return getattr(request.app.state, name)


def _public_scenario(scenario) -> dict:
    return scenario.model_dump(exclude={"labels"})


def _find_rule(cases: CaseStore, rule_id: str) -> tuple[dict, dict] | None:
    for case in cases.all():
        for rule in case.get("rules", []):
            if rule["id"] == rule_id:
                return case, rule
    return None


@app.get("/health")
async def health(request: Request) -> dict:
    return {
        "status": "ok",
        "scenario_count": len(_service(request, "scenarios").all()),
        "knowledge_graph": "networkx-json",
    }


@app.get("/api/scenarios")
async def list_scenarios(request: Request) -> list[dict]:
    repository = _service(request, "scenarios")
    return [repository.public_summary(scenario) for scenario in repository.all()]


@app.get("/api/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str, request: Request) -> dict:
    scenario = _service(request, "scenarios").get(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found. Generate the MetaDrive corpus first.")
    return _public_scenario(scenario)


@app.post("/api/scenarios/{scenario_id}/triage")
async def triage_scenario(scenario_id: str, request: Request) -> dict:
    scenario = _service(request, "scenarios").get(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    case = await _service(request, "triage_workflow").run(scenario_id)
    await _service(request, "notifications").dispatch(case, case["activity"][-1])
    return case


@app.get("/api/cases/{case_id}")
async def get_case(case_id: str, request: Request) -> dict:
    case = _service(request, "cases").get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Triage this scenario before opening its case")
    return case


@app.post("/api/cases/{case_id}/comments")
async def add_comment(case_id: str, payload: CommentCreate, request: Request) -> dict:
    cases = _service(request, "cases")
    case = cases.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    comment = payload.model_dump()
    comment.update({"id": f"comment-{uuid4().hex[:10]}", "at": now()})
    case["comments"].append(comment)
    comment_node = _service(request, "graph").record_comment(case_id, comment)
    rule = _service(request, "rules").propose(case, comment)
    case["rules"].append(rule)
    _service(request, "graph").record_rule(rule, case_id, comment_node)
    cases.activity(case, "comment", comment["body"], comment["author"])
    cases.activity(case, "rule_candidate", f"Created candidate {rule['id']}", "Rule miner")
    cases.upsert(case_id, case)
    await _service(request, "notifications").dispatch(case, case["activity"][-1])
    return {"case": case, "rule": rule}


@app.post("/api/cases/{case_id}/review")
async def record_case_review(case_id: str, payload: CaseReview, request: Request) -> dict:
    cases = _service(request, "cases")
    case = cases.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.get("human_review", {}).get("status") != "pending":
        raise HTTPException(status_code=409, detail="This triage review has already been recorded")
    if payload.action == "approve" and payload.reviewer_role != "System owner":
        raise HTTPException(status_code=403, detail="Only the system owner can approve a triage review")

    status_by_action = {
        "approve": ("approved", "triage_reviewed"),
        "request_more_evidence": ("needs_more_evidence", "needs_more_evidence"),
        "reject": ("rejected", "triage_rejected"),
    }
    review_status, case_status = status_by_action[payload.action]
    case["human_review"].update(
        {
            "status": review_status,
            "reviewed_by": payload.reviewer,
            "reviewed_role": payload.reviewer_role,
            "note": payload.note,
        }
    )
    case["status"] = case_status
    cases.activity(
        case,
        "human_review",
        f"{payload.action.replace('_', ' ')}: {payload.note or 'no note'}",
        payload.reviewer,
    )
    cases.upsert(case_id, case)
    await _service(request, "notifications").dispatch(case, case["activity"][-1])
    return case


@app.post("/api/rules/{rule_id}/test")
async def test_rule(rule_id: str, request: Request) -> dict:
    cases = _service(request, "cases")
    located = _find_rule(cases, rule_id)
    if located is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    case, rule = located
    test = _service(request, "rules").test(rule, _service(request, "scenarios").all())
    rule["test"] = test
    rule["status"] = "tested"
    _service(request, "graph").update_rule(rule)
    cases.activity(case, "rule_test", f"Regression test: precision {test['precision']}, recall {test['recall']}", "Rule miner")
    cases.upsert(case["id"], case)
    return rule


@app.post("/api/rules/{rule_id}/approve")
async def approve_rule(rule_id: str, payload: RuleApproval, request: Request) -> dict:
    cases = _service(request, "cases")
    located = _find_rule(cases, rule_id)
    if located is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    case, rule = located
    if not rule.get("test", {}).get("passed"):
        raise HTTPException(status_code=409, detail="A rule needs a passing regression test before approval")
    rule["status"] = "active"
    rule["approved_by"] = payload.owner
    rule["approval_note"] = payload.note
    _service(request, "graph").update_rule(rule)
    cases.activity(case, "rule_approved", f"Approved {rule_id}: {payload.note or 'no note'}", payload.owner)
    cases.upsert(case["id"], case)
    await _service(request, "notifications").dispatch(case, case["activity"][-1])
    return rule


@app.get("/api/rules")
async def list_rules(request: Request) -> list[dict]:
    return [rule for case in _service(request, "cases").all() for rule in case.get("rules", [])]


@app.get("/api/knowledge-graph")
async def knowledge_graph(request: Request) -> dict:
    return _service(request, "graph").snapshot()


@app.get("/api/observability/summary")
async def observability_summary(request: Request) -> dict:
    return _service(request, "observer").summary()
