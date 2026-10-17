"""
Unit tests for UnifiedEntityResolver service.

Tests verify:
- OntServe entity fetching with caching
- Case entity fetching from TemporaryRDFStorage
- Merged lookup with case precedence
- Label-based index for auto-enhancement
"""

import pytest
import time
from unittest.mock import MagicMock, patch


class TestUnifiedEntityResolver:
    """Tests for UnifiedEntityResolver service."""

    def test_case_entities_take_precedence(self):
        """Case entities override OntServe entities with same URI."""
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

        with patch.object(UnifiedEntityResolver, '_get_ontserve_entities') as mock_ontserve:
            with patch.object(UnifiedEntityResolver, '_get_case_entities') as mock_case:
                # OntServe has base entity
                mock_ontserve.return_value = {
                    'http://example.org/Professional_Engineer': {
                        'label': 'Professional Engineer',
                        'definition': 'Base definition from ontology',
                        'entity_type': 'roles',
                        'extraction_type': 'roles',
                        'uri': 'http://example.org/Professional_Engineer',
                    }
                }

                # Case has specific instance
                mock_case.return_value = {
                    'http://example.org/Professional_Engineer': {
                        'label': 'Professional Engineer',
                        'definition': 'Case-specific: Mr. Smith, licensed PE',
                        'entity_type': 'roles',
                        'extraction_type': 'roles',
                        'source_pass': 1,
                        'uri': 'http://example.org/Professional_Engineer',
                    }
                }

                resolver = UnifiedEntityResolver(case_id=7)
                lookup = resolver.get_lookup_dict()

                # Case version should win
                entity = lookup['http://example.org/Professional_Engineer']
                assert entity['source'] == 'case'
                assert 'Mr. Smith' in entity['definition']

    def test_ontserve_only_when_no_case_match(self):
        """OntServe entities available when no case match exists."""
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

        with patch.object(UnifiedEntityResolver, '_get_ontserve_entities') as mock_ontserve:
            with patch.object(UnifiedEntityResolver, '_get_case_entities') as mock_case:
                mock_ontserve.return_value = {
                    'http://example.org/Duty_of_Care': {
                        'label': 'Duty of Care',
                        'definition': 'Professional obligation to avoid harm',
                        'entity_type': 'obligations',
                        'extraction_type': 'obligations',
                        'uri': 'http://example.org/Duty_of_Care',
                    }
                }
                mock_case.return_value = {}

                resolver = UnifiedEntityResolver(case_id=7)
                lookup = resolver.get_lookup_dict()

                # OntServe entity should be present
                assert 'http://example.org/Duty_of_Care' in lookup
                entity = lookup['http://example.org/Duty_of_Care']
                assert entity['source'] == 'ontology'
                assert entity['source_pass'] is None

    def test_label_index_case_insensitive(self):
        """Label index supports case-insensitive matching."""
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

        with patch.object(UnifiedEntityResolver, '_get_ontserve_entities') as mock_ontserve:
            with patch.object(UnifiedEntityResolver, '_get_case_entities') as mock_case:
                mock_ontserve.return_value = {}
                mock_case.return_value = {
                    'http://example.org/John_Smith': {
                        'label': 'John Smith',
                        'definition': 'The engineer',
                        'entity_type': 'roles',
                        'extraction_type': 'roles',
                        'source_pass': 1,
                        'uri': 'http://example.org/John_Smith',
                    }
                }

                resolver = UnifiedEntityResolver(case_id=7)
                resolver.get_lookup_dict()

                # Should match regardless of case
                label_index = resolver.get_label_index()
                assert 'john smith' in label_index
                assert label_index['john smith']['label'] == 'John Smith'

    def test_resolve_by_uri(self):
        """resolve() method works with URI."""
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

        with patch.object(UnifiedEntityResolver, '_get_ontserve_entities') as mock_ontserve:
            with patch.object(UnifiedEntityResolver, '_get_case_entities') as mock_case:
                mock_ontserve.return_value = {}
                mock_case.return_value = {
                    'http://example.org/Test_Entity': {
                        'label': 'Test Entity',
                        'definition': 'Test definition',
                        'entity_type': 'roles',
                        'extraction_type': 'roles',
                        'source_pass': 1,
                        'uri': 'http://example.org/Test_Entity',
                    }
                }

                resolver = UnifiedEntityResolver(case_id=7)
                entity = resolver.resolve('http://example.org/Test_Entity')

                assert entity is not None
                assert entity['label'] == 'Test Entity'

    def test_resolve_by_label(self):
        """resolve() method works with label."""
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

        with patch.object(UnifiedEntityResolver, '_get_ontserve_entities') as mock_ontserve:
            with patch.object(UnifiedEntityResolver, '_get_case_entities') as mock_case:
                mock_ontserve.return_value = {}
                mock_case.return_value = {
                    'http://example.org/Some_Entity': {
                        'label': 'My Entity Label',
                        'definition': 'Test definition',
                        'entity_type': 'roles',
                        'extraction_type': 'roles',
                        'source_pass': 1,
                        'uri': 'http://example.org/Some_Entity',
                    }
                }

                resolver = UnifiedEntityResolver(case_id=7)
                entity = resolver.resolve('My Entity Label')

                assert entity is not None
                assert entity['uri'] == 'http://example.org/Some_Entity'

    def test_resolve_returns_none_for_unknown(self):
        """resolve() returns None for unknown entities."""
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

        with patch.object(UnifiedEntityResolver, '_get_ontserve_entities') as mock_ontserve:
            with patch.object(UnifiedEntityResolver, '_get_case_entities') as mock_case:
                mock_ontserve.return_value = {}
                mock_case.return_value = {}

                resolver = UnifiedEntityResolver(case_id=7)
                entity = resolver.resolve('http://example.org/Unknown')

                assert entity is None

    def test_convenience_function(self):
        """get_unified_entity_lookup() convenience function works."""
        from app.services.entity.unified_entity_resolver import get_unified_entity_lookup

        with patch('app.services.entity.unified_entity_resolver.UnifiedEntityResolver') as MockResolver:
            mock_instance = MagicMock()
            mock_instance.get_lookup_dict.return_value = {'test': 'data'}
            MockResolver.return_value = mock_instance

            result = get_unified_entity_lookup(case_id=7)

            MockResolver.assert_called_once_with(case_id=7)
            assert result == {'test': 'data'}


