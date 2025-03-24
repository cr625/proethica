#!/usr/bin/env python
"""
Script to test the embedding service functionality.
This script creates a test document, processes it, and performs a similarity search.
"""

import os
import sys
import json
from datetime import datetime

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.document import Document, DocumentChunk
from app.services.embedding_service import EmbeddingService

def create_test_document():
    """Create a test document for embedding."""
    app = create_app()
    
    with app.app_context():
        # Create a test text file
        test_file_path = os.path.join(os.path.dirname(__file__), 'test_document.txt')
        with open(test_file_path, 'w') as f:
            f.write("""
            # Test Document for Embedding Service
            
            This is a test document to verify that the embedding service is working correctly.
            
            ## Features to Test
            
            1. Text extraction from files
            2. Chunking of text
            3. Embedding generation
            4. Similarity search
            
            The embedding service should be able to process this document, generate embeddings,
            and then find this paragraph when searching for terms like "embedding" or "similarity".
            """)
        
        # Create document record
        document = Document(
            title="Test Document",
            document_type="test",
            file_path=test_file_path,
            file_type="txt",
            doc_metadata={"test": True}
        )
        
        db.session.add(document)
        db.session.commit()
        
        print(f"Created test document with ID: {document.id}")
        
        # Process the document
        embedding_service = EmbeddingService()
        embedding_service.process_document(document.id)
        
        print("Document processed successfully")
        
        # Test similarity search
        results = embedding_service.search_similar_chunks("embedding similarity search", k=2)
        
        print("\nSimilarity Search Results:")
        for i, result in enumerate(results):
            print(f"\nResult {i+1}:")
            print(f"Text: {result['chunk_text'][:100]}...")
            print(f"Distance: {result['distance']}")
        
        # Clean up
        os.remove(test_file_path)
        print("\nTest completed and test file removed")

if __name__ == "__main__":
    create_test_document()
