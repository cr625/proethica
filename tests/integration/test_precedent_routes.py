"""
Tests for precedent discovery routes.

Tests the routes in app/routes/precedents.py including:
- Precedent finder page
- API endpoints for finding precedents
- Similarity network API
- Similarity matrix API
- Lineage graph API
- Pending precedents
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass
from typing import Dict, List, Optional
from app.models.document import Document, PROCESSING_STATUS
from app.models.world import World
from app import db


# --- Fixtures ---

@pytest.fixture
def test_world(app_context):
    """Create a test world for case documents."""
    world = World(name='Test World', description='Test world for precedent tests')
    db.session.add(world)
    db.session.commit()
    return world


# --- Test data helpers ---

def _create_case_document(world_id, title, case_number=None, outcome=None,
                          subject_tags=None, year=None):
    """Create a case document in the test database."""
    metadata = {}
    if case_number:
        metadata['case_number'] = case_number
    if outcome:
        metadata['outcome'] = outcome
    if subject_tags:
        metadata['subject_tags'] = subject_tags
    if year:
        metadata['year'] = year
        metadata['date_parts'] = {'year': int(year)}

    doc = Document(
        title=title,
        document_type='case',
        world_id=world_id,
        content=f'Content for {title}',
        processing_status=PROCESSING_STATUS['PENDING'],
        doc_metadata=metadata,
    )
    db.session.add(doc)
    db.session.commit()
    return doc


@dataclass
class MockPrecedentMatch:
    """Mock of PrecedentMatch dataclass."""
    target_case_id: int
    target_case_title: str
    target_case_url: Optional[str]
    overall_score: float
    component_scores: Dict[str, float]
    matching_provisions: List[str]
    outcome_match: bool
    llm_analysis: Optional[str] = None
    relevance_explanation: Optional[str] = None
    target_outcome: Optional[str] = None
    target_transformation: Optional[str] = None


@dataclass
class MockSimilarityResult:
    """Mock of SimilarityResult dataclass."""
    source_case_id: int
    target_case_id: int
    overall_similarity: float
    component_scores: Dict[str, float]
    matching_provisions: List[str]
    outcome_match: bool
    weights_used: Dict[str, float]
    method: str = 'section'
    per_component_scores: Optional[Dict[str, float]] = None


# --- Tests for find_precedents page ---

class TestPrecedentFinderPage:
    """Tests for GET /cases/precedents/"""

    def test_precedent_finder_loads(self, client, app_context):
        """Precedent finder page renders without cases."""
        response = client.get('/cases/precedents/')
        assert response.status_code == 200

    def test_precedent_finder_shows_cases(self, client, test_world):
        """Precedent finder lists available cases in the selector."""
        doc = _create_case_document(test_world.id, 'Case 23-4: Test Ethics Case',
                                    case_number='23-4')

        response = client.get('/cases/precedents/')
        assert response.status_code == 200
        assert b'23-4' in response.data

    def test_precedent_finder_with_source_case(self, client, test_world):
        """Precedent finder accepts case_id query parameter."""
        doc = _create_case_document(test_world.id, 'Case 23-4: Test Case',
                                    case_number='23-4')

        with patch('app.routes.precedents._find_precedents_for_case') as mock_find:
            mock_find.return_value = {
                'success': True,
                'source_case_id': doc.id,
                'count': 0,
                'precedents': []
            }
            response = client.get(f'/cases/precedents/?case_id={doc.id}')
            assert response.status_code == 200
            mock_find.assert_called_once_with(doc.id)

    def test_precedent_finder_nonexistent_case(self, client, app_context):
        """Precedent finder handles nonexistent case_id gracefully."""
        response = client.get('/cases/precedents/?case_id=99999')
        assert response.status_code == 200


# --- Tests for API find precedents ---

class TestApiFindPrecedents:
    """Tests for GET /cases/precedents/api/find"""

    def test_api_find_requires_case_id(self, client, app_context):
        """API returns 400 when case_id is missing."""
        response = client.get('/cases/precedents/api/find')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_api_find_returns_results(self, client, test_world):
        """API returns precedent results for valid case_id."""
        doc = _create_case_document(test_world.id, 'Case 23-4: Test Case',
                                    case_number='23-4')

        with patch('app.routes.precedents._find_precedents_for_case') as mock_find:
            mock_find.return_value = {
                'success': True,
                'source_case_id': doc.id,
                'count': 1,
                'precedents': [{
                    'case_id': 2,
                    'title': 'Similar Case',
                    'overall_score': 0.75
                }]
            }
            response = client.get(f'/cases/precedents/api/find?case_id={doc.id}')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['count'] == 1

    def test_api_find_accepts_limit_and_min_score(self, client, test_world):
        """API passes limit and min_score parameters to the service."""
        doc = _create_case_document(test_world.id, 'Case 23-4: Test Case',
                                    case_number='23-4')

        with patch('app.routes.precedents._find_precedents_for_case') as mock_find:
            mock_find.return_value = {'success': True, 'count': 0, 'precedents': []}
            response = client.get(
                f'/cases/precedents/api/find?case_id={doc.id}&limit=5&min_score=0.5'
            )
            assert response.status_code == 200
            mock_find.assert_called_once_with(doc.id, limit=5, min_score=0.5)


# --- Tests for similarity network ---

class TestSimilarityNetworkView:
    """Tests for GET /cases/precedents/network"""

    def test_network_view_loads(self, client, app_context):
        """Network visualization page renders."""
        response = client.get('/cases/precedents/network')
        assert response.status_code == 200

    def test_network_view_with_focus_case(self, client, test_world):
        """Network view accepts focus case_id."""
        doc = _create_case_document(test_world.id, 'Case 23-4: Test Case',
                                    case_number='23-4')
        response = client.get(f'/cases/precedents/network?case_id={doc.id}')
        assert response.status_code == 200


class TestApiSimilarityNetwork:
    """Tests for GET /cases/precedents/api/similarity_network"""

    def test_network_api_no_features(self, client, app_context):
        """Network API returns error when no cases have features."""
        response = client.get('/cases/precedents/api/similarity_network')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is False or len(data.get('nodes', [])) == 0

    def test_network_api_with_features(self, client, test_world):
        """Network API returns nodes and edges when features exist."""
        doc1 = _create_case_document(test_world.id, 'Case 23-4: Test A',
                                     case_number='23-4', outcome='ethical')
        doc2 = _create_case_document(test_world.id, 'Case 24-1: Test B',
                                     case_number='24-1', outcome='unethical')

        db.session.execute(db.text("""
            INSERT INTO case_precedent_features (case_id, outcome_type, provisions_cited, subject_tags)
            VALUES (:id1, 'ethical', ARRAY['II.1.a'], ARRAY['AI']),
                   (:id2, 'unethical', ARRAY['II.1.a', 'III.4'], ARRAY['AI', 'Safety'])
        """), {'id1': doc1.id, 'id2': doc2.id})
        db.session.commit()

        mock_result = MockSimilarityResult(
            source_case_id=doc1.id,
            target_case_id=doc2.id,
            overall_similarity=0.65,
            component_scores={
                'facts_similarity': 0.7,
                'discussion_similarity': 0.5,
                'provision_overlap': 0.8,
                'outcome_alignment': 0.0,
                'tag_overlap': 0.5,
                'principle_overlap': 0.0
            },
            matching_provisions=['II.1.a'],
            outcome_match=False,
            weights_used={'facts_similarity': 0.3}
        )

        with patch('app.services.precedent.PrecedentSimilarityService') as MockService:
            instance = MockService.return_value
            instance.calculate_similarity.return_value = mock_result
            instance.cache_similarity.return_value = None

            response = client.get('/cases/precedents/api/similarity_network?min_score=0.1')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert len(data['nodes']) == 2
            assert 'metadata' in data

    def test_network_api_component_filter(self, client, test_world):
        """Network API supports filtering by specific component."""
        doc1 = _create_case_document(test_world.id, 'Case 23-4: Test A',
                                     case_number='23-4')
        doc2 = _create_case_document(test_world.id, 'Case 24-1: Test B',
                                     case_number='24-1')

        db.session.execute(db.text("""
            INSERT INTO case_precedent_features (case_id, outcome_type, provisions_cited)
            VALUES (:id1, 'ethical', ARRAY['II.1.a']),
                   (:id2, 'unethical', ARRAY['II.1.a'])
        """), {'id1': doc1.id, 'id2': doc2.id})

        db.session.execute(db.text("""
            INSERT INTO precedent_similarity_cache
                (source_case_id, target_case_id, overall_similarity,
                 facts_similarity, discussion_similarity, provision_overlap,
                 outcome_alignment, tag_overlap, principle_overlap)
            VALUES (:src, :tgt, 0.7, 0.8, 0.5, 0.9, 0.0, 0.3, 0.1)
        """), {'src': doc1.id, 'tgt': doc2.id})
        db.session.commit()

        response = client.get(
            '/cases/precedents/api/similarity_network'
            '?component=provision_overlap&component_min=0.5'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data.get('component_filter') == 'provision_overlap'

    def test_network_api_tag_filter(self, client, test_world):
        """Network API supports filtering by subject tag."""
        doc1 = _create_case_document(test_world.id, 'Case 23-4: Test A',
                                     case_number='23-4')

        db.session.execute(db.text("""
            INSERT INTO case_precedent_features (case_id, outcome_type, subject_tags)
            VALUES (:id1, 'ethical', ARRAY['AI', 'Safety'])
        """), {'id1': doc1.id})
        db.session.commit()

        response = client.get('/cases/precedents/api/similarity_network?tag=AI')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data.get('tag_filter') == 'AI'


# --- Tests for similarity matrix ---

class TestApiSimilarityMatrix:
    """Tests for GET /cases/precedents/api/similarity_matrix"""

    def test_matrix_api_no_features(self, client, app_context):
        """Matrix API returns empty when no features exist."""
        response = client.get('/cases/precedents/api/similarity_matrix')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['cases'] == []
        assert data['matrix'] == []

    def test_matrix_api_with_cases(self, client, test_world):
        """Matrix API returns NxN matrix for cases with features."""
        doc1 = _create_case_document(test_world.id, 'Case 23-4: Test A',
                                     case_number='23-4')
        doc2 = _create_case_document(test_world.id, 'Case 24-1: Test B',
                                     case_number='24-1')

        db.session.execute(db.text("""
            INSERT INTO case_precedent_features (case_id, outcome_type)
            VALUES (:id1, 'ethical'), (:id2, 'unethical')
        """), {'id1': doc1.id, 'id2': doc2.id})
        db.session.commit()

        mock_result = MockSimilarityResult(
            source_case_id=doc1.id,
            target_case_id=doc2.id,
            overall_similarity=0.65,
            component_scores={'provision_overlap': 0.8},
            matching_provisions=['II.1.a'],
            outcome_match=False,
            weights_used={}
        )

        with patch('app.services.precedent.PrecedentSimilarityService') as MockService:
            instance = MockService.return_value
            instance.calculate_similarity.return_value = mock_result

            response = client.get('/cases/precedents/api/similarity_matrix')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert len(data['cases']) == 2
            assert len(data['matrix']) == 2
            assert len(data['matrix'][0]) == 2
            # Diagonal should be 1.0 (self-similarity)
            assert data['matrix'][0][0] == 1.0
            assert data['matrix'][1][1] == 1.0

    def test_matrix_api_component_parameter(self, client, test_world):
        """Matrix API accepts component parameter for specific scoring."""
        doc1 = _create_case_document(test_world.id, 'Case 23-4: Test A',
                                     case_number='23-4')

        db.session.execute(db.text("""
            INSERT INTO case_precedent_features (case_id, outcome_type)
            VALUES (:id1, 'ethical')
        """), {'id1': doc1.id})
        db.session.commit()

        response = client.get('/cases/precedents/api/similarity_matrix?component=provision_overlap')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['component'] == 'provision_overlap'


# --- Tests for lineage graph ---

class TestLineageGraphView:
    """Tests for GET /cases/precedents/lineage"""

    def test_lineage_view_loads(self, client, app_context):
        """Lineage graph page renders."""
        response = client.get('/cases/precedents/lineage')
        assert response.status_code == 200

    def test_lineage_view_with_focus_case(self, client, test_world):
        """Lineage view accepts focus case_id."""
        doc = _create_case_document(test_world.id, 'Case 23-4: Test Case',
                                    case_number='23-4')

        db.session.execute(db.text("""
            INSERT INTO case_precedent_features (case_id, outcome_type)
            VALUES (:id, 'ethical')
        """), {'id': doc.id})
        db.session.commit()

        response = client.get(f'/cases/precedents/lineage?case_id={doc.id}')
        assert response.status_code == 200


class TestApiLineageGraph:
    """Tests for GET /cases/precedents/api/lineage_graph"""

    def test_lineage_api_no_features(self, client, app_context):
        """Lineage API returns empty when no features exist."""
        response = client.get('/cases/precedents/api/lineage_graph')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['nodes'] == []
        assert data['edges'] == []

    def test_lineage_api_returns_nodes(self, client, test_world):
        """Lineage API returns nodes for cases with features."""
        doc1 = _create_case_document(test_world.id, 'Case 23-4: Test A',
                                     case_number='23-4', year='2023')
        doc2 = _create_case_document(test_world.id, 'Case 24-1: Test B',
                                     case_number='24-1', year='2024')

        db.session.execute(db.text("""
            INSERT INTO case_precedent_features (case_id, outcome_type, cited_case_ids)
            VALUES (:id1, 'ethical', ARRAY[:id2]::int[]),
                   (:id2, 'unethical', NULL)
        """), {'id1': doc1.id, 'id2': doc2.id})
        db.session.commit()

        response = client.get('/cases/precedents/api/lineage_graph?show_all=true')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['nodes']) == 2
        assert len(data['edges']) == 1
        # Edge direction: doc1 cites doc2
        assert data['edges'][0]['source'] == doc1.id
        assert data['edges'][0]['target'] == doc2.id

    def test_lineage_api_focus_mode(self, client, test_world):
        """Lineage API focus mode filters to ego-network."""
        doc1 = _create_case_document(test_world.id, 'Case 23-4: A',
                                     case_number='23-4', year='2023')
        doc2 = _create_case_document(test_world.id, 'Case 24-1: B',
                                     case_number='24-1', year='2024')
        doc3 = _create_case_document(test_world.id, 'Case 25-1: C',
                                     case_number='25-1', year='2025')

        # doc1 cites doc2; doc3 is isolated
        db.session.execute(db.text("""
            INSERT INTO case_precedent_features (case_id, outcome_type, cited_case_ids)
            VALUES (:id1, 'ethical', ARRAY[:id2]::int[]),
                   (:id2, 'unethical', NULL),
                   (:id3, 'ethical', NULL)
        """), {'id1': doc1.id, 'id2': doc2.id, 'id3': doc3.id})
        db.session.commit()

        response = client.get(f'/cases/precedents/api/lineage_graph?case_id={doc1.id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        # Focus on doc1 should include doc1 and doc2 (connected), exclude doc3
        node_ids = [n['id'] for n in data['nodes']]
        assert doc1.id in node_ids
        assert doc2.id in node_ids
        assert doc3.id not in node_ids

    def test_lineage_api_metadata(self, client, test_world):
        """Lineage API returns metadata with statistics."""
        doc1 = _create_case_document(test_world.id, 'Case 23-4: A',
                                     case_number='23-4', year='2023')

        db.session.execute(db.text("""
            INSERT INTO case_precedent_features (case_id, outcome_type)
            VALUES (:id1, 'ethical')
        """), {'id1': doc1.id})
        db.session.commit()

        response = client.get('/cases/precedents/api/lineage_graph?show_all=true')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'metadata' in data
        assert 'total_nodes' in data['metadata']
        assert 'total_edges' in data['metadata']
        assert 'year_range' in data['metadata']
        assert 'outcome_distribution' in data['metadata']


# --- Tests for pending precedents ---

class TestPendingPrecedents:
    """Tests for pending precedent routes."""

    def test_pending_page_loads(self, client, app_context):
        """Pending precedents page renders."""
        with patch(
            'app.services.precedent.cited_case_ingestor.CitedCaseIngestor'
        ) as MockIngestor, patch(
            'app.services.precedent.cited_case_ingestor.get_ingestion_summary'
        ) as mock_summary:
            instance = MockIngestor.return_value
            instance.get_all_pending_url_summary.return_value = {
                'total_pending': 0,
                'urls': []
            }
            instance.find_missing_case_urls.return_value = []
            mock_summary.return_value = {'total': 0, 'ingested': 0}

            response = client.get('/cases/precedents/pending')
            assert response.status_code == 200

    def test_pending_api_returns_summary(self, client, app_context):
        """Pending API returns structured summary."""
        with patch(
            'app.services.precedent.cited_case_ingestor.CitedCaseIngestor'
        ) as MockIngestor, patch(
            'app.services.precedent.cited_case_ingestor.get_ingestion_summary'
        ) as mock_summary:
            instance = MockIngestor.return_value
            instance.find_missing_case_urls.return_value = [
                'https://example.com/case1',
                'https://example.com/case2'
            ]
            instance.get_all_pending_url_summary.return_value = [
                {'url': 'https://example.com/case1', 'referenced_by': [1]}
            ]
            mock_summary.return_value = {'total': 10, 'ingested': 8}

            response = client.get('/cases/precedents/api/pending')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['total_missing'] == 2
            assert data['summary']['total'] == 10


# --- Tests for ingest API ---

class TestApiIngest:
    """Tests for POST /cases/precedents/api/ingest"""

    def test_ingest_single_url(self, client, app_context):
        """Ingest API handles single URL ingestion."""
        with patch(
            'app.services.precedent.cited_case_ingestor.CitedCaseIngestor'
        ) as MockIngestor:
            instance = MockIngestor.return_value
            instance.ingest_from_url.return_value = {
                'success': True,
                'case_id': 100,
                'title': 'New Case'
            }

            response = client.post(
                '/cases/precedents/api/ingest',
                json={'url': 'https://example.com/case', 'world_id': 1},
                content_type='application/json'
            )
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            instance.ingest_from_url.assert_called_once_with(
                'https://example.com/case', world_id=1
            )

    def test_ingest_batch(self, client, app_context):
        """Ingest API handles batch ingestion when no URL specified."""
        with patch(
            'app.services.precedent.cited_case_ingestor.CitedCaseIngestor'
        ) as MockIngestor:
            instance = MockIngestor.return_value
            instance.ingest_missing_urls.return_value = {
                'success': True,
                'ingested': 3,
                'failed': 0
            }

            response = client.post(
                '/cases/precedents/api/ingest',
                json={'max_cases': 5},
                content_type='application/json'
            )
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            instance.ingest_missing_urls.assert_called_once_with(
                max_cases=5, world_id=1
            )


# --- Tests for helper functions ---

class TestHelperFunctions:
    """Tests for internal helper functions in precedents module."""

    def test_get_primary_method_highest_score(self, app_context):
        """_get_primary_method returns key with highest score."""
        from app.routes.precedents import _get_primary_method

        scores = {
            'facts_similarity': 0.3,
            'discussion_similarity': 0.8,
            'provision_overlap': 0.5
        }
        assert _get_primary_method(scores) == 'discussion_similarity'

    def test_get_primary_method_empty(self, app_context):
        """_get_primary_method returns default for empty scores."""
        from app.routes.precedents import _get_primary_method

        assert _get_primary_method({}) == 'provision_overlap'
        assert _get_primary_method(None) == 'provision_overlap'

    def test_count_outcomes(self, app_context):
        """_count_outcomes tallies outcome distribution."""
        from app.routes.precedents import _count_outcomes

        nodes = [
            {'outcome': 'ethical'},
            {'outcome': 'ethical'},
            {'outcome': 'unethical'},
            {'outcome': 'unknown'}
        ]
        result = _count_outcomes(nodes)
        assert result == {'ethical': 2, 'unethical': 1, 'unknown': 1}

    def test_get_case_year_from_metadata(self, app_context):
        """_get_case_year extracts year from doc_metadata."""
        from app.routes.precedents import _get_case_year

        mock_case = MagicMock()
        mock_case.doc_metadata = {'year': '2023'}
        assert _get_case_year(mock_case) == '2023'

    def test_get_case_year_from_date_parts(self, app_context):
        """_get_case_year falls back to date_parts."""
        from app.routes.precedents import _get_case_year

        mock_case = MagicMock()
        mock_case.doc_metadata = {'date_parts': {'year': '2024'}}
        assert _get_case_year(mock_case) == '2024'

    def test_get_case_year_no_metadata(self, app_context):
        """_get_case_year returns empty string when no metadata."""
        from app.routes.precedents import _get_case_year

        mock_case = MagicMock()
        mock_case.doc_metadata = None
        assert _get_case_year(mock_case) == ''
