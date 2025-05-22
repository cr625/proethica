"""
Experiment Prediction Service.

This service extends the LLM service to support the ProEthica experiment,
implementing both baseline and enhanced prompting strategies for case prediction.
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
            
        # Get document metadata
        if not document.doc_metadata or not isinstance(document.doc_metadata, dict):
            logger.error(f"Document {document_id} has no valid metadata")
            return {}
            
        metadata = document.doc_metadata
        
        # Check for document structure
        sections = {}
        
        # Case 1: New format with document_structure
        if 'document_structure' in metadata and 'sections' in metadata['document_structure']:
            doc_sections = metadata['document_structure']['sections']
            
            for section_id, section_data in doc_sections.items():
                section_type = section_data.get('type', '').lower()
                content = section_data.get('content', '')
                
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
            for section_id, section_data in metadata['sections'].items():
                section_type = section_data.get('type', '').lower()
                content = section_data.get('content', '')
                
                # Skip conclusion if leave_out_conclusion is True
                if leave_out_conclusion and section_type == 'conclusion':
                    continue
                    
                # Add or merge section content
                if section_type in sections:
                    sections[section_type] += "\n\n" + content
                else:
                    sections[section_type] = content
        
        # Case 3: Check for standard DocumentSection records
        else:
            # Query the DocumentSection table
            doc_sections = DocumentSection.query.filter_by(document_id=document_id).all()
            
            for section in doc_sections:
                section_type = section.section_type.lower() if section.section_type else ''
                
                # Skip conclusion if leave_out_conclusion is True
                if leave_out_conclusion and section_type == 'conclusion':
                    continue
                    
                # Add or merge section content
                if section_type in sections:
                    sections[section_type] += "\n\n" + section.content
                else:
                    sections[section_type] = section.content
        
        return sections
    
    def generate_baseline_prediction(self, document_id: int, 
                                    leave_out_conclusion: bool = True) -> Dict[str, Any]:
        """
        Generate a prediction using the baseline approach.
        
        Args:
            document_id: ID of the document
            leave_out_conclusion: Whether to exclude conclusion section from prompt
            
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
                
            # Get document sections
            sections = self.get_document_sections(document_id, leave_out_conclusion)
            
            if not sections:
                return {
                    'success': False,
                    'error': "No sections found for document"
                }
                
            # Find similar cases for precedent matching (basic implementation)
            similar_cases = self._find_similar_cases(document_id, limit=3)
            
            # Construct the baseline prompt
            prompt = self._construct_baseline_prompt(document, sections, similar_cases)
            
            # Generate prediction using LLM
            logger.info(f"Generating baseline prediction for document {document_id}")
            response = self.llm_service.llm.invoke(prompt)
            
            # Process and return the result
            return {
                'success': True,
                'document_id': document_id,
                'condition': 'baseline',
                'prediction': response,
                'prompt': prompt,
                'timestamp': datetime.utcnow().isoformat(),
                'metadata': {
                    'sections_included': list(sections.keys()),
                    'similar_cases': [case['title'] for case in similar_cases],
                    'leave_out_conclusion': leave_out_conclusion
                }
            }
            
        except Exception as e:
            logger.exception(f"Error generating baseline prediction: {str(e)}")
            return {
                'success': False,
                'error': f"Error generating prediction: {str(e)}"
            }
    
    def _construct_baseline_prompt(self, document: Document, 
                                 sections: Dict[str, str],
                                 similar_cases: List[Dict[str, Any]]) -> str:
        """
        Construct a baseline prompt for case prediction.
        
        Args:
            document: Document object
            sections: Dictionary of section types to content
            similar_cases: List of similar cases for precedent
            
        Returns:
            Prompt string
        """
        # Start with a standard prompt introduction
        prompt = f"""
        You are an AI assistant with expertise in engineering ethics, tasked with analyzing an engineering ethics case and predicting the decision that would be made by the National Society of Professional Engineers (NSPE) Board of Ethical Review.
        
        CASE INFORMATION:
        Title: {document.title}
        """
        
        # Add each section to the prompt in a logical order
        section_order = ['question', 'facts', 'references', 'discussion']
        for section_type in section_order:
            if section_type in sections:
                prompt += f"\n\n{section_type.upper()}:\n{sections[section_type]}"
        
        # Add any other sections not in the predefined order
        for section_type, content in sections.items():
            if section_type not in section_order:
                prompt += f"\n\n{section_type.upper()}:\n{content}"
        
        # Add similar cases as precedents if available
        if similar_cases:
            prompt += "\n\nRELEVANT PRECEDENT CASES:"
            for case in similar_cases:
                prompt += f"\n\nCase: {case['title']}"
                if 'outcome' in case:
                    prompt += f"\nOutcome: {case['outcome']}"
                if 'summary' in case:
                    prompt += f"\nSummary: {case['summary']}"
        
        # Add the prediction request
        prompt += """
        
        TASK:
        Based on the information provided, predict what decision the NSPE Board of Ethical Review would make in this case. Your prediction should include:
        
        1. A clear decision statement (whether the conduct described is ethical or unethical)
        2. A detailed explanation of your reasoning
        3. References to relevant ethical principles involved
        
        Please structure your response clearly, focusing on the facts presented and logical reasoning.
        """
        
        return prompt
    
    def generate_conclusion_prediction(self, document_id: int) -> Dict[str, Any]:
        """
        Generate a prediction for the conclusion section using ontology-enhanced approach.
        
        Args:
            document_id: ID of the document
            
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
                
            # Get ontology entities associated with document sections
            ontology_entities = self.get_section_ontology_entities(document_id, sections)
            
            # Find similar cases with ontology-enhanced matching
            similar_cases = self._find_similar_cases(document_id, limit=3)

            # Construct specialized conclusion prediction prompt
            prompt = self._construct_conclusion_prediction_prompt(document, sections, ontology_entities, similar_cases)

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
                'condition': 'proethica',
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
                                            similar_cases: List[Dict[str, Any]]) -> str:
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
    
    def _extract_conclusion(self, response: str) -> str:
        """
        Extract just the conclusion part from the LLM response.
        
        This might use heuristics, pattern matching, or further LLM processing
        to isolate just the conclusion section from the full response.
        
        Args:
            response: The full LLM response
            
        Returns:
            Extracted conclusion text
        """
        # For now, use a simple approach - either rely on formatting or return the entire response
        # Could be enhanced with more sophisticated extraction methods
        
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
        
        # Use LLM to evaluate coherence (future enhancement)
        
        return {
            'entity_mentions': entity_mentions,
            'total_entities': total_entities,
            'mention_ratio': mention_ratio,
            'mentioned_entities': mentioned_entities[:10],  # Limit to first 10
            'validation_status': 'passed' if mention_ratio > 0.1 else 'failed'
        }
            
    def generate_proethica_prediction(self, document_id: int,
                                    leave_out_conclusion: bool = True) -> Dict[str, Any]:
        """
        Generate a prediction using the ProEthica enhanced approach with ontology constraints.

        Args:
            document_id: ID of the document
            leave_out_conclusion: Whether to exclude conclusion section from prompt

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

            # Get document sections
            sections = self.get_document_sections(document_id, leave_out_conclusion)

            if not sections:
                return {
                    'success': False,
                    'error': "No sections found for document"
                }

            # Get ontology entities associated with document sections
            ontology_entities = self.get_section_ontology_entities(document_id, sections)
            
            # Find similar cases with ontology-enhanced matching
            similar_cases = self._find_similar_cases(document_id, limit=3)

            # Construct the ProEthica prompt with ontology constraints
            prompt = self._construct_proethica_prompt(document, sections, ontology_entities, similar_cases)

            # Generate prediction using LLM
            logger.info(f"Generating ProEthica prediction for document {document_id}")
            response = self.llm_service.llm.invoke(prompt)

            # Validate the prediction against ontology constraints
            validation_results = self._validate_prediction(response, ontology_entities)

            # Process and return the result
            return {
                'success': True,
                'document_id': document_id,
                'condition': 'proethica',
                'prediction': response,
                'prompt': prompt,
                'timestamp': datetime.utcnow().isoformat(),
                'metadata': {
                    'sections_included': list(sections.keys()),
                    'ontology_entities': self._summarize_ontology_entities(ontology_entities),
                    'similar_cases': [case['title'] for case in similar_cases],
                    'validation_metrics': validation_results,
                    'leave_out_conclusion': leave_out_conclusion
                }
            }

        except Exception as e:
            logger.exception(f"Error generating ProEthica prediction: {str(e)}")
            return {
                'success': False,
                'error': f"Error generating prediction: {str(e)}"
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
                
                # Query associated triples
                triples = self.triple_association_service.get_section_triples(section_id)
                
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

    def _construct_proethica_prompt(self, document: Document, 
                                  sections: Dict[str, str],
                                  ontology_entities: Dict[str, List[Dict]],
                                  similar_cases: List[Dict[str, Any]]) -> str:
        """
        Construct an ontology-enhanced FIRAC prompt.
        
        Args:
            document: Document object
            sections: Dictionary of section types to content
            ontology_entities: Dictionary of section types to ontology entities
            similar_cases: List of similar cases for precedent
        
        Returns:
            Enhanced prompt string
        """
        # Start with a structured FIRAC introduction
        prompt = f"""
        You are an AI assistant with expertise in engineering ethics, tasked with analyzing an engineering ethics case and predicting the decision that would be made by the National Society of Professional Engineers (NSPE) Board of Ethical Review.
        
        You will follow a structured FIRAC (Facts, Issues, Rules, Application, Conclusion) framework, incorporating relevant engineering ethics principles and ontological concepts.
        
        CASE INFORMATION:
        Title: {document.title}
        """
        
        # Add FACTS section
        prompt += "\n\n# FACTS:"
        if 'facts' in sections:
            prompt += f"\n{sections['facts']}"
        
        # Add relevant ontology concepts for facts
        fact_entities = ontology_entities.get('facts', [])
        if fact_entities:
            prompt += "\n\nRelevant factual concepts:"
            # Include up to 5 most relevant fact entities
            for entity in fact_entities[:5]:
                prompt += f"\n- {entity['subject']} {entity['predicate']} {entity['object']}"
        
        # Add ISSUES section
        prompt += "\n\n# ISSUES:"
        if 'question' in sections:
            prompt += f"\n{sections['question']}"
        
        # Add relevant ontology concepts for issues
        issue_entities = ontology_entities.get('question', [])
        if issue_entities:
            prompt += "\n\nRelevant ethical issues:"
            # Include up to 5 most relevant issue entities
            for entity in issue_entities[:5]:
                prompt += f"\n- {entity['subject']} {entity['predicate']} {entity['object']}"
        
        # Add RULES section
        prompt += "\n\n# RULES:"
        if 'references' in sections:
            prompt += f"\n{sections['references']}"
        
        # Add relevant ontology concepts for rules
        rule_entities = []
        for section_type, entities in ontology_entities.items():
            if section_type in ['references', 'discussion']:
                rule_entities.extend(entities)
        
        if rule_entities:
            # Sort by relevance score
            rule_entities = sorted(rule_entities, key=lambda x: x.get('score', 0.0), reverse=True)
            
            prompt += "\n\nRelevant ethical principles and rules:"
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
        
        # Add APPLICATION section guidance
        prompt += """
        
        # APPLICATION:
        In your analysis, you should apply the ethical principles and rules to the specific facts of this case.
        Consider how the NSPE Code of Ethics principles apply to the situation described.
        Reference specific ethical principles that are most relevant to this case.
        """
        
        # Add CONCLUSION section guidance
        prompt += """
        
        # CONCLUSION:
        Based on your analysis, predict what decision the NSPE Board of Ethical Review would make in this case.
        
        Your prediction should include:
        1. A clear decision statement (whether the conduct described is ethical or unethical)
        2. A detailed explanation of your reasoning, following the FIRAC framework
        3. Explicit references to relevant ethical principles from the NSPE Code of Ethics
        
        Please structure your response with clear headings for each FIRAC element, focusing on logical reasoning and ethical principles.
        """
        
        return prompt
        
    def _validate_prediction(self, prediction: str, 
                           ontology_entities: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """
        Validate prediction against ontology constraints.
        
        Args:
            prediction: Generated prediction text
            ontology_entities: Dictionary of section types to ontology entities
        
        Returns:
            Validation results and confidence metrics
        """
        # This is a placeholder implementation for now
        # In a full implementation, we would:
        # 1. Parse the prediction to extract key components
        # 2. Check if relevant ontology entities were incorporated
        # 3. Verify logical consistency between sections
        # 4. Calculate confidence metrics
        
        # Extract all entity subjects and objects for basic validation
        all_entities = []
        for section_type, entities in ontology_entities.items():
            for entity in entities:
                # Add subject and object terms
                if 'subject' in entity:
                    all_entities.append(entity['subject'])
                if 'object' in entity:
                    all_entities.append(entity['object'])
        
        # Simple validation: check if any entities are mentioned in the prediction
        entity_mentions = 0
        mentioned_entities = []
        for entity in all_entities:
            if entity in prediction:
                entity_mentions += 1
                mentioned_entities.append(entity)
                
        # Calculate basic metrics
        total_entities = len(all_entities)
        mention_ratio = entity_mentions / total_entities if total_entities > 0 else 0
        
        return {
            'entity_mentions': entity_mentions,
            'total_entities': total_entities,
            'mention_ratio': mention_ratio,
            'mentioned_entities': mentioned_entities[:10],  # Limit to 10 for readability
            'validation_status': 'passed' if mention_ratio > 0.1 else 'failed'
        }
    
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
