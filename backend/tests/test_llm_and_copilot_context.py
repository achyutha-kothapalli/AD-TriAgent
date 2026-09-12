from app.agents import CASE_CONTEXT_DESCRIPTION, build_copilot_graph, selected_case_id
from app.config import Settings
from app.llm import llm_client_options


def test_llm_client_options_use_a_configured_openai_compatible_base_url() -> None:
    settings = Settings(
        llm_api_key="test-key",
        llm_model="test-model",
        llm_base_url="https://llm.example.test/v1",
    )

    assert llm_client_options(settings) == {
        "api_key": "test-key",
        "base_url": "https://llm.example.test/v1",
    }


def test_llm_client_options_are_none_without_a_key() -> None:
    assert llm_client_options(Settings(llm_api_key=None)) is None


def test_selected_case_id_reads_the_copilot_context_contract() -> None:
    config = {
        "configurable": {
            "copilotkit": {
                "context": [
                    {
                        "description": CASE_CONTEXT_DESCRIPTION,
                        "value": '{"caseId":"case-scenario-012"}',
                    }
                ]
            }
        }
    }

    assert selected_case_id(config) == "case-scenario-012"


def test_selected_case_id_rejects_a_non_case_identifier() -> None:
    config = {
        "configurable": {
            "copilotkit": {
                "context": [{"description": CASE_CONTEXT_DESCRIPTION, "value": '{"caseId":"12"}'}]
            }
        }
    }

    assert selected_case_id(config) is None


def test_copilot_graph_has_a_checkpointer_for_thread_state() -> None:
    graph = build_copilot_graph(Settings(llm_enabled=False))

    assert graph.checkpointer is not None
