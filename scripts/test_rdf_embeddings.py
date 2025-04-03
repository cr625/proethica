#!/usr/bin/env python
"""
Test script demonstrating the use of semantic embeddings with RDF triples.
This script combines the RDF triple store with pgvector for semantic search.
"""

import os
import sys
import time
import numpy as np
from pprint import pprint

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.character import Character
from app.models.triple import Triple
from app.services.rdf_service import RDFService
from app.services.embedding_service import EmbeddingService
from sqlalchemy import text

def setup_demo_data(app):
    """Set up demo data for embedding tests."""
    with app.app_context():
        print("Setting up demo data...")
        
        # Initialize services
        rdf_service = RDFService()
        embedding_service = EmbeddingService()
        
        # Find existing characters
        characters = Character.query.limit(5).all()
        
        if not characters:
            print("No characters found. Please run test_character_rdf_triples.py first.")
            return None, None, None
        
        # Convert characters to triples if not already done
        for character in characters:
            # Check if character already has triples
            existing_triples = rdf_service.find_triples(character_id=character.id)
            
            if not existing_triples:
                print(f"Converting character '{character.name}' to triples...")
                rdf_service.character_to_triples(character)
            else:
                print(f"Character '{character.name}' already has {len(existing_triples)} triples")
        
        # Get all triples for the demo
        all_triples = Triple.query.all()
        print(f"Found {len(all_triples)} total triples in database")
        
        return app, rdf_service, embedding_service

def generate_embeddings(app, embedding_service):
    """Generate embeddings for triples that don't have them."""
    with app.app_context():
        print("\nChecking for triples without embeddings...")
        
        query = db.session.execute(text("""
            SELECT COUNT(*) 
            FROM character_triples 
            WHERE subject_embedding IS NULL
        """))
        missing_count = query.scalar()
        
        if missing_count == 0:
            print("All triples already have embeddings")
            return
        
        print(f"Found {missing_count} triples without embeddings")
        
        # Update embeddings in batches
        total_updated = 0
        batch_size = 50
        
        while total_updated < missing_count:
            updated = embedding_service.batch_update_embeddings(limit=batch_size)
            total_updated += updated
            
            print(f"Updated {updated} triples in this batch, {total_updated}/{missing_count} total")
            
            # Break if we didn't update any in this batch
            if updated == 0:
                break
                
            # Small delay to prevent hammering the system
            time.sleep(0.5)
        
        print(f"Finished updating embeddings: {total_updated} triples updated")

def test_semantic_queries(app, rdf_service, embedding_service):
    """Test semantic queries against the triple store."""
    with app.app_context():
        print("\nTesting semantic queries...")
        
        # Example 1: Find triples related to "engineering ethics"
        print("\nFinding triples related to 'engineering ethics':")
        triples = embedding_service.find_similar_triples(
            text="engineering ethics", 
            field="subject", 
            limit=5
        )
        
        for i, triple in enumerate(triples):
            print(f"{i+1}. [{triple['similarity']:.4f}] {triple['subject']} -> {triple['predicate']} -> {triple['object']}")
        
        # Example 2: Find triples with predicates similar to "has professional responsibility"
        print("\nFinding triples with predicates similar to 'has professional responsibility':")
        triples = embedding_service.find_similar_triples(
            text="has professional responsibility",
            field="predicate",
            limit=5
        )
        
        for i, triple in enumerate(triples):
            print(f"{i+1}. [{triple['similarity']:.4f}] {triple['subject']} -> {triple['predicate']} -> {triple['object']}")
        
        # Example 3: Find objects similar to "public safety"
        print("\nFinding triples with objects similar to 'public safety':")
        triples = embedding_service.find_similar_triples(
            text="public safety",
            field="object",
            limit=5
        )
        
        for i, triple in enumerate(triples):
            print(f"{i+1}. [{triple['similarity']:.4f}] {triple['subject']} -> {triple['predicate']} -> {triple['object']}")
        
        # Example 4: Semantic query for engineering roles and responsibilities
        print("\nSemantic query for engineering roles and responsibilities:")
        query_embedding = embedding_service.get_embedding("Professional engineer responsibilities")
        
        # Convert the embedding to a string representation for SQL
        embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"
        
        # Complex query combining triple patterns with semantic similarity
        query = f"""
        WITH role_triples AS (
            SELECT 
                t.subject,
                t.object_literal
            FROM 
                character_triples t
            WHERE 
                t.predicate = '{str(rdf_service.namespaces['proethica'].hasRole)}'
                AND t.object_literal LIKE '%Engineer%'
        )
        SELECT 
            rt.subject,
            rt.object_literal as role,
            t.predicate,
            CASE 
                WHEN t.is_literal THEN t.object_literal 
                ELSE t.object_uri 
            END as object,
            t.object_embedding <-> '{embedding_str}'::vector AS distance
        FROM 
            role_triples rt
        JOIN 
            character_triples t ON rt.subject = t.subject
        WHERE 
            t.object_embedding IS NOT NULL
        ORDER BY 
            distance
        LIMIT 10
        """
        
        result = db.session.execute(text(query))
        
        print("\nResults from complex semantic query:")
        for i, row in enumerate(result):
            similarity = 1.0 - row.distance
            print(f"{i+1}. [{similarity:.4f}] {row.subject} ({row.role}) -> {row.predicate} -> {row.object}")

def main():
    """Run the RDF embeddings demonstration."""
    app = create_app()
    
    # Set up the demo data
    app, rdf_service, embedding_service = setup_demo_data(app)
    if not app:
        print("Setup failed. Exiting...")
        return
    
    # Generate embeddings for triples
    generate_embeddings(app, embedding_service)
    
    # Test semantic queries
    test_semantic_queries(app, rdf_service, embedding_service)
    
    print("\nRDF embeddings demonstration completed")

if __name__ == "__main__":
    main()
