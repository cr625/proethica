"""
Mock modules for ProEthica testing.

Provides mock LLM responses and other test utilities to enable
fast unit testing without actual LLM API calls.
"""

from .llm_client import MockLLMClient, MockLLMResponse

__all__ = ['MockLLMClient', 'MockLLMResponse']
