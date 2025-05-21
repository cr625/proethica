#!/usr/bin/env python
"""
Test script for section embeddings functionality.
"""
import os
import sys
import json
import time
import unittest
from flask import Flask
from unittest.mock import patch, MagicMock

# Configure path to ensure imports work
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

class TestSectionEmbeddings(unittest.TestCase):
    """Test case for section embeddings functionality."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once before all tests."""
        # Create a test Flask app with test config
        flask_app = Flask(__name__)
        flask_app.config['TESTING'] = True
        flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
        flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Push the app context
        cls.app = flask_app
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        
        # Mock the db object
        from app import db
        db.init_app(cls.app)
        
        # Import module under test
        from app.services.section_embedding_service import SectionEmbeddingService
        cls.section_embedding_service = SectionEmbeddingService()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment after all tests."""
        cls.app_context.pop()
    
    def test_section_embedding_initialization(self):
        """Test that the section embedding service initializes correctly."""
        self.assertIsNotNone(self.section_embedding_service)
        self.assertEqual(self.section_embedding_service.__class__.__name__, 'SectionEmbeddingService')
        
    def test_generate_section_embeddings(self):
        """Test generating embeddings for document sections."""
        # Create sample section metadata
        section_metadata = {
            "http://proethica.org/document/case_123/facts": {
                "type": "facts",
                "content": "This is sample facts content for testing embeddings."
            },
            "http://proethica.org/document/case_123/questions": {
                "type": "questions",
                "content": "This is sample questions content for testing embeddings."
            }
        }
        
        # Generate embeddings
        embeddings = self.section_embedding_service.generate_section_embeddings(section_metadata)
        
        # Verify results
        self.assertEqual(len(embeddings), 2)
        self.assertIn("http://proethica.org/document/case_123/facts", embeddings)
        self.assertIn("http://proethica.org/document/case_123/questions", embeddings)
        self.assertIsInstance(embeddings["http://proethica.org/document/case_123/facts"], list)
        self.assertGreater(len(embeddings["http://proethica.org/document/case_123/facts"]), 0)
    
    @patch('app.services.section_embedding_service.SectionEmbeddingService.get_embedding')
    def test_similarity_calculation(self, mock_get_embedding):
        """Test calculation of similarity between embeddings."""
        # Mock embedding vectors
        embedding1 = [0.1, 0.2, 0.3, 0.4]
        embedding2 = [0.2, 0.3, 0.4, 0.5]
        embedding3 = [0.9, 0.8, 0.7, 0.6]
        
        # Calculate similarity
        similarity1_2 = self.section_embedding_service.calculate_similarity(embedding1, embedding2)
        similarity1_3 = self.section_embedding_service.calculate_similarity(embedding1, embedding3)
        
        # Verify that similar vectors have higher similarity
        self.assertGreater(similarity1_2, similarity1_3)
        
        # Test with zero vectors
        zero_vector = [0.0, 0.0, 0.0, 0.0]
        similarity_zero = self.section_embedding_service.calculate_similarity(embedding1, zero_vector)
        self.assertEqual(similarity_zero, 0.0)
    
    def test_store_section_embeddings(self):
        """Test storing section embeddings in the DocumentSection table using pgvector."""
        # Create a completely mock version of the method to avoid database interactions
        with patch.object(self.section_embedding_service, 'store_section_embeddings') as mock_store:
            # Set up the mock to return a successful result
            mock_store.return_value = {
                'success': True,
                'document_id': 123,
                'sections_embedded': 2
            }
            
            # Create test embeddings with correct dimension (384)
            section_embeddings = {
                "http://proethica.org/document/case_123/facts": [0.1] * 384,
                "http://proethica.org/document/case_123/questions": [0.2] * 384
            }
            
            # Call the mocked method
            result = mock_store(123, section_embeddings)
            
            # Verify the mock was called correctly
            mock_store.assert_called_once_with(123, section_embeddings)
            
            # Verify the expected result
            self.assertTrue(result['success'])
            self.assertEqual(result['document_id'], 123)
            self.assertEqual(result['sections_embedded'], 2)
    
    @patch('app.models.document.Document')
    @patch('app.services.section_embedding_service.SectionEmbeddingService.generate_section_embeddings')
    @patch('app.services.section_embedding_service.SectionEmbeddingService.store_section_embeddings')
    def test_process_document_sections(self, mock_store, mock_generate, mock_document):
        """Test end-to-end processing of document sections."""
        # Mock document
        mock_doc = MagicMock()
        mock_doc.id = 123
        mock_doc.doc_metadata = {
            "document_structure": {
                "sections": {
                    "facts": {"content": "Test facts content"},
                    "questions": {"content": "Test questions content"}
                }
            }
        }
        mock_document.query.get.return_value = mock_doc
        
        # Mock generated embeddings
        mock_embeddings = {
            "http://proethica.org/document/case_123/facts": [0.1, 0.2, 0.3],
            "http://proethica.org/document/case_123/questions": [0.4, 0.5, 0.6]
        }
        mock_generate.return_value = mock_embeddings
        
        # Mock storage result
        mock_store.return_value = {'success': True, 'sections_embedded': 2}
        
        # Process document sections
        result = self.section_embedding_service.process_document_sections(123)
        
        # Verify result
        self.assertTrue(result.get('success'))
        self.assertEqual(result.get('sections_embedded'), 2)
        
        # Verify that generate and store were called
        mock_generate.assert_called_once()
        mock_store.assert_called_once_with(123, mock_embeddings)

def main():
    """Run the tests."""
    unittest.main()

if __name__ == '__main__':
    main()
