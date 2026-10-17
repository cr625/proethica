"""get_llm_client delegates construction to the provider adapters."""
import pytest


def test_get_llm_client_constructs_anthropic_without_network(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from app.utils.llm_utils import get_llm_client
    from model_config import ModelConfig

    client = get_llm_client()
    assert hasattr(client, "messages")
    assert client.available_models[0] == ModelConfig.get_tier_model("default")


def test_get_llm_client_raises_without_keys(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from app.utils.llm_utils import get_llm_client

    with pytest.raises(RuntimeError, match="No LLM client available"):
        get_llm_client()
