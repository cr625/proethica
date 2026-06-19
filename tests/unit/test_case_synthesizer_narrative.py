"""
Golden-output characterization for CaseSynthesizer narrative helpers, locking the
behavior of the NarrativeConstructionMixin extraction (plan: services-modularization.md,
Phase 2 case_synthesizer). _generate_case_summary is pure (uses only its args), so it
is called unbound with a dummy self -- no model/DB/app context.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.case_synthesizer import CaseSynthesizer


def _summary(foundation, cps, conclusions):
    # unbound call: the method does not touch self
    return CaseSynthesizer._generate_case_summary(object(), foundation, cps, conclusions)


def test_case_summary_golden():
    foundation = SimpleNamespace(roles=[SimpleNamespace(label="Engineer A")])
    cps = [SimpleNamespace(decision_question="Should the engineer disclose?")]
    conclusions = [{"label": "The Board found a duty to disclose"}]
    assert _summary(foundation, cps, conclusions) == (
        "Engineer A faced 1 key decision point "
        "involving Should the engineer disclose? "
        "The Board found a duty to disclose"
    )


def test_case_summary_plural_decisions():
    foundation = SimpleNamespace(roles=[SimpleNamespace(label="Engineer B")])
    cps = [SimpleNamespace(decision_question="Q1?"), SimpleNamespace(decision_question="Q2?")]
    out = _summary(foundation, cps, [{"label": "ok"}])
    assert "faced 2 key decision points " in out   # plural 's'


def test_case_summary_defaults_when_empty():
    foundation = SimpleNamespace(roles=[])
    out = _summary(foundation, [], [])
    assert out.startswith("An engineer faced 0 key decision points ")  # 0 != 1 -> plural
    assert "a professional ethics question" in out
    assert "The Board deliberated" in out
