#!/usr/bin/env python3
"""
SectionTripleAssociationService - Main service for section-to-triple association.

This module provides the main service for associating document sections with
relevant ontology concepts using the TTL-based approach.
"""

import os
import logging
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Set, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# Import component classes
from ttl_triple_association.ontology_triple_loader import OntologyTripleLoader
from ttl_triple_association.embedding_service import EmbeddingService
from ttl_triple_association.section_triple_associator import SectionTripleAssociator
from ttl_triple_association.section_triple_association_storage import SectionTripleAssociationStorage

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SectionTripleAssociationService:
    """
    Main service for associating document sections with ontology concepts.
    
    This class brings together all the components needed for the section-triple
    association process and provides the main interface for using the system.
    """
    
    def __init__(self, db_url: Optional[str] = None, 
                similarity_threshold: float = 0.6, 
                max_matches: int = 10):
        """
        Initialize the section triple association service.
        
        Args:
            db_url: Database connection URL
            similarity_threshold: Minimum similarity score for matches (0-1)
            max_matches: Maximum number of matches to return per section
        """
        # Database settings
        self.db_url = db_url or os.environ.get(
            "DATABASE_URL", 
            "postgresql://postgres:postgres@localhost:5433/ai_ethical_dm"
        )
        
        # Initialize database connection
        self.engine = create_engine(self.db_url)
        self.Session = sessionmaker(bind=self.engine)
        
        # Component initialization
        logger.info("Initializing components...")
        self.ontology_loader = OntologyTripleLoader()
        self.embedding_service = EmbeddingService()
        self.storage = SectionTripleAssociationStorage(self.db_url)
        
        # Component settings
        self.similarity_threshold = similarity_threshold
        self.max_matches = max_matches
        
        # Lazily initialize the associator when needed
        self._associator = None
        
    def _get_associator(self) -> SectionTripleAssociator:
        """
        Get or initialize the SectionTripleAssociator.
        
        This is done lazily to avoid loading the ontology and generating 
        embeddings until they are actually needed.
        
        Returns:
            Initialized SectionTripleAssociator
        """
        if self._associator is None:
            logger.info("Initializing section triple associator...")
            
            # Load ontology if not already loaded
            if not hasattr(self.ontology_loader, 'concepts') or not self.ontology_loader.concepts:
                logger.info("Loading ontology...")
                self.ontology_loader.load()
                
            # Initialize associator
            self._associator = SectionTripleAssociator(
                self.ontology_loader,
                self.embedding_service,
                self.similarity_threshold,
                self.max_matches
            )
            
        return self._associator
    
    def get_section_embedding(self, section_id: int) -> Optional[np.ndarray]:
        """
        Retrieve embedding for a document section.
        
        Args:
            section_id: ID of the section
            
        Returns:
            Numpy array containing the embedding, or None if not found
        """
        try:
            session = self.Session()
            # Try directly from document_sections table first (new schema)
            query = text("""
                SELECT embedding 
                FROM document_sections 
                WHERE id = :section_id
                LIMIT 1
            """)
            
            result = session.execute(query, {"section_id": section_id}).fetchone()
            
            if result and result[0]:
                # Convert from database format to numpy array
                embedding_bytes = result[0]
                if isinstance(embedding_bytes, str):
                    return None
                return np.frombuffer(embedding_bytes, dtype=np.float32)
            
            # Fall back to document_section_embeddings if exists
            try:
                query = text("""
                    SELECT embedding 
                    FROM document_section_embeddings 
                    WHERE section_id = :section_id
                    LIMIT 1
                """)
                
                result = session.execute(query, {"section_id": section_id}).fetchone()
                
                if result and result[0]:
                    # Convert from database format to numpy array
                    embedding_bytes = result[0]
                    return np.frombuffer(embedding_bytes, dtype=np.float32)
            except:
                # Table might not exist, just continue
                pass
            
            logger.warning(f"No embedding found for section {section_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving section embedding: {str(e)}")
            return None
        finally:
            session.close()
            
    def get_section_metadata(self, section_id: int) -> Dict[str, Any]:
        """
        Retrieve metadata for a document section.
        
        Args:
            section_id: ID of the section
            
        Returns:
            Dictionary with section metadata
        """
        try:
            session = self.Session()
            query = text("""
                SELECT ds.id, ds.section_id as title, ds.content, ds.section_type, 
                       ds.position as parent_id, d.id as document_id, d.title as document_title
                FROM document_sections ds
                JOIN documents d ON ds.document_id = d.id
                WHERE ds.id = :section_id
            """)
            
            result = session.execute(query, {"section_id": section_id}).fetchone()
            
            if result:
                return {
                    "id": result[0],
                    "title": result[1] or f"Section {result[0]}",  # Use section_id or default
                    "content": result[2],
                    "section_type": result[3],
                    "parent_id": result[4],
                    "document_id": result[5],
                    "document_title": result[6]
                }
            
            logger.warning(f"No metadata found for section {section_id}")
            return {}
            
        except Exception as e:
            logger.error(f"Error retrieving section metadata: {str(e)}")
            return {}
        finally:
            session.close()
    
    def associate_section_with_concepts(self, section_id: int) -> Dict[str, Any]:
        """
        Associate a document section with relevant ontology concepts.
        
        This is the main method that performs the association process for 
        a single section.
        
        Args:
            section_id: ID of the section to process
            
        Returns:
            Result dictionary with success flag and matches
        """
        # Get section embedding and metadata
        section_embedding = self.get_section_embedding(section_id)
        if section_embedding is None:
            logger.warning(f"No embedding found for section {section_id}")
            return {
                "success": False,
                "error": f"No embedding found for section {section_id}",
                "matches": []
            }
            
        # Log embedding size and shape for debugging
        logger.info(f"Section {section_id} embedding shape: {section_embedding.shape}")
        logger.info(f"Section {section_id} embedding sample: {section_embedding[:5]}")
        
        section_metadata = self.get_section_metadata(section_id)
        if not section_metadata:
            return {
                "success": False,
                "error": f"No metadata found for section {section_id}",
                "matches": []
            }
        
        try:
            # Get associator (lazy initialization)
            associator = self._get_associator()
            
            # Perform association
            logger.info(f"Associating section {section_id} with concepts...")
            matches = associator.associate_section(section_embedding, section_metadata)
            
            # Map vector_similarity to match_score if necessary
            for match in matches:
                if "vector_similarity" in match and "match_score" not in match:
                    match["match_score"] = match["vector_similarity"]
            
            if not matches:
                logger.info(f"No matches found for section {section_id}")
                return {
                    "success": True,
                    "matches": [],
                    "section_id": section_id,
                    "count": 0
                }
            
            # Store associations
            stored_count = self.storage.store_associations(section_id, matches)
            
            # Return result
            return {
                "success": True,
                "matches": matches,
                "section_id": section_id,
                "count": stored_count,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error associating section with concepts: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "section_id": section_id,
                "matches": []
            }
    
    def batch_associate_sections(self, section_ids: Optional[List[int]] = None,
                                document_id: Optional[int] = None,
                                batch_size: int = 10) -> Dict[str, Any]:
        """
        Process multiple sections in batch.
        
        Args:
            section_ids: List of section IDs to process (optional)
            document_id: Document ID to process all sections from (optional)
            batch_size: Maximum number of sections to process in a batch
            
        Returns:
            Result dictionary with counts and statistics
        """
        if not section_ids and not document_id:
            return {
                "success": False,
                "error": "Either section_ids or document_id must be provided",
                "processed": 0
            }
            
        try:
            # Get sections to process
            sections_to_process = []
            
            if document_id:
                # Get all sections for this document
                session = self.Session()
                query = text("""
                    SELECT id FROM document_sections 
                    WHERE document_id = :document_id
                    ORDER BY id
                """)
                
                result = session.execute(query, {"document_id": document_id})
                sections_to_process = [row[0] for row in result]
                session.close()
                
                logger.info(f"Found {len(sections_to_process)} sections for document {document_id}")
                
            else:
                sections_to_process = section_ids
                
            if not sections_to_process:
                return {
                    "success": False,
                    "error": "No sections found to process",
                    "processed": 0
                }
                
            # Process sections in batches
            results = {
                "success": True,
                "processed": 0,
                "successful": 0,
                "failed": 0,
                "sections": {},
                "start_time": datetime.utcnow().isoformat(),
            }
            
            for i in range(0, len(sections_to_process), batch_size):
                batch = sections_to_process[i:i+batch_size]
                logger.info(f"Processing batch {i//batch_size + 1} with {len(batch)} sections")
                
                for section_id in batch:
                    result = self.associate_section_with_concepts(section_id)
                    results["processed"] += 1
                    
                    if result["success"]:
                        results["successful"] += 1
                        results["sections"][section_id] = {
                            "success": True,
                            "matches": len(result.get("matches", []))
                        }
                    else:
                        results["failed"] += 1
                        results["sections"][section_id] = {
                            "success": False,
                            "error": result.get("error", "Unknown error")
                        }
                    
                    # Log progress
                    if results["processed"] % 10 == 0:
                        logger.info(f"Processed {results['processed']}/{len(sections_to_process)} sections")
            
            # Add end timestamp
            results["end_time"] = datetime.utcnow().isoformat()
            results["total_sections"] = len(sections_to_process)
            
            return results
                
        except Exception as e:
            logger.error(f"Error in batch section processing: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "processed": 0
            }
            
    def get_section_associations(self, section_id: int, limit: int = 10) -> Dict[str, Any]:
        """
        Get stored associations for a section.
        
        Args:
            section_id: ID of the section
            limit: Maximum number of associations to return
            
        Returns:
            Result dictionary with associations
        """
        try:
            # Get section metadata
            section_metadata = self.get_section_metadata(section_id)
            if not section_metadata:
                return {
                    "success": False,
                    "error": f"No metadata found for section {section_id}",
                    "associations": []
                }
                
            # Get associations
            associations = self.storage.get_section_associations(section_id, limit)
            
            return {
                "success": True,
                "section": section_metadata,
                "associations": associations,
                "count": len(associations)
            }
            
        except Exception as e:
            logger.error(f"Error getting section associations: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "associations": []
            }
            
    def get_document_associations(self, document_id: int, limit_per_section: int = 5) -> Dict[str, Any]:
        """
        Get stored associations for all sections in a document.
        
        Args:
            document_id: ID of the document
            limit_per_section: Maximum number of associations per section
            
        Returns:
            Result dictionary with associations by section
        """
        try:
            # Get document metadata
            session = self.Session()
            query = text("""
                SELECT id, title, document_type
                FROM documents
                WHERE id = :document_id
            """)
            
            result = session.execute(query, {"document_id": document_id}).fetchone()
            session.close()
            
            if not result:
                return {
                    "success": False,
                    "error": f"Document {document_id} not found",
                    "associations": {}
                }
                
            document = {
                "id": result[0],
                "title": result[1],
                "document_type": result[2]
            }
                
            # Get associations
            associations_by_section = self.storage.get_document_associations(
                document_id, limit_per_section
            )
            
            return {
                "success": True,
                "document": document,
                "sections": associations_by_section,
                "section_count": len(associations_by_section)
            }
            
        except Exception as e:
            logger.error(f"Error getting document associations: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "associations": {}
            }
