"""
LLM (Language Model) services for ProEthica.

Provides centralized LLM management with:
- Unified interface across providers (Anthropic, OpenAI)
- Consistent timeout and retry handling
- Token usage tracking
- Model switching capability

Usage:
    from app.services.llm import get_llm_manager

    llm = get_llm_manager()
    response = llm.complete(
        messages=[{"role": "user", "content": "Your prompt"}],
        max_tokens=2000
    )
    print(response.text)

Provider abstraction (protocol, adapters, capabilities, factory) resolves
"provider:model" references and tier names to vendor adapters; see
capabilities.py for the structured-output guarantee ladder.
"""

from .manager import LLMManager, get_llm_manager, reset_llm_manager
from .response import LLMResponse, Usage
from .config import LLMConfig
from .capabilities import (
    ProviderCapabilities, UnsupportedCapabilityError, capabilities_for_ref,
    get_capabilities, ref_provider_name, require_capability,
)
from .factory import get_provider, get_tier_provider
from .protocol import BaseLLMProvider, ToolLoopResult

__all__ = [
    'LLMManager',
    'get_llm_manager',
    'reset_llm_manager',
    'LLMResponse',
    'Usage',
    'LLMConfig',
    'ProviderCapabilities',
    'UnsupportedCapabilityError',
    'capabilities_for_ref',
    'get_capabilities',
    'ref_provider_name',
    'require_capability',
    'get_provider',
    'get_tier_provider',
    'BaseLLMProvider',
    'ToolLoopResult',
]
