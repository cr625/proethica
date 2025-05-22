"""
Helper module for finding similar cases in the ProEthica system.

This module provides functions for finding similar engineering ethics cases
based on content similarity and shared ontology entities.
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import func, desc

from app.models.document import Document
from app.models.document_section import DocumentSection
from app.services.section_embedding_service import SectionEmbeddingService

logger = logging.getLogger(__name__)

def find_similar_cases(document_id: int, 
                      section_embedding_service: SectionEmbeddingService,
                      limit: int = 3,
                      exclude_self: bool = True) -> List[Dict[str, Any]]:
    """
    Find similar engineering ethics cases based on content similarity.
    
    Args:
        document_id: ID of the document to find similar cases for
        section_embedding_service: Instance of SectionEmbeddingService
        limit: Maximum number of similar cases to return
        exclude_self: Whether to exclude the input document from results
        
    Returns:
        List of dictionaries with similar case information
    """
    try:
        # Get the document
        document = Document.query.get(document_id)
        if not document:
            logger.error(f"Document with ID {document_id} not found")
            return []
            
        # Get document sections
        sections = get_document_sections(document_id)
        if not sections:
            return []
            
        # Combine all section content for a simple search
        combined_content = " ".join(sections.values())
        
        # Use section embedding service to find similar sections across cases
        similar_sections = section_embedding_service.find_similar_sections(
            query_text=combined_content,
            limit=limit * 2  # Get more results than needed to allow filtering
        )
        
        # Group results by document
        doc_scores = {}
        doc_data = {}
        
        for section in similar_sections:
            # Skip if same document and exclude_self is True
            if exclude_self and section.get('document_id') == document_id:
                continue
                
            doc_id = section.get('document_id')
            if doc_id:
                # Add to score for this document
                if doc_id in doc_scores:
                    doc_scores[doc_id] += section.get('score', 0.0)
                else:
                    doc_scores[doc_id] = section.get('score', 0.0)
                    
                    # Store document data
                    if doc_id not in doc_data:
                        doc = Document.query.get(doc_id)
                        if doc:
                            doc_data[doc_id] = {
                                'id': doc_id,
                                'title': doc.title,
                                'document_type': doc.document_type
                            }
                            
                            # Try to extract outcome from conclusion section
                            conclusion = get_document_conclusion(doc_id)
                            if conclusion:
                                doc_data[doc_id]['outcome'] = extract_outcome_from_conclusion(conclusion)
                                doc_data[doc_id]['summary'] = conclusion[:200] + "..." if len(conclusion) > 200 else conclusion
        
        # Sort documents by score
        sorted_doc_ids = sorted(doc_scores.keys(), key=lambda k: doc_scores[k], reverse=True)
        
        # Build result list
        results = []
        for doc_id in sorted_doc_ids[:limit]:
            if doc_id in doc_data:
                case_data = doc_data[doc_id]
                case_data['score'] = doc_scores[doc_id]
                results.append(case_data)
        
        return results
        
    except Exception as e:
        logger.exception(f"Error finding similar cases: {str(e)}")
        return []

def get_document_sections(document_id: int, leave_out_conclusion: bool = False) -> Dict[str, str]:
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
        for section_id, section_data in metadata['sections'].items():
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

def get_document_conclusion(document_id: int) -> Optional[str]:
    """
    Get the conclusion section for a document.
    
    Args:
        document_id: ID of the document
        
    Returns:
        Conclusion text or None if not found
    """
    # Try to find conclusion in document sections
    document = Document.query.get(document_id)
    if not document or not document.doc_metadata:
        return None
    
    metadata = document.doc_metadata
    
    # Case 1: New format with document_structure
    if 'document_structure' in metadata and 'sections' in metadata['document_structure']:
        doc_sections = metadata['document_structure']['sections']
        
        for section_id, section_data in doc_sections.items():
            # Check if section_data is a dictionary
            if isinstance(section_data, dict):
                if section_data.get('type', '').lower() == 'conclusion':
                    return section_data.get('content', '')
            # If section_data is a string and section_id indicates it's a conclusion
            elif section_id.lower() == 'conclusion':
                return str(section_data)
    
    # Case 2: Legacy format with top-level sections
    elif 'sections' in metadata:
        for section_id, section_data in metadata['sections'].items():
            # Check if section_data is a dictionary
            if isinstance(section_data, dict):
                if section_data.get('type', '').lower() == 'conclusion':
                    return section_data.get('content', '')
            # If section_data is a string and section_id indicates it's a conclusion
            elif section_id.lower() == 'conclusion':
                return str(section_data)
    
    # Case 3: Check for DocumentSection records
    conclusion_section = DocumentSection.query.filter_by(
        document_id=document_id,
        section_type='conclusion'
    ).first()
    
    if conclusion_section:
        return conclusion_section.content
    
    return None

def extract_outcome_from_conclusion(conclusion: str) -> str:
    """
    Extract the outcome (ethical/unethical decision) from a conclusion.
    
    Args:
        conclusion: Conclusion text
        
    Returns:
        Extracted outcome statement
    """
    import re
    
    # Common patterns in NSPE case conclusions
    patterns = [
        r'(not ethical|unethical|ethical)',
        r'(violates|does not violate)',
        r'(is|is not) in accordance with',
        r'(complies|does not comply)',
        r'(in conflict|not in conflict)'
    ]
    
    # Check each sentence for patterns
    sentences = re.split(r'(?<=[.!?])\s+', conclusion)
    
    for sentence in sentences[:3]:  # Look only in first few sentences
        for pattern in patterns:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                # Return the sentence containing the outcome
                return sentence.strip()
    
    # If no pattern found, return first sentence as default
    if sentences:
        return sentences[0].strip()
    
    return "Outcome not specified"
