"""Golden behavior-lock test for the commit-service composition (PHASE 2 Step 2.0
of docs-internal/plans/god-file-split.md / .claude/plans/god-file-split.md).

Locks the emitted TTL of `app/services/commit/` -- specifically
`OntServeCommitService`'s individuals-commit path -- against stored snapshots
via rdflib graph ISOMORPHISM, so the upcoming composition refactor (steps
2.1-2.4: per-commit context object, mixins-to-collaborators, shim removal,
test migration) can prove byte-equivalent behavior at each step by re-running
this file unchanged.

Follows the established DB/OntServe-free stubbing pattern in
`tests/extraction/test_match_honoring.py` (`_placement_service`): the service
is built with `object.__new__` (no `__init__`, no real OntServe paths); edge
materialization, canonicalization, the role-axis resolver, the case-title
lookup, and edge provenance recording are stubbed; `_established_core_category`
is overridden with a small deterministic map instead of parsing a real curated
base. `tests/unit/test_individual_serializer_unified.py`'s fixture idiom
(`OntServeCommitService.__new__` + `types.SimpleNamespace` stand-ins for
`TemporaryRDFStorage` rows) is reused for the entity shape.

Coverage (drives the deepest DB-free entry point of each of the five mixins
`OntServeCommitService` composes):

- `_commit_individuals_to_case_ontology` (the live APPEND path -- what the
  pipeline / staged re-extraction / entity-review commit actually call).
  Exercises AgentLayerMixin, EmitterMixin, CategoryResolutionMixin, and the
  naming.py shims over one fixture case with representative entity variety:
  a role individual with archetype-axis data (occupational + relational +
  professional/participant), an obligation, a state, an event with an origin
  category, role-to-role relationship properties (with PROV derivation), a
  temporal action with the full field set, a decision point / question /
  conclusion analysis triad (Toulmin + Q&C edges), a match decision honored
  onto an existing class, and a match decision that keeps a minted type --
  which also produces a synthesis-literal marker (from the obligation's
  `valueBasis` and the state's demoted-text `triggeringEvent`).
- `_write_case_ttl_fresh` -- VersionedCommitMixin's TTL writer. This is the
  ONLY member of that mixin reachable without a live database:
  `commit_case_versioned` and its helpers (`_commit_individuals_versioned`,
  `_commit_classes_versioned`, `_get_next_extraction_version`,
  `_supersede_case_versions`) all open a `psycopg2` connection or touch
  `TemporaryRDFStorage.query` / Flask-SQLAlchemy, so they are NOT exercised
  here and are NOT locked by this test (the documented gap the PHASE 2 plan
  anticipates -- "otherwise note the gap explicitly").
- `_commit_classes_to_intermediate` -- ClassCommitMixin. Not reachable at all
  from the individuals path (classes and individuals are separate storage
  channels), so driven directly with one class-channel fixture row.

Wall-clock timestamps are the only non-deterministic triples either TTL writer
emits: the case-ontology header's `dcterms:created` (stamped fresh on every
new case file) and the relationship-edge PROV `Derivation` node's
`prov:generatedAtTime`. `_strip_wallclock` removes exactly those two triple
families from the parsed graph before comparison -- and was applied the same
way when the golden snapshots were generated -- so every other triple
(including the OTHER, fixture-supplied `generatedAtTime`/`sourceText` values
on the action/event/role individuals) is compared byte-for-byte via
isomorphism.
"""
import types
from pathlib import Path

from rdflib import Graph, Namespace, RDF, OWL
from rdflib.compare import isomorphic, graph_diff

from app.services.commit.ontserve_commit_service import OntServeCommitService

GOLDEN_DIR = Path(__file__).parent.parent / 'fixtures' / 'commit_golden'

CASE_NS = "http://proethica.org/ontology/case/{}#"
INT_NS = "http://proethica.org/ontology/intermediate#"
CORE_NS = "http://proethica.org/ontology/core#"
CASES_NS = "http://proethica.org/ontology/cases#"
PROV_NS = Namespace('http://www.w3.org/ns/prov#')

# Deterministic stand-in for CategoryResolver.resolve(): which of these fixture
# classes an EXISTING curated ontology already parents under a core category.
# 'EngineerRole' is established (Role) so the role individual's match decision
# can be HONORED onto it; every other class here is intentionally absent, so
# each is treated as genuinely new (declared locally with its own
# subClassOf-core, and -- for roles -- routed through the occupational-parent
# attachment / role_category fallback instead of the honoring shortcut).
_ESTABLISHED = {
    'EngineerRole': 'Role',
}


