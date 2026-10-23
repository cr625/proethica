"""Case documents as their own class (user decision 2026-10-23).

The resources pass returns the documents of the case events (reports, data, drawings,
photographs) in a case_documents array beside its classes and individuals. They are stored
under their own extraction type, committed typed proeth:CaseDocument (outside the nine
components, disjoint with Resource), and linked to their holders by the case_document_edges
family. DB-free except the storage tests, which reuse the in-memory SQLite fixtures of
test_storage_persistence_case8, and the commit test, which uses the stub commit service.
"""
import types
from pathlib import Path

from rdflib import Graph, Namespace, RDF, RDFS, OWL
from rdflib.namespace import SKOS

from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.services.extraction.edge_spec import EDGE_REGISTRY, PROETH
from app.services.extraction.extraction_graph import case_documents_to_rdf_data, store_extraction_result
from app.services.extraction.field_classification import FieldKind, classify
from app.services.extraction.schemas import (
    CONCEPT_MODELS, CONCEPT_SCHEMAS, CONCEPT_SIDE_OUTPUTS, INTERMEDIATE_NS, CaseDocument,
    ResourceExtractionResult, to_structured_output_schema,
)
from app.services.extraction.unified_dual_extractor import CONCEPT_CONFIG, UnifiedDualExtractor
from tests.mocks.commit_service_stub import make_stub_commit_service
from tests.unit.test_storage_persistence_case8 import (  # noqa: F401  (fixtures)
    fake_embeddings, session, sqlite_app,
)

CORE = 'http://proethica.org/ontology/core#'
CASE7 = Namespace('http://proethica.org/ontology/case/7#')

_DOC = {"label": "Groundwater Monitoring Data", "description": "The wells data Engineer A collected",
        "held_by": ["Engineer A"], "text_references": ["the monitoring data showed contamination"]}


def _resources_extractor():
    ext = object.__new__(UnifiedDualExtractor)
    ext.concept_type = "resources"
    ext.config = CONCEPT_CONFIG["resources"]
    ext.result_schema = CONCEPT_SCHEMAS["resources"]
    ext.class_model, ext.individual_model = CONCEPT_MODELS["resources"]
    ext.side_output_models = CONCEPT_SIDE_OUTPUTS["resources"]
    ext.side_outputs = {}
    return ext


# --- extraction --------------------------------------------------------------

def test_structured_output_schema_carries_case_documents():
    """The main call constrains its reply to this schema, so an array outside it could never
    appear in the response."""
    assert "case_documents" in to_structured_output_schema(ResourceExtractionResult)["properties"]


def test_parse_keeps_case_documents_beside_classes_and_individuals():
    ext = _resources_extractor()
    classes, individuals = ext._parse_and_validate(
        {"new_resource_classes": [], "resource_individuals": [], "case_documents": [_DOC]}, case_id=7)
    assert classes == [] and individuals == []
    [doc] = ext.side_outputs["case_documents"]
    assert doc.identifier == "Groundwater Monitoring Data"
    assert doc.held_by == ["Engineer A"]


def test_fallback_parse_keeps_case_documents_without_resource_normalization():
    """An invalid resource item forces the per-item fallback. The documents survive it, a
    non-object item is skipped, and the resources field normalization (which infers a
    resource_category) is not applied to them."""
    ext = _resources_extractor()
    ext._parse_and_validate({"resource_individuals": [{"identifier": "X", "provision_codes": 5}],
                             "case_documents": [_DOC, "not an object"]}, case_id=7)
    [doc] = ext.side_outputs["case_documents"]
    assert doc.identifier == "Groundwater Monitoring Data"
    assert "resource_category" not in doc.model_dump()


def test_case_documents_to_rdf_data():
    docs = [CaseDocument.model_validate(_DOC), CaseDocument.model_validate({"label": "  "})]
    rdf = case_documents_to_rdf_data(docs, case_id=7, section_type="facts", pass_number=1, step_number=1)
    assert rdf["new_classes"] == []
    [entry] = rdf["new_individuals"]  # the blank identifier is dropped
    assert entry["types"] == [f"{INTERMEDIATE_NS}CaseDocument"]
    assert entry["uri"] == "http://proethica.org/ontology/case/7#Groundwater_Monitoring_Data"
    assert entry["definition"] == "The wells data Engineer A collected"
    assert entry["properties"]["heldBy"] == ["Engineer A"]
    assert "description" not in entry["properties"]  # carried as the definition
    assert entry["properties"]["discoveredInSection"] == ["facts"]


