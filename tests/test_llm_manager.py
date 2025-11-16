"""
Tests for centralized LLM manager.

Tests basic functionality, configuration, and provider handling.
"""

import pytest
import os
from app.services.llm import (
    LLMManager,
    get_llm_manager,
    reset_llm_manager,
    LLMConfig,
    LLMResponse,
    Usage
)


class TestLLMConfig:
    """Test LLM configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = LLMConfig()

        assert config.default_model == "claude-sonnet-4-20250514"
        assert config.read_timeout == 180.0
        assert config.max_retries == 3
        assert config.track_usage is True

    def test_from_env(self, monkeypatch):
        """Test loading configuration from environment."""
        monkeypatch.setenv("LLM_READ_TIMEOUT", "300")
        monkeypatch.setenv("LLM_MAX_RETRIES", "5")

        config = LLMConfig.from_env()

        assert config.read_timeout == 300.0
        assert config.max_retries == 5

    def test_for_testing(self):
        """Test testing configuration."""
        config = LLMConfig.for_testing()

        assert config.read_timeout == 30.0
        assert config.max_retries == 1
        assert config.track_usage is False
        assert config.log_requests is True


class TestUsage:
    """Test usage tracking model."""

    def test_total_tokens_calculation(self):
        """Test total tokens are calculated correctly."""
        usage = Usage(input_tokens=100, output_tokens=50)

        assert usage.total_tokens == 150

    def test_with_cost(self):
        """Test usage with cost estimation."""
        usage = Usage(
            input_tokens=1000,
            output_tokens=500,
            estimated_cost_usd=0.0075
        )

        assert usage.total_tokens == 1500
        assert usage.estimated_cost_usd == 0.0075


class TestLLMResponse:
    """Test LLM response model."""

    def test_response_creation(self):
        """Test creating an LLM response."""
        usage = Usage(input_tokens=100, output_tokens=50)
        response = LLMResponse(
            text="Test response",
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            usage=usage,
            metadata={"test": "data"}
        )

        assert response.text == "Test response"
        assert response.model == "claude-sonnet-4-20250514"
        assert response.provider == "anthropic"
        assert response.usage.total_tokens == 150

    def test_to_dict(self):
        """Test converting response to dictionary."""
        usage = Usage(input_tokens=100, output_tokens=50, estimated_cost_usd=0.001)
        response = LLMResponse(
            text="Test",
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            usage=usage
        )

        data = response.to_dict()

        assert data['text'] == "Test"
        assert data['model'] == "claude-sonnet-4-20250514"
        assert data['usage']['total_tokens'] == 150
        assert 'timestamp' in data


class TestLLMManager:
    """Test LLM manager core functionality."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_llm_manager()

    def test_initialization(self):
        """Test LLM manager initializes correctly."""
        # Skip if no API key
        if not os.getenv('ANTHROPIC_API_KEY'):
            pytest.skip("ANTHROPIC_API_KEY not set")

        manager = LLMManager()

        assert manager.model == "claude-sonnet-4-20250514"
        assert manager.provider == "anthropic"
        assert manager.client is not None

    def test_provider_detection(self):
        """Test provider detection from model name."""
        # Skip if no API key
        if not os.getenv('ANTHROPIC_API_KEY'):
            pytest.skip("ANTHROPIC_API_KEY not set")

        manager = LLMManager()

        assert manager._detect_provider("claude-sonnet-4-20250514") == "anthropic"
        assert manager._detect_provider("gpt-4") == "openai"
        assert manager._detect_provider("unknown-model") == "anthropic"  # Default

    def test_cost_estimation_anthropic(self):
        """Test Anthropic cost estimation."""
        # Skip if no API key
        if not os.getenv('ANTHROPIC_API_KEY'):
            pytest.skip("ANTHROPIC_API_KEY not set")

        manager = LLMManager()

        # Sonnet 4: $3/MTok input, $15/MTok output
        cost = manager._estimate_cost_anthropic(
            input_tokens=1000,
            output_tokens=1000,
            model="claude-sonnet-4-20250514"
        )

        # Should be (1000/1M * 3) + (1000/1M * 15) = 0.003 + 0.015 = 0.018
        assert cost == 0.018

    def test_json_parsing_with_markdown(self):
        """Test parsing JSON with markdown code blocks."""
        # Skip if no API key
        if not os.getenv('ANTHROPIC_API_KEY'):
            pytest.skip("ANTHROPIC_API_KEY not set")

        manager = LLMManager()

        # Test with markdown wrapper
        markdown_json = '```json\n{"name": "test", "value": 123}\n```'
        result = manager.parse_json_response(markdown_json)

        assert result == {"name": "test", "value": 123}

        # Test without markdown
        plain_json = '{"name": "test", "value": 123}'
        result = manager.parse_json_response(plain_json)

        assert result == {"name": "test", "value": 123}

    def test_model_switching(self):
        """Test switching between models."""
        # Skip if no API key
        if not os.getenv('ANTHROPIC_API_KEY'):
            pytest.skip("ANTHROPIC_API_KEY not set")

        manager = LLMManager(model="claude-sonnet-4-20250514")
        assert manager.model == "claude-sonnet-4-20250514"

        manager.switch_model("claude-opus-4-1-20250805")
        assert manager.model == "claude-opus-4-1-20250805"

    def test_singleton_access(self):
        """Test singleton get_llm_manager function."""
        # Skip if no API key
        if not os.getenv('ANTHROPIC_API_KEY'):
            pytest.skip("ANTHROPIC_API_KEY not set")

        manager1 = get_llm_manager()
        manager2 = get_llm_manager()

        # Should be same instance
        assert manager1 is manager2


@pytest.mark.integration
class TestLLMManagerIntegration:
    """
    Integration tests that actually call the LLM API.

    These tests are marked as @pytest.mark.integration and require:
    - ANTHROPIC_API_KEY environment variable
    - Network connectivity
    - Costs money to run (small amounts)

    Run with: pytest -v -m integration tests/test_llm_manager.py
    """

    def setup_method(self):
        """Reset singleton before each test."""
        reset_llm_manager()

    def test_simple_completion(self):
        """Test a simple completion call."""
        # Skip if no API key
        if not os.getenv('ANTHROPIC_API_KEY'):
            pytest.skip("ANTHROPIC_API_KEY not set")

        manager = get_llm_manager()

        response = manager.complete(
            messages=[{"role": "user", "content": "Say 'test successful' and nothing else."}],
            max_tokens=50
        )

        assert isinstance(response, LLMResponse)
        assert "test successful" in response.text.lower()
        assert response.usage.total_tokens > 0
        assert response.provider == "anthropic"

    def test_usage_tracking(self):
        """Test usage tracking works."""
        # Skip if no API key
        if not os.getenv('ANTHROPIC_API_KEY'):
            pytest.skip("ANTHROPIC_API_KEY not set")

        manager = get_llm_manager()

        # Make a call
        manager.complete(
            messages=[{"role": "user", "content": "Say hello."}],
            max_tokens=50
        )

        stats = manager.get_usage_stats()

        assert stats['total_calls'] == 1
        assert stats['total_input_tokens'] > 0
        assert stats['total_output_tokens'] > 0
        assert stats['total_cost_usd'] > 0


if __name__ == "__main__":
    # Run tests with: python tests/test_llm_manager.py
    pytest.main([__file__, "-v"])
