"""
FIXED Experiment Prediction Service.

This service extends the LLM service to support the ProEthica experiment,
implementing both baseline and enhanced prompting strategies for case prediction.

CRITICAL FIX: Ensures Facts section is always included when available in DocumentSection records.
"""

import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.models.document import Document
from app.models.document_section import DocumentSection
from app.services.llm_service import LLMService
from app.services.section_embedding_service import SectionEmbeddingService
from app.services.guideline_section_service import GuidelineSectionService
from ttl_triple_association.section_triple_association_service import SectionTripleAssociationService
from app.services.experiment.find_similar_cases import find_similar_cases

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PredictionService:
    """Service for generating case predictions under different experimental conditions."""
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Initialize the prediction service.
        
        Args:
            llm_service: Optional LLMService instance
        """
        self.llm_service = llm_service or LLMService()
        self.embedding_service = SectionEmbeddingService()
        self.guideline_service = GuidelineSectionService()
        self.triple_association_service = SectionTripleAssociationService()
        
    def get_document_sections(self, document_id: int, leave_out_conclusion: bool = True) -> Dict[str, str]:
        """
        Get document sections for a case, optionally excluding the conclusion.
        
        FIXED: Always checks DocumentSection records as primary source or fallback.
        
        Args:
            document_id: ID of the document
            leave_out_conclusion: Whether to exclude conclusion section
            
        Returns:
            Dictionary of section types to content
        """
        # Get the document
        document = Document.query.get(document_id)
        if not document:
            logger.error(f"Document with ID {document_id} not found")
            return {}
        
        # Initialize sections dictionary
        sections = {}
        
        # CRITICAL FIX: Always try DocumentSection records first
        logger.info(f"Getting sections for document {document_id} from DocumentSection records")
        doc_sections = DocumentSection.query.filter_by(document_id=document_id).all()
        
        if doc_sections:
            logger.info(f"Found {len(doc_sections)} DocumentSection records for document {document_id}")
            for section in doc_sections:
                section_type = section.section_type.lower() if section.section_type else ''
                
                # Skip conclusion if leave_out_conclusion is True
                if leave_out_conclusion and section_type == 'conclusion':
                    logger.info(f"Skipping conclusion section for document {document_id}")
                    continue
                
                # Ensure we have content
                content = section.content or ''
                
                # Add or merge section content
                if section_type in sections:
                    sections[section_type] += "\n\n" + content
                else:
                    sections[section_type] = content
                    
                logger.info(f"Added section '{section_type}' with {len(content)} characters")
        
        # If we found sections from DocumentSection records, use them
        if sections:
            logger.info(f"Retrieved sections from DocumentSection records: {list(sections.keys())}")
            return sections
        
        # Fallback: Try metadata if DocumentSection records are empty
        logger.warning(f"No DocumentSection records found for document {document_id}, trying metadata")
        
        # Get document metadata
        if not document.doc_metadata or not isinstance(document.doc_metadata, dict):
            logger.error(f"Document {document_id} has no valid metadata and no DocumentSection records")
            return {}
            
        metadata = document.doc_metadata
        
        # Case 1: New format with document_structure
        if 'document_structure' in metadata and 'sections' in metadata['document_structure']:
            logger.info(f"Using document_structure format for document {document_id}")
            doc_sections = metadata['document_structure']['sections']
            
            for section_id, section_data in doc_sections.items():
                # Check if section_data is a dictionary
                if isinstance(section_data, dict):
                    section_type = section_data.get('type', '').lower()
                    content = section_data.get('content', '')
                else:
                    # Handle case where section_data is a string
                    section_type = 'text'
                    content = str(section_data)
                
                # Skip conclusion if leave_out_conclusion is True
                if leave_out_conclusion and section_type == 'conclusion':
                    continue
                    
                # Add or merge section content
                if section_type in sections:
                    sections[section_type] += "\n\n" + content
                else:
                    sections[section_type] = content
        
        # Case 2: Legacy format with top-level sections
        elif 'sections' in metadata:
            logger.info(f"Using legacy sections format for document {document_id}")
            for section_key, section_data in metadata['sections'].items():
                # Handle direct string content (Case 252's format)
                if isinstance(section_data, str):
                    section_type = section_key.lower()  # Use the key as section type
                    content = section_data              # Content is the string directly
                elif isinstance(section_data, dict):
                    # Handle dictionary format
                    section_type = section_data.get('type', section_key).lower()
                    content = section_data.get('content', '')
                else:
                    # Handle other formats
                    section_type = section_key.lower()
                    content = str(section_data)
                
                # Skip conclusion if leave_out_conclusion is True
                if leave_out_conclusion and section_type == 'conclusion':
                    continue
                    
                # Add or merge section content
                if section_type in sections:
                    sections[section_type] += "\n\n" + content
                else:
                    sections[section_type] = content
        
        # Log what sections we found for debugging
        logger.info(f"Final sections for document {document_id}: {list(sections.keys())}")
        if 'facts' in sections:
            logger.info(f"✓ Facts section found with {len(sections['facts'])} characters")
        else:
            logger.warning(f"❌ Facts section NOT found for document {document_id}")
        
        return sections
    
    def generate_conclusion_prediction(self, document_id: int, use_ontology: bool = True) -> Dict[str, Any]:
        """
        Generate a prediction for the conclusion section.
        
        Args:
            document_id: ID of the document
            use_ontology: Whether to use ontology enhancement (default: True)
            
        Returns:
            Dictionary with prediction results
        """
        try:
            # Get the document
            document = Document.query.get(document_id)
            if not document:
                return {
                    'success': False,
                    'error': f"Document with ID {document_id} not found"
                }
                
            # Get document sections (excluding conclusion)
            sections = self.get_document_sections(document_id, leave_out_conclusion=True)
            
            if not sections:
                return {
                    'success': False,
                    'error': "No sections found for document"
                }
                
            # Get ontology entities and similar cases only if using ontology
            if use_ontology:
                ontology_entities = self.get_section_ontology_entities(document_id, sections)
                similar_cases = self._find_similar_cases(document_id, limit=3)
                condition = 'proethica'
            else:
                ontology_entities = {}
                similar_cases = []
                condition = 'baseline'

            # Construct specialized conclusion prediction prompt
            prompt = self._construct_conclusion_prediction_prompt(document, sections, ontology_entities, similar_cases, use_ontology)

            # Generate prediction using LLM
            logger.info(f"Generating conclusion prediction for document {document_id}")
            response = self.llm_service.llm.invoke(prompt)

            # Extract just the conclusion from the response
            conclusion = self._extract_conclusion(response)
            
            # Optional: Validate the conclusion against ontology constraints
            validation_results = self._validate_conclusion(conclusion, ontology_entities)

            # Return results
            return {
                'success': True,
                'document_id': document_id,
                'condition': condition,
                'target': 'conclusion',
                'prediction': conclusion,
                'full_response': response,
                'prompt': prompt,
                'timestamp': datetime.utcnow().isoformat(),
                'metadata': {
                    'sections_included': list(sections.keys()),
                    'ontology_entities': self._summarize_ontology_entities(ontology_entities),
                    'similar_cases': [case['title'] for case in similar_cases],
                    'validation_metrics': validation_results
                }
            }

        except Exception as e:
            logger.exception(f"Error generating conclusion prediction: {str(e)}")
            return {
                'success': False,
                'error': f"Error generating prediction: {str(e)}"
            }
    
    def _construct_conclusion_prediction_prompt(self, document: Document, 
                                            sections: Dict[str, str],
                                            ontology_entities: Dict[str, List[Dict]],
                                            similar_cases: List[Dict[str, Any]],
                                            use_ontology: bool = True) -> str:
        """
        Construct a specialized prompt for conclusion prediction.
        
        Args:
            document: Document object
            sections: Dictionary of section types to content
            ontology_entities: Dictionary of section types to ontology entities
            similar_cases: List of similar cases for precedent
        
        Returns:
            Enhanced prompt string
        """
        prompt = f"""
        You are an AI assistant with expertise in engineering ethics, tasked with predicting the conclusion for an engineering ethics case from the National Society of Professional Engineers (NSPE) Board of Ethical Review.
        
        CASE INFORMATION:
        Title: {document.title}
        """
        
        # Add FACTS section
        prompt += "\n\n# FACTS:"
        if 'facts' in sections:
            prompt += f"\n{sections['facts']}"
            logger.info(f"✓ Added Facts section to prompt ({len(sections['facts'])} chars)")
        else:
            prompt += "\n[No facts section available]"
            logger.warning("❌ No Facts section available for prompt")
        
        # Add relevant ontology concepts for facts
        fact_entities = ontology_entities.get('facts', [])
        if fact_entities:
            prompt += "\n\nRelevant factual concepts:"
            # Include up to 5 most relevant fact entities
            for entity in fact_entities[:5]:
                prompt += f"\n- {entity['subject']} {entity['predicate']} {entity['object']}"
        
        # Add ISSUES section
        prompt += "\n\n# QUESTION:"
        if 'question' in sections:
            prompt += f"\n{sections['question']}"
        else:
            prompt += "\n[No question section available]"
        
        # Add relevant ontology concepts for issues
        issue_entities = ontology_entities.get('question', [])
        if issue_entities:
            prompt += "\n\nRelevant ethical issues:"
            # Include up to 5 most relevant issue entities
            for entity in issue_entities[:5]:
                prompt += f"\n- {entity['subject']} {entity['predicate']} {entity['object']}"
        
        # Add REFERENCES section
        if 'references' in sections:
            prompt += "\n\n# REFERENCES:"
            prompt += f"\n{sections['references']}"
        
        # Add DISCUSSION section if available
        if 'discussion' in sections:
            prompt += "\n\n# DISCUSSION:"
            prompt += f"\n{sections['discussion']}"
        
        # Add relevant ontology concepts for rules and principles
        rule_entities = []
        for section_type, entities in ontology_entities.items():
            if section_type in ['references', 'discussion']:
                rule_entities.extend(entities)
        
        if rule_entities:
            # Sort by relevance score
            rule_entities = sorted(rule_entities, key=lambda x: x.get('score', 0.0), reverse=True)
            
            prompt += "\n\n# RELEVANT ETHICAL PRINCIPLES:"
            # Include up to 10 most relevant rule entities
            for entity in rule_entities[:10]:
                prompt += f"\n- {entity['subject']} {entity['predicate']} {entity['object']}"
        
        # Add similar cases as precedents if available
        if similar_cases:
            prompt += "\n\n# RELEVANT PRECEDENT CASES:"
            for case in similar_cases:
                prompt += f"\n\nCase: {case['title']}"
                if 'outcome' in case:
                    prompt += f"\nOutcome: {case['outcome']}"
                if 'summary' in case:
                    prompt += f"\nSummary: {case['summary']}"
        
        # Add conclusion prediction request
        prompt += """
        
        # TASK:
        Based on the information provided, generate the conclusion section for this engineering ethics case.
        
        Your conclusion should:
        1. Clearly state whether the conduct described is ethical or unethical according to the NSPE Code of Ethics
        2. Provide a detailed justification for this determination
        3. Reference specific sections of the NSPE Code of Ethics that support your conclusion
        4. Use formal language appropriate for an official ethics review board decision
        
        Format your conclusion as an official NSPE Board of Ethical Review conclusion paragraph.
        """
        
        return prompt
    
    def _extract_conclusion(self, response_obj) -> str:
        """
        Extract just the conclusion part from the LLM response.
        
        Args:
            response_obj: The full LLM response (may be a string or AIMessage object)
            
        Returns:
            Extracted conclusion text
        """
        # Handle different response types
        if hasattr(response_obj, 'content'):
            response = response_obj.content
        elif isinstance(response_obj, dict) and 'content' in response_obj:
            response = response_obj['content']
        else:
            response = str(response_obj)
            
        # Try to extract text between "CONCLUSION" and next heading
        import re
        conclusion_match = re.search(r'(?i)#*\s*CONCLUSION:?\s*(.*?)(?=#|\Z)', response, re.DOTALL)
        
        if conclusion_match:
            return conclusion_match.group(1).strip()
        
        # If no explicit conclusion heading, return the whole response
        return response
    
    def _validate_conclusion(self, conclusion: str, 
                           ontology_entities: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """
        Validate conclusion against ontology constraints.
        
        Args:
            conclusion: Generated conclusion text
            ontology_entities: Dictionary of section types to ontology entities
        
        Returns:
            Validation results and confidence metrics
        """
        # Extract all relevant entities for validation
        all_entities = []
        for section_type, entities in ontology_entities.items():
            for entity in entities:
                # Add subject and object terms
                if 'subject' in entity:
                    all_entities.append(entity['subject'])
                if 'object' in entity:
                    all_entities.append(entity['object'])
        
        # Check which entities are mentioned in the conclusion
        entity_mentions = 0
        mentioned_entities = []
        
        for entity in all_entities:
            if entity in conclusion:
                entity_mentions += 1
                mentioned_entities.append(entity)
        
        # Calculate metrics
        total_entities = len(all_entities)
        mention_ratio = entity_mentions / total_entities if total_entities > 0 else 0
        
        return {
            'entity_mentions': entity_mentions,
            'total_entities': total_entities,
            'mention_ratio': mention_ratio,
            'mentioned_entities': mentioned_entities[:10],  # Limit to first 10
            'validation_status': 'passed' if mention_ratio > 0.1 else 'failed'
        }
    
    def get_section_ontology_entities(self, document_id: int, 
                                     sections: Dict[str, str]) -> Dict[str, List[Dict]]:
        """
        Get ontology entities associated with document sections.
        
        Args:
            document_id: ID of the document
            sections: Dictionary of section types to content
        
        Returns:
            Dictionary mapping section types to associated ontology entities
        """
        # Initialize results dictionary
        ontology_entities = {}
        
        try:
            # Get section IDs for the document
            section_ids = []
            for section_type in sections:
                # Query DocumentSection records for this document and section type
                doc_sections = DocumentSection.query.filter_by(
                    document_id=document_id,
                    section_type=section_type
                ).all()
                
                section_ids.extend([s.id for s in doc_sections])
            
            # If no section IDs found, return empty dictionary
            if not section_ids:
                logger.warning(f"No section IDs found for document {document_id}")
                return ontology_entities
                
            # Query triple associations for these section IDs
            for section_id in section_ids:
                # Get section type for this section ID
                section = DocumentSection.query.get(section_id)
                if not section:
                    continue
                    
                section_type = section.section_type.lower() if section.section_type else ''

                # Query associated triples using get_section_associations
                associations_result = self.triple_association_service.get_section_associations(section_id)
                
                # Extract triples from associations result
                triples = []
                if associations_result and 'associations' in associations_result:
                    triples = associations_result['associations']

                # Process and group triples
                if triples:
                    if section_type not in ontology_entities:
                        ontology_entities[section_type] = []

                    for triple in triples:
                        # Extract and process triple components
                        entity = {
                            'subject': triple.get('subject', ''),
                            'predicate': triple.get('predicate', ''),
                            'object': triple.get('object', ''),
                            'score': triple.get('score', 0.0),
                            'source': triple.get('source', '')
                        }
                        
                        # Add to section entities
                        ontology_entities[section_type].append(entity)
            
            # Calculate relevance scores and sort entities by relevance
            for section_type in ontology_entities:
                ontology_entities[section_type] = sorted(
                    ontology_entities[section_type],
                    key=lambda x: x.get('score', 0.0),
                    reverse=True
                )
                
            return ontology_entities
                
        except Exception as e:
            logger.exception(f"Error retrieving ontology entities: {str(e)}")
            return ontology_entities

    def _summarize_ontology_entities(self, ontology_entities: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """
        Create a summary of ontology entities for metadata.
        
        Args:
            ontology_entities: Dictionary of section types to ontology entities
        
        Returns:
            Summary information about ontology entities
        """
        summary = {}
        total_entities = 0
        
        # Count entities per section type
        for section_type, entities in ontology_entities.items():
            summary[section_type] = len(entities)
            total_entities += len(entities)
            
        # Add total count
        summary['total'] = total_entities
        
        return summary

    def _find_similar_cases(self, document_id: int, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Find similar cases based on content similarity.

        Args:
            document_id: ID of the document to find similar cases for
            limit: Maximum number of similar cases to return

        Returns:
            List of dictionaries with similar case information
        """
        # Use the separate find_similar_cases module for implementation
        return find_similar_cases(
            document_id=document_id,
            section_embedding_service=self.embedding_service,
            limit=limit,
            exclude_self=True
        )
