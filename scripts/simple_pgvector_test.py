#!/usr/bin/env python
"""
Simple script to test pgvector functionality.
This script creates a small test document and verifies that pgvector is working.
"""

import os
import sys
import numpy as np

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.document import Document, DocumentChunk
from sqlalchemy import text

def test_pgvector():
    """Test pgvector functionality."""
    app = create_app()
    
    with app.app_context():
        # Check if pgvector extension is enabled
        result = db.session.execute(text("SELECT * FROM pg_extension WHERE extname = 'vector'"))
        if result.rowcount == 0:
            print("pgvector extension is not enabled")
            return
        
        print("pgvector extension is enabled")
        
        # Create a test document
        document = Document(
            title="PGVector Test Document",
            document_type="test",
            file_path="test_path",
            file_type="txt",
            content="This is a test document for pgvector",
            doc_metadata={"test": True}
        )
        
        db.session.add(document)
        db.session.flush()  # Get document ID
        
        print(f"Created test document with ID: {document.id}")
        
        # Create a test embedding
        embedding = np.random.rand(384).tolist()  # 384 is the dimension of the all-MiniLM-L6-v2 model
        
        # Create a document chunk with the embedding
        chunk = DocumentChunk(
            document_id=document.id,
            chunk_index=0,
            chunk_text="This is a test chunk",
            embedding=embedding,
            chunk_metadata={"index": 0}
        )
        
        db.session.add(chunk)
        db.session.commit()
        
        print("Created document chunk with embedding")
        
        # Test querying with the embedding
        # Convert the embedding to a string for proper casting
        embedding_str = f"[{','.join(str(x) for x in embedding)}]"
        
        query = f"""
        SELECT 
            dc.id,
            dc.chunk_text,
            dc.embedding <-> '{embedding_str}'::vector AS distance
        FROM 
            document_chunks dc
        WHERE 
            dc.document_id = {document.id}
        ORDER BY 
            distance
        LIMIT 1
        """
        
        result = db.session.execute(text(query))
        
        for row in result:
            print(f"Found chunk: {row.chunk_text}")
            print(f"Distance: {row.distance}")
        
        # Clean up
        db.session.delete(document)
        db.session.commit()
        
        print("Test completed successfully")

if __name__ == "__main__":
    test_pgvector()
