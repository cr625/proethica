"""
Code Provision Pattern Matcher

Multi-pattern citation detection for NSPE Code provisions.
Handles various citation formats and extracts contextual excerpts.
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CandidateMatch:
    """Represents a potential code provision mention in case text."""
    section: str  # 'facts', 'discussion', 'questions', 'conclusions'
    excerpt: str  # Full text with context
    matched_text: str  # The actual matched citation text
    match_type: str  # 'exact', 'prefix', 'written', 'variant', 'flexible'
    confidence: float  # Initial pattern-based confidence (0.0-1.0)
    position: int  # Character position in section
    before_context: str  # Text before match
    after_context: str  # Text after match


class CodeProvisionPatternMatcher:
    """Finds all possible mentions of code provisions using multiple patterns."""

    # Confidence levels for different match types
    CONFIDENCE_EXACT = 0.95
    CONFIDENCE_PREFIX = 0.85
    CONFIDENCE_HYPHENATED = 0.80
    CONFIDENCE_FLEXIBLE = 0.75
    CONFIDENCE_WRITTEN = 0.70

    def __init__(self):
        self.match_cache = {}

    def find_all_mentions(
        self,
        case_sections: Dict[str, str],
        code_provision: str,
        provision_text: str
    ) -> List[CandidateMatch]:
        """
        Find all possible mentions of a code provision across all case sections.

        Args:
            case_sections: Dict with section names as keys and text as values
            code_provision: The code provision number (e.g., "II.1.e")
            provision_text: The text of the provision (for context)

        Returns:
            List of CandidateMatch objects
        """
        all_candidates = []

        # Generate all search patterns for this provision
        patterns = self._generate_citation_patterns(code_provision)

        logger.info(f"Searching for provision {code_provision} with {len(patterns)} patterns")

        # Search each section
        for section_name, section_text in case_sections.items():
            if not section_text:
                continue

            section_candidates = self._search_section(
                section_text=section_text,
                section_name=section_name,
                patterns=patterns,
                code_provision=code_provision
            )

            all_candidates.extend(section_candidates)

        logger.info(f"Found {len(all_candidates)} candidate mentions for {code_provision}")

        # Deduplicate overlapping matches (keep highest confidence)
        deduplicated = self._deduplicate_matches(all_candidates)

        logger.info(f"After deduplication: {len(deduplicated)} unique mentions")

        return deduplicated

    def _generate_citation_patterns(self, code_provision: str) -> List[Tuple[str, str, float]]:
        """
        Generate all regex patterns for a code provision.

        Args:
            code_provision: E.g., "II.1.e" or "I.4"

        Returns:
            List of (pattern, match_type, confidence) tuples
        """
        patterns = []

        # Parse the provision into components
        # Format: Roman.Number.Letter (letter optional)
        parts = code_provision.split('.')
        roman = parts[0]  # E.g., "II"
        number = parts[1] if len(parts) > 1 else ""  # E.g., "1"
        letter = parts[2] if len(parts) > 2 else ""  # E.g., "e"

        # 1. EXACT MATCH (highest confidence)
        # Match: "II.1.e" or "II.1.e."
        exact_pattern = re.escape(code_provision) + r'\.?'
        patterns.append((
            r'\b' + exact_pattern + r'\b',
            'exact',
            self.CONFIDENCE_EXACT
        ))

        # 2. PREFIX MATCHES (with common prefixes)
        prefixes = [
            'Section', 'Provision', 'Code', 'Paragraph',
            'section', 'provision', 'code', 'paragraph',
            'NSPE Code', 'Code of Ethics', 'Ethics Code'
        ]
        for prefix in prefixes:
            prefix_pattern = r'\b' + re.escape(prefix) + r'\s+' + exact_pattern + r'\b'
            patterns.append((
                prefix_pattern,
                'prefix',
                self.CONFIDENCE_PREFIX
            ))

        # 3. HYPHENATED VARIANTS
        # Match: "II-1-e", "II-1e"
        if number:
            hyphen_patterns = [
                rf'\b{roman}-{number}' + (f'-{letter}' if letter else '') + r'\b',
                rf'\b{roman}-{number}' + (letter if letter else '') + r'\b'
            ]
            for hp in hyphen_patterns:
                patterns.append((
                    hp,
                    'hyphenated',
                    self.CONFIDENCE_HYPHENATED
                ))

        # 4. FLEXIBLE SPACING
        # Match: "II . 1 . e" or "II.1 . e"
        if number:
            flexible = rf'\b{roman}\s*\.\s*{number}'
            if letter:
                flexible += rf'\s*\.\s*{letter}'
            flexible += r'\b'
            patterns.append((
                flexible,
                'flexible',
                self.CONFIDENCE_FLEXIBLE
            ))

        # 5. WRITTEN-OUT FORMATS (lower confidence)
        # Match: "Section II, paragraph 1, subparagraph e"
        if number and letter:
            written_patterns = [
                rf'\bSection {roman}\W+paragraph {number}\W+subparagraph {letter}\b',
                rf'\bSection {roman}\W+para(?:graph)?\W+{number}\W+subpara(?:graph)?\W+{letter}\b',
                rf'\b{roman}\W+{number}\W+{letter}\b',  # Simplified written form
            ]
            for wp in written_patterns:
                patterns.append((
                    wp,
                    'written',
                    self.CONFIDENCE_WRITTEN
                ))
        elif number:  # No letter
            written_patterns = [
                rf'\bSection {roman}\W+paragraph {number}\b',
                rf'\b{roman}\W+{number}\b',
            ]
            for wp in written_patterns:
                patterns.append((
                    wp,
                    'written',
                    self.CONFIDENCE_WRITTEN
                ))

        logger.debug(f"Generated {len(patterns)} patterns for {code_provision}")
        return patterns

    def _search_section(
        self,
        section_text: str,
        section_name: str,
        patterns: List[Tuple[str, str, float]],
        code_provision: str
    ) -> List[CandidateMatch]:
        """
        Search a single section for all pattern matches.

        Args:
            section_text: The text to search
            section_name: Name of the section
            patterns: List of (pattern, match_type, confidence) tuples
            code_provision: The provision being searched for

        Returns:
            List of CandidateMatch objects
        """
        candidates = []

        for pattern, match_type, confidence in patterns:
            # Find all matches for this pattern
            for match in re.finditer(pattern, section_text, re.IGNORECASE):
                matched_text = match.group(0)
                position = match.start()

                # Extract context window
                before, after = self._extract_context(
                    section_text,
                    position,
                    len(matched_text)
                )

                # Create full excerpt (context + match)
                excerpt = before + matched_text + after

                candidate = CandidateMatch(
                    section=section_name,
                    excerpt=excerpt.strip(),
                    matched_text=matched_text,
                    match_type=match_type,
                    confidence=confidence,
                    position=position,
                    before_context=before.strip(),
                    after_context=after.strip()
                )

                candidates.append(candidate)

                logger.debug(
                    f"Found {match_type} match in {section_name}: '{matched_text}' "
                    f"(confidence: {confidence})"
                )

        return candidates

    def _extract_context(
        self,
        text: str,
        match_start: int,
        match_length: int,
        window_size: int = 200
    ) -> Tuple[str, str]:
        """
        Extract text before and after a match for context.

        Args:
            text: Full text
            match_start: Starting position of match
            match_length: Length of matched text
            window_size: Characters to include before/after (default 200)

        Returns:
            Tuple of (before_text, after_text)
        """
        # Get text before match
        before_start = max(0, match_start - window_size)
        before_text = text[before_start:match_start]

        # Try to start at sentence boundary
        last_period = before_text.rfind('. ')
        if last_period != -1 and (len(before_text) - last_period) < window_size:
            before_text = before_text[last_period + 2:]  # Skip ". "

        # Get text after match
        match_end = match_start + match_length
        after_end = min(len(text), match_end + window_size)
        after_text = text[match_end:after_end]

        # Try to end at sentence boundary
        first_period = after_text.find('. ')
        if first_period != -1 and first_period < window_size:
            after_text = after_text[:first_period + 1]  # Include period

        return before_text, after_text

    def _deduplicate_matches(
        self,
        candidates: List[CandidateMatch]
    ) -> List[CandidateMatch]:
        """
        Remove overlapping matches, keeping the highest confidence one.

        Args:
            candidates: List of all candidate matches

        Returns:
            Deduplicated list
        """
        if not candidates:
            return []

        # Group by section
        by_section = {}
        for candidate in candidates:
            if candidate.section not in by_section:
                by_section[candidate.section] = []
            by_section[candidate.section].append(candidate)

        deduplicated = []

        # Process each section
        for section_name, section_candidates in by_section.items():
            # Sort by position
            section_candidates.sort(key=lambda c: c.position)

            kept = []
            for candidate in section_candidates:
                # Check if this overlaps with any already kept
                overlaps = False
                for kept_candidate in kept:
                    # Check position overlap (within 50 chars)
                    if abs(candidate.position - kept_candidate.position) < 50:
                        # Overlapping - keep the higher confidence one
                        if candidate.confidence > kept_candidate.confidence:
                            kept.remove(kept_candidate)
                            kept.append(candidate)
                        overlaps = True
                        break

                if not overlaps:
                    kept.append(candidate)

            deduplicated.extend(kept)

        return deduplicated

    def get_citation_format_explanation(self, match_type: str) -> str:
        """
        Get human-readable explanation of how a provision was cited.

        Args:
            match_type: The type of match found

        Returns:
            Explanation string
        """
        explanations = {
            'exact': 'Exact provision number cited',
            'prefix': 'Provision cited with prefix (e.g., "Section II.1.e")',
            'hyphenated': 'Hyphenated format (e.g., "II-1-e")',
            'flexible': 'Flexible spacing format',
            'written': 'Written-out format (e.g., "Section II, paragraph 1")'
        }
        return explanations.get(match_type, 'Unknown citation format')
