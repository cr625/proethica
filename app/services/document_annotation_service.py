"""
Document Annotation Service - Modular service for handling annotations across different document types
"""
from typing import Dict, List, Optional, Any, Tuple
from flask import current_app
from sqlalchemy import and_

from ..models.document_concept_annotation import DocumentConceptAnnotation
from ..models.guideline import Guideline
from ..models.document import Document
from .. import db


class DocumentAnnotationService:
    """Service for handling document annotations across different document types"""
    
    @staticmethod
    def get_document_by_id_and_type(document_id: int, document_type: str) -> Optional[Any]:
        """Get a document by ID and type"""
        if document_type == 'guideline':
            return Guideline.query.get(document_id)
        elif document_type == 'case':
            return Document.query.get(document_id)
        else:
            raise ValueError(f"Unsupported document type: {document_type}")
    
    @staticmethod
    def get_annotations_by_document(document_id: int, document_type: str) -> List[DocumentConceptAnnotation]:
        """Get all annotations for a specific document"""
        return DocumentConceptAnnotation.query.filter(
            and_(
                DocumentConceptAnnotation.document_id == document_id,
                DocumentConceptAnnotation.document_type == document_type
            )
        ).all()
    
    @staticmethod
    def get_annotations_grouped_by_ontology(document_id: int, document_type: str) -> Dict[str, List[DocumentConceptAnnotation]]:
        """Get annotations grouped by ontology for a specific document"""
        annotations = DocumentAnnotationService.get_annotations_by_document(document_id, document_type)
        
        grouped_annotations = {}
        for annotation in annotations:
            ontology_name = annotation.ontology_name or 'Unknown'
            if ontology_name not in grouped_annotations:
                grouped_annotations[ontology_name] = []
            grouped_annotations[ontology_name].append(annotation)
        
        return grouped_annotations
    
    @staticmethod
    def get_annotation_statistics(document_id: int, document_type: str) -> Dict[str, Any]:
        """Get annotation statistics for a specific document"""
        annotations = DocumentAnnotationService.get_annotations_by_document(document_id, document_type)
        
        # Count total annotations
        total_annotations = len(annotations)
        
        # Count by ontology
        ontologies = set(ann.ontology_name for ann in annotations if ann.ontology_name)
        ontology_count = len(ontologies)
        
        # Count by method (concept_type)
        method_counts = {}
        for annotation in annotations:
            method = annotation.concept_type or 'basic'
            method_counts[method] = method_counts.get(method, 0) + 1
        
        return {
            'total_annotations': total_annotations,
            'ontology_count': ontology_count,
            'method_counts': method_counts
        }
    
    @staticmethod
    def prepare_annotation_context(document_id: int, document_type: str, world=None) -> Dict[str, Any]:
        """Prepare all annotation context data for a document"""
        # Get the document
        document = DocumentAnnotationService.get_document_by_id_and_type(document_id, document_type)
        if not document:
            return None
        
        # Get annotations grouped by ontology
        annotations_by_ontology = DocumentAnnotationService.get_annotations_grouped_by_ontology(
            document_id, document_type
        )
        
        # Get statistics
        stats = DocumentAnnotationService.get_annotation_statistics(document_id, document_type)
        
        # Prepare context
        context = {
            'document': document,
            'document_type': document_type,
            'world': world,
            'annotations_by_ontology': annotations_by_ontology,
            **stats
        }
        
        # Add document-specific context
        if document_type == 'guideline':
            context.update({
                'guideline': document,
                'back_url': f"/worlds/{world.id}/guidelines/{document_id}" if world else f"/guidelines/{document_id}"
            })
        elif document_type == 'case':
            context.update({
                'case': document,
                'back_url': f"/cases/{document_id}"
            })
        
        return context
    
    @staticmethod
    def get_document_content_for_annotation(document_id: int, document_type: str) -> Optional[str]:
        """Get the content of a document for annotation processing"""
        from flask import current_app
        
        document = DocumentAnnotationService.get_document_by_id_and_type(document_id, document_type)
        if not document:
            current_app.logger.error(f"Document {document_id} of type {document_type} not found")
            return None
        
        current_app.logger.info(f"Processing document {document_id} of type {document_type}")
        current_app.logger.info(f"Document title: {document.title}")
        current_app.logger.info(f"Document content length: {len(document.content) if document.content else 'None'}")
        current_app.logger.info(f"Document has metadata: {bool(document.doc_metadata)}")
        
        if document_type == 'guideline':
            return document.content
        elif document_type == 'case':
            # For cases, try multiple content extraction strategies
            content_parts = []
            
            # Strategy 1: Primary content from document.content field
            if document.content:
                current_app.logger.info(f"Strategy 1 - Adding document.content: {len(document.content)} chars")
                content_parts.append(document.content)
            
            # Strategy 2: Get content from get_content method (handles file reading)
            elif hasattr(document, 'get_content'):
                try:
                    file_content = document.get_content()
                    if file_content and file_content.strip():
                        current_app.logger.info(f"Strategy 2 - Adding file content: {len(file_content)} chars")
                        content_parts.append(file_content)
                except Exception as e:
                    current_app.logger.error(f"Strategy 2 failed: {str(e)}")
            
            # Strategy 3: Extract from metadata structures
            if document.doc_metadata and isinstance(document.doc_metadata, dict):
                metadata = document.doc_metadata
                current_app.logger.info(f"Strategy 3 - Metadata keys: {list(metadata.keys())}")
                
                # Check for sections in different metadata structures
                sections = metadata.get('sections', {})
                sections_dual = metadata.get('sections_dual', {})
                
                # Handle sections structure
                if sections and isinstance(sections, dict):
                    current_app.logger.info(f"Found sections: {list(sections.keys())}")
                    for section_name, section_content in sections.items():
                        if section_content and str(section_content).strip():
                            current_app.logger.info(f"Adding section {section_name}: {len(str(section_content))} chars")
                            content_parts.append(f"{section_name.title()}: {section_content}")
                
                # Handle sections_dual structure (HTML content)
                if sections_dual and isinstance(sections_dual, dict):
                    current_app.logger.info(f"Found sections_dual: {list(sections_dual.keys())}")
                    for section_name, section_data in sections_dual.items():
                        if isinstance(section_data, dict) and section_data.get('html'):
                            # Strip HTML tags for annotation content
                            import re
                            clean_content = re.sub(r'<[^>]+>', '', section_data['html'])
                            if clean_content.strip():
                                current_app.logger.info(f"Adding HTML section {section_name}: {len(clean_content)} chars")
                                content_parts.append(f"{section_name.title()}: {clean_content}")
                
                # Get additional fields that might contain content
                for field in ['decision', 'outcome', 'ethical_analysis', 'description']:
                    value = metadata.get(field)
                    if value and str(value).strip():
                        current_app.logger.info(f"Adding field {field}: {len(str(value))} chars")
                        content_parts.append(f"{field.title()}: {value}")
            
            current_app.logger.info(f"Total content parts: {len(content_parts)}")
            if content_parts:
                result = '\n\n'.join(content_parts)
                current_app.logger.info(f"Final content length: {len(result)} chars")
                return result
            else:
                current_app.logger.error("No content found using any strategy!")
                return None
        
        return None
    
    @staticmethod
    def create_annotation(document_id: int, document_type: str, **annotation_data) -> DocumentConceptAnnotation:
        """Create a new annotation for a document"""
        annotation = DocumentConceptAnnotation(
            document_id=document_id,
            document_type=document_type,
            **annotation_data
        )
        db.session.add(annotation)
        return annotation
    
    @staticmethod
    def get_pending_annotations_count(document_id: int, document_type: str) -> int:
        """Get count of pending annotations for a document"""
        return DocumentConceptAnnotation.query.filter(
            and_(
                DocumentConceptAnnotation.document_id == document_id,
                DocumentConceptAnnotation.document_type == document_type,
                DocumentConceptAnnotation.approval_stage == 'pending'
            )
        ).count()
    
    @staticmethod
    def get_approved_annotations_count(document_id: int, document_type: str) -> int:
        """Get count of approved annotations for a document"""
        return DocumentConceptAnnotation.query.filter(
            and_(
                DocumentConceptAnnotation.document_id == document_id,
                DocumentConceptAnnotation.document_type == document_type,
                DocumentConceptAnnotation.approval_stage == 'user_approved'
            )
        ).count()
    
    @staticmethod
    def get_annotation_by_id(annotation_id: int) -> Optional[DocumentConceptAnnotation]:
        """Get a specific annotation by ID"""
        return DocumentConceptAnnotation.query.get(annotation_id)
    
    @staticmethod
    def delete_all_annotations_for_document(document_id: int, document_type: str) -> int:
        """Delete all annotations for a specific document. Returns count of deleted annotations."""
        deleted_count = DocumentConceptAnnotation.query.filter(
            and_(
                DocumentConceptAnnotation.document_id == document_id,
                DocumentConceptAnnotation.document_type == document_type
            )
        ).delete()
        return deleted_count
    
    @staticmethod
    def get_document_url_for_type(document_id: int, document_type: str, world=None) -> str:
        """Get the appropriate URL for a document based on its type"""
        if document_type == 'guideline':
            if world:
                return f"/worlds/{world.id}/guidelines/{document_id}"
            else:
                return f"/guidelines/{document_id}"
        elif document_type == 'case':
            return f"/cases/{document_id}"
        else:
            return "#"
    
    @staticmethod
    def get_annotations_url_for_type(document_id: int, document_type: str, world=None) -> str:
        """Get the annotations URL for a document based on its type"""
        if document_type == 'guideline':
            if world:
                return f"/worlds/{world.id}/guidelines/{document_id}/annotations"
            else:
                return f"/guidelines/{document_id}/annotations"
        elif document_type == 'case':
            return f"/cases/{document_id}/annotations"
        else:
            return "#"
