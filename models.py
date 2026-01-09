"""
Central configuration for all AI model references.
This file consolidates all model configurations to avoid scattered references.
"""

import os

class ModelConfig:
    """Centralized configuration for AI models."""
    
    # Anthropic/Claude Models (as of January 2026)
    # See: https://docs.anthropic.com/en/docs/about-claude/models/overview
    CLAUDE_MODELS = {
        # Primary models for different use cases
        "fast": os.getenv("CLAUDE_FAST_MODEL", "claude-haiku-4-5-20251022"),
        "powerful": os.getenv("CLAUDE_POWERFUL_MODEL", "claude-opus-4-5-20251124"),
        "default": os.getenv("CLAUDE_DEFAULT_MODEL", "claude-sonnet-4-5-20250929"),

        # Specific versions (for testing/compatibility)
        "opus-4.5": "claude-opus-4-5-20251124",  # Latest Opus 4.5 (Nov 2025)
        "sonnet-4.5": "claude-sonnet-4-5-20250929",  # Latest Sonnet 4.5 (Sep 2025)
        "haiku-4.5": "claude-haiku-4-5-20251022",  # Latest Haiku 4.5 (Oct 2025)
        "sonnet-4": "claude-sonnet-4-20250514",  # Previous Sonnet 4
        "opus-4.1": "claude-opus-4-1-20250805",  # Previous Opus 4.1
        "opus-4": "claude-opus-4-20250514",  # Previous Opus 4
        "haiku-3.5": "claude-3-5-haiku-20241022",  # Legacy Haiku 3.5
        
        # Legacy models (deprecated, for backward compatibility only)
        "legacy_sonnet": "claude-3-sonnet-20240229",
        "legacy_opus": "claude-3-opus-20240229",
        "sonnet-3.5": "claude-3.5-sonnet-latest",
        "opus-3.5": "claude-3.5-opus-latest",
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
    
    # Model selection based on use case
    @classmethod
    def get_claude_model(cls, use_case="default"):
        """Get the appropriate Claude model for a use case."""
        return cls.CLAUDE_MODELS.get(use_case, cls.CLAUDE_MODELS["default"])
    
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
                "claude-3-7-sonnet-20250219": "claude-sonnet-4-20250514",
                "claude-3-sonnet-20240229": "claude-sonnet-4-20250514",
                "claude-3-opus-20240229": "claude-opus-4-1-20250805",  # Map to latest Opus 4.1
                "claude-3.5-sonnet-latest": "claude-sonnet-4-20250514",
                "claude-3.5-opus-latest": "claude-opus-4-1-20250805",  # Map to latest Opus 4.1
                "claude-opus-4-20250514": "claude-opus-4-1-20250805",  # Auto-upgrade to Opus 4.1
            }
            return model_mapping.get(old_model, old_model)
        return cls.get_claude_model("default")