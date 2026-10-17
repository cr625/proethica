"""
Provider protocol for LLM interactions.

One interface for every provider: plain completion, streaming text, and
structured JSON. Call sites depend on this protocol and on the capability
registry, never on a vendor SDK. Vendor adapters (anthropic_provider,
openai_provider) translate the protocol to each SDK; tests substitute
fakes with recorded calls.

The structured method implements the capability ladder from
capabilities.py: schema-enforced decoding where the provider guarantees
it, JSON-object mode where only valid JSON is guaranteed, and prompt-only
JSON with tolerant parsing everywhere else. Every tier ends in a parsed
Python object or an exception; no tier returns raw text for the caller to
guess at.
"""

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .capabilities import ProviderCapabilities, UnsupportedCapabilityError, get_capabilities
from .response import LLMResponse


@dataclass
class ToolLoopResult:
    """Outcome of a tool-use conversation loop."""

    text: str
    stop_reason: Optional[str] = None  # end_turn | max_tokens | other vendor stop
    rounds: int = 0


class BaseLLMProvider:
    """Base class for provider adapters. Subclasses set ``name``."""

    name: str = "base"

    def __init__(self, model: Optional[str] = None, client: Any = None,
                 timeout: Optional[float] = None):
        self.model = model
        self._client = client
        self.timeout = timeout

    # -- client ---------------------------------------------------------
    @property
    def client(self):
        """Vendor SDK client, constructed lazily by subclasses."""
        raise NotImplementedError

    def capabilities(self, model: Optional[str] = None) -> ProviderCapabilities:
        """Capability record for the given (or default) model."""
        return get_capabilities(self.name, model or self.model or "")

    # -- core interface ---------------------------------------------------
    def complete(
        self,
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: Optional[float] = 1.0,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """Return one completion as an LLMResponse."""
        raise NotImplementedError

    def stream_text(
        self,
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: Optional[float] = 0.1,
        model: Optional[str] = None,
    ) -> str:
        """Stream one completion and return the joined text."""
        raise NotImplementedError

    def stream_complete(
        self,
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: Optional[float] = 0.1,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """Stream one completion and return the full LLMResponse.

        Streaming transport with complete-result semantics (text, usage,
        stop metadata), for call sites that record token usage from a
        streamed call. Default falls back to ``complete``; adapters with
        native streaming override it.
        """
        return self.complete(
            messages, system=system, max_tokens=max_tokens,
            temperature=temperature, model=model,
        )

    # -- tool-use loop ------------------------------------------------------
    def tool_loop(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        tool_runner: Callable[[str, Dict[str, Any]], str],
        system: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        max_rounds: int = 25,
    ) -> ToolLoopResult:
        """Run a tool-use conversation until the model stops calling tools.

        ``tools`` uses the Anthropic tool shape (name, description,
        input_schema); adapters translate to their vendor shape.
        ``tool_runner(name, input)`` executes one call and returns its
        result text. When rounds are exhausted, one final call without
        tools forces a text answer. Raises UnsupportedCapabilityError
        where the model does not declare tool use.
        """
        use_model = model or self.model or ""
        self._check_tool_use(use_model)
        raise NotImplementedError(f"{self.name} does not implement tool_loop")

    def _check_tool_use(self, use_model: str) -> None:
        """Raise UnsupportedCapabilityError unless tool use is declared."""
        if not self.capabilities(use_model).supports_tool_use:
            raise UnsupportedCapabilityError(
                f"{self.name}:{use_model} does not declare capability 'tool_use'; "
                "repoint the tier or keep this call site on a tool-capable model"
            )

    # -- structured JSON (capability ladder) ------------------------------
    def structured(
        self,
        messages: List[Dict[str, Any]],
        schema: Dict[str, Any],
        system: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: Optional[float] = 0.1,
        model: Optional[str] = None,
        schema_name: str = "response",
    ) -> Dict[str, Any]:
        """Return a parsed dict conforming to ``schema`` as far as the
        provider tier guarantees, validated by parsing in every tier."""
        use_model = model or self.model or ""
        caps = self.capabilities(use_model)

        if caps.structured_tier == "schema":
            return self._structured_schema(
                messages, system, schema, max_tokens, temperature, use_model, schema_name
            )
        if caps.structured_tier == "json_object":
            text = self._json_object_text(messages, system, max_tokens, temperature, use_model)
            return _parse_json_text(text)
        # prompt_only: state the contract in the prompt, parse tolerantly.
        instruction = (
            "\n\nRespond with only a JSON object matching this JSON Schema. "
            "No prose, no markdown fences.\n" + json.dumps(schema)
        )
        prompted = _append_to_last_user(messages, instruction)
        response = self.complete(
            prompted, system=system, max_tokens=max_tokens,
            temperature=temperature, model=use_model,
        )
        return _parse_json_text(response.text)

    def _structured_schema(self, messages, system, schema, max_tokens,
                           temperature, model, schema_name) -> Dict[str, Any]:
        raise NotImplementedError(f"{self.name} does not implement schema structured output")

    def _json_object_text(self, messages, system, max_tokens, temperature, model) -> str:
        """Default JSON-object implementation: plain completion text."""
        return self.complete(
            messages, system=system, max_tokens=max_tokens,
            temperature=temperature, model=model,
        ).text


def _parse_json_text(text: str) -> Dict[str, Any]:
    """Parse JSON text tolerantly (markdown fences, surrounding prose)."""
    from app.utils.llm_json_utils import extract_json_from_response

    parsed = extract_json_from_response(text or "")
    if not isinstance(parsed, dict):
        raise ValueError(f"structured response is not a JSON object: {str(parsed)[:200]}")
    return parsed


def _append_to_last_user(messages: List[Dict[str, Any]], suffix: str) -> List[Dict[str, Any]]:
    """Copy messages with ``suffix`` appended to the last user message."""
    copied = [dict(m) for m in messages]
    for message in reversed(copied):
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            message["content"] = message["content"] + suffix
            return copied
    copied.append({"role": "user", "content": suffix.strip()})
    return copied
