"""Unit tests for the unified OntServeCommitService._add_individual_properties.

This is the SINGLE per-individual serializer shared by the live append path
(`_commit_individuals_to_case_ontology`, used by the pipeline / staged
re-extraction / entity-review commit) and the versioned path
(`_write_case_ttl_fresh`). The two had drifted: the live path emitted role
`relationships`/`attributes` as opaque stringified-dict literals, while the
versioned path had the real serialization but stubbed Step-4 synthesis handlers.
Unification put one serializer in place. These tests lock two contracts:

1. Role-individual `attributes` become one queryable triple per key and
   `relationships` become real proeth-core actor edges -- against the ACTUAL
   stored shape (a stringified dict inside a one-element list, the shape
   `_extract_properties` produces).
2. The rich Step-4 synthesis handlers (argument_validation, decision-point
   options, conclusion citedProvisions) still emit their triples (regression
   guard, since these previously lived only in the live path's inline chain).
"""
import types

from rdflib import Graph, Namespace, RDF, Literal

from app.services.ontserve_commit_service import OntServeCommitService

CASE = Namespace('http://proethica.org/ontology/case/15#')
CORE = Namespace('http://proethica.org/ontology/core#')
PROETHICA = Namespace('http://proethica.org/ontology/intermediate#')
CASES = Namespace('http://proethica.org/ontology/cases#')
PROV = Namespace('http://www.w3.org/ns/prov#')


def _svc(rel_index=None):
    svc = OntServeCommitService.__new__(OntServeCommitService)
    svc._rel_label_index = rel_index or {}
    return svc


def _entity(extraction_type):
    return types.SimpleNamespace(extraction_type=extraction_type)


def _role_entity(label):
    return types.SimpleNamespace(extraction_type='roles', entity_label=label)


def test_attributes_become_per_key_triples():
    """Stored shape is a one-element list holding a stringified dict."""
    svc = _svc()
    g = Graph()
    uri = CASE['EngineerA']
    rdf_data = {'properties': {
        'attributes': ["{'license': 'PE in State X', 'experience': '20 years'}"],
    }}
    svc._add_individual_properties(g, uri, _entity('roles'), rdf_data, CASE)
    assert (uri, PROETHICA['license'], Literal('PE in State X')) in g
    assert (uri, PROETHICA['experience'], Literal('20 years')) in g
    # The opaque dead-text literal must NOT survive.
    assert (uri, PROETHICA['attributes'],
            Literal("{'license': 'PE in State X', 'experience': '20 years'}")) not in g


def test_relationships_become_resolved_actor_edges():
    target = CASE['OwnerTowerDevelopmentClient']
    svc = _svc({'owner tower development client': target})
    g = Graph()
    uri = CASE['EngineerAOriginalDesignEngineer']
    rdf_data = {'properties': {
        'relationships': ["{'type': 'client', 'target': 'Owner Tower Development Client'}"],
    }}
    svc._add_individual_properties(g, uri, _entity('roles'), rdf_data, CASE)
    assert (uri, CORE['hasClient'], target) in g
    # No opaque literal fallback for a resolved relationship.
    assert (uri, PROETHICA['relationships'],
            Literal("{'type': 'client', 'target': 'Owner Tower Development Client'}")) not in g


def test_relationship_unresolved_target_skipped_not_deadtext():
    svc = _svc({})  # empty index -> nothing resolves
    g = Graph()
    uri = CASE['EngineerA']
    rdf_data = {'properties': {
        'relationships': ["{'type': 'peer', 'target': 'Nonexistent Person'}"],
    }}
    svc._add_individual_properties(g, uri, _entity('roles'), rdf_data, CASE)
    # An unresolved target is logged and skipped, never turned back into dead text.
    assert len(list(g.triples((uri, None, None)))) == 0


def test_peer_relationship_maps_to_symmetric_property():
    target = CASE['EngineerBPeerReviewer']
    svc = _svc({'engineer b peer reviewer': target})
    g = Graph()
    uri = CASE['EngineerAOriginalDesignEngineer']
    rdf_data = {'properties': {
        'relationships': ["{'type': 'peer', 'target': 'Engineer B Peer Reviewer'}"],
    }}
    svc._add_individual_properties(g, uri, _entity('roles'), rdf_data, CASE)
    assert (uri, CORE['professionalPeerOf'], target) in g


