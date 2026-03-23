"""Tests for scenario_consolidation_service."""
import pytest
from app.services.scenario_consolidation_service import (
    consolidate_branches,
    _score_branch,
    _select_representatives,
    _extract_base_name,
    _word_overlap,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _branch(label="Engineer A", question="Should they disclose?",
            obligations=None, options=None, board_rationale="",
            board_choice_idx=0):
    """Build a minimal branch dict for testing."""
    if obligations is None:
        obligations = ["Duty of Candor", "Loyalty"]
    if options is None:
        options = [
            {"label": "Disclose", "is_board_choice": (board_choice_idx == 0),
             "consequence_narrative": "Disclosed."},
            {"label": "Stay silent", "is_board_choice": (board_choice_idx == 1),
             "consequence_narrative": "Stayed silent."},
        ]
    return {
        "decision_maker_label": label,
        "question": question,
        "competing_obligation_labels": obligations,
        "options": options,
        "board_rationale": board_rationale,
    }


# ---------------------------------------------------------------------------
# _extract_base_name
# ---------------------------------------------------------------------------

class TestExtractBaseName:
    def test_engineer_with_suffix(self):
        assert _extract_base_name("Engineer A (lead engineer)") == "Engineer A"

    def test_client_label(self):
        assert _extract_base_name("Client W") == "Client W"

    def test_professor_label(self):
        assert _extract_base_name("Professor Smith, Department Chair") == "Professor Smith"

    def test_plain_string(self):
        assert _extract_base_name("Board of Directors") == "Board of Directors"

    def test_empty(self):
        assert _extract_base_name("") == ""


# ---------------------------------------------------------------------------
# _word_overlap
# ---------------------------------------------------------------------------

class TestWordOverlap:
    def test_identical(self):
        assert _word_overlap("disclose the conflict", "disclose the conflict") == 1.0

    def test_no_overlap(self):
        assert _word_overlap("disclose everything", "stay silent") == 0.0

    def test_partial(self):
        result = _word_overlap("disclose the conflict", "resolve the conflict")
        assert 0.3 < result < 0.8

    def test_empty_a(self):
        assert _word_overlap("", "something") == 0.0

    def test_empty_both(self):
        assert _word_overlap("", "") == 0.0


# ---------------------------------------------------------------------------
# _score_branch
# ---------------------------------------------------------------------------

class TestScoreBranch:
    def test_richer_branch_scores_higher(self):
        rich = _branch(
            obligations=["Duty A", "Duty B", "Duty C"],
            board_rationale="The board found...",
            board_choice_idx=1,  # non-obvious
        )
        sparse = _branch(obligations=[], board_rationale="")
        assert _score_branch(rich) > _score_branch(sparse)

    def test_consequence_data_adds_score(self):
        with_cons = _branch()
        without_cons = _branch(options=[
            {"label": "Opt A", "is_board_choice": True},
            {"label": "Opt B", "is_board_choice": False},
        ])
        assert _score_branch(with_cons) > _score_branch(without_cons)

    def test_non_obvious_board_choice_bonus(self):
        obvious = _branch(board_choice_idx=0)
        non_obvious = _branch(board_choice_idx=1)
        assert _score_branch(non_obvious) > _score_branch(obvious)

    def test_short_question_no_bonus(self):
        short_q = _branch(question="Yes?")
        good_q = _branch(question="Should the engineer disclose the conflict of interest?")
        assert _score_branch(good_q) > _score_branch(short_q)


# ---------------------------------------------------------------------------
# _select_representatives
# ---------------------------------------------------------------------------

class TestSelectRepresentatives:
    def test_one_per_group_when_under_target(self):
        groups = {
            "Engineer A": [{"index": 0, "score": 10}],
            "Client W": [{"index": 3, "score": 8}],
        }
        result = _select_representatives(groups, target_count=5)
        assert sorted(result) == [0, 3]

    def test_fills_from_remaining(self):
        groups = {
            "Engineer A": [
                {"index": 0, "score": 10},
                {"index": 1, "score": 5},
                {"index": 2, "score": 3},
            ],
            "Client W": [{"index": 3, "score": 8}],
        }
        result = _select_representatives(groups, target_count=3)
        assert len(result) == 3
        assert 0 in result  # top of Engineer A
        assert 3 in result  # top of Client W
        assert 1 in result  # next best from Engineer A

    def test_trims_when_too_many_groups(self):
        groups = {
            f"Actor {i}": [{"index": i, "score": 10 - i}]
            for i in range(10)
        }
        result = _select_representatives(groups, target_count=5)
        assert len(result) == 5
        # Highest-scored groups should be selected
        assert 0 in result


# ---------------------------------------------------------------------------
# consolidate_branches (integration of above)
# ---------------------------------------------------------------------------

class TestConsolidateBranches:
    def test_all_included_when_under_target(self):
        branches = [_branch() for _ in range(3)]
        result = consolidate_branches(branches, target_count=7)
        assert result["method"] == "all_included"
        assert result["branch_indices"] == [0, 1, 2]

    def test_all_included_when_equal_to_target(self):
        branches = [_branch() for _ in range(7)]
        result = consolidate_branches(branches, target_count=7)
        assert result["method"] == "all_included"

    def test_consolidates_when_over_target(self):
        branches = [
            _branch(label="Engineer A", question=f"Question {i}?")
            for i in range(12)
        ]
        result = consolidate_branches(branches, target_count=5)
        assert result["method"] == "auto_consolidate_v1"
        assert len(result["branch_indices"]) == 5
        assert result["branch_indices"] == sorted(result["branch_indices"])

    def test_preserves_narrative_order(self):
        branches = [
            _branch(label="Engineer A"),
            _branch(label="Client W"),
            _branch(label="Engineer A"),
            _branch(label="Client W"),
            _branch(label="Engineer A"),
            _branch(label="Client W"),
            _branch(label="Engineer A"),
            _branch(label="Client W"),
            _branch(label="Engineer A"),
            _branch(label="Client W"),
        ]
        result = consolidate_branches(branches, target_count=5)
        indices = result["branch_indices"]
        assert indices == sorted(indices), "Selected indices must be in original order"

    def test_multiple_actor_groups_represented(self):
        branches = [
            _branch(label="Engineer A"),
            _branch(label="Engineer A"),
            _branch(label="Engineer A"),
            _branch(label="Client W"),
            _branch(label="Client W"),
            _branch(label="Client W"),
            _branch(label="Professor Smith"),
            _branch(label="Professor Smith"),
            _branch(label="Professor Smith"),
        ]
        result = consolidate_branches(branches, target_count=5)
        selected_labels = [branches[i]["decision_maker_label"] for i in result["branch_indices"]]
        unique_actors = set(_extract_base_name(l) for l in selected_labels)
        assert len(unique_actors) >= 2, "Should represent multiple actor groups"

    def test_overridden_field_default_false(self):
        branches = [_branch() for _ in range(3)]
        result = consolidate_branches(branches)
        assert result["overridden"] is False

    def test_empty_branches(self):
        result = consolidate_branches([], target_count=5)
        assert result["branch_indices"] == []
        assert result["method"] == "all_included"
