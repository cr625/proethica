"""
Provenance mini-batch regression tests (pre-rebuild audit, 2026-07-11).

Covers the run-record capture gaps: the conformance provenance record used
keys the gate never returns (remaining/reason vs residual/error, so residual
counts recorded as null), and run_commit_task rebuilt its persisted results
dict from four keys, dropping the commit-time guard statistics
(role_axis_vetoes, qc_edges_dropped, canonicalization counters, conformance)
that existed only in the log stream.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.commit.ontserve_commit_service import OntServeCommitService

_MODULE = 'app.services.commit.ontserve_commit_service'
_TASKS = 'app.tasks.pipeline_tasks'


def _service():
    svc = OntServeCommitService.__new__(OntServeCommitService)
    svc.ontologies_dir = Path('/fake/OntServe/ontologies')
    svc._record_ontology_commit = MagicMock()
    return svc


def test_conformance_provenance_records_gate_keys():
    """The record must use gate_case_ttl's real contract (residual/error),
    not the never-returned remaining/reason."""
    svc = OntServeCommitService.__new__(OntServeCommitService)
    with patch('app.services.provenance_service.get_provenance_service') as gps:
        prov = MagicMock()
        gps.return_value = prov
        svc._record_conformance_provenance(
            9, {'status': 'ok', 'conforms': False,
                'repairs_applied': 2, 'residual': 3})
    check = prov.track_pass.call_args_list[0].kwargs['result']
    assert check == {'conforms': False, 'residual': 3, 'error': None, 'status': 'ok'}
    assert 'remaining' not in check and 'reason' not in check
    repair = prov.track_pass.call_args_list[1].kwargs['result']
    assert repair == {'repairs_applied': 2}


def test_conformance_provenance_records_gate_error():
    svc = OntServeCommitService.__new__(OntServeCommitService)
    with patch('app.services.provenance_service.get_provenance_service') as gps:
        prov = MagicMock()
        gps.return_value = prov
        svc._record_conformance_provenance(
            9, {'status': 'gate_error', 'error': 'MCP unreachable'})
    check = prov.track_pass.call_args_list[0].kwargs['result']
    assert check['status'] == 'gate_error'
    assert check['error'] == 'MCP unreachable'
    assert len(prov.track_pass.call_args_list) == 1  # no repair pass


class _Row:
    def __init__(self, row_id):
        self.id = row_id
        self.storage_type = 'individual'
        self.rdf_json_ld = {}
        self.is_published = False
        self.committed_at = None
        self.content_hash = None
        self.entity_uri = f"http://proethica.org/ontology/case/test#e{row_id}"
        self.entity_label = f"Entity {row_id}"
        self.entity_definition = "test definition"
        self.ontology_target = 'proethica-case-9'


def test_commit_result_carries_canonicalization_stats():
    """commit_selected_entities surfaces the full canonicalization counters,
    not only the veto counts."""
    rows = [_Row(4)]
    svc = _service()
    svc._record_conformance_provenance = MagicMock()
    canon = {'roles_decomposed': 2, 'states_materialized': 1,
             'obligations_materialized': 0, 'compound_classes_removed': 2}
    svc._commit_individuals_to_case_ontology = MagicMock(
        return_value={'count': 1, 'merged': 0, 'file': 'x.ttl',
                      'role_axis_vetoes': 1, 'qc_edges_dropped': 0,
                      'role_axis_vetoes_post_canonicalization': 0,
                      'canonicalization': canon})
    svc._sync_ontology_to_db = MagicMock(return_value={'success': True})

    storage = MagicMock()
    storage.query.filter.return_value.all.return_value = rows
    storage.compute_content_hash.return_value = 'hash'

    with patch(f'{_MODULE}.TemporaryRDFStorage', storage), \
         patch('app.services.extraction.conformance_gate.gate_case_ttl',
               return_value={'status': 'ok', 'conforms': True,
                             'repairs_applied': 0, 'residual': 0}), \
         patch('app.services.commit.precedent_features.update_entity_classes_from_storage',
               return_value={}), \
         patch('app.db'):
        result = svc.commit_selected_entities(9, [4])

    assert result['success'] is True
    assert result['canonicalization'] == canon
    assert result['role_axis_vetoes'] == 1
    assert result['conformance']['residual'] == 0


def test_rpo_prov_iris_content_addressed_and_collision_free():
    """Two runs whose edge ORDER differs must produce the same Derivation
    nodes (the positional scheme grafted two unrelated edges onto one IRI --
    the case-59 merged node)."""
    from rdflib import Graph, Namespace, RDF
    from app.services.extraction.rpo_edges import add_edges_to_graph
    PROV = Namespace("http://www.w3.org/ns/prov#")

    edges = [
        {"predicate": "derivedFromPrinciple",
         "subject_iri": "http://proethica.org/ontology/case/59#Duty_A",
         "object_iri": "http://proethica.org/ontology/case/59#Principle_A",
         "source_text": "quote A", "confidence": 0.9},
        {"predicate": "derivedFromPrinciple",
         "subject_iri": "http://proethica.org/ontology/case/59#Duty_B",
         "object_iri": "http://proethica.org/ontology/case/59#Principle_B",
         "source_text": "quote B", "confidence": 0.6},
    ]
    g1, g2 = Graph(), Graph()
    add_edges_to_graph(g1, edges, 59)
    add_edges_to_graph(g2, list(reversed(edges)), 59)

    nodes1 = {s for s in g1.subjects(RDF.type, PROV.Derivation)}
    nodes2 = {s for s in g2.subjects(RDF.type, PROV.Derivation)}
    assert nodes1 == nodes2 and len(nodes1) == 2
    for n in nodes1:
        frag = str(n).rsplit('#', 1)[-1]
        assert frag.startswith('rpo_edge_provenance_Duty_')
        # each node carries exactly one edge's pair, its quote, its
        # confidence (comment), and a generation timestamp
        assert len(list(g1.objects(n, PROV.wasDerivedFrom))) == 2
        assert len(list(g1.objects(n, PROV.value))) == 1
        assert len(list(g1.objects(n, PROV.generatedAtTime))) == 1
    comments = {str(c) for n in nodes1
                for c in g1.objects(n, __import__('rdflib').RDFS.comment)}
    assert any('confidence 0.90' in c for c in comments)
    assert any('confidence 0.60' in c for c in comments)


def test_temporal_converter_stamps_and_serializer_emits_generated_at():
    from rdflib import Graph, Namespace, URIRef, XSD
    from app.services.temporal_dynamics.utils.rdf_converter import convert_action_to_rdf
    from app.services.commit.ontserve_commit_service import OntServeCommitService
    PROV = Namespace("http://www.w3.org/ns/prov#")

    rdf_data = convert_action_to_rdf({'label': 'Notify Client'}, 9)
    assert rdf_data.get('generatedAtTime'), "converter must stamp the extraction time"

    svc = OntServeCommitService.__new__(OntServeCommitService)
    svc._objprop_cache = set()
    g = Graph()
    uri = URIRef("http://proethica.org/ontology/case/9#Notify_Client")
    svc._add_temporal_fields(g, uri, rdf_data)
    stamps = list(g.objects(uri, PROV.generatedAtTime))
    assert len(stamps) == 1
    assert stamps[0].datatype == XSD.dateTime


def test_join_llm_traces_joins_and_handles_empty():
    from app.services.narrative.trace_capture import join_llm_traces
    traces = [
        {'stage': 'CHARACTER_ENHANCEMENT', 'prompt': 'p1', 'response': 'r1'},
        {'stage': 'INSIGHT_GENERATION', 'prompt': 'p2', 'response': 'r2'},
        'not-a-dict',
        {'stage': 'NO_PROMPT'},
    ]
    p, r = join_llm_traces(traces)
    assert '=== CHARACTER_ENHANCEMENT ===\np1' in p
    assert '=== INSIGHT_GENERATION ===\np2' in p
    assert 'r1' in r and 'r2' in r
    assert join_llm_traces(None) == ("", "")
    assert join_llm_traces([]) == ("", "")


def _emit_conclusion(rdf_data):
    from rdflib import Graph, Namespace, URIRef
    g = Graph()
    uri = URIRef("http://proethica.org/ontology/case/9#Conclusion_1")
    svc = OntServeCommitService.__new__(OntServeCommitService)
    entity = type('E', (), {'extraction_type': 'ethical_conclusion'})()
    svc._add_individual_properties(
        g, uri, entity, rdf_data, Namespace("http://proethica.org/ontology/case/9#"))
    return g, uri


def test_conclusion_emitter_adds_board_conclusion_type():
    """The ethical_conclusion serializer branch emits boardConclusionType;
    the detector non-answer 'unknown' stays absent."""
    from rdflib import Namespace
    PROETH = Namespace("http://proethica.org/ontology/intermediate#")

    g, uri = _emit_conclusion(
        {'conclusionText': 'The engineer violated the Code.',
         'conclusionType': 'board_explicit', 'boardConclusionType': 'violation',
         'conclusionNumber': 1})
    assert [str(o) for o in g.objects(uri, PROETH.boardConclusionType)] == ['violation']

    g2, uri2 = _emit_conclusion(
        {'conclusionText': 'Some conclusion.', 'conclusionType': 'board_explicit',
         'boardConclusionType': 'unknown', 'conclusionNumber': 2})
    assert list(g2.objects(uri2, PROETH.boardConclusionType)) == []


def test_run_commit_task_persists_guard_stats():
    """The stats present on the commit result must reach mark_step_complete
    (the only durable record of the commit)."""
    from app.tasks.pipeline_tasks import run_commit_task

    run = MagicMock()
    run.case_id = 9
    run.config = {'mode': 'single'}

    entity = _Row(1)
    entity.review_notes = 'verification-gate: vetted run 77'
    entity.is_selected = True

    commit_result = {
        'success': True, 'classes_committed': 0, 'individuals_committed': 1,
        'ontserve_synced': True, 'errors': [],
        'role_axis_vetoes': 2, 'qc_edges_dropped': 1,
        'canonicalization': {'roles_decomposed': 3},
        'conformance': {'status': 'ok', 'conforms': True,
                        'repairs_applied': 0, 'residual': 0},
    }

    gate = MagicMock()
    gate.dropped_ids = set()
    gate.dropped = []
    gate.flagged = []
    gate.corrected_quotes = {}
    gate.repaired_quoteless = set()
    gate.report = {'dropped_detail': []}

    svc = MagicMock()
    svc.commit_selected_entities.return_value = commit_result

    storage = MagicMock()
    storage.query.filter_by.return_value.filter.return_value.all.return_value = [entity]

    with patch(f'{_TASKS}.PipelineRun') as pr, \
         patch(f'{_TASKS}.db'), \
         patch(f'{_TASKS}.get_case_sections',
               return_value={'facts': 'f', 'discussion': 'd'}), \
         patch(f'{_TASKS}._record_pass'), \
         patch('app.models.temporary_rdf_storage.TemporaryRDFStorage', storage), \
         patch('app.services.extraction.verification_gate.verify_case_entities',
               return_value=gate), \
         patch(f'{_MODULE}.OntServeCommitService', return_value=svc):
        pr.query.get.return_value = run
        out = run_commit_task.run(77)

    assert out['success'] is True
    results = run.mark_step_complete.call_args.args[1]
    assert results['role_axis_vetoes'] == 2
    assert results['qc_edges_dropped'] == 1
    assert results['canonicalization'] == {'roles_decomposed': 3}
    assert results['conformance']['residual'] == 0
