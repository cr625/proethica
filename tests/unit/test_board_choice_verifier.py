"""Board-choice verification pass (2026-07-08 Phase-B audit): a single-purpose
checker overrides is_board_choice against the full board conclusions --
generation-embedded marking inverted the flag in violation cases (case 7
marked condemned conduct as the Board's choice) and prompt rules did not fix
it. Covers: override to the checker's pick, clearing when the Board made no
determination, and leaving flags unchanged on unmatched picks or checker
failure."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.decision_point_synthesizer.board_choice_verifier import verify_board_choices


def _dp(focus_id, options):
    return SimpleNamespace(focus_id=focus_id, decision_question="Should X?",
                           options=[dict(o) for o in options])


def _client(picks):
    resp = MagicMock()
    resp.stop_reason = "end_turn"
    block = MagicMock(); block.type = "text"
    block.text = json.dumps({"picks": picks})
    resp.content = [block]
    client = MagicMock()
    client.messages.create.return_value = resp
    return client


CONCLUSIONS = [{"conclusion_text": "Engineer A's cursory review was unethical; a full review was required."}]


def test_inverted_flag_overridden():
    dp = _dp("DP1", [
        {"label": "Perform Only Cursory Review", "is_board_choice": True},
        {"label": "Conduct Full Independent Review", "is_board_choice": False},
    ])
    s = verify_board_choices(7, [dp], CONCLUSIONS, llm_client=_client(
        [{"id": "DP1", "board_option_label": "Conduct Full Independent Review", "reason": "condemned conduct"}]))
    assert s["overridden"] == 1
    assert [o["is_board_choice"] for o in dp.options] == [False, True]


def test_null_pick_clears_flags():
    dp = _dp("DP1", [
        {"label": "A", "is_board_choice": True},
        {"label": "B", "is_board_choice": False},
    ])
    s = verify_board_choices(7, [dp], CONCLUSIONS, llm_client=_client(
        [{"id": "DP1", "board_option_label": None, "reason": "no determination"}]))
    assert s["cleared"] == 1
    assert not any(o["is_board_choice"] for o in dp.options)


def test_unmatched_pick_leaves_flags():
    dp = _dp("DP1", [
        {"label": "A", "is_board_choice": True},
        {"label": "B", "is_board_choice": False},
    ])
    s = verify_board_choices(7, [dp], CONCLUSIONS, llm_client=_client(
        [{"id": "DP1", "board_option_label": "Nonexistent Option", "reason": "?"}]))
    assert s["unmatched"] == 1
    assert dp.options[0]["is_board_choice"] is True


def test_checker_failure_never_fatal(monkeypatch):
    import app.services.decision_point_synthesizer.board_choice_verifier as mod
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    dp = _dp("DP1", [{"label": "A", "is_board_choice": True},
                     {"label": "B", "is_board_choice": False}])
    client = MagicMock()
    client.messages.create.side_effect = RuntimeError("api down")
    s = verify_board_choices(7, [dp], CONCLUSIONS, llm_client=client)
    assert s["error"] == "no valid checker response"
    assert dp.options[0]["is_board_choice"] is True


def test_confirmed_flag_untouched():
    dp = _dp("DP1", [
        {"label": "A", "is_board_choice": True},
        {"label": "B", "is_board_choice": False},
    ])
    s = verify_board_choices(7, [dp], CONCLUSIONS, llm_client=_client(
        [{"id": "DP1", "board_option_label": "a", "reason": "case-insensitive confirm"}]))
    assert s["overridden"] == 0 and s["checked"] == 1
    assert dp.options[0]["is_board_choice"] is True