class TestOntServeCache:
    """Tests for OntServe entity caching."""

    def test_cache_used_on_second_call(self):
        """Second call uses cached OntServe entities."""
        from app.services.entity import unified_entity_resolver
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

        # Set up cache directly to test caching behavior
        unified_entity_resolver._ontserve_cache['entities'] = {
            'http://example.org/Cached_Entity': {
                'label': 'Cached Entity',
                'definition': 'From cache',
                'entity_type': 'roles',
                'extraction_type': 'roles',
                'uri': 'http://example.org/Cached_Entity',
            }
        }
        unified_entity_resolver._ontserve_cache['timestamp'] = time.time()

        with patch.object(UnifiedEntityResolver, '_get_case_entities', return_value={}):
            # First resolver - should use cache (no MCP call)
            resolver1 = UnifiedEntityResolver(case_id=7)
            lookup1 = resolver1.get_lookup_dict()

            # Second resolver - should also use cache
            resolver2 = UnifiedEntityResolver(case_id=8)
            lookup2 = resolver2.get_lookup_dict()

            # Both should have the cached entity
            assert 'http://example.org/Cached_Entity' in lookup1
            assert 'http://example.org/Cached_Entity' in lookup2
            assert lookup1['http://example.org/Cached_Entity']['source'] == 'ontology'

    def test_clear_cache(self):
        """clear_ontserve_cache() clears the cache."""
        from app.services.entity import unified_entity_resolver
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

        # Set up fake cache
        unified_entity_resolver._ontserve_cache['entities'] = {'fake': 'data'}
        unified_entity_resolver._ontserve_cache['timestamp'] = time.time()

        # Clear it
        UnifiedEntityResolver.clear_ontserve_cache()

        assert unified_entity_resolver._ontserve_cache['entities'] is None
        assert unified_entity_resolver._ontserve_cache['timestamp'] == 0


