"""
Smoke/characterization test for the Phase2ExtractionMixin extraction (plan:
services-modularization.md, Phase 2 case_synthesizer increment 2).

The Phase-2 methods are LLM/DB-bound (no pure parse method), so this exercises the
smallest one, _get_transformation_type, with the module-level db stubbed. It both
characterizes the read (row -> value, no row -> '') and proves db/text resolve in
the relocated phase2 module (the relocation's main risk is a missing import).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.case_synthesizer.phase2 import Phase2ExtractionMixin


def test_get_transformation_type_reads_db(monkeypatch):
    fake_db = MagicMock()
    fake_db.session.execute.return_value.fetchone.return_value = ("precedent_extension",)
    monkeypatch.setattr("app.services.case_synthesizer.phase2.db", fake_db)
    # unbound call: the method does not use self
    assert Phase2ExtractionMixin._get_transformation_type(object(), 7) == "precedent_extension"


def test_get_transformation_type_empty_when_no_row(monkeypatch):
    fake_db = MagicMock()
    fake_db.session.execute.return_value.fetchone.return_value = None
    monkeypatch.setattr("app.services.case_synthesizer.phase2.db", fake_db)
    assert Phase2ExtractionMixin._get_transformation_type(object(), 7) == ""
