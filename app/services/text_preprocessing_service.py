"""
Text Preprocessing Service for LLM Analysis

This service cleans HTML text for LLM consumption while preserving important
precedent case links and resolving them to internal ProEthica case references.

Key Features:
- Strip HTML markup while preserving text content
- Extract NSPE case links and resolve to internal cases
- Maintain precedent case metadata for scenario generation
- Provide clean text optimized for LLM analysis
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup

from app.models import Document
from app import db

logger = logging.getLogger(__name__)


class TextPreprocessingService:
    """Service for preprocessing text before LLM analysis."""
    
    def __init__(self):
        # Pattern for NSPE case numbers (e.g., "24-02", "23-4", etc.)
        self.nspe_case_pattern = re.compile(r'\b(\d{1,2})-(\d{1,2})\b')
        
        # Pattern for BER case references (Board of Ethical Review)
        self.ber_case_pattern = re.compile(r'BER\s*[Cc]ase\s*No\.\s*(\d{2}-\d{1,2})', re.IGNORECASE)
        
        # Cache for resolved case mappings
        self._case_url_cache = {}
        self._internal_case_cache = {}
        
    def preprocess_for_llm(self, html_text: str, preserve_precedents: bool = True) -> Dict[str, Any]:
        """
        Preprocess HTML text for LLM consumption.
        
        Args:
            html_text: HTML text from case sections
            preserve_precedents: Whether to extract and resolve precedent cases
            
        Returns:
            Dictionary with clean text and precedent case metadata
        """
        if not html_text:
            return {
                'clean_text': '',
                'precedent_cases': [],
                'processing_notes': []
            }
        
        processing_notes = []
        
        # Extract precedent cases before cleaning
        precedent_cases = []
        if preserve_precedents:
            precedent_cases = self._extract_precedent_cases(html_text)
            if precedent_cases:
                processing_notes.append(f"Extracted {len(precedent_cases)} precedent case references")
        
        # Clean HTML while preserving case reference context
        clean_text = self._clean_html_preserve_context(html_text, precedent_cases)
        
        # Post-process to ensure readability
        clean_text = self._post_process_text(clean_text)
        
        return {
            'clean_text': clean_text,
            'precedent_cases': precedent_cases,
            'processing_notes': processing_notes,
            'original_length': len(html_text),
            'cleaned_length': len(clean_text)
        }
    
    def preprocess_case_sections(self, sections: Dict[str, str]) -> Dict[str, Any]:
        """
        Preprocess all sections in a case for LLM analysis.
        
        Args:
            sections: Dictionary of section name -> HTML content
            
        Returns:
            Dictionary with cleaned sections and consolidated precedent cases
        """
        cleaned_sections = {}
        all_precedent_cases = []
        processing_summary = {}
        
        for section_name, content in sections.items():
            if content:
                processed = self.preprocess_for_llm(content, preserve_precedents=True)
                cleaned_sections[section_name] = processed['clean_text']
                all_precedent_cases.extend(processed['precedent_cases'])
                
                processing_summary[section_name] = {
                    'original_length': processed['original_length'],
                    'cleaned_length': processed['cleaned_length'],
                    'precedent_cases_found': len(processed['precedent_cases'])
                }
        
        # Deduplicate precedent cases
        unique_precedents = self._deduplicate_precedent_cases(all_precedent_cases)
        
        return {
            'cleaned_sections': cleaned_sections,
            'precedent_cases': unique_precedents,
            'processing_summary': processing_summary,
            'total_precedents': len(unique_precedents)
        }
    
    def _extract_precedent_cases(self, html_text: str) -> List[Dict[str, Any]]:
        """Extract precedent case references from HTML text."""
        precedent_cases = []
        
        # Parse HTML
        soup = BeautifulSoup(html_text, 'html.parser')
        
        # Find all links
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link.get('href', '')
            link_text = link.get_text(strip=True)
            
            # Check if this looks like an NSPE case link
            case_info = self._analyze_case_link(href, link_text)
            if case_info:
                # Try to resolve to internal case
                internal_case = self._resolve_to_internal_case(case_info)
                
                precedent_case = {
                    'original_url': href,
                    'link_text': link_text,
                    'case_number': case_info.get('case_number'),
                    'case_type': case_info.get('case_type', 'NSPE'),
                    'internal_case_id': internal_case.get('case_id') if internal_case else None,
                    'internal_case_title': internal_case.get('title') if internal_case else None,
                    'internal_case_url': internal_case.get('url') if internal_case else None,
                    'resolved': internal_case is not None
                }
                precedent_cases.append(precedent_case)
        
        # Also look for case number patterns in text (without links)
        text_only = soup.get_text()
        case_numbers = self._find_case_numbers_in_text(text_only)
        
        for case_num in case_numbers:
            # Check if we already have this case from links
            existing = any(p.get('case_number') == case_num for p in precedent_cases)
            if not existing:
                internal_case = self._resolve_case_number_to_internal(case_num)
                
                precedent_case = {
                    'original_url': None,
                    'link_text': f"Case {case_num}",
                    'case_number': case_num,
                    'case_type': 'NSPE',
                    'internal_case_id': internal_case.get('case_id') if internal_case else None,
                    'internal_case_title': internal_case.get('title') if internal_case else None,
                    'internal_case_url': internal_case.get('url') if internal_case else None,
                    'resolved': internal_case is not None,
                    'found_in_text': True
                }
                precedent_cases.append(precedent_case)
        
        logger.info(f"Extracted {len(precedent_cases)} precedent case references")
        return precedent_cases
    
    def _analyze_case_link(self, href: str, link_text: str) -> Optional[Dict[str, Any]]:
        """Analyze a link to determine if it's an NSPE case reference."""
        # Check for NSPE URLs
        if 'nspe.org' in href.lower():
            # Try to extract case number from URL or link text
            case_number = self._extract_case_number_from_text(link_text) or self._extract_case_number_from_url(href)
            
            if case_number:
                return {
                    'case_number': case_number,
                    'case_type': 'NSPE',
                    'source': 'nspe_website'
                }
        
        # Check for case number patterns in link text
        case_number = self._extract_case_number_from_text(link_text)
        if case_number:
            return {
                'case_number': case_number,
                'case_type': 'NSPE',
                'source': 'text_pattern'
            }
        
        return None
    
    def _extract_case_number_from_text(self, text: str) -> Optional[str]:
        """Extract NSPE case number from text."""
        # Look for BER Case patterns
        ber_match = self.ber_case_pattern.search(text)
        if ber_match:
            return ber_match.group(1)
        
        # Look for general case number patterns
        case_match = self.nspe_case_pattern.search(text)
        if case_match:
            return f"{case_match.group(1)}-{case_match.group(2)}"
        
        return None
    
    def _extract_case_number_from_url(self, url: str) -> Optional[str]:
        """Extract case number from NSPE URL."""
        # Parse URL for case number patterns
        parsed = urlparse(url)
        
        # Check path for case numbers
        case_match = self.nspe_case_pattern.search(parsed.path)
        if case_match:
            return f"{case_match.group(1)}-{case_match.group(2)}"
        
        # Check query parameters
        query_params = parse_qs(parsed.query)
        for param_value in query_params.values():
            for value in param_value:
                case_match = self.nspe_case_pattern.search(value)
                if case_match:
                    return f"{case_match.group(1)}-{case_match.group(2)}"
        
        return None
    
    def _find_case_numbers_in_text(self, text: str) -> List[str]:
        """Find all case numbers mentioned in plain text."""
        case_numbers = []
        
        # Find BER Case references
        ber_matches = self.ber_case_pattern.findall(text)
        case_numbers.extend(ber_matches)
        
        # Find general case number patterns
        case_matches = self.nspe_case_pattern.findall(text)
        for year, num in case_matches:
            case_numbers.append(f"{year}-{num}")
        
        return list(set(case_numbers))  # Remove duplicates
    
    def _resolve_to_internal_case(self, case_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Resolve case information to internal ProEthica case."""
        case_number = case_info.get('case_number')
        
        if not case_number:
            return None
        
        # Check cache first
        if case_number in self._internal_case_cache:
            return self._internal_case_cache[case_number]
        
        # Search database for matching case
        try:
            # Look for exact case number match in metadata using proper JSON query
            from sqlalchemy import text
            
            matching_docs = Document.query.filter(
                Document.document_type.in_(['case', 'case_study']),
                text("doc_metadata->>'case_number' = :case_number")
            ).params(case_number=case_number).all()
            
            for doc in matching_docs:
                if doc.doc_metadata and doc.doc_metadata.get('case_number') == case_number:
                    internal_case = {
                        'case_id': doc.id,
                        'title': doc.title,
                        'url': f"/cases/{doc.id}",
                        'source': doc.source
                    }
                    self._internal_case_cache[case_number] = internal_case
                    return internal_case
            
            # If no exact match, cache as not found
            self._internal_case_cache[case_number] = None
            
        except Exception as e:
            logger.error(f"Error resolving case number {case_number} to internal case: {e}")
        
        return None
    
    def _resolve_case_number_to_internal(self, case_number: str) -> Optional[Dict[str, Any]]:
        """Resolve case number directly to internal case."""
        return self._resolve_to_internal_case({'case_number': case_number})
    
    def _clean_html_preserve_context(self, html_text: str, precedent_cases: List[Dict[str, Any]]) -> str:
        """Clean HTML while preserving precedent case context."""
        soup = BeautifulSoup(html_text, 'html.parser')
        
        # Replace links to precedent cases with clean text markers
        for precedent in precedent_cases:
            if precedent.get('resolved'):
                # Replace with clean reference to internal case
                case_marker = f"[Precedent Case: {precedent['case_number']} - {precedent['internal_case_title']}]"
            else:
                # Mark as external reference
                case_marker = f"[External Case: {precedent['case_number']}]"
            
            # Find and replace the original link
            links = soup.find_all('a', href=precedent.get('original_url'))
            for link in links:
                link.replace_with(case_marker)
        
        # Get clean text
        clean_text = soup.get_text()
        
        # Clean up whitespace
        clean_text = re.sub(r'\s+', ' ', clean_text)
        clean_text = re.sub(r'\n\s*\n', '\n\n', clean_text)
        
        return clean_text.strip()
    
    def _post_process_text(self, text: str) -> str:
        """Post-process text for better LLM readability."""
        # Remove excessive whitespace
        text = re.sub(r' {2,}', ' ', text)
        
        # Fix spacing around punctuation
        text = re.sub(r' +([,.;:])', r'\1', text)
        text = re.sub(r'([,.;:])([A-Za-z])', r'\1 \2', text)
        
        # Ensure proper sentence spacing
        text = re.sub(r'\.([A-Z])', r'. \1', text)
        
        # Clean up line breaks
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    
    def _deduplicate_precedent_cases(self, precedent_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate precedent case references."""
        seen_cases = set()
        unique_cases = []
        
        for case in precedent_cases:
            case_key = case.get('case_number', '') + case.get('original_url', '')
            if case_key not in seen_cases:
                seen_cases.add(case_key)
                unique_cases.append(case)
        
        return unique_cases
    
    def preprocess_event_text(self, event_text: str) -> Dict[str, Any]:
        """Preprocess text from a single event for LLM analysis."""
        return self.preprocess_for_llm(event_text, preserve_precedents=True)
    
    def preprocess_decision_text(self, decision_text: str, context_text: str = "") -> Dict[str, Any]:
        """Preprocess decision text and context for LLM analysis."""
        # Process decision text
        decision_processed = self.preprocess_for_llm(decision_text, preserve_precedents=True)
        
        # Process context text if provided
        context_processed = {}
        if context_text:
            context_processed = self.preprocess_for_llm(context_text, preserve_precedents=True)
        
        # Combine precedent cases from both sources
        all_precedents = decision_processed['precedent_cases']
        if context_processed.get('precedent_cases'):
            all_precedents.extend(context_processed['precedent_cases'])
        
        unique_precedents = self._deduplicate_precedent_cases(all_precedents)
        
        return {
            'clean_decision_text': decision_processed['clean_text'],
            'clean_context_text': context_processed.get('clean_text', ''),
            'precedent_cases': unique_precedents,
            'processing_notes': decision_processed['processing_notes'] + context_processed.get('processing_notes', [])
        }
    
    def get_precedent_case_summary(self, precedent_cases: List[Dict[str, Any]]) -> str:
        """Generate a summary of precedent cases for LLM context."""
        if not precedent_cases:
            return ""
        
        summary_lines = ["PRECEDENT CASES REFERENCED:"]
        
        for case in precedent_cases:
            if case.get('resolved'):
                summary_lines.append(f"- Case {case['case_number']}: {case['internal_case_title']} (Internal Case ID: {case['internal_case_id']})")
            else:
                summary_lines.append(f"- Case {case['case_number']}: External NSPE case reference")
        
        return "\n".join(summary_lines)
    
    def enhance_llm_prompt_with_precedents(self, base_prompt: str, precedent_cases: List[Dict[str, Any]]) -> str:
        """Enhance LLM prompt with precedent case context."""
        if not precedent_cases:
            return base_prompt
        
        precedent_summary = self.get_precedent_case_summary(precedent_cases)
        
        enhanced_prompt = f"""{base_prompt}

{precedent_summary}

When analyzing this case, please consider how the referenced precedent cases might inform your reasoning. If internal ProEthica cases are referenced, you can assume they provide relevant ethical guidance for this analysis."""
        
        return enhanced_prompt


# Global service instance
_global_preprocessor = None

def get_text_preprocessor() -> TextPreprocessingService:
    """Get the global text preprocessing service instance."""
    global _global_preprocessor
    if _global_preprocessor is None:
        _global_preprocessor = TextPreprocessingService()
    return _global_preprocessor
