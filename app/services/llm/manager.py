"""
Centralized LLM manager for ProEthica.

Provides unified interface for LLM interactions with consistent timeout handling,
model switching, and usage tracking.

Addresses issues documented in CLAUDE.md:
- Sonnet 4.5 timeout issues → configurable timeouts
- 76 hardcoded model references → centralized model selection
- Inconsistent error handling → unified retry/fallback logic
- URI bloat in prompts → helper methods for sanitization
"""

import logging
import os
import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from .config import LLMConfig
from .response import LLMResponse, Usage

logger = logging.getLogger(__name__)


class LLMManager:
    """
    Centralized LLM management for ProEthica.

    Supports:
    - Anthropic (Claude) - primary provider
    - OpenAI (GPT) - fallback provider
    - Consistent timeout and retry handling
    - Token usage tracking
    - Dynamic model switching

    Example:
        llm = LLMManager()
        response = llm.complete(
            messages=[{"role": "user", "content": "Extract roles..."}],
            max_tokens=2000
        )
        print(response.text)
    """

    def __init__(self, config: Optional[LLMConfig] = None, model: Optional[str] = None,
                 providers: Optional[Dict[str, Any]] = None):
        """
        Initialize LLM manager.

        Args:
            config: LLMConfig instance (defaults to from_env())
            model: Optional model override (overrides config.default_model)
            providers: Optional {provider_name: provider adapter} map for
                dependency injection (tests, pre-built clients). When given,
                no SDK client is constructed at initialization.
        """
        self.config = config or LLMConfig.from_env()
        self.model = model or self.config.default_model
        self.provider = self._detect_provider(self.model)
        self._injected_providers = providers
        self._provider_cache: Dict[str, Any] = {}

        # Initialize provider client (skipped when providers are injected)
        self.client = None if providers is not None else self._initialize_client()

        # Usage tracking
        self.usage_stats = {
            'total_calls': 0,
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_cost_usd': 0.0,
            'calls_by_model': {}
        }

        logger.info(f"[LLM Manager] Initialized with model={self.model}, provider={self.provider}")

    def _detect_provider(self, model: str) -> str:
        """Detect provider from a model reference ("provider:model" or bare id)."""
        from model_config import ModelConfig

        return ModelConfig.parse_model_ref(model)[0]

    def _provider_for(self, model: str):
        """Return the provider adapter for a model, dispatching per call.

        A per-call model override on a different provider routes to that
        provider; the construction-time provider no longer pins routing
        (the previous behavior sent OpenAI model ids to the Anthropic API
        and vice versa).
        """
        provider_name = self._detect_provider(model)
        if self._injected_providers is not None:
            adapter = self._injected_providers.get(provider_name)
            if adapter is None:
                raise ValueError(f"No provider injected for {provider_name!r}")
            return adapter
        if provider_name not in self._provider_cache:
            from .factory import get_provider

            # Reuse the already-initialized SDK client when the provider
            # matches the construction-time one.
            client = self.client if provider_name == self.provider else None
            self._provider_cache[provider_name] = get_provider(model, client=client)
        return self._provider_cache[provider_name]

    @staticmethod
    def _is_transient(exc: BaseException) -> bool:
        """Whether an LLM call failure is worth retrying.

        Vendor connection/timeout errors are matched by class name so the
        manager does not import either SDK to classify them.
        """
        return isinstance(exc, (ConnectionError, TimeoutError)) or (
            type(exc).__name__ in ("APIConnectionError", "APITimeoutError")
        )

    def _with_retry(self, call):
        """Run one LLM call under the configured tenacity retry policy.

        Only transient connection/timeout failures retry; parse and
        validation errors propagate on the first attempt.
        """
        attempts = max(1, self.config.max_retries)
        if attempts == 1:
            return call()
        from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential

        for attempt in Retrying(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=self.config.retry_delay,
                                  min=self.config.retry_delay, max=30),
            retry=retry_if_exception(self._is_transient),
            reraise=True,
        ):
            with attempt:
                return call()

    def _initialize_client(self):
        """Initialize the appropriate LLM client."""
        if self.provider == 'anthropic':
            try:
                import anthropic
                api_key = os.getenv('ANTHROPIC_API_KEY')
                if not api_key:
                    raise ValueError("ANTHROPIC_API_KEY not found in environment")
                return anthropic.Anthropic(api_key=api_key)
            except ImportError:
                raise ImportError("anthropic package not installed. Run: uv pip install anthropic")

        elif self.provider == 'openai':
            try:
                import openai
                api_key = os.getenv('OPENAI_API_KEY')
                if not api_key:
                    raise ValueError("OPENAI_API_KEY not found in environment")
                return openai.OpenAI(api_key=api_key)
            except ImportError:
                raise ImportError("openai package not installed. Run: uv pip install openai")

        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 1.0,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> LLMResponse:
        """
        Unified completion interface.

        Args:
            messages: List of {"role": "user"|"assistant", "content": str}
            system: Optional system prompt
            max_tokens: Maximum response tokens
            temperature: Sampling temperature (0.0-1.0)
            model: Optional model override
            metadata: Optional metadata for tracking/logging

        Returns:
            LLMResponse with text, usage, metadata

        Raises:
            Exception: On LLM call failure after retries
        """
        use_model = model or self.model
        use_metadata = metadata or {}
        use_metadata['requested_at'] = datetime.utcnow().isoformat()

        if self.config.log_requests:
            logger.debug(f"[LLM Manager] Calling {use_model} with {len(messages)} messages")
            logger.debug(f"[LLM Manager] System: {system[:100] if system else 'None'}...")
            logger.debug(f"[LLM Manager] First message: {messages[0]['content'][:100] if messages else 'None'}...")

        # Dispatch on the per-call model, not the construction-time
        # provider, so a model override reaches its own provider.
        adapter = self._provider_for(use_model)
        response = self._with_retry(lambda: adapter.complete(
            messages=messages,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            model=use_model,
        ))
        response.metadata = {**use_metadata, **response.metadata}
        if response.usage.estimated_cost_usd is None:
            estimator = (
                self._estimate_cost_anthropic
                if response.provider == "anthropic"
                else self._estimate_cost_openai
            )
            response.usage.estimated_cost_usd = estimator(
                response.usage.input_tokens, response.usage.output_tokens, use_model
            )

        # Track usage
        if self.config.track_usage:
            self._track_usage(response)

        return response

    def stream_text(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.1,
        model: Optional[str] = None,
    ) -> str:
        """Stream one completion to text through the per-call provider."""
        use_model = model or self.model
        return self._provider_for(use_model).stream_text(
            messages=messages, system=system, max_tokens=max_tokens,
            temperature=temperature, model=use_model,
        )

    def stream_complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.1,
        model: Optional[str] = None,
    ):
        """Stream one completion to a full LLMResponse via the per-call provider."""
        use_model = model or self.model
        response = self._provider_for(use_model).stream_complete(
            messages=messages, system=system, max_tokens=max_tokens,
            temperature=temperature, model=use_model,
        )
        if self.config.track_usage:
            self._track_usage(response)
        return response

    def structured(
        self,
        messages: List[Dict[str, str]],
        schema: Dict[str, Any],
        system: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.1,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return parsed structured JSON through the capability ladder."""
        use_model = model or self.model
        return self._provider_for(use_model).structured(
            messages=messages, schema=schema, system=system,
            max_tokens=max_tokens, temperature=temperature, model=use_model,
        )

    def _estimate_cost_anthropic(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """
        Estimate cost for Anthropic API call.

        Pricing (as of Oct 2026, platform.claude.com/docs/en/models/overview):
        - Claude Sonnet 5.5: $2 per MTok input, $10 per MTok output
        - Claude Opus 5.5: $4 per MTok input, $20 per MTok output
        - Claude Fable 5.1: $10 per MTok input, $50 per MTok output
        """
        pricing = {
            'claude-sonnet-5-5': (2.0, 10.0),
            'claude-opus-5-5': (4.0, 20.0),
            'claude-fable-5-1': (10.0, 50.0),
            'claude-sonnet-4-6': (3.0, 15.0),
            'claude-opus-4-6': (15.0, 75.0),
        }

        input_price, output_price = pricing.get(model, (2.0, 10.0))  # Default to Sonnet 5.5

        cost = (input_tokens / 1_000_000 * input_price) + (output_tokens / 1_000_000 * output_price)
        return round(cost, 6)

    def _estimate_cost_openai(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """
        Estimate cost for OpenAI API call.

        Pricing (as of Nov 2025):
        - GPT-4: $30 per MTok input, $60 per MTok output
        - GPT-3.5-turbo: $0.5 per MTok input, $1.5 per MTok output
        """
        pricing = {
            'gpt-4': (30.0, 60.0),
            'gpt-4-turbo': (10.0, 30.0),
            'gpt-3.5-turbo': (0.5, 1.5)
        }

        input_price, output_price = pricing.get(model, (10.0, 30.0))  # Default to GPT-4 Turbo

        cost = (input_tokens / 1_000_000 * input_price) + (output_tokens / 1_000_000 * output_price)
        return round(cost, 6)

    def _track_usage(self, response: LLMResponse):
        """Track token usage and costs."""
        self.usage_stats['total_calls'] += 1
        self.usage_stats['total_input_tokens'] += response.usage.input_tokens
        self.usage_stats['total_output_tokens'] += response.usage.output_tokens
        if response.usage.estimated_cost_usd:
            self.usage_stats['total_cost_usd'] += response.usage.estimated_cost_usd

        # Track by model
        model_key = response.model
        if model_key not in self.usage_stats['calls_by_model']:
            self.usage_stats['calls_by_model'][model_key] = {
                'calls': 0,
                'input_tokens': 0,
                'output_tokens': 0,
                'cost_usd': 0.0
            }

        self.usage_stats['calls_by_model'][model_key]['calls'] += 1
        self.usage_stats['calls_by_model'][model_key]['input_tokens'] += response.usage.input_tokens
        self.usage_stats['calls_by_model'][model_key]['output_tokens'] += response.usage.output_tokens
        if response.usage.estimated_cost_usd:
            self.usage_stats['calls_by_model'][model_key]['cost_usd'] += response.usage.estimated_cost_usd

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics."""
        return self.usage_stats.copy()

    def parse_json_response(self, text: str) -> Any:
        """
        Parse JSON from LLM response, handling markdown code blocks.

        Common issue (documented in CLAUDE.md): LLMs often return JSON
        wrapped in markdown code blocks like: ```json {...} ```

        Args:
            text: Response text potentially containing JSON

        Returns:
            Parsed JSON object

        Raises:
            json.JSONDecodeError: If parsing fails
        """
        # Try to extract from markdown code block first
        code_block_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', text)
        if code_block_match:
            text = code_block_match.group(1).strip()

        # Parse JSON
        return json.loads(text)

    def switch_model(self, model: str):
        """
        Switch to a different model.

        Useful for A/B testing or using different models for different tasks.

        Args:
            model: New model identifier
        """
        old_model = self.model
        self.model = model
        self.provider = self._detect_provider(model)

        # Re-initialize client if provider changed (not when providers
        # were injected: routing is per call and needs no client swap)
        old_provider = self._detect_provider(old_model)
        if old_provider != self.provider and self._injected_providers is None:
            self.client = self._initialize_client()
            self._provider_cache.pop(old_provider, None)

        logger.info(f"[LLM Manager] Switched model: {old_model} → {model} (provider: {self.provider})")


# Singleton for easy access
_llm_manager: Optional[LLMManager] = None


def get_llm_manager(model: Optional[str] = None, config: Optional[LLMConfig] = None) -> LLMManager:
    """
    Get or create singleton LLM manager.

    Args:
        model: Optional model override
        config: Optional config override

    Returns:
        LLMManager instance
    """
    global _llm_manager

    if _llm_manager is None:
        _llm_manager = LLMManager(config=config, model=model)
    elif model and model != _llm_manager.model:
        # If model is different, switch to it
        _llm_manager.switch_model(model)

    return _llm_manager


def reset_llm_manager():
    """Reset singleton (useful for testing)."""
    global _llm_manager
    _llm_manager = None
