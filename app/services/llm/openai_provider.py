"""
OpenAI provider adapter.

Wraps the OpenAI SDK (Chat Completions surface) behind the provider
protocol. The system prompt travels as a leading system message, which is
the only structural translation the protocol requires. Structured output
uses ``response_format`` with a strict JSON Schema on capable models and
JSON-object mode on the rest (see capabilities.py); refusal and
truncation surface as unparsable text and raise in the protocol layer,
matching the Anthropic adapter contract of parsed-object-or-exception.
"""

import json
import os
from typing import Any, Dict, List, Optional

from .protocol import BaseLLMProvider
from .response import LLMResponse, Usage


def _with_system(messages: List[Dict[str, Any]], system: Optional[str]) -> List[Dict[str, Any]]:
    if not system:
        return list(messages)
    return [{"role": "system", "content": system}] + list(messages)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI (GPT) adapter over the chat completions API."""

    name = "openai"

    @property
    def client(self):
        if self._client is None:
            import openai

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in environment")
            kwargs = {"api_key": api_key}
            if self.timeout is not None:
                kwargs["timeout"] = self.timeout
            self._client = openai.OpenAI(**kwargs)
        return self._client

    def _create(self, messages, system, max_tokens, temperature, model, **extra):
        kwargs: Dict[str, Any] = {
            "model": model or self.model,
            "messages": _with_system(messages, system),
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        kwargs.update(extra)
        return self.client.chat.completions.create(**kwargs)

    @staticmethod
    def _to_response(response, use_model) -> LLMResponse:
        choice = response.choices[0]
        usage = Usage(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )
        return LLMResponse(
            text=choice.message.content or "",
            model=use_model,
            provider="openai",
            usage=usage,
            metadata={
                "response_id": getattr(response, "id", None),
                "finish_reason": getattr(choice, "finish_reason", None),
            },
        )

    def complete(self, messages, system=None, max_tokens=2000,
                 temperature=1.0, model=None) -> LLMResponse:
        use_model = model or self.model
        response = self._create(messages, system, max_tokens, temperature, use_model)
        return self._to_response(response, use_model)

    @staticmethod
    def _chunk_text(stream):
        """Joined delta text from a streamed chat completion."""
        chunks = []
        for chunk in stream:
            if not chunk.choices:
                continue
            content = getattr(chunk.choices[0].delta, "content", None)
            if content:
                chunks.append(content)
        return "".join(chunks)

    def stream_text(self, messages, system=None, max_tokens=4000,
                    temperature=0.1, model=None) -> str:
        use_model = model or self.model
        stream = self._create(
            messages, system, max_tokens, temperature, use_model, stream=True
        )
        return self._chunk_text(stream)

    def stream_complete(self, messages, system=None, max_tokens=4000,
                        temperature=0.1, model=None) -> LLMResponse:
        use_model = model or self.model
        stream = self._create(
            messages, system, max_tokens, temperature, use_model,
            stream=True, stream_options={"include_usage": True},
        )
        chunks = []
        usage = Usage(input_tokens=0, output_tokens=0)
        finish_reason = None
        for chunk in stream:
            chunk_usage = getattr(chunk, "usage", None)
            if chunk_usage is not None:
                usage = Usage(
                    input_tokens=chunk_usage.prompt_tokens,
                    output_tokens=chunk_usage.completion_tokens,
                )
            if not chunk.choices:
                continue
            finish_reason = getattr(chunk.choices[0], "finish_reason", None) or finish_reason
            content = getattr(chunk.choices[0].delta, "content", None)
            if content:
                chunks.append(content)
        return LLMResponse(
            text="".join(chunks), model=use_model, provider="openai",
            usage=usage, metadata={"finish_reason": finish_reason},
        )

    @staticmethod
    def _translate_tools(tools):
        """Anthropic tool shape -> OpenAI function-calling shape."""
        return [{
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {"type": "object"}),
            },
        } for tool in tools]

    def tool_loop(self, prompt, tools, tool_runner, system=None,
                  max_tokens=4000, temperature=None, model=None,
                  max_rounds=25):
        """OpenAI function-calling loop.

        Translation only: tool definitions become function specs, tool
        results become ``tool`` role messages keyed by call id, and the
        arguments JSON string is parsed before the runner sees it.
        Prompt caching is automatic on this provider, so no breakpoints
        are managed here.
        """
        from .protocol import ToolLoopResult

        use_model = model or self.model
        self._check_tool_use(use_model)
        messages = _with_system(
            [{"role": "user", "content": prompt}], system)
        translated = self._translate_tools(tools)

        for round_num in range(max_rounds):
            response = self._create(
                messages, None, max_tokens, temperature, use_model,
                tools=translated, tool_choice="auto")
            choice = response.choices[0]
            message = choice.message
            if choice.finish_reason != "tool_calls" or not getattr(message, "tool_calls", None):
                return ToolLoopResult(
                    text=message.content or "", stop_reason=choice.finish_reason,
                    rounds=round_num + 1)
            assistant = {"role": "assistant", "content": message.content,
                         "tool_calls": []}
            pending = []
            for call in message.tool_calls:
                assistant["tool_calls"].append({
                    "id": call.id, "type": "function",
                    "function": {"name": call.function.name,
                                 "arguments": call.function.arguments},
                })
                pending.append(call)
            messages.append(assistant)
            for call in pending:
                try:
                    arguments = json.loads(call.function.arguments or "{}")
                except (ValueError, TypeError):
                    arguments = {}
                messages.append({
                    "role": "tool", "tool_call_id": call.id,
                    "content": tool_runner(call.function.name, arguments),
                })

        response = self._create(messages, None, max_tokens, temperature, use_model)
        choice = response.choices[0]
        return ToolLoopResult(
            text=choice.message.content or "", stop_reason=choice.finish_reason,
            rounds=max_rounds + 1)

    def _structured_schema(self, messages, system, schema, max_tokens,
                           temperature, model, schema_name) -> Dict[str, Any]:
        response = self._create(
            messages, system, max_tokens, temperature, model,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
        )
        return json.loads(self._to_response(response, model).text)

    def _json_object_text(self, messages, system, max_tokens, temperature, model) -> str:
        # JSON-object mode requires the word "json" in the conversation.
        joined = " ".join(str(m.get("content", "")) for m in messages).lower()
        if "json" not in joined and "json" not in (system or "").lower():
            system = ((system + "\n") if system else "") + "Respond in JSON."
        response = self._create(
            messages, system, max_tokens, temperature, model,
            response_format={"type": "json_object"},
        )
        return self._to_response(response, model).text
