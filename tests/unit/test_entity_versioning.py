"""
Unit tests for entity versioning and change detection.

Tests content hash contract, CaseOntologyCommit model,
hash consistency between ProEthica and OntServe,
and the entity change detector logic.
"""

import hashlib
from unittest.mock import patch, MagicMock
import pytest

from app.models import db
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.models.case_ontology_commit import CaseOntologyCommit
from app.models.document import Document
from app.models.world import World


@pytest.fixture
def case_with_entities(app):
    """Create a test case with published and draft entities."""
    with app.app_context():
        world = World(name="Test World", description="test", metadata={})
        db.session.add(world)
        db.session.flush()
        doc = Document(title="Test Case", document_type="case", world_id=world.id)
        db.session.add(doc)
        db.session.commit()

        # Published class entity
        published_class = TemporaryRDFStorage(
            case_id=doc.id,
            extraction_session_id="test-session",
            extraction_type="roles",
            storage_type="class",
            ontology_target="proethica-intermediate",
            entity_label="Professional Engineer Role",
            entity_uri="http://proethica.org/ontology/intermediate#ProfessionalEngineerRole",
            entity_definition="A licensed professional engineer",
            is_selected=True,
            is_reviewed=True,
            is_published=True,
            content_hash=TemporaryRDFStorage.compute_content_hash(
                "http://proethica.org/ontology/intermediate#ProfessionalEngineerRole",
                "Professional Engineer Role",
                "A licensed professional engineer"
            ),
            extraction_model="claude-sonnet-4-6",
        )

        # Published individual entity
        published_indiv = TemporaryRDFStorage(
            case_id=doc.id,
            extraction_session_id="test-session",
            extraction_type="roles",
            storage_type="individual",
            ontology_target=f"proethica-case-{doc.id}",
            entity_label="Engineer A",
            entity_uri=f"http://proethica.org/ontology/case/{doc.id}#Engineer_A",
            entity_definition="The primary engineer in the case",
            is_selected=True,
            is_reviewed=True,
            is_published=True,
            content_hash=TemporaryRDFStorage.compute_content_hash(
                f"http://proethica.org/ontology/case/{doc.id}#Engineer_A",
                "Engineer A",
                "The primary engineer in the case"
            ),
        )

        # Draft entity (not committed)
        draft = TemporaryRDFStorage(
            case_id=doc.id,
            extraction_session_id="test-session",
            extraction_type="principles",
            storage_type="class",
            ontology_target="proethica-intermediate",
            entity_label="Draft Principle",
            entity_uri="http://proethica.org/ontology/intermediate#DraftPrinciple",
            entity_definition="A draft principle not yet committed",
            is_selected=True,
            is_reviewed=False,
            is_published=False,
        )

        db.session.add_all([published_class, published_indiv, draft])
        db.session.commit()

        yield {
            'case': doc,
            'published_class': published_class,
            'published_indiv': published_indiv,
            'draft': draft,
        }


class TestContentHash:
    """Test content hash computation on TemporaryRDFStorage."""

    def test_hash_deterministic(self):
        h1 = TemporaryRDFStorage.compute_content_hash(
            'http://test.org#A', 'Label', 'Definition'
        )
        h2 = TemporaryRDFStorage.compute_content_hash(
            'http://test.org#A', 'Label', 'Definition'
        )
        assert h1 == h2

    def test_hash_is_sha256(self):
        uri = 'http://test.org#A'
        label = 'TestLabel'
        defn = 'TestDefinition'

        expected = hashlib.sha256(
            f"{uri}|{label}|{defn}".encode('utf-8')
        ).hexdigest()
        actual = TemporaryRDFStorage.compute_content_hash(uri, label, defn)
        assert actual == expected
        assert len(actual) == 64

    def test_hash_handles_none(self):
        h = TemporaryRDFStorage.compute_content_hash('http://test.org#A', None, None)
        expected = hashlib.sha256(
            'http://test.org#A||'.encode('utf-8')
        ).hexdigest()
        assert h == expected

    def test_hash_changes_with_definition(self):
        h1 = TemporaryRDFStorage.compute_content_hash('http://test.org#A', 'L', 'Def1')
        h2 = TemporaryRDFStorage.compute_content_hash('http://test.org#A', 'L', 'Def2')
        assert h1 != h2


