"""
Case Content Cleaner
------------------
Processes and cleans case content to improve quality of semantic tagging.

This module:
1. Normalizes whitespace and formatting
2. Identifies and structures case sections
3. Cleans up common formatting issues and artifacts
4. Extracts key elements like the ethical verdict
"""

import re
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("case_content_cleaner")

class CaseContentCleaner:
    """Cleans and processes case content."""
    
    def __init__(self):
        """Initialize the cleaner with common patterns."""
        # Common section headers in NSPE cases
        self.section_patterns = {
            'facts': r'(?i)^\s*facts\s*:?\s*$',
            'question': r'(?i)^\s*question\s*:?\s*$',
            'references': r'(?i)^\s*references\s*:?\s*$',
            'discussion': r'(?i)^\s*discussion\s*:?\s*$',
            'conclusion': r'(?i)^\s*conclusion\s*:?\s*$'
        }
        
        # Common artifacts to remove
        self.artifacts = [
            r'©\s*NSPE.*$',
            r'www\.nspe\.org',
            r'Page\s+\d+\s+of\s+\d+',
            r'Board of Ethical Review Case Files'
        ]
        
    def clean_case(self, case_data):
        """
        Clean and process a case.
        
        Args:
            case_data: Dictionary containing case information
            
        Returns:
            dict: Updated case data with cleaned content
        """
        if not case_data.get('full_text'):
            logger.warning("No full text to clean")
            return case_data
            
        cleaned_data = case_data.copy()
        
        # Clean the full text
        cleaned_data['full_text'] = self._clean_text(cleaned_data['full_text'])
        
        # Extract and structure sections
        sections = self._extract_sections(cleaned_data['full_text'])
        if sections:
            cleaned_data['sections'] = sections
            
            # Extract description (typically the preamble and facts)
            description_parts = []
            if 'preamble' in sections:
                description_parts.append(sections['preamble'])
            if 'facts' in sections:
                description_parts.append(sections['facts'])
                
            if description_parts:
                cleaned_data['description'] = '\n\n'.join(description_parts)
                
            # Extract decision (conclusion section)
            if 'conclusion' in sections:
                cleaned_data['decision'] = sections['conclusion']
                
        # Add metadata for cleaning
        if 'metadata' not in cleaned_data:
            cleaned_data['metadata'] = {}
            
        cleaned_data['metadata']['cleaned_at'] = datetime.now().isoformat()
        cleaned_data['metadata']['section_count'] = len(cleaned_data.get('sections', {}))
        
        return cleaned_data
        
    def _clean_text(self, text):
        """
        Clean text content.
        
        Args:
            text: Raw text content
            
        Returns:
            str: Cleaned text
        """
        if not text:
            return ""
            
        # Normalize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove common artifacts
        for pattern in self.artifacts:
            text = re.sub(pattern, '', text, flags=re.MULTILINE)
            
        # Normalize whitespace within lines
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Split into lines and remove empty lines
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        
        # Remove consecutive empty lines (reduce to one)
        cleaned_lines = []
        previous_empty = False
        
        for line in lines:
            if not line:
                if not previous_empty:
                    cleaned_lines.append(line)
                    previous_empty = True
            else:
                cleaned_lines.append(line)
                previous_empty = False
                
        # Rejoin text
        return '\n'.join(cleaned_lines)
        
    def _extract_sections(self, text):
        """
        Extract sections from case text.
        
        Args:
            text: Case text content
            
        Returns:
            dict: Dictionary of sections
        """
        if not text:
            return {}
            
        lines = text.split('\n')
        current_section = 'preamble'
        sections = {current_section: []}
        
        for line in lines:
            # Check if line is a section header
            match_found = False
            
            for section_name, pattern in self.section_patterns.items():
                if re.match(pattern, line):
                    current_section = section_name
                    sections[current_section] = [line]
                    match_found = True
                    break
                    
            if not match_found:
                # Add line to current section
                if current_section in sections:
                    sections[current_section].append(line)
                else:
                    sections[current_section] = [line]
                    
        # Join lines for each section
        for section, lines in sections.items():
            sections[section] = '\n'.join(lines).strip()
            
        return sections


def clean_case_content(case_data):
    """
    Clean and process case content.
    
    Args:
        case_data: Dictionary containing case data
        
    Returns:
        dict: Cleaned case data
    """
    cleaner = CaseContentCleaner()
    return cleaner.clean_case(case_data)


if __name__ == "__main__":
    # Simple test if run directly
    import sys
    
    if len(sys.argv) > 1:
        # Read a file and clean it
        with open(sys.argv[1], 'r') as f:
            text = f.read()
            
        test_case = {
            'title': 'Test Case',
            'full_text': text
        }
        
        cleaned = clean_case_content(test_case)
        
        print(f"Original length: {len(text)} characters")
        print(f"Cleaned length: {len(cleaned['full_text'])} characters")
        
        if 'sections' in cleaned:
            print(f"Sections found: {list(cleaned['sections'].keys())}")
            
            for section, content in cleaned['sections'].items():
                print(f"\n{section.upper()}:")
                print(f"  {len(content)} characters")
                print(f"  First 50 chars: {content[:50]}...")
    else:
        print("Usage: python case_content_cleaner.py <file_to_clean>")