def test_argument_validation_rich_handler_emits():
    """Regression guard: the rich synthesis handler ported into the unified
    serializer still emits its triples (this used to live only in the live path).
    """
    svc = _svc()
    g = Graph()
    uri = CASE['Validation_DP1']
    rdf_data = {
        'argument_id': 'Arg_DP1_optA',
        'is_valid': True,
        'validation_score': 0.85,
        'validation_notes': ['note one', 'note two'],
        'entity_validation': {'is_valid': False, 'missing_entities': ['EngineerB']},
        'virtue_validation': {'is_valid': True},
    }
    svc._add_individual_properties(g, uri, _entity('argument_validation'), rdf_data, CASE)
    assert (uri, RDF.type, CASES['ArgumentValidation']) in g
    assert (uri, PROETHICA['validatesArgument'], CASE['Arg_DP1_optA']) in g
    assert (uri, PROETHICA['argumentId'], Literal('Arg_DP1_optA')) in g
    assert (uri, PROETHICA['validationNote1'], Literal('note one')) in g
    assert (uri, PROETHICA['missingEntity1'], Literal('EngineerB')) in g


def test_decision_point_options_and_conclusion_provisions():
    svc = _svc()
    g = Graph()
    dp = CASE['DP1']
    svc._add_individual_properties(g, dp, _entity('canonical_decision_point'), {
        'focus_id': 'DP1',
        'description': 'Whether to sign',
        'decision_question': 'Sign or not?',
        'options': [{'description': 'Sign'}, {'description': 'Refuse'}],
    }, CASE)
    assert (dp, PROETHICA['option1'], Literal('Sign')) in g
    assert (dp, PROETHICA['option2'], Literal('Refuse')) in g
    assert (dp, PROETHICA['decisionQuestion'], Literal('Sign or not?')) in g

    g2 = Graph()
    c = CASE['Conclusion_1']
    svc._add_individual_properties(g2, c, _entity('ethical_conclusion'), {
        'conclusionText': 'It was unethical',
        'conclusionNumber': 1,
        'citedProvisions': ['II.1.a', 'III.2.b'],
    }, CASE)
    assert (c, PROETHICA['citedProvision1'], Literal('II.1.a')) in g2
    assert (c, PROETHICA['citedProvision2'], Literal('III.2.b')) in g2


# --- Agent layer (Option C: cross-section actor identity) --------------------

def test_agent_layer_unifies_cross_section_actor():
    """Two role facets (facts + discussion) declaring the same `actor` are borne
    by ONE proeth-core:Agent via hasRole -- the actor is not fragmented."""
    svc = _svc()
    individuals = [
        (_role_entity('Engineer A Original Design Engineer'),
         {'properties': {'actor': ['Engineer A']}}),
        (_role_entity('Cooperation-Refusing Design Engineer'),
         {'properties': {'actor': ['Engineer A']}}),
    ]
    svc._build_agent_indices(individuals, CASE)
    g = Graph()
    svc._emit_agent_layer(g)
    agent = CASE['Agent_Engineer_A']
    assert (agent, RDF.type, CORE['Agent']) in g
    f1 = CASE[svc._safe_label('Engineer A Original Design Engineer')]
    f2 = CASE[svc._safe_label('Cooperation-Refusing Design Engineer')]
    assert (agent, CORE['hasRole'], f1) in g
    assert (agent, CORE['hasRole'], f2) in g
    assert len(list(g.subjects(RDF.type, CORE['Agent']))) == 1


def test_distinct_actors_get_distinct_agents():
    svc = _svc()
    individuals = [
        (_role_entity('Engineer A Original Design Engineer'), {'properties': {'actor': ['Engineer A']}}),
        (_role_entity('Engineer B Peer Reviewer'), {'properties': {'actor': ['Engineer B']}}),
    ]
    svc._build_agent_indices(individuals, CASE)
    g = Graph()
    svc._emit_agent_layer(g)
    assert len(list(g.subjects(RDF.type, CORE['Agent']))) == 2


def test_actor_fallback_to_label_when_absent():
    """No declared actor -> the facet still gets its own Agent (no merge)."""
    svc = _svc()
    individuals = [(_role_entity('Some Lone Engineer'), {'properties': {}})]
    svc._build_agent_indices(individuals, CASE)
    g = Graph()
    svc._emit_agent_layer(g)
    agent = CASE['Agent_' + svc._safe_label('Some Lone Engineer')]
    assert (agent, RDF.type, CORE['Agent']) in g