class TestHashContractWithOntServe:
    """Verify ProEthica hash matches OntServe hash computation.

    The hash contract is critical: ProEthica uses 'definition' parameter name,
    OntServe uses 'comment', but both must produce identical output.
    """

    def test_hash_matches_ontserve_formula(self):
        """ProEthica hash == sha256(uri|label|definition) == OntServe sha256(uri|label|comment)."""
        uri = 'http://proethica.org/ontology/intermediate#TestEntity'
        label = 'Test Entity'
        text = 'A test entity for hash verification'

        # ProEthica side
        proethica_hash = TemporaryRDFStorage.compute_content_hash(uri, label, text)

        # OntServe side (simulated -- same formula, different param name)
        raw = f"{uri}|{label or ''}|{text or ''}"
        ontserve_hash = hashlib.sha256(raw.encode('utf-8')).hexdigest()

        assert proethica_hash == ontserve_hash

    def test_hash_with_unicode(self):
        """Hash handles unicode characters consistently."""
        uri = 'http://test.org#Entity'
        label = 'Responsabilit\u00e9'
        defn = 'Principle d\u2019\u00e9thique'

        h = TemporaryRDFStorage.compute_content_hash(uri, label, defn)
        assert len(h) == 64

        # Verify matches raw computation
        raw = f"{uri}|{label}|{defn}"
        expected = hashlib.sha256(raw.encode('utf-8')).hexdigest()
        assert h == expected


class TestCaseOntologyCommit:
    """Test the CaseOntologyCommit model."""

    def test_create_commit_record(self, app):
        with app.app_context():
            world = World(name="Commit World", description="test", metadata={})
            db.session.add(world)
            db.session.flush()
            doc = Document(title="Commit Case", document_type="case", world_id=world.id)
            db.session.add(doc)
            db.session.commit()

            commit = CaseOntologyCommit(
                case_id=doc.id,
                ontology_name='proethica-intermediate',
                ontserve_version_id=42,
                version_tag='v1.0.0',
                entity_count=15
            )
            db.session.add(commit)
            db.session.commit()

            result = CaseOntologyCommit.query.filter_by(case_id=doc.id).first()
            assert result is not None
            assert result.ontology_name == 'proethica-intermediate'
            assert result.ontserve_version_id == 42
            assert result.version_tag == 'v1.0.0'
            assert result.entity_count == 15
            assert result.committed_at is not None

    def test_commit_relates_to_case(self, app):
        with app.app_context():
            world = World(name="Rel World", description="test", metadata={})
            db.session.add(world)
            db.session.flush()
            doc = Document(title="Rel Case", document_type="case", world_id=world.id)
            db.session.add(doc)
            db.session.commit()

            commit = CaseOntologyCommit(
                case_id=doc.id,
                ontology_name='proethica-case-99',
                entity_count=10
            )
            db.session.add(commit)
            db.session.commit()

            assert commit.case is not None
            assert commit.case.title == 'Rel Case'

    def test_multiple_commits_per_case(self, app):
        """A case can have commits to multiple ontologies."""
        with app.app_context():
            world = World(name="Multi World", description="test", metadata={})
            db.session.add(world)
            db.session.flush()
            doc = Document(title="Multi Case", document_type="case", world_id=world.id)
            db.session.add(doc)
            db.session.commit()

            for name in ['proethica-intermediate', f'proethica-case-{doc.id}']:
                commit = CaseOntologyCommit(
                    case_id=doc.id,
                    ontology_name=name,
                    entity_count=5
                )
                db.session.add(commit)
            db.session.commit()

            commits = CaseOntologyCommit.query.filter_by(case_id=doc.id).all()
            assert len(commits) == 2


class TestPublishedEntityFields:
    """Test versioning fields on published entities."""

    def test_published_entity_has_content_hash(self, case_with_entities):
        entity = case_with_entities['published_class']
        assert entity.content_hash is not None
        assert len(entity.content_hash) == 64

    def test_draft_entity_has_no_content_hash(self, case_with_entities):
        entity = case_with_entities['draft']
        assert entity.content_hash is None

    def test_uri_fragment_extraction(self, case_with_entities):
        """Verify URI fragment extraction logic used by templates."""
        entity = case_with_entities['published_class']
        uri = entity.entity_uri
        fragment = uri.split('#')[-1] if '#' in uri else uri.split('/')[-1]
        assert fragment == 'ProfessionalEngineerRole'

        entity2 = case_with_entities['published_indiv']
        uri2 = entity2.entity_uri
        fragment2 = uri2.split('#')[-1] if '#' in uri2 else uri2.split('/')[-1]
        assert fragment2 == 'Engineer_A'

    def test_ontology_target_set(self, case_with_entities):
        cls = case_with_entities['published_class']
        assert cls.ontology_target == 'proethica-intermediate'

        indiv = case_with_entities['published_indiv']
        assert indiv.ontology_target.startswith('proethica-case-')


