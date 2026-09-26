import json
from pathlib import Path

from app.integrations.telemetry_adapter import adapt_telemetry, load_profile

ROOT = Path(__file__).resolve().parents[2]


def test_customer_profile_maps_an_urban_event_to_the_canonical_contract() -> None:
    profile = load_profile(ROOT / "customer_profiles" / "urban-delivery-fleet.json")
    payload = json.loads((ROOT / "samples" / "customer_telemetry" / "urban-delivery-event.json").read_text())

    scenario = adapt_telemetry(profile, payload)

    assert scenario.id == "scenario-urban-0001"
    assert scenario.metadata["customer_profile"] == "urban-delivery-fleet"
    assert scenario.frames[1].metrics["ttc_s"] == 0.7
    assert scenario.labels["primary_failure"] == "safety_conflict"
