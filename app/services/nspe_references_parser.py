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
