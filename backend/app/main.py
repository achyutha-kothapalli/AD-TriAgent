from __future__ import annotations

import hashlib
import hmac
from contextlib import asynccontextmanager
from uuid import uuid4

from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from copilotkit import LangGraphAGUIAgent
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.agents import build_copilot_graph
from app.collaboration.dispatcher import CollaborationDispatcher
from app.config import get_settings
from app.graph.store import KnowledgeGraph
from app.models import AmbiguousInboundEvent, CommentCreate, RuleApproval
from app.scenarios.repository import ScenarioRepository
from app.services.cases import CaseStore, now
from app.services.evidence import EvidenceExtractor
from app.services.narrator import TriageNarrator
from app.services.rules import RuleMiner


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.runtime_path.mkdir(parents=True, exist_ok=True)
    app.state.scenarios = ScenarioRepository(settings.scenario_path)
    app.state.cases = CaseStore(settings.runtime_path / "cases.json")
    app.state.graph = KnowledgeGraph(settings.runtime_path / "rule_graph.json")
    app.state.extractor = EvidenceExtractor()
    app.state.rules = RuleMiner(app.state.extractor)
    app.state.narrator = TriageNarrator(settings)
    app.state.dispatcher = CollaborationDispatcher(settings)
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
add_langgraph_fastapi_endpoint(
    app=app,
    agent=LangGraphAGUIAgent(
        name="triage_copilot",
        description="Evidence-first autonomous driving triage assistant.",
        graph=build_copilot_graph(settings),
    ),
    path="/agents/triage",
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


def _valid_ambiguous_signature(secret: str | None, body: bytes, signature: str | None) -> bool:
    """Verify the normalized relay signature without assuming Ambiguous's native schema."""
    if not secret or not signature:
        return False
    supplied = signature.removeprefix("sha256=")
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(supplied, expected)


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
    cases = _service(request, "cases")
    case_id = f"case-{scenario_id}"
    triage = _service(request, "extractor").extract(scenario).as_dict()
    triage["narrative"] = await _service(request, "narrator").explain(scenario.title, triage)
    triage["active_rules"] = _service(request, "graph").active_rules_for(triage["primary_family"])
    case = cases.get(case_id) or {
        "id": case_id,
        "scenario_id": scenario_id,
        "scenario_title": scenario.title,
        "created_at": now(),
        "comments": [],
        "rules": [],
        "activity": [],
    }
    case["triage"] = triage
    case["status"] = "awaiting_expert_review"
    cases.activity(case, "triage", f"Routed to {triage['primary_family_label']} ({triage['severity']})", "Triage agent")
    cases.upsert(case_id, case)
    _service(request, "graph").record_triage(scenario_id, case_id, triage)
    await _service(request, "dispatcher").dispatch(case, case["activity"][-1])
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
    await _service(request, "dispatcher").dispatch(case, case["activity"][-1])
    return {"case": case, "rule": rule}


@app.post("/webhooks/ambiguous")
async def ambiguous_webhook(request: Request) -> dict:
    """Accept verified, normalized Ambiguous events without reflecting them back out."""
    settings = get_settings()
    body = await request.body()
    if not _valid_ambiguous_signature(
        settings.ambiguous_webhook_secret,
        body,
        request.headers.get("x-triage-signature"),
    ):
        raise HTTPException(status_code=401, detail="Invalid Ambiguous relay signature")

    try:
        payload = AmbiguousInboundEvent.model_validate_json(body)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Invalid Ambiguous event payload") from error

    cases = _service(request, "cases")
    case = cases.get(payload.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    ambiguous = case.setdefault("collaboration", {}).setdefault("ambiguous", {})
    received_ids = ambiguous.setdefault("received_event_ids", [])
    if payload.event_id in received_ids:
        return {"status": "duplicate", "case_id": case["id"]}
    received_ids.append(payload.event_id)
    del received_ids[:-100]

    if payload.kind == "expert_comment":
        comment = {
            "id": f"ambiguous-{payload.event_id}",
            "author": payload.actor,
            "role": payload.role,
            "body": payload.message,
            "at": now(),
            "is_simulated_persona": False,
        }
        case["comments"].append(comment)
        comment_node = _service(request, "graph").record_comment(case["id"], comment)
        rule = _service(request, "rules").propose(case, comment)
        case["rules"].append(rule)
        _service(request, "graph").record_rule(rule, case["id"], comment_node)
        cases.activity(case, "ambiguous_comment", payload.message, payload.actor)
        cases.activity(case, "rule_candidate", f"Created candidate {rule['id']}", "Rule miner")
    else:
        cases.activity(case, "ambiguous_task_update", payload.message, payload.actor)

    cases.upsert(case["id"], case)
    return {"status": "recorded", "case_id": case["id"]}


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
    await _service(request, "dispatcher").dispatch(case, case["activity"][-1])
    return rule


@app.get("/api/rules")
async def list_rules(request: Request) -> list[dict]:
    return [rule for case in _service(request, "cases").all() for rule in case.get("rules", [])]


@app.get("/api/knowledge-graph")
async def knowledge_graph(request: Request) -> dict:
    return _service(request, "graph").snapshot()
