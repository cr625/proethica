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
"""

from .manager import LLMManager, get_llm_manager
from .response import LLMResponse, Usage
from .config import LLMConfig

__all__ = [
    'LLMManager',
    'get_llm_manager',
    'LLMResponse',
    'Usage',
    'LLMConfig'
]
