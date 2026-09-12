from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph

from app.config import Settings
from app.llm import create_llm_client
from app.services.cases import CaseStore

logger = logging.getLogger(__name__)

CASE_CONTEXT_DESCRIPTION = "Selected autonomous-driving triage case"


def selected_case_id(config: RunnableConfig | None) -> str | None:
    """Read the selected case ID sent by CopilotKit, without trusting other browser fields."""
    configurable = (config or {}).get("configurable", {})
    copilotkit = configurable.get("copilotkit", {})
    for entry in copilotkit.get("context", []):
        if entry.get("description") != CASE_CONTEXT_DESCRIPTION:
            continue
        value = entry.get("value")
        try:
            payload = json.loads(value) if isinstance(value, str) else value
        except json.JSONDecodeError:
            return None
        case_id = payload.get("caseId") if isinstance(payload, dict) else None
        if isinstance(case_id, str) and case_id.startswith("case-"):
            return case_id
    return None


def selected_case_evidence(settings: Settings, case_id: str | None) -> dict[str, Any] | None:
    """Load a small, server-authoritative evidence summary for the active Copilot case."""
    if not case_id:
        return None
    case = CaseStore(settings.runtime_path / "cases.json").get(case_id)
    if case is None:
        return None

    triage = case.get("triage", {})
    return {
        "case_id": case.get("id"),
        "scenario_title": case.get("scenario_title"),
        "status": case.get("status"),
        "primary_failure": triage.get("primary_family_label"),
        "severity": triage.get("severity"),
        "evidence": triage.get("evidence", []),
        "contributing_factors": triage.get("contributing_factors", []),
        "active_rules": [
            {"id": rule.get("id"), "definition": rule.get("definition"), "status": rule.get("status")}
            for rule in case.get("rules", [])
        ],
        "recent_expert_input": [
            {"role": comment.get("role"), "body": comment.get("body")}
            for comment in case.get("comments", [])[-3:]
        ],
    }

def build_copilot_graph(settings: Settings):
    """A small AG-UI graph for questions in the CopilotKit case-room panel."""

    async def respond(state: MessagesState, config: RunnableConfig):
        latest = state["messages"][-1].content if state.get("messages") else ""
        content = (
            "I can help investigate the current triage case. Ask about evidence, the five failure "
            f"families, or whether a candidate rule needs human approval. Your question: {latest}"
        )
        evidence = selected_case_evidence(settings, selected_case_id(config))
        if settings.llm_enabled and settings.llm_api_key:
            client = create_llm_client(settings)
            try:
                from openai import APIError

                if client is None:
                    return {"messages": [AIMessage(content=content)]}
                evidence_note = (
                    f"\nAuthoritative case evidence: {json.dumps(evidence)}" if evidence else
                    "\nNo triaged case is selected. Ask the reviewer to run triage and select a case."
                )
                response = await client.chat.completions.create(
                    model=settings.llm_model,
                    temperature=0.2,
                    max_tokens=250,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a concise autonomous-driving triage copilot. Explain only the "
                                "authoritative supplied evidence. Never make final safety decisions, invent "
                                "telemetry, or approve a rule. Ask for human review when uncertain."
                                f"{evidence_note}"
                            ),
                        },
                        *[
                            {"role": "user" if message.type == "human" else "assistant", "content": str(message.content)}
                            for message in state["messages"]
                        ],
                    ],
                )
                content = response.choices[0].message.content or content
            except (APIError, OSError, ValueError) as error:
                logger.info("LLM copilot fallback: %s", error)
            finally:
                if client is not None:
                    await client.close()
        return {"messages": [AIMessage(content=content)]}

    workflow = StateGraph(MessagesState)
    workflow.add_node("respond", respond)
    workflow.add_edge(START, "respond")
    workflow.add_edge("respond", END)
    # CopilotKit's AG-UI adapter reads per-thread graph state before a run. The
    # POC keeps that state only in process memory; a database checkpointer is
    # the appropriate replacement before deploying multiple backend instances.
    return workflow.compile(checkpointer=InMemorySaver())
