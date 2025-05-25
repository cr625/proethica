#!/usr/bin/env python3
"""
Section Triple Association Service

This service associates document sections with relevant ontology triples
using both vector similarity and semantic matching properties.

It implements the two-phase matching process described in the section_embedding_and_triple_association_analysis.md document:
1. Coarse matching using vector similarity
2. Fine-grained matching using semantic properties
"""

import os
import logging
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/ai_ethical_dm")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class SectionTripleAssociationService:
    """Service for associating document sections with relevant ontology triples."""

    def __init__(self, similarity_threshold: float = 0.6, max_matches: int = 10):
        """
        Initialize the service.
        
        Args:
            similarity_threshold: Minimum similarity score (0-1) for a triple to be considered relevant
            max_matches: Maximum number of triple matches to return per section
        """
        self.similarity_threshold = similarity_threshold
        self.max_matches = max_matches
        self.session = Session()
        logger.info(f"SectionTripleAssociationService initialized with threshold={similarity_threshold}")

    def get_section_embedding(self, section_id: int) -> Optional[np.ndarray]:
        """Retrieve embedding for a document section."""
        try:
            query = text("""
                SELECT embedding 
                FROM document_section_embeddings 
                WHERE section_id = :section_id
                LIMIT 1
            """)
            
            result = self.session.execute(query, {"section_id": section_id}).fetchone()
            
            if result and result[0]:
                # Convert from database format to numpy array
                embedding_bytes = result[0]
                return np.frombuffer(embedding_bytes, dtype=np.float32)
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving section embedding: {e}")
            return None

    def get_section_metadata(self, section_id: int) -> Dict[str, Any]:
        """Retrieve metadata for a document section."""
        try:
            query = text("""
                SELECT ds.id, ds.title, ds.content, ds.section_type, ds.parent_id,
                       d.id as document_id, d.title as document_title, d.case_id
                FROM document_sections ds
                JOIN documents d ON ds.document_id = d.id
                WHERE ds.id = :section_id
            """)
            
            result = self.session.execute(query, {"section_id": section_id}).fetchone()
            
            if result:
                return {
                    "id": result[0],
                    "title": result[1],
                    "content": result[2],
                    "section_type": result[3],
                    "parent_id": result[4],
                    "document_id": result[5],
                    "document_title": result[6],
                    "case_id": result[7]
                }
            return {}
            
        except Exception as e:
            logger.error(f"Error retrieving section metadata: {e}")
            return {}

    def get_ontology_concept_embeddings(self) -> Dict[str, Tuple[np.ndarray, Dict[str, Any]]]:
        """
        Retrieve embeddings for ontology concepts.
        
        Returns:
            Dictionary mapping concept URIs to tuples of (embedding, metadata)
        """
        # In a full implementation, this would retrieve pre-computed concept embeddings
        # For now, we'll return a mock structure
        
        # Mock implementation - in reality, these would be retrieved from the database
        # or computed on demand from the ontology triples
        mock_concepts = {
            "http://proethica.org/ontology/engineering-ethics/PublicSafetyPrinciple": (
                np.random.rand(1536).astype(np.float32),  # Mock embedding
                {
                    "label": "Public Safety Principle",
                    "description": "Engineers must prioritize public safety, health, and welfare above all other considerations",
                    "matching_terms": ["safety", "public safety", "welfare", "health"],
                    "category": "core ethical principle",
                    "relevance_score": 0.9
                }
            ),
            "http://proethica.org/ontology/engineering-ethics/ProfessionalIntegrityPrinciple": (
                np.random.rand(1536).astype(np.float32),  # Mock embedding
                {
                    "label": "Professional Integrity Principle",
                    "description": "Engineers must maintain honesty, ethical conduct, and avoid deceptive practices",
                    "matching_terms": ["integrity", "honesty", "ethical conduct"],
                    "category": "core ethical principle",
                    "relevance_score": 0.85
                }
            ),
            # Add more mock concepts as needed
        }
        
        logger.info(f"Retrieved {len(mock_concepts)} concept embeddings")
        return mock_concepts

    def compute_vector_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings."""
        # Ensure the embeddings are normalized
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        embedding1_normalized = embedding1 / norm1
        embedding2_normalized = embedding2 / norm2
        
        # Compute cosine similarity
        similarity = np.dot(embedding1_normalized, embedding2_normalized)
        
        return float(similarity)

    def extract_keywords_from_section(self, section_content: str) -> List[str]:
        """Extract keywords from section content for keyword matching."""
        # Simple implementation - in a real system, this would use NLP techniques
        # like entity extraction, keyword extraction, etc.
        
        # For now, just split on spaces and remove punctuation
        words = section_content.lower().replace('.', ' ').replace(',', ' ').split()
        
        # Remove common stopwords (a very basic list)
        stopwords = {'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with', 'by'}
        keywords = [word for word in words if word not in stopwords and len(word) > 3]
        
        return list(set(keywords))  # Remove duplicates

    def term_match_score(self, section_keywords: List[str], concept_terms: List[str]) -> float:
        """
        Calculate a match score based on keyword overlap between section and concept.
        
        Returns:
            A score between 0 and 1 representing the strength of the term match.
        """
        if not section_keywords or not concept_terms:
            return 0.0
            
        # Count matching terms
        matches = sum(1 for keyword in section_keywords if any(term.lower() in keyword or keyword in term.lower() for term in concept_terms))
        
        # Calculate score as proportion of matching keywords
        score = matches / len(section_keywords)
        
        return min(score, 1.0)  # Cap at 1.0

    def perform_coarse_matching(self, section_embedding: np.ndarray, 
                              concept_embeddings: Dict[str, Tuple[np.ndarray, Dict[str, Any]]]) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        First phase: Perform coarse matching using vector similarity.
        
        Args:
            section_embedding: Embedding vector for the section
            concept_embeddings: Dictionary of concept embeddings
            
        Returns:
            List of tuples (concept_uri, similarity_score, concept_metadata)
        """
        matches = []
        
        for concept_uri, (concept_embedding, concept_metadata) in concept_embeddings.items():
            similarity = self.compute_vector_similarity(section_embedding, concept_embedding)
            
            if similarity >= self.similarity_threshold:
                matches.append((concept_uri, similarity, concept_metadata))
        
        # Sort by similarity score (descending)
        matches.sort(key=lambda x: x[1], reverse=True)
        
        # Limit to max_matches
        return matches[:self.max_matches]

    def perform_fine_grained_matching(self, section_metadata: Dict[str, Any], 
                                    coarse_matches: List[Tuple[str, float, Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Second phase: Perform fine-grained matching using semantic properties.
        
        Args:
            section_metadata: Metadata for the section
            coarse_matches: Results from coarse matching
            
        Returns:
            List of match results with combined scores
        """
        fine_grained_matches = []
        
        # Extract keywords from section content
        section_keywords = self.extract_keywords_from_section(section_metadata.get("content", ""))
        
        for concept_uri, similarity_score, concept_metadata in coarse_matches:
            # Calculate term match score
            concept_terms = concept_metadata.get("matching_terms", [])
            term_score = self.term_match_score(section_keywords, concept_terms)
            
            # Consider section type relevance
            # This would be more sophisticated in a real implementation
            section_type_bonus = 0.1 if concept_metadata.get("category") == "core ethical principle" else 0.0
            
            # Calculate combined score
            # This is a simple weighted average - could be more sophisticated
            combined_score = (0.6 * similarity_score) + (0.3 * term_score) + (0.1 * concept_metadata.get("relevance_score", 0.5)) + section_type_bonus
            
            fine_grained_matches.append({
                "concept_uri": concept_uri,
                "concept_label": concept_metadata.get("label", ""),
                "concept_description": concept_metadata.get("description", ""),
                "vector_similarity": similarity_score,
                "term_match_score": term_score,
                "combined_score": combined_score,
                "category": concept_metadata.get("category", "")
            })
        
        # Sort by combined score (descending)
        fine_grained_matches.sort(key=lambda x: x["combined_score"], reverse=True)
        
        return fine_grained_matches

    def store_section_triple_associations(self, section_id: int, matches: List[Dict[str, Any]]) -> bool:
        """
        Store the section-triple associations in the database.
        
        Args:
            section_id: ID of the section
            matches: List of match results
            
        Returns:
            Success status
        """
        try:
            # First, delete any existing associations for this section
            delete_query = text("""
                DELETE FROM section_triple_association 
                WHERE section_id = :section_id
            """)
            
            self.session.execute(delete_query, {"section_id": section_id})
            
            # Insert new associations
            for match in matches:
                # Convert the concept URI to subject/predicate/object
                # This is a simplification - in reality, we'd store the actual triple
                subject = match["concept_uri"]
                predicate = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
                object_uri = "http://proethica.org/ontology/Concept"
                
                insert_query = text("""
                    INSERT INTO section_triple_association 
                    (section_id, triple_subject, triple_predicate, triple_object, 
                     similarity_score, match_confidence, match_type)
                    VALUES 
                    (:section_id, :subject, :predicate, :object, 
                     :similarity, :confidence, :match_type)
                """)
                
                self.session.execute(insert_query, {
                    "section_id": section_id,
                    "subject": subject,
                    "predicate": predicate,
                    "object": object_uri,
                    "similarity": match["vector_similarity"],
                    "confidence": match["combined_score"],
                    "match_type": "concept_match"
                })
            
            self.session.commit()
            logger.info(f"Stored {len(matches)} associations for section {section_id}")
            return True
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error storing section-triple associations: {e}")
            return False

    def associate_section_with_triples(self, section_id: int) -> List[Dict[str, Any]]:
        """
        Main method to associate a section with relevant triples.
        
        Args:
            section_id: ID of the section to process
            
        Returns:
            List of match results
        """
        # Get section embedding and metadata
        section_embedding = self.get_section_embedding(section_id)
        if section_embedding is None:
            logger.warning(f"No embedding found for section {section_id}")
            return []
            
        section_metadata = self.get_section_metadata(section_id)
        if not section_metadata:
            logger.warning(f"No metadata found for section {section_id}")
            return []
        
        # Get concept embeddings
        concept_embeddings = self.get_ontology_concept_embeddings()
        
        # Perform coarse matching
        coarse_matches = self.perform_coarse_matching(section_embedding, concept_embeddings)
        logger.info(f"Found {len(coarse_matches)} coarse matches for section {section_id}")
        
        # Perform fine-grained matching
        fine_grained_matches = self.perform_fine_grained_matching(section_metadata, coarse_matches)
        logger.info(f"Produced {len(fine_grained_matches)} fine-grained matches for section {section_id}")
        
        # Store associations
        self.store_section_triple_associations(section_id, fine_grained_matches)
        
        return fine_grained_matches

    def batch_associate_sections(self, section_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
        """
        Process multiple sections in batch.
        
        Args:
            section_ids: List of section IDs to process
            
        Returns:
            Dictionary mapping section IDs to their match results
        """
        results = {}
        
        for section_id in section_ids:
            matches = self.associate_section_with_triples(section_id)
            results[section_id] = matches
            
        return results
        
    def get_similar_sections_by_concept(self, concept_uri: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find sections associated with a specific concept.
        
        Args:
            concept_uri: URI of the concept
            limit: Maximum number of sections to return
            
        Returns:
            List of section metadata with match scores
        """
        try:
            query = text("""
                SELECT ds.id, ds.title, ds.content, ds.section_type, 
                       d.id as document_id, d.title as document_title,
                       sta.similarity_score, sta.match_confidence
                FROM section_triple_association sta
                JOIN document_sections ds ON sta.section_id = ds.id
                JOIN documents d ON ds.document_id = d.id
                WHERE sta.triple_subject = :concept_uri
                ORDER BY sta.match_confidence DESC
                LIMIT :limit
            """)
            
            results = self.session.execute(query, {
                "concept_uri": concept_uri,
                "limit": limit
            }).fetchall()
            
            sections = []
            for row in results:
                sections.append({
                    "section_id": row[0],
                    "title": row[1],
                    "excerpt": row[2][:200] + "..." if row[2] and len(row[2]) > 200 else row[2],
                    "section_type": row[3],
                    "document_id": row[4],
                    "document_title": row[5],
                    "similarity_score": row[6],
                    "match_confidence": row[7]
                })
            
            return sections
            
        except Exception as e:
            logger.error(f"Error retrieving sections by concept: {e}")
            return []

    def close(self):
        """Close database session."""
        self.session.close()


def create_section_triple_association_table():
    """Create the section_triple_association table if it doesn't exist."""
    try:
        with engine.connect() as connection:
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS section_triple_association (
                  id SERIAL PRIMARY KEY,
                  section_id INTEGER REFERENCES document_sections(id) ON DELETE CASCADE,
                  triple_subject TEXT NOT NULL,
                  triple_predicate TEXT NOT NULL,
                  triple_object TEXT NOT NULL,
                  similarity_score FLOAT NOT NULL,
                  match_confidence FLOAT NOT NULL,
                  match_type VARCHAR(50) NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Create index for efficient querying
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_section_triple_assoc_section_id 
                ON section_triple_association(section_id)
            """))
            
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_section_triple_assoc_subject 
                ON section_triple_association(triple_subject)
            """))
            
        logger.info("Section triple association table created or verified")
        return True
        
    except Exception as e:
        logger.error(f"Error creating section_triple_association table: {e}")
        return False


if __name__ == "__main__":
    # Create the table if it doesn't exist
    create_section_triple_association_table()
    
    # Example usage
    service = SectionTripleAssociationService()
    
    # Test with a sample section
    # Replace with a valid section ID from your database
    sample_section_id = 1
    matches = service.associate_section_with_triples(sample_section_id)
    
    print(f"Found {len(matches)} concept matches for section {sample_section_id}")
    for match in matches[:5]:  # Print top 5
        print(f"  {match['concept_label']} (Score: {match['combined_score']:.4f})")
    
    service.close()
