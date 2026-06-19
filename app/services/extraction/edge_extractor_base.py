"""
Shared base for the per-case LLM edge extractors.

Several extractors in this package follow the same shape: lazily obtain an
Anthropic streaming client, resolve a model, stream a system+user prompt to
completion, then parse the JSON response into edges. ``StreamingEdgeExtractor``
owns that machinery so the concrete extractors only declare their prompt and
their parse/validate logic.

Concrete subclasses:
  - ``DefeasibilityEdgeExtractor`` (defeasibility_edges.py)
  - ``RPOEdgeExtractor``           (rpo_edges.py)
  - ``TemporalSequenceExtractor``  (temporal_sequence.py)

Streaming (rather than a single non-streaming request) is the standard pattern
in this codebase: it keeps the TCP connection alive past the WSL2 60s idle
window and avoids the APIConnectionError that long generations hit. The
system+user split lets the property axioms in the system prompt receive
Anthropic's higher system-prompt treatment.

Subclass contract:
  - set ``log_label`` (used verbatim in log lines) and, when the natural cap
    differs, ``default_max_tokens``;
  - implement ``_system_prompt()`` returning the system prompt string;
  - override ``_default_model()`` when the extractor does not run on the
    powerful tier (e.g. temporal-sequence uses the default tier);
  - set ``swallow_stream_errors = False`` to let a streaming exception propagate
    instead of being logged and converted to a ``None`` return.
"""

from __future__ import annotations

import json as _json
import logging
import re as _re
from typing import Any, Dict, Iterator, List, Optional

from model_config import ModelConfig

logger = logging.getLogger(__name__)


class StreamingEdgeExtractor:
    """Base class: LLM streaming + truncation-recovery for edge extractors."""

    # Subclass-configurable knobs.
    log_label: str = "edge"
    default_max_tokens: int = 16384
    swallow_stream_errors: bool = True

    def __init__(
        self,
        llm_client: Any = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ):
        # Lazy LLM client: a backfill script can supply a pre-built client, and
        # the live pipeline can let us fetch one at extract() time.
        self._llm_client = llm_client
        self.model = model
        self.temperature = temperature
        self.max_tokens = self.default_max_tokens if max_tokens is None else max_tokens
        self.last_prompt: Optional[str] = None
        self.last_raw_response: Optional[str] = None

    # ------------------------------------------------------------------
    # LLM plumbing (shared)
    # ------------------------------------------------------------------

    def _get_client(self):
        if self._llm_client is None:
            from app.utils.llm_utils import get_llm_client
            self._llm_client = get_llm_client()
        return self._llm_client

    def _default_model(self) -> str:
        """Model used when the caller did not pin one. Defaults to the powerful
        (Opus) tier; relational edge reasoning is paper-critical and bounded to
        one call per case. Override for cheaper-tier extractors."""
        return ModelConfig.get_claude_model("powerful")

    def _resolve_model(self) -> str:
        if self.model:
            return self.model
        return self._default_model()

    def _system_prompt(self) -> str:
        raise NotImplementedError

    def _stream_llm(self, user_prompt: str) -> Optional[str]:
        """Stream a system+user request to completion and return the joined text.

        Returns ``None`` when the client is not an Anthropic streaming client.
        On a streaming exception, returns ``None`` (logging it) unless
        ``swallow_stream_errors`` is False, in which case the exception
        propagates.
        """
        client = self._get_client()
        model = self._resolve_model()

        if not (hasattr(client, "messages") and hasattr(client.messages, "stream")):
            logger.error(
                "%s requires an Anthropic streaming client; got %s",
                type(self).__name__, type(client).__name__,
            )
            return None

        try:
            chunks: List[str] = []
            stream_kwargs = dict(
                model=model,
                max_tokens=self.max_tokens,
                system=self._system_prompt(),
                messages=[{"role": "user", "content": user_prompt}],
            )
            if ModelConfig.supports_temperature(model):  # Opus 4.8 rejects temperature
                stream_kwargs["temperature"] = self.temperature
            with client.messages.stream(**stream_kwargs) as stream:
                for text in stream.text_stream:
                    chunks.append(text)
                final_msg = stream.get_final_message()
            stop_reason = getattr(final_msg, "stop_reason", None)
            usage = getattr(final_msg, "usage", None)
            if usage:
                logger.info(
                    "%s stream complete: %d in / %d out, stop=%s",
                    self.log_label, usage.input_tokens, usage.output_tokens, stop_reason,
                )
            if stop_reason == "max_tokens":
                logger.warning(
                    "%s hit max_tokens (%d); response may be truncated",
                    self.log_label, self.max_tokens,
                )
            self.last_raw_response = "".join(chunks)
            return self.last_raw_response
        except Exception as e:
            if not self.swallow_stream_errors:
                raise
            logger.error("Anthropic %s stream failed: %s", self.log_label, e)
            return None

    # ------------------------------------------------------------------
    # Truncation recovery (used by the flat-edge extractors)
    # ------------------------------------------------------------------

    @staticmethod
    def _iter_flat_json_objects(raw: str) -> Iterator[Dict[str, Any]]:
        """Yield each flat ``{...}`` block (no inner braces) parsed as a dict.

        Defeasibility and R->P->O edges are flat objects (no nested object in
        any value), so every complete edge survives as a brace-balanced block
        even when ``max_tokens`` truncated the enclosing array. Blocks that fail
        to parse, or are not dicts, are skipped. Predicate/endpoint filtering is
        left to the caller.
        """
        for m in _re.finditer(r"\{[^{}]*\}", raw):
            try:
                obj = _json.loads(m.group(0))
            except Exception:
                continue
            if isinstance(obj, dict):
                yield obj
