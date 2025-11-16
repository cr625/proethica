"""
LLM response models.

Provides unified response format across different LLM providers.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class Usage:
    """Token usage information."""

    input_tokens: int
    output_tokens: int
    total_tokens: int = field(init=False)
    estimated_cost_usd: Optional[float] = None

    def __post_init__(self):
        """Calculate total tokens."""
        self.total_tokens = self.input_tokens + self.output_tokens


@dataclass
class LLMResponse:
    """
    Unified response format across LLM providers.

    Attributes:
        text: The generated text response
        model: Model identifier used
        provider: Provider name (anthropic, openai, etc.)
        usage: Token usage information
        metadata: Additional metadata (request_id, timing, etc.)
        timestamp: When the response was generated
    """

    text: str
    model: str
    provider: str
    usage: Usage
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'text': self.text,
            'model': self.model,
            'provider': self.provider,
            'usage': {
                'input_tokens': self.usage.input_tokens,
                'output_tokens': self.usage.output_tokens,
                'total_tokens': self.usage.total_tokens,
                'estimated_cost_usd': self.usage.estimated_cost_usd
            },
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }
