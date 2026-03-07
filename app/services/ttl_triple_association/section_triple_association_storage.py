#!/usr/bin/env python3
"""
SectionTripleAssociationStorage - Database storage for section-triple associations.

This module provides functionality to store and retrieve associations between
document sections and ontology concepts, handling the database interactions.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Set
from sqlalchemy import create_engine, Table, MetaData, Column, Integer, Float, String, \
                      ForeignKey, text, DateTime, Boolean, func
from sqlalchemy.sql import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SectionTripleAssociationStorage:
    """Handles database storage for section-triple associations."""
    
    def __init__(self, db_url: Optional[str] = None):
        """
        Initialize with optional database URL.
        
        Args:
            db_url: Database connection URL
        """
        self.db_url = db_url or os.environ.get(
            "DATABASE_URL",
            "postgresql://postgres:PASS@localhost:5432/ai_ethical_dm"
        )
        
        self.engine = None
        self.metadata = MetaData()
        self._define_tables()
        
    def _define_tables(self):
        """Define the database table structure."""
        # Association table definition
        self.section_triple_association = Table(
            'section_ontology_associations', 
            self.metadata,
            Column('id', Integer, primary_key=True),
            Column('section_id', Integer, 
                   ForeignKey('document_sections.id', ondelete='CASCADE')),
            Column('concept_uri', String, nullable=False),
            Column('concept_label', String),
            Column('match_score', Float, nullable=False),
            Column('match_type', String),
            Column('created_at', DateTime, 
                   server_default=func.now())
        )
        
    def connect(self):
        """Create database connection."""
        if self.engine is None:
            try:
                logger.info(f"Connecting to database: {self.db_url}")
                self.engine = create_engine(self.db_url)
                logger.info("Database connection established")
                return True
            except SQLAlchemyError as e:
                logger.error(f"Error connecting to database: {str(e)}")
                return False
        return True
        
    def create_table(self):
        """
        Create the section_triple_association table if it doesn't exist.
        
        Returns:
            bool: Success flag
        """
        if not self.connect():
            return False
            
        try:
            # First check if table exists
            with self.engine.connect() as conn:
                query = text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'section_ontology_associations'
                    )
                """)
                result = conn.execute(query).scalar()
                
                if result:
                    logger.info("Table section_triple_association already exists")
                    return True
                    
                # Table doesn't exist, create it
                self.section_triple_association.create(self.engine)
                
                # Create indexes
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_section_triple_assoc_section_id 
                    ON section_ontology_associations(section_id)
                """))
                
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_section_triple_assoc_concept_uri 
                    ON section_ontology_associations(concept_uri)
                """))
                
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_section_triple_assoc_match_score 
                    ON section_ontology_associations(match_score DESC)
                """))
                
                logger.info("Created section_ontology_associations table and indexes")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Error creating table: {str(e)}")
            return False
            
    def store_associations(self, section_id: int, matches: List[Dict[str, Any]]) -> int:
        """
        Store section-triple associations in the database.
        
        Args:
            section_id: ID of the section
            matches: List of match dictionaries
            
        Returns:
            Number of associations stored
        """
        if not self.connect():
            logger.error("Failed to connect to database")
            return 0
            
        if not matches:
            logger.warning(f"No matches to store for section {section_id}")
            return 0
            
        try:
            # Ensure table exists
            self.create_table()
            
            # Delete existing associations for this section
            with self.engine.connect() as conn:
                delete_query = text("DELETE FROM section_ontology_associations WHERE section_id = :section_id")
                conn.execute(delete_query, {"section_id": section_id})
                
                # Insert new associations
                insert_count = 0
                for match in matches:
                    # Insert record
                    insert_query = text("""
                        INSERT INTO section_ontology_associations
                        (section_id, concept_uri, concept_label, match_score, match_type)
                        VALUES
                        (:section_id, :concept_uri, :concept_label, :match_score, :match_type)
                    """)
                    
                    conn.execute(insert_query, {
                        "section_id": section_id,
                        "concept_uri": match["concept_uri"],
                        "concept_label": match.get("concept_label", ""),
                        "match_score": match.get("vector_similarity", 0.0),
                        "match_type": match.get("match_type", "unknown")
                    })
                    
                    insert_count += 1
                
                conn.commit()
                
            logger.info(f"Stored {insert_count} associations for section {section_id}")
            return insert_count
            
        except SQLAlchemyError as e:
            logger.error(f"Error storing associations: {str(e)}")
            return 0
            
    def get_section_associations(self, section_id: int, 
                               limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get stored associations for a section.
        
        Args:
            section_id: ID of the section
            limit: Maximum number of associations to return
            
        Returns:
            List of association dictionaries
        """
        if not self.connect():
            return []
            
        try:
            with self.engine.connect() as conn:
                query = text("""
                    SELECT 
                        id, section_id, concept_uri, concept_label, match_score,
                        match_type, created_at
                    FROM 
                        section_ontology_associations
                    WHERE 
                        section_id = :section_id
                    ORDER BY 
                        match_score DESC
                    LIMIT :limit
                """)
                
                result = conn.execute(query, {
                    "section_id": section_id,
                    "limit": limit
                })
                
                associations = []
                for row in result:
                    associations.append({
                        "id": row[0],
                        "section_id": row[1],
                        "concept_uri": row[2],
                        "concept_label": row[3],
                        "match_score": row[4],
                        "match_type": row[5],
                        "created_at": row[6]
                    })
                    
                logger.info(f"Retrieved {len(associations)} associations for section {section_id}")
                return associations
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting section associations: {str(e)}")
            return []
            
    def get_document_associations(self, document_id: int, 
                                limit_per_section: int = 5) -> Dict[int, List[Dict[str, Any]]]:
        """
        Get stored associations for all sections in a document.
        
        Args:
            document_id: ID of the document
            limit_per_section: Maximum number of associations per section
            
        Returns:
            Dictionary mapping section IDs to lists of associations
        """
        if not self.connect():
            return {}
            
        try:
            # First get all sections for this document
            sections = {}
            with self.engine.connect() as conn:
                section_query = text("""
                    SELECT id, section_id as title, section_type
                    FROM document_sections
                    WHERE document_id = :document_id
                """)
                
                section_result = conn.execute(section_query, {"document_id": document_id})
                
                for row in section_result:
                    sections[row[0]] = {
                        "id": row[0],
                        "title": row[1],
                        "section_type": row[2]
                    }
            
            # No sections found
            if not sections:
                logger.warning(f"No sections found for document {document_id}")
                return {}
                
            # Get associations for each section
            associations = {}
            for section_id in sections:
                section_associations = self.get_section_associations(
                    section_id, limit=limit_per_section
                )
                
                if section_associations:
                    associations[section_id] = section_associations
                    
            logger.info(f"Retrieved associations for {len(associations)} sections in document {document_id}")
            return associations
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting document associations: {str(e)}")
            return {}
            
    def delete_section_associations(self, section_id: int) -> bool:
        """
        Delete all associations for a section.
        
        Args:
            section_id: ID of the section
            
        Returns:
            Success flag
        """
        if not self.connect():
            return False
            
        try:
            with self.engine.connect() as conn:
                query = text("""
                    DELETE FROM section_ontology_associations 
                    WHERE section_id = :section_id
                """)
                
                result = conn.execute(query, {"section_id": section_id})
                conn.commit()
                
                logger.info(f"Deleted {result.rowcount} associations for section {section_id}")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Error deleting section associations: {str(e)}")
            return False
            
    def delete_document_associations(self, document_id: int) -> bool:
        """
        Delete all associations for a document.
        
        Args:
            document_id: ID of the document
            
        Returns:
            Success flag
        """
        if not self.connect():
            return False
            
        try:
            with self.engine.connect() as conn:
                query = text("""
                    DELETE FROM section_ontology_associations 
                    WHERE section_id IN (
                        SELECT id FROM document_sections 
                        WHERE document_id = :document_id
                    )
                """)
                
                result = conn.execute(query, {"document_id": document_id})
                conn.commit()
                
                logger.info(f"Deleted associations for document {document_id}")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Error deleting document associations: {str(e)}")
            return False
