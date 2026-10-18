"""entity_classes for retrieval come from the committed graph (case 24-1 review,
lesson L7).

The working store (temporary_rdf_storage rdf_json_ld.types) is rewritten by
later canonicalization passes: for case 8 it named
CompetenceSelfAssessmentCapability, which no committed individual bears, and
omitted two classes committed individuals do bear. When a committed ontology
exists, the rdf:type triples of the case TTL decide; the working store is the
fallback. No database and no OntServe checkout: the graph loader, the
existence check and the session are patched.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import rdflib
from rdflib import RDF, RDFS, Literal, Namespace, URIRef
from rdflib.namespace import OWL

from app.services.commit import precedent_features
from app.services.commit.precedent_features import (
    derive_entity_classes,
    entity_classes_from_graph,
    update_entity_classes_from_storage,
)

CASE8 = Namespace('http://proethica.org/ontology/case/8#')
CORE = Namespace('http://proethica.org/ontology/core#')
PROETH = Namespace('http://proethica.org/ontology/intermediate#')
CASES = Namespace('http://proethica.org/ontology/cases#')
PROV = Namespace('http://www.w3.org/ns/prov#')

COMMITTED_CAPABILITY = str(PROETH.RiskAssessmentCapability)
COMMITTED_CAPABILITY_2 = str(PROETH.EngineeringAdvisoryCapability)
COMMITTED_OBLIGATION = str(PROETH.FaithfulAgentObligation)
WORKING_STORE_CAPABILITY = str(PROETH.CompetenceSelfAssessmentCapability)


def _committed_graph():
    g = rdflib.Graph()
    # Two capability individuals with their own intermediate classes.
    for ind, cls in ((CASE8.Engineer_L_Risk_Assessment, PROETH.RiskAssessmentCapability),
                     (CASE8.Engineer_L_Protective_Measures_Advisory, PROETH.EngineeringAdvisoryCapability)):
        g.add((ind, RDF.type, OWL.NamedIndividual))
        g.add((ind, RDF.type, CORE.Capability))
        g.add((ind, RDF.type, cls))
        g.add((ind, RDFS.label, Literal(str(ind).rsplit('#', 1)[-1].replace('_', ' '))))
    # An obligation individual.
    g.add((CASE8.Engineer_L_Faithful_Agent_Duty, RDF.type, OWL.NamedIndividual))
    g.add((CASE8.Engineer_L_Faithful_Agent_Duty, RDF.type, CORE.Obligation))
    g.add((CASE8.Engineer_L_Faithful_Agent_Duty, RDF.type, PROETH.FaithfulAgentObligation))
    # An analysis-layer individual without a core category, and a support node
    # that is not a named individual: neither contributes.
    g.add((CASE8['BER_Case_20-4'], RDF.type, OWL.NamedIndividual))
    g.add((CASE8['BER_Case_20-4'], RDF.type, CASES.PrecedentCaseReference))
    g.add((CASE8.some_edge_provenance, RDF.type, PROV.Derivation))
    return g


def _working_store_rows():
    return [SimpleNamespace(extraction_type='capabilities',
                            rdf_json_ld={'types': [WORKING_STORE_CAPABILITY]})]


class TestEntityClassesFromGraph:

    def test_groups_committed_rdf_types_by_core_category(self):
        classes = entity_classes_from_graph(_committed_graph())
        assert set(classes) == {'capability', 'obligation'}
        assert sorted(classes['capability']) == sorted([COMMITTED_CAPABILITY, COMMITTED_CAPABILITY_2])
        assert classes['obligation'] == [COMMITTED_OBLIGATION]

    def test_core_types_and_named_individual_are_not_classes_of_the_mapping(self):
        classes = entity_classes_from_graph(_committed_graph())
        flat = {uri for uris in classes.values() for uri in uris}
        assert str(CORE.Capability) not in flat
        assert str(OWL.NamedIndividual) not in flat
        assert str(CASES.PrecedentCaseReference) not in flat


class TestDerivationSource:

    def test_committed_graph_wins_over_a_divergent_working_store(self):
        storage = MagicMock()
        storage.query.filter_by.return_value.filter.return_value.all.return_value = _working_store_rows()
        with patch('app.services.entity.committed_case_graph.committed_case_exists', return_value=True), \
             patch('app.services.entity.committed_case_graph.load_case_graph',
                   return_value=_committed_graph()), \
             patch.object(precedent_features, 'TemporaryRDFStorage', storage):
            classes, source = derive_entity_classes(8)
        assert source == 'committed_graph'
        assert WORKING_STORE_CAPABILITY not in classes['capability']
        assert set(classes['capability']) == {COMMITTED_CAPABILITY, COMMITTED_CAPABILITY_2}

    def test_working_store_is_the_fallback_without_a_committed_ontology(self):
        storage = MagicMock()
        storage.query.filter_by.return_value.filter.return_value.all.return_value = _working_store_rows()
        with patch('app.services.entity.committed_case_graph.committed_case_exists', return_value=False), \
             patch.object(precedent_features, 'TemporaryRDFStorage', storage):
            classes, source = derive_entity_classes(8)
        assert source == 'working_store'
        assert classes == {'capability': [WORKING_STORE_CAPABILITY]}


class TestUpdateWritesTheCommittedMapping:

    def test_update_writes_committed_classes_and_records_the_source(self):
        fake_db = MagicMock()
        fake_db.session.execute.return_value.fetchone.return_value = (1,)
        with patch('app.services.entity.committed_case_graph.committed_case_exists', return_value=True), \
             patch('app.services.entity.committed_case_graph.load_case_graph',
                   return_value=_committed_graph()), \
             patch.object(precedent_features, 'db', fake_db):
            written = update_entity_classes_from_storage(8)
        assert written == 2
        update_params = fake_db.session.execute.call_args_list[-1].args[1]
        stored = json.loads(update_params['ec'])
        assert set(stored['capability']) == {COMMITTED_CAPABILITY, COMMITTED_CAPABILITY_2}
        assert update_params['src'] == 'committed_graph'
        fake_db.session.commit.assert_called_once()

    def test_update_never_raises(self):
        with patch('app.services.entity.committed_case_graph.committed_case_exists',
                   side_effect=RuntimeError('no OntServe checkout')), \
             patch.object(precedent_features, 'db', MagicMock()) as fake_db:
            assert update_entity_classes_from_storage(8) == 0
        fake_db.session.rollback.assert_called_once()
