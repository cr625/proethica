#!/usr/bin/env python
"""
Test script for the enhanced embedding service with multiple providers.
This script tests different embedding providers (local, Claude, OpenAI) and 
shows how to configure the priority order.
"""

import os
import sys
import time
import numpy as np
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_providers():
    """Test the embedding service with different provider priorities."""
    from app.services.embedding_service import EmbeddingService
    
    test_cases = [
        "This is a test embedding for the subject of a triple.",
        "hasProperty is a common predicate in RDF triples.",
        "Engineering ethics requires consideration of public safety.",
        "Professional engineers must adhere to a code of conduct.",
        "RDF triple storage enables semantic reasoning about character attributes."
    ]
    
    # Try different provider priorities
    priorities = [
        "local",
        "claude",
        "openai",
        "local,claude,openai",
        "claude,openai,local",
        "openai,claude,local"
    ]
    
    for priority in priorities:
        print(f"\n{'='*70}")
        print(f"Testing with provider priority: {priority}")
        print(f"{'='*70}")
        
        # Override the environment variable
        os.environ["EMBEDDING_PROVIDER_PRIORITY"] = priority
        
        # Initialize the embedding service
        service = EmbeddingService()
        
        # Print current settings
        print(f"Embedding dimension: {service.embedding_dimension}")
        
        for i, test_text in enumerate(test_cases):
            print(f"\nTest case {i+1}: '{test_text[:30]}...'")
            
            # Time the embedding generation
            start_time = time.time()
            try:
                embedding = service.get_embedding(test_text)
                elapsed_time = time.time() - start_time
                
                print(f"✓ Got embedding with dimension: {len(embedding)}")
                print(f"✓ Time taken: {elapsed_time:.3f} seconds")
                
                # Print first few values
                print(f"✓ Sample values: {embedding[:3]}...")
                
                # Calculate magnitude (should be close to 1.0 for normalized vectors)
                magnitude = np.linalg.norm(embedding)
                print(f"✓ Vector magnitude: {magnitude:.4f}")
                
            except Exception as e:
                print(f"✗ Error: {str(e)}")

def test_similarity():
    """Test embedding similarity measurements."""
    from app.services.embedding_service import EmbeddingService
    
    print(f"\n{'='*70}")
    print(f"Testing embedding similarity")
    print(f"{'='*70}")
    
    service = EmbeddingService()
    
    # Test similarity between related and unrelated concepts
    test_pairs = [
        # Related pairs (should have high similarity)
        ("engineering ethics", "professional responsibility"),
        ("safety considerations", "public welfare"),
        ("code of conduct", "professional standards"),
        
        # Unrelated pairs (should have lower similarity)
        ("engineering ethics", "restaurant menu"),
        ("bridge design", "fashion trends"),
        ("safety regulations", "movie reviews")
    ]
    
    for text1, text2 in test_pairs:
        print(f"\nComparing: '{text1}' vs '{text2}'")
        
        try:
            # Get embeddings
            embed1 = service.get_embedding(text1)
            embed2 = service.get_embedding(text2)
            
            # Convert to numpy arrays
            np_embed1 = np.array(embed1)
            np_embed2 = np.array(embed2)
            
            # Calculate cosine similarity
            dot_product = np.dot(np_embed1, np_embed2)
            norm1 = np.linalg.norm(np_embed1)
            norm2 = np.linalg.norm(np_embed2)
            
            similarity = dot_product / (norm1 * norm2)
            
            print(f"Cosine similarity: {similarity:.4f}")
            print(f"Interpretation: {'High similarity' if similarity > 0.7 else 'Medium similarity' if similarity > 0.3 else 'Low similarity'}")
            
        except Exception as e:
            print(f"✗ Error: {str(e)}")

def main():
    """Run embedding provider tests."""
    test_providers()
    test_similarity()
    print("\nEmbedding provider tests completed.")

if __name__ == "__main__":
    main()
