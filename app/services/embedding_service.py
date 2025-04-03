import os
import numpy as np
from typing import List, Dict, Any, Union, Optional
import requests
import json
from sqlalchemy import text

class EmbeddingService:
    """
    Service for generating and managing embeddings for RDF triples.
    Supports using local or remote embedding models with configurable provider priority.
    """
    
    def __init__(self, model_name=None, embedding_dimension=None):
        """
        Initialize the embedding service.
        
        Args:
            model_name: The name of the local embedding model to use (defaults to env var or 'all-MiniLM-L6-v2')
            embedding_dimension: The dimension of the embedding vectors (determined by model)
        """
        # Configuration from environment or default values
        self.model_name = model_name or os.environ.get("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        
        # Provider priority (configurable through environment)
        self.provider_priority = os.environ.get(
            "EMBEDDING_PROVIDER_PRIORITY", 
            "local,claude,openai"
        ).lower().split(',')
        
        # Model dimensions (these will be used if embeddings need to be generated from scratch)
        self.dimensions = {
            "local": embedding_dimension or 384,  # Default for all-MiniLM-L6-v2
            "claude": 1024,  # Claude embedding dimension
            "openai": 1536   # OpenAI ada-002 dimension
        }
        
        # Default dimension based on first provider in priority
        for provider in self.provider_priority:
            if provider in self.dimensions:
                self.embedding_dimension = self.dimensions[provider]
                break
        else:
            self.embedding_dimension = embedding_dimension or 384  # Fallback
        
        # Provider setup and validation
        self.providers = {}
        self._setup_providers()
    
    def _setup_providers(self):
        """Initialize and validate all configured providers."""
        # Local model setup
        if "local" in self.provider_priority:
            try:
                from sentence_transformers import SentenceTransformer
                self.providers["local"] = {
                    "model": SentenceTransformer(self.model_name),
                    "available": True,
                    "dimension": self.dimensions["local"]
                }
                print(f"Local embedding provider ready: {self.model_name}")
            except Exception as e:
                print(f"Local embedding provider unavailable: {str(e)}")
                self.providers["local"] = {"available": False}
        
        # Claude API setup
        if "claude" in self.provider_priority:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key and not api_key.startswith("your-") and len(api_key) > 20:
                self.providers["claude"] = {
                    "api_key": api_key,
                    "available": True,
                    "model": os.environ.get("CLAUDE_EMBEDDING_MODEL", "claude-3-embedding-3-0"),
                    "dimension": self.dimensions["claude"],
                    "api_base": os.environ.get("ANTHROPIC_API_BASE", "https://api.anthropic.com/v1")
                }
                print(f"Claude embedding provider ready: {self.providers['claude']['model']} (API key: {api_key[:5]}...{api_key[-4:]})")
            else:
                print(f"Claude embedding provider unavailable: Invalid API key [{api_key[:5] if api_key else 'None'}...]")
                self.providers["claude"] = {"available": False}
        
        # OpenAI API setup
        if "openai" in self.provider_priority:
            # Get API key from .env file - read the actual .env variable
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key and not api_key.startswith("your-") and len(api_key) > 20:
                self.providers["openai"] = {
                    "api_key": api_key,
                    "available": True,
                    "api_base": os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1"),
                    "model": os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002"),
                    "dimension": self.dimensions["openai"]
                }
                print(f"OpenAI embedding provider ready: {self.providers['openai']['model']} (API key: {api_key[:5]}...{api_key[-4:]})")
            else:
                print(f"OpenAI embedding provider unavailable: Invalid API key [{api_key[:5] if api_key else 'None'}...]")
                self.providers["openai"] = {"available": False}
                
    def get_embedding(self, text: str) -> List[float]:
        """
        Get an embedding for a text string using configured provider priority.
        
        Args:
            text: The text to embed
            
        Returns:
            A list of floats representing the embedding vector
        """
        if not text:
            # Return a zero vector if text is empty
            return [0.0] * self.embedding_dimension
        
        # Try each provider in priority order
        for provider in self.provider_priority:
            if provider not in self.providers or not self.providers[provider]["available"]:
                continue
                
            try:
                if provider == "local":
                    embedding = self._get_local_embedding(text)
                    self.embedding_dimension = len(embedding)  # Update dimension based on result
                    return embedding
                elif provider == "claude":
                    embedding = self._get_claude_embedding(text)
                    self.embedding_dimension = len(embedding)  # Update dimension based on result
                    return embedding
                elif provider == "openai":
                    embedding = self._get_openai_embedding(text)
                    self.embedding_dimension = len(embedding)  # Update dimension based on result
                    return embedding
            except Exception as e:
                print(f"Error using {provider} embeddings: {str(e)}")
                continue
        
        # Fallback to random if all providers fail
        print("Warning: All embedding providers failed. Using random embeddings.")
        return self._get_random_embedding()
    
    def _get_local_embedding(self, text: str) -> List[float]:
        """Get embedding from local sentence-transformers model."""
        embedding = self.providers["local"]["model"].encode(text)
        return embedding.tolist()

    def _get_claude_embedding(self, text: str) -> List[float]:
        """Get embedding from Claude API."""
        # Claude's API version for embeddings
        # Try the documented approach first (may change over time)
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.providers["claude"]["api_key"],
            "anthropic-version": "2023-06-01"  # API version may change
        }
        
        # Standard format for the request
        data = {
            "model": self.providers["claude"]["model"],
            "input": text
        }
        
        api_base = self.providers["claude"]["api_base"]
        
        # Try the v1 embeddings endpoint
        embeddings_endpoint = f"{api_base.rstrip('/')}/embeddings"
        
        try:
            print(f"Using Claude embeddings API: {embeddings_endpoint}")
            response = requests.post(
                embeddings_endpoint,
                headers=headers, 
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                # Check if the response has the expected structure
                if "embedding" in result:
                    return result["embedding"]
                elif "embeddings" in result and len(result["embeddings"]) > 0:
                    return result["embeddings"][0]
                else:
                    raise Exception(f"Unexpected response format: {result}")
                    
            # Try alternative API path if first attempt fails with 404
            elif response.status_code == 404:
                # Alternative v2 endpoint
                print("Original endpoint not found, trying alternative API version...")
                headers["anthropic-version"] = "2023-01-01"  # Try a different API version
                alt_endpoint = f"{api_base.rstrip('/')}/v1/embeddings"
                
                alt_response = requests.post(
                    alt_endpoint,
                    headers=headers, 
                    json=data
                )
                
                if alt_response.status_code == 200:
                    result = alt_response.json()
                    if "embedding" in result:
                        return result["embedding"]
                    elif "embeddings" in result and len(result["embeddings"]) > 0:
                        return result["embeddings"][0]
                
                # If that also fails, use the Claude completion API to get embeddings
                print("Embeddings API unavailable. Falling back to simulated embedding...")
                return self._get_random_embedding()  # Fall back to random for now
            
            # Other errors
            raise Exception(f"Claude API error: {response.status_code} {response.text}")
        except Exception as e:
            print(f"Claude embedding API error: {str(e)}")
            raise

    def _get_openai_embedding(self, text: str) -> List[float]:
        """Get an embedding from OpenAI API."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.providers['openai']['api_key']}"
        }
        
        data = {
            "input": text,
            "model": self.providers["openai"]["model"]
        }
        
        response = requests.post(
            f"{self.providers['openai']['api_base']}/embeddings", 
            headers=headers, 
            json=data
        )
        
        if response.status_code != 200:
            raise Exception(f"OpenAI API error: {response.status_code} {response.text}")
        
        result = response.json()
        return result["data"][0]["embedding"]
    
    def _get_random_embedding(self) -> List[float]:
        """Generate a random embedding for testing purposes."""
        random_vector = np.random.randn(self.embedding_dimension)
        # Normalize the vector to unit length
        normalized = random_vector / np.linalg.norm(random_vector)
        return normalized.tolist()
    
    def generate_triple_embeddings(self, triple) -> Dict[str, List[float]]:
        """
        Generate embeddings for the subject, predicate, and object of a triple.
        
        Args:
            triple: The Triple object to generate embeddings for
            
        Returns:
            Dictionary with embeddings for subject, predicate, and object
        """
        # Generate embeddings
        subject_embedding = self.get_embedding(triple.subject)
        predicate_embedding = self.get_embedding(triple.predicate)
        
        # Object could be literal or URI
        object_text = triple.object_literal if triple.is_literal else triple.object_uri
        object_embedding = self.get_embedding(object_text)
        
        return {
            "subject_embedding": subject_embedding,
            "predicate_embedding": predicate_embedding,
            "object_embedding": object_embedding
        }
    
    def update_triple_embeddings(self, triple, commit: bool = True):
        """
        Update the embeddings for a triple.
        
        Args:
            triple: The Triple object to update embeddings for
            commit: Whether to commit the session after update
            
        Returns:
            The updated Triple object
        """
        from app import db
        
        embeddings = self.generate_triple_embeddings(triple)
        
        # Update the triple
        triple.subject_embedding = embeddings["subject_embedding"]
        triple.predicate_embedding = embeddings["predicate_embedding"]
        triple.object_embedding = embeddings["object_embedding"]
        
        if commit:
            db.session.commit()
        
        return triple
    
    def batch_update_embeddings(self, triple_ids: List[int] = None, limit: int = 100):
        """
        Update embeddings for multiple triples in batch.
        
        Args:
            triple_ids: Optional list of triple IDs to update. If None, update all triples.
            limit: Maximum number of triples to update at once
            
        Returns:
            Number of triples updated
        """
        from app import db
        from app.models.triple import Triple
        
        query = db.session.query(Triple)
        
        # Filter by IDs if provided
        if triple_ids:
            query = query.filter(Triple.id.in_(triple_ids))
        
        # Filter triples with missing embeddings
        query = query.filter(Triple.subject_embedding.is_(None))
        
        # Limit the batch size
        query = query.limit(limit)
        
        triples = query.all()
        
        print(f"Updating embeddings for {len(triples)} triples...")
        
        for triple in triples:
            self.update_triple_embeddings(triple, commit=False)
        
        db.session.commit()
        
        return len(triples)
    
    def find_similar_triples(self, text: str, field: str = "subject", limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find triples with similar embeddings to the given text.
        
        Args:
            text: The text to find similar triples for
            field: Which field to search (subject, predicate, object)
            limit: Maximum number of results to return
            
        Returns:
            List of (triple, similarity) tuples
        """
        from app import db
        
        # Generate embedding for the query text
        embedding = self.get_embedding(text)
        
        # Determine which embedding field to search
        if field == "subject":
            embedding_field = "subject_embedding"
        elif field == "predicate":
            embedding_field = "predicate_embedding"
        elif field == "object":
            embedding_field = "object_embedding"
        else:
            raise ValueError(f"Invalid field: {field}")
        
        # Convert the embedding to a string representation for SQL
        embedding_str = f"[{','.join(str(x) for x in embedding)}]"
        
        # Query for similar triples
        query = f"""
        SELECT 
            id,
            subject,
            predicate, 
            object_literal,
            object_uri,
            is_literal,
            {embedding_field} <-> '{embedding_str}'::vector AS distance
        FROM 
            character_triples
        WHERE 
            {embedding_field} IS NOT NULL
        ORDER BY 
            distance
        LIMIT {limit}
        """
        
        result = db.session.execute(text(query))
        
        # Format results
        similar_triples = []
        for row in result:
            object_value = row.object_literal if row.is_literal else row.object_uri
            similar_triples.append({
                "id": row.id,
                "subject": row.subject,
                "predicate": row.predicate,
                "object": object_value,
                "is_literal": row.is_literal,
                "similarity": 1.0 - row.distance
            })
        
        return similar_triples