def _chain_resolver(local_name):
    return _ESTABLISHED.get(local_name)


def _stub_service(tmp_path, monkeypatch):
    """OntServeCommitService with every DB / OntServe / filesystem-base
    touchpoint stubbed, mirroring test_match_honoring.py's _placement_service."""
    import app.services.extraction.canonicalization as canon
    import app.services.extraction.edge_materialization as edge_mat
    import app.services.extraction.category_resolver as category_resolver

    svc = object.__new__(OntServeCommitService)
    svc.ontologies_dir = tmp_path
    svc._established_core_category = _chain_resolver
    svc._case_title = lambda case_id: 'AI Diplomate Credential Case'
    svc._record_edge_provenance = lambda *a, **k: None
    # Deterministic empty object-property set except the two the Action
    # fixture below needs redirected to a <local>Text sibling (mirrors
    # test_temporal_field_serialization.py).
    svc._objprop_cache = {'fulfillsObligation', 'causedByAction'}

    def _stub_canonicalize(case_id, ttl_path):
        g = Graph()
        g.parse(str(ttl_path), format='turtle')
        return {'stubbed': True, '_graph': g}

    monkeypatch.setattr(canon, 'canonicalize_ttl', _stub_canonicalize)
    monkeypatch.setattr(edge_mat, 'materialize_edges_on_ttl',
                         lambda case_id, ttl_path: {'stubbed': True})
    monkeypatch.setattr(category_resolver, 'resolve_role_axis', lambda uri: None)
    return svc


def _entity(extraction_type, entity_label, entity_type=None, entity_definition=None):
    """Stand-in for a TemporaryRDFStorage row (the attributes the commit paths
    read), mirroring test_match_honoring.py's _placement_entity."""
    return types.SimpleNamespace(
        extraction_type=extraction_type,
        entity_type=entity_type or extraction_type,
        entity_label=entity_label,
        entity_definition=entity_definition,
        iao_document_uri=None,
        iao_document_label=None,
        cited_by_role=None,
        available_to_role=None,
        extraction_model='claude-test-model',
    )


