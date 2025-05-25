"""
Improved NSPE Case Extraction Step - Extracts both HTML and plain text versions.
"""
import logging
import re
from bs4 import BeautifulSoup
from .nspe_extraction_step import NSPECaseExtractionStep

logger = logging.getLogger(__name__)

class NSPECaseExtractionStepImproved(NSPECaseExtractionStep):
    """
    Enhanced version that extracts both HTML (for display) and plain text (for embeddings).
    """
    
    def extract_text_only(self, html):
        """
        Extract plain text from HTML, preserving semantic meaning.
        
        Args:
            html: HTML content
            
        Returns:
            str: Plain text with normalized whitespace
        """
        if not html:
            return ""
            
        # Parse HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
            
        # Get text with proper spacing
        lines = []
        for elem in soup.find_all(['p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div']):
            text = elem.get_text(separator=' ', strip=True)
            if text:
                lines.append(text)
                
        # Join lines with proper spacing
        text = '\n'.join(lines)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n', text)
        
        # Clean up special characters
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        text = text.replace('&lt;', '<').replace('&gt;', '>')
        
        return text.strip()
    
    def extract_section_dual(self, soup, section_name, extractor_method):
        """
        Extract both HTML and plain text versions of a section.
        
        Args:
            soup: BeautifulSoup object
            section_name: Name of the section
            extractor_method: Method to extract HTML content
            
        Returns:
            dict: {'html': str, 'text': str}
        """
        # Get HTML version using existing method
        html_content = extractor_method(soup)
        
        if not html_content:
            return {'html': '', 'text': ''}
            
        # Extract plain text version
        text_content = self.extract_text_only(html_content)
        
        return {
            'html': html_content,
            'text': text_content
        }
    
    def process(self, input_data):
        """
        Extract structured content with both HTML and plain text versions.
        
        Returns dict with sections containing both formats.
        """
        # Get base extraction result
        result = super().process(input_data)
        
        if result.get('status') != 'success':
            return result
            
        # Parse HTML again for dual extraction
        html_content = input_data.get('content', '')
        soup = BeautifulSoup(html_content, 'html.parser')
        base_url = self._get_base_url(input_data.get('url', ''))
        
        # Convert sections to dual format
        sections_dual = {}
        
        # Facts
        facts_html = self.extract_facts_section(soup)
        sections_dual['facts'] = {
            'html': self.clean_section_text(facts_html) if facts_html else '',
            'text': self.extract_text_only(facts_html) if facts_html else ''
        }
        
        # Questions
        questions_data = self.extract_questions_section(soup)
        if questions_data and isinstance(questions_data, dict):
            sections_dual['question'] = {
                'html': self.clean_section_text(questions_data.get('html', '')),
                'text': self.extract_text_only(questions_data.get('html', ''))
            }
        else:
            sections_dual['question'] = {'html': '', 'text': ''}
            
        # References
        references_html = self.extract_references_section(soup, base_url)
        sections_dual['references'] = {
            'html': self.clean_section_text(references_html) if references_html else '',
            'text': self.extract_text_only(references_html) if references_html else ''
        }
        
        # Discussion
        discussion_html = self.extract_discussion_section(soup, base_url)
        sections_dual['discussion'] = {
            'html': self.clean_section_text(discussion_html) if discussion_html else '',
            'text': self.extract_text_only(discussion_html) if discussion_html else ''
        }
        
        # Conclusion
        conclusion_data = self.extract_conclusion_section(soup, base_url)
        if isinstance(conclusion_data, dict):
            conclusion_html = conclusion_data.get('html', '')
        else:
            conclusion_html = conclusion_data
            
        sections_dual['conclusion'] = {
            'html': self.clean_section_text(conclusion_html) if conclusion_html else '',
            'text': self.extract_text_only(conclusion_html) if conclusion_html else ''
        }
        
        # Update result with dual format sections
        result['sections_dual'] = sections_dual
        
        # Keep original sections for backward compatibility
        # but update them to use the cleaner text versions for embeddings
        result['sections_for_embeddings'] = {
            'facts': sections_dual['facts']['text'],
            'question': sections_dual['question']['text'],
            'references': sections_dual['references']['text'],
            'discussion': sections_dual['discussion']['text'],
            'conclusion': sections_dual['conclusion']['text']
        }
        
        return result