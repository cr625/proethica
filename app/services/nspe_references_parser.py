"""
NSPE Code of Ethics References Parser

Parses HTML from the NSPE references section to extract:
- Code provision numbers (e.g., "I.1", "II.3.a")
- Provision text (the ethical principle quoted)
- Subject reference links (URLs to related precedent collections)
"""

import logging
import re
from typing import List, Dict
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class NSPEReferencesParser:
    """Parser for NSPE Code of Ethics References section HTML."""

    def __init__(self):
        self.parsed_provisions = []

    def parse_references_html(self, html_content: str) -> List[Dict]:
        """
        Parse NSPE references HTML to extract code provisions and subject references.

        Tries structured HTML parsing first (div.field__item + H2 tags). If that
        returns 0 results, falls back to plain-text parsing for cases where
        references are stored as unstructured text (e.g., "II.1. Engineers shall...").

        Args:
            html_content: HTML string from the references section

        Returns:
            List of dictionaries with structure:
            {
                'code_provision': 'I.1',
                'provision_text': 'Hold paramount the safety...',
                'subject_references': [
                    {
                        'category': 'Duty to the Public',
                        'url': 'https://www.nspe.org/...'
                    }
                ]
            }
        """
        if not html_content:
            logger.warning("No HTML content provided")
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        provisions = []

        # Find all field__item divs (each represents one code provision)
        provision_divs = soup.find_all('div', class_='field__item', recursive=True)

        logger.info(f"Found {len(provision_divs)} potential provision divs")

        for div in provision_divs:
            provision_data = self._parse_provision_div(div)
            if provision_data:
                provisions.append(provision_data)
                logger.info(f"Parsed provision: {provision_data['code_provision']}")

        # Fallback: if structured parsing found nothing, try plain-text parsing
        if not provisions:
            plain_text = soup.get_text(separator=' ', strip=True)
            if plain_text:
                logger.info("Structured parsing returned 0 provisions, trying plain-text fallback")
                provisions = self._parse_references_plaintext(plain_text)

        self.parsed_provisions = provisions
        logger.info(f"Total provisions parsed: {len(provisions)}")
        return provisions

    def _parse_provision_div(self, div) -> Dict:
        """
        Parse a single provision div to extract code, text, and references.

        Structure expected:
        <div class="field__item">
            <div>
                <h2>
                    <div class="field__item">I.1.</div>
                </h2>
                <div>
                    <div class="field__item"><p>Hold paramount...</p></div>
                    <div>
                        <div>Subject Reference</div>
                        <div class="field__items">
                            <div class="field__item">
                                <a href="...">Duty to the Public</a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """
        # Find the h2 tag containing the code provision number
        h2 = div.find('h2')
        if not h2:
            return None

        # Extract code provision number
        code_field = h2.find('div', class_='field__item')
        if not code_field:
            return None

        code_provision = code_field.get_text(strip=True)

        # Validate it looks like a code provision (e.g., "I.1", "II.3.a")
        if not self._is_valid_code_provision(code_provision):
            return None

        # Find the provision text (in a paragraph after the h2)
        provision_text = None
        # Use lambda to match any div with 'text-formatted' in its class list
        text_div = div.find('div', class_=lambda x: x and 'text-formatted' in x.split() if isinstance(x, str) else (x and 'text-formatted' in x))
        if text_div:
            p_tag = text_div.find('p')
            if p_tag:
                provision_text = p_tag.get_text(strip=True)

        if not provision_text:
            logger.warning(f"No provision text found for {code_provision}")
            return None

        # Extract subject references
        subject_references = []

        # Find all anchor tags within the div
        links = div.find_all('a', href=True)
        for link in links:
            href = link['href']
            # Filter for NSPE subject reference links
            if 'nspe.org' in href and 'subject-reference-guide-code-ethics' in href:
                category = link.get_text(strip=True)
                subject_references.append({
                    'category': category,
                    'url': href,
                    'description': f'NSPE precedent cases on {category}'
                })

        logger.info(f"Provision {code_provision}: {len(subject_references)} subject references")

        return {
            'code_provision': code_provision,
            'provision_text': provision_text,
            'subject_references': subject_references
        }

    def _parse_references_plaintext(self, text: str) -> List[Dict]:
        """
        Parse plain-text references to extract code provisions.

        Handles cases where the references section contains unstructured text
        like "II.1. Engineers shall hold paramount..." rather than structured
        HTML with div.field__item and H2 tags.

        Splits text on provision code boundaries, captures each code and its
        following provision text.

        Args:
            text: Plain text from the references section (HTML tags stripped)

        Returns:
            List of provision dicts with same format as parse_references_html()
        """
        provisions = []
        seen_codes = set()

        # Pattern: provision code at a boundary, followed by provision text
        # Matches: "II.1." or "II.1.f." at start-of-string or after whitespace
        provision_pattern = re.compile(
            r'(?:^|\s)([IVX]+\.\d+\.(?:[a-z]\.)?)\s+'
            r'(Engineers\s.+?)(?=\s+[IVX]+\.\d+\.|$)',
            re.DOTALL
        )

        for match in provision_pattern.finditer(text):
            raw_code = match.group(1).strip().rstrip('.')
            provision_text = match.group(2).strip()

            # Normalize: ensure no trailing dot on code for consistency with
            # _is_valid_code_provision, but store with trailing dot for DB match
            if not self._is_valid_code_provision(raw_code):
                continue

            if raw_code in seen_codes:
                continue
            seen_codes.add(raw_code)

            provisions.append({
                'code_provision': raw_code,
                'provision_text': provision_text,
                'subject_references': []
            })
            logger.info(f"Plain-text parsed provision: {raw_code}")

        logger.info(f"Plain-text fallback found {len(provisions)} provisions")
        return provisions

    def _is_valid_code_provision(self, text: str) -> bool:
        """
        Check if text looks like a valid NSPE code provision number.

        Valid formats:
        - I.1
        - I.4
        - II.1.a
        - II.3.a
        - III.1.b
        """
        # Pattern: Roman numeral, period, number, optional letter
        pattern = r'^[IVX]+\.\d+\.?[a-z]?\.?$'
        return bool(re.match(pattern, text))

    def get_parsed_provisions(self) -> List[Dict]:
        """Return the last parsed provisions."""
        return self.parsed_provisions

    def format_for_llm(self, provisions: List[Dict]) -> str:
        """
        Format parsed provisions as readable text for LLM processing.

        Args:
            provisions: List of provision dictionaries

        Returns:
            Formatted string describing all provisions
        """
        if not provisions:
            return "No code provisions found."

        formatted = "NSPE Code of Ethics Provisions Referenced by Board:\n\n"

        for i, prov in enumerate(provisions, 1):
            formatted += f"{i}. Code Provision {prov['code_provision']}\n"
            formatted += f"   Text: {prov['provision_text']}\n"

            if prov['subject_references']:
                formatted += f"   Subject References ({len(prov['subject_references'])}):\n"
                for ref in prov['subject_references']:
                    formatted += f"   - {ref['category']}\n"
                    formatted += f"     URL: {ref['url']}\n"

            formatted += "\n"

        return formatted