def _fixture_individuals():
    """Representative entity variety for the individuals-commit path: a role
    with archetype-axis data (occupational + relational + professional/
    participant), an obligation, a state, an event with an origin category,
    role-to-role relationship properties, a temporal action, a decision-point
    / question / conclusion analysis triad, a match decision honored onto an
    existing class, and a match decision that keeps a minted type."""
    individuals = []

    # 1. Role with archetype-axis data: roleKind (professional/participant
    # axis) + roleCategory (relational archetype) + an actor edge (which wins
    # over the roleCategory fallback) + a match decision HONORED onto the
    # established EngineerRole (chain-validated: matches the component's own
    # Role category).
    individuals.append((
        _entity('roles', 'Engineer A Original Design Engineer'),
        {
            'properties': {
                'actor': ['Engineer A'],
                'roleCategory': ['provider_client'],
                'roleKind': ['professional'],
                'relationships': [
                    "{'type': 'has_client', 'target': 'Owner Tower Development Client', "
                    "'quote': 'Engineer A was retained by the Owner for design services.'}"
                ],
                'attributes': ["{'license': 'PE in State X', 'experience': '15 years'}"],
                'generatedAtTime': ['2024-01-01T09:00:00Z'],
                'sourceText': ['Engineer A served as the original design engineer of record.'],
            },
            'definitions': [
                {'text': 'Served as the engineer of record for the original tower designs.',
                 'is_primary': True, 'source_section': 'facts'},
                {'text': 'Occupational archetype head for engineer specializations.',
                 'is_primary': False, 'source_uri': f'{INT_NS}EngineerRole',
                 'source_ontology': 'proethica-intermediate'},
            ],
            'types': [f'{INT_NS}DesignEngineerRole'],
            'match_decision': {
                'matches_existing': True,
                'matched_uri': f'{INT_NS}EngineerRole',
                'matched_label': 'Engineer Role',
                'confidence': 0.87,
                'reasoning': 'Design Engineer is a specialization of Engineer Role.',
            },
        },
    ))

    # 2. Role target of the relationship above: NOT edge-archetyped (it is the
    # object of hasClient, and hasClient is not symmetric), so it falls back
    # to its roleCategory for the relational archetype; a genuinely-new
    # (unmatched) type class exercises the occupational-parent attachment
    # (resolves "client" -> ClientRole from the real archetype ontology, the
    # same dependency tests/unit/test_individual_serializer_unified.py already
    # takes on). No match decision -- locks the unmatched-individual fallback.
    individuals.append((
        _entity('roles', 'Owner Tower Development Client',
                entity_definition='The party that commissioned the tower development project.'),
        {
            'properties': {
                'actor': ['Owner'],
                'roleCategory': ['provider_client'],
            },
            'types': [f'{INT_NS}DeveloperClient'],
        },
    ))

    # 3. Obligation: minted (unmatched) type, a CONTENT property (valueBasis,
    # the synthesis-literal marker) and a typed confidence literal.
    individuals.append((
        _entity('obligations', 'Duty to Present Earned Credentials Truthfully'),
        {
            'properties': {
                'valueBasis': ['Professional integrity requires accurate '
                               'representation of one\'s credentials.'],
                'confidence': ['0.92'],
            },
            'definitions': [
                {'text': 'The duty to identify oneself only by earned credentials.',
                 'is_primary': True, 'source_section': 'discussion'},
            ],
            'types': [f'{INT_NS}DisclosureObligationDraft'],
            'match_decision': {
                'matches_existing': False, 'confidence': 0.0,
                'reasoning': 'no sufficiently similar existing obligation',
            },
        },
    ))

    # 4. State: minted type, a demoted-text CONTENT property
    # (triggeringEvent -- shadows the state-anchored activation edge but
    # keeps its own verbatim literal) plus the entity_definition fallback
    # path in _emit_definitions (no definitions[] array supplied).
    individuals.append((
        _entity('states', 'Design Under Peer Review Prior to Signing',
                entity_definition='A state in which the design remains subject '
                                   'to peer review before signing.'),
        {
            'properties': {
                'triggeringEvent': ['The peer review request was submitted to Engineer B.'],
                'confidence': ['0.8'],
            },
            'types': [f'{INT_NS}PeerReviewPendingStateDraft'],
        },
    ))

    # 5. Event with an origin category (exogenous -> ExogenousEvent),
    # temporal JSON-LD shape (not the unified Pydantic 'properties' shape).
    individuals.append((
        _entity('temporal_dynamics_enhanced', 'State Board Denial of the Permit Application',
                entity_type='events'),
        {
            '@type': 'proeth:Event',
            'proeth:eventType': 'exogenous',
            'proeth:description': 'The state licensing board denied the permit '
                                   'application without explanation.',
            'proeth:createsObligation': ['Duty_to_Present_Earned_Credentials_Truthfully'],
            'generatedAtTime': '2024-02-01T10:15:00',
            'proeth:discoveredInSection': 'facts',
        },
    ))

    # 6. Action with the full temporal field set: scalar/list literals, native
    # bool/int preservation, an object-property literal redirected to its
    # <local>Text sibling (fulfillsObligation), and an IRI object reference
    # that is skipped entirely (causedByAction).
    individuals.append((
        _entity('temporal_dynamics_enhanced', 'Credential Title Selection During Report Signing',
                entity_type='actions'),
        {
            '@type': 'proeth:Action',
            'proeth:description': 'Engineer A signed the report identifying himself as a '
                                   'Diplomate rather than a licensed PE.',
            'proeth:hasAgent': 'Engineer A',
            'proeth:temporalMarker': 'At the time of report signing',
            'proeth:temporalSequence': 6,
            'proeth:foreseenUnintendedEffects': ['Client confusion about credential status',
                                                  'Board scrutiny of the title'],
            'proeth:withinCompetence': False,
            'proeth:fulfillsObligation': 'Duty to Present Earned Credentials Truthfully',
            'proeth:causedByAction': 'http://proethica.org/cases/999#Action_Other',
            'proeth:discoveredInStep': 3,
        },
    ))

    # 7. Decision point: Toulmin slots, board resolution, scores, provisions,
    # options incl. the board-chosen option (emit_decision_point_enrichment,
    # enrichment.py -- migrated verbatim in god-file split Item 1 Step 1.2).
    individuals.append((
        _entity('canonical_decision_point', 'DP1 Diplomate Title Decision'),
        {
            'focus_id': 'DP1',
            'description': 'Whether Engineer A should have disclosed use of the Diplomate title.',
            'decision_question': 'Should Engineer A have used the title "Diplomate" without '
                                  'clarifying it was not a PE license?',
            'options': [
                {'description': 'Use the Diplomate title without further clarification',
                 'label': 'Use as-is'},
                {'description': 'Clarify the Diplomate title is not a PE license',
                 'label': 'Clarify', 'is_board_choice': True},
            ],
            'board_resolution': 'The Board found the unclarified use of Diplomate misleading.',
            'intensity_score': 0.6,
            'qc_alignment_score': 0.75,
            'toulmin': {
                'claim': 'Engineer A should have clarified the title.',
                'data_summary': 'The title Diplomate is a specialty certification, not a PE license.',
                'warrants_summary': 'NSPE Code requires accurate representation of qualifications.',
                'rebuttals_summary': 'Some Diplomates are commonly known by that title alone.',
                'qualifier': 'absent a clear disclaimer',
                'backing_provisions': ['II.1.a', 'III.3.a'],
            },
        },
    ))

    # 8. Ethical question: target of the conclusion's answersQuestion edge
    # below (must exist + be typed for _prune_dangling_qc_edges to keep it).
    individuals.append((
        _entity('ethical_question', 'Diplomate Title Truthfulness Question'),
        {
            'questionText': "Did Engineer A's use of the Diplomate title violate the "
                            "NSPE Code's truthfulness provisions?",
            'questionType': 'board_explicit',
            'questionNumber': 1,
        },
    ))

    # 9. Ethical conclusion: citedProvisions + the Q&C answersQuestion object
    # edge (proethica-cases v3.5.0, edge-primary -- no string/int literal).
    individuals.append((
        _entity('ethical_conclusion', 'Diplomate Title Violation Conclusion'),
        {
            'conclusionText': 'Engineer A violated the Code by using the Diplomate title '
                              'without clarification.',
            'conclusionType': 'violation',
            'boardConclusionType': 'violation',
            'conclusionNumber': 1,
            'extractionReasoning': 'The Board explicitly found a violation of Section III.3.a.',
            'citedProvisions': ['II.1.a', 'III.3.a'],
            'answersQuestions': [1],
        },
    ))

    return individuals


