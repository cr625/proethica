"""
Provider factory.

Resolves a model reference ("provider:model" or bare id) or a tier name
to a provider adapter instance. Unknown providers raise immediately:
silently substituting a different vendor would invalidate extraction
calibration, prompt tuning, and cost accounting.
"""

from typing import Any, Optional

from .protocol import BaseLLMProvider


def get_provider(ref: str, client: Any = None,
                 timeout: Any = None) -> BaseLLMProvider:
    """Return the provider adapter for a model reference.

    ``client`` injects a pre-built (or fake) SDK client for testing;
    ``timeout`` overrides the adapter SDK client timeout.
    """
    from model_config import ModelConfig

    provider, model = ModelConfig.parse_model_ref(ref)
    if provider == "anthropic":
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(model=model, client=client, timeout=timeout)
    if provider == "openai":
        from .openai_provider import OpenAIProvider

        return OpenAIProvider(model=model, client=client, timeout=timeout)
    raise ValueError(
        f"Unsupported LLM provider {provider!r} in reference {ref!r}. "
        "Supported providers: anthropic, openai."
    )


def provider_for_client(client: Any, model: str) -> BaseLLMProvider:
    """Return a provider adapter for an optionally injected client.

    A provider instance passes through; a raw vendor client is wrapped in
    the Anthropic adapter (the only raw client shape in the codebase);
    ``None`` resolves the adapter from the model reference, so a model on
    another provider gets its own adapter and SDK client.
    """
    if isinstance(client, BaseLLMProvider):
        return client
    if client is not None:
        # OpenAI-shaped clients (chat.completions, no messages API) get
        # the OpenAI adapter; every other raw client in the codebase is
        # an Anthropic messages client.
        if not hasattr(client, "messages") and hasattr(
            getattr(client, "chat", None), "completions"
        ):
            from .openai_provider import OpenAIProvider

            return OpenAIProvider(model=model, client=client)
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(model=model, client=client)
    return get_provider(model)


def has_streaming_shape(client: Any) -> bool:
    """True when no client was injected (the adapter resolves its own)
    or the injected object is a provider / streaming vendor client."""
    return client is None or isinstance(client, BaseLLMProvider) or (
        hasattr(client, "messages") and hasattr(client.messages, "stream")
    )


def streaming_provider_for_client(client: Any, model: str):
    """Provider adapter for a streaming call, or None when an injected
    raw client cannot stream (callers keep their fallback behavior)."""
    if not has_streaming_shape(client):
        return None
    return provider_for_client(client, model)


def complete_text(client: Any, prompt: str, max_tokens: int,
                  temperature: Any = None, tier: str = "default",
                  system: Any = None) -> str:
    """One text completion for an optionally injected client.

    The shared body behind the per-class ``_llm_text`` helpers: resolves
    the tier model, wraps or passes through the client via
    ``provider_for_client``, and returns the response text.
    """
    from model_config import ModelConfig

    model = ModelConfig.get_tier_model(tier)
    provider = provider_for_client(client, model)
    return provider.complete(
        messages=[{"role": "user", "content": prompt}],
        system=system, max_tokens=max_tokens, temperature=temperature,
        model=model,
    ).text


def get_tier_provider(tier: str = "default", client: Any = None,
                      timeout: Any = None) -> BaseLLMProvider:
    """Return the provider adapter configured for a model tier."""
    from model_config import ModelConfig

    return get_provider(ModelConfig.get_tier_ref(tier), client=client, timeout=timeout)
