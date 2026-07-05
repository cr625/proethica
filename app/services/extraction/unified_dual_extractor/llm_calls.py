"""LLM calling for the unified dual extractor.

LLMCallMixin: the streaming completion call (_call_llm), the tool-use
conversation loop for label-only injection (_call_llm_with_tools + the
ONTOLOGY_LOOKUP_TOOLS tool definition), and the OntServe definition-lookup tool
executor (_execute_tool_call). Methods relocated verbatim from the former
unified_dual_extractor.py; UnifiedDualExtractor inherits this mixin, so calls to
sibling methods (e.g. self._repair_truncated_json) and instance attributes
(self.model_name, self.config, self.mcp_client, ...) resolve unchanged via MRO.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict

import anthropic

from app.utils.llm_utils import extract_json_from_response

logger = logging.getLogger(__name__)

# Concept types whose cleaned result schema compiles to a structured-outputs grammar that exceeds the
# API's size ceiling (a 400 "compiled grammar is too large"). Learned at runtime on the first such 400
# so the failed call is not repeated; those concepts fall back to free-form JSON for the rest of the
# process. As of 2026-07-04 all nine per-concept schemas fit (probed against the API): the Optional[str]
# null-branch collapse in schemas._clean_structured_output_node bought back the grammar budget that
# previously pushed roles and actions over the ceiling. This set remains as the safety net for future
# schema growth (only the legacy combined 'actions_events' schema, which the pipeline never dispatches,
# still exceeds the ceiling).
_GRAMMAR_TOO_LARGE: set = set()


class LLMCallMixin:
    """Streaming + tool-use LLM calls for UnifiedDualExtractor."""

    def _maybe_temperature(self) -> Dict[str, Any]:
        """Return ``{'temperature': ...}`` for models that accept the parameter, or an
        empty dict for models that reject it (Opus 4.8 returns HTTP 400 if temperature is
        passed; ModelConfig.TEMPERATURE_UNSUPPORTED tracks these). The default Sonnet/Haiku
        path is unchanged -- it keeps the per-concept temperature. Spread into the stream
        kwargs so the live path and any model override both respect the model's contract."""
        from model_config import ModelConfig
        if ModelConfig.supports_temperature(self.model_name):
            return {'temperature': self.config['temperature']}
        return {}

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------

    def _call_llm(self, prompt: str) -> Dict[str, Any]:
        """Call the LLM and parse JSON from the response.

        Delegates to _call_llm_with_tools() when injection_mode is
        'label_only', enabling on-demand class definition retrieval.
        """
        if (self.injection_mode == 'label_only'
                and self.llm_client is None
                and self.mcp_client is not None):
            return self._call_llm_with_tools(prompt)

        try:
            # Mock client path (testing)
            if self.llm_client is not None:
                response = self.llm_client.call(
                    prompt=prompt,
                    extraction_type=self.concept_type,
                    section_type=getattr(
                        self, '_current_section_type', 'facts'
                    ),
                )
                response_text = (
                    response.content
                    if hasattr(response, 'content')
                    else str(response)
                )
                self.last_raw_response = response_text
                return extract_json_from_response(response_text)

            # Real LLM path
            from app.utils.llm_utils import get_llm_client

            client = get_llm_client()
            if not client:
                logger.error("No LLM client available")
                return {}

            logger.info(
                f"_call_llm: sending {len(prompt)} chars, "
                f"type={type(prompt).__name__}, "
                f"model={self.model_name}, "
                f"max_tokens={self.config['max_tokens']}"
            )

            # Use streaming to avoid server-side timeout on long responses.
            # Non-streaming requests fail with APIConnectionError when
            # generation exceeds ~180s (e.g., discussion principles at 7K+
            # output tokens).
            chunks = []
            stream_kwargs = dict(
                model=self.model_name,
                max_tokens=self.config['max_tokens'],
                **self._maybe_temperature(),
                messages=[{"role": "user", "content": prompt}],
            )
            _system = (getattr(self, '_rendered_system', '') or '').strip()
            if _system:
                stream_kwargs['system'] = _system
            # Structured outputs: constrain the model to the cleaned result schema so a
            # complete response is guaranteed-parseable JSON. Without it, Opus 4.8 can
            # emit JSON that extract_json_from_response cannot recover, silently dropping
            # every entity (e.g. all obligations on case 7). output_config guarantees
            # FORMAT only -- a max_tokens cut still truncates, so the truncation-repair
            # branch below is retained and extract_json_from_response now succeeds on the
            # first try. Skipped (free-form fallback) when no result_schema is set.
            _schema = getattr(self, '_structured_output_schema', None)
            _use_so = (
                _schema is not None
                and self.concept_type not in _GRAMMAR_TOO_LARGE
            )
            if _use_so:
                stream_kwargs['output_config'] = {
                    "format": {"type": "json_schema", "schema": _schema}
                }
            # Transient server-side errors (overloaded / rate-limit / 5xx) surface mid-stream, and the SDK
            # does not retry an already-started stream -- so wrap the stream attempt in a backoff retry. The
            # batch-1 corpus run dropped a whole component (case-5 constraints) to a one-off overloaded_error;
            # across 119 cases that would silently lose components, so retry the full call before giving up.
            _MAX_TRANSIENT_RETRIES = 4
            for _attempt in range(_MAX_TRANSIENT_RETRIES):
                chunks = []
                try:
                    try:
                        with client.messages.stream(**stream_kwargs) as stream:
                            for text in stream.text_stream:
                                chunks.append(text)
                        final_msg = stream.get_final_message()
                    except anthropic.BadRequestError as e:
                        # Structured outputs compiles the schema into a grammar with a size ceiling
                        # (the actions schema exceeds it: 400 "compiled grammar is too large"). Fall
                        # back to free-form for this concept and remember it so the failed call is not
                        # repeated. The free-form parse path below still applies.
                        if _use_so and 'grammar' in str(e).lower():
                            _GRAMMAR_TOO_LARGE.add(self.concept_type)
                            logger.warning(
                                f"output_config grammar too large for {self.concept_type}; "
                                f"falling back to free-form JSON for this concept"
                            )
                            stream_kwargs.pop('output_config', None)
                            chunks = []
                            with client.messages.stream(**stream_kwargs) as stream:
                                for text in stream.text_stream:
                                    chunks.append(text)
                            final_msg = stream.get_final_message()
                        else:
                            raise
                    break  # got a complete response
                except anthropic.APIStatusError as e:
                    _msg = str(e).lower()
                    _transient = (
                        'overloaded' in _msg or 'rate_limit' in _msg
                        or getattr(e, 'status_code', 0) in (429, 500, 502, 503, 529)
                    )
                    if _transient and _attempt < _MAX_TRANSIENT_RETRIES - 1:
                        _wait = min(2 ** _attempt, 20)
                        logger.warning(
                            f"transient API error for {self.concept_type} (attempt "
                            f"{_attempt + 1}/{_MAX_TRANSIENT_RETRIES}, {type(e).__name__}); retrying in {_wait}s"
                        )
                        time.sleep(_wait)
                        continue
                    raise

            response_text = "".join(chunks)
            self.last_raw_response = response_text

            stop_reason = final_msg.stop_reason
            logger.info(
                f"LLM stream complete: {final_msg.usage.input_tokens} in / "
                f"{final_msg.usage.output_tokens} out, stop={stop_reason}"
            )

            if stop_reason == 'max_tokens':
                logger.warning(
                    f"Response truncated at {self.config['max_tokens']} "
                    f"tokens for {self.concept_type}"
                )
                # Try to repair truncated JSON
                response_text = self._repair_truncated_json(response_text)

            logger.debug(f"LLM response ({len(response_text)} chars)")

            return extract_json_from_response(response_text)

        except Exception as e:
            logger.error(
                f"LLM call failed for {self.concept_type}: "
                f"{type(e).__name__}: {e}"
            )
            # Log full chain for connection errors
            if hasattr(e, '__cause__') and e.__cause__:
                logger.error(f"  Caused by: {type(e.__cause__).__name__}: {e.__cause__}")
            if hasattr(e, 'status_code'):
                logger.error(f"  Status code: {e.status_code}")
            if hasattr(e, 'response'):
                logger.error(f"  Response: {e.response}")
            import traceback
            logger.error(f"  Traceback: {traceback.format_exc()}")
            return {}

    # ------------------------------------------------------------------
    # Tool-use LLM call (Phase 2 label-only injection)
    # ------------------------------------------------------------------

    # Tool definition sent to the Anthropic API so Claude can request
    # class definitions on demand during label-only extraction.
    ONTOLOGY_LOOKUP_TOOLS = [
        {
            "name": "get_class_definition",
            "description": (
                "Retrieve the full definition of an ontology class by its "
                "label. Use when you need to check whether an existing class "
                "matches a concept found in the case text, especially when "
                "two or more labels could plausibly apply."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": (
                            "The exact class label from the PREVIOUSLY "
                            "EXTRACTED CLASSES list"
                        ),
                    }
                },
                "required": ["label"],
            },
        }
    ]

    def _call_llm_with_tools(self, prompt: str) -> Dict[str, Any]:
        """Call the LLM with tool-use support for on-demand definition retrieval.

        Used in Phase 2 (label-only injection). The LLM sees class labels
        without definitions and can call get_class_definition to retrieve
        definitions for disambiguation.

        Uses streaming messages.stream() with a tool-use conversation
        loop to avoid WSL2 TCP timeout on long responses.
        Max 25 tool-call round-trips to prevent runaway. Concept types
        with 300+ existing classes (capabilities, constraints, obligations)
        routinely need 10-15 rounds for definition lookups.
        """
        from app.utils.llm_utils import get_llm_client

        client = get_llm_client()
        if not client:
            logger.error("No LLM client available")
            return {}

        logger.info(
            f"_call_llm_with_tools: sending {len(prompt)} chars, "
            f"model={self.model_name}, "
            f"max_tokens={self.config['max_tokens']}, "
            f"tools={len(self.ONTOLOGY_LOOKUP_TOOLS)}"
        )

        messages = [{"role": "user", "content": prompt}]
        max_rounds = 25
        _system = (getattr(self, '_rendered_system', '') or '').strip()

        try:
            for round_num in range(max_rounds):
                # Use streaming to avoid WSL2 TCP timeout on long responses.
                # client.messages.stream() supports tool_use and end_turn
                # stop reasons identically to messages.create().
                stream_kwargs = dict(
                    model=self.model_name,
                    max_tokens=self.config['max_tokens'],
                    **self._maybe_temperature(),
                    messages=messages,
                    tools=self.ONTOLOGY_LOOKUP_TOOLS,
                )
                if _system:
                    stream_kwargs['system'] = _system
                with client.messages.stream(**stream_kwargs) as stream:
                    # Consume the stream to get the final message
                    response = stream.get_final_message()

                logger.info(
                    f"Tool-use round {round_num + 1}: "
                    f"{response.usage.input_tokens} in / "
                    f"{response.usage.output_tokens} out, "
                    f"stop={response.stop_reason}"
                )

                if response.stop_reason == 'end_turn':
                    # Extract text content from the response
                    response_text = ""
                    for block in response.content:
                        if block.type == 'text':
                            response_text += block.text

                    self.last_raw_response = response_text
                    logger.info(
                        f"Tool-use complete after {round_num + 1} rounds, "
                        f"{self.tool_call_count} tool calls this extraction"
                    )
                    return extract_json_from_response(response_text)

                if response.stop_reason == 'max_tokens':
                    # Truncated -- extract what we can
                    response_text = ""
                    for block in response.content:
                        if block.type == 'text':
                            response_text += block.text
                    self.last_raw_response = response_text
                    logger.warning(
                        f"Tool-use response truncated at "
                        f"{self.config['max_tokens']} tokens"
                    )
                    response_text = self._repair_truncated_json(response_text)
                    return extract_json_from_response(response_text)

                if response.stop_reason == 'tool_use':
                    # Process tool calls and continue the conversation
                    # Add assistant's response (with tool_use blocks) to messages
                    messages.append({
                        "role": "assistant",
                        "content": response.content,
                    })

                    # Execute each tool call and collect results
                    tool_results = []
                    for block in response.content:
                        if block.type != 'tool_use':
                            continue

                        tool_result = self._execute_tool_call(
                            block.name, block.input
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": tool_result,
                        })

                    messages.append({
                        "role": "user",
                        "content": tool_results,
                    })
                    continue

                # Unexpected stop reason
                logger.warning(
                    f"Unexpected stop_reason: {response.stop_reason}"
                )
                response_text = ""
                for block in response.content:
                    if block.type == 'text':
                        response_text += block.text
                self.last_raw_response = response_text
                return extract_json_from_response(response_text)

            # Exhausted max rounds -- try one final call without tools
            # to force the LLM to produce its JSON response.
            logger.warning(
                f"Tool-use loop hit max rounds ({max_rounds}) "
                f"for {self.concept_type}, forcing final response"
            )
            try:
                messages.append({
                    "role": "assistant",
                    "content": response.content,
                })
                # Add stub results for any pending tool calls so the
                # conversation is valid, then call without tools.
                tool_stubs = []
                for block in response.content:
                    if block.type == 'tool_use':
                        tool_stubs.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": "Definition not available. Proceed with extraction using the labels you already have.",
                        })
                if tool_stubs:
                    messages.append({"role": "user", "content": tool_stubs})

                final_kwargs = dict(
                    model=self.model_name,
                    max_tokens=self.config['max_tokens'],
                    **self._maybe_temperature(),
                    messages=messages,
                )
                if _system:
                    final_kwargs['system'] = _system
                with client.messages.stream(**final_kwargs) as final_stream:
                    final_response = final_stream.get_final_message()

                response_text = ""
                for block in final_response.content:
                    if block.type == 'text':
                        response_text += block.text
                if response_text:
                    self.last_raw_response = response_text
                    logger.info(
                        f"Forced final response: {len(response_text)} chars, "
                        f"stop={final_response.stop_reason}"
                    )
                    if final_response.stop_reason == 'max_tokens':
                        response_text = self._repair_truncated_json(
                            response_text
                        )
                    return extract_json_from_response(response_text)
            except Exception as fallback_err:
                logger.error(
                    f"Forced final response failed: {fallback_err}"
                )
            return {}

        except Exception as e:
            logger.error(
                f"Tool-use LLM call failed for {self.concept_type}: "
                f"{type(e).__name__}: {e}"
            )
            import traceback
            logger.error(f"  Traceback: {traceback.format_exc()}")
            return {}

    def _execute_tool_call(
        self, tool_name: str, tool_input: Dict[str, Any]
    ) -> str:
        """Execute a tool call against OntServe and return the result text.

        Maps the LLM-facing tool name (get_class_definition) to the
        OntServe MCP tool (get_entity_by_label). The ExternalMCPClient
        already parses the JSON-RPC response, returning
        {'success': True, 'result': <dict>}.
        """
        if tool_name != 'get_class_definition':
            return f"Unknown tool: {tool_name}"

        label = tool_input.get('label', '')
        self.tool_call_count += 1

        try:
            result = self.mcp_client.call_tool(
                'get_entity_by_label', {'label': label}
            )

            if not (isinstance(result, dict) and result.get('success')):
                logger.warning(f"MCP call failed for label '{label}': {result}")
                return f"Failed to retrieve definition for '{label}'."

            content = result['result']
            found = content.get('found', False)
            self.tool_call_log.append({
                'label': label,
                'found': found,
                'source': content.get('source_ontology', ''),
                'concept_type': self.concept_type,
            })

            if found:
                definition = content.get('definition', 'No definition available')
                source = content.get('source_ontology', 'unknown')
                parent = content.get('parent_type', '')
                logger.debug(f"Tool call: '{label}' -> found in {source}")
                return (
                    f"Class: {label}\n"
                    f"Definition: {definition}\n"
                    f"Source ontology: {source}\n"
                    f"Parent class: {parent}"
                )
            else:
                logger.debug(f"Tool call: '{label}' -> not found")
                return f"Class '{label}' not found in the ontology."

        except Exception as e:
            logger.error(f"Tool call error for '{label}': {e}")
            return f"Error retrieving definition for '{label}': {str(e)}"
