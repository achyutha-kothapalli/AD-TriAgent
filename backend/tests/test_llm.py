from app.config import Settings
from app.llm import create_chat_model, llm_client_options


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


def test_chat_model_uses_the_langchain_openai_adapter() -> None:
    model = create_chat_model(
        Settings(
            llm_api_key="test-key",
            llm_model="test-model",
            llm_base_url="https://llm.example.test/v1",
        )
    )

    assert model is not None
    assert model.model_name == "test-model"
    assert model.temperature == 0.2
    assert str(model.openai_api_base) == "https://llm.example.test/v1"
