"""
Central configuration for all AI model references.
This file consolidates all model configurations to avoid scattered references.
"""

import os

class ModelConfig:
    """Centralized configuration for AI models."""
    
    # Anthropic/Claude Models (as of January 2025)
    # See: https://docs.anthropic.com/en/docs/about-claude/models/overview
    CLAUDE_MODELS = {
        # Primary models for different use cases
        "fast": os.getenv("CLAUDE_FAST_MODEL", "claude-sonnet-4-20250514"),
        "powerful": os.getenv("CLAUDE_POWERFUL_MODEL", "claude-opus-4-20250514"),
        "default": os.getenv("CLAUDE_DEFAULT_MODEL", "claude-sonnet-4-20250514"),
        
        # Specific versions (for testing/compatibility)
        "sonnet-4": "claude-sonnet-4-20250514",
        "opus-4": "claude-opus-4-20250514",
        "haiku": "claude-3-haiku-20240307",  # Legacy, still available
        
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
                "claude-3-opus-20240229": "claude-opus-4-20250514",
                "claude-3.5-sonnet-latest": "claude-sonnet-4-20250514",
                "claude-3.5-opus-latest": "claude-opus-4-20250514",
            }
            return model_mapping.get(old_model, old_model)
        return cls.get_claude_model("default")