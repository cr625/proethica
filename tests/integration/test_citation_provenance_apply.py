"""Integration tests for apply_citation_provenance (study-corrections Phase 4).

Shared logic behind the live Step-4 pipeline hook and the historical-citation
corpus driver. No LLM: non-resolvable citations are classified by pattern and
annotated with a proeth:citationProvenance field. citedProvisions is never
modified; resolvable citations (modern guideline_sections leaves) are left for A8.
"""
import pytest

from app import db
from app.models.world import World
from app.models.document import Document
from app.models.guideline import Guideline
from app.models.guideline_section import GuidelineSection
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.services.extraction.citation_provenance_apply import (
    apply_citation_provenance,
    classify,
)
from app.services.extraction.cited_provisions_apply import NSPE_GUIDELINE_ID


def _seed(case_id, cited, label="Conclusion_1"):
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
        extraction_type="ethical_conclusion", entity_label=label, is_published=True,
        rdf_json_ld={"answersQuestions": [1], "citedProvisions": cited}))
    db.session.commit()


def test_classify_categories():
    canon = {"II.1.a", "I.1"}
    assert classify("II.1.a.", canon) is None          # resolves -> not annotated
    assert classify("I.1", canon) is None
    assert classify("II.4.", canon) == "modern_section_no_leaf"
    assert classify("NSPE Code of Ethics Section 2", canon) == "nspe_pre_2007_numbered"
    assert classify("Section 2(a)", canon) == "nspe_pre_2007_numbered"
    assert classify("2(c)", canon) == "nspe_pre_2007_numbered"
    assert classify("BER Case No. 67-10", canon) == "ber_cross_case_precedent"
    assert classify("BER_Case_62-14", canon) == "ber_cross_case_precedent"  # underscore form
    assert classify("Brooks Act (Federal A/E Selection Law)", canon) == "external_law_or_regulation"
    assert classify("State_Engineering_Registration_Law_Discipline", canon) == "external_law_or_regulation"
    assert classify("Engineer-Confidentiality-Obligation-Standard", canon) == "synthesized_standard_label"
    assert classify("NSPE-Code-of-Ethics-Primary", canon) == "generic_nspe_no_leaf"


def test_annotates_unmapped_only(app_context):
    case_id = 9501
    _seed(case_id, ["II.1.a.", "NSPE Code of Ethics Section 2", "BER Case No. 67-10"])
    result = apply_citation_provenance(case_id)
    assert result["status"] == "ok"
    assert result["annotated"] == 1

    row = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type="ethical_conclusion").first()
    prov = row.rdf_json_ld["proeth:citationProvenance"]
    cats = {u["category"] for u in prov["unmapped"]}
    assert cats == {"nspe_pre_2007_numbered", "ber_cross_case_precedent"}
    assert prov["resolvable"] == ["II.1.a."]          # modern leaf left for A8
    # citedProvisions untouched
    assert len(row.rdf_json_ld["citedProvisions"]) == 3
    assert row.provenance_metadata["phase4_citation_annotation"]


def test_no_unmapped_when_all_resolve(app_context):
    case_id = 9502
    _seed(case_id, ["II.1.a.", "I.1."])
    result = apply_citation_provenance(case_id)
    assert result["status"] == "no_unmapped"
    assert result["annotated"] == 0
    row = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type="ethical_conclusion").first()
    assert "proeth:citationProvenance" not in row.rdf_json_ld


def test_idempotent_second_run(app_context):
    case_id = 9503
    _seed(case_id, ["Section 7"])
    first = apply_citation_provenance(case_id)
    assert first["annotated"] == 1
    second = apply_citation_provenance(case_id)
    assert second["status"] == "no_unmapped"   # already-annotated row is skipped
    assert second["annotated"] == 0


def test_dry_run_writes_nothing(app_context):
    case_id = 9504
    _seed(case_id, ["Section 8(b)"])
    result = apply_citation_provenance(case_id, dry_run=True)
    assert result["status"] == "dry_run"
    assert result["annotated"] == 1
    row = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type="ethical_conclusion").first()
    assert "proeth:citationProvenance" not in row.rdf_json_ld
