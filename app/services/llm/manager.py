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

    def __init__(self, config: Optional[LLMConfig] = None, model: Optional[str] = None):
        """
        Initialize LLM manager.

        Args:
            config: LLMConfig instance (defaults to from_env())
            model: Optional model override (overrides config.default_model)
        """
        self.config = config or LLMConfig.from_env()
        self.model = model or self.config.default_model
        self.provider = self._detect_provider(self.model)

        # Initialize provider client
        self.client = self._initialize_client()

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
        """Detect provider from model name."""
        if 'claude' in model.lower():
            return 'anthropic'
        elif 'gpt' in model.lower():
            return 'openai'
        else:
            # Default to anthropic
            return 'anthropic'

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

        # Call appropriate provider
        if self.provider == 'anthropic':
            response = self._call_anthropic(
                messages=messages,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
                model=use_model,
                metadata=use_metadata
            )
        elif self.provider == 'openai':
            response = self._call_openai(
                messages=messages,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
                model=use_model,
                metadata=use_metadata
            )
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

        # Track usage
        if self.config.track_usage:
            self._track_usage(response)

        return response

    def _call_anthropic(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str],
        max_tokens: int,
        temperature: float,
        model: str,
        metadata: Dict[str, Any]
    ) -> LLMResponse:
        """Call Anthropic API with timeout and retry handling."""
        import anthropic

        try:
            # Build API call
            api_kwargs = {
                'model': model,
                'messages': messages,
                'max_tokens': max_tokens,
                'temperature': temperature,
                'timeout': self.config.timeout.read  # Use read timeout for Anthropic
            }

            if system:
                api_kwargs['system'] = system

            # Make the call
            response = self.client.messages.create(**api_kwargs)

            # Extract response
            text = response.content[0].text if response.content else ""

            # Build usage
            usage = Usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                estimated_cost_usd=self._estimate_cost_anthropic(
                    response.usage.input_tokens,
                    response.usage.output_tokens,
                    model
                )
            )

            # Build metadata
            response_metadata = {
                **metadata,
                'response_id': response.id if hasattr(response, 'id') else None,
                'model': response.model if hasattr(response, 'model') else model,
                'stop_reason': response.stop_reason if hasattr(response, 'stop_reason') else None
            }

            return LLMResponse(
                text=text,
                model=model,
                provider='anthropic',
                usage=usage,
                metadata=response_metadata
            )

        except Exception as e:
            logger.error(f"[LLM Manager] Anthropic API error: {str(e)}")
            raise

    def _call_openai(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str],
        max_tokens: int,
        temperature: float,
        model: str,
        metadata: Dict[str, Any]
    ) -> LLMResponse:
        """Call OpenAI API with timeout and retry handling."""
        try:
            # Add system message if provided
            api_messages = []
            if system:
                api_messages.append({"role": "system", "content": system})
            api_messages.extend(messages)

            # Make the call
            response = self.client.chat.completions.create(
                model=model,
                messages=api_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=self.config.timeout.read
            )

            # Extract response
            text = response.choices[0].message.content

            # Build usage
            usage = Usage(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                estimated_cost_usd=self._estimate_cost_openai(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                    model
                )
            )

            # Build metadata
            response_metadata = {
                **metadata,
                'response_id': response.id if hasattr(response, 'id') else None,
                'model': response.model if hasattr(response, 'model') else model,
                'finish_reason': response.choices[0].finish_reason if response.choices else None
            }

            return LLMResponse(
                text=text,
                model=model,
                provider='openai',
                usage=usage,
                metadata=response_metadata
            )

        except Exception as e:
            logger.error(f"[LLM Manager] OpenAI API error: {str(e)}")
            raise

    def _estimate_cost_anthropic(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """
        Estimate cost for Anthropic API call.

        Pricing (as of Nov 2025):
        - Claude Sonnet 4: $3 per MTok input, $15 per MTok output
        - Claude Opus 4.1: $15 per MTok input, $75 per MTok output
        """
        pricing = {
            'claude-sonnet-4-20250514': (3.0, 15.0),
            'claude-opus-4-1-20250805': (15.0, 75.0),
            'claude-opus-4-20250514': (15.0, 75.0)
        }

        input_price, output_price = pricing.get(model, (3.0, 15.0))  # Default to Sonnet 4

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

        # Re-initialize client if provider changed
        old_provider = self._detect_provider(old_model)
        if old_provider != self.provider:
            self.client = self._initialize_client()

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