def _fixture_class_row():
    """One class-channel row for _commit_classes_to_intermediate
    (ClassCommitMixin) -- not reachable from the individuals path at all."""
    entity = _entity('obligations', 'Novel Credential Accuracy Obligation')
    rdf_data = {
        'properties': {
            'obligation_type': ['disclosure'],
            'discoveredInCase': [501],
            'valueBasis': ['Truthful representation of credentials preserves public trust.'],
            'confidence': ['0.88'],
        },
        'definitions': [
            {'text': "The duty to represent one's professional credentials accurately "
                     "in all public communications.",
             'is_primary': True, 'source_section': 'discussion'},
        ],
        'match_decision': {
            'matches_existing': False, 'confidence': 0.0,
            'reasoning': 'no sufficiently similar existing class',
        },
    }
    return [(entity, rdf_data)]


def _strip_wallclock(g: Graph) -> None:
    """Remove the two wall-clock-timestamped triple families the commit paths
    emit (case-ontology dcterms:created, relationship-edge PROV Derivation
    generatedAtTime), in place. Everything else -- including the fixture-
    supplied generatedAtTime/sourceText values on individuals -- is
    deterministic and left untouched."""
    from rdflib.namespace import DCTERMS
    for s in list(g.subjects(RDF.type, OWL.Ontology)):
        for o in list(g.objects(s, DCTERMS.created)):
            g.remove((s, DCTERMS.created, o))
    for s in list(g.subjects(RDF.type, PROV_NS.Derivation)):
        for o in list(g.objects(s, PROV_NS.generatedAtTime)):
            g.remove((s, PROV_NS.generatedAtTime, o))


def _load_and_normalize(ttl_path) -> Graph:
    g = Graph()
    g.parse(str(ttl_path), format='turtle')
    _strip_wallclock(g)
    return g


def _assert_matches_golden(g: Graph, golden_path: Path):
    golden = Graph()
    golden.parse(str(golden_path), format='turtle')
    if isomorphic(g, golden):
        return
    in_both, in_g_only, in_golden_only = graph_diff(g, golden)
    lines = [f"Golden mismatch against {golden_path.name}:",
             f"  triples only in the FRESH graph ({len(in_g_only)}):"]
    for t in sorted(in_g_only, key=str):
        lines.append(f"    + {t}")
    lines.append(f"  triples only in the GOLDEN graph ({len(in_golden_only)}):")
    for t in sorted(in_golden_only, key=str):
        lines.append(f"    - {t}")
    raise AssertionError('\n'.join(lines))


# ---------------------------------------------------------------------------
# 1. The live append path: _commit_individuals_to_case_ontology
# ---------------------------------------------------------------------------

