"""
Ontology Term Recognition Service

Identifies individual words and phrases in document sections that match 
terms in the engineering-ethics ontology and creates term links.
"""
import re
import logging
from typing import Dict, List, Any, Optional, Set
from app import db
from app.models.section_term_link import SectionTermLink
from app.models.document import Document

logger = logging.getLogger(__name__)

class OntologyTermRecognitionService:
    """Service for recognizing and linking ontology terms in document sections."""
    
    def __init__(self):
        self.ontology_terms = None
        self.term_patterns = None
        self._load_ontology_terms()
    
    def _load_ontology_terms(self):
        """Load ontology terms from the engineering-ethics ontology."""
        try:
            from app.services.ontology_entity_service import OntologyEntityService
            from app.models.world import World
            
            # Get the engineering-ethics world (assume it's world ID 1)
            world = World.query.filter_by(name='Engineering Ethics').first()
            if not world:
                # Fallback to world ID 1
                world = World.query.get(1)
            
            if not world:
                logger.warning("No engineering-ethics world found")
                self.ontology_terms = {}
                return
            
            ontology_service = OntologyEntityService()
            
            # Get all entities for the engineering-ethics world
            result = ontology_service.get_entities_for_world(world)
            entities_data = result.get('entities', {})
            
            if not entities_data:
                logger.warning("No entities found in engineering-ethics ontology")
                self.ontology_terms = {}
                return
            
            self.ontology_terms = {}
            
            # Process all entity types
            for entity_type, entities_list in entities_data.items():
                if not isinstance(entities_list, list):
                    continue
                    
                for entity in entities_list:
                    # Use the label as the primary term
                    if entity.get('label'):
                        term = entity['label'].lower()
                        self.ontology_terms[term] = {
                            'uri': entity.get('uri', ''),
                            'label': entity['label'],
                            'definition': entity.get('description', '') or entity.get('comment', ''),
                            'comment': entity.get('comment', ''),
                            'entity_type': entity_type
                        }
                    
                    # Also add the ID as a term if it's different from label
                    if entity.get('id') and entity['id'].lower() != entity.get('label', '').lower():
                        id_term = entity['id'].lower()
                        if id_term not in self.ontology_terms:
                            self.ontology_terms[id_term] = {
                                'uri': entity.get('uri', ''),
                                'label': entity.get('label', entity['id']),
                                'definition': entity.get('description', '') or entity.get('comment', ''),
                                'comment': entity.get('comment', ''),
                                'entity_type': entity_type,
                                'is_id_match': True
                            }
            
            # Create regex patterns for efficient matching
            self._create_term_patterns()
            
            logger.info(f"Loaded {len(self.ontology_terms)} ontology terms for recognition")
            
        except Exception as e:
            logger.error(f"Error loading ontology terms: {str(e)}")
            self.ontology_terms = {}
    
    def _create_term_patterns(self):
        """Create compiled regex patterns for efficient term matching."""
        if not self.ontology_terms:
            self.term_patterns = {}
            return
        
        # Sort terms by length (longest first) to match longer phrases before shorter ones
        sorted_terms = sorted(self.ontology_terms.keys(), key=len, reverse=True)
        
        self.term_patterns = {}
        
        for term in sorted_terms:
            # Create word boundary pattern for exact matches
            # Handle multi-word terms
            if ' ' in term:
                # For multi-word terms, escape special characters and allow flexible spacing
                escaped_term = re.escape(term)
                pattern = r'\b' + escaped_term.replace(r'\ ', r'\s+') + r'\b'
            else:
                # For single words, use simple word boundaries
                pattern = r'\b' + re.escape(term) + r'\b'
            
            try:
                self.term_patterns[term] = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                logger.warning(f"Could not compile regex for term '{term}': {e}")
    
    def recognize_terms_in_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Recognize ontology terms in a given text.
        
        Args:
            text: The text to analyze
            
        Returns:
            List of term matches with positions and ontology information
        """
        if not self.term_patterns or not text:
            return []
        
        matches = []
        seen_positions = set()  # Track positions to avoid overlapping matches
        
        # Process terms in order (longest first)
        for term, pattern in self.term_patterns.items():
            for match in pattern.finditer(text):
                start_pos = match.start()
                end_pos = match.end()
                
                # Check for overlaps with existing matches
                overlap = any(
                    start_pos < existing_end and end_pos > existing_start
                    for existing_start, existing_end in seen_positions
                )
                
                if not overlap:
                    ontology_info = self.ontology_terms[term]
                    
                    matches.append({
                        'term_text': match.group(),
                        'term_start': start_pos,
                        'term_end': end_pos,
                        'ontology_uri': ontology_info['uri'],
                        'ontology_label': ontology_info['label'],
                        'definition': ontology_info.get('definition', '') or ontology_info.get('comment', ''),
                        'matched_term': term,
                        'is_synonym': ontology_info.get('is_synonym', False)
                    })
                    
                    seen_positions.add((start_pos, end_pos))
        
        # Sort matches by position
        matches.sort(key=lambda x: x['term_start'])
        
        return matches
    
    def process_document_sections(self, document_id: int, force_regenerate: bool = False) -> Dict[str, Any]:
        """
        Process all sections of a document to recognize ontology terms.
        
        Args:
            document_id: ID of the document to process
            force_regenerate: Whether to regenerate existing term links
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Get the document
            document = Document.query.get(document_id)
            if not document:
                return {'success': False, 'error': f'Document {document_id} not found'}
            
            # Check if term links already exist
            existing_links = SectionTermLink.query.filter_by(document_id=document_id).count()
            if existing_links > 0 and not force_regenerate:
                return {
                    'success': True,
                    'message': f'Document {document_id} already has {existing_links} term links',
                    'existing_links': existing_links
                }
            
            # Clear existing links if regenerating
            if force_regenerate:
                SectionTermLink.delete_document_term_links(document_id)
                logger.info(f"Cleared existing term links for document {document_id}")
            
            # Get document metadata and sections
            metadata = document.doc_metadata or {}
            
            # Find sections in various possible locations
            sections_data = self._extract_sections_data(metadata)
            
            if not sections_data:
                return {'success': False, 'error': 'No section data found in document'}
            
            total_links_created = 0
            sections_processed = 0
            
            # Process each section
            for section_id, section_content in sections_data.items():
                if not section_content or not section_content.strip():
                    continue
                
                # Clean the content (remove HTML tags if necessary)
                clean_content = self._clean_section_content(section_content)
                
                if not clean_content.strip():
                    continue
                
                # Recognize terms in this section
                term_matches = self.recognize_terms_in_text(clean_content)
                
                # Store term links in database
                for match in term_matches:
                    try:
                        term_link = SectionTermLink(
                            document_id=document_id,
                            section_id=section_id,
                            term_text=match['term_text'],
                            term_start=match['term_start'],
                            term_end=match['term_end'],
                            ontology_uri=match['ontology_uri'],
                            ontology_label=match['ontology_label'],
                            definition=match['definition']
                        )
                        
                        db.session.add(term_link)
                        total_links_created += 1
                        
                    except Exception as e:
                        logger.warning(f"Could not create term link for {match['term_text']}: {e}")
                
                sections_processed += 1
            
            # Commit all changes
            db.session.commit()
            
            logger.info(f"Created {total_links_created} term links across {sections_processed} sections for document {document_id}")
            
            return {
                'success': True,
                'sections_processed': sections_processed,
                'term_links_created': total_links_created,
                'document_id': document_id
            }
            
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error processing document sections for term recognition: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _extract_sections_data(self, metadata: Dict) -> Dict[str, str]:
        """Extract section content from document metadata."""
        sections_data = {}
        
        # Strategy 1: Check document_structure.sections
        if 'document_structure' in metadata and 'sections' in metadata['document_structure']:
            sections = metadata['document_structure']['sections']
            if isinstance(sections, dict):
                for section_id, section_content in sections.items():
                    if isinstance(section_content, str):
                        sections_data[section_id] = section_content
                    elif isinstance(section_content, dict) and 'content' in section_content:
                        sections_data[section_id] = section_content['content']
        
        # Strategy 2: Check top-level sections
        if not sections_data and 'sections' in metadata:
            sections = metadata['sections']
            if isinstance(sections, dict):
                for section_id, section_content in sections.items():
                    if isinstance(section_content, str):
                        sections_data[section_id] = section_content
        
        # Strategy 3: Check sections_text (clean text versions)
        if 'sections_text' in metadata:
            sections_text = metadata['sections_text']
            if isinstance(sections_text, dict):
                # Prefer clean text versions for term recognition
                for section_id, text_content in sections_text.items():
                    if text_content and isinstance(text_content, str):
                        sections_data[section_id] = text_content
        
        return sections_data
    
    def _clean_section_content(self, content: str) -> str:
        """Clean section content for term recognition."""
        if not content:
            return ""
        
        # Remove HTML tags if present
        import re
        from html import unescape
        
        # Unescape HTML entities
        content = unescape(content)
        
        # Remove HTML tags but preserve the text content
        content = re.sub(r'<[^>]+>', ' ', content)
        
        # Clean up whitespace
        content = re.sub(r'\s+', ' ', content).strip()
        
        return content
    
    def get_document_term_links(self, document_id: int) -> Dict[str, List[Dict]]:
        """Get all term links for a document, grouped by section."""
        return SectionTermLink.get_document_term_links(document_id)
    
    def refresh_ontology_terms(self):
        """Reload ontology terms from the database."""
        logger.info("Refreshing ontology terms...")
        self._load_ontology_terms()