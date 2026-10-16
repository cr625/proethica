"""
Provider capability registry.

A capability record states what a provider/model combination can be asked
to do, so call sites branch on declared capability instead of on model-name
substrings. The structured-output tier is the load-bearing field:

- ``schema``: the provider constrains decoding to a supplied JSON Schema
  (Anthropic ``output_config.format``; OpenAI ``response_format`` with
  ``strict: true``). Format is guaranteed for a complete response only;
  truncation can still cut the payload.
- ``json_object``: the provider guarantees syntactically valid JSON but no
  schema conformance. Pydantic validation remains mandatory.
- ``prompt_only``: no provider guarantee. The prompt asks for JSON and the
  tolerant parser plus truncation repair are the only defense.

Capabilities are derived per model where providers differ by model (schema
support, temperature rejection, thinking-by-default on Anthropic) and per
provider otherwise. Unknown OpenAI models fall back to ``json_object`` and
unknown providers to ``prompt_only``: the registry fails toward less
guarantee, never more.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderCapabilities:
    """Declared capabilities for one provider/model combination."""

    provider: str
    model: str
    structured_tier: str = "prompt_only"  # schema | json_object | prompt_only
    supports_temperature: bool = True
    thinking_on_by_default: bool = False
    supports_streaming: bool = True
    supports_tool_use: bool = False
    prompt_caching: str = "none"  # explicit | automatic | none

    @property
    def guarantees_schema(self) -> bool:
        """Whether a supplied JSON Schema is enforced by the provider."""
        return self.structured_tier == "schema"


# OpenAI model prefixes with strict JSON Schema structured outputs. Models
# outside this list are treated as json_object only, so a newly released
# model never silently inherits a guarantee it may not have.
_OPENAI_SCHEMA_PREFIXES = ("gpt-4o", "gpt-4.1", "gpt-5", "o3", "o4-mini")

# Anthropic models probed against the structured-outputs grammar in the
# extraction pipeline (all current tiers). Any other Anthropic model is
# still called with output_config by the adapter; the registry records the
# probed set implicitly by returning schema for every claude-* model, and
# the grammar-too-large fallback in the extractor remains the safety net.
def get_capabilities(provider: str, model: str) -> ProviderCapabilities:
    """Return the capability record for a provider/model combination."""
    provider = (provider or "").strip().lower()
    if provider == "claude":
        provider = "anthropic"
    model_id = (model or "").strip()

    if provider == "anthropic":
        from model_config import ModelConfig

        return ProviderCapabilities(
            provider="anthropic",
            model=model_id,
            structured_tier="schema",
            supports_temperature=ModelConfig.supports_temperature(model_id),
            thinking_on_by_default=ModelConfig.thinking_on_by_default(model_id),
            supports_streaming=True,
            supports_tool_use=True,
            prompt_caching="explicit",
        )

    if provider == "openai":
        lowered = model_id.lower()
        tier = "schema" if lowered.startswith(_OPENAI_SCHEMA_PREFIXES) else "json_object"
        return ProviderCapabilities(
            provider="openai",
            model=model_id,
            structured_tier=tier,
            supports_temperature=True,
            thinking_on_by_default=False,
            supports_streaming=True,
            supports_tool_use=True,
            prompt_caching="automatic",
        )

    # Unknown provider (local, OpenAI-compatible endpoints, future): claim
    # nothing beyond streaming text.
    return ProviderCapabilities(
        provider=provider or "unknown",
        model=model_id,
        structured_tier="prompt_only",
        supports_temperature=True,
        thinking_on_by_default=False,
        supports_streaming=True,
        supports_tool_use=False,
        prompt_caching="none",
    )


def ref_provider_name(ref: str) -> str:
    """Provider name for a model reference, by string inspection only.

    Mirrors ModelConfig.parse_model_ref without importing it, so native
    call-site guards keep working where tests substitute ModelConfig.
    Bare non-GPT ids resolve to anthropic (the legacy default).
    """
    text = (ref or "").strip()
    if ":" in text:
        provider = text.partition(":")[0].strip().lower()
        return "anthropic" if provider == "claude" else provider
    if text.lower().startswith(("gpt-", "o1-", "o3-", "o4-", "chatgpt-")):
        return "openai"
    return "anthropic"


def capabilities_for_ref(ref: str) -> ProviderCapabilities:
    """Return capabilities for a "provider:model" or bare model reference."""
    from model_config import ModelConfig

    provider, model = ModelConfig.parse_model_ref(ref)
    return get_capabilities(provider, model)


class UnsupportedCapabilityError(RuntimeError):
    """Raised when a call site requires a capability the configured
    provider/model does not declare. Call sites that still use a
    vendor-native API surface (Anthropic structured outputs, tool use,
    prompt caching) check through here so repointing a tier at another
    provider fails explicitly instead of sending vendor-specific
    parameters to the wrong API."""


def require_capability(ref: str, capability: str) -> ProviderCapabilities:
    """Return capabilities for ``ref`` or raise UnsupportedCapabilityError.

    ``capability`` is one of: schema (structured-output guarantee),
    tool_use, streaming.
    """
    caps = capabilities_for_ref(ref)
    satisfied = {
        "schema": caps.guarantees_schema,
        "tool_use": caps.supports_tool_use,
        "streaming": caps.supports_streaming,
    }.get(capability, False)
    if not satisfied:
        raise UnsupportedCapabilityError(
            f"{caps.provider}:{caps.model} does not declare capability "
            f"{capability!r} (structured_tier={caps.structured_tier}); "
            "repoint the tier or migrate the call site to the provider protocol"
        )
    return caps
