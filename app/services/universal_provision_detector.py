"""
Universal Provision Detector

Finds ALL NSPE code provision mentions in case text, regardless of which
provisions we're looking for. This is the first stage of the mention-first
approach for accurate code provision extraction.
"""

import re
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProvisionMention:
    """Represents a mention of a code provision found in case text."""
    mentioned_provision: str  # Normalized code (e.g., "II.4.e")
    section: str  # Section name ('facts', 'discussion', etc.)
    excerpt: str  # Text excerpt with context
    citation_text: str  # Actual citation found (e.g., "Section II.4.e")
    position: int  # Character position in section
    match_type: str  # How it was found ('exact', 'prefixed', 'written')


class UniversalProvisionDetector:
    """
    Detects all NSPE code provision mentions in text.

    Unlike the pattern matcher which searches for specific provisions,
    this finds ALL provisions mentioned anywhere in the case.
    """

    def __init__(self):
        self.all_mentions = []

    def detect_all_provisions(
        self,
        case_sections: Dict[str, str]
    ) -> List[ProvisionMention]:
        """
        Find all code provision mentions across all case sections.

        Args:
            case_sections: Dict with section names as keys, text as values

        Returns:
            List of ProvisionMention objects
        """
        all_mentions = []

        for section_name, section_text in case_sections.items():
            if not section_text:
                continue

            section_mentions = self._detect_in_section(section_text, section_name)
            all_mentions.extend(section_mentions)

        logger.info(f"Detected {len(all_mentions)} total provision mentions across all sections")

        # Deduplicate very close mentions (within 50 chars)
        deduplicated = self._deduplicate_mentions(all_mentions)

        logger.info(f"After deduplication: {len(deduplicated)} unique mentions")

        self.all_mentions = deduplicated
        return deduplicated

    def _detect_in_section(
        self,
        section_text: str,
        section_name: str
    ) -> List[ProvisionMention]:
        """
        Detect all provision mentions in a single section.

        Args:
            section_text: Text to search
            section_name: Name of section

        Returns:
            List of ProvisionMention objects
        """
        mentions = []

        # Pattern 1: Exact provision codes (I.4, II.4.e, III.1.a, etc.)
        # Uses word boundaries to avoid matching "I.4" in "II.4"
        exact_pattern = r'\b([IVX]+)\.(\d+)(?:\.([a-z]))?\b'
        for match in re.finditer(exact_pattern, section_text, re.IGNORECASE):
            provision_code = self._build_provision_code(
                match.group(1),  # Roman numeral
                match.group(2),  # Number
                match.group(3)   # Letter (optional)
            )

            excerpt = self._extract_context(section_text, match.start(), match.end())

            mentions.append(ProvisionMention(
                mentioned_provision=provision_code,
                section=section_name,
                excerpt=excerpt,
                citation_text=match.group(0),
                position=match.start(),
                match_type='exact'
            ))

        # Pattern 2: With prefixes (Section II.4.e, Provision I.4, Code II.4.e)
        prefix_pattern = r'\b(?:Section|Provision|Code|Paragraph)\s+([IVX]+)\.(\d+)(?:\.([a-z]))?\b'
        for match in re.finditer(prefix_pattern, section_text, re.IGNORECASE):
            provision_code = self._build_provision_code(
                match.group(1),
                match.group(2),
                match.group(3)
            )

            excerpt = self._extract_context(section_text, match.start(), match.end())

            mentions.append(ProvisionMention(
                mentioned_provision=provision_code,
                section=section_name,
                excerpt=excerpt,
                citation_text=match.group(0),
                position=match.start(),
                match_type='prefixed'
            ))

        # Pattern 3: Written out (Section II, paragraph 4, subparagraph e)
        written_pattern = r'\bSection\s+([IVX]+)\s*,?\s*paragraph\s+(\d+)(?:\s*,?\s*subparagraph\s+([a-z]))?\b'
        for match in re.finditer(written_pattern, section_text, re.IGNORECASE):
            provision_code = self._build_provision_code(
                match.group(1),
                match.group(2),
                match.group(3)
            )

            excerpt = self._extract_context(section_text, match.start(), match.end())

            mentions.append(ProvisionMention(
                mentioned_provision=provision_code,
                section=section_name,
                excerpt=excerpt,
                citation_text=match.group(0),
                position=match.start(),
                match_type='written'
            ))

        # Pattern 4: Code of Ethics Section format
        code_ethics_pattern = r'\bCode\s+of\s+Ethics\s+Section\s+([IVX]+)\.(\d+)(?:\.([a-z]))?\b'
        for match in re.finditer(code_ethics_pattern, section_text, re.IGNORECASE):
            provision_code = self._build_provision_code(
                match.group(1),
                match.group(2),
                match.group(3)
            )

            excerpt = self._extract_context(section_text, match.start(), match.end())

            mentions.append(ProvisionMention(
                mentioned_provision=provision_code,
                section=section_name,
                excerpt=excerpt,
                citation_text=match.group(0),
                position=match.start(),
                match_type='prefixed'
            ))

        # Pattern 5: "Code Section" format (common in NSPE cases)
        code_section_pattern = r'\bCode\s+Section\s+([IVX]+)\.(\d+)(?:\.([a-z]))?\b'
        for match in re.finditer(code_section_pattern, section_text, re.IGNORECASE):
            provision_code = self._build_provision_code(
                match.group(1),
                match.group(2),
                match.group(3)
            )

            excerpt = self._extract_context(section_text, match.start(), match.end())

            mentions.append(ProvisionMention(
                mentioned_provision=provision_code,
                section=section_name,
                excerpt=excerpt,
                citation_text=match.group(0),
                position=match.start(),
                match_type='prefixed'
            ))

        logger.info(f"Found {len(mentions)} mentions in {section_name}")

        return mentions

    def _build_provision_code(
        self,
        roman: str,
        number: str,
        letter: Optional[str] = None
    ) -> str:
        """
        Build normalized provision code from components.

        Args:
            roman: Roman numeral (I, II, III, IV)
            number: Number (1, 2, 3, 4)
            letter: Optional letter (a, b, c, etc.)

        Returns:
            Normalized code like "II.4.e" or "I.4"
        """
        # Normalize roman numeral to uppercase
        roman = roman.upper()

        # Build code
        code = f"{roman}.{number}"
        if letter:
            code += f".{letter.lower()}"

        return code

    def _extract_context(
        self,
        text: str,
        match_start: int,
        match_end: int,
        window_size: int = 200
    ) -> str:
        """
        Extract text excerpt with context around a match.

        Args:
            text: Full text
            match_start: Start position of match
            match_end: End position of match
            window_size: Characters to include before/after

        Returns:
            Excerpt string with context
        """
        # Get text before match
        before_start = max(0, match_start - window_size)
        before_text = text[before_start:match_start]

        # Try to start at sentence boundary
        last_period = before_text.rfind('. ')
        if last_period != -1 and (len(before_text) - last_period) < window_size:
            before_text = before_text[last_period + 2:]

        # Get matched text
        matched_text = text[match_start:match_end]

        # Get text after match
        after_end = min(len(text), match_end + window_size)
        after_text = text[match_end:after_end]

        # Try to end at sentence boundary
        first_period = after_text.find('. ')
        if first_period != -1 and first_period < window_size:
            after_text = after_text[:first_period + 1]

        excerpt = (before_text + matched_text + after_text).strip()

        return excerpt

    def _deduplicate_mentions(
        self,
        mentions: List[ProvisionMention]
    ) -> List[ProvisionMention]:
        """
        Remove duplicate mentions that are very close together.

        Args:
            mentions: List of all mentions

        Returns:
            Deduplicated list
        """
        if not mentions:
            return []

        # Group by section and provision
        by_section_provision = {}
        for mention in mentions:
            key = (mention.section, mention.mentioned_provision)
            if key not in by_section_provision:
                by_section_provision[key] = []
            by_section_provision[key].append(mention)

        deduplicated = []

        # For each group, remove overlapping mentions
        for (section, provision), group in by_section_provision.items():
            # Sort by position
            group.sort(key=lambda m: m.position)

            kept = []
            for mention in group:
                # Check if this overlaps with any already kept
                overlaps = False
                for kept_mention in kept:
                    # If within 50 characters, consider it a duplicate
                    if abs(mention.position - kept_mention.position) < 50:
                        # Keep the one with the more specific match type
                        if self._match_type_priority(mention.match_type) > \
                           self._match_type_priority(kept_mention.match_type):
                            kept.remove(kept_mention)
                            kept.append(mention)
                        overlaps = True
                        break

                if not overlaps:
                    kept.append(mention)

            deduplicated.extend(kept)

        return deduplicated

    def _match_type_priority(self, match_type: str) -> int:
        """
        Return priority score for match types.
        Higher = more specific/reliable.
        """
        priorities = {
            'written': 3,  # Most specific
            'prefixed': 2,
            'exact': 1
        }
        return priorities.get(match_type, 0)

    def get_all_mentioned_provisions(self) -> List[str]:
        """
        Get unique list of all provisions mentioned in case.

        Returns:
            List of provision codes (e.g., ["I.4", "II.4.e"])
        """
        provisions = set()
        for mention in self.all_mentions:
            provisions.add(mention.mentioned_provision)

        return sorted(list(provisions))

    def get_mentions_for_provision(
        self,
        provision_code: str
    ) -> List[ProvisionMention]:
        """
        Get all mentions of a specific provision.

        Args:
            provision_code: Code like "II.4.e"

        Returns:
            List of ProvisionMention objects for that provision
        """
        # Normalize code for comparison
        normalized = provision_code.strip().rstrip('.').upper()

        mentions = []
        for mention in self.all_mentions:
            mention_normalized = mention.mentioned_provision.strip().rstrip('.').upper()
            if mention_normalized == normalized:
                mentions.append(mention)

        return mentions