def test_relationship_attaches_at_agent_level():
    svc = _svc()
    subj_facet = _role_entity('Engineer A Original Design Engineer')
    tgt_facet = _role_entity('Owner Tower Development Client')
    subj_rdf = {'properties': {
        'actor': ['Engineer A'],
        'relationships': ["{'type': 'client', 'target': 'Owner Tower Development Client'}"],
    }}
    individuals = [(subj_facet, subj_rdf), (tgt_facet, {'properties': {'actor': ['Owner']}})]
    subj_uri = CASE[svc._safe_label('Engineer A Original Design Engineer')]
    tgt_uri = CASE[svc._safe_label('Owner Tower Development Client')]
    svc._rel_label_index = {
        svc._norm_label('Engineer A Original Design Engineer'): subj_uri,
        svc._norm_label('Owner Tower Development Client'): tgt_uri,
    }
    svc._build_agent_indices(individuals, CASE)
    g = Graph()
    svc._add_individual_properties(g, subj_uri, subj_facet, subj_rdf, CASE)
    agent_a = CASE['Agent_Engineer_A']
    agent_owner = CASE['Agent_Owner']
    # Edge is between the AGENTS, not the role facets.
    assert (agent_a, CORE['hasClient'], agent_owner) in g
    assert (subj_uri, CORE['hasClient'], tgt_uri) not in g


def test_relationship_edge_carries_prov_derivation():
    """The per-relationship quote is emitted as a prov:Derivation/prov:value on
    the edge, mirroring the defeasibility-edge provenance pattern."""
    svc = _svc()
    subj_facet = _role_entity('Engineer A Original Design Engineer')
    tgt_facet = _role_entity('Owner Tower Development Client')
    subj_rdf = {'properties': {
        'actor': ['Engineer A'],
        'relationships': ["{'type': 'client', 'target': 'Owner Tower Development Client', "
                          "'quote': 'Engineer A was retained by the Owner'}"],
    }}
    individuals = [(subj_facet, subj_rdf), (tgt_facet, {'properties': {'actor': ['Owner']}})]
    subj_uri = CASE[svc._safe_label('Engineer A Original Design Engineer')]
    tgt_uri = CASE[svc._safe_label('Owner Tower Development Client')]
    svc._rel_label_index = {
        svc._norm_label('Engineer A Original Design Engineer'): subj_uri,
        svc._norm_label('Owner Tower Development Client'): tgt_uri,
    }
    svc._build_agent_indices(individuals, CASE)
    g = Graph()
    svc._add_individual_properties(g, subj_uri, subj_facet, subj_rdf, CASE)
    agent_a = CASE['Agent_Engineer_A']
    agent_owner = CASE['Agent_Owner']
    assert (agent_a, CORE['hasClient'], agent_owner) in g
    derivs = list(g.subjects(RDF.type, PROV.Derivation))
    assert len(derivs) == 1, derivs
    d = derivs[0]
    assert (d, PROV.wasDerivedFrom, agent_a) in g
    assert (d, PROV.wasDerivedFrom, agent_owner) in g
    assert (d, PROV.value, Literal('Engineer A was retained by the Owner')) in g


def test_role_individual_occupational_archetype_divergent_type():
    """Layer-1 convergence: the class a role individual is typed under gets its
    OCCUPATIONAL archetype even when its name diverges from the role_class entity.
    Only the occupational axis is attached (one side of the ProfessionalRole/
    ParticipantRole disjointness), so no unsatisfiable pairing is created."""
    svc = _svc()
    ENGINEER = str(PROETHICA['EngineerRole'])
    CLIENT = str(PROETHICA['ClientRole'])
    # Divergent compound engineering type-class -> EngineerRole.
    assert svc._role_individual_occupational_archetype(
        'OriginalDesignEngineerSubjecttoPeerReview') == [ENGINEER]
    # De-camelCased "Developer Client" -> ClientRole.
    assert svc._role_individual_occupational_archetype('DeveloperClient') == [CLIENT]
    # Unmapped occupational label -> empty (the tail the RoleArchetypeShape flags,
    # never a spurious parent).
    assert svc._role_individual_occupational_archetype('Confidentiality-BoundPeerReviewer') == []


def test_rel_property_mapping_orientations():
    """Direct mapping coverage: (proeth-core property, swap) per relationship type.
    Locks the orientation contract the directional vocabulary depends on."""
    svc = _svc()
    expected = {
        'has_client': ('hasClient', False),
        'has_provider': ('hasClient', True),
        'client': ('hasClient', False),
        'client_of': ('hasClient', True),
        'retained_by': ('hasClient', False),
        'employed_by': ('employedBy', False),
        'employs': ('employedBy', True),
        'reviewer_of': ('reviewsWorkOf', False),
        'subject_of_review': ('workReviewedBy', False),
        'reviewed_by': ('workReviewedBy', False),
        'peer': ('professionalPeerOf', False),
        'mentor': ('relatedTo', False),  # unmapped -> controlled fallback
    }
    for rtype, want in expected.items():
        assert svc._rel_property_for(rtype) == want, (rtype, svc._rel_property_for(rtype))


