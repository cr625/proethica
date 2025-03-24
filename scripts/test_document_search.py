#!/usr/bin/env python
"""
Script to test the document search functionality.
This script creates a test document, processes it, and performs a search.
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

def test_document_search():
    """Test the document search functionality."""
    app = create_app()
    
    with app.app_context():
        # Create a test text file
        test_file_path = os.path.join(os.path.dirname(__file__), 'test_document.txt')
        with open(test_file_path, 'w') as f:
            f.write("""
            # Test Document for Search Testing
            
            This is a test document to verify that the document search functionality is working correctly.
            
            ## Topics Covered
            
            1. Ethical dilemmas in healthcare
            2. Patient autonomy and informed consent
            3. Resource allocation in limited settings
            4. End-of-life care decisions
            
            Healthcare professionals often face ethical dilemmas when patient autonomy conflicts with 
            beneficence or non-maleficence. For example, a patient may refuse life-saving treatment 
            based on religious beliefs, creating a conflict between respecting autonomy and the 
            healthcare provider's duty to prevent harm.
            
            Resource allocation presents another ethical challenge, especially in settings with limited 
            resources. How should scarce medical resources be distributed? Should priority be given based 
            on severity of condition, likelihood of recovery, age, or other factors?
            
            End-of-life care decisions involve complex ethical considerations around quality of life, 
            dignity in dying, and the appropriate use of life-sustaining treatments. These decisions 
            often involve multiple stakeholders including patients, families, and healthcare providers.
            """)
        
        # Create document record
        document = Document(
            title="Healthcare Ethics Test Document",
            document_type="test",
            file_path=test_file_path,
            file_type="txt",
            doc_metadata={"test": True, "domain": "healthcare"}
        )
        
        db.session.add(document)
        db.session.commit()
        
        print(f"Created test document with ID: {document.id}")
        
        # Process the document
        embedding_service = EmbeddingService()
        embedding_service.process_document(document.id)
        
        print("Document processed successfully")
        
        # Test searches with different queries
        search_queries = [
            "ethical dilemmas in healthcare",
            "patient autonomy",
            "resource allocation",
            "end-of-life care"
        ]
        
        for query in search_queries:
            print(f"\nSearching for: '{query}'")
            results = embedding_service.search_similar_chunks(query, k=1)
            
            if results:
                print(f"Found {len(results)} results")
                for i, result in enumerate(results):
                    print(f"\nResult {i+1}:")
                    print(f"Text: {result['chunk_text'][:150]}...")
                    print(f"Distance: {result['distance']}")
            else:
                print("No results found")
        
        # Clean up
        os.remove(test_file_path)
        print("\nTest completed and test file removed")

if __name__ == "__main__":
    test_document_search()
