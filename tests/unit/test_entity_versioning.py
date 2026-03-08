"""
Unit tests for entity versioning and Shepard's signal infrastructure.

Tests content hash contract, CaseOntologyCommit model, and
hash consistency between ProEthica and OntServe.
"""

import hashlib
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
