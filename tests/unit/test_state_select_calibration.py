"""
Tests for the state-edge select calibration (2026-07-11): 3-vote per-item
majority on the default tier, cached identical vote prompts, and unchanged
single-vote behavior for every other caller of the shared driver.

The calibration answers a measured instability: a controlled 5x-repeatability
experiment showed single select calls flip run to run on BOTH tiers (2-4
distinct selection sets of 5 at temperature 0.0), and the fast tier sits at a
systematically different operating point (zero activatesObligation choices on
case 9 where the default tier reproduces the committed gold pair 5/5).
"""

from unittest.mock import MagicMock, patch

from app.services.extraction import edge_resolution as er
from app.services.extraction import state_edges as se

ITEMS = [
    {"id": 1, "prop": "activatesObligation", "desc": "d1",
     "shortlist": [("iri://a", "A", 0.9), ("iri://b", "B", 0.8)]},
    {"id": 2, "prop": "terminatedByEvent", "desc": "d2",
     "shortlist": [("iri://c", "C", 0.9)]},
]


def _select_with_ballots(ballots, votes=3):
    with patch.object(er, "_select_attempt", side_effect=ballots) as mock_attempt, \
         patch("app.utils.llm_utils.get_llm_client") as mock_client_fn, \
         patch("model_config.ModelConfig") as mock_cfg:
        client = MagicMock()
        client.messages.stream = MagicMock()
        mock_client_fn.return_value = client
        mock_cfg.get_claude_model.return_value = "test-model"
        out = er._llm_select(ITEMS, lambda items: "the prompt", votes=votes)
    return out, mock_attempt


def test_majority_picks_modal_choice_and_refuses_split():
    ballots = [
        {"1": "iri://a", "2": "iri://c"},
        {"1": "iri://a", "2": None},
        {"1": "iri://b", "2": None},
    ]
    out, mock_attempt = _select_with_ballots(ballots)
    assert out == {"1": "iri://a", "2": None}
    assert mock_attempt.call_count == 3
    # The votes send the identical prompt with the cached-prefix marker.
    assert all(c.kwargs.get("cache_prompt") is True
               for c in mock_attempt.call_args_list)


def test_three_way_split_resolves_to_none():
    ballots = [{"1": "iri://a", "2": None},
               {"1": "iri://b", "2": None},
               {"1": None, "2": None}]
    out, _ = _select_with_ballots(ballots)
    assert out == {"1": None, "2": None}


def test_all_none_majority_is_accepted_not_fallback():
    """Three unanimous-none votes are an ANSWER, not a failure: overriding
    them with the embedding threshold would undo the precision layer."""
    ballots = [{"1": None, "2": None}] * 3
    out, _ = _select_with_ballots(ballots)
    assert out == {"1": None, "2": None}


def test_failed_ballots_dropped_and_total_failure_falls_back():
    out, _ = _select_with_ballots([None, {"1": "iri://a", "2": None}, None])
    assert out == {"1": "iri://a", "2": None}  # majority of the ONE valid ballot
    out, _ = _select_with_ballots([None, None, None])
    assert out is None  # every vote failed -> embedding fallback


def test_single_vote_path_unchanged():
    """votes=1 (every other caller of the shared driver) keeps the original
    single-attempt + all-none-retry contract, uncached."""
    ballots = [{"1": "iri://a", "2": "iri://c"}]
    out, mock_attempt = _select_with_ballots(ballots, votes=1)
    assert out == {"1": "iri://a", "2": "iri://c"}
    assert mock_attempt.call_count == 1
    assert not mock_attempt.call_args.kwargs.get("cache_prompt")


def test_state_wrapper_passes_calibrated_settings():
    with patch.object(se, "_llm_select_generic", return_value={"1": None}) as mock_generic:
        se._llm_select(ITEMS, client=MagicMock())
    kwargs = mock_generic.call_args.kwargs
    assert kwargs["model_tier"] == "default"
    assert kwargs["votes"] == 3


def test_select_attempt_cache_flag_builds_block():
    captured = {}

    class _Stream:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        @property
        def text_stream(self):
            return iter(['{"1": 1, "2": "none"}'])

    client = MagicMock()

    def _stream(**kwargs):
        captured.update(kwargs)
        return _Stream()

    client.messages.stream.side_effect = _stream
    out = er._select_attempt(client, "claude-sonnet-5", "the prompt", ITEMS,
                             cache_prompt=True)
    content = captured["messages"][0]["content"]
    assert isinstance(content, list)
    assert content[0]["cache_control"] == {"type": "ephemeral"}
    assert out == {"1": "iri://a", "2": None}