class TestOntologyTargetDerivation:
    """Tests for _derive_ontology_target URI parsing."""

    def test_case_ontology_uri(self):
        """Case ontology URIs produce proethica-case-N target."""
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver
        assert UnifiedEntityResolver._derive_ontology_target(
            'http://proethica.org/ontology/case/7#EngineerARole'
        ) == 'proethica-case-7'

    def test_intermediate_ontology_uri(self):
        """Intermediate ontology URIs produce proethica-intermediate target."""
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver
        assert UnifiedEntityResolver._derive_ontology_target(
            'http://proethica.org/ontology/intermediate#ProfessionalEngineer'
        ) == 'proethica-intermediate'

    def test_unknown_uri_returns_empty(self):
        """Unrecognized URIs return empty string."""
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver
        assert UnifiedEntityResolver._derive_ontology_target(
            'http://example.org/some/other/uri#Foo'
        ) == ''

    def test_empty_and_none(self):
        """Empty string and None return empty string."""
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver
        assert UnifiedEntityResolver._derive_ontology_target('') == ''
        assert UnifiedEntityResolver._derive_ontology_target(None) == ''

    def test_ontology_target_in_case_entities(self):
        """ontology_target propagates through _get_case_entities output."""
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

        with patch.object(UnifiedEntityResolver, '_get_ontserve_entities', return_value={}):
            with patch.object(UnifiedEntityResolver, '_get_case_entities') as mock_case:
                mock_case.return_value = {
                    'http://proethica.org/ontology/case/7#TestRole': {
                        'label': 'Test Role',
                        'definition': 'A test role',
                        'entity_type': 'roles',
                        'extraction_type': 'roles',
                        'source_pass': 1,
                        'uri': 'http://proethica.org/ontology/case/7#TestRole',
                        'ontology_target': 'proethica-case-7',
                    }
                }

                resolver = UnifiedEntityResolver(case_id=7)
                lookup = resolver.get_lookup_dict()
                entity = lookup['http://proethica.org/ontology/case/7#TestRole']
                assert entity['ontology_target'] == 'proethica-case-7'

    def test_ontology_target_in_ontserve_entities(self):
        """ontology_target is set to proethica-intermediate for OntServe entities."""
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

        with patch.object(UnifiedEntityResolver, '_get_ontserve_entities') as mock_ont:
            mock_ont.return_value = {
                'http://proethica.org/ontology/intermediate#DutyOfCare': {
                    'label': 'Duty of Care',
                    'definition': 'Professional duty',
                    'entity_type': 'obligations',
                    'extraction_type': 'obligations',
                    'uri': 'http://proethica.org/ontology/intermediate#DutyOfCare',
                    'ontology_target': 'proethica-intermediate',
                }
            }
            with patch.object(UnifiedEntityResolver, '_get_case_entities', return_value={}):
                resolver = UnifiedEntityResolver(case_id=7)
                lookup = resolver.get_lookup_dict()
                entity = lookup['http://proethica.org/ontology/intermediate#DutyOfCare']
                assert entity['ontology_target'] == 'proethica-intermediate'


class TestComputeOntservePath:
    """Tests for compute_ontserve_path URL construction."""

    def test_case_entity_path(self):
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver
        path = UnifiedEntityResolver.compute_ontserve_path(
            'http://proethica.org/ontology/case/7#EngineerARole',
            'proethica-case-7'
        )
        assert path == '/entity/proethica-case-7/EngineerARole'

    def test_intermediate_entity_path(self):
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver
        path = UnifiedEntityResolver.compute_ontserve_path(
            'http://proethica.org/ontology/intermediate#DutyOfCare',
            'proethica-intermediate'
        )
        assert path == '/entity/proethica-intermediate/DutyOfCare'

    def test_derives_target_when_none(self):
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver
        path = UnifiedEntityResolver.compute_ontserve_path(
            'http://proethica.org/ontology/case/7#EngineerARole'
        )
        assert path == '/entity/proethica-case-7/EngineerARole'

    def test_empty_uri_returns_empty(self):
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver
        assert UnifiedEntityResolver.compute_ontserve_path('') == ''
        assert UnifiedEntityResolver.compute_ontserve_path(None) == ''

    def test_uri_without_fragment_returns_empty(self):
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver
        assert UnifiedEntityResolver.compute_ontserve_path('http://example.org/no-fragment') == ''

    def test_unrecognized_uri_no_target_returns_empty(self):
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver
        assert UnifiedEntityResolver.compute_ontserve_path('http://example.org/other#Foo') == ''


