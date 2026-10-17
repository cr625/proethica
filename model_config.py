"""
Central configuration for all AI model references.
This file consolidates all model configurations to avoid scattered references.
"""

import os

class ModelConfig:
    """Centralized configuration for AI models."""
    
    # Anthropic/Claude Models (as of October 2026)
    # See: https://platform.claude.com/docs/en/models/overview
    CLAUDE_MODELS = {
        # Primary models for different use cases: latest model per family.
        "fast": os.getenv("CLAUDE_FAST_MODEL", "claude-haiku-5-5"),
        "powerful": os.getenv("CLAUDE_POWERFUL_MODEL", "claude-fable-5-1"),
        "default": os.getenv("CLAUDE_DEFAULT_MODEL", "claude-sonnet-5-5"),
        # The verification/commit-gate judge. Deliberately a DIFFERENT model from the
        # powerful extraction tier (judge-extractor diversity: with Fable extracting, an
        # Opus judge audits work it did not produce). Vote thresholds were calibrated
        # on Opus 4.8; the Opus 5.5 default requires an offline report-only judge A/B
        # before production repointing. Pin the prior judge with CLAUDE_GATE_MODEL.
        "gate": os.getenv("CLAUDE_GATE_MODEL", "claude-opus-5-5"),

        # Specific versions (for testing/compatibility)
        "sonnet-5.5": "claude-sonnet-5-5",
        "opus-5.5": "claude-opus-5-5",
        "fable-5.1": "claude-fable-5-1",
        "haiku-5.5": "claude-haiku-5-5",
        "sonnet-4.6": "claude-sonnet-4-6",
        "opus-4.8": "claude-opus-4-8",
        "opus-4.7": "claude-opus-4-7",  # Opus 4.7
        "opus-4.6": "claude-opus-4-6",  # Opus 4.6 (Feb 2026)
        "opus-4.5": "claude-opus-4-5-20251101",  # Legacy Opus 4.5 (Nov 2025)
        "sonnet-4.5": "claude-sonnet-4-5-20250929",  # Sonnet 4.5 (Sep 2025)
        "haiku-4.5": "claude-haiku-4-5-20251001",  # Haiku 4.5 (Oct 2025)
        "sonnet-4": "claude-sonnet-4-20250514",  # Previous Sonnet 4
        "opus-4.1": "claude-opus-4-1-20250805",  # Previous Opus 4.1
        "opus-4": "claude-opus-4-20250514",  # Previous Opus 4
    }
    
    # OpenAI Models
    OPENAI_MODELS = {
        "chat": os.getenv("OPENAI_CHAT_MODEL", "gpt-4"),
        "chat_fast": os.getenv("OPENAI_CHAT_FAST_MODEL", "gpt-3.5-turbo"),
        "embedding": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002"),
    }
    
    # Local Models
    LOCAL_MODELS = {
        "embedding": os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
    }
    
    # Models that reject the `temperature` sampling parameter (they manage sampling
    # internally and return HTTP 400 "temperature is deprecated for this model" if it is
    # passed). Callers should omit temperature for these. Opus 4.8 is the first such model.
    TEMPERATURE_UNSUPPORTED = {
        "claude-opus-4-8",
        "claude-sonnet-5",
        "claude-fable-5",
        "claude-opus-5-5",
        "claude-sonnet-5-5",
        "claude-haiku-5-5",
        "claude-fable-5-1",
    }

    # Models that run extended thinking when the `thinking` param is omitted (Fable 5:
    # always-on, cannot be disabled; Sonnet 5: adaptive by default). Thinking tokens
    # draw from the SAME max_tokens budget as the visible text, so a per-call budget
    # sized for the text alone truncates the text mid-generation. Opus 4.8 omits
    # thinking when the param is absent, so it is not in this set.
    THINKING_ON_BY_DEFAULT = {
        "claude-sonnet-5",
        "claude-fable-5",
        "claude-opus-5-5",
        "claude-sonnet-5-5",
        "claude-fable-5-1",
    }

    _TIER_LEGACY_ENV = {
        "fast": "CLAUDE_FAST_MODEL",
        "powerful": "CLAUDE_POWERFUL_MODEL",
        "default": "CLAUDE_DEFAULT_MODEL",
        "gate": "CLAUDE_GATE_MODEL",
    }

    # Model selection based on use case
    @classmethod
    def get_claude_model(cls, use_case="default"):
        """Get the appropriate Claude model for a use case.

        Tier values are read from the legacy CLAUDE_<TIER>_MODEL variable at
        call time, so a repoint after import is observed; the CLAUDE_MODELS
        entry remains the fallback. Single resolution authority for tiers is
        get_tier_ref, which prefers LLM_<TIER>_REF over this legacy path.
        """
        env_name = cls._TIER_LEGACY_ENV.get(use_case)
        if env_name:
            override = os.getenv(env_name)
            if override and override.strip():
                return override.strip()
        return cls.CLAUDE_MODELS.get(use_case, cls.CLAUDE_MODELS["default"])

    # ------------------------------------------------------------------
    # Provider-qualified tier references (LLM provider abstraction)
    # ------------------------------------------------------------------
    # A tier reference is "provider:model" (for example
    # "anthropic:claude-sonnet-4-6" or "openai:gpt-4o") or a bare model id.
    # Bare ids keep legacy behavior: "claude-*" resolves to anthropic,
    # "gpt-*" / "o1-*" / "o3-*" / "o4-*" to openai, anything else to
    # anthropic (the historical default in LLMManager._detect_provider).
    # Tier refs are read from LLM_<TIER>_REF at call time so a tier can be
    # repointed without code changes; the legacy CLAUDE_<TIER>_MODEL values
    # in CLAUDE_MODELS remain the fallback and are unchanged.

    _TIER_ENV = {
        "fast": "LLM_FAST_REF",
        "default": "LLM_DEFAULT_REF",
        "powerful": "LLM_POWERFUL_REF",
        "gate": "LLM_GATE_REF",
    }

    @staticmethod
    def parse_model_ref(ref):
        """Split a model reference into (provider, model_id).

        Accepts "provider:model" or a bare model id. The provider is
        lower-cased; "claude" is normalized to "anthropic".
        """
        text = (ref or "").strip()
        if ":" in text:
            provider, _, model = text.partition(":")
            provider = provider.strip().lower()
            if provider == "claude":
                provider = "anthropic"
            return provider, model.strip()
        lowered = text.lower()
        if lowered.startswith(("gpt-", "o1-", "o3-", "o4-", "chatgpt-")):
            return "openai", text
        return "anthropic", text

    @classmethod
    def get_tier_ref(cls, tier="default"):
        """Return the "provider:model" reference for a tier.

        Resolution order: LLM_<TIER>_REF environment variable, then the
        legacy CLAUDE_MODELS entry for the tier (anthropic-qualified).
        """
        env_name = cls._TIER_ENV.get(tier)
        if env_name:
            override = os.getenv(env_name)
            if override and override.strip():
                provider, model = cls.parse_model_ref(override)
                return f"{provider}:{model}"
        model = cls.get_claude_model(tier)
        provider, model_id = cls.parse_model_ref(model)
        return f"{provider}:{model_id}"

    @classmethod
    def get_tier_model(cls, tier="default"):
        """Return the bare model id for a tier, on any provider."""
        return cls.parse_model_ref(cls.get_tier_ref(tier))[1]

    @classmethod
    def get_tier_provider(cls, tier="default"):
        """Return the provider name for a tier (anthropic, openai, ...)."""
        return cls.parse_model_ref(cls.get_tier_ref(tier))[0]

    @classmethod
    def supports_temperature(cls, model: str) -> bool:
        """Whether `model` accepts the `temperature` parameter (some newer models reject it)."""
        return model not in cls.TEMPERATURE_UNSUPPORTED

    @classmethod
    def thinking_on_by_default(cls, model: str) -> bool:
        """Whether `model` spends thinking tokens out of max_tokens without being asked."""
        return model in cls.THINKING_ON_BY_DEFAULT
    
    @classmethod
    def get_openai_model(cls, use_case="chat"):
        """Get the appropriate OpenAI model for a use case."""
        return cls.OPENAI_MODELS.get(use_case, cls.OPENAI_MODELS["chat"])
    
    @classmethod
    def get_embedding_model(cls, provider="local"):
        """Get the appropriate embedding model for a provider."""
        if provider == "openai":
            return cls.OPENAI_MODELS["embedding"]
        return cls.LOCAL_MODELS["embedding"]
    
    # Backward compatibility
    @classmethod
    def get_default_model(cls):
        """Get the default model (for backward compatibility)."""
        # Check old environment variables first
        old_model = os.getenv("CLAUDE_MODEL_VERSION") or os.getenv("ANTHROPIC_MODEL")
        if old_model:
            # Map old model names to new ones
            model_mapping = {
                "claude-3-7-sonnet-20250219": "claude-sonnet-5-5",
                "claude-3-sonnet-20240229": "claude-sonnet-5-5",
                "claude-3-opus-20240229": "claude-opus-5-5",
                "claude-3.5-sonnet-latest": "claude-sonnet-5-5",
                "claude-3.5-opus-latest": "claude-opus-5-5",
                "claude-opus-4-20250514": "claude-opus-5-5",
                "claude-sonnet-4-20250514": "claude-sonnet-5-5",
                "claude-opus-4-1-20250805": "claude-opus-5-5",
                "claude-sonnet-4-5-20250929": "claude-sonnet-5-5",
            }
            return model_mapping.get(old_model, old_model)
        return cls.get_claude_model("default")