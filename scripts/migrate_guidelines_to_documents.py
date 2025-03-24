#!/usr/bin/env python
"""
Migration script to move guidelines from World model to Document model.
This script:
1. Creates Document records for existing guidelines_text and guidelines_url
2. Associates these Document records with their respective worlds
3. Prepares for removing the guidelines_url and guidelines_text fields from the World model
"""

import os
import sys
from datetime import datetime

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.world import World
from app.models.document import Document
from app.services.embedding_service import EmbeddingService

def migrate_guidelines():
    """Migrate guidelines from World model to Document model."""
    app = create_app()
    
    with app.app_context():
        print("Starting migration of guidelines to Document model...")
        
        # Get all worlds
        worlds = World.query.all()
        print(f"Found {len(worlds)} worlds to process")
        
        # Initialize embedding service
        embedding_service = EmbeddingService()
        
        # Process each world
        for world in worlds:
            print(f"Processing world: {world.name} (ID: {world.id})")
            
            # Check if world has guidelines_text attribute
            if hasattr(world, 'guidelines_text') and world.guidelines_text and world.guidelines_text.strip():
                print(f"  - Found guidelines_text for world {world.id}")
                
                # Create a Document record for the guidelines_text
                document = Document(
                    title=f"Guidelines for {world.name}",
                    document_type="guideline",
                    world_id=world.id,
                    content=world.guidelines_text,
                    file_type="txt",
                    doc_metadata={"source": "migrated_from_guidelines_text"}
                )
                db.session.add(document)
                db.session.flush()  # Get document ID
                
                print(f"  - Created Document record with ID {document.id} for guidelines_text")
                
                # Create chunks and embeddings for the document
                try:
                    # Create chunks and embeddings
                    chunks = embedding_service._split_text(world.guidelines_text)
                    embeddings = embedding_service.embed_documents(chunks)
                    embedding_service._store_chunks(document.id, chunks, embeddings)
                    print(f"  - Created {len(chunks)} chunks with embeddings for document {document.id}")
                except Exception as e:
                    print(f"  - Error creating embeddings for document {document.id}: {str(e)}")
            else:
                print(f"  - No guidelines_text found for world {world.id}")
            
            # Check if world has guidelines_url attribute
            if hasattr(world, 'guidelines_url') and world.guidelines_url and world.guidelines_url.strip():
                print(f"  - Found guidelines_url for world {world.id}: {world.guidelines_url}")
                
                try:
                    # Process the URL using the embedding service
                    document_id = embedding_service.process_url(
                        world.guidelines_url,
                        f"Guidelines URL for {world.name}",
                        "guideline",
                        world.id
                    )
                    print(f"  - Processed URL and created Document record with ID {document_id}")
                except Exception as e:
                    print(f"  - Error processing URL {world.guidelines_url}: {str(e)}")
                    
                    # Create a Document record for the URL without processing
                    document = Document(
                        title=f"Guidelines URL for {world.name}",
                        document_type="guideline",
                        world_id=world.id,
                        source=world.guidelines_url,
                        file_type="url",
                        doc_metadata={"source": "migrated_from_guidelines_url"}
                    )
                    db.session.add(document)
                    print(f"  - Created Document record for URL without processing")
            else:
                print(f"  - No guidelines_url found for world {world.id}")
        
        # Commit all changes
        db.session.commit()
        print("Migration completed successfully")

if __name__ == "__main__":
    migrate_guidelines()
