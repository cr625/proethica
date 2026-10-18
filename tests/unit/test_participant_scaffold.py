"""Participant scaffold and public duty (case-8 review, L6).

The participant Agent definition wrote "performs X, Y and Z and n more" from
isPerformedBy edges in alphabetical order, so an unperformed prescribed action
(the refusal to acquiesce, an unresolved endpoint) read as performed and the
prevailing duty hid behind "and 1 more". owesDutyToward, the
public_responsibility archetype edge, was named in the prompt but absent from
the controlled relationships vocabulary and the emitter's actor-edge map, so
the model staged "rel:owesDutyToward -> Community" as a literal with no
counterparty. Relational-only facets of an agent whose other facet carried the
occupational DesignEngineerRole produced RoleArchetypeShape warnings.

DB-free: graphs are built in the tests; the commit paths run on the shared stub.
"""
import textwrap
import types

from rdflib import Graph, Literal, Namespace, OWL, RDF, RDFS, URIRef
from rdflib.namespace import SKOS

from app.services import prompt_variable_resolver as pvr
from app.services.extraction import edge_spec as es
from app.services.commit.ontserve_commit_service import OntServeCommitService
from tests.mocks.commit_service_stub import make_stub_commit_service

CORE = Namespace("http://proethica.org/ontology/core#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
PROV = Namespace("http://www.w3.org/ns/prov#")
NS = Namespace("http://proethica.org/ontology/case/8#")
INT_NS = str(PROETH)


def _agent(g, local, label):
    agent = NS[local]
    g.add((agent, RDF.type, CORE.Agent))
    g.add((agent, RDFS.label, Literal(label)))
    return agent


def _action(g, local, label, agent, comment=None, marker=None, modality=None):
    a = NS[local]
    g.add((a, RDF.type, CORE.Action))
    g.add((a, RDFS.label, Literal(label)))
    g.add((a, CORE.isPerformedBy, agent))
    if comment:
        g.add((a, RDFS.comment, Literal(comment)))
    if marker:
        g.add((a, PROETH.temporalMarker, Literal(marker)))
    if modality:
        g.add((a, PROETH.actionModality, Literal(modality)))
    return a


def test_performs_names_only_performed_actions():
    g = Graph()
    agent = _agent(g, "Agent_Engineer_L", "Engineer L")
    _action(g, "Risk_Notification", "Risk Notification", agent,
            comment="Engineer L notifies Client X of the increased risk.", marker="After the studies")
    _action(g, "Refusal_to_Acquiesce", "Refusal to Acquiesce", agent,
            comment="Engineer L cannot ethically acquiesce in the client's refusal.",
            marker="Present, unresolved endpoint after Client X's refusal")
    _action(g, "Withdrawal", "Withdrawal from Project", agent, modality="prescribed")
    _action(g, "Study_Conduct", "Risk Study Conduct", agent, modality="performed",
            comment="The engineer must not skip the study.")   # explicit modality wins over the marker
    _action(g, "Hypothetical", "Hypothetical Redesign", agent, modality="counterfactual")

    assert es._action_modality(g, NS.Refusal_to_Acquiesce) == "prescribed"
    assert es._action_modality(g, NS.Risk_Notification) == "performed"
    assert es._action_modality(g, NS.Study_Conduct) == "performed"
    es.annotate_participant_agents(g, 8)
    d = str(g.value(agent, SKOS.definition))
    assert "performs Risk Notification and Risk Study Conduct;" in d
    assert "is prescribed to perform Refusal to Acquiesce and Withdrawal from Project" in d
    assert "Hypothetical Redesign" not in d
    assert d.endswith(es._DERIVED_MARKER)


def test_obligations_ordered_by_salience_not_alphabet():
    g = Graph()
    agent = _agent(g, "Agent_Engineer_L", "Engineer L")
    duties = {}
    for local, label in (("Alpha_Duty", "Alpha Confidentiality Duty"),
                         ("Faithful_Agent_Duty", "Faithful Agent Duty"),
                         ("Watershed_Safety_Duty", "Watershed Safety Duty"),
                         ("Zeta_Duty", "Zeta Reporting Duty")):
        o = NS[local]
        g.add((o, RDF.type, CORE.Obligation))
        g.add((o, RDFS.label, Literal(label)))
        g.add((o, CORE.obligatedParty, agent))
        duties[local] = o
    # The prevailing duty comes first regardless of the alphabet or the timeline.
    g.add((duties["Watershed_Safety_Duty"], CORE.prevailsOver, duties["Faithful_Agent_Duty"]))
    # Temporal order through the actions that engage each duty.
    for local, seq, duty in (("A1", 3, "Alpha_Duty"), ("A2", 1, "Zeta_Duty"), ("A3", 2, "Faithful_Agent_Duty")):
        a = NS[local]
        g.add((a, RDF.type, CORE.Action))
        g.add((a, PROETH.temporalSequence, Literal(seq)))
        g.add((a, CORE.raisesObligation, duties[duty]))
    assert es._salient_obligation_labels(g, agent) == [
        "Watershed Safety Duty", "Zeta Reporting Duty", "Faithful Agent Duty", "Alpha Confidentiality Duty"]
    es.annotate_participant_agents(g, 8)
    d = str(g.value(agent, SKOS.definition))
    assert "bears Watershed Safety Duty, Zeta Reporting Duty, Faithful Agent Duty and Alpha Confidentiality Duty" in d


def test_facet_clause_fits_a_character_budget():
    labels = [f"Obligation number {i} with a deliberately long label for the budget" for i in range(12)]
    clause = es._facet_clause("bears", labels)
    assert len(clause) <= es.FACET_CLAUSE_BUDGET
    assert clause.endswith("more")
    shown = sum(1 for lbl in labels if lbl in clause)
    assert shown >= 3 and shown < len(labels)
    assert clause.endswith(f"and {len(labels) - shown} more")
    # The first label always fits, even when it exceeds the budget on its own.
    long = ["x" * 400]
    assert es._facet_clause("bears", long) == "bears " + "x" * 400
    # Short lists are listed in full.
    assert es._facet_clause("performs", ["A", "B", "C", "D"]) == "performs A, B, C and D"


# --- owesDutyToward and the PublicInterest counterparty -----------------------

def _service(tmp_path, monkeypatch, chain=None):
    chain = chain or (lambda local: 'Role' if local in ('DesignEngineerRole', 'PublicResponsibilityRole') else None)
    return make_stub_commit_service(tmp_path, monkeypatch, chain_resolver=chain,
                                    header_fields={'title': 'Mock Case', 'case_number': None, 'decade': None})


def _role(label, props, types_=('DesignEngineerRole',)):
    entity = types.SimpleNamespace(
        extraction_type='roles', entity_type='roles', entity_label=label, entity_definition='A role.',
        iao_document_uri=None, iao_document_label=None, cited_by_role=None, available_to_role=None,
        extraction_model=None)
    return entity, {'properties': props, 'types': [f'{INT_NS}{t}' for t in types_]}


def _assert_public_duty(g, facet, alt_label):
    public = NS.PublicInterest
    assert (public, RDF.type, PROETH.PublicInterest) in g
    assert (public, RDF.type, OWL.NamedIndividual) in g
    assert (public, RDF.type, CORE.Agent) not in g   # not a one-hop actor-pool candidate
    assert str(g.value(public, RDFS.label)) == 'General public'
    assert g.value(public, SKOS.definition) is not None
    if alt_label:
        assert (public, SKOS.altLabel, Literal(alt_label)) in g
    assert (facet, PROETH.owesDutyToward, public) in g
    assert (facet, RDF.type, PROETH.PublicResponsibilityRole) in g
    staged = {str(o) for o in g.objects(facet, PROETH.otherAttribute)}
    assert not any(s.startswith('rel:owesDutyToward') for s in staged), staged


def test_relationship_owes_duty_toward_mints_the_counterparty(tmp_path, monkeypatch):
    svc = _service(tmp_path, monkeypatch)
    entity, rdf = _role('Engineer L Design Engineer', {
        'actor': ['Engineer L'],
        'relationships': ["{'type': 'owesDutyToward', 'target': 'Community', "
                          "'quote': 'hold paramount the safety, health, and welfare of the public'}"],
    })
    result = svc._commit_individuals_to_case_ontology(8, [(entity, rdf)])
    assert result.get('error') is None, result
    g = Graph()
    g.parse(result['file'], format='turtle')
    facet = NS['Engineer_L_Design_Engineer']
    _assert_public_duty(g, facet, 'Community')
    prov = NS['relationship_edge_provenance_Engineer_L_Design_Engineer_owesDutyToward_PublicInterest']
    assert (prov, RDF.type, PROV.Derivation) in g
    assert str(g.value(prov, PROV.value)).startswith('hold paramount')


def test_overflow_entry_naming_the_public_duty_becomes_the_edge(tmp_path, monkeypatch):
    svc = _service(tmp_path, monkeypatch)
    entity, rdf = _role('Engineer L Design Engineer', {
        'actor': ['Engineer L'],
        'additionalRelationships': ["{'type': 'owesDutyToward', 'target': 'Community', 'quote': 'q'}",
                                    "{'type': 'mentors', 'target': 'Engineer M', 'quote': 'q2'}"],
    })
    result = svc._commit_individuals_to_case_ontology(8, [(entity, rdf)])
    g = Graph()
    g.parse(result['file'], format='turtle')
    facet = NS['Engineer_L_Design_Engineer']
    _assert_public_duty(g, facet, 'Community')
    # Other overflow entries are still staged as before.
    assert (facet, PROETH.otherAttribute, Literal('rel:mentors -> Engineer M')) in g


def test_public_responsibility_fallback_mints_the_counterparty(tmp_path, monkeypatch):
    svc = _service(tmp_path, monkeypatch)
    entity, rdf = _role('Engineer L Public Responsibility', {
        'actor': ['Engineer L'], 'roleCategory': ['public_responsibility']},
        types_=('PublicResponsibilityRole',))
    result = svc._commit_individuals_to_case_ontology(8, [(entity, rdf)])
    g = Graph()
    g.parse(result['file'], format='turtle')
    _assert_public_duty(g, NS['Engineer_L_Public_Responsibility'], None)


def test_vocabulary_block_lists_owes_duty_toward(tmp_path, monkeypatch):
    (tmp_path / 'proethica-core.ttl').write_text(textwrap.dedent('''\
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
        @prefix core: <http://proethica.org/ontology/core#> .
        core:relatedTo a owl:ObjectProperty .
        core:hasClient a owl:ObjectProperty ; rdfs:subPropertyOf core:relatedTo ;
            skos:definition "The provider side of a service relationship." .
    '''), encoding='utf-8')
    (tmp_path / 'proethica-intermediate.ttl').write_text(textwrap.dedent('''\
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix : <http://proethica.org/ontology/intermediate#> .
        :owesDutyToward a owl:ObjectProperty ;
            rdfs:comment "A professional role owes a protective duty toward the general public." .
    '''), encoding='utf-8')
    monkeypatch.setattr(pvr, '_ontology_ttl', lambda name: str(tmp_path / name))
    block = pvr._role_relationships_block()
    lines = block.splitlines()
    assert any(l.startswith('- hasClient: The provider side') for l in lines)
    odt = [l for l in lines if l.startswith('- owesDutyToward:')]
    assert len(odt) == 1
    assert 'protective duty toward the general public' in odt[0]
    assert 'PublicInterest' in odt[0] and 'public_responsibility' in odt[0]
    assert lines.index(odt[0]) < [i for i, l in enumerate(lines) if l.startswith('- relatedTo:')][0]


def test_relational_only_facet_carries_the_bearer_occupational_type(tmp_path, monkeypatch):
    svc = _service(tmp_path, monkeypatch)
    design, design_rdf = _role('Engineer L Design Engineer',
                               {'actor': ['Engineer L'], 'roleCategory': ['provider_client']})
    public, public_rdf = _role('Engineer L Public Responsibility',
                               {'actor': ['Engineer L'], 'roleCategory': ['public_responsibility']},
                               types_=('PublicResponsibilityRole',))
    faithful, faithful_rdf = _role('Engineer L Faithful Agent',
                                   {'actor': ['Engineer L'], 'roleCategory': ['provider_client']},
                                   types_=('ProviderClientRole',))
    result = svc._commit_individuals_to_case_ontology(
        8, [(design, design_rdf), (public, public_rdf), (faithful, faithful_rdf)])
    assert result.get('error') is None, result
    g = Graph()
    g.parse(result['file'], format='turtle')
    for local in ('Engineer_L_Public_Responsibility', 'Engineer_L_Faithful_Agent'):
        assert (NS[local], RDF.type, PROETH.DesignEngineerRole) in g, local
    assert (NS['Engineer_L_Design_Engineer'], RDF.type, PROETH.DesignEngineerRole) in g
    agent = NS['Agent_Engineer_L']
    assert len(list(g.objects(agent, CORE.hasRole))) == 3


def test_two_occupational_classes_leave_relational_facets_untyped(tmp_path, monkeypatch):
    svc = _service(tmp_path, monkeypatch,
                   chain=lambda local: 'Role' if local in ('ClientRole', 'OwnerRole', 'ProviderClientRole') else None)
    rows = [
        _role('Owner Developer Client', {'actor': ['Owner']}, types_=('ClientRole',)),
        _role('Owner Property Owner', {'actor': ['Owner']}, types_=('OwnerRole',)),
        _role('Owner Service Recipient', {'actor': ['Owner']}, types_=('ProviderClientRole',)),
    ]
    result = svc._commit_individuals_to_case_ontology(8, rows)
    g = Graph()
    g.parse(result['file'], format='turtle')
    types_ = {str(t).split('#')[-1] for t in g.objects(NS['Owner_Service_Recipient'], RDF.type)
              if str(t).startswith(INT_NS)}
    assert types_ == {'ProviderClientRole'}