def test_holders_and_document_use_are_relations():
    """A relation becomes an edge through an edge family; the commit writes no literal for it."""
    assert classify("heldBy") is FieldKind.RELATION
    assert classify("usesDocument") is FieldKind.RELATION


def test_case_document_edge_family():
    spec = next(s for s in EDGE_REGISTRY if s.name == "case_document_edges")
    assert spec.extraction_type == "case_documents"
    assert spec.subject_resolution == "type" and spec.subject_type == PROETH.CaseDocument
    [pred] = spec.predicates
    assert (pred.prop, pred.namespace, pred.range_category) == ("heldBy", PROETH, "Agent")
    prompt = pred.prompt_builder_factory(pred, spec)([{
        "id": 1, "document_label": "Groundwater Monitoring Data", "desc": "Engineer A",
        "shortlist": [("iri", "Engineer A", 0.9)]}])
    assert "CASE DOCUMENT" in prompt and "1) Engineer A" in prompt


def test_resources_template_routes_case_documents():
    body = (Path(__file__).resolve().parents[2] / "app" / "utils" / "prompts" / "resources.md").read_text()
    assert "THREE arrays" in body and "CASE DOCUMENT SCHEMA" in body
    assert "never as a resource individual" in body


# --- storage -----------------------------------------------------------------

def _extractor(docs):
    return types.SimpleNamespace(
        model_name="test-model", last_prompt="prompt", last_raw_response="{}", injection_mode="full",
        tool_call_log=None, ontology_definitions=None,
        side_output_models=CONCEPT_SIDE_OUTPUTS["resources"], side_outputs={"case_documents": docs})


def _store(session_id, docs):
    store_extraction_result(
        case_id=7, concept_type="resources", step_number=1, section_type="facts",
        session_id=session_id, extractor=_extractor(docs), classes=[], individuals=[],
        pass_number=1, extraction_pass="contextual_framework",
    )


def test_case_documents_stored_under_their_own_type(session, fake_embeddings):
    _store("facts-1", [CaseDocument.model_validate(_DOC)])
    [row] = TemporaryRDFStorage.query.filter_by(extraction_type="case_documents").all()
    assert row.storage_type == "individual" and row.extraction_session_id == "facts-1"
    assert row.entity_label == "Groundwater Monitoring Data"
    assert row.rdf_json_ld["types"] == [f"{INTERMEDIATE_NS}CaseDocument"]
    assert TemporaryRDFStorage.query.filter_by(extraction_type="resources").count() == 0


def test_rerun_clears_the_case_documents_of_the_earlier_run(session, fake_embeddings):
    """The documents are saved with the resources prompt, so the rows an earlier run of the
    same section left are found through the resources sessions and cleared, even when the
    rerun returns none."""
    _store("facts-1", [CaseDocument.model_validate(_DOC)])
    _store("facts-2", [])
    assert TemporaryRDFStorage.query.filter_by(extraction_type="case_documents").count() == 0


# --- commit ------------------------------------------------------------------

def test_commit_types_a_case_document_without_a_core_category(tmp_path, monkeypatch):
    svc = make_stub_commit_service(tmp_path, monkeypatch, chain_resolver=lambda local: None,
                                   header_fields={'title': 'Mock Case', 'case_number': None, 'decade': None})
    rdf = case_documents_to_rdf_data([CaseDocument.model_validate(_DOC)], case_id=7,
                                     section_type="facts", pass_number=1, step_number=1)["new_individuals"][0]
    entity = types.SimpleNamespace(
        extraction_type='case_documents', entity_type='Case_documents', entity_label=rdf['label'],
        entity_definition=rdf['definition'], iao_document_uri=None, iao_document_label=None,
        cited_by_role=None, available_to_role=None, extraction_model=None)
    result = svc._commit_individuals_to_case_ontology(7, [(entity, rdf)])
    assert result.get('error') is None, result
    g = Graph()
    g.parse(result['file'], format='turtle')
    doc = CASE7['Groundwater_Monitoring_Data']
    assert (doc, RDF.type, PROETH.CaseDocument) in g
    assert not [t for t in g.objects(doc, RDF.type) if str(t).startswith(CORE)]
    assert (PROETH.CaseDocument, RDF.type, OWL.Class) not in g  # the shared class is not redeclared
    assert str(g.value(doc, RDFS.label)) == "Groundwater Monitoring Data"
    assert str(g.value(doc, SKOS.definition)) == "The wells data Engineer A collected"
    assert g.value(doc, PROETH.heldBy) is None  # an edge of the family, never a literal
