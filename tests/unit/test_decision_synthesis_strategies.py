"""
Golden-output characterization tests for the Phase-3 LLM-fallback parse methods.

Written before the strategies extraction (plan: services-modularization.md, Phase 2
decision_point_synthesizer increment 2) and re-run after, to prove the relocation
of the LLM strategy methods into a mixin is behavior-preserving. These exercise
the parse methods with controlled LLM-response strings (no DB/LLM/model): the only
DB touch, _build_entity_uri_lookup, is stubbed on the instance.
"""

from __future__ import annotations

import json

from app.services.decision_point_synthesizer import DecisionPointSynthesizer


def _synth_with_lookup(lookup):
    s = DecisionPointSynthesizer()
    # _build_entity_uri_lookup hits the DB; stub it deterministically.
    s._build_entity_uri_lookup = lambda case_id: lookup
    return s


def test_parse_causal_link_response_golden():
    s = _synth_with_lookup({"engineer a": "http://role/a"})
    resp = json.dumps([{
        "focus_id": "DP1",
        "description": "desc",
        "decision_question": "What should the engineer do?",
        "role_label": "Engineer A",
        "obligation_label": "Safety Obligation",
        "addresses_questions": ["Q1"],
        "toulmin_data": "the facts",
        "toulmin_warrants": "the duties",
        "toulmin_rebuttals": "the doubt",
        "provision_labels": ["NSPE I.1"],
        "intensity_score": 0.8,
        "qc_alignment_score": 0.6,
        "board_resolution": "resolved thus",
        "options": [
            {"option_id": "O1", "label": "Disclose", "description": "tell", "is_board_choice": True},
        ],
    }])
    questions = [{"uri": "http://q1", "question_text": "What?"}]
    conclusions = [{"uri": "http://c1"}]

    out = s._parse_causal_link_response(resp, case_id=1, questions=questions, conclusions=conclusions)

    assert len(out) == 1
    dp = out[0]
    assert dp.focus_id == "DP1"
    assert dp.focus_number == 1
    assert dp.role_label == "Engineer A"
    assert dp.role_uri == "http://role/a"            # resolved via lookup
    assert dp.obligation_label == "Safety Obligation"
    assert dp.obligation_uri == ""                   # label present but not in lookup -> '' (not None)
    assert dp.toulmin.data_summary == "the facts"
    assert dp.toulmin.backing_provisions == ["NSPE I.1"]
    assert dp.intensity_score == 0.8
    assert dp.qc_alignment_score == 0.6
    assert dp.addresses_questions == ["http://q1"]   # Q1 -> uri
    assert dp.aligned_question_uri == "http://q1"
    assert dp.aligned_question_text == "What?"
    assert dp.options[0]["is_board_choice"] is True
    assert dp.synthesis_method == "llm_fallback"


def test_parse_causal_link_response_invalid_score_falls_back_to_zero():
    s = _synth_with_lookup({})
    resp = json.dumps([{
        "focus_id": "DP1", "description": "d", "decision_question": "q",
        "role_label": "Someone", "intensity_score": "not-a-number",
    }])
    out = s._parse_causal_link_response(resp, 1, [], [])
    assert len(out) == 1
    assert out[0].intensity_score == 0.0   # non-numeric -> 0.0, not a sentinel


def test_parse_refinement_response_golden():
    s = DecisionPointSynthesizer()
    resp = json.dumps([{
        "focus_id": "DP1",
        "description": "d",
        "decision_question": "q?",
        "role_label": "Engineer B",
        "role_uri": "http://llm/roleB",
        "obligation_label": "Obl",
        "obligation_uri": "http://llm/obl",
        "addresses_questions": [0],
        "provision_labels": ["P1"],
        "options": [{"label": "o"}],
        "intensity_score": 0.5,
        "qc_alignment_score": 0.4,
        "board_resolution": "r",
    }])
    questions = [{"uri": "http://q0", "text": "q0"}]

    # empty top_candidates and no case graph -> no label->URI lookup. An
    # LLM-emitted URI is kept ONLY when the case graph knows it; unknown URIs
    # are dropped rather than stored (2026-07-08: the unvalidated fallback put
    # obligation URIs into role slots on case 9). Labels are retained.
    out = s._parse_refinement_response(resp, top_candidates=[], questions=questions,
                                       conclusions=[], question_emergence=[], resolution_patterns=[])

    assert len(out) == 1
    dp = out[0]
    assert dp.focus_id == "DP1"
    assert dp.role_uri == ""   # unknown LLM URI dropped
    assert dp.role_label == "Engineer B"
    assert dp.obligation_uri == ""   # unknown LLM URI dropped
    assert dp.addresses_questions == ["http://q0"]   # int index 0 -> questions[0].uri
    assert dp.aligned_question_uri == "http://q0"
    assert dp.aligned_question_text == "q0"
    assert dp.source == "unified"
    assert dp.synthesis_method == "algorithmic+llm"
    assert dp.llm_refined_description == "d"
