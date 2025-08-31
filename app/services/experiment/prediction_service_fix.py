"""
Fixed version of the PredictionService with improvements to handle various metadata formats.

This file contains a fixed version of the get_document_sections method to handle cases
where section_data might be a string rather than a dictionary.
"""

import logging
from typing import Dict, Any
from app.models import Document
from app.models.document_section import DocumentSection

logger = logging.getLogger(__name__)

def fixed_get_document_sections(self, document_id: int, leave_out_conclusion: bool = True) -> Dict[str, str]:
    """
    Fixed version of get_document_sections that safely handles different metadata formats.
    
    Args:
        document_id: ID of the document
        leave_out_conclusion: Whether to exclude conclusion section
        
    Returns:
        Dictionary of section types to content
    """
    # Get the document using standard query interface
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
    
    try:
        # Case 1: New format with document_structure
        if 'document_structure' in metadata and 'sections' in metadata['document_structure']:
            doc_sections = metadata['document_structure']['sections']
            
            for section_id, section_data in doc_sections.items():
                # Ensure section_data is a dictionary
                if not isinstance(section_data, dict):
                    logger.warning(f"Section data for {section_id} is not a dictionary: {type(section_data)}")
                    continue
                    
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
            # Check if sections is a dictionary
            if isinstance(metadata['sections'], dict):
                for section_id, section_data in metadata['sections'].items():
                    # Ensure section_data is a dictionary
                    if not isinstance(section_data, dict):
                        logger.warning(f"Section data for {section_id} is not a dictionary: {type(section_data)}")
                        continue
                        
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
            # Handle case where sections is a list
            elif isinstance(metadata['sections'], list):
                for section_data in metadata['sections']:
                    # Ensure section_data is a dictionary
                    if not isinstance(section_data, dict):
                        logger.warning(f"Section data is not a dictionary: {type(section_data)}")
                        continue
                        
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
            else:
                logger.warning(f"Sections in metadata is not a dictionary or list: {type(metadata['sections'])}")
        
        # Case 3: Check for standard DocumentSection records
        else:
            # Query the DocumentSection table using the imported model
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
                    
    except Exception as e:
        logger.exception(f"Error processing document sections: {str(e)}")
        
    # If we don't have any sections yet, check if document has content field
    if not sections:
        logger.info(f"No structured sections found for document {document_id}")
        
        # Try to access potential content attributes
        if hasattr(document, 'content') and document.content:
            logger.info(f"Using document 'content' attribute")
            sections = {'text': document.content}
        elif hasattr(document, 'text') and document.text:
            logger.info(f"Using document 'text' attribute")
            sections = {'text': document.text}
        else:
            # If we found no content, log this and return an empty result
            logger.warning(f"Document {document_id} has no identifiable content fields")
    
    # Log what sections were found
    logger.info(f"Returning sections: {list(sections.keys())}")
    return sections