class TestPassMapping:
    """Tests for extraction type to pass number mapping."""

    def test_pass_1_entities(self):
        """Pass 1 entities get source_pass=1."""
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

        assert UnifiedEntityResolver.PASS_MAP['roles'] == 1
        assert UnifiedEntityResolver.PASS_MAP['states'] == 1
        assert UnifiedEntityResolver.PASS_MAP['resources'] == 1

    def test_pass_2_entities(self):
        """Pass 2 entities get source_pass=2."""
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

        assert UnifiedEntityResolver.PASS_MAP['principles'] == 2
        assert UnifiedEntityResolver.PASS_MAP['obligations'] == 2
        assert UnifiedEntityResolver.PASS_MAP['constraints'] == 2
        assert UnifiedEntityResolver.PASS_MAP['capabilities'] == 2

    def test_pass_3_entities(self):
        """Pass 3 entities get source_pass=3."""
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

        assert UnifiedEntityResolver.PASS_MAP['actions'] == 3
        assert UnifiedEntityResolver.PASS_MAP['events'] == 3

    def test_pass_4_entities(self):
        """Pass 4 entities get source_pass=4."""
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

        assert UnifiedEntityResolver.PASS_MAP['ethical_question'] == 4
        assert UnifiedEntityResolver.PASS_MAP['ethical_conclusion'] == 4
        assert UnifiedEntityResolver.PASS_MAP['causal_normative_link'] == 4


class TestOntServeRowSelection:
    """Category-inventory rows: case ontology and placeholder rows are skipped,
    a definitional ontology wins a shared URI (review of case 24-1, defect A)."""

    ENGINEER = 'http://proethica.org/ontology/intermediate#Engineer'
    PRECEDENT = 'http://proethica.org/ontology/intermediate#CasePrecedent'

    @staticmethod
    def _fake_client(rows_by_method):
        client = MagicMock()
        for method in ('get_all_role_entities', 'get_all_state_entities', 'get_all_resource_entities',
                       'get_all_principle_entities', 'get_all_obligation_entities',
                       'get_all_constraint_entities', 'get_all_capability_entities',
                       'get_all_action_entities', 'get_all_event_entities'):
            getattr(client, method).return_value = rows_by_method.get(method, [])
        return client

    def _fetch(self, rows_by_method):
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

        UnifiedEntityResolver.clear_ontserve_cache()
        try:
            with patch('app.services.ontserve.external_mcp_client.get_external_mcp_client',
                       return_value=self._fake_client(rows_by_method)):
                return UnifiedEntityResolver(case_id=None)._get_ontserve_entities()
        finally:
            UnifiedEntityResolver.clear_ontserve_cache()

    def test_case_ontology_placeholder_row_is_skipped(self):
        """intermediate#Engineer is declared only by proethica-case-112 with the
        placeholder description, so the bare word never enters the lookup."""
        entities = self._fetch({'get_all_role_entities': [{
            'uri': self.ENGINEER, 'label': 'Engineer',
            'description': 'Ontology class for Role', 'source': 'proethica-case-112',
        }]})
        assert self.ENGINEER not in entities

    def test_placeholder_row_from_a_definitional_ontology_is_skipped_too(self):
        entities = self._fetch({'get_all_role_entities': [{
            'uri': self.ENGINEER, 'label': 'Engineer',
            'description': 'Ontology class for Role', 'source': 'proethica-intermediate',
        }]})
        assert self.ENGINEER not in entities

    @pytest.mark.parametrize('reverse', [False, True])
    def test_definition_bearing_row_wins_a_shared_uri_in_either_order(self, reverse):
        rows = [
            {'uri': self.PRECEDENT, 'label': 'Case Precedent',
             'description': 'Ontology class for Resource', 'source': 'proethica-case-8'},
            {'uri': self.PRECEDENT, 'label': 'Case Precedent',
             'description': 'A prior Board opinion the discussion relies on.',
             'source': 'proethica-intermediate'},
        ]
        if reverse:
            rows.reverse()
        entities = self._fetch({'get_all_resource_entities': rows})
        entry = entities[self.PRECEDENT]
        assert entry['definition'] == 'A prior Board opinion the discussion relies on.'
        assert entry['ontology_target'] == 'proethica-intermediate'
        assert entry['ontserve_path'] == '/entity/proethica-intermediate/CasePrecedent'

    @pytest.mark.parametrize('reverse', [False, True])
    def test_definitional_ontology_outranks_a_described_domain_row(self, reverse):
        rows = [
            {'uri': self.PRECEDENT, 'label': 'Case Precedent',
             'description': 'Domain-level note.', 'source': 'engineering-ethics'},
            {'uri': self.PRECEDENT, 'label': 'Case Precedent',
             'description': 'A prior Board opinion the discussion relies on.',
             'source': 'proethica-intermediate'},
        ]
        if reverse:
            rows.reverse()
        entities = self._fetch({'get_all_resource_entities': rows})
        assert entities[self.PRECEDENT]['definition'] == 'A prior Board opinion the discussion relies on.'

    def test_extended_store_row_keeps_its_ontology_target(self):
        uri = 'http://proethica.org/ontology/intermediate#FaithfulAgentObligation'
        entities = self._fetch({'get_all_obligation_entities': [{
            'uri': uri, 'label': 'Faithful Agent Obligation',
            'description': 'The duty to act for each employer or client as a faithful agent.',
            'source': 'proethica-intermediate-extended',
        }]})
        assert entities[uri]['ontology_target'] == 'proethica-intermediate-extended'
        assert entities[uri]['ontserve_path'] == '/entity/proethica-intermediate-extended/FaithfulAgentObligation'

    def test_row_without_source_defaults_to_intermediate(self):
        uri = 'http://proethica.org/ontology/intermediate#DutyOfCare'
        entities = self._fetch({'get_all_obligation_entities': [{
            'uri': uri, 'label': 'Duty of Care', 'description': 'Professional duty.',
        }]})
        assert entities[uri]['ontology_target'] == 'proethica-intermediate'

    def test_rank_helper(self):
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver as R

        assert R._ontserve_row_rank({'source': 'proethica-case-8', 'description': 'Real text.'}) is None
        assert R._ontserve_row_rank({'source': 'proethica-core', 'description': 'ontology class for Role.'}) is None
        assert R._ontserve_row_rank({'source': 'proethica-core', 'description': 'Real text.'}) == (True, True)
        assert R._ontserve_row_rank({'source': 'engineering-ethics', 'description': 'Real text.'}) == (False, True)
        assert R._ontserve_row_rank({'source': 'engineering-ethics', 'description': ''}) == (False, False)


