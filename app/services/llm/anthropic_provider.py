"""
Anthropic provider adapter.

Wraps the Anthropic SDK behind the provider protocol. Behavior matches the
existing direct call sites: ``direct_call_params`` floors ``max_tokens``
for thinking-by-default models and omits ``temperature`` for models that
reject it, and ``text_from_message`` reads text blocks past any leading
thinking blocks. Streaming is the default transport for long generations
(WSL2 idle-timeout avoidance, as in ``streaming_completion``).

Tool use and prompt caching are not part of the protocol yet; the
label-only extraction loop keeps its native Anthropic implementation,
gated by the capability record.
"""

import json
import os
from typing import Any, Dict

from .protocol import BaseLLMProvider
from .response import LLMResponse, Usage


def _final_message(stream):
    """Final streamed message, or None for minimal stream doubles that
    only replay text (real SDK streams always provide it)."""
    get_final = getattr(stream, "get_final_message", None)
    if get_final is None:
        return None
    try:
        return get_final()
    except Exception:
        return None


def _usage_of(message) -> Usage:
    """Usage from a (possibly minimal) response message; zeros if absent."""
    raw = getattr(message, "usage", None)
    return Usage(
        input_tokens=getattr(raw, "input_tokens", 0) or 0,
        output_tokens=getattr(raw, "output_tokens", 0) or 0,
    )


class AnthropicProvider(BaseLLMProvider):
    """Anthropic (Claude) adapter over the messages API."""

    name = "anthropic"

    @property
    def client(self):
        if self._client is None:
            import anthropic

            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not found in environment")
            self._client = anthropic.Anthropic(
                api_key=api_key, timeout=self.timeout if self.timeout is not None else 180.0)
        return self._client

    def _call_kwargs(self, messages, system, max_tokens, temperature, model):
        """SDK kwargs with the budget floor / temperature gates applied."""
        from app.utils.llm_utils import direct_call_params

        kwargs: Dict[str, Any] = {
            **direct_call_params(model or self.model, max_tokens, temperature),
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        return kwargs

    def _stream_chunks(self, kwargs):
        """Run one streamed call; return (joined_text, final_message)."""
        from app.utils.llm_utils import text_from_message

        with self.client.messages.stream(**kwargs) as stream:
            chunks = [text for text in getattr(stream, "text_stream", None) or []]
            final = _final_message(stream)
        text = "".join(chunks) if chunks else (
            text_from_message(final) if final is not None else "")
        return text, final

    def complete(self, messages, system=None, max_tokens=2000,
                 temperature=1.0, model=None) -> LLMResponse:
        from app.utils.llm_utils import text_from_message

        use_model = model or self.model
        response = self.client.messages.create(
            **self._call_kwargs(messages, system, max_tokens, temperature, use_model))
        return LLMResponse(
            text=text_from_message(response) if response.content else "",
            model=use_model,
            provider=self.name,
            usage=_usage_of(response),
            metadata={
                "response_id": getattr(response, "id", None),
                "stop_reason": getattr(response, "stop_reason", None),
            },
        )

    def stream_text(self, messages, system=None, max_tokens=4000,
                    temperature=0.1, model=None) -> str:
        return self.stream_complete(
            messages, system=system, max_tokens=max_tokens,
            temperature=temperature, model=model).text

    def stream_complete(self, messages, system=None, max_tokens=4000,
                        temperature=0.1, model=None) -> LLMResponse:
        use_model = model or self.model
        text, final = self._stream_chunks(
            self._call_kwargs(messages, system, max_tokens, temperature, use_model))
        return LLMResponse(
            text=text,
            model=use_model,
            provider=self.name,
            usage=_usage_of(final),
            metadata={
                "response_id": getattr(final, "id", None),
                "stop_reason": getattr(final, "stop_reason", None),
            },
        )

    def tool_loop(self, prompt, tools, tool_runner, system=None,
                  max_tokens=4000, temperature=None, model=None,
                  max_rounds=25):
        """Anthropic tool-use loop with within-call prompt caching.

        Every tool round re-sends the full conversation, and label-only
        extraction routinely runs 10-15 rounds, so two cache breakpoints
        (of the allowed four) are held: a stable anchor on the initial
        prompt and a moving one on the latest tool_result. Each round
        writes only its own delta and reads the rest at reduced cost
        (5-minute TTL; rounds are seconds apart).
        """
        from .protocol import ToolLoopResult

        use_model = model or self.model
        self._check_tool_use(use_model)

        messages = [{
            "role": "user",
            "content": [{
                "type": "text", "text": prompt,
                "cache_control": {"type": "ephemeral"},
            }],
        }]
        prev_tail_mark = None
        response = None

        def _text_of(message):
            return "".join(
                block.text for block in message.content
                if getattr(block, "type", "") == "text")

        for round_num in range(max_rounds):
            kwargs = self._call_kwargs(messages, system, max_tokens, temperature, use_model)
            kwargs["tools"] = tools
            with self.client.messages.stream(**kwargs) as stream:
                response = stream.get_final_message()

            if response.stop_reason != "tool_use":
                return ToolLoopResult(
                    text=_text_of(response), stop_reason=response.stop_reason,
                    rounds=round_num + 1)

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if getattr(block, "type", "") != "tool_use":
                    continue
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": tool_runner(block.name, block.input),
                })
            if tool_results:
                if prev_tail_mark is not None:
                    prev_tail_mark.pop("cache_control", None)
                tool_results[-1]["cache_control"] = {"type": "ephemeral"}
                prev_tail_mark = tool_results[-1]
            messages.append({"role": "user", "content": tool_results})

        # Exhausted rounds: stub pending results and force a final answer
        # without tools (a full cache miss by construction; rare path).
        if response is not None:
            messages.append({"role": "assistant", "content": response.content})
            stubs = [{
                "type": "tool_result", "tool_use_id": block.id,
                "content": ("Definition not available. Proceed with extraction "
                            "using the labels you already have."),
            } for block in response.content
                if getattr(block, "type", "") == "tool_use"]
            if stubs:
                messages.append({"role": "user", "content": stubs})
        kwargs = self._call_kwargs(messages, system, max_tokens, temperature, use_model)
        with self.client.messages.stream(**kwargs) as stream:
            final = stream.get_final_message()
        return ToolLoopResult(
            text=_text_of(final), stop_reason=final.stop_reason,
            rounds=max_rounds + 1)

    def _structured_schema(self, messages, system, schema, max_tokens,
                           temperature, model, schema_name) -> Dict[str, Any]:
        kwargs = self._call_kwargs(messages, system, max_tokens, temperature, model)
        kwargs["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
        text, _final = self._stream_chunks(kwargs)
        return json.loads(text)
