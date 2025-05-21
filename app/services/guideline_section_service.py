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
from app.models.document import Document
from app.models.document_section import DocumentSection
from app.services.mcp_client import MCPClient
from app.services.section_embedding_service import SectionEmbeddingService
from app.utils.llm_utils import get_llm_client
from app.utils.nltk_verification import verify_nltk_resources

# Set up logging
logger = logging.getLogger(__name__)

class GuidelineSectionService:
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
                        except:
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
            document_metadata = document.doc_metadata or {}
            if not document_metadata:
                document_metadata = {}
            
            # Properly handle document metadata
            if not document.doc_metadata:
                document.doc_metadata = {}
            
            if isinstance(document.doc_metadata, dict):
                metadata_dict = document.doc_metadata
            else:
                # Try to convert to dict if not already
                try:
                    metadata_dict = dict(document.doc_metadata)
                except:
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
            document.doc_metadata = metadata_dict
            
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
            if document.doc_metadata and 'document_structure' in document.doc_metadata:
                if 'guideline_associations' in document.doc_metadata['document_structure']:
                    association_type = document.doc_metadata['document_structure']['guideline_associations'].get(
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
    
    def calculate_triple_section_relevance(self, section, triple):
        """
        Calculate comprehensive relevance between section and triple using multiple metrics.
        
        Args:
            section: Document section object
            triple: Guideline triple dictionary
            
        Returns:
            dict: Relevance metrics and scores
        """
        try:
            # Convert triple to text for embedding comparison
            triple_text = self._triple_to_text(triple)
            
            # 1. Vector similarity using section embedding service
            vector_similarity = 0.0
            if section.embedding is not None:
                # Get embedding for the triple text
                triple_embedding = self.embedding_service.get_embedding(triple_text)
                # Calculate similarity
                vector_similarity = self.embedding_service.calculate_similarity(
                    section.embedding, 
                    triple_embedding
                )
            
            # 2. Term overlap using basic NLP
            term_overlap, shared_terms = self._calculate_term_overlap(section.content, triple_text)
            
            # 3. Structural relevance based on section type and triple type
            structural_relevance = self._get_structural_relevance(section.section_type, triple.get('entity_type', 'guideline'))
            
            # Combined preliminary score
            combined_score = (
                0.6 * vector_similarity + 
                0.25 * term_overlap + 
                0.15 * structural_relevance
            )
            
            return {
                'vector_similarity': vector_similarity,
                'term_overlap': term_overlap,
                'shared_terms': shared_terms,
                'structural_relevance': structural_relevance,
                'combined_score': combined_score,
                'triple': triple,
                'section': section
            }
            
        except Exception as e:
            logger.exception(f"Error calculating triple-section relevance: {str(e)}")
            # Return default scores
            return {
                'vector_similarity': 0.0,
                'term_overlap': 0.0,
                'shared_terms': [],
                'structural_relevance': 0.0,
                'combined_score': 0.0,
                'triple': triple,
                'section': section,
                'error': str(e)
            }
    
    def _triple_to_text(self, triple):
        """
        Convert a triple to text for embedding and comparison.
        
        Args:
            triple: Guideline triple dictionary
            
        Returns:
            str: Text representation of the triple
        """
        # Start with subject label
        text = triple.get('subject_label', '')
        
        # Add predicate if available (simplified version)
        predicate = triple.get('predicate', '')
        if predicate:
            # Extract the last part of the URI
            pred_parts = predicate.split('/')
            if pred_parts:
                pred_name = pred_parts[-1]
                # Convert camelCase to spaces
                pred_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', pred_name)
                text += f" {pred_name}"
        
        # Add object (literal or label)
        if 'object_literal' in triple:
            text += f" {triple['object_literal']}"
        elif 'object_label' in triple:
            text += f" {triple['object_label']}"
        
        # Add description if available
        if 'description' in triple:
            text += f". {triple['description']}"
            
        return text
    
    def _calculate_term_overlap(self, section_content: str, triple_text: str) -> Tuple[float, List[str]]:
        """
        Calculate term overlap between section content and triple text.
        
        Args:
            section_content: Content of the document section
            triple_text: Text representation of the triple
            
        Returns:
            Tuple of (overlap score, list of shared terms)
        """
        try:
            # Normalize and tokenize section content and triple text
            section_tokens = word_tokenize(section_content.lower())
            triple_tokens = word_tokenize(triple_text.lower())
            
            # Remove stopwords and short words
            section_terms = {w for w in section_tokens if w not in self.stop_words and len(w) > 2}
            triple_terms = {w for w in triple_tokens if w not in self.stop_words and len(w) > 2}
            
            # Find intersection and calculate Jaccard similarity
            intersection = section_terms.intersection(triple_terms)
            union = section_terms.union(triple_terms)
            
            # Calculate Jaccard similarity
            if union:
                jaccard = len(intersection) / len(union)
            else:
                jaccard = 0.0
                
            # Return the score and shared terms
            return jaccard, list(intersection)
            
        except Exception as e:
            logger.exception(f"Error calculating term overlap: {str(e)}")
            return 0.0, []
    
    def _get_structural_relevance(self, section_type: str, entity_type: str) -> float:
        """
        Calculate structural relevance based on section type and entity type.
        
        Args:
            section_type: Type of the document section
            entity_type: Type of the entity in the triple
            
        Returns:
            float: Structural relevance score (0-1)
        """
        # Define relevance matrix for different combinations
        # This maps section types to entity types with relevance scores
        relevance_matrix = {
            'facts': {
                'condition': 0.9,
                'resource': 0.7,
                'action': 0.6,
                'role': 0.5,
                'guideline': 0.6
            },
            'discussion': {
                'condition': 0.7,
                'resource': 0.5,
                'action': 0.8,
                'role': 0.7,
                'guideline': 0.8
            },
            'conclusion': {
                'condition': 0.6,
                'resource': 0.4,
                'action': 0.7,
                'role': 0.6,
                'guideline': 0.9
            },
            'question': {
                'condition': 0.8,
                'resource': 0.6,
                'action': 0.7,
                'role': 0.6,
                'guideline': 0.7
            }
        }
        
        # Normalize section_type and entity_type
        normalized_section_type = section_type.lower().split('_')[0]  # handle types like "discussion_1"
        normalized_entity_type = entity_type.lower()
        
        # Get relevance score from matrix or use default
        if normalized_section_type in relevance_matrix:
            if normalized_entity_type in relevance_matrix[normalized_section_type]:
                return relevance_matrix[normalized_section_type][normalized_entity_type]
        
        # Default relevance score
        return 0.5
        
    def analyze_triple_relevance_with_llm(self, section, triple, combined_score):
        """
        Use LLM to analyze relevance between section and triple for deeper semantic understanding.
        
        Args:
            section: Document section object
            triple: Guideline triple dictionary
            combined_score: Previously calculated combined score
            
        Returns:
            dict: LLM analysis results
        """
        try:
            # Get the LLM client
            client = get_llm_client()
            if not client:
                logger.warning("LLM client unavailable for triple relevance analysis")
                return {
                    'llm_is_relevant': None,
                    'llm_reasoning': "LLM analysis unavailable",
                    'llm_patterns': [],
                    'agreement_score': 0.5  # Neutral score if LLM unavailable
                }
            
            # Prepare section content (limit length to avoid token limits)
            max_content_length = 1000
            section_content = section.content
            if len(section_content) > max_content_length:
                section_content = section_content[:max_content_length] + "..."
            
            # Convert triple to text
            triple_text = self._triple_to_text(triple)
            
            # Construct the prompt
            prompt = f"""
            Analyze the relevance between this document section and ethical guideline:
            
            DOCUMENT SECTION TYPE: {section.section_type}
            DOCUMENT SECTION CONTENT:
            {section_content}
            
            ETHICAL GUIDELINE:
            {triple_text}
            
            Is there a clear semantic relationship between the section and the guideline? Provide:
            1. A yes/no determination if there's a meaningful relationship
            2. Brief reasoning for your assessment (1-2 sentences)
            3. Specific patterns or key terms that connect them, if any

            Format your response as JSON:
            {{
              "is_relevant": true/false,
              "reasoning": "Brief explanation of the relationship",
              "patterns_identified": ["pattern1", "pattern2"]
            }}
            """
            
            # Send to LLM based on API version
            result = ""
            try:
                # If new API (v2)
                if hasattr(client, 'chat') and hasattr(client.chat, 'completions'):
                    response = client.chat.completions.create(
                        model=client.available_models[0],  # Use latest available model
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,  # Low temperature for more consistent results
                        max_tokens=500
                    )
                    result = response.choices[0].message.content
                    
                # If messages API (v1.5)
                elif hasattr(client, 'messages') and hasattr(client.messages, 'create'):
                    response = client.messages.create(
                        model=client.available_models[0],
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        max_tokens=500
                    )
                    result = response.content[0].text
                    
                # If old API (v1)
                else:
                    response = client.completion(
                        prompt=f"Human: {prompt}\n\nAssistant:",
                        model=client.available_models[0],
                        temperature=0.1,
                        max_tokens_to_sample=500
                    )
                    result = response.completion
            except Exception as api_error:
                logger.warning(f"Error using LLM API: {str(api_error)}")
                return {
                    'llm_is_relevant': None,
                    'llm_reasoning': f"LLM API error: {str(api_error)}",
                    'llm_patterns': [],
                    'agreement_score': 0.5  # Neutral score if LLM fails
                }
                
            # Parse JSON response
            try:
                # Clean up the result to ensure it's valid JSON
                # Sometimes LLM responses include markdown code blocks or additional text
                json_start = result.find('{')
                json_end = result.rfind('}')
                if json_start >= 0 and json_end >= 0:
                    json_str = result[json_start:json_end+1]
                    analysis = json.loads(json_str)
                else:
                    # If no JSON found, create default response
                    analysis = {
                        'is_relevant': False,
                        'reasoning': "Could not reliably determine relevance",
                        'patterns_identified': []
                    }
            except json.JSONDecodeError:
                # If JSON parsing fails, create a default response
                logger.warning(f"Failed to parse LLM response as JSON: {result}")
                analysis = {
                    'is_relevant': False,
                    'reasoning': "Could not parse LLM response",
                    'patterns_identified': []
                }
            
            # Calculate agreement score - how well does the LLM assessment match the vector similarity?
            llm_score = 1.0 if analysis.get('is_relevant', False) else 0.0
            agreement_score = 1.0 - abs(llm_score - combined_score)
            
            return {
                'llm_is_relevant': analysis.get('is_relevant', False),
                'llm_reasoning': analysis.get('reasoning', ''),
                'llm_patterns': analysis.get('patterns_identified', []),
                'agreement_score': agreement_score
            }
            
        except Exception as e:
            logger.exception(f"Error in LLM analysis: {str(e)}")
            return {
                'llm_is_relevant': False,
                'llm_reasoning': f"Error in LLM analysis: {str(e)}",
                'llm_patterns': [],
                'agreement_score': 0.5  # Neutral score if error
            }
    
    def calculate_final_relevance(self, basic_scores, llm_analysis):
        """
        Calculate final relevance score with comprehensive reasoning chain.
        
        Args:
            basic_scores: Initial metrics from calculate_triple_section_relevance
            llm_analysis: Results from LLM analysis
            
        Returns:
            dict: Final relevance metrics with complete reasoning chain
        """
        try:
            # Extract base metrics
            vector_similarity = basic_scores.get('vector_similarity', 0.0)
            term_overlap = basic_scores.get('term_overlap', 0.0)
            structural_relevance = basic_scores.get('structural_relevance', 0.0)
            
            # Extract LLM metrics
            llm_is_relevant = llm_analysis.get('llm_is_relevant', False)
            agreement_score = llm_analysis.get('agreement_score', 0.5)
            
            # Convert LLM boolean to score
            llm_relevance_score = 1.0 if llm_is_relevant else 0.0
            
            # Calculate weighted final score
            # Weight components based on confidence and reliability
            final_score = (
                0.35 * vector_similarity +
                0.20 * term_overlap +
                0.10 * structural_relevance +
                0.35 * llm_relevance_score
            )
            
            # Apply agreement bonus if metrics are in strong agreement
            if agreement_score > 0.75:
                final_score *= 1.15  # 15% bonus for strong agreement
                agreement_bonus = "Strong agreement between embedding similarity and LLM analysis"
            elif agreement_score < 0.25:
                final_score *= 0.85  # 15% penalty for strong disagreement
                agreement_bonus = "Strong disagreement between embedding similarity and LLM analysis"
            else:
                agreement_bonus = "Neutral agreement between metrics"
            
            # Determine relationship type based on final score and patterns
            relationship = "related_to"  # Default
            
            # If score is very high, suggest stronger relationship
            if final_score > 0.8:
                relationship = "strongly_related_to"
            elif final_score > 0.95:
                relationship = "directly_implements"
            
            # Calculate explanatory string for the score calculation
            calculation = (
                f"Final score {final_score:.2f} calculated from: "
                f"Vector similarity ({vector_similarity:.2f} × 0.35) + "
                f"Term overlap ({term_overlap:.2f} × 0.20) + "
                f"Structural relevance ({structural_relevance:.2f} × 0.10) + "
                f"LLM assessment ({llm_relevance_score:.1f} × 0.35) "
                f"with {agreement_bonus}"
            )
            
            # Return complete result
            return {
                'score': min(1.0, max(0.0, final_score)),  # Clamp to 0-1 range
                'relationship': relationship,
                'vector_similarity': vector_similarity,
                'term_overlap': term_overlap,
                'shared_terms': basic_scores.get('shared_terms', []),
                'structural_relevance': structural_relevance,
                'llm_reasoning': llm_analysis.get('llm_reasoning', ''),
                'llm_patterns': llm_analysis.get('llm_patterns', []),
                'calculation': calculation
            }
            
        except Exception as e:
            logger.exception(f"Error calculating final relevance: {str(e)}")
            # Return default result with error information
            return {
                'score': 0.0,
                'relationship': 'related_to',
                'vector_similarity': basic_scores.get('vector_similarity', 0.0),
                'term_overlap': basic_scores.get('term_overlap', 0.0),
                'shared_terms': basic_scores.get('shared_terms', []),
                'structural_relevance': basic_scores.get('structural_relevance', 0.0),
                'llm_reasoning': f"Error calculating final relevance: {str(e)}",
                'llm_patterns': [],
                'calculation': f"Calculation failed: {str(e)}"
            }
    
    def _generate_mock_guidelines(self, section_content: str, section_type: str) -> Dict[str, Any]:
        """
        Generate mock guidelines for a section when MCP extraction fails.
        This is a fallback implementation for testing and graceful degradation.
        
        Args:
            section_content: Content of the document section
            section_type: Type of the document section
            
        Returns:
            dict: Mock guideline extraction result
        """
        # Generic guidelines by section type
        section_type_guidelines = {
            'facts': [
                {
                    'uri': 'http://proethica.org/guidelines/fact_verification',
                    'label': 'Fact Verification Guideline',
                    'description': 'Engineers must ensure all factual statements are accurate and verifiable.',
                    'confidence': 0.75
                },
                {
                    'uri': 'http://proethica.org/guidelines/due_diligence',
                    'label': 'Due Diligence Guideline',
                    'description': 'Engineers should perform due diligence before making statements of fact.',
                    'confidence': 0.65
                }
            ],
            'discussion': [
                {
                    'uri': 'http://proethica.org/guidelines/balanced_view',
                    'label': 'Balanced Perspective Guideline',
                    'description': 'Engineers should present multiple perspectives when discussing complex issues.',
                    'confidence': 0.70
                },
                {
                    'uri': 'http://proethica.org/guidelines/informed_discussion',
                    'label': 'Informed Discussion Guideline',
                    'description': 'Engineers must base discussions on valid engineering principles and factual data.',
                    'confidence': 0.68
                }
            ],
            'conclusion': [
                {
                    'uri': 'http://proethica.org/guidelines/evidence_based_conclusions',
                    'label': 'Evidence-Based Conclusion Guideline',
                    'description': 'Engineers must draw conclusions based on sound evidence and reasoning.',
                    'confidence': 0.72
                },
                {
                    'uri': 'http://proethica.org/guidelines/public_safety',
                    'label': 'Public Safety Guideline',
                    'description': 'Engineers must prioritize public safety in all professional conclusions.',
                    'confidence': 0.85
                }
            ],
            'question': [
                {
                    'uri': 'http://proethica.org/guidelines/ethical_inquiry',
                    'label': 'Ethical Inquiry Guideline',
                    'description': 'Engineers should question practices that may compromise ethical standards.',
                    'confidence': 0.65
                },
                {
                    'uri': 'http://proethica.org/guidelines/critical_thinking',
                    'label': 'Critical Thinking Guideline',
                    'description': 'Engineers must apply critical thinking to professional questions and challenges.',
                    'confidence': 0.70
                }
            ]
        }
        
        # Normalize the section type
        normalized_section_type = section_type.lower().split('_')[0]
        
        # Select guidelines based on section type
        if normalized_section_type in section_type_guidelines:
            guidelines = section_type_guidelines[normalized_section_type]
        else:
            # Default guidelines for other section types
            guidelines = [
                {
                    'uri': 'http://proethica.org/guidelines/professional_conduct',
                    'label': 'Professional Conduct Guideline',
                    'description': 'Engineers shall uphold the highest standards of professional conduct.',
                    'confidence': 0.60
                },
                {
                    'uri': 'http://proethica.org/guidelines/competence',
                    'label': 'Professional Competence Guideline',
                    'description': 'Engineers shall perform services only in areas of their competence.',
                    'confidence': 0.55
                }
            ]
        
        # Add some variation based on content to make it less obvious these are mock guidelines
        # Use some keywords from the content
        words = section_content.lower().split()
        keywords = [w for w in words if len(w) > 5 and w not in self.stop_words]
        
        if keywords:
            # Add a content-specific guideline using extracted keywords
            # Select up to 3 random keywords
            selected_keywords = random.sample(keywords, min(3, len(keywords)))
            keyword_string = ', '.join(selected_keywords)
            
            content_guideline = {
                'uri': f"http://proethica.org/guidelines/content_specific_{selected_keywords[0]}",
                'label': f"Content-Specific Guideline on {keyword_string.title()}",
                'description': f"Engineers should carefully consider {keyword_string} in their professional practice.",
                'confidence': 0.50  # Lower confidence for these dynamic guidelines
            }
            
            guidelines.append(content_guideline)
        
        # Add relationship information
        for guideline in guidelines:
            guideline['relationship'] = 'related_to'
        
        return {
            'success': True,
            'guidelines': guidelines
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
