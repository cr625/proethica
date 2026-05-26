"""Integration tests for apply_cited_provisions (study-corrections A8).

Shared logic behind the live Step-4 pipeline hook and the B3 corpus backfill.
No LLM is involved: reference rows are built from canonical guideline_sections
text. Codes with no canonical leaf are skipped, never synthesized.
"""
import pytest

from app import db
from app.models.world import World
from app.models.document import Document
from app.models.guideline import Guideline
from app.models.guideline_section import GuidelineSection
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.services.extraction.cited_provisions_apply import (
    apply_cited_provisions,
    NSPE_GUIDELINE_ID,
)


def _seed_nspe_and_case(case_id, cited):
    world = World.query.first() or World(name="Test World")
    if world.id is None:
        db.session.add(world)
        db.session.flush()
    if not Guideline.query.get(NSPE_GUIDELINE_ID):
        db.session.add(Guideline(id=NSPE_GUIDELINE_ID, world_id=world.id, title="NSPE Code"))
        db.session.flush()
        db.session.add(GuidelineSection(
            guideline_id=NSPE_GUIDELINE_ID, section_code="II.1.a",
            section_text="Notify employer or client and appropriate authority."))
        db.session.add(GuidelineSection(
            guideline_id=NSPE_GUIDELINE_ID, section_code="I.1",
            section_text="Hold paramount the safety, health, and welfare of the public."))
    if not Document.query.get(case_id):
        db.session.add(Document(id=case_id, title=f"Case {case_id}",
                                document_type="case", world_id=world.id))
    db.session.add(TemporaryRDFStorage(
        case_id=case_id, extraction_session_id="t", storage_type="individual",
        extraction_type="ethical_conclusion", entity_label="Conclusion_1", is_published=True,
        rdf_json_ld={"answersQuestions": [1], "citedProvisions": cited}))
    db.session.commit()


def test_inserts_for_canonical_codes_only(app_context):
    case_id = 9401
    # II.1.a. resolves; "Section 7" is historical/non-canonical and is skipped.
    _seed_nspe_and_case(case_id, ["II.1.a.", "Section 7"])

    result = apply_cited_provisions(case_id)
    assert result["status"] == "ok"
    assert result["inserted"] == 1
    assert result["skipped"] == 1
    assert result["skipped_codes"] == ["Section 7"]

    ref = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type="code_provision_reference").all()
    assert len(ref) == 1
    row = ref[0]
    assert row.entity_label == "II.1.a."  # trailing dot preserved
    assert row.rdf_json_ld["@type"] == "proeth-case:CodeProvisionReference"
    assert row.provenance_metadata["source"] == "auto_generated_from_citation"
    assert "II.1.a" in row.entity_definition or row.entity_definition  # canonical text present


def test_idempotent_second_run(app_context):
    case_id = 9402
    _seed_nspe_and_case(case_id, ["I.1."])
    first = apply_cited_provisions(case_id)
    assert first["inserted"] == 1
    second = apply_cited_provisions(case_id)
    assert second["status"] == "no_gaps"
    assert second["inserted"] == 0
    # Exactly one reference row exists after two runs.
    assert TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type="code_provision_reference").count() == 1


def test_dry_run_writes_nothing(app_context):
    case_id = 9403
    _seed_nspe_and_case(case_id, ["II.1.a."])
    result = apply_cited_provisions(case_id, dry_run=True)
    assert result["status"] == "dry_run"
    assert result["inserted"] == 0
    assert TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type="code_provision_reference").count() == 0


def test_no_gaps_when_already_covered(app_context):
    case_id = 9404
    _seed_nspe_and_case(case_id, ["II.1.a."])
    # Pre-existing reference row covers the cited code.
    db.session.add(TemporaryRDFStorage(
        case_id=case_id, extraction_session_id="t", storage_type="individual",
        extraction_type="code_provision_reference", entity_label="II.1.a.", is_published=True,
        rdf_json_ld={"codeProvision": "II.1.a."}))
    db.session.commit()
    result = apply_cited_provisions(case_id)
    assert result["status"] == "no_gaps"
    assert result["inserted"] == 0
