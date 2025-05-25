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

    def extract_references_section(self, soup, base_url=None):
        """
        Extract NSPE Code of Ethics References section with special handling for code references.
        
        Args:
            soup: BeautifulSoup object of the full page content
            base_url: Base URL for converting relative links to absolute
            
        Returns:
            str: Extracted and cleaned references section HTML
        """
        # First try the specific div structure for modern NSPE cases
        references_div = soup.find('div', class_='field--name-field-code-of-ethics')
        if not references_div:
            references_div = soup.find('div', class_='field-name-field-case-references')
        if not references_div:
            # Try to find by field label
            field_labels = soup.find_all('div', class_='field__label')
            for label in field_labels:
                if 'nspe code of ethics references' in label.get_text().lower():
                    references_div = label.parent
                    break
        
        if references_div:
            # Find the field__items or field__item which contains the actual content
            field_items = references_div.find('div', class_='field__items')
            if field_items:
                # Process the content for links and formatting
                return self._process_references_html(str(field_items), base_url)
            
            field_item = references_div.find('div', class_='field__item')
            if field_item:
                return self._process_references_html(str(field_item), base_url)
        
        # Fall back to general section extraction method if specialized methods fail
        return None
    
    def _process_references_html(self, html, base_url=None):
        """
        Process references section HTML to properly handle code references and links.
        
        Args:
            html: Raw HTML content of references section
            base_url: Base URL for converting relative links to absolute
            
        Returns:
            str: Processed HTML with proper link handling
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
        
        # Keep essential attributes for code references and links
        for tag in soup.find_all(True):
            if tag.name == 'a':
                # For anchor tags, preserve href and target attributes
                href = tag.get('href', '')
                target = tag.get('target', '_blank')
                title = tag.get('title', '')
                tag.attrs = {}  # Clear all attributes
                tag['href'] = href
                tag['target'] = target
                if title:
                    tag['title'] = title
            elif tag.name in ['h2']:
                # Preserve h2 tags which often contain code section numbers
                pass
            else:
                # For other tags, clean up attributes but preserve structure
                classes = tag.get('class', [])
                if 'field__item' in classes or 'field__items' in classes:
                    tag.attrs = {'class': classes}
                else:
                    tag.attrs = {}
        
        # Get the cleaned HTML
        cleaned_html = str(soup)
        
        # Fix excessive whitespace but preserve formatting
        cleaned_html = re.sub(r'\n\s*\n', '\n\n', cleaned_html)
        
        return cleaned_html
        
    def extract_discussion_section(self, soup, base_url=None):
        """
        Extract discussion section with special handling for links and references.
        The discussion section often contains links to other cases and complex formatting.
        
        Args:
            soup: BeautifulSoup object of the full page content
            base_url: Base URL for converting relative links to absolute
            
        Returns:
            str: Extracted and cleaned discussion section HTML with links preserved
        """
        # First try the specific div structure for modern NSPE cases
        discussion_div = soup.find('div', class_='field--name-field-case-discussion')
        if discussion_div:
            # Find the field__item which contains the actual content
            field_item = discussion_div.find('div', class_='field__item')
            if field_item:
                # Process the content for links and formatting
                return self._process_discussion_html(str(field_item), base_url)
                
        # Next, try to find the discussion section by its label
        discussion_divs = soup.find_all('div', class_='field__label')
        for div in discussion_divs:
            if div.get_text().strip().lower() == 'discussion':
                # Found the discussion label, get the content from the nearest field__item
                parent = div.parent
                if parent:
                    field_item = parent.find('div', class_='field__item')
                    if field_item:
                        return self._process_discussion_html(str(field_item), base_url)
                        
        # Fall back to general section extraction method if specialized methods fail
        return None
    
    def extract_conclusion_section(self, soup, base_url=None):
        """
        Extract conclusion section with special handling.
        Returns both the raw HTML and a list of individual conclusion items if available.
        
        Args:
            soup: BeautifulSoup object of the full page content
            base_url: Base URL for converting relative links to absolute
            
        Returns:
            dict: Dictionary containing the HTML content and list of individual conclusion items
                 or str: Just the HTML content for backward compatibility
        """
        conclusion_html = None
        
        # First try the specific div structure for modern NSPE cases
        conclusion_div = soup.find('div', class_='field--name-field-case-conclusion')
        if conclusion_div:
            # Find the field__item which contains the actual content
            field_item = conclusion_div.find('div', class_='field__item')
            if field_item:
                # Extract and clean the conclusion content
                conclusion_html = self._clean_minimal_html(str(field_item))
        
        # Next, try to find by field label
        if not conclusion_html:
            field_labels = soup.find_all('div', class_='field__label')
            for label in field_labels:
                if label.get_text().strip().lower() == 'conclusion' or label.get_text().strip().lower() == 'conclusions':
                    # Found the conclusion label, get the content from the nearest field__item
                    parent = label.parent
                    if parent:
                        field_item = parent.find('div', class_='field__item')
                        if field_item:
                            conclusion_html = self._clean_minimal_html(str(field_item))
        
        # Fall back to general section extraction method if specialized methods fail
        if not conclusion_html:
            conclusion_html = self.extract_section(soup, "Conclusion:", [], base_url)
            if not conclusion_html:
                conclusion_html = self.extract_section(soup, "Conclusions:", [], base_url)
                
        # If we have conclusion HTML, extract individual items
        if conclusion_html:
            # Parse the cleaned HTML to extract individual conclusions from ordered lists
            conclusion_items = self._extract_individual_conclusions(conclusion_html)
            
            # If we found individual items, return both HTML and items
            if conclusion_items:
                return {
                    'html': conclusion_html,
                    'conclusions': conclusion_items
                }
        
        # Return just the HTML for backward compatibility
        return conclusion_html
    
    def extract_dissenting_opinion_section(self, soup, base_url=None):
        """
        Extract dissenting opinion section using specific HTML structure.
        Some NSPE cases include dissenting opinions from board members.
        
        Args:
            soup: BeautifulSoup object of the full page content
            base_url: Base URL for converting relative links to absolute
            
        Returns:
            str: Extracted dissenting opinion HTML content or None if not found
        """
        # First try the specific div structure for modern NSPE cases
        dissenting_div = soup.find('div', class_='field--name-field-dissenting-opinion')
        if dissenting_div:
            # Find the field__item which contains the actual content
            field_item = dissenting_div.find('div', class_='field__item')
            if field_item:
                # Process the content for links and formatting
                return self._process_discussion_html(str(field_item), base_url)
        
        # Next, try to find by field label
        field_labels = soup.find_all('div', class_='field__label')
        for label in field_labels:
            label_text = label.get_text().strip().lower()
            if 'dissenting opinion' in label_text:
                # Found the dissenting opinion label, get the content from the nearest field__item
                parent = label.parent
                if parent:
                    field_item = parent.find('div', class_='field__item')
                    if field_item:
                        return self._process_discussion_html(str(field_item), base_url)
        
        # Fall back to general section extraction method if specialized methods fail
        dissenting_html = self.extract_section(soup, "Dissenting Opinion:", [], base_url)
        if not dissenting_html:
            dissenting_html = self.extract_section(soup, "DISSENTING OPINION:", [], base_url)
            
        return dissenting_html
    
    def _process_discussion_html(self, html, base_url=None):
        """
        Process discussion section HTML to properly handle links and formatting.
        
        Args:
            html: Raw HTML content of discussion section
            base_url: Base URL for converting relative links to absolute
            
        Returns:
            str: Processed HTML with proper link handling
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
                    
                # Mark links to other cases with a special class
                if 'case' in href.lower() or 'ethics' in href.lower():
                    link['class'] = link.get('class', []) + ['case-link']
        
        # Process BER case references in text that aren't already links
        self._mark_case_references(soup)
        
        # Remove all divs but keep their content
        for div in soup.find_all('div'):
            div.unwrap()
            
        # Keep essential attributes for anchors, but clean other tags
        for tag in soup.find_all(True):
            if tag.name == 'a':
                # For anchor tags, preserve href and target attributes
                href = tag.get('href', '')
                target = tag.get('target', '_blank')
                title = tag.get('title', '')
                tag.attrs = {}  # Clear all attributes
                tag['href'] = href
                tag['target'] = target
                if title:
                    tag['title'] = title
            elif tag.name not in ['span']:
                # For other tags, remove all attributes except for spans (might have case-reference class)
                tag.attrs = {}
        
        # Get the cleaned HTML
        cleaned_html = str(soup)
        
        # Fix excessive whitespace but preserve paragraph structure
        cleaned_html = re.sub(r'\n\s*\n', '\n\n', cleaned_html)
        
        return cleaned_html
        
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
        
    def _extract_individual_conclusions(self, html):
        """
        Extract individual conclusion items from HTML content.
        Handles ordered lists, unordered lists, and text with numbered items.
        
        Args:
            html: HTML content containing conclusion
            
        Returns:
            list: List of individual conclusion items as strings
        """
        if not html:
            return []
            
        # Parse the HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        conclusions = []
        
        # Look for ordered lists first (most common format for multiple conclusion items)
        ordered_list = soup.find('ol')
        if ordered_list:
            # Extract each list item as a separate conclusion item
            for item in ordered_list.find_all('li'):
                conclusions.append(item.get_text().strip())
            return conclusions
        
        # If no ordered list is found, check for unordered lists
        unordered_list = soup.find('ul')
        if unordered_list:
            for item in unordered_list.find_all('li'):
                conclusions.append(item.get_text().strip())
            return conclusions
        
        # If no list is found, try to find numbered items in the text
        # This handles cases where numbers are used but not in HTML list format
        text_content = soup.get_text().strip()
        if text_content:
            # Look for patterns like "1.", "2.", "(1)", "(2)" at the beginning of lines or sentences
            numbered_items = re.findall(r'(?:^|\n|\.\s+)(\(\d+\)|\d+\.)\s+([^\(\d\n\.]+?)(?=\n\s*\(\d+\)|\n\s*\d+\.|\Z)', text_content)
            if numbered_items:
                for _, item_text in numbered_items:
                    conclusions.append(item_text.strip())
                return conclusions
            
            # If no numbered items found, use the entire content as a single conclusion
            conclusions.append(text_content)
            
        return conclusions
        
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
    
    def extract_text_only(self, html):
        """
        Extract plain text from HTML for embeddings and similarity matching.
        Preserves semantic structure without HTML formatting.
        
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
            
        # Extract text with proper spacing between elements
        text_parts = []
        
        # Process block-level elements to maintain structure
        for elem in soup.find_all(['p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'ol', 'ul']):
            # Skip if this element is inside another we'll process
            if any(parent.name in ['ol', 'ul'] for parent in elem.parents):
                if elem.name not in ['li']:
                    continue
                    
            text = elem.get_text(separator=' ', strip=True)
            if text:
                # Add list markers for better structure preservation
                if elem.name == 'li':
                    # Check if it's in an ordered list
                    parent = elem.parent
                    if parent and parent.name == 'ol':
                        # Find the item's position
                        position = len([sib for sib in elem.previous_siblings if sib.name == 'li']) + 1
                        text = f"{position}. {text}"
                    else:
                        text = f"• {text}"
                text_parts.append(text)
                
        # Join with newlines to preserve structure
        text = '\n'.join(text_parts)
        
        # Normalize whitespace within lines
        text = re.sub(r'[ \t]+', ' ', text)
        # Remove excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Clean up special HTML entities
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        text = text.replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&quot;', '"').replace('&#39;', "'")
        
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
            
            # Extract references section with specialized handling
            references = self.extract_references_section(soup, base_url)
            if not references:
                # Fall back to generic extraction
                references = self.extract_section(soup, "NSPE Code of Ethics References:", ["Discussion:", "Conclusion:", "Conclusions:"], base_url)
                if not references:
                    references = self.extract_section(soup, "Reference:", ["Discussion:", "Conclusion:", "Conclusions:"], base_url)
                    if not references:
                        references = self.extract_section(soup, "References:", ["Discussion:", "Conclusion:", "Conclusions:"], base_url)
                
            # Extract discussion section with specialized handling
            discussion = self.extract_discussion_section(soup, base_url)
            if not discussion:
                # Fall back to the general extraction method
                discussion = self.extract_section(soup, "Discussion:", ["Conclusion:", "Conclusions:"], base_url)
                
            # Extract conclusion section with specialized handling that may return a dict or string
            conclusion_data = self.extract_conclusion_section(soup, base_url)
            conclusion_html = None
            conclusion_items = []
            
            # Handle the result which may be a dict or string depending on if individual items were found
            if isinstance(conclusion_data, dict):
                conclusion_html = conclusion_data.get('html')
                conclusion_items = conclusion_data.get('conclusions', [])
            else:
                conclusion_html = conclusion_data
                
            # Extract dissenting opinion section (if present)
            dissenting_opinion = self.extract_dissenting_opinion_section(soup, base_url)
                
            # Store raw content for text extraction before cleaning
            raw_facts = facts
            raw_question_html = question_html
            raw_references = references
            raw_discussion = discussion
            raw_conclusion_html = conclusion_html
            raw_dissenting_opinion = dissenting_opinion
            
            # Clean sections while preserving links
            facts = self.clean_section_text(facts)
            question_html = self.clean_section_text(question_html)
            references = self.clean_section_text(references)
            discussion = self.clean_section_text(discussion)
            conclusion_html = self.clean_section_text(conclusion_html)
            dissenting_opinion = self.clean_section_text(dissenting_opinion)
            
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
            
            # Prepare result with all extracted components
            # Store both HTML (for display) and text (for embeddings) versions
            sections_dual = {
                'facts': {
                    'html': facts,
                    'text': self.extract_text_only(raw_facts) if raw_facts else ''
                },
                'question': {
                    'html': question_html,
                    'text': self.extract_text_only(raw_question_html) if raw_question_html else ''
                },
                'references': {
                    'html': references,
                    'text': self.extract_text_only(raw_references) if raw_references else ''
                },
                'discussion': {
                    'html': discussion,
                    'text': self.extract_text_only(raw_discussion) if raw_discussion else ''
                },
                'conclusion': {
                    'html': conclusion_html,
                    'text': self.extract_text_only(raw_conclusion_html) if raw_conclusion_html else ''
                },
                'dissenting_opinion': {
                    'html': dissenting_opinion,
                    'text': self.extract_text_only(raw_dissenting_opinion) if raw_dissenting_opinion else ''
                }
            }
            
            result = {
                'status': 'success',
                'title': title,
                'case_number': case_number,
                'year': year,
                'pdf_url': pdf_url,
                'questions_list': questions_list,  # List of individual questions
                'conclusion_items': conclusion_items,  # List of individual conclusion items
                'url': url,
                'sections': {  # Keep for backward compatibility
                    'facts': facts,
                    'question': question_html,
                    'references': references,
                    'discussion': discussion,
                    'conclusion': conclusion_html,
                    'dissenting_opinion': dissenting_opinion
                },
                'sections_dual': sections_dual,  # New dual format
                'sections_text': {  # Convenience access to text versions
                    'facts': sections_dual['facts']['text'],
                    'question': sections_dual['question']['text'],
                    'references': sections_dual['references']['text'],
                    'discussion': sections_dual['discussion']['text'],
                    'conclusion': sections_dual['conclusion']['text'],
                    'dissenting_opinion': sections_dual['dissenting_opinion']['text']
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing HTML content: {str(e)}")
            return self.get_error_result(f"Error extracting case content: {str(e)}")