class TestEntityChangeDetector:
    """Test entity change detection logic."""

    @patch('app.services.entity_change_detector.psycopg2')
    def test_detects_changed_entity(self, mock_psycopg2, case_with_entities):
        """Entity with different hash in OntServe is detected as changed."""
        from app.services.entity_change_detector import detect_changed_entities

        cls = case_with_entities['published_class']
        indiv = case_with_entities['published_indiv']
        case_id = case_with_entities['case'].id

        # OntServe returns different hash for the class, same for individual
        new_hash = hashlib.sha256(b'different content').hexdigest()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (cls.entity_uri, new_hash, 'Professional Engineer Role', 'Updated definition'),
            (indiv.entity_uri, indiv.content_hash, 'Engineer A', 'The primary engineer in the case'),
        ]
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        changed = detect_changed_entities(case_id)

        assert cls.entity_uri in changed
        assert changed[cls.entity_uri]['committed_hash'] == cls.content_hash
        assert changed[cls.entity_uri]['current_hash'] == new_hash
        assert indiv.entity_uri not in changed

    @patch('app.services.entity_change_detector.psycopg2')
    def test_no_changes_when_hashes_match(self, mock_psycopg2, case_with_entities):
        """No changes detected when all hashes match."""
        from app.services.entity_change_detector import detect_changed_entities

        cls = case_with_entities['published_class']
        indiv = case_with_entities['published_indiv']
        case_id = case_with_entities['case'].id

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (cls.entity_uri, cls.content_hash, 'Professional Engineer Role', 'A licensed professional engineer'),
            (indiv.entity_uri, indiv.content_hash, 'Engineer A', 'The primary engineer in the case'),
        ]
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        changed = detect_changed_entities(case_id)
        assert len(changed) == 0

    @patch('app.services.entity_change_detector.psycopg2')
    def test_missing_ontserve_entities_excluded(self, mock_psycopg2, case_with_entities):
        """Entities not found in OntServe are not reported as changed."""
        from app.services.entity_change_detector import detect_changed_entities

        case_id = case_with_entities['case'].id

        # OntServe returns empty -- entities not found
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        changed = detect_changed_entities(case_id)
        assert len(changed) == 0

    @patch('app.services.entity_change_detector.psycopg2')
    def test_db_connection_failure_returns_empty(self, mock_psycopg2, case_with_entities):
        """Connection failure returns empty dict, not an exception."""
        from app.services.entity_change_detector import detect_changed_entities
        import psycopg2 as real_psycopg2

        case_id = case_with_entities['case'].id
        mock_psycopg2.connect.side_effect = real_psycopg2.OperationalError("connection refused")
        mock_psycopg2.Error = real_psycopg2.Error

        changed = detect_changed_entities(case_id)
        assert changed == {}

    @patch('app.services.entity_change_detector.psycopg2')
    def test_get_changed_entity_uris_returns_set(self, mock_psycopg2, case_with_entities):
        """Convenience wrapper returns a set of URIs."""
        from app.services.entity_change_detector import get_changed_entity_uris

        cls = case_with_entities['published_class']
        indiv = case_with_entities['published_indiv']
        case_id = case_with_entities['case'].id

        new_hash = hashlib.sha256(b'different').hexdigest()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (cls.entity_uri, new_hash, 'Professional Engineer Role', 'Changed'),
            (indiv.entity_uri, indiv.content_hash, 'Engineer A', 'Same'),
        ]
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        uris = get_changed_entity_uris(case_id)
        assert isinstance(uris, set)
        assert cls.entity_uri in uris
        assert indiv.entity_uri not in uris

    def test_no_published_entities_returns_empty(self, app):
        """Case with no published entities returns empty dict."""
        from app.services.entity_change_detector import detect_changed_entities

        with app.app_context():
            world = World(name="Empty World", description="test", metadata={})
            db.session.add(world)
            db.session.flush()
            doc = Document(title="Empty Case", document_type="case", world_id=world.id)
            db.session.add(doc)
            db.session.commit()

            # No psycopg2 mock needed -- should return early
            changed = detect_changed_entities(doc.id)
            assert changed == {}
