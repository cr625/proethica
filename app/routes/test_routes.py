from flask import Blueprint, render_template, abort, request, flash, redirect, url_for
from app.models import Document
from app.models.document_section import DocumentSection
from app.services.guideline_section_service import GuidelineSectionService
import logging

test_bp = Blueprint('test', __name__, url_prefix='/test')
logger = logging.getLogger(__name__)

@test_bp.route('/guideline_sections/<int:document_id>')
def view_guideline_sections(document_id):
    """View guideline associations for a document's sections without regenerating them."""
    try:
        # Get document
        document = Document.query.get_or_404(document_id)
        
        # Get all sections for this document
        sections = DocumentSection.query.filter_by(document_id=document_id).all()
        
        # Process section data to extract guideline associations
        section_data = []
        for section in sections:
            guideline_associations = []
            
            # Extract guideline associations from section metadata
            if section.section_metadata and 'guideline_associations' in section.section_metadata:
                guideline_associations = section.section_metadata['guideline_associations']
                # Log the guideline associations for debugging
                logger.info(f"Section {section.id} ({section.section_type}) has {len(guideline_associations)} guideline associations")
                logger.info(f"First association sample: {guideline_associations[0] if guideline_associations else 'None'}")
            
            section_data.append({
                'id': section.id,
                'section_id': section.section_id,
                'section_type': section.section_type,
                'content_preview': section.content[:200] + '...' if len(section.content) > 200 else section.content,
                'guideline_associations': guideline_associations
            })
        
        # Get document metadata about guideline associations
        guideline_metadata = {}
        if document.doc_metadata and 'document_structure' in document.doc_metadata:
            if 'guideline_associations' in document.doc_metadata['document_structure']:
                guideline_metadata = document.doc_metadata['document_structure']['guideline_associations']
        
        return render_template(
            'test/guideline_sections.html',
            document=document,
            sections=section_data,
            guideline_metadata=guideline_metadata
        )
    except Exception as e:
        logger.error(f"Error viewing guideline sections: {e}")
        abort(500, description=str(e))

@test_bp.route('/guideline_sections/<int:document_id>/regenerate', methods=['POST'])
def regenerate_guideline_sections(document_id):
    """Regenerate guideline associations for a document's sections."""
    try:
        guideline_service = GuidelineSectionService()
        result = guideline_service.associate_guidelines_with_sections(document_id)
        flash(f"Guideline associations regenerated: {result.get('sections_processed', 0)} sections processed")
    except Exception as e:
        logger.error(f"Error regenerating guideline sections: {e}")
        flash(f"Error regenerating guideline associations: {str(e)}", "error")
    
    return redirect(url_for('test.view_guideline_sections', document_id=document_id))
