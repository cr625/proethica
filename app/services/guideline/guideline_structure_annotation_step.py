"""
Guideline Structure Annotation Step for extracting structured sections from guidelines documents.

This service extracts individual sections (like I.1, II.1.c, III.3) from ethical guidelines
documents such as the NSPE Code of Ethics, storing them as GuidelineSection records for
precise referencing and interactive tooltips.
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from app.models import db
from app.models.guideline_section import GuidelineSection
from app.services.section_embedding_service import SectionEmbeddingService

logger = logging.getLogger(__name__)

class GuidelineStructureAnnotationStep:
    """
    Service for extracting structured sections from guidelines documents.
    
    Currently supports:
    - NSPE Code of Ethics format (I.1, II.1.c, III.3, etc.)
    - Hierarchical section structures
    - Automatic categorization and ordering
    """
    
    def __init__(self):
        """Initialize the guideline structure annotation service."""
        self.embedding_service = SectionEmbeddingService()
    
    def process(self, guideline_document) -> Dict[str, Any]:
        """
        Extract structured sections from a guideline document.
        
        Args:
            guideline_document: Guideline model instance
            
        Returns:
            dict: Processing results including section count and any errors
        """
        try:
            logger.info(f"Starting guideline structure annotation for guideline {guideline_document.id}")
            
            # Determine the format and extract sections
            if self._is_nspe_format(guideline_document.content):
                sections = self._extract_nspe_sections(guideline_document.content)
                format_type = "nspe"
            else:
                # For non-NSPE formats, attempt generic extraction
                sections = self._extract_generic_sections(guideline_document.content)
                format_type = "generic"
            
            logger.info(f"Extracted {len(sections)} sections from {format_type} format guideline")
            
            # Store sections in database
            sections_created = self._store_sections(guideline_document.id, sections)
            
            # Update guideline metadata
            self._update_guideline_metadata(guideline_document, format_type, len(sections_created))
            
            return {
                'success': True,
                'format_type': format_type,
                'sections_extracted': len(sections),
                'sections_created': len(sections_created),
                'guideline_id': guideline_document.id
            }
            
        except Exception as e:
            logger.exception(f"Error in guideline structure annotation: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'guideline_id': guideline_document.id
            }
    
    def _is_nspe_format(self, content: str) -> bool:
        """
        Check if the content appears to be in NSPE Code of Ethics format.
        
        Args:
            content: Document content string
            
        Returns:
            bool: True if content matches NSPE format
        """
        # Look for NSPE-specific patterns
        nspe_indicators = [
            r'# NSPE Code of Ethics',
            r'## I\. Fundamental Canons',
            r'## II\. Rules of Practice',
            r'## III\. Professional Obligations',
            r'Engineers, in the fulfillment of their professional duties'
        ]
        
        matches = sum(1 for pattern in nspe_indicators if re.search(pattern, content, re.IGNORECASE))
        return matches >= 3  # Require at least 3 indicators
    
    def _extract_nspe_sections(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract sections from NSPE Code of Ethics format.
        
        Args:
            content: NSPE document content
            
        Returns:
            List of section dictionaries
        """
        sections = []
        
        # Extract Fundamental Canons (I.1, I.2, etc.)
        sections.extend(self._extract_fundamental_canons(content))
        
        # Extract Rules of Practice (II.1.a, II.2.b, etc.)
        sections.extend(self._extract_rules_of_practice(content))
        
        # Extract Professional Obligations (III.1, III.2, etc.)
        sections.extend(self._extract_professional_obligations(content))
        
        return sections
    
    def _extract_fundamental_canons(self, content: str) -> List[Dict[str, Any]]:
        """Extract Fundamental Canons sections (I.1, I.2, etc.)."""
        sections = []
        
        # Find the Fundamental Canons section
        canons_match = re.search(r'## I\. Fundamental Canons\s*\n(.*?)(?=## II\.|$)', content, re.DOTALL)
        if not canons_match:
            return sections
        
        canons_content = canons_match.group(1)
        
        # Extract individual canons (numbered list) - more flexible pattern
        # Look for lines that start with a number followed by a period
        lines = canons_content.split('\n')
        current_canon = None
        current_text = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if line starts with a number followed by a period
            canon_match = re.match(r'^(\d+)\.\s+(.+)', line)
            if canon_match:
                # Save previous canon if exists
                if current_canon is not None and current_text:
                    section_code = f"I.{current_canon}"
                    section_text = ' '.join(current_text).strip()
                    
                    sections.append({
                        'section_code': section_code,
                        'section_title': f'Fundamental Canon {section_code}',
                        'section_text': section_text,
                        'section_category': 'fundamental_canons',
                        'section_subcategory': self._categorize_fundamental_canon(section_text),
                        'section_order': current_canon,
                        'parent_section_code': 'I'
                    })
                
                # Start new canon
                current_canon = int(canon_match.group(1))
                current_text = [canon_match.group(2)]
            elif current_canon is not None:
                # Continue current canon text
                current_text.append(line)
        
        # Don't forget the last canon
        if current_canon is not None and current_text:
            section_code = f"I.{current_canon}"
            section_text = ' '.join(current_text).strip()
            
            sections.append({
                'section_code': section_code,
                'section_title': f'Fundamental Canon {section_code}',
                'section_text': section_text,
                'section_category': 'fundamental_canons',
                'section_subcategory': self._categorize_fundamental_canon(section_text),
                'section_order': current_canon,
                'parent_section_code': 'I'
            })
        
        return sections
    
    def _extract_rules_of_practice(self, content: str) -> List[Dict[str, Any]]:
        """Extract Rules of Practice sections (II.1.a, II.2.b, etc.)."""
        sections = []
        
        # Find the Rules of Practice section
        rules_match = re.search(r'## II\. Rules of Practice\s*\n(.*?)(?=## III\.|$)', content, re.DOTALL)
        if not rules_match:
            return sections
        
        rules_content = rules_match.group(1)
        
        # Extract main rule sections (### 1. Engineers shall...)
        main_rule_pattern = r'### (\d+)\.\s+([^\n]+)\n(.*?)(?=### \d+\.|$)'
        main_rule_matches = re.findall(main_rule_pattern, rules_content, re.DOTALL)
        
        for rule_num, rule_title, rule_body in main_rule_matches:
            # Extract bullet points as sub-sections
            bullet_pattern = r'-\s+([^\n-]+)'
            bullet_matches = re.findall(bullet_pattern, rule_body)
            
            for i, bullet_text in enumerate(bullet_matches):
                section_code = f"II.{rule_num}.{chr(97 + i)}"  # II.1.a, II.1.b, etc.
                
                sections.append({
                    'section_code': section_code,
                    'section_title': f'Rules of Practice {section_code}',
                    'section_text': bullet_text.strip(),
                    'section_category': 'rules_of_practice',
                    'section_subcategory': self._categorize_rule_of_practice(rule_title),
                    'section_order': int(rule_num) * 100 + i + 1,
                    'parent_section_code': f'II.{rule_num}'
                })
        
        return sections
    
    def _extract_professional_obligations(self, content: str) -> List[Dict[str, Any]]:
        """Extract Professional Obligations sections (III.1, III.2, etc.)."""
        sections = []
        
        # Find the Professional Obligations section
        obligations_match = re.search(r'## III\. Professional Obligations\s*\n(.*?)(?=\n---|\n## |\Z)', content, re.DOTALL)
        if not obligations_match:
            return sections
        
        obligations_content = obligations_match.group(1)
        
        # Extract main obligation sections (### 1. Engineers shall...)
        main_obligation_pattern = r'### (\d+)\.\s+([^\n]+)\n(.*?)(?=### \d+\.|$)'
        main_obligation_matches = re.findall(main_obligation_pattern, obligations_content, re.DOTALL)
        
        for obligation_num, obligation_title, obligation_body in main_obligation_matches:
            # Extract bullet points as sub-sections
            bullet_pattern = r'-\s+([^\n-]+)'
            bullet_matches = re.findall(bullet_pattern, obligation_body)
            
            if bullet_matches:
                # If there are bullet points, create sub-sections
                for i, bullet_text in enumerate(bullet_matches):
                    section_code = f"III.{obligation_num}.{chr(97 + i)}"  # III.1.a, III.1.b, etc.
                    
                    sections.append({
                        'section_code': section_code,
                        'section_title': f'Professional Obligations {section_code}',
                        'section_text': bullet_text.strip(),
                        'section_category': 'professional_obligations',
                        'section_subcategory': self._categorize_professional_obligation(obligation_title),
                        'section_order': int(obligation_num) * 100 + i + 1,
                        'parent_section_code': f'III.{obligation_num}'
                    })
            else:
                # If no bullet points, treat the whole section as one
                section_code = f"III.{obligation_num}"
                
                sections.append({
                    'section_code': section_code,
                    'section_title': f'Professional Obligations {section_code}',
                    'section_text': obligation_body.strip(),
                    'section_category': 'professional_obligations',
                    'section_subcategory': self._categorize_professional_obligation(obligation_title),
                    'section_order': int(obligation_num) * 100,
                    'parent_section_code': 'III'
                })
        
        return sections
    
    def _categorize_fundamental_canon(self, text: str) -> str:
        """Categorize a fundamental canon based on its content."""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['safety', 'health', 'welfare', 'public']):
            return 'safety_health_welfare'
        elif any(word in text_lower for word in ['competence', 'qualified', 'expertise']):
            return 'competence'
        elif any(word in text_lower for word in ['truthful', 'objective', 'public statements']):
            return 'truthfulness'
        elif any(word in text_lower for word in ['faithful', 'agent', 'trustee', 'employer', 'client']):
            return 'loyalty'
        elif any(word in text_lower for word in ['deceptive', 'honest', 'integrity']):
            return 'honesty'
        elif any(word in text_lower for word in ['honor', 'reputation', 'profession']):
            return 'professional_dignity'
        else:
            return 'general'
    
    def _categorize_rule_of_practice(self, title: str) -> str:
        """Categorize a rule of practice based on its title."""
        title_lower = title.lower()
        
        if 'safety' in title_lower or 'health' in title_lower or 'welfare' in title_lower:
            return 'safety_health_welfare'
        elif 'competence' in title_lower:
            return 'competence'
        elif 'public statements' in title_lower or 'truthful' in title_lower:
            return 'truthfulness'
        elif 'employer' in title_lower or 'client' in title_lower or 'faithful' in title_lower:
            return 'loyalty'
        elif 'deceptive' in title_lower:
            return 'honesty'
        else:
            return 'general'
    
    def _categorize_professional_obligation(self, title: str) -> str:
        """Categorize a professional obligation based on its title."""
        title_lower = title.lower()
        
        if 'honesty' in title_lower or 'integrity' in title_lower:
            return 'honesty_integrity'
        elif 'public interest' in title_lower:
            return 'public_interest'
        elif 'deceive' in title_lower or 'deception' in title_lower:
            return 'avoid_deception'
        elif 'confidentiality' in title_lower:
            return 'confidentiality'
        elif 'conflict' in title_lower:
            return 'conflicts_of_interest'
        elif 'gain' in title_lower or 'improper' in title_lower:
            return 'improper_gain'
        elif 'reputation' in title_lower:
            return 'professional_reputation'
        elif 'responsibility' in title_lower:
            return 'responsibility'
        elif 'credit' in title_lower:
            return 'attribution'
        else:
            return 'general'
    
    def _extract_generic_sections(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract sections from non-NSPE format documents.
        
        This is a fallback method for documents that don't follow NSPE format.
        """
        sections = []
        
        # Split by major headings (## or #)
        heading_pattern = r'^(#{1,3})\s+(.+)$'
        lines = content.split('\n')
        
        current_section = None
        current_content = []
        section_order = 1
        
        for line in lines:
            heading_match = re.match(heading_pattern, line)
            
            if heading_match:
                # Save previous section if exists
                if current_section:
                    sections.append({
                        'section_code': f"S.{section_order}",
                        'section_title': current_section,
                        'section_text': '\n'.join(current_content).strip(),
                        'section_category': 'generic',
                        'section_subcategory': 'general',
                        'section_order': section_order,
                        'parent_section_code': None
                    })
                    section_order += 1
                
                # Start new section
                current_section = heading_match.group(2).strip()
                current_content = []
            else:
                if current_section:  # Only collect content if we have a section
                    current_content.append(line)
        
        # Don't forget the last section
        if current_section and current_content:
            sections.append({
                'section_code': f"S.{section_order}",
                'section_title': current_section,
                'section_text': '\n'.join(current_content).strip(),
                'section_category': 'generic',
                'section_subcategory': 'general',
                'section_order': section_order,
                'parent_section_code': None
            })
        
        return sections
    
    def _store_sections(self, guideline_id: int, sections: List[Dict[str, Any]]) -> List[GuidelineSection]:
        """
        Store extracted sections in the database.
        
        Args:
            guideline_id: ID of the parent guideline
            sections: List of section dictionaries
            
        Returns:
            List of created GuidelineSection objects
        """
        created_sections = []
        
        # Clear existing sections for this guideline
        GuidelineSection.query.filter_by(guideline_id=guideline_id).delete()
        
        for section_data in sections:
            try:
                # Generate embedding for the section text
                embedding = None
                try:
                    embedding = self.embedding_service.get_embedding(section_data['section_text'])
                except Exception as e:
                    logger.warning(f"Failed to generate embedding for section {section_data['section_code']}: {e}")
                
                # Create GuidelineSection object
                section = GuidelineSection(
                    guideline_id=guideline_id,
                    section_code=section_data['section_code'],
                    section_title=section_data['section_title'],
                    section_text=section_data['section_text'],
                    section_category=section_data['section_category'],
                    section_subcategory=section_data['section_subcategory'],
                    section_order=section_data['section_order'],
                    parent_section_code=section_data.get('parent_section_code'),
                    embedding=embedding
                )
                
                db.session.add(section)
                created_sections.append(section)
                
            except Exception as e:
                logger.error(f"Error creating section {section_data['section_code']}: {e}")
                continue
        
        # Commit all sections
        db.session.commit()
        logger.info(f"Successfully stored {len(created_sections)} sections for guideline {guideline_id}")
        
        return created_sections
    
    def _update_guideline_metadata(self, guideline_document, format_type: str, section_count: int):
        """Update the guideline document metadata with structure information."""
        try:
            # Get current metadata or create new
            metadata = guideline_document.guideline_metadata or {}
            
            # Add structure information
            metadata['structure_annotation'] = {
                'format_type': format_type,
                'section_count': section_count,
                'annotated_at': datetime.utcnow().isoformat(),
                'annotation_version': '1.0'
            }
            
            # Update the guideline
            guideline_document.guideline_metadata = metadata
            db.session.commit()
            
            logger.info(f"Updated metadata for guideline {guideline_document.id}")
            
        except Exception as e:
            logger.error(f"Error updating guideline metadata: {e}")
    
    def get_sections_for_codes(self, guideline_id: int, section_codes: List[str]) -> Dict[str, GuidelineSection]:
        """
        Get guideline sections for specific codes.
        
        Args:
            guideline_id: ID of the guideline
            section_codes: List of codes like ["I.1", "II.1.c"]
            
        Returns:
            Dictionary mapping codes to GuidelineSection objects
        """
        sections = GuidelineSection.query.filter(
            GuidelineSection.guideline_id == guideline_id,
            GuidelineSection.section_code.in_(section_codes)
        ).all()
        
        return {section.section_code: section for section in sections}