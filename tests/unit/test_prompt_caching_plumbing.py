"""
Tests for the within-case prompt-caching plumbing (build-gate decision 2026-07-11).

Two placements exist, both chosen because the identical prefix is re-sent
within the 5-minute TTL:

  - the label_only tool loop re-sends the full conversation every tool round
    (routinely 10-15 rounds), so the initial prompt carries a stable anchor
    breakpoint and the newest tool_result carries a moving tail breakpoint;
  - the over-reach vote panel sends one identical prompt N times, so the
    verifier's structured-stream helper marks it when cache_prompt=True.

Everywhere else deliberately stays uncached: a breakpoint on a never-re-read
prompt only pays the 1.25x cache-write premium.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.extraction.extraction_verifier import (
    _structured_stream_json,
    detect_overreach,
)
from app.services.extraction.unified_dual_extractor.llm_calls import LLMCallMixin

EPHEMERAL = {"type": "ephemeral"}


class _FakeStream:
    def __init__(self, final_message, text='{"results": []}'):
        self._final = final_message
        self._text = text

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    @property
    def text_stream(self):
        return iter([self._text])

    def get_final_message(self):
        return self._final


def _client_capturing(streams):
    """Capture stream kwargs by DEEP COPY: the tool loop deliberately mutates
    prior message dicts between rounds (unmarking the old tail breakpoint), so
    a by-reference capture would show post-mutation state instead of what each
    request actually carried at send time."""
    import copy
    calls = []
    client = MagicMock()

    def _stream(**kwargs):
        calls.append(copy.deepcopy(kwargs))
        return streams[len(calls) - 1]

    client.messages.stream.side_effect = _stream
    return client, calls


def test_structured_stream_cache_flag_marks_prompt_block():
    final = SimpleNamespace(stop_reason='end_turn')
    client, calls = _client_capturing([_FakeStream(final)])
    _structured_stream_json(client, 'test-model', 'the prompt', {"type": "object"},
                            max_tokens=100, cache_prompt=True)
    content = calls[0]['messages'][0]['content']
    assert isinstance(content, list)
    assert content[0]['text'] == 'the prompt'
    assert content[0]['cache_control'] == EPHEMERAL


def test_structured_stream_default_stays_plain_string():
    """No breakpoint on single-shot callers (verify_and_reground): a marker
    there would pay the write premium with nothing ever reading it."""
    final = SimpleNamespace(stop_reason='end_turn')
    client, calls = _client_capturing([_FakeStream(final)])
    _structured_stream_json(client, 'test-model', 'the prompt', {"type": "object"},
                            max_tokens=100)
    assert calls[0]['messages'][0]['content'] == 'the prompt'


def test_overreach_votes_send_identical_cached_prompt():
    verdict = {'results': [{'id': 0, 'overreach': False, 'reason': '', 'limiting_quote': ''}]}
    with patch('app.services.extraction.extraction_verifier._structured_stream_json',
               return_value=verdict) as mock_call, \
         patch('app.utils.llm_utils.get_llm_client', return_value=MagicMock()), \
         patch('model_config.ModelConfig') as mock_cfg:
        mock_cfg.get_claude_model.return_value = 'test-model'
        detect_overreach('case text', [{'label': 'Duty', 'definition': 'd'}], votes=3)
    assert mock_call.call_count == 3
    prompts = {c.args[2] for c in mock_call.call_args_list}
    assert len(prompts) == 1, "votes must send byte-identical prompts (the cache key)"
    assert all(c.kwargs.get('cache_prompt') is True for c in mock_call.call_args_list)


class _DummyExtractor(LLMCallMixin):
    def __init__(self):
        self.model_name = 'test-model'
        self.config = {'max_tokens': 100, 'temperature': 0.1}
        self.concept_type = 'roles'
        self.injection_mode = 'label_only'
        self.llm_client = None
        self.mcp_client = MagicMock()
        self.mcp_client.call_tool.return_value = {
            'success': True,
            'result': {'found': True, 'definition': 'd', 'source_ontology': 's',
                       'parent_type': 'p'},
        }
        self.tool_call_count = 0
        self.tool_call_log = []


def _tool_use_msg(tu_id):
    return SimpleNamespace(
        stop_reason='tool_use',
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        content=[SimpleNamespace(type='tool_use', name='get_class_definition',
                                 input={'label': 'X'}, id=tu_id)],
    )


_END = SimpleNamespace(
    stop_reason='end_turn',
    usage=SimpleNamespace(input_tokens=1, output_tokens=1),
    content=[SimpleNamespace(type='text', text='{"individuals": []}')],
)


def test_tool_loop_anchor_and_moving_tail_breakpoints():
    """Round 1 anchors the initial prompt; each tool round moves the tail
    breakpoint to the newest tool_result and unmarks the previous one (max 4
    breakpoints per request -- we hold at two)."""
    extractor = _DummyExtractor()
    streams = [_FakeStream(_tool_use_msg('tu_1')),
               _FakeStream(_tool_use_msg('tu_2')),
               _FakeStream(_END)]
    client, calls = _client_capturing(streams)

    with patch('app.utils.llm_utils.get_llm_client', return_value=client), \
         patch('model_config.ModelConfig') as mock_cfg:
        mock_cfg.supports_temperature.return_value = False
        result = extractor._call_llm_with_tools('the big prompt')

    assert result == {"individuals": []}
    assert len(calls) == 3

    # Round 1: the initial prompt is a block list with the anchor breakpoint.
    first = calls[0]['messages'][0]['content']
    assert first[0]['cache_control'] == EPHEMERAL

    # Round 2: anchor intact, round-1 tool_result carries the tail breakpoint.
    msgs2 = calls[1]['messages']
    assert msgs2[0]['content'][0]['cache_control'] == EPHEMERAL
    assert msgs2[2]['content'][-1]['cache_control'] == EPHEMERAL

    # Round 3: the round-1 tail was unmarked; the round-2 tool_result holds it.
    msgs3 = calls[2]['messages']
    assert 'cache_control' not in msgs3[2]['content'][-1]
    assert msgs3[4]['content'][-1]['cache_control'] == EPHEMERAL
    # Anchor still present -- exactly two breakpoints in the final request.
    assert msgs3[0]['content'][0]['cache_control'] == EPHEMERAL
