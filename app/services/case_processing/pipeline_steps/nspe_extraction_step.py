"""
NSPE Case Extraction Step - Extracts structured content from NSPE case HTML.
"""
import logging
import re
import requests
from bs4 import BeautifulSoup
from .base_step import BaseStep
from urllib.parse import urljoin, urlparse

# Set up logging
logger = logging.getLogger(__name__)

class NSPECaseExtractionStep(BaseStep):
    """Step for extracting structured content from NSPE case HTML."""
    
    def __init__(self):
        super().__init__()
        self.description = "Extracts structured content from NSPE case HTML"
        
    def validate_input(self, input_data):
        """Validate that the input contains HTML content."""
        if not input_data or not isinstance(input_data, dict):
            logger.error("Invalid input: Input must be a dictionary")
            return False
            
        if 'content' not in input_data:
            logger.error("Invalid input: 'content' key is required")
            return False
            
        content = input_data.get('content', '')
        if not content or not isinstance(content, str):
            logger.error("Invalid content: Empty or not a string")
            return False
            
        # Check if content appears to be HTML
        if '<html' not in content.lower() and '<body' not in content.lower() and '<div' not in content.lower():
            logger.warning("Content may not be HTML, but will try to process anyway")
            
        return True
        
    def get_error_result(self, message, details=None):
        """Return a standardized error result."""
        return {
            'status': 'error',
            'message': message,
            'details': details or {}
        }
        
    def extract_pdf_url(self, soup, url):
        """Extract PDF URL from the page."""
        # Try to find PDF links
        pdf_links = soup.find_all('a', href=lambda href: href and href.lower().endswith('.pdf'))
        
        if pdf_links:
            pdf_url = pdf_links[0]['href']
            # If it's a relative URL, convert to absolute
            if pdf_url.startswith('/'):
                # Extract the base URL
                base_url = self._get_base_url(url)
                pdf_url = base_url + pdf_url
            return pdf_url
        
        return None

    def _get_base_url(self, url):
        """Extract base URL for creating absolute URLs from relative ones."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
        
    def extract_case_number(self, soup):
        """Extract case number from the page."""
        # Method 1: Look for the case number in the specific div structure
        case_number_div = soup.find('div', class_='field--name-field-case-number')
        if case_number_div:
            field_item = case_number_div.find('div', class_='field__item')
            if field_item:
                case_text = field_item.get_text().strip()
                case_number_match = re.search(r'Case\s+(\d{1,2}-\d{1,2})', case_text)
                if case_number_match:
                    return case_number_match.group(1)
                return case_text.replace('Case', '').strip()
        
        # Method 2: Look for "BER Case XX-X" pattern
        content_text = soup.get_text()
        case_number_match = re.search(r'BER\s+Case\s+(\d{1,2}-\d{1,2})', content_text)
        if case_number_match:
            return case_number_match.group(1)
        
        # Method 3: Look in the title
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text()
            case_number_match = re.search(r'Case\s+(\d{1,2}-\d{1,2})', title_text)
            if case_number_match:
                return case_number_match.group(1)
        
        # Method 4: Look in heading elements
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        for heading in headings:
            heading_text = heading.get_text()
            case_number_match = re.search(r'Case\s+(\d{1,2}-\d{1,2})', heading_text)
            if case_number_match:
                return case_number_match.group(1)
        
        return None
        
    def extract_year(self, soup, case_number):
        """Extract year from the page or case number."""
        # If case number exists and has year format (e.g., 23-4 for 2023)
        if case_number:
            year_prefix = case_number.split('-')[0]
            if len(year_prefix) == 2:
                # Assume 20xx for modern cases, 19xx for older
                century = "20" if int(year_prefix) < 50 else "19"
                return century + year_prefix
                
        # Look for a year pattern in the text
        content_text = soup.get_text()
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', content_text)
        if year_match:
            return year_match.group(1)
            
        return None
        
    def extract_facts_section(self, soup):
        """Extract the facts section using specific HTML structure."""
        facts_div = soup.find('div', class_='field--name-field-case-facts')
        if facts_div:
            # Find the field__item which contains the actual content
            field_item = facts_div.find('div', class_='field__item')
            if field_item:
                # Extract just the essential content
                return self._clean_minimal_html(str(field_item))
            # If no field__item, use the whole div
            return self._extract_section_html(facts_div, "Facts")
        return None
        
    def extract_questions_section(self, soup):
        """
        Extract questions section using specific class targeting.
        Returns both the raw HTML and a list of individual questions if available.
        """
        # First try the specific class pattern
        questions_div = soup.find('div', class_='field--name-field-case-question')
        if questions_div:
            # Find the field__item which contains the actual content
            field_item = questions_div.find('div', class_='field__item')
            if field_item:
                # Extract just the essential content
                clean_html = self._clean_minimal_html(str(field_item))
                
                # Parse the cleaned HTML to extract individual questions from ordered lists
                questions_list = self._extract_individual_questions(clean_html)
                
                return {
                    'html': clean_html,
                    'questions': questions_list
                }
        
        # Fall back to more generic extraction if specific pattern not found
        return None
        
    def _extract_individual_questions(self, html):
        """
        Extract individual questions from HTML content, particularly from ordered lists.
        
        Args:
            html: HTML content containing questions
            
        Returns:
            list: List of individual questions as strings
        """
        if not html:
            return []
            
        # Parse the HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        questions = []
        
        # Look for ordered lists first (most common format for multiple questions)
        ordered_list = soup.find('ol')
        if ordered_list:
            # Extract each list item as a separate question
            for item in ordered_list.find_all('li'):
                questions.append(item.get_text().strip())
            return questions
        
        # If no ordered list is found, check for unordered lists
        unordered_list = soup.find('ul')
        if unordered_list:
            for item in unordered_list.find_all('li'):
                questions.append(item.get_text().strip())
            return questions
        
        # If no list is found, use the entire content as a single question
        text_content = soup.get_text().strip()
        if text_content:
            questions.append(text_content)
            
        return questions
        
    def _clean_minimal_html(self, html):
        """
        Clean HTML content but preserve only essential elements like lists and links.
        This is more aggressive than _clean_html_preserve_links, retaining only
        necessary structured content.
        """
        if not html:
            return ""
            
        # Create a BeautifulSoup object from the HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Keep only essential tags and their content
        allowed_tags = ['p', 'ol', 'ul', 'li', 'a', 'strong', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']
        
        # Process the content, preserving only essential tags
        for tag in soup.find_all(True):
            if tag.name not in allowed_tags:
                tag.unwrap()  # unwrap keeps the content but removes the tag
        
        # Clean attributes except href for links
        for tag in soup.find_all(True):
            if tag.name == 'a' and tag.has_attr('href'):
                href = tag['href']
                tag.attrs = {}  # Clear all attributes
                tag['href'] = href  # Keep only href attribute
            else:
                tag.attrs = {}  # Clear all attributes for non-anchor tags
        
        # Get the cleaned HTML
        cleaned_html = str(soup)
        
        # Fix excessive whitespace but preserve formatting
        cleaned_html = re.sub(r'\n\s*\n', '\n\n', cleaned_html)
        cleaned_html = re.sub(r'>\s+<', '><', cleaned_html)
        
        return cleaned_html
        
    def extract_section(self, soup, start_marker, end_markers=None, base_url=None):
        """
        Extract content between a start marker and any of the end markers.
        
        Args:
            soup: BeautifulSoup object
            start_marker: Text marking the beginning of the section
            end_markers: List of texts marking possible ends of the section
            base_url: Base URL for converting relative links to absolute
            
        Returns:
            str: Extracted section content or None if not found
        """
        # Try to find section by looking for specific headers or paragraphs
        start_marker_lower = start_marker.lower().rstrip(':')
        end_markers_lower = [marker.lower().rstrip(':') for marker in end_markers] if end_markers else []
        
        # Find paragraphs and headings that might contain section markers
        potential_markers = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div'])
        
        # Find the start element
        start_element = None
        start_idx = None
        for i, element in enumerate(potential_markers):
            text = element.get_text().lower()
            # Check if this element contains the start marker
            if start_marker_lower in text and (
                text.strip() == start_marker_lower or
                text.strip() == start_marker_lower + ':' or
                text.strip().startswith(start_marker_lower + ':') or
                re.search(r'\b' + re.escape(start_marker_lower) + r'[:\s]*$', text)
            ):
                start_element = element
                start_idx = i
                break
        
        if start_element and start_idx is not None:
            # Find the end element
            end_idx = len(potential_markers)
            for i in range(start_idx + 1, len(potential_markers)):
                element = potential_markers[i]
                text = element.get_text().lower()
                
                # Check if this element is an end marker
                if any(end_marker in text and (
                    text.strip() == end_marker or
                    text.strip() == end_marker + ':' or
                    text.strip().startswith(end_marker + ':') or
                    re.search(r'\b' + re.escape(end_marker) + r'[:\s]*$', text)
                ) for end_marker in end_markers_lower):
                    end_idx = i
                    break
            
            # Extract the section elements
            section_elements = potential_markers[start_idx+1:end_idx]
            
            # If we found elements, convert them to HTML strings with links preserved
            if section_elements:
                section_html = ""
                for element in section_elements:
                    section_html += str(element)
                return self._clean_html_preserve_links(section_html, base_url)
        
        # Fall back to standard text-based extraction
        content_text = soup.get_text()
        start_pos = -1
        for marker in [start_marker, start_marker.title(), start_marker.upper()]:
            start_pos = content_text.find(marker)
            if start_pos >= 0:
                start_pos += len(marker)
                break
                
        if start_pos >= 0:
            # Find the first end marker
            end_pos = len(content_text)
            if end_markers:
                for end_marker in end_markers:
                    for variant in [end_marker, end_marker.title(), end_marker.upper()]:
                        pos = content_text.find(variant, start_pos)
                        if pos >= 0 and pos < end_pos:
                            end_pos = pos
                            break
                            
            return content_text[start_pos:end_pos].strip()
            
        return None

    def _extract_section_html(self, section_element, section_name):
        """Extract HTML content from a section element preserving links and formatting."""
        if not section_element:
            return None
            
        # Get HTML content
        html_content = str(section_element)
        
        # Clean up but preserve links and basic formatting
        cleaned_html = self._clean_html_preserve_links(html_content)
        
        # Remove section header if present
        cleaned_html = re.sub(rf'<[^>]*>{section_name}:?</[^>]*>', '', cleaned_html, flags=re.IGNORECASE)
        
        return cleaned_html
    
    def _clean_html_preserve_links(self, html, base_url=None):
        """
        Clean HTML content but preserve links and minimal formatting.
        This preserves <a> tags, basic formatting, and removes unwanted elements.
        
        Args:
            html: HTML content to clean
            base_url: Base URL for converting relative links to absolute
            
        Returns:
            str: Cleaned HTML content with links preserved
        """
        if not html:
            return ""
            
        # Create a BeautifulSoup object from the HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Process links to make them absolute if needed
        if base_url:
            for link in soup.find_all('a', href=True):
                href = link['href']
                if not href.startswith(('http://', 'https://', 'mailto:', 'tel:')):
                    link['href'] = urljoin(base_url, href)
        
        # Find all NSPE case references and mark them
        self._mark_case_references(soup)
        
        # Remove all divs but keep their content
        for div in soup.find_all('div'):
            div.unwrap()
            
        # Remove classes and ids but keep href attributes
        for tag in soup.find_all(True):
            if tag.name not in ['a']:  # Keep a tags intact
                if 'class' in tag.attrs:
                    del tag['class']
                if 'id' in tag.attrs:
                    del tag['id']
                if 'style' in tag.attrs:
                    del tag['style']
            
        # Get the cleaned HTML
        cleaned_html = str(soup)
        
        # Fix excessive whitespace but preserve formatting
        cleaned_html = re.sub(r'\n\s*\n', '\n\n', cleaned_html)
        
        return cleaned_html
    
    def _mark_case_references(self, soup):
        """
        Find references to other NSPE cases in the text and mark them.
        
        Args:
            soup: BeautifulSoup object
        """
        # Find case references in text nodes
        case_pattern = re.compile(r'\b(?:BER\s+)?Case\s+(\d{1,2}-\d{1,2})\b')
        
        # Iterate through all text nodes
        for text in soup.find_all(text=True):
            if case_pattern.search(text):
                # Get parent element
                parent = text.parent
                
                # Don't process if the parent is already an anchor
                if parent.name == 'a':
                    continue
                
                # Replace the text with marked-up text
                new_text = case_pattern.sub(r'<span class="case-reference">Case \1</span>', text)
                new_soup = BeautifulSoup(new_text, 'html.parser')
                text.replace_with(new_soup)
    
    def clean_section_text(self, text):
        """Clean up extracted section text but preserve links."""
        if not text:
            return ""
        
        # If the text already has HTML tags, return it as is
        if '<a ' in text or '<span ' in text:
            return text
            
        # Otherwise, apply standard cleaning
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove any HTML tags that might remain
        text = re.sub(r'<[^>]+>', '', text)
        
        # Clean up any remaining special characters
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        
        return text.strip()
        
    def process(self, input_data):
        """
        Extract structured content from NSPE case HTML.
        
        Args:
            input_data: Dict containing 'content' key with HTML
            
        Returns:
            dict: Results containing extracted case components
        """
        # Validate input
        if not self.validate_input(input_data):
            return self.get_error_result('Invalid input', input_data)
            
        # Get HTML content and URL
        html_content = input_data.get('content', '')
        url = input_data.get('url', '')
        base_url = self._get_base_url(url) if url else None
        
        try:
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract case metadata
            pdf_url = self.extract_pdf_url(soup, url)
            case_number = self.extract_case_number(soup)
            year = self.extract_year(soup, case_number)
            
            # Extract major sections with links preserved
            facts = self.extract_facts_section(soup)
            if not facts:
                facts = self.extract_section(soup, "Facts:", ["Question:", "Questions:", "Reference:", "References:", "Discussion:", "Conclusion:", "Conclusions:"], base_url)
            
            # Extract questions using the specialized method
            questions_data = self.extract_questions_section(soup)
            question_html = None
            questions_list = []
            
            if questions_data and isinstance(questions_data, dict):
                question_html = questions_data.get('html')
                questions_list = questions_data.get('questions', [])
            else:
                # Fall back to generic extraction for backwards compatibility
                question_html = self.extract_section(soup, "Question:", ["Reference:", "References:", "Discussion:", "Conclusion:", "Conclusions:"], base_url)
                if not question_html:
                    question_html = self.extract_section(soup, "Questions:", ["Reference:", "References:", "Discussion:", "Conclusion:", "Conclusions:"], base_url)
                # Try to extract individual questions from the generic extraction result
                if question_html:
                    questions_list = self._extract_individual_questions(question_html)
                
            # Extract references section with specific targeting
            references_div = soup.find('div', class_='field--name-field-case-references')
            if references_div and references_div.find('div', class_='field__item'):
                references = self._clean_minimal_html(str(references_div.find('div', class_='field__item')))
            else:
                references = self.extract_section(soup, "Reference:", ["Discussion:", "Conclusion:", "Conclusions:"], base_url)
                if not references:
                    references = self.extract_section(soup, "References:", ["Discussion:", "Conclusion:", "Conclusions:"], base_url)
                
            # Extract discussion section with specific targeting
            discussion_div = soup.find('div', class_='field--name-field-case-discussion')
            if discussion_div and discussion_div.find('div', class_='field__item'):
                discussion = self._clean_minimal_html(str(discussion_div.find('div', class_='field__item')))
            else:
                discussion = self.extract_section(soup, "Discussion:", ["Conclusion:", "Conclusions:"], base_url)
            # Extract conclusion section with specific targeting
            conclusion_div = soup.find('div', class_='field--name-field-case-conclusion')
            if conclusion_div and conclusion_div.find('div', class_='field__item'):
                conclusion = self._clean_minimal_html(str(conclusion_div.find('div', class_='field__item')))
            else:
                conclusion = self.extract_section(soup, "Conclusion:", [], base_url)
                if not conclusion:
                    conclusion = self.extract_section(soup, "Conclusions:", [], base_url)
                
            # Clean sections while preserving links
            facts = self.clean_section_text(facts)
            question_html = self.clean_section_text(question_html)
            references = self.clean_section_text(references)
            discussion = self.clean_section_text(discussion)
            conclusion = self.clean_section_text(conclusion)
            
            # Extract title
            title = None
            # First try to find the specific title span
            title_span = soup.find('span', class_='single-node-title')
            if title_span:
                title = title_span.get_text().strip()
            
            if not title:
                # Try title tag, but remove "| National Society of Professional Engineers" part
                title_tag = soup.find('title')
                if title_tag:
                    title_text = title_tag.get_text().strip()
                    # Remove the organization suffix if present
                    if '|' in title_text:
                        title = title_text.split('|')[0].strip()
                    else:
                        title = title_text
            
            if not title:
                # Try to get from the first heading
                heading = soup.find(['h1', 'h2'])
                if heading:
                    title = heading.get_text().strip()
                    
            # Extract linked case references from the discussion section
            linked_cases = []
            if discussion and '<a ' in discussion:
                # Create temporary soup to extract links
                disc_soup = BeautifulSoup(discussion, 'html.parser')
                for link in disc_soup.find_all('a', href=True):
                    link_text = link.get_text().strip()
                    link_url = link['href']
                    
                    # If the link appears to be to another case, add it to the linked cases
                    if 'case' in link_url.lower() or 'ethics' in link_url.lower():
                        linked_cases.append({
                            'text': link_text,
                            'url': link_url
                        })
            
            # Return structured result
            return {
                'status': 'success',
                'url': url,
                'title': title,
                'case_number': case_number,
                'year': year,
                'pdf_url': pdf_url,
                'sections': {
                    'facts': facts,
                    'question': question_html,
                    'references': references,
                    'discussion': discussion,
                    'conclusion': conclusion
                },
                'questions_list': questions_list,
                'linked_cases': linked_cases,
                'raw_content': html_content  # Include the original content
            }
                
        except Exception as e:
            logger.error(f"Error extracting NSPE case content: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return self.get_error_result(f"Error extracting case content: {str(e)}")
