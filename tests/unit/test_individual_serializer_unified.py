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

from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal, URIRef
from rdflib.namespace import SKOS, XSD

from app.services.commit.ontserve_commit_service import OntServeCommitService

PROV_NS = Namespace('http://proethica.org/provenance#')

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
    # Recurring professional keys map to the controlled vocabulary (hasLicense,
    # experienceLevel) so cross-case queries work and the datatype-predicate space
    # stays closed.
    assert (uri, PROETHICA['hasLicense'], Literal('PE in State X')) in g
    assert (uri, PROETHICA['experienceLevel'], Literal('20 years')) in g
    # The opaque dead-text literal must NOT survive.
    assert (uri, PROETHICA['attributes'],
            Literal("{'license': 'PE in State X', 'experience': '20 years'}")) not in g


def test_relationships_become_resolved_actor_edges():
    svc = _svc()
    g, subj_uri, tgt_uri = _rel_fixture(svc, 'Engineer A Original Design Engineer', 'Engineer A',
                               'client', 'Owner Tower Development Client', 'Owner')
    # Edge is ROLE-to-ROLE (between the role facets) so a defined relational archetype
    # -- ProviderClientRole equivalentClass Role and (hasClient some Role) -- classifies it.
    assert (subj_uri, CORE['hasClient'], tgt_uri) in g
    # No opaque literal fallback for a resolved relationship.
    assert (subj_uri, PROETHICA['relationships'],
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
    svc = _svc()
    g, subj_uri, tgt_uri = _rel_fixture(svc, 'Engineer A Original Design Engineer', 'Engineer A',
                        'peer', 'Engineer B Peer Reviewer', 'Engineer B')
    assert (subj_uri, CORE['professionalPeerOf'], tgt_uri) in g


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


def test_relationship_attaches_at_role_level():
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
    # Edge is between the ROLE FACETS, not the Agents (so the defined relational
    # archetype classifies the role, not every role its bearer holds).
    assert (subj_uri, CORE['hasClient'], tgt_uri) in g
    assert (agent_a, CORE['hasClient'], agent_owner) not in g


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
    # Edge + provenance reference the ROLE FACETS now.
    assert (subj_uri, CORE['hasClient'], tgt_uri) in g
    derivs = list(g.subjects(RDF.type, PROV.Derivation))
    assert len(derivs) == 1, derivs
    d = derivs[0]
    assert (d, PROV.wasDerivedFrom, subj_uri) in g
    assert (d, PROV.wasDerivedFrom, tgt_uri) in g
    assert (d, PROV.value, Literal('Engineer A was retained by the Owner')) in g


def test_role_individual_archetype_parents_divergent_type():
    """Layer-1 convergence: the class a role individual is typed under gets BOTH
    archetype axes even when its name diverges from the role_class entity. The
    relational archetype sits under RelationalRole, decoupled from the
    ProfessionalRole/ParticipantRole disjointness, so pairing it with a
    Participant-side occupational archetype (ClientRole) is satisfiable."""
    svc = _svc()
    PROVIDER_CLIENT = str(PROETHICA['ProviderClientRole'])
    DESIGN_ENGINEER = str(PROETHICA['DesignEngineerRole'])
    CLIENT = str(PROETHICA['ClientRole'])
    # Divergent compound engineering type-class + provider_client category. The
    # occupational resolver returns the MOST SPECIFIC match (DesignEngineerRole, which
    # subClassOf EngineerRole), composed with the relational ProviderClientRole.
    p1 = svc._role_individual_archetype_parents(
        {'properties': {'roleCategory': ['provider_client']}},
        'OriginalDesignEngineerSubjecttoPeerReview')
    assert DESIGN_ENGINEER in p1 and PROVIDER_CLIENT in p1, p1
    # The Participant-side ClientRole composes with the relational ProviderClientRole.
    p2 = svc._role_individual_archetype_parents(
        {'properties': {'roleCategory': ['provider_client']}}, 'DeveloperClient')
    assert CLIENT in p2 and PROVIDER_CLIENT in p2, p2
    # No roleCategory and an unmapped occupational label -> empty (the tail the
    # RoleArchetypeShape flags, never a spurious parent).
    assert svc._role_individual_archetype_parents({'properties': {}}, 'Confidentiality-BoundPeerReviewer') == []


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
    """Build a two-individual fixture and return (g, subj_uri, tgt_uri) after
    serializing the subject's single relationship of type `rtype` toward
    `target_label`. The edges are ROLE-to-ROLE (between the role facets), so the
    facet URIs are the relevant endpoints."""
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
    return g, subj_uri, tgt_uri


def test_subject_of_review_maps_to_work_reviewed_by():
    """Passive review direction must orient to workReviewedBy, not reviewsWorkOf."""
    svc = _svc()
    g, subj_uri, tgt_uri = _rel_fixture(svc, 'Engineer A Original Design Engineer', 'Engineer A',
                        'subject_of_review', 'Engineer B Peer Reviewer', 'Engineer B')
    assert (subj_uri, CORE['workReviewedBy'], tgt_uri) in g
    assert (subj_uri, CORE['reviewsWorkOf'], tgt_uri) not in g


def test_has_provider_orients_hasclient_from_client_side():
    """A client naming its provider (has_provider) yields hasClient(provider, client)."""
    svc = _svc()
    g, subj_uri, tgt_uri = _rel_fixture(svc, 'Owner Peer Review Instructing Client', 'Owner',
                        'has_provider', 'Engineer B Peer Reviewer', 'Engineer B')
    # has_provider swaps: the provider (Engineer B = target facet) hasClient the client
    # (Owner = subject facet); edge runs target->subject at the ROLE level.
    assert (tgt_uri, CORE['hasClient'], subj_uri) in g
    assert (subj_uri, CORE['hasClient'], tgt_uri) not in g


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
    # The edge connects the role facets; the non-role action node never receives one.
    assert (subj_uri, CORE['hasClient'], owner_uri) in g2
    assert (subj_uri, CORE['hasClient'], action_uri) not in g2


def test_actor_edge_to_non_role_target_is_skipped():
    """Hardening: a target that resolves ONLY to a non-role node (no Agent, e.g. an
    Action) gets no actor edge. Actor relations hold between role-bearers, so an
    edge to a non-Agent node would violate domain/range."""
    svc = _svc()
    subj_facet = _role_entity('Engineer A Original Design Engineer')
    subj_rdf = {'properties': {
        'actor': ['Engineer A'],
        'relationships': ["{'type': 'has_client', 'target': 'Owner Covert Review Instruction'}"],
    }}
    svc._build_agent_indices([(subj_facet, subj_rdf)], CASE)
    subj_uri = CASE[svc._safe_label('Engineer A Original Design Engineer')]
    action_uri = CASE[svc._safe_label('Owner Covert Review Instruction')]
    # The only candidate for the target label is the non-role action node.
    svc._rel_label_index = {
        svc._norm_label('Engineer A Original Design Engineer'): subj_uri,
        svc._norm_label('Owner Covert Review Instruction'): action_uri,
    }
    g = Graph()
    svc._add_individual_properties(g, subj_uri, subj_facet, subj_rdf, CASE)
    assert len(list(g.triples((None, CORE['hasClient'], None)))) == 0


def test_relationship_provenance_idempotent():
    """Hardening: the prov-node IRI is deterministic from (subj, relprop, obj), so
    re-emitting the same edge (the actor bears it on multiple facets, or a re-commit)
    must not multi-value generatedAtTime / value / comment."""
    svc = _svc()
    g = Graph()
    a, b = CASE['Agent_Engineer_A'], CASE['Agent_Owner']
    svc._emit_relationship_provenance(g, CASE, a, 'hasClient', b, 'has_client', 'a quote')
    svc._emit_relationship_provenance(g, CASE, a, 'hasClient', b, 'has_client', 'a quote')
    prov = list(g.subjects(RDF.type, PROV.Derivation))
    assert len(prov) == 1, prov
    assert len(list(g.objects(prov[0], PROV.generatedAtTime))) == 1
    assert len(list(g.objects(prov[0], PROV.value))) == 1


# --- Individual definitions (symmetric with the class path) ---------------------

def test_individual_definition_emits_comment_and_skos():
    """Individuals previously received NO rdfs:comment/skos:definition; their
    definition survived only as a duplicated property literal. _emit_definitions
    (shared with the class path) restores symmetry."""
    svc = _svc()
    g = Graph()
    uri = CASE['Engineer_A_Design_Engineer']
    entity = types.SimpleNamespace(extraction_type='roles', entity_definition=None)
    rdf_data = {'definitions': [
        {'text': 'Created the original plans and designs for both towers.',
         'is_primary': True, 'source_section': 'facts'},
        {'text': 'Occupational archetype head for engineer specializations.',
         'is_primary': False,
         'source_uri': 'http://proethica.org/ontology/intermediate#EngineerRole',
         'source_ontology': 'proethica-intermediate', 'source_type': 'ontology'},
    ]}
    svc._emit_definitions(g, uri, entity, rdf_data)
    primary = 'Created the original plans and designs for both towers.'
    assert (uri, RDFS.comment, Literal(primary)) in g
    assert (uri, SKOS.definition, Literal(primary)) in g
    # Alternate definition -> skos:scopeNote tagged with the source CLASS (from
    # source_uri), not the source ontology, so it reads "Inherited from EngineerRole".
    assert (uri, SKOS.scopeNote,
            Literal('[EngineerRole] Occupational archetype head for engineer specializations.')) in g
    assert len(list(g.objects(uri, RDFS.comment))) == 1


def test_scopenote_tag_falls_back_to_ontology_then_section():
    """Without a source_uri the scope-note tag falls back to the source ontology,
    then the section (a second extraction definition from another pass)."""
    svc = _svc()
    g = Graph()
    uri = CASE['X']
    entity = types.SimpleNamespace(extraction_type='roles', entity_definition=None)
    rdf_data = {'definitions': [
        {'text': 'primary', 'is_primary': True, 'source_section': 'facts'},
        {'text': 'onto def', 'is_primary': False, 'source_ontology': 'proethica-intermediate'},
        {'text': 'discussion def', 'is_primary': False, 'source_section': 'discussion'},
    ]}
    svc._emit_definitions(g, uri, entity, rdf_data)
    assert (uri, SKOS.scopeNote, Literal('[proethica-intermediate] onto def')) in g
    assert (uri, SKOS.scopeNote, Literal('[discussion] discussion def')) in g


def test_individual_definition_falls_back_to_entity_definition():
    svc = _svc()
    g = Graph()
    uri = CASE['SomeIndividual']
    entity = types.SimpleNamespace(extraction_type='states', entity_definition='Fallback text.')
    svc._emit_definitions(g, uri, entity, {})  # no definitions[] array
    assert (uri, RDFS.comment, Literal('Fallback text.')) in g
    assert (uri, SKOS.definition, Literal('Fallback text.')) in g


# --- match_decision persisted as XAI annotation provenance ----------------------

def test_match_decision_persisted_as_annotations():
    svc = _svc()
    g = Graph()
    uri = CASE['Engineer_A_Design_Engineer']
    rdf_data = {'match_decision': {
        'reasoning': 'Design Engineer is a specialization of Engineer Role.',
        'confidence': 0.75,
        'matched_uri': 'http://proethica.org/ontology/intermediate#EngineerRole',
        'matched_label': 'Engineer Role',
        'matches_existing': True,
    }}
    svc._emit_match_decision(g, uri, rdf_data, PROV_NS)
    assert (uri, PROV_NS['matchedOntologyClass'], PROETHICA['EngineerRole']) in g
    assert (uri, PROV_NS['matchedOntologyLabel'], Literal('Engineer Role')) in g
    assert (uri, PROV_NS['matchConfidence'], Literal(0.75, datatype=XSD.decimal)) in g
    assert (uri, PROV_NS['matchesExisting'], Literal(True, datatype=XSD.boolean)) in g
    assert (uri, PROV_NS['matchReasoning'],
            Literal('Design Engineer is a specialization of Engineer Role.')) in g
    # The IRI-valued property MUST be declared owl:AnnotationProperty inline, or
    # Pellet auto-types it ObjectProperty and puns the target class.
    assert (PROV_NS['matchedOntologyClass'], RDF.type, OWL.AnnotationProperty) in g


def test_match_decision_minted_class_records_negative_evidence():
    """A 'no match' decision (the matcher minted a new class) still records the
    negative evidence -- itself XAI-useful -- without dangling matchedOntologyClass."""
    svc = _svc()
    g = Graph()
    uri = CASE['Engineer_A_Known_Design_Defect']
    rdf_data = {'match_decision': {'confidence': 0.0, 'matches_existing': False}}
    svc._emit_match_decision(g, uri, rdf_data, PROV_NS)
    assert (uri, PROV_NS['matchesExisting'], Literal(False, datatype=XSD.boolean)) in g
    assert len(list(g.objects(uri, PROV_NS['matchedOntologyClass']))) == 0


def test_category_disambiguation_on_cross_layer_collision():
    """A class IRI the immutable base reserves for a disjoint category must be
    disambiguated by appending the entity's category, so a Principle is never minted
    onto a Capability IRI (the pass-2 ProfessionalCompetence collision). No-op when
    there is no collision, the IRI is not in the base, or no category is given."""
    svc = _svc()
    # Stand in for the core+intermediate base map (avoids parsing TTLs in the test).
    svc._base_cat_cache = {'ProfessionalCompetence': 'Capability', 'EngineerRole': 'Role'}
    # Collision: a Principle onto a base Capability IRI -> disambiguated.
    assert svc._category_safe_class_local('ProfessionalCompetence', 'Principle') == 'ProfessionalCompetencePrinciple'
    # Same category as the base -> unchanged (legit reuse of an existing class).
    assert svc._category_safe_class_local('EngineerRole', 'Role') == 'EngineerRole'
    # Not in the base (a fresh discovered class) -> unchanged.
    assert svc._category_safe_class_local('NovelPrincipleClass', 'Principle') == 'NovelPrincipleClass'
    # No category (non-concept entity) -> unchanged.
    assert svc._category_safe_class_local('ProfessionalCompetence', None) == 'ProfessionalCompetence'


def test_match_decision_rejects_per_case_matched_uri():
    """A per-case copy IRI must not be recorded as the canonical match (it would
    re-introduce the injection pollution the curated filter removed)."""
    svc = _svc()
    g = Graph()
    uri = CASE['SomeIndividual']
    rdf_data = {'match_decision': {
        'matched_uri': 'http://proethica.org/ontology/case/8#JunkCopy',
        'matches_existing': True,
    }}
    svc._emit_match_decision(g, uri, rdf_data, PROV_NS)
    assert len(list(g.objects(uri, PROV_NS['matchedOntologyClass']))) == 0
    # matches_existing is still recorded.
    assert (uri, PROV_NS['matchesExisting'], Literal(True, datatype=XSD.boolean)) in g