class TestProvisionAndCitationKeys:
    """Label index keys added for the case page scanner (review of case 24-1,
    defects B and D)."""

    def _index(self, case_entities):
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

        with patch.object(UnifiedEntityResolver, '_get_ontserve_entities', return_value={}), \
                patch.object(UnifiedEntityResolver, '_get_case_entities', return_value=case_entities):
            resolver = UnifiedEntityResolver(case_id=8)
            resolver.get_lookup_dict()
            return resolver.get_label_index()

    def test_provision_label_indexed_with_and_without_trailing_period(self):
        index = self._index({
            'http://proethica.org/ontology/case/8#III.1.b.': {
                'label': 'III.1.b.', 'definition': 'Engineers shall advise their clients.',
                'entity_type': 'CodeProvisionReference', 'extraction_type': 'code_provision_reference',
                'source_pass': 4, 'uri': 'http://proethica.org/ontology/case/8#III.1.b.',
            }
        })
        assert index['iii.1.b.']['label'] == 'III.1.b.'
        assert index['iii.1.b'] is index['iii.1.b.']

    def test_cited_case_indexed_as_cited(self):
        index = self._index({
            'http://proethica.org/ontology/case/8#BER_Case_76-4': {
                'label': 'BER Case 76-4', 'definition': 'Foundational precedent.',
                'entity_type': 'Resource', 'extraction_type': 'resources',
                'source_pass': 1, 'uri': 'http://proethica.org/ontology/case/8#BER_Case_76-4',
            }
        })
        assert index['case 76-4'] is index['ber case 76-4']

    def test_case_key_is_not_displaced_by_an_ontology_entry(self):
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

        ontology = {'http://proethica.org/ontology/intermediate#III_1_b': {
            'label': 'III.1.b', 'definition': 'Ontology provision text.',
            'entity_type': 'resources', 'extraction_type': 'resources',
            'uri': 'http://proethica.org/ontology/intermediate#III_1_b',
        }}
        case = {'http://proethica.org/ontology/case/8#III.1.b.': {
            'label': 'III.1.b.', 'definition': 'Case provision text.',
            'entity_type': 'CodeProvisionReference', 'extraction_type': 'code_provision_reference',
            'source_pass': 4, 'uri': 'http://proethica.org/ontology/case/8#III.1.b.',
        }}
        with patch.object(UnifiedEntityResolver, '_get_ontserve_entities', return_value=ontology), \
                patch.object(UnifiedEntityResolver, '_get_case_entities', return_value=case):
            resolver = UnifiedEntityResolver(case_id=8)
            resolver.get_lookup_dict()
            index = resolver.get_label_index()
        assert index['iii.1.b']['source'] == 'case'


