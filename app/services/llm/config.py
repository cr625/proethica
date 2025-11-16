"""
LLM configuration.

Centralizes all LLM-related configuration including timeouts, retries, and model selection.
"""

import os
from dataclasses import dataclass, field
from typing import List
from httpx import Timeout


@dataclass
class LLMConfig:
    """
    Configuration for LLM manager.

    Handles model selection, timeouts, retries, and provider settings.
    Can be loaded from environment variables or set directly.
    """

    # Model selection
    default_model: str = "claude-sonnet-4-20250514"
    fast_model: str = "claude-sonnet-4-20250514"
    powerful_model: str = "claude-opus-4-1-20250805"

    # Timeout configuration (addresses Sonnet 4.5 timeout issues documented in CLAUDE.md)
    connect_timeout: float = 10.0
    read_timeout: float = 180.0  # 3 minutes for complex reasoning
    write_timeout: float = 180.0
    pool_timeout: float = 180.0

    # Retry configuration
    max_retries: int = 3
    retry_delay: float = 2.0  # Base delay for exponential backoff

    # Provider settings
    enable_provider_fallback: bool = True
    fallback_providers: List[str] = field(default_factory=lambda: ["anthropic", "openai"])

    # Usage tracking
    track_usage: bool = True
    log_requests: bool = False  # Set True for debugging

    @property
    def timeout(self) -> Timeout:
        """Get httpx Timeout object."""
        return Timeout(
            connect=self.connect_timeout,
            read=self.read_timeout,
            write=self.write_timeout,
            pool=self.pool_timeout
        )

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """
        Load configuration from environment variables.

        Environment variables:
            LLM_DEFAULT_MODEL: Default model to use
            LLM_READ_TIMEOUT: Read timeout in seconds (default 180)
            LLM_MAX_RETRIES: Maximum retry attempts (default 3)
            LLM_TRACK_USAGE: Enable usage tracking (default true)
            LLM_LOG_REQUESTS: Enable request logging (default false)
        """
        from models import ModelConfig

        return cls(
            default_model=os.getenv("LLM_DEFAULT_MODEL") or ModelConfig.get_default_model(),
            fast_model=os.getenv("LLM_FAST_MODEL") or ModelConfig.get_claude_model("fast"),
            powerful_model=os.getenv("LLM_POWERFUL_MODEL") or ModelConfig.get_claude_model("powerful"),
            read_timeout=float(os.getenv("LLM_READ_TIMEOUT", "180")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
            track_usage=os.getenv("LLM_TRACK_USAGE", "true").lower() == "true",
            log_requests=os.getenv("LLM_LOG_REQUESTS", "false").lower() == "true"
        )

    @classmethod
    def for_testing(cls) -> "LLMConfig":
        """Create configuration optimized for testing (shorter timeouts)."""
        return cls(
            read_timeout=30.0,
            max_retries=1,
            track_usage=False,
            log_requests=True
        )
