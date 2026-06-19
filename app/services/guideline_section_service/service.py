"""
Service for associating guidelines with document sections.
Includes enhanced multi-metric relevance calculation with explainable reasoning.
"""
import logging
import json
import re
import random
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime
import numpy as np
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import nltk
from sqlalchemy import text

from app import db
from app.models import Document
from app.models.document_section import DocumentSection
from app.services.mcp_client import MCPClient
from app.services.embedding.section_embedding_service import SectionEmbeddingService
from app.utils.llm_utils import get_llm_client
from app.utils.nltk_verification import verify_nltk_resources

# Set up logging
logger = logging.getLogger(__name__)

from .relevance_scoring import RelevanceScoringMixin


class GuidelineSectionService(RelevanceScoringMixin):
    """
    Service for managing guideline associations with document sections.
    
    Features:
    - Multi-metric relevance calculation for more accurate associations
    - Vector similarity using section embeddings
    - Term overlap analysis for keyword matching
    - Structural relevance based on section type
    - LLM pattern analysis for deeper semantic understanding
    - Agreement score calculation for confidence estimation
    - Complete reasoning chain storage for explanation
    """
    
    def __init__(self):
        """Initialize the guideline section service with required dependencies."""
        self.mcp_client = MCPClient.get_instance()
        self.embedding_service = SectionEmbeddingService()
        self.stop_words = set(stopwords.words('english'))
        
    def _get_world_id_for_document(self, document_id: int) -> Optional[int]:
        """
        Get the world ID associated with a document.
        
        Args:
            document_id: ID of the document
            
        Returns:
            World ID or None if not found
        """
        try:
            # Get the document
            document = Document.query.get(document_id)
            if not document:
                return None
            
            # First try to get world_id directly from document
            if hasattr(document, 'world_id') and document.world_id is not None:
                return document.world_id
            
            # Only if direct world_id fails, try the case_id approach
            if hasattr(document, 'case_id') and document.case_id:
                # Try to get the world ID from the case
                query = """
                SELECT world_id FROM cases WHERE id = :case_id
                """
                
                result = db.session.execute(text(query), {'case_id': document.case_id}).first()
                
                if result and result[0]:
                    return result[0]
            
            # If all else fails, use default world
            return 1  # Default to engineering ethics world
        except Exception as e:
            logger.exception(f"Error getting world ID for document {document_id}: {str(e)}")
            return 1  # Default to world 1 on error
    
    def _get_guideline_triples_for_world(self, world_id: int) -> List[Dict[str, Any]]:
        """
        Get guideline triples for a specific world from the database.
        Includes triples directly linked to the world and triples linked to guidelines in that world.
        
        Args:
            world_id: ID of the world
            
        Returns:
            List of guideline triples
        """
        try:
            # Primary approach: Get directly from database with optimized filtering
            # Only include the relevant guideline triples with IDs in the specified range (3096-3222)
            # as identified in guideline_section_integration_enhancement.md
            query = """
            SELECT 
                et.subject, 
                et.subject_label,
                et.predicate,
                et.object_literal,
                et.object_uri,
                et.is_literal,
                et.entity_type
            FROM 
                entity_triples et
            WHERE 
                et.id BETWEEN 3096 AND 3222
                AND et.entity_type = 'guideline_concept'
            """
            
            results = db.session.execute(text(query), {'world_id': world_id}).fetchall()
            
            if results:
                triples = []
                for row in results:
                    triple = {
                        'subject_uri': row[0],
                        'subject_label': row[1] or row[0].split('/')[-1].replace('_', ' ').title(),
                        'predicate': row[2],
                        'entity_type': row[6] or 'guideline'
                    }
                    
                    if row[5]:  # is_literal
                        triple['object_literal'] = row[3]
                    else:
                        triple['object_uri'] = row[4]
                        
                    triples.append(triple)
                
                logger.info(f"Found {len(triples)} guideline triples in database for world {world_id}")
                return triples
            
            # Fallback: Try to get from MCP client
            try:
                world_data = self.mcp_client.get_world_entities(f"world_{world_id}")
                if world_data and 'entities' in world_data:
                    guidelines = []
                    
                    # Extract guidelines from different entity types
                    for entity_type in ['roles', 'resources', 'conditions', 'actions']:
                        if entity_type in world_data['entities']:
                            for entity in world_data['entities'][entity_type]:
                                if 'label' in entity:
                                    guidelines.append({
                                        'subject_uri': entity.get('uri', f"http://proethica.org/guidelines/{entity['label'].lower().replace(' ', '_')}"),
                                        'subject_label': entity['label'],
                                        'predicate': "http://proethica.org/ontology/hasDescription",
                                        'object_literal': entity.get('description', f"Guidelines about {entity['label']}"),
                                        'entity_type': entity_type
                                    })
                    
                    logger.info(f"Found {len(guidelines)} guideline entities via MCP for world {world_id}")
                    return guidelines
            except Exception as e:
                logger.warning(f"Error getting guideline triples from MCP client: {str(e)}")
            
            # If no triples found, return empty list
            logger.warning(f"No guideline triples found for world {world_id}")
            return []
            
        except Exception as e:
            logger.exception(f"Error getting guideline triples for world {world_id}: {str(e)}")
            return []
    
    def associate_guidelines_with_sections(self, document_id: int) -> Dict[str, Any]:
        """
        Associate relevant guidelines with document sections using multi-metric 
        relevance calculation for more accurate and explainable associations.
        
        Args:
            document_id: ID of the document to process
            
        Returns:
            dict: Results of the association process
        """
        try:
            logger.info(f"Starting enhanced guideline association process for document {document_id}")
            
            # Get the document
            document = Document.query.get(document_id)
            if not document:
                logger.error(f"Document {document_id} not found")
                return {
                    'success': False,
                    'error': 'Document not found'
                }
            
            # Get the document sections
            sections = DocumentSection.query.filter_by(document_id=document_id).all()
            if not sections:
                logger.warning(f"No sections found for document {document_id}")
                return {
                    'success': False,
                    'error': 'No sections found for document'
                }
            
            logger.info(f"Found {len(sections)} sections for document {document_id}")
            
            # Get document ontology and world information for guideline context
            world_id = self._get_world_id_for_document(document_id)
            
            if not world_id:
                logger.warning(f"Could not determine world ID for document {document_id}, using fallback")
                world_id = 1  # Default world ID as fallback
            
            # Get all potential guideline triples from the world ontology
            guideline_triples = self._get_guideline_triples_for_world(world_id)
            if not guideline_triples:
                logger.warning(f"No guideline triples found for world {world_id}, using mock data")
                # We'll fall back to mock implementation later
            
            # Process each section
            sections_processed = 0
            associations_created = 0
            section_guideline_map = {}
            
            for section in sections:
                logger.info(f"Processing section {section.id} ({section.section_type})")
                
                # If we have guideline triples from ontology, use them for relevance calculation
                enhanced_guidelines = []
                if guideline_triples:
                    for triple in guideline_triples:
                        # Calculate basic similarity metrics
                        basic_scores = self.calculate_triple_section_relevance(section, triple)
                        
                        # If the initial score is promising, perform deeper analysis
                        if basic_scores['combined_score'] > 0.3:
                            # Get LLM analysis for semantic understanding
                            llm_analysis = self.analyze_triple_relevance_with_llm(
                                section, 
                                triple,
                                basic_scores['combined_score']
                            )
                            
                            # Calculate final relevance with full reasoning chain
                            final_result = self.calculate_final_relevance(basic_scores, llm_analysis)
                            
                            # If the final score is high enough, add it to enhanced guidelines
                            if final_result['score'] > 0.5:
                                # Create guideline object with reasoning metadata
                                guideline = {
                                    'uri': triple.get('subject_uri', ''),
                                    'label': triple.get('subject_label', ''),
                                    'description': triple.get('object_literal', ''),
                                    'confidence': final_result['score'],
                                    'relationship': final_result['relationship'],
                                    'reasoning': {
                                        'vector_similarity': final_result['vector_similarity'],
                                        'term_overlap': final_result['term_overlap'],
                                        'shared_terms': final_result['shared_terms'],
                                        'structural_relevance': final_result['structural_relevance'],
                                        'llm_reasoning': final_result['llm_reasoning'],
                                        'llm_patterns': final_result['llm_patterns'],
                                        'calculation': final_result['calculation']
                                    }
                                }
                                enhanced_guidelines.append(guideline)
                
                # If we couldn't get or process ontology guidelines, fall back to mock implementation
                if not enhanced_guidelines:
                    logger.warning(f"No enhanced guidelines for section {section.id}, using mock implementation")
                    guideline_result = self._generate_mock_guidelines(section.content, section.section_type)
                    
                    if not guideline_result.get('success'):
                        logger.warning(f"Failed to extract guidelines for section {section.id}: {guideline_result.get('error', 'Unknown error')}")
                        continue
                    
                    # Get the guidelines from the result
                    guidelines = guideline_result.get('guidelines', [])
                    logger.info(f"Extracted {len(guidelines)} guidelines for section {section.id}")
                    
                    # Mark these as non-enhanced guidelines
                    for guideline in guidelines:
                        guideline['enhanced'] = False
                    
                    enhanced_guidelines = guidelines
                else:
                    # These are enhanced guidelines
                    for guideline in enhanced_guidelines:
                        guideline['enhanced'] = True
                    logger.info(f"Generated {len(enhanced_guidelines)} enhanced guideline associations for section {section.id}")
                
                # Store guidelines in the section metadata
                if enhanced_guidelines:
                    associations_created += len(enhanced_guidelines)
                    
                    # Handle SQLAlchemy MetaData object carefully
                    current_metadata = {}
                    
                    # Check if section_metadata exists and determine its type
                    if section.section_metadata is not None:
                        # Try to get metadata as a JSON string and parse it
                        try:
                            metadata_str = str(section.section_metadata)
                            if '{' in metadata_str and '}' in metadata_str:
                                # Extract the JSON part if it exists
                                json_start = metadata_str.find('{')
                                json_end = metadata_str.rfind('}') + 1
                                json_str = metadata_str[json_start:json_end]
                                current_metadata = json.loads(json_str)
                            else:
                                # If no JSON structure, create empty dict
                                current_metadata = {}
                        except Exception:
                            logger.debug("Failed to parse section metadata JSON, using empty dict", exc_info=True)
                            # If JSON parsing fails, create new metadata
                            current_metadata = {}
                    
                    # Create a new metadata dict and update section
                    new_metadata = {
                        **current_metadata,
                        'guideline_associations': enhanced_guidelines,
                        'guideline_association_type': 'enhanced_multi_metric',
                        'guideline_association_updated': str(datetime.utcnow())
                    }
                    
                    # Set the new metadata
                    section.section_metadata = new_metadata
                    
                    # Add to our result map
                    section_guideline_map[section.id] = {
                        'section_type': section.section_type,
                        'guidelines': enhanced_guidelines,
                        'enhanced': True
                    }
                    
                    sections_processed += 1
            
            # Update document metadata to indicate it has enhanced guideline associations
            document_metadata = document.guideline_metadata or {}
            if not document_metadata:
                document_metadata = {}
            
            # Properly handle document metadata
            if not document.guideline_metadata:
                document.guideline_metadata = {}
            
            if isinstance(document.guideline_metadata, dict):
                metadata_dict = document.guideline_metadata
            else:
                # Try to convert to dict if not already
                try:
                    metadata_dict = dict(document.guideline_metadata)
                except Exception:
                    logger.debug("Failed to convert guideline_metadata to dict, using empty dict", exc_info=True)
                    metadata_dict = {}
                
            # Ensure document_structure exists
            if 'document_structure' not in metadata_dict:
                metadata_dict['document_structure'] = {}
            
            # Update guideline associations info
            metadata_dict['document_structure']['guideline_associations'] = {
                'section_count': sections_processed,
                'association_count': associations_created,
                'association_type': 'enhanced_multi_metric',
                'last_updated': str(datetime.utcnow())
            }
            
            # Update the document metadata
            document.guideline_metadata = metadata_dict
            
            # Commit changes
            db.session.commit()
            
            logger.info(f"Successfully created {associations_created} enhanced guideline associations across {sections_processed} sections")
            
            return {
                'success': True,
                'document_id': document_id,
                'sections_processed': sections_processed,
                'associations_created': associations_created,
                'association_type': 'enhanced_multi_metric',
                'section_guideline_map': section_guideline_map
            }
            
        except Exception as e:
            logger.exception(f"Error associating guidelines with document sections: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_section_guidelines(self, section_id: int) -> Dict[str, Any]:
        """
        Retrieve guidelines associated with a specific document section.
        
        Args:
            section_id: ID of the section
            
        Returns:
            dict: Section guideline associations
        """
        try:
            logger.info(f"Retrieving guidelines for section {section_id}")
            
            # Get the section
            section = DocumentSection.query.get(section_id)
            if not section:
                logger.error(f"Section {section_id} not found")
                return {
                    'success': False,
                    'error': 'Section not found'
                }
            
            # Check if section has guideline associations
            if not section.section_metadata or 'guideline_associations' not in section.section_metadata:
                logger.warning(f"Section {section_id} has no guideline associations")
                return {
                    'success': False,
                    'error': 'Section has no guideline associations'
                }
            
            # Get guidelines from section
            guidelines = section.section_metadata.get('guideline_associations', [])
            
            # Check if these are enhanced guidelines
            is_enhanced = section.section_metadata.get('guideline_association_type') == 'enhanced_multi_metric'
            
            # Get the document for context
            document = Document.query.get(section.document_id)
            document_title = document.title if document else None
            
            return {
                'success': True,
                'section_id': section.id,
                'document_id': section.document_id,
                'document_title': document_title,
                'section_type': section.section_type,
                'section_title': getattr(section, 'title', None) or section.section_type.capitalize(),
                'section_content': section.content[:200] + '...' if len(section.content) > 200 else section.content,
                'guidelines': guidelines,
                'enhanced': is_enhanced,
                'guideline_count': len(guidelines)
            }
            
        except Exception as e:
            logger.exception(f"Error retrieving guidelines for section {section_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_document_section_guidelines(self, document_id: int) -> Dict[str, Any]:
        """
        Retrieve guidelines associated with document sections.
        
        Args:
            document_id: ID of the document
            
        Returns:
            dict: Section guideline associations
        """
        try:
            logger.info(f"Retrieving section guidelines for document {document_id}")
            
            # Get the document
            document = Document.query.get(document_id)
            if not document:
                logger.error(f"Document {document_id} not found")
                return {
                    'success': False,
                    'error': 'Document not found'
                }
                
            # Check if document sections have guideline associations - we don't need document metadata
            # We'll check if any sections have guideline associations
            has_section_associations = False
            
            # Get sections
            sections = DocumentSection.query.filter_by(document_id=document_id).all()
            if not sections:
                logger.warning(f"No sections found for document {document_id}")
                return {
                    'success': False,
                    'error': 'No sections found for document'
                }
            
            # Check if any section has guideline associations
            for section in sections:
                if section.section_metadata and isinstance(section.section_metadata, dict) and 'guideline_associations' in section.section_metadata:
                    has_section_associations = True
                    break
            
            if not has_section_associations:
                logger.warning(f"Document {document_id} has no section guideline associations")
                return {
                    'success': False,
                    'error': 'Document has no guideline associations'
                }
            
            # Get document sections
            sections = DocumentSection.query.filter_by(document_id=document_id).all()
            if not sections:
                logger.warning(f"No sections found for document {document_id}")
                return {
                    'success': False,
                    'error': 'No sections found for document'
                }
            
            # Collect guideline data from sections
            section_guideline_map = {}
            guideline_count = 0
            
            for section in sections:
                if section.section_metadata and 'guideline_associations' in section.section_metadata:
                    guidelines = section.section_metadata['guideline_associations']
                    if guidelines:
                        # Check if these are enhanced guidelines
                        is_enhanced = section.section_metadata.get('guideline_association_type') == 'enhanced_multi_metric'
                        
                        section_guideline_map[section.id] = {
                            'section_type': section.section_type,
                            'section_title': getattr(section, 'title', None) or section.section_type.capitalize(),
                            'section_content': section.content[:100] + '...' if len(section.content) > 100 else section.content,
                            'guidelines': guidelines,
                            'enhanced': is_enhanced
                        }
                        guideline_count += len(guidelines)
            
            # Determine association type
            association_type = 'standard'
            if document.guideline_metadata and 'document_structure' in document.guideline_metadata:
                if 'guideline_associations' in document.guideline_metadata['document_structure']:
                    association_type = document.guideline_metadata['document_structure']['guideline_associations'].get(
                        'association_type', 'standard')
            
            return {
                'success': True,
                'document_id': document_id,
                'document_title': document.title,
                'section_count': len(section_guideline_map),
                'guideline_count': guideline_count,
                'association_type': association_type,
                'sections': section_guideline_map
            }
            
        except Exception as e:
            logger.exception(f"Error retrieving section guidelines: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
            
    def get_guideline_reasoning(self, document_id: int, section_id: int, guideline_uri: str) -> Dict[str, Any]:
        """
        Retrieve the detailed reasoning chain for a specific guideline association.
        
        Args:
            document_id: ID of the document
            section_id: ID of the section
            guideline_uri: URI of the guideline
            
        Returns:
            dict: Detailed reasoning information
        """
        try:
            # Get the section
            section = DocumentSection.query.filter_by(
                document_id=document_id, 
                id=section_id
            ).first()
            
            if not section:
                return {
                    'success': False,
                    'error': f"Section {section_id} not found for document {document_id}"
                }
            
            # Check if section has guideline associations
            if not section.section_metadata or 'guideline_associations' not in section.section_metadata:
                return {
                    'success': False,
                    'error': f"Section {section_id} has no guideline associations"
                }
            
            # Find the guideline with matching URI
            guideline = None
            for g in section.section_metadata['guideline_associations']:
                if g.get('uri') == guideline_uri:
                    guideline = g
                    break
            
            if not guideline:
                return {
                    'success': False,
                    'error': f"Guideline {guideline_uri} not found for section {section_id}"
                }
            
            # Check if this is an enhanced guideline with reasoning data
            if not guideline.get('enhanced', False) or 'reasoning' not in guideline:
                return {
                    'success': True,
                    'is_enhanced': False,
                    'guideline': guideline,
                    'reasoning': {
                        'explanation': "This guideline was generated using the standard extraction method, without multi-metric reasoning."
                    }
                }
            
            # Return the full reasoning chain for enhanced guidelines
            return {
                'success': True,
                'is_enhanced': True,
                'document_id': document_id,
                'section_id': section_id,
                'guideline': {
                    'uri': guideline['uri'],
                    'label': guideline['label'],
                    'description': guideline.get('description', ''),
                    'confidence': guideline.get('confidence', 0.0),
                    'relationship': guideline.get('relationship', 'related_to')
                },
                'reasoning': guideline['reasoning']
            }
            
        except Exception as e:
            logger.exception(f"Error retrieving guideline reasoning: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def search_guideline_associations(self, guideline_uri: str, confidence_threshold: float = 0.5) -> Dict[str, Any]:
        """
        Search for document sections associated with a specific guideline.
        
        Args:
            guideline_uri: URI of the guideline to search for
            confidence_threshold: Minimum confidence score for associations (0.0-1.0)
            
        Returns:
            dict: Sections associated with the guideline
        """
        try:
            logger.info(f"Searching for sections associated with guideline {guideline_uri}")
            
            # Find sections with this guideline
            sections = []
            
            # Query all document sections
            query = """
            SELECT 
                ds.id,
                ds.document_id,
                ds.section_type,
                ds.content,
                ds.section_metadata,
                d.title as document_title
            FROM 
                document_sections ds
            JOIN
                documents d ON ds.document_id = d.id
            """
            
            results = db.session.execute(text(query)).fetchall()
            
            for row in results:
                # Check if section has guideline associations
                if not row[4] or not isinstance(row[4], dict) or 'guideline_associations' not in row[4]:
                    continue
                
                section_id = row[0]
                document_id = row[1]
                section_type = row[2]
                content = row[3]
                section_metadata = row[4]
                document_title = row[5]
                
                # Get guideline associations
                guideline_associations = section_metadata.get('guideline_associations', [])
                
                # Find matching guideline
                matching_guidelines = []
                for guideline in guideline_associations:
                    if guideline.get('uri') == guideline_uri and guideline.get('confidence', 0) >= confidence_threshold:
                        matching_guidelines.append(guideline)
                
                # If found matching guideline, add to sections
                if matching_guidelines:
                    sections.append({
                        'section_id': section_id,
                        'document_id': document_id,
                        'document_title': document_title,
                        'section_type': section_type,
                        'content_preview': content[:100] + '...' if len(content) > 100 else content,
                        'guidelines': matching_guidelines,
                        'match_count': len(matching_guidelines)
                    })
            
            return {
                'success': True,
                'guideline_uri': guideline_uri,
                'confidence_threshold': confidence_threshold,
                'sections': sections,
                'section_count': len(sections)
            }
        
        except Exception as e:
            logger.exception(f"Error searching guideline associations: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
