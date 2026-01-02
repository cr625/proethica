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
        from app.services.unified_entity_resolver import UnifiedEntityResolver

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
        from app.services.unified_entity_resolver import UnifiedEntityResolver

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
        from app.services.unified_entity_resolver import UnifiedEntityResolver

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
        from app.services.unified_entity_resolver import UnifiedEntityResolver

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
        from app.services.unified_entity_resolver import UnifiedEntityResolver

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
        from app.services.unified_entity_resolver import UnifiedEntityResolver

        with patch.object(UnifiedEntityResolver, '_get_ontserve_entities') as mock_ontserve:
            with patch.object(UnifiedEntityResolver, '_get_case_entities') as mock_case:
                mock_ontserve.return_value = {}
                mock_case.return_value = {}

                resolver = UnifiedEntityResolver(case_id=7)
                entity = resolver.resolve('http://example.org/Unknown')

                assert entity is None

    def test_convenience_function(self):
        """get_unified_entity_lookup() convenience function works."""
        from app.services.unified_entity_resolver import get_unified_entity_lookup

        with patch('app.services.unified_entity_resolver.UnifiedEntityResolver') as MockResolver:
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
        from app.services import unified_entity_resolver
        from app.services.unified_entity_resolver import UnifiedEntityResolver

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
        from app.services import unified_entity_resolver
        from app.services.unified_entity_resolver import UnifiedEntityResolver

        # Set up fake cache
        unified_entity_resolver._ontserve_cache['entities'] = {'fake': 'data'}
        unified_entity_resolver._ontserve_cache['timestamp'] = time.time()

        # Clear it
        UnifiedEntityResolver.clear_ontserve_cache()

        assert unified_entity_resolver._ontserve_cache['entities'] is None
        assert unified_entity_resolver._ontserve_cache['timestamp'] == 0


class TestPassMapping:
    """Tests for extraction type to pass number mapping."""

    def test_pass_1_entities(self):
        """Pass 1 entities get source_pass=1."""
        from app.services.unified_entity_resolver import UnifiedEntityResolver

        assert UnifiedEntityResolver.PASS_MAP['roles'] == 1
        assert UnifiedEntityResolver.PASS_MAP['states'] == 1
        assert UnifiedEntityResolver.PASS_MAP['resources'] == 1

    def test_pass_2_entities(self):
        """Pass 2 entities get source_pass=2."""
        from app.services.unified_entity_resolver import UnifiedEntityResolver

        assert UnifiedEntityResolver.PASS_MAP['principles'] == 2
        assert UnifiedEntityResolver.PASS_MAP['obligations'] == 2
        assert UnifiedEntityResolver.PASS_MAP['constraints'] == 2
        assert UnifiedEntityResolver.PASS_MAP['capabilities'] == 2

    def test_pass_3_entities(self):
        """Pass 3 entities get source_pass=3."""
        from app.services.unified_entity_resolver import UnifiedEntityResolver

        assert UnifiedEntityResolver.PASS_MAP['actions'] == 3
        assert UnifiedEntityResolver.PASS_MAP['events'] == 3

    def test_pass_4_entities(self):
        """Pass 4 entities get source_pass=4."""
        from app.services.unified_entity_resolver import UnifiedEntityResolver

        assert UnifiedEntityResolver.PASS_MAP['ethical_question'] == 4
        assert UnifiedEntityResolver.PASS_MAP['ethical_conclusion'] == 4
        assert UnifiedEntityResolver.PASS_MAP['causal_normative_link'] == 4
