"""
Improved Case Content Cleaner
---------------------------
Enhanced version of the case content cleaner with additional processing
for specific formatting issues in NSPE cases.

This module:
1. Adds specialized cleaning for NSPE case headers (PDF references, metadata)
2. Properly extracts case metadata like case number and year
3. Fixes common content issues for better semantic tagging
"""

import re
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("improved_content_cleaner")

class ImprovedContentCleaner:
    """Enhanced cleaner for NSPE case content."""
    
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
        
        # PDF reference pattern: "TitlePDF12-3-filename.pdf"
        self.pdf_reference_pattern = r'([A-Za-z\s]+)PDF([^\.]+\.pdf)'
        
        # Case metadata patterns
        self.case_number_pattern = r'(?i)Case\s*Number\s*Case\s*([0-9\-]+)'
        self.year_pattern = r'(?i)Year\s*([0-9]{4}|[A-Za-z]+,\s*[A-Za-z]+\s*[0-9]{1,2},\s*[0-9]{4})'
    
    def clean_case(self, case_data):
        """
        Clean and process a case with enhanced cleaning.
        
        Args:
            case_data: Dictionary containing case information
            
        Returns:
            dict: Updated case data with cleaned content and fixed metadata
        """
        if not case_data.get('full_text'):
            logger.warning("No full text to clean")
            return case_data
            
        cleaned_data = case_data.copy()
        
        # First extract metadata from the content
        extracted_metadata = self._extract_metadata(cleaned_data['full_text'])
        
        # Update metadata if found
        if extracted_metadata:
            if 'doc_metadata' not in cleaned_data:
                cleaned_data['doc_metadata'] = {}
            
            for key, value in extracted_metadata.items():
                if value:
                    cleaned_data['doc_metadata'][key] = value
        
        # Clean the full text
        cleaned_data['full_text'] = self._fix_header_formatting(cleaned_data['full_text'])
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
        cleaned_data['metadata']['used_improved_cleaner'] = True
        
        return cleaned_data

    def _extract_metadata(self, text):
        """
        Extract metadata from the case content.
        
        Args:
            text: Raw case text
            
        Returns:
            dict: Extracted metadata
        """
        metadata = {}
        
        # Try to extract title and PDF reference
        pdf_match = re.search(self.pdf_reference_pattern, text)
        if pdf_match:
            title = pdf_match.group(1).strip()
            if title:
                metadata['title'] = title
            
            pdf_ref = pdf_match.group(2).strip()
            if pdf_ref:
                metadata['pdf_reference'] = pdf_ref
        
        # Try to extract case number
        case_number_match = re.search(self.case_number_pattern, text)
        if case_number_match:
            case_number = case_number_match.group(1).strip()
            if case_number:
                metadata['case_number'] = case_number
        
        # Try to extract year
        year_match = re.search(self.year_pattern, text)
        if year_match:
            year_text = year_match.group(1).strip()
            
            # If it's a date, extract just the year
            if ',' in year_text:
                date_parts = year_text.split(',')
                if len(date_parts) > 1:
                    # Extract year from the end of the date
                    year = re.search(r'([0-9]{4})', date_parts[-1])
                    if year:
                        metadata['year'] = year.group(1)
                    else:
                        metadata['year'] = year_text
            else:
                metadata['year'] = year_text
        
        return metadata
        
    def _fix_header_formatting(self, text):
        """
        Fix common header formatting issues in NSPE cases.
        
        Args:
            text: Raw case text
            
        Returns:
            str: Text with fixed header formatting
        """
        if not text:
            return ""
        
        # Fix PDF references in title
        text = re.sub(self.pdf_reference_pattern, r'\1\n\n', text)
        
        # Fix case number formatting
        text = re.sub(self.case_number_pattern, r'Case Number: \1\n', text)
        
        # Fix year formatting
        text = re.sub(self.year_pattern, r'Year: \1\n\n', text)
        
        # Ensure Facts section starts on a new line
        text = re.sub(r'([0-9]{4})\s*Facts', r'\1\n\nFacts', text)
        
        return text
        
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
    Clean and process case content with enhanced cleaning.
    
    Args:
        case_data: Dictionary containing case data
        
    Returns:
        dict: Cleaned case data
    """
    cleaner = ImprovedContentCleaner()
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
        print(f"Extracted metadata: {cleaned.get('doc_metadata', {})}")
        
        if 'sections' in cleaned:
            print(f"Sections found: {list(cleaned['sections'].keys())}")
            
            for section, content in cleaned['sections'].items():
                print(f"\n{section.upper()}:")
                print(f"  {len(content)} characters")
                print(f"  First 50 chars: {content[:50]}...")
    else:
        print("Usage: python improved_content_cleaner.py <file_to_clean>")
