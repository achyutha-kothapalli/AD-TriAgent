from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx
from networkx.readwrite import json_graph


class KnowledgeGraph:
    """Small, portable knowledge graph for POC-scale provenance and rule lifecycle."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.graph = self._load()

    def _load(self) -> nx.MultiDiGraph:
        if not self.path.exists():
            return nx.MultiDiGraph()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return nx.MultiDiGraph(json_graph.node_link_graph(data, directed=True, multigraph=True))

    def save(self) -> None:
        self.path.write_text(json.dumps(json_graph.node_link_data(self.graph), indent=2), encoding="utf-8")

    def add_node(self, node_id: str, kind: str, **attributes: Any) -> None:
        self.graph.add_node(node_id, kind=kind, **attributes)
        self.save()

    def add_edge(self, source: str, target: str, relation: str, **attributes: Any) -> None:
        self.graph.add_edge(source, target, relation=relation, **attributes)
        self.save()

    def record_triage(self, scenario_id: str, case_id: str, triage: dict[str, Any]) -> None:
        decision_id = f"decision:{case_id}"
        self.graph.add_node(scenario_id, kind="Scenario")
        self.graph.add_node(case_id, kind="DisengagementCase", severity=triage["severity"])
        self.graph.add_node(
            decision_id,
            kind="TriageDecision",
            family=triage["primary_family"],
            confidence=triage["confidence"],
        )
        self.graph.add_edge(scenario_id, case_id, relation="HAS_CASE")
        self.graph.add_edge(case_id, decision_id, relation="HAS_DECISION")
        for number, item in enumerate(triage["evidence"]):
            evidence_id = f"evidence:{case_id}:{number}"
            self.graph.add_node(evidence_id, kind="Evidence", **item)
            self.graph.add_edge(evidence_id, decision_id, relation="SUPPORTS")
        self.save()

    def record_comment(self, case_id: str, comment: dict[str, Any]) -> str:
        comment_id = f"comment:{case_id}:{len(self.graph.nodes)}"
        author_id = f"expert:{comment['author']}"
        self.graph.add_node(author_id, kind="Collaborator", role=comment["role"])
        self.graph.add_node(comment_id, kind="Comment", body=comment["body"], at=comment["at"])
        self.graph.add_edge(author_id, comment_id, relation="AUTHORED")
        self.graph.add_edge(comment_id, case_id, relation="COMMENTS_ON")
        self.save()
        return comment_id

    def record_rule(self, rule: dict[str, Any], case_id: str, comment_id: str) -> None:
        self.graph.add_node(
            rule["id"],
            kind="RuleVersion",
            status=rule["status"],
            family=rule["family"],
            definition=rule["definition"],
            version=rule["version"],
        )
        self.graph.add_edge(comment_id, rule["id"], relation="PROPOSES")
        self.graph.add_edge(rule["id"], case_id, relation="DERIVED_FROM")
        self.save()

    def update_rule(self, rule: dict[str, Any]) -> None:
        if rule["id"] in self.graph:
            self.graph.nodes[rule["id"]].update(
                status=rule["status"], test=rule.get("test"), approved_by=rule.get("approved_by")
            )
            self.save()

    def active_rules_for(self, family: str) -> list[dict[str, Any]]:
        return [
            {"id": node_id, **attributes}
            for node_id, attributes in self.graph.nodes(data=True)
            if attributes.get("kind") == "RuleVersion"
            and attributes.get("family") == family
            and attributes.get("status") == "active"
        ]

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        nodes = [{"id": node_id, **attributes} for node_id, attributes in self.graph.nodes(data=True)]
        edges = [
            {"source": source, "target": target, "key": key, **attributes}
            for source, target, key, attributes in self.graph.edges(keys=True, data=True)
        ]
        return {"nodes": nodes, "edges": edges}
