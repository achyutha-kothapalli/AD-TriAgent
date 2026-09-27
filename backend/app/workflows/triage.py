from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.graph.store import KnowledgeGraph
from app.scenarios.repository import ScenarioRepository
from app.services.cases import CaseStore, now
from app.services.evidence import EvidenceExtractor
from app.services.mlflow_tracing import MLflowTracer
from app.services.narrator import TriageNarrator
from app.services.observability import WorkflowObserver
from app.services.retrieval import GuidanceRetriever

REVIEW_ROUTES = {
    "safety_conflict": ["Safety reviewer", "System owner"],
    "perception_localization": ["Perception/localization expert", "System owner"],
    "prediction_interaction": ["Prediction/interaction expert", "System owner"],
    "planning_control": ["Planning/control expert", "System owner"],
    "odd_handover": ["ODD/platform/handover expert", "System owner"],
}


class TriageState(TypedDict, total=False):
    """Server-authoritative state passed between LangGraph nodes."""

    scenario_id: str
    scenario_title: str
    triage: dict[str, Any]
    review_route: list[str]
    case: dict[str, Any]
    human_review: dict[str, Any]


class TriageWorkflow:
    """Evidence-first workflow that pauses at a persisted human-review boundary."""

    def __init__(
        self,
        scenarios: ScenarioRepository,
        cases: CaseStore,
        knowledge_graph: KnowledgeGraph,
        extractor: EvidenceExtractor,
        narrator: TriageNarrator,
        retriever: GuidanceRetriever,
        observer: WorkflowObserver,
        mlflow_tracer: MLflowTracer,
        checkpointer: Any,
    ) -> None:
        self.scenarios = scenarios
        self.cases = cases
        self.knowledge_graph = knowledge_graph
        self.extractor = extractor
        self.narrator = narrator
        self.retriever = retriever
        self.observer = observer
        self.mlflow_tracer = mlflow_tracer
        self.checkpointer = checkpointer
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(TriageState)
        workflow.add_node("extract_evidence", self._extract_evidence)
        workflow.add_node("retrieve_active_rules", self._retrieve_active_rules)
        workflow.add_node("retrieve_investigation_guidance", self._retrieve_investigation_guidance)
        workflow.add_node("assign_review_route", self._assign_review_route)
        workflow.add_node("draft_explanation", self._draft_explanation)
        workflow.add_node("await_human_review", self._await_human_review)
        workflow.add_node("persist_case", self._persist_case)
        workflow.add_node("record_provenance", self._record_provenance)
        workflow.add_edge(START, "extract_evidence")
        workflow.add_edge("extract_evidence", "retrieve_active_rules")
        workflow.add_edge("retrieve_active_rules", "retrieve_investigation_guidance")
        workflow.add_edge("retrieve_investigation_guidance", "assign_review_route")
        workflow.add_edge("assign_review_route", "draft_explanation")
        workflow.add_edge("draft_explanation", "await_human_review")
        workflow.add_edge("await_human_review", "persist_case")
        workflow.add_edge("persist_case", "record_provenance")
        workflow.add_edge("record_provenance", END)
        return workflow.compile(checkpointer=self.checkpointer)

    def _extract_evidence(self, state: TriageState) -> TriageState:
        with self._measure("extract_evidence", state):
            scenario = self.scenarios.get(state["scenario_id"])
            if scenario is None:
                raise ValueError(f"Scenario {state['scenario_id']} was not found")
            return {
                "scenario_title": scenario.title,
                "triage": self.extractor.extract(scenario).as_dict(),
            }

    def _retrieve_active_rules(self, state: TriageState) -> TriageState:
        with self._measure("retrieve_active_rules", state):
            triage = dict(state["triage"])
            triage["active_rules"] = self.knowledge_graph.active_rules_for(triage["primary_family"])
            return {"triage": triage}

    def _retrieve_investigation_guidance(self, state: TriageState) -> TriageState:
        with self._measure("retrieve_investigation_guidance", state) as details:
            triage = dict(state["triage"])
            guidance = self.retriever.retrieve(triage)
            triage["investigation_guidance"] = guidance
            details["guidance_status"] = guidance["status"]
            details["retrieved_sources"] = len(guidance["sources"])
            return {"triage": triage}

    def _assign_review_route(self, state: TriageState) -> TriageState:
        with self._measure("assign_review_route", state):
            family = state["triage"]["primary_family"]
            return {"review_route": REVIEW_ROUTES.get(family, ["System owner"])}

    async def _draft_explanation(self, state: TriageState) -> TriageState:
        with self._measure("draft_explanation", state) as details:
            triage = dict(state["triage"])
            draft = await self.narrator.draft(state["scenario_title"], triage)
            triage["narrative"] = draft.text
            triage["narrative_provenance"] = {
                "source": draft.source,
                "model": draft.model,
                "fallback_reason": draft.fallback_reason,
            }
            details["narrative_source"] = draft.source
            return {"triage": triage}

    def _await_human_review(self, state: TriageState) -> TriageState:
        with self._measure("await_human_review", state):
            case_id = f"case-{state['scenario_id']}"
            case = self.cases.get(case_id) or {
                "id": case_id,
                "scenario_id": state["scenario_id"],
                "scenario_title": state["scenario_title"],
                "created_at": now(),
                "comments": [],
                "rules": [],
                "activity": [],
            }
            case["triage"] = state["triage"]
            case["status"] = "awaiting_expert_review"
            human_review = {
                "status": "pending",
                "required": True,
                "reviewers": state["review_route"],
                "decision_boundary": "A system owner must approve a passing candidate rule.",
            }
            case["workflow"] = {
                "engine": "langgraph",
                "state": "awaiting_human_review",
                "review_route": state["review_route"],
            }
            case["human_review"] = human_review
            self.cases.activity(
                case,
                "triage",
                f"Routed to {state['triage']['primary_family_label']} ({state['triage']['severity']})",
                "Triage workflow",
            )
            return {"case": case, "human_review": human_review}

    def _persist_case(self, state: TriageState) -> TriageState:
        with self._measure("persist_case", state):
            case = state["case"]
            self.cases.upsert(case["id"], case)
            return {"case": case}

    def _record_provenance(self, state: TriageState) -> TriageState:
        with self._measure("record_provenance", state):
            case = state["case"]
            self.knowledge_graph.record_triage(case["scenario_id"], case["id"], state["triage"])
            return {"case": case}

    @contextmanager
    def _measure(self, node: str, state: TriageState):
        started = perf_counter()
        details: dict[str, Any] = {}
        try:
            with self.mlflow_tracer.node_span(node, state, details):
                yield details
        except Exception as error:
            self.observer.record(
                scenario_id=state["scenario_id"],
                node=node,
                outcome="error",
                duration_ms=(perf_counter() - started) * 1000,
                details={"error_type": type(error).__name__},
            )
            raise
        else:
            self.observer.record(
                scenario_id=state["scenario_id"],
                node=node,
                outcome="ok",
                duration_ms=(perf_counter() - started) * 1000,
                details=details,
            )

    async def run(self, scenario_id: str) -> dict[str, Any]:
        with self.mlflow_tracer.workflow_span(scenario_id) as span:
            state = await self.graph.ainvoke(
                {"scenario_id": scenario_id},
                config={"configurable": {"thread_id": f"triage:{scenario_id}"}},
            )
            case = state["case"]
            self.mlflow_tracer.set_case_outcome(span, case)
            return case
