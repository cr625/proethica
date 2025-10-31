"""
HTML Precedent Extractor

Extracts precedent case references from the initial case HTML during import.
This leverages the case links that are already marked up in the NSPE source HTML
with proper URLs, titles, and case numbers.

This is the PRIMARY method for precedent extraction - the LLM-based extractor
in precedent_citation_extractor.py acts as a FALLBACK for cases that:
- Lack proper HTML markup
- Come from non-NSPE sources
- Have unmarked case references in the text
"""

import logging
import re
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HTMLPrecedentCitation:
    """A precedent case extracted from HTML markup."""
    case_number: str  # e.g., "22-5"
    case_url: str  # Full NSPE URL
    case_title: Optional[str]  # Extracted from URL slug or link text
    full_citation: str  # e.g., "BER Case 22-5"
    year_decided: Optional[int]  # Extracted from case number
    mentioned_in_section: str  # "discussion" or "conclusion"

    def to_dict(self) -> Dict:
        """Convert to dictionary matching PrecedentCitation format."""
        return {
            'caseNumber': self.case_number,
            'caseUrl': self.case_url,
            'caseTitle': self.case_title or f"BER Case {self.case_number}",
            'fullCitation': self.full_citation,
            'yearDecided': self.year_decided,
            'citationContext': '',  # Will be filled by context extraction
            'relevanceReasoning': '',  # Will be filled by LLM if needed
            'relatedProvisions': [],  # Will be filled by analysis
            'mentionedInSection': self.mentioned_in_section,
            'confidence': 1.0,  # High confidence - directly from source HTML
            'extractionMethod': 'html_markup'  # Mark as HTML-extracted
        }


