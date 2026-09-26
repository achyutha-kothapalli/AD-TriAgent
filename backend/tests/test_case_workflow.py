from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

GENERATED = get_settings().scenario_path / "scenario-001.json"


@pytest.mark.skipif(not Path(GENERATED).exists(), reason="Run the MetaDrive corpus generator first")
def test_case_rule_workflow() -> None:
    with TestClient(app) as client:
        client.app.state.narrator.settings.llm_enabled = False
        response = client.post("/api/scenarios/scenario-001/triage")
        assert response.status_code == 200
        case = response.json()
        assert case["triage"]["primary_family"] == "safety_conflict"
        assert case["workflow"]["engine"] == "langgraph"
        assert case["human_review"]["status"] == "pending"
        assert "Safety reviewer" in case["human_review"]["reviewers"]

        comment = client.post(
            f"/api/cases/{case['id']}/comments",
            json={
                "author": "Ava Safety",
                "role": "Safety reviewer",
                "body": "The minimum TTC is sufficient to require a safety review and an escalation rule.",
                "is_simulated_persona": True,
            },
        )
        assert comment.status_code == 200
        rule_id = comment.json()["rule"]["id"]

        tested = client.post(f"/api/rules/{rule_id}/test")
        assert tested.status_code == 200
        assert tested.json()["status"] == "tested"
        assert tested.json()["test"]["passed"] is True

        approved = client.post(
            f"/api/rules/{rule_id}/approve",
            json={"owner": "Sam Owner", "note": "Validated on the synthetic corpus."},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "active"
