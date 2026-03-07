#!/usr/bin/env python3
"""
EmbeddingService - Service for generating embeddings and computing similarity.

This module provides functionality for generating embeddings from text content
and computing similarity between embeddings. It handles text cleaning to avoid
formatting tokens affecting the semantic meaning.
"""

import logging
import re
import numpy as np
from typing import Optional, Union, List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Service for generating embeddings and computing similarity.
    
    This service handles:
    - Loading the embedding model
    - Cleaning text of formatting tokens
    - Generating embeddings for text content
    - Computing similarity between embeddings
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str = None):
        """
        Initialize the embedding service.
        
        Args:
            model_name: Name of the SentenceTransformer model to use
            device: Device to use for inference (None for auto, 'cpu', 'cuda')
        """
        self.model_name = model_name
        self.device = device
        self.model = None
        self.embedding_dim = 384  # Default for all-MiniLM-L6-v2
        
        # Patterns for text cleaning
        self.uri_pattern = re.compile(r'https?://\S+|http?://\S+')
        self.xml_tag_pattern = re.compile(r'<[^>]+>')
        self.formatting_tokens_pattern = re.compile(r'rdf:|rdfs:|owl:|xsd:|xml:|xmlns:|#')
        self.excessive_whitespace_pattern = re.compile(r'\s+')
        
        logger.info(f"Initialized embedding service with model: {model_name}")
        
    def load_model(self):
        """
        Load the embedding model.
        
        Loads the SentenceTransformer model specified in the constructor.
        """
        try:
            # Import here to avoid hard dependency if not using this feature
            from sentence_transformers import SentenceTransformer
            
            logger.info(f"Loading sentence transformer model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name, device=self.device)
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            logger.info(f"Loaded model with embedding dimension: {self.embedding_dim}")
            
            return True
        except ImportError:
            logger.error("Failed to import SentenceTransformer. "
                         "Install with: pip install sentence-transformers")
            return False
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            return False
            
    def _clean_text(self, text: str) -> str:
        """
        Remove special formatting characters from text.
        
        Args:
            text: Text to clean
            
        Returns:
            Cleaned text with formatting tokens removed
        """
        if not text:
            return ""
            
        # Remove URIs
        clean = self.uri_pattern.sub(' ', text)
        
        # Remove XML tags
        clean = self.xml_tag_pattern.sub(' ', clean)
        
        # Remove common RDF/OWL formatting tokens
        clean = self.formatting_tokens_pattern.sub(' ', clean)
        
        # Normalize whitespace
        clean = self.excessive_whitespace_pattern.sub(' ', clean).strip()
        
        return clean
        
    def generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        Generate embedding for text.
        
        Args:
            text: Text to generate embedding for
            
        Returns:
            Numpy array containing the embedding, or None if generation fails
        """
        if not text:
            logger.warning("Empty text provided for embedding generation")
            return None
            
        # Load model if not already loaded
        if self.model is None:
            success = self.load_model()
            if not success:
                logger.error("Failed to load model for embedding generation")
                return None
        
        try:
            # Clean the text
            clean_text = self._clean_text(text)
            
            if not clean_text:
                logger.warning("Text was cleaned to empty string, cannot generate embedding")
                return None
                
            # Generate embedding
            embedding = self.model.encode(clean_text, 
                                         convert_to_numpy=True, 
                                         normalize_embeddings=True)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            return None
            
    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding
            embedding2: Second embedding
            
        Returns:
            Cosine similarity score between 0 and 1
        """
        try:
            # Ensure embeddings are normalized
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            
            if norm1 == 0 or norm2 == 0:
                logger.warning("Zero norm embedding detected in similarity calculation")
                return 0.0
                
            # Normalize if needed
            if abs(norm1 - 1.0) > 1e-5:
                embedding1 = embedding1 / norm1
                
            if abs(norm2 - 1.0) > 1e-5:
                embedding2 = embedding2 / norm2
                
            # Compute cosine similarity
            similarity = np.dot(embedding1, embedding2)
            
            # Ensure result is in valid range [0, 1]
            similarity = max(0.0, min(1.0, similarity))
            
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Error computing similarity: {str(e)}")
            return 0.0
            
    def get_most_similar_items(self, 
                              query_embedding: np.ndarray, 
                              item_embeddings: Dict[str, np.ndarray],
                              similarity_threshold: float = 0.0,
                              top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Find most similar items to a query embedding.
        
        Args:
            query_embedding: Embedding to compare against
            item_embeddings: Dictionary mapping item IDs to embeddings
            similarity_threshold: Minimum similarity score to include in results
            top_k: Maximum number of results to return
            
        Returns:
            List of dictionaries with item IDs and similarity scores
        """
        if query_embedding is None:
            logger.warning("Query embedding is None")
            return []
            
        if not item_embeddings:
            logger.warning("Empty item embeddings provided")
            return []
            
        # Calculate similarities
        similarities = []
        for item_id, item_embedding in item_embeddings.items():
            if item_embedding is None:
                continue
                
            similarity = self.compute_similarity(query_embedding, item_embedding)
            
            if similarity >= similarity_threshold:
                similarities.append({
                    'id': item_id,
                    'similarity': similarity
                })
                
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Return top-k
        return similarities[:top_k]
