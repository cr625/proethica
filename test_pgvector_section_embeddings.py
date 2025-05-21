"""
Test pgvector section embeddings implementation.

This test verifies the new DocumentSection model, migration scripts,
and updated SectionEmbeddingService functions for storing and retrieving
section embeddings using pgvector.
"""

import os
import sys
import unittest
import json
import logging
from datetime import datetime
from flask import Flask

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to the path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

class TestPgvectorSectionEmbeddings(unittest.TestCase):
    """Test case for pgvector section embeddings implementation."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        import os
        import sys
        from flask import Flask
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker, scoped_session
        from app.models import db
        
        # Import the mock User model first to satisfy dependencies
        from app.models.mock_user import User
        
        # Create a minimal Flask app without loading all routes
        app = Flask(__name__)
        app.config.from_object('app.config.DevelopmentConfig')
        
        # Configure the app
        db.init_app(app)
        cls.app = app
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        
        # Check if the document_sections table exists
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        if 'document_sections' not in inspector.get_table_names():
            logger.info("Running migration to create document_sections table")
            # Run migration script
            import migration_document_sections
            migration_document_sections.run_migration()
        
        # Import models
        from app.models.document import Document
        from app.models.document_section import DocumentSection
        from app.services.section_embedding_service import SectionEmbeddingService
        
        cls.Document = Document
        cls.DocumentSection = DocumentSection
        cls.SectionEmbeddingService = SectionEmbeddingService
        cls.db = db
        
        # Create test document
        cls.create_test_document()
    
    @classmethod
    def tearDownClass(cls):
        """Tear down test fixtures."""
        # Clean up test data
        cls.cleanup_test_data()
        
        # Remove app context
        cls.app_context.pop()
    
    @classmethod
    def create_test_document(cls):
        """Create a test document with sections for testing."""
        # Create a test document
        test_doc = cls.Document(
            title="Test Case for pgvector Embeddings",
            document_type="case_study",
            world_id=1,  # Assuming default world
            source="test",
            processing_status="completed"
        )
        
        # Add sections to document metadata
        test_doc.doc_metadata = {
            "sections": {
                "facts": "This is a test case about ethical engineering decisions in a software project.",
                "discussion": "The discussion centers around data privacy and user consent.",
                "conclusion": "Engineers should prioritize user privacy and informed consent."
            },
            "document_structure": {
                "document_uri": f"http://proethica.org/document/test_case",
                "sections": {
                    "facts": {
                        "type": "facts",
                        "content": "This is a test case about ethical engineering decisions in a software project."
                    },
                    "discussion": {
                        "type": "discussion",
                        "content": "The discussion centers around data privacy and user consent."
                    },
                    "conclusion": {
                        "type": "conclusion",
                        "content": "Engineers should prioritize user privacy and informed consent."
                    }
                }
            }
        }
        
        # Save document
        cls.db.session.add(test_doc)
        cls.db.session.commit()
        
        # Store document ID for later use
        cls.test_document_id = test_doc.id
        logger.info(f"Created test document with ID: {cls.test_document_id}")
    
    @classmethod
    def cleanup_test_data(cls):
        """Clean up test data after tests."""
        # Delete test document sections
        cls.DocumentSection.query.filter_by(document_id=cls.test_document_id).delete()
        
        # Delete test document
        test_doc = cls.Document.query.get(cls.test_document_id)
        if test_doc:
            cls.db.session.delete(test_doc)
            cls.db.session.commit()
            logger.info(f"Deleted test document with ID: {cls.test_document_id}")
    
    def test_01_create_document_section(self):
        """Test creating a document section with an embedding."""
        # Create a test section
        embedding = [0.1] * 1536  # Create a 1536-dimension embedding to match the table definition
        embedding_str = f"[{','.join(str(x) for x in embedding)}]"
        section = self.DocumentSection(
            document_id=self.test_document_id,
            section_id="test_section",
            section_type="test",
            content="This is a test section for pgvector embeddings.",
            embedding=embedding_str,
            section_metadata={"test_key": "test_value"}
        )
        
        # Save section
        self.db.session.add(section)
        self.db.session.commit()
        
        # Verify section was saved
        saved_section = self.DocumentSection.query.filter_by(
            document_id=self.test_document_id,
            section_id="test_section"
        ).first()
        
        self.assertIsNotNone(saved_section)
        self.assertEqual(saved_section.section_type, "test")
        self.assertEqual(saved_section.content, "This is a test section for pgvector embeddings.")
        # Verify the embedding was stored properly as a string
        self.assertIsNotNone(saved_section.embedding)
        self.assertTrue(saved_section.embedding.startswith('['))
        self.assertTrue(saved_section.embedding.endswith(']'))
        self.assertTrue('0.1' in saved_section.embedding)
        self.assertTrue('0.5' in saved_section.embedding)
        self.assertEqual(saved_section.section_metadata["test_key"], "test_value")
    
    def test_02_section_embedding_service_store(self):
        """Test storing section embeddings using SectionEmbeddingService."""
        # Initialize service
        service = self.SectionEmbeddingService()
        
        # Create test embeddings
        section_embeddings = {
            f"http://proethica.org/document/case_{self.test_document_id}/facts": [0.1] * 1536,
            f"http://proethica.org/document/case_{self.test_document_id}/discussion": [0.2] * 1536,
            f"http://proethica.org/document/case_{self.test_document_id}/conclusion": [0.3] * 1536
        }
        
        # Store embeddings
        result = service.store_section_embeddings(self.test_document_id, section_embeddings)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['sections_embedded'], 3)
        
        # Verify sections were saved
        sections = self.DocumentSection.query.filter_by(document_id=self.test_document_id).all()
        self.assertEqual(len(sections), 4)  # 3 + 1 from previous test
        
        # Verify document metadata was updated
        document = self.Document.query.get(self.test_document_id)
        self.assertIn('document_structure', document.doc_metadata)
        self.assertIn('section_embeddings', document.doc_metadata['document_structure'])
        self.assertEqual(document.doc_metadata['document_structure']['section_embeddings']['count'], 3)
        self.assertEqual(document.doc_metadata['document_structure']['section_embeddings']['storage_type'], 'pgvector')
    
    def test_03_section_embedding_service_process(self):
        """Test processing document sections with SectionEmbeddingService."""
        # Initialize service with mock embedding function
        service = self.SectionEmbeddingService()
        
        # Store the original get_embedding function
        original_get_embedding = service.get_embedding
        
        # Replace with a mock function that returns a fixed-size embedding with 1536 dimensions to match the vector schema
        def mock_get_embedding(text):
            return [0.5] * 1536
        
        service.get_embedding = mock_get_embedding
        
        # Process the document
        result = service.process_document_sections(self.test_document_id)
        
        # Restore the original function
        service.get_embedding = original_get_embedding
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertGreaterEqual(result['sections_embedded'], 3)
        
        # Check document sections
        sections = self.DocumentSection.query.filter_by(document_id=self.test_document_id).all()
        self.assertGreaterEqual(len(sections), 3)
    
    def test_04_section_embedding_service_find_similar(self):
        """Test finding similar sections using SectionEmbeddingService."""
        # Initialize service with mock embedding function
        service = self.SectionEmbeddingService()
        
        # Store the original get_embedding function
        original_get_embedding = service.get_embedding
        
        # Replace with a mock function that returns a fixed-size embedding with the correct dimensions
        def mock_get_embedding(text):
            return [0.5] * 1536
        
        service.get_embedding = mock_get_embedding
        
        # Search for similar sections
        results = service.find_similar_sections(
            query_text="Test query about engineering ethics",
            limit=10
        )
        
        # Restore the original function
        service.get_embedding = original_get_embedding
        
        # Verify results
        self.assertIsInstance(results, list)
        self.assertGreaterEqual(len(results), 1)
        
        # Check result structure
        if results:
            result = results[0]
            self.assertIn('document_id', result)
            self.assertIn('document_title', result)
            self.assertIn('section_id', result)
            self.assertIn('section_type', result)
            self.assertIn('similarity', result)
            self.assertIn('content', result)
            
            # Verify similarity score is between 0 and 1
            self.assertGreaterEqual(result['similarity'], 0.0)
            self.assertLessEqual(result['similarity'], 1.0)
    
    def test_05_migration_script(self):
        """Test the migration script to create document_sections table."""
        # Run migration
        import migration_document_sections
        
        # This should not raise any exceptions if the table already exists
        migration_document_sections.run_migration()
        
        # Verify table exists
        from sqlalchemy import inspect
        inspector = inspect(self.db.engine)
        self.assertIn('document_sections', inspector.get_table_names())
        
        # Check columns
        columns = {col['name'] for col in inspector.get_columns('document_sections')}
        expected_columns = {
            'id', 'document_id', 'section_id', 'section_type', 'position',
            'content', 'embedding', 'section_metadata', 'created_at', 'updated_at'
        }
        self.assertTrue(expected_columns.issubset(columns))
    
    def test_06_migrate_section_data(self):
        """Test migrating section data from document metadata to DocumentSection model."""
        # Run migration script
        import migrate_section_data
        
        # This will process all documents, including our test document
        migrate_section_data.run_migration()
        
        # Verify sections for our test document
        sections = self.DocumentSection.query.filter_by(document_id=self.test_document_id).all()
        self.assertGreaterEqual(len(sections), 3)
        
        # Verify document metadata was updated
        document = self.Document.query.get(self.test_document_id)
        self.assertIn('document_structure', document.doc_metadata)
        self.assertIn('section_embeddings', document.doc_metadata['document_structure'])
        self.assertIn('storage_type', document.doc_metadata['document_structure']['section_embeddings'])
        self.assertEqual(document.doc_metadata['document_structure']['section_embeddings']['storage_type'], 'pgvector')

if __name__ == '__main__':
    unittest.main()
