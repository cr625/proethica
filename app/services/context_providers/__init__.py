"""
Context providers package.

This package contains providers that generate context for the LLM
about different aspects of the application state.
"""

from app.services.context_providers.base_provider import ContextProvider
from app.services.context_providers.default_provider import DefaultContextProvider

__all__ = [
    'ContextProvider',
    'DefaultContextProvider'
]
