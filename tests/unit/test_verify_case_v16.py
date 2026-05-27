"""Hermetic tests for the V16 QC check (Step-3 direct emission) in
``docs-internal/scripts/verify_case_quick.py``.

V16 confirms the inline Step-3 hooks ran: ``proeth:temporalSequence`` on every
Action/Event timeline row, and ``proeth:raisesObligation`` on every
obligation-bearing Action. The script talks to Postgres via a ``psql`` helper;
these tests monkeypatch that helper with a query-routing stub so the V16 logic
is exercised without a database.
"""

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "docs-internal" / "scripts" / "verify_case_quick.py"
)

# verify_case_quick.py lives under docs-internal/ (gitignored internal tooling); skip
# this module on a checkout that does not include it rather than erroring at collection.
pytestmark = pytest.mark.skipif(
    not _SCRIPT.exists(), reason="docs-internal/scripts/verify_case_quick.py not present"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_case_quick", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_psql(seq_counts, raises_counts):
    """Return a psql stub routed by query substring.

    seq_counts = (ae_with_seq, ae_total); raises_counts = (raises_missing, act_with_obl).
    Non-V16 queries return values that keep the other checks quiet/irrelevant.
    """
    def _stub(query, db="ai_ethical_dm"):
        if "proeth:temporalSequence" in query:
            return f"{seq_counts[0]}|{seq_counts[1]}"
        if "proeth:raisesObligation" in query:
            return f"{raises_counts[0]}|{raises_counts[1]}"
        # All 16 extraction types present (avoid spurious V6 CRITICALs)
        if "GROUP BY extraction_type" in query:
            mod = _load_module()
            return "\n".join(f"{t}|5" for t in mod.EXPECTED_TYPES)
        if "is_published" in query:
            return "100|100"
        if "PREVIOUSLY EXTRACTED CLASSES" in query:
            return "roles|facts|HAS_CONTEXT"
        if "ontology_entities" in query:
            return "42"
        if "DISTINCT llm_model" in query:
            return "claude-sonnet-4-6"
        return ""
    return _stub


def test_v16_passes_when_fields_complete(monkeypatch, capsys):
    m = _load_module()
    monkeypatch.setattr(m, "psql", _make_psql(seq_counts=(10, 10), raises_counts=(0, 5)))
    monkeypatch.setattr(m.os.path, "exists", lambda p: False)  # skip TTL file read
    m.verify_case(999)
    out = capsys.readouterr().out
    assert "Action/Event rows sequenced PASS" in out
    assert "raises-partition applied to 5/5" in out
    assert "V16" not in out  # no V16 issue raised


def test_v16_fires_on_missing_temporal_sequence(monkeypatch, capsys):
    m = _load_module()
    monkeypatch.setattr(m, "psql", _make_psql(seq_counts=(7, 10), raises_counts=(0, 5)))
    monkeypatch.setattr(m.os.path, "exists", lambda p: False)
    m.verify_case(999)
    out = capsys.readouterr().out
    assert "CRITICAL: V16 temporal sequence missing on 3/10" in out


def test_v16_fires_on_missing_raises(monkeypatch, capsys):
    m = _load_module()
    monkeypatch.setattr(m, "psql", _make_psql(seq_counts=(10, 10), raises_counts=(3, 4)))
    monkeypatch.setattr(m.os.path, "exists", lambda p: False)
    m.verify_case(999)
    out = capsys.readouterr().out
    assert "CRITICAL: V16 obligation engagement not applied to 3/4" in out


def test_v16_skips_when_under_two_entries(monkeypatch, capsys):
    """Mirrors the apply-hook's insufficient_entries no-op (<2 rows)."""
    m = _load_module()
    monkeypatch.setattr(m, "psql", _make_psql(seq_counts=(0, 1), raises_counts=(0, 0)))
    monkeypatch.setattr(m.os.path, "exists", lambda p: False)
    m.verify_case(999)
    out = capsys.readouterr().out
    assert "V16 temporal sequence missing" not in out
    assert "no ordering needed" in out


def test_v16_exempts_zero_obligation_actions(monkeypatch, capsys):
    """Actions with no obligations legitimately lack the raises key (act_with_obl=0)."""
    m = _load_module()
    monkeypatch.setattr(m, "psql", _make_psql(seq_counts=(3, 3), raises_counts=(0, 0)))
    monkeypatch.setattr(m.os.path, "exists", lambda p: False)
    m.verify_case(999)
    out = capsys.readouterr().out
    assert "V16 obligation engagement not applied" not in out
    assert "no Actions carry obligations" in out