def _rel_fixture(svc, subj_label, subj_actor, rtype, target_label, target_actor, extra_index=None):
    """Build a two-individual fixture and return (g, subj_uri) after serializing
    the subject's single relationship of type `rtype` toward `target_label`."""
    subj_facet = _role_entity(subj_label)
    tgt_facet = _role_entity(target_label)
    subj_rdf = {'properties': {
        'actor': [subj_actor],
        'relationships': ["{'type': '%s', 'target': '%s'}" % (rtype, target_label)],
    }}
    individuals = [(subj_facet, subj_rdf), (tgt_facet, {'properties': {'actor': [target_actor]}})]
    subj_uri = CASE[svc._safe_label(subj_label)]
    tgt_uri = CASE[svc._safe_label(target_label)]
    svc._rel_label_index = dict(extra_index or {})
    svc._rel_label_index[svc._norm_label(subj_label)] = subj_uri
    svc._rel_label_index[svc._norm_label(target_label)] = tgt_uri
    svc._build_agent_indices(individuals, CASE)
    g = Graph()
    svc._add_individual_properties(g, subj_uri, subj_facet, subj_rdf, CASE)
    return g, subj_uri


def test_subject_of_review_maps_to_work_reviewed_by():
    """Passive review direction must orient to workReviewedBy, not reviewsWorkOf."""
    svc = _svc()
    g, _ = _rel_fixture(svc, 'Engineer A Original Design Engineer', 'Engineer A',
                        'subject_of_review', 'Engineer B Peer Reviewer', 'Engineer B')
    agent_a = CASE['Agent_Engineer_A']
    agent_b = CASE['Agent_Engineer_B']
    assert (agent_a, CORE['workReviewedBy'], agent_b) in g
    assert (agent_a, CORE['reviewsWorkOf'], agent_b) not in g


def test_has_provider_orients_hasclient_from_client_side():
    """A client naming its provider (has_provider) yields hasClient(provider, client)."""
    svc = _svc()
    g, _ = _rel_fixture(svc, 'Owner Peer Review Instructing Client', 'Owner',
                        'has_provider', 'Engineer B Peer Reviewer', 'Engineer B')
    agent_owner = CASE['Agent_Owner']
    agent_b = CASE['Agent_Engineer_B']
    assert (agent_b, CORE['hasClient'], agent_owner) in g
    assert (agent_owner, CORE['hasClient'], agent_b) not in g


def test_target_resolver_prefers_role_facet_over_nonrole():
    """A bare actor name that substring-matches a non-role node (e.g. an action
    "Owner Covert Review Instruction") still resolves to the role facet."""
    svc = _svc()
    action_uri = CASE[svc._safe_label('Owner Covert Review Instruction')]
    # Build the fixture with the bare "Owner" target to exercise substring
    # resolution, seeding the non-role action node FIRST so it would win under a
    # naive first-match resolver.
    subj_facet = _role_entity('Engineer A Original Design Engineer')
    owner_facet = _role_entity('Owner Peer Review Instructing Client')
    subj_rdf = {'properties': {
        'actor': ['Engineer A'],
        'relationships': ["{'type': 'has_client', 'target': 'Owner'}"],
    }}
    individuals = [(subj_facet, subj_rdf), (owner_facet, {'properties': {'actor': ['Owner']}})]
    subj_uri = CASE[svc._safe_label('Engineer A Original Design Engineer')]
    owner_uri = CASE[svc._safe_label('Owner Peer Review Instructing Client')]
    svc._rel_label_index = {
        svc._norm_label('Owner Covert Review Instruction'): action_uri,
        svc._norm_label('Engineer A Original Design Engineer'): subj_uri,
        svc._norm_label('Owner Peer Review Instructing Client'): owner_uri,
    }
    svc._build_agent_indices(individuals, CASE)
    g2 = Graph()
    svc._add_individual_properties(g2, subj_uri, subj_facet, subj_rdf, CASE)
    agent_a = CASE['Agent_Engineer_A']
    agent_owner = CASE['Agent_Owner']
    assert (agent_a, CORE['hasClient'], agent_owner) in g2
    assert (agent_a, CORE['hasClient'], action_uri) not in g2