class TestActorBoundAliases:
    """Text-grounded aliases are grounded by sentences that name the entity's
    actor (review of case 24-1, defect E)."""

    ROLE_URI = 'http://proethica.org/ontology/case/8#Engineer_L_Faithful_Agent'
    DUTY_URI = 'http://proethica.org/ontology/case/8#Engineer_L_Faithful_Agent_Duty'
    STATE_URI = 'http://proethica.org/ontology/case/8#Public_Safety_Faithful_Agent_Conflict'

    def _entities(self):
        canon = ("the present case illustrates a conflict between Fundamental Canon I.1, the engineer's "
                 "obligation to hold paramount the safety, health and welfare of the public; and Canon I.4, "
                 "the engineer's obligation to act for each employer or client as a faithful agent or trustee")
        own = ("Beyond the fact limitation, under Fundamental Canon I.4, Engineer L has an affirmative "
               "obligation to act as the client's faithful agent or trustee.")
        return {
            self.ROLE_URI: {
                'label': 'Engineer L Faithful Agent', 'definition': 'Role definition.',
                'entity_type': 'Role', 'extraction_type': 'roles', 'source_pass': 1,
                'uri': self.ROLE_URI, 'text_references': [own],
            },
            self.DUTY_URI: {
                'label': 'Engineer L Faithful Agent Duty', 'definition': 'Duty definition.',
                'entity_type': 'Obligation', 'extraction_type': 'obligations', 'source_pass': 2,
                'uri': self.DUTY_URI, 'text_references': [own],
            },
            self.STATE_URI: {
                'label': 'Public Safety Faithful Agent Conflict', 'definition': 'State definition.',
                'entity_type': 'State', 'extraction_type': 'states', 'source_pass': 1,
                'uri': self.STATE_URI, 'text_references': [canon],
            },
        }

    def _index(self, case_entities):
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

        with patch.object(UnifiedEntityResolver, '_get_ontserve_entities', return_value={}), \
                patch.object(UnifiedEntityResolver, '_get_case_entities', return_value=case_entities):
            resolver = UnifiedEntityResolver(case_id=8)
            resolver.get_lookup_dict()
            return resolver.get_label_index()

    def test_alias_carries_its_actor_and_drops_the_generic_quotation(self):
        index = self._index(self._entities())
        alias = index['faithful agent']
        assert alias['alias_actors'] == ['Engineer L']
        assert {e['uri'] for e in alias['alias_entities']} == {self.ROLE_URI, self.DUTY_URI}

    def test_alias_from_sentences_about_someone_else_is_not_grounded(self):
        entities = self._entities()
        recap = ('In BER Case 76-4, Engineer Doe acted as a faithful agent of the client '
                 'when he withheld the findings.')
        entities[self.ROLE_URI]['text_references'] = [recap]
        entities[self.DUTY_URI]['text_references'] = [recap]
        index = self._index(entities)
        assert 'faithful agent' not in index

    def test_exact_reference_grounds_an_entity_without_an_actor(self):
        entities = self._entities()
        entities[self.STATE_URI]['text_references'] = ['Faithful Agent']
        index = self._index(entities)
        assert self.STATE_URI in {e['uri'] for e in index['faithful agent']['alias_entities']}

    def test_actor_label_derivation(self):
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver as R

        agents = ['Board of Ethical Review', 'Engineer L', 'Client X']
        assert R._actor_label('Engineer L Faithful Agent Duty', agents) == 'Engineer L'
        assert R._actor_label('Board of Ethical Review Adjudicator', agents) == 'Board of Ethical Review'
        assert R._actor_label('Public Safety Faithful Agent Conflict', agents) == ''
        # no Agent individuals (working store): the label's own designator
        assert R._actor_label('Engineer A Engineer in Responsible Charge', []) == 'Engineer A'
        assert R._actor_label('Engineer Doe Design Engineer', []) == 'Engineer Doe'
        assert R._actor_label('Client W Project Owner', []) == 'Client W'
        assert R._actor_label('Public Safety Faithful Agent Conflict', []) == ''

    def test_phrase_grounding_rule(self):
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver as R

        refs = ['Engineer L acted as a faithful agent. The client refused.']
        sentences = R._reference_sentences(refs)
        assert sentences == ['Engineer L acted as a faithful agent.', 'The client refused.']
        assert R._phrase_grounded('faithful agent', 'Engineer L', refs, sentences)
        assert not R._phrase_grounded('faithful agent', 'Engineer Doe', refs, sentences)
        assert not R._phrase_grounded('faithful agent', '', refs, sentences)
        assert R._phrase_grounded('faithful agent', '', ['Faithful Agent'], ['Faithful Agent'])