class HTMLPrecedentExtractor:
    """
    Extracts precedent case citations from HTML-marked case references.

    Processes the initial case HTML (discussion/conclusion sections) to find
    <a> tags linking to other NSPE BER cases with their full URLs intact.
    """

    def extract_from_html(
        self,
        discussion_html: Optional[str],
        conclusion_html: Optional[str]
    ) -> List[HTMLPrecedentCitation]:
        """
        Extract precedent cases from HTML sections.

        Args:
            discussion_html: HTML from discussion section
            conclusion_html: HTML from conclusion section

        Returns:
            List of HTMLPrecedentCitation objects
        """
        citations = []
        seen_cases = set()  # Track case numbers to avoid duplicates

        # Process discussion section
        if discussion_html:
            discussion_citations = self._extract_from_section(
                discussion_html,
                'discussion'
            )
            for citation in discussion_citations:
                if citation.case_number not in seen_cases:
                    citations.append(citation)
                    seen_cases.add(citation.case_number)

        # Process conclusion section
        if conclusion_html:
            conclusion_citations = self._extract_from_section(
                conclusion_html,
                'conclusion'
            )
            for citation in conclusion_citations:
                if citation.case_number not in seen_cases:
                    citations.append(citation)
                    seen_cases.add(citation.case_number)

        logger.info(f"[HTML Precedent Extractor] Found {len(citations)} precedent cases in HTML markup")
        return citations

    def _extract_from_section(
        self,
        html: str,
        section_name: str
    ) -> List[HTMLPrecedentCitation]:
        """
        Extract precedent citations from a single HTML section.

        Args:
            html: HTML content to parse
            section_name: Name of section (for metadata)

        Returns:
            List of HTMLPrecedentCitation objects
        """
        if not html:
            return []

        citations = []

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Find all links to NSPE case pages
            # Pattern: href contains "nspe.org" and "board-ethical-review-cases"
            case_links = soup.find_all(
                'a',
                href=lambda href: href and 'nspe.org' in href and
                                 ('board-ethical-review-cases' in href or
                                  'ethics-resources' in href)
            )

            for link in case_links:
                href = link.get('href', '')
                link_text = link.get_text().strip()

                # Extract case number from link text
                # Patterns: "BER Case 22-5", "BOR Case 79-5", "Case 92-7"
                case_number = self._extract_case_number(link_text)

                if case_number:
                    # Extract title from URL slug if not in link text
                    case_title = self._extract_title_from_url(href)

                    # Determine year from case number
                    year_decided = self._extract_year_from_case_number(case_number)

                    citation = HTMLPrecedentCitation(
                        case_number=case_number,
                        case_url=href,
                        case_title=case_title,
                        full_citation=link_text,
                        year_decided=year_decided,
                        mentioned_in_section=section_name
                    )

                    citations.append(citation)
                    logger.debug(f"[HTML Precedent Extractor] Found case: {link_text} -> {href}")

        except Exception as e:
            logger.error(f"[HTML Precedent Extractor] Error parsing HTML: {e}")
            import traceback
            traceback.print_exc()

        return citations

    def _extract_case_number(self, text: str) -> Optional[str]:
        """
        Extract case number from link text.

        Patterns:
        - "BER Case 22-5" -> "22-5"
        - "BOR Case 79-5" -> "79-5"
        - "Case 92-7" -> "92-7"
        - "NSPE Case 05-10" -> "05-10"

        Args:
            text: Link text to extract from

        Returns:
            Case number string or None
        """
        # Match patterns like "Case 22-5" or "BER Case 22-5"
        match = re.search(r'(?:BER|BOR|NSPE)?\s*Case\s+(\d{1,2}-\d{1,2})', text, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _extract_title_from_url(self, url: str) -> Optional[str]:
        """
        Extract case title from NSPE URL slug.

        Example:
        https://www.nspe.org/career-growth/ethics/board-ethical-review-cases/sustainability-lawn-irrigation-design
        -> "Sustainability Lawn Irrigation Design"

        Args:
            url: NSPE case URL

        Returns:
            Title string or None
        """
        # Get the last part of the URL path
        url_parts = url.rstrip('/').split('/')
        if len(url_parts) > 0:
            slug = url_parts[-1]
            # Convert kebab-case to Title Case
            title = ' '.join(word.capitalize() for word in slug.split('-'))
            return title
        return None

    def _extract_year_from_case_number(self, case_number: str) -> Optional[int]:
        """
        Extract year from case number.

        Case numbers use YY-N format where YY is the last 2 digits of the year.
        Examples:
        - "22-5" -> 2022
        - "99-3" -> 1999
        - "05-10" -> 2005
        - "76-4" -> 1976

        Args:
            case_number: Case number (e.g., "22-5")

        Returns:
            Four-digit year or None
        """
        match = re.match(r'(\d{1,2})-\d+', case_number)
        if match:
            year_prefix = match.group(1).zfill(2)  # Pad to 2 digits
            year_int = int(year_prefix)

            # Heuristic: 50-99 = 1900s, 00-49 = 2000s
            if year_int >= 50:
                return 1900 + year_int
            else:
                return 2000 + year_int
        return None

    def extract_citation_context(
        self,
        case_number: str,
        html: str,
        context_window: int = 300
    ) -> str:
        """
        Extract surrounding text context for a case citation.

        Finds where the case is mentioned and extracts surrounding text
        to understand HOW and WHY it's being cited.

        Args:
            case_number: Case number to find (e.g., "22-5")
            html: HTML content to search
            context_window: Characters before/after to extract

        Returns:
            Context string (plain text)
        """
        if not html:
            return ""

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Find the link containing this case number
            case_pattern = f"Case {case_number}"
            link = soup.find('a', string=re.compile(case_pattern, re.IGNORECASE))

            if link:
                # Get the parent paragraph or containing element
                parent = link.find_parent(['p', 'li', 'div'])
                if parent:
                    # Extract text from parent element
                    context = parent.get_text().strip()
                    return context

        except Exception as e:
            logger.error(f"[HTML Precedent Extractor] Error extracting context: {e}")

        return ""
