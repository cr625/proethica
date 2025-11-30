"""
Mock LLM Provider for UI Testing

Provides mock LLM client when MOCK_LLM_ENABLED=true in configuration.
This allows testing the full UI flow without making real LLM API calls.

IMPORTANT: This module is EXPLICIT about data sources:
- Mock mode must be explicitly enabled (MOCK_LLM_ENABLED=true)
- Real LLM errors are NEVER silently converted to mock data
- Data source is always trackable via get_current_data_source()

Usage in extractors:
    from app.services.extraction.mock_llm_provider import (
        get_llm_client_for_extraction,
        get_current_data_source,
        DataSource
    )

    class DualRoleExtractor:
        def __init__(self, llm_client=None):
            self.llm_client = llm_client or get_llm_client_for_extraction()
            self.data_source = get_current_data_source()
"""

import os
import logging
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class DataSource(Enum):
    """Enum to track where extraction data comes from."""
    REAL_LLM = "real_llm"      # Live API call to real LLM
    MOCK_LLM = "mock_llm"      # Mock fixtures for testing
    CACHED = "cached"          # Previously saved response from database
    UNKNOWN = "unknown"        # Source not determined


class ExtractionError(Exception):
    """Base exception for extraction errors. NEVER silently catch these."""
    pass


class LLMConnectionError(ExtractionError):
    """LLM API connection failed."""
    pass


class LLMResponseError(ExtractionError):
    """LLM returned invalid/unparseable response."""
    pass


class MockModeError(ExtractionError):
    """Mock mode enabled but mock client unavailable."""
    pass

_mock_client_instance = None


def is_mock_mode_enabled() -> bool:
    """Check if mock LLM mode is enabled."""
    # Check environment variable directly (works before Flask app context)
    env_value = os.environ.get('MOCK_LLM_ENABLED', 'false').lower()
    if env_value == 'true':
        return True

    # Also check Flask config if available
    try:
        from flask import current_app
        if current_app and current_app.config.get('MOCK_LLM_ENABLED'):
            return True
    except RuntimeError:
        # No Flask app context
        pass

    return False


def get_mock_llm_client():
    """Get or create the singleton mock LLM client."""
    global _mock_client_instance

    if _mock_client_instance is None:
        try:
            from tests.mocks.llm_client import MockLLMClient
            _mock_client_instance = MockLLMClient()
            logger.info("Mock LLM client initialized for UI testing")
        except ImportError as e:
            logger.error(f"Could not import MockLLMClient: {e}")
            return None

    return _mock_client_instance


def get_llm_client_for_extraction(llm_client=None):
    """
    Get the appropriate LLM client for extraction.

    If llm_client is provided (dependency injection), use it.
    If MOCK_LLM_ENABLED is true, return mock client.
    Otherwise return None (extractors will use their default real client).

    Args:
        llm_client: Optional injected client (takes precedence)

    Returns:
        LLM client instance or None
    """
    # Dependency injection takes precedence
    if llm_client is not None:
        return llm_client

    # Check for mock mode
    if is_mock_mode_enabled():
        mock_client = get_mock_llm_client()
        if mock_client:
            return mock_client
        logger.warning("Mock mode enabled but could not create mock client")

    return None


def reset_mock_client():
    """Reset the mock client instance (useful for testing)."""
    global _mock_client_instance
    _mock_client_instance = None


def get_current_data_source() -> DataSource:
    """
    Get the current data source based on configuration.

    Returns:
        DataSource enum indicating mock vs real mode
    """
    if is_mock_mode_enabled():
        return DataSource.MOCK_LLM
    return DataSource.REAL_LLM


def get_data_source_display() -> dict:
    """
    Get display information about current data source for UI.

    Returns:
        dict with 'source', 'label', and 'is_mock' keys
    """
    source = get_current_data_source()

    if source == DataSource.MOCK_LLM:
        return {
            'source': source.value,
            'label': 'MOCK DATA (Testing Mode)',
            'is_mock': True,
            'warning': 'Responses are from test fixtures, not real LLM'
        }
    elif source == DataSource.CACHED:
        return {
            'source': source.value,
            'label': 'Cached Response',
            'is_mock': False,
            'warning': 'Using previously saved response'
        }
    else:
        return {
            'source': source.value,
            'label': 'Live LLM',
            'is_mock': False,
            'warning': None
        }