def test_individuals_commit_golden_ttl(tmp_path, monkeypatch):
    svc = _stub_service(tmp_path, monkeypatch)
    individuals = _fixture_individuals()

    result = svc._commit_individuals_to_case_ontology(501, individuals)

    assert result.get('error') is None, result
    assert result['count'] == len(individuals)
    assert result['merged'] == 0

    g = Graph()
    g.parse(result['file'], format='turtle')
    case_ns = Namespace(CASE_NS.format(501))
    int_ns = Namespace(INT_NS)
    core_ns = Namespace(CORE_NS)
    cases_ns = Namespace(CASES_NS)

    # Representative spot checks (named, so a partial regression is
    # diagnosable even before the full isomorphism diff below).
    engineer_a = case_ns['Engineer_A_Original_Design_Engineer']
    owner = case_ns['Owner_Tower_Development_Client']
    # Match-decision honoring: typed to the established EngineerRole, not the
    # minted DesignEngineerRole.
    assert (engineer_a, RDF.type, int_ns['EngineerRole']) in g
    assert (engineer_a, RDF.type, int_ns['DesignEngineerRole']) not in g
    # Relationship -> real actor edge + edge-primary relational archetype.
    assert (engineer_a, core_ns['hasClient'], owner) in g
    assert (engineer_a, RDF.type, int_ns['ProviderClientRole']) in g
    # role_category fallback fires on the target (not edge-archetyped).
    assert (owner, RDF.type, int_ns['ProviderClientRole']) in g
    # Occupational-parent attachment on the target's genuinely-new type class
    # (resolved from the real archetype ontology: "client" -> ClientRole).
    assert (int_ns['DeveloperClient'], RDF.type, OWL.Class) in g
    assert (int_ns['DeveloperClient'], None, int_ns['ClientRole']) in g
    # Event origin category.
    event_uri = case_ns['State_Board_Denial_of_the_Permit_Application']
    assert (event_uri, RDF.type, core_ns['Event']) in g
    assert (event_uri, RDF.type, core_ns['ExogenousEvent']) in g
    # Temporal action: object-property literal redirected to its Text sibling;
    # IRI object reference skipped entirely.
    action_uri = case_ns['Credential_Title_Selection_During_Report_Signing']
    assert (action_uri, int_ns['fulfillsObligationText'], None) in g
    assert (action_uri, int_ns['fulfillsObligation'], None) not in g
    assert (action_uri, int_ns['causedByAction'], None) not in g
    # Decision-point enrichment (Toulmin + board-chosen option).
    dp_uri = case_ns['DP1']
    assert (dp_uri, int_ns['boardChosenOption'], None) in g
    assert (dp_uri, int_ns['toulminClaim'], None) in g
    # Q&C edge survives the dangling-endpoint prune (target exists + typed).
    conclusion_uri = case_ns['Conclusion_1']
    question_uri = case_ns['Question_1']
    assert (conclusion_uri, cases_ns['answersQuestion'], question_uri) in g
    # Synthesis-literal marker (from the obligation's valueBasis and the
    # state's demoted triggeringEvent).
    obligation_uri = case_ns['Duty_to_Present_Earned_Credentials_Truthfully']
    state_uri = case_ns['Design_Under_Peer_Review_Prior_to_Signing']
    prov_ns = Namespace('http://proethica.org/provenance#')
    assert (obligation_uri, prov_ns['synthesisLiteral'], None) in g
    assert (state_uri, prov_ns['synthesisLiteral'], None) in g

    normalized = Graph()
    normalized.parse(result['file'], format='turtle')
    _strip_wallclock(normalized)
    _assert_matches_golden(normalized, GOLDEN_DIR / 'individuals_case_501.ttl')


# ---------------------------------------------------------------------------
# 2. VersionedCommitMixin's DB-free TTL writer: _write_case_ttl_fresh
# ---------------------------------------------------------------------------

def test_write_case_ttl_fresh_golden(tmp_path, monkeypatch):
    svc = _stub_service(tmp_path, monkeypatch)
    individuals = _fixture_individuals()

    result = svc._write_case_ttl_fresh(601, individuals)

    assert result.get('error') is None, result
    assert result['count'] == len(individuals)

    g = _load_and_normalize(result['file'])
    _assert_matches_golden(g, GOLDEN_DIR / 'versioned_case_601.ttl')


# ---------------------------------------------------------------------------
# 3. ClassCommitMixin: _commit_classes_to_intermediate (not reachable from
#    the individuals path -- classes and individuals are separate channels)
# ---------------------------------------------------------------------------

def test_class_commit_golden_ttl(tmp_path, monkeypatch):
    svc = _stub_service(tmp_path, monkeypatch)
    classes = _fixture_class_row()

    result = svc._commit_classes_to_intermediate(classes)

    assert result.get('error') is None, result
    assert result['count'] == 1

    g = _load_and_normalize(result['file'])
    _assert_matches_golden(g, GOLDEN_DIR / 'classes_extended.ttl')
