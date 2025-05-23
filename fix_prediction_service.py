#!/usr/bin/env python3

# This script contains the fixed get_document_sections method
# that properly handles Case 252's metadata structure

def get_document_sections_fixed(document_id: int, leave_out_conclusion: bool = True):
    """
    FIXED VERSION: Get document sections for a case, optionally excluding the conclusion.
    
    Args:
        document_id: ID of the document
        leave_out_conclusion: Whether to exclude conclusion section
        
    Returns:
        Dictionary of section types to content
    """
    from app.models.document import Document
    from app.models.document_section import DocumentSection
    import logging
    
    logger = logging.getLogger(__name__)
    
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
    
    # Case 2: Legacy format with top-level sections (THIS IS THE CASE FOR 252)
    elif 'sections' in metadata:
        for section_key, section_data in metadata['sections'].items():
            # FIXED: Handle direct string content (Case 252's format)
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

print("Fixed prediction service method ready for integration!")
