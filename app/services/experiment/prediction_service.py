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
    
    def _find_similar_cases(self, document_id: int, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Find similar cases based on content similarity.
        
        Args:
            document_id: ID of the document to find similar cases for
            limit: Maximum number of similar cases to return
            
        Returns:
            List of dictionaries with similar case information
        """
        try:
            # Get the document
            document = Document.query.get(document_id)
            if not document:
                logger.error(f"Document with ID {document_id} not found")
                return []
                
            # For this basic implementation, we'll just search for similar cases
            # based on section content similarity using the section embedding service
            
            # Get document sections
            sections = self.get_document_sections(document_id, leave_out_conclusion=False)
            if not sections:
                return []
                
            # Combine all section content for a simple search
            combined_content = " ".join(sections.values())
            
            # Use section embedding service to find similar sections across cases
            similar_sections = self.embedding_service.find_similar_sections(
                query_text=combined_content[:1000],  # Limit length to avoid token limits
                limit=limit * 3  # Get more than needed to have enough unique documents
            )
            
            # Extract unique documents from similar sections
            seen_docs = set([document_id])  # Exclude the current document
            similar_cases = []
            
            for section in similar_sections:
                doc_id = section.get('document_id')
                if doc_id and doc_id not in seen_docs:
                    seen_docs.add(doc_id)
                    
                    # Get the document
                    similar_doc = Document.query.get(doc_id)
                    if similar_doc:
                        # Get conclusion for outcome if available
                        outcome = ""
                        summary = ""
                        
                        # Try to get conclusion from document sections
                        doc_sections = self.get_document_sections(doc_id, leave_out_conclusion=False)
                        if 'conclusion' in doc_sections:
                            outcome = doc_sections['conclusion']
                        
                        # Create summary from facts if available
                        if 'facts' in doc_sections:
                            summary = doc_sections['facts'][:300] + "..."  # Truncate for brevity
                        
                        similar_cases.append({
                            'document_id': doc_id,
                            'title': similar_doc.title,
                            'outcome': outcome,
                            'summary': summary,
                            'similarity_score': section.get('similarity', 0.0)
                        })
                        
                        # Break if we have enough cases
                        if len(similar_cases) >= limit:
                            break
            
            return similar_cases
            
        except Exception as e:
            logger.exception(f"Error finding similar cases: {str(e)}")
            return []
