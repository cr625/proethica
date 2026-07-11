"""Step-4 review prose-surface joins (ROADMAP pre-rebuild item 6).

Timeline: causal_normative_link rows attach reasoning to timeline entries by
the URI fragment of rdf_json_ld['action_id'] (after '#'), never by
entity_label (the column truncates long labels). Links keyed to fragments
absent from the timeline degrade silently.

Q&C: resolution_pattern rows attach a 'resolution' dict to linked
conclusions through qc_refs (conclusion_refs + key_aliases, kind='C'), so
both the committed-URI form ('case-N#Conclusion_1') and the legacy
positional form ('case-N#C1') join; exact-string joins silently drop legacy
stores (the c422755 finding). RP rows are never published, so the join must
not depend on is_published.
"""
import pytest

from app import db
from app.models.world import World
from app.models.document import Document
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.services.validation.synthesis_view_builder import SynthesisViewBuilder


def _seed_case(case_id):
    world = World.query.first() or World(name="Test World")
    if world.id is None:
        db.session.add(world)
        db.session.flush()
    if not db.session.get(Document, case_id):
        db.session.add(Document(id=case_id, title=f"Case {case_id}",
                                document_type="case", world_id=world.id))


def _temp_row(case_id, extraction_type, entity_label, rdf, definition=None):
    return TemporaryRDFStorage(
        case_id=case_id, extraction_session_id="t", storage_type="individual",
        extraction_type=extraction_type, entity_label=entity_label,
        entity_definition=definition, rdf_json_ld=rdf)


def _seed_timeline(case_id):
    _seed_case(case_id)
    ns = f"http://proethica.org/ontology/case/{case_id}#"
    db.session.add(_temp_row(
        case_id, "temporal_dynamics_enhanced", "Alpha Beta Issuance",
        {"@id": f"{ns}Action_Alpha_Beta_Issuance", "@type": "proeth:Action",
         "proeth:hasAgent": "Engineer A",
         "proeth:description": "Engineer A issues the documents."}))
    db.session.add(_temp_row(
        case_id, "temporal_dynamics_enhanced", "Gamma Collapse",
        {"@id": f"{ns}Event_Gamma_Collapse", "@type": "proeth:Event",
         "proeth:description": "The structure collapses."}))


def _seed_qc(case_id, conclusion_uri, with_provision_row=False):
    _seed_case(case_id)
    db.session.add(_temp_row(
        case_id, "ethical_question", "Question_1",
        {"questionType": "board_explicit", "questionNumber": 1},
        definition="Was the issuance ethical?"))
    db.session.add(_temp_row(
        case_id, "ethical_conclusion", "Conclusion_1",
        {"answersQuestions": [1], "conclusionNumber": 1,
         "citedProvisions": []},
        definition="The issuance was ethical."))
    rp = {"conclusion_uri": conclusion_uri,
          "weighing_process": "The board weighed competence against safety.",
          "determinative_principles": ["Competence"],
          "determinative_facts": ["Standard of care met"],
          "resolution_conditions": "Holds when the design meets the standard of care.",
          "resolution_narrative": "No error occurred.",
          "cited_provisions": ["I.1."],
          "confidence": 0.85}
    db.session.add(_temp_row(case_id, "resolution_pattern",
                             "ResolutionPattern_1", rp))
    if with_provision_row:
        db.session.add(_temp_row(
            case_id, "code_provision_reference", "I.1", {},
            definition="Hold paramount the safety of the public."))
    db.session.commit()


def _builder():
    return SynthesisViewBuilder(published_only=False)


def test_timeline_cnl_joins_by_action_id_fragment(app_context):
    case_id = 9601
    _seed_timeline(case_id)
    # entity_label deliberately truncated (the live column truncates long
    # labels): the join must succeed through action_id alone.
    db.session.add(_temp_row(
        case_id, "causal_normative_link", "CausalLink_Alpha Beta Issuanc",
        {"action_id": f"case-{case_id}#Alpha_Beta_Issuance",
         "action_label": "Alpha Beta Issuance",
         "reasoning": "Issuing the documents fulfills the safety obligation.",
         "confidence": 0.8}))
    db.session.commit()

    view = _builder().get_timeline_view(case_id)
    by_frag = {e["fragment"]: e for e in view["entries"]}
    action = by_frag["Alpha_Beta_Issuance"]
    assert action["causal_reasoning"] == (
        "Issuing the documents fulfills the safety obligation.")
    assert action["causal_confidence"] == 0.8
    # The unmatched event stays unannotated.
    assert by_frag["Gamma_Collapse"]["causal_reasoning"] == ""
    assert by_frag["Gamma_Collapse"]["causal_confidence"] is None


def test_timeline_cnl_absent_fragment_degrades_silently(app_context):
    case_id = 9602
    _seed_timeline(case_id)
    db.session.add(_temp_row(
        case_id, "causal_normative_link", "CausalLink_Missing",
        {"action_id": f"case-{case_id}#Missing_Step",
         "reasoning": "Keyed to a happening the timeline excludes."}))
    db.session.commit()

    view = _builder().get_timeline_view(case_id)
    assert all(e["causal_reasoning"] == "" for e in view["entries"])


def test_timeline_cnl_never_joins_by_entity_label(app_context):
    case_id = 9603
    _seed_timeline(case_id)
    # entity_label matches an entry label exactly, but action_id points
    # elsewhere: the entry must NOT pick up the reasoning.
    db.session.add(_temp_row(
        case_id, "causal_normative_link", "Alpha Beta Issuance",
        {"action_id": f"case-{case_id}#Some_Other_Action",
         "reasoning": "Label echo that must not attach."}))
    db.session.commit()

    view = _builder().get_timeline_view(case_id)
    assert all(e["causal_reasoning"] == "" for e in view["entries"])


def _board_conclusion(view):
    (bq,) = view["board_questions"]
    (c,) = bq["linked_conclusions"]
    return c


def test_qc_resolution_joins_committed_uri(app_context):
    case_id = 9604
    _seed_qc(case_id, conclusion_uri=f"case-{case_id}#Conclusion_1")

    c = _board_conclusion(_builder().get_qc_view(case_id))
    assert c["resolution"] is not None
    assert c["resolution"]["weighing_process"] == (
        "The board weighed competence against safety.")
    assert c["resolution"]["determinative_principles"] == ["Competence"]
    assert c["resolution"]["confidence"] == 0.85


def test_qc_resolution_joins_legacy_positional_key(app_context):
    case_id = 9605
    _seed_qc(case_id, conclusion_uri=f"case-{case_id}#C1")

    c = _board_conclusion(_builder().get_qc_view(case_id))
    assert c["resolution"] is not None
    assert c["resolution"]["resolution_narrative"] == "No error occurred."


def test_qc_resolution_without_conclusion_uri_is_skipped(app_context):
    case_id = 9606
    _seed_qc(case_id, conclusion_uri="")

    c = _board_conclusion(_builder().get_qc_view(case_id))
    assert c["resolution"] is None


def test_qc_rp_provision_spelling_aliased_into_lookup(app_context):
    case_id = 9607
    # The per-case provision row stores the canonical 'I.1'; the RP cites
    # the raw spelling 'I.1.'. The aliasing pass must resolve the raw form.
    _seed_qc(case_id, conclusion_uri=f"case-{case_id}#Conclusion_1",
             with_provision_row=True)

    view = _builder().get_qc_view(case_id)
    assert view["provision_text_lookup"]["I.1."] == (
        "Hold paramount the safety of the public.")
