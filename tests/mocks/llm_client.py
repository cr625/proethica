"""
Mock LLM Client for Testing

Provides a mock LLM client that returns pre-defined responses from JSON fixtures.
This enables fast unit testing without actual API calls.

Usage:
    from tests.mocks import MockLLMClient

    # Create client with default fixtures
    client = MockLLMClient()

    # Or specify custom fixture directory
    client = MockLLMClient(fixture_dir='/path/to/fixtures')

    # Use in extractor via dependency injection
    extractor = DualRoleExtractor(llm_client=client)
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable

logger = logging.getLogger(__name__)


@dataclass
class MockLLMResponse:
    """Represents a mock LLM response matching the structure of real responses."""
    content: str
    model: str = "mock-claude-3"
    stop_reason: str = "end_turn"
    input_tokens: int = 100
    output_tokens: int = 500

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'content': self.content,
            'model': self.model,
            'stop_reason': self.stop_reason,
            'usage': {
                'input_tokens': self.input_tokens,
                'output_tokens': self.output_tokens
            }
        }


@dataclass
class MockLLMClient:
    """
    Mock LLM client that returns pre-defined responses from JSON fixtures.

    Fixtures are organized by:
    - extraction_type: roles, states, resources, principles, etc.
    - section_type: facts, discussion

    Fixture naming convention:
    - {extraction_type}_{section_type}.json
    - Example: roles_facts.json, principles_discussion.json
    """

    fixture_dir: Path = field(default_factory=lambda: Path(__file__).parent / 'responses')
    _fixtures: Dict[str, Any] = field(default_factory=dict, repr=False)
    _call_log: List[Dict[str, Any]] = field(default_factory=list, repr=False)

    def __post_init__(self):
        """Load all fixtures on initialization."""
        self.fixture_dir = Path(self.fixture_dir)
        self._load_fixtures()

    def _load_fixtures(self) -> None:
        """Load all JSON fixtures from the fixture directory."""
        if not self.fixture_dir.exists():
            logger.warning(f"Fixture directory does not exist: {self.fixture_dir}")
            return

        for fixture_file in self.fixture_dir.glob('*.json'):
            fixture_name = fixture_file.stem  # e.g., "roles_facts"
            try:
                with open(fixture_file, 'r') as f:
                    self._fixtures[fixture_name] = json.load(f)
                logger.debug(f"Loaded fixture: {fixture_name}")
            except json.JSONDecodeError as e:
                logger.error(f"Error loading fixture {fixture_file}: {e}")

    def get_fixture(self, extraction_type: str, section_type: str = 'facts') -> Optional[Dict[str, Any]]:
        """
        Get a fixture by extraction type and section type.

        Args:
            extraction_type: Type of extraction (roles, states, etc.)
            section_type: Section type (facts, discussion)

        Returns:
            Fixture data or None if not found
        """
        fixture_key = f"{extraction_type}_{section_type}"

        # Try exact match first
        if fixture_key in self._fixtures:
            return self._fixtures[fixture_key]

        # Try extraction type only (for step4/step5 fixtures)
        if extraction_type in self._fixtures:
            return self._fixtures[extraction_type]

        logger.warning(f"No fixture found for: {fixture_key}")
        return None

    def call(
        self,
        prompt: str,
        extraction_type: str = None,
        section_type: str = 'facts',
        model: str = None,
        **kwargs
    ) -> MockLLMResponse:
        """
        Simulate an LLM call by returning a fixture response.

        Args:
            prompt: The prompt (logged but not used for response selection)
            extraction_type: Type of extraction to return fixture for
            section_type: Section type (facts or discussion)
            model: Model name (ignored, for API compatibility)
            **kwargs: Additional arguments (ignored)

        Returns:
            MockLLMResponse with fixture content
        """
        # Log the call for debugging/assertions
        self._call_log.append({
            'prompt': prompt[:200] + '...' if len(prompt) > 200 else prompt,
            'extraction_type': extraction_type,
            'section_type': section_type,
            'model': model
        })

        # Get fixture
        fixture = self.get_fixture(extraction_type, section_type)

        if fixture is None:
            # Return empty response if no fixture
            return MockLLMResponse(
                content=json.dumps({
                    'error': f'No fixture for {extraction_type}_{section_type}'
                })
            )

        # Return fixture as JSON string (mimicking LLM JSON output)
        return MockLLMResponse(
            content=json.dumps(fixture, indent=2)
        )

    def call_streaming(
        self,
        prompt: str,
        extraction_type: str = None,
        section_type: str = 'facts',
        on_chunk: Callable[[str], None] = None,
        **kwargs
    ) -> MockLLMResponse:
        """
        Simulate a streaming LLM call.

        For testing, this immediately returns the full response.
        The on_chunk callback is called once with the full content.

        Args:
            prompt: The prompt
            extraction_type: Type of extraction
            section_type: Section type
            on_chunk: Callback for streaming chunks
            **kwargs: Additional arguments

        Returns:
            MockLLMResponse with fixture content
        """
        response = self.call(
            prompt=prompt,
            extraction_type=extraction_type,
            section_type=section_type,
            **kwargs
        )

        # Call chunk callback if provided
        if on_chunk:
            on_chunk(response.content)

        return response

    def reset_call_log(self) -> None:
        """Clear the call log."""
        self._call_log.clear()

    @property
    def call_count(self) -> int:
        """Return the number of calls made."""
        return len(self._call_log)

    def get_calls(self, extraction_type: str = None) -> List[Dict[str, Any]]:
        """
        Get logged calls, optionally filtered by extraction type.

        Args:
            extraction_type: Filter by extraction type (optional)

        Returns:
            List of call records
        """
        if extraction_type is None:
            return self._call_log.copy()
        return [c for c in self._call_log if c['extraction_type'] == extraction_type]


class MockLLMClientFactory:
    """
    Factory for creating configured MockLLMClient instances.

    Useful for creating clients with specific fixture overrides for testing.
    """

    @staticmethod
    def create_with_overrides(overrides: Dict[str, Any]) -> MockLLMClient:
        """
        Create a MockLLMClient with fixture overrides.

        Args:
            overrides: Dict of fixture_key -> fixture_data overrides

        Returns:
            Configured MockLLMClient
        """
        client = MockLLMClient()
        client._fixtures.update(overrides)
        return client

    @staticmethod
    def create_empty() -> MockLLMClient:
        """Create a MockLLMClient with no fixtures (for testing error handling)."""
        client = MockLLMClient()
        client._fixtures.clear()
        return client
