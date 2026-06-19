"""
Provision Grouper

Groups detected provision mentions by which Board provision they relate to.
This is the second stage of the mention-first approach.
"""

import logging
from typing import List, Dict
from collections import defaultdict

logger = logging.getLogger(__name__)


class ProvisionGrouper:
    """
    Groups provision mentions by Board provision.

    Takes all detected mentions and organizes them by which provision
    from the Board's References section they correspond to.
    """

    def __init__(self):
        pass

    def group_mentions_by_provision(
        self,
        all_mentions: List,  # List of ProvisionMention objects
        board_provisions: List[Dict]  # From HTML parser
    ) -> Dict[str, List]:
        """
        Group mentions by Board provision.

        Args:
            all_mentions: All detected provision mentions in case
            board_provisions: Provisions from References section HTML
                             (each has 'code_provision' key)

        Returns:
            Dict mapping provision code → list of mentions
            Example: {
                "I.4": [mention1, mention2],
                "II.4.e": [mention3, mention4, mention5],
            }

        Note: Only includes provisions that are in the Board's References.
              Other mentions are logged but not included.
        """
        # Create normalized set of Board provision codes
        board_codes = {}  # normalized_code → original_code
        for provision in board_provisions:
            original = provision['code_provision']
            normalized = self._normalize_code(original)
            board_codes[normalized] = original

        logger.info(f"Grouping mentions for {len(board_codes)} Board provisions: {list(board_codes.values())}")

        # Initialize groups with empty lists
        grouped = {original: [] for original in board_codes.values()}

        # Track unmatched mentions
        unmatched = []

        # Group mentions
        for mention in all_mentions:
            normalized = self._normalize_code(mention.mentioned_provision)

            if normalized in board_codes:
                # Match found - add to appropriate group
                original_code = board_codes[normalized]
                grouped[original_code].append(mention)
                logger.debug(
                    f"Matched '{mention.citation_text}' in {mention.section} "
                    f"to Board provision {original_code}"
                )
            else:
                # Not a Board provision - log it
                unmatched.append(mention)

        # Log statistics
        for code, mentions in grouped.items():
            logger.info(f"Provision {code}: {len(mentions)} mentions")

        if unmatched:
            unmatched_codes = set(m.mentioned_provision for m in unmatched)
            logger.info(
                f"Found {len(unmatched)} mentions of provisions not in Board References: "
                f"{sorted(unmatched_codes)}"
            )

        return grouped

    def _normalize_code(self, code: str) -> str:
        """
        Normalize provision code for comparison.

        Handles variations like:
        - "II.4.e" → "II.4.E"
        - "II.4.e." → "II.4.E" (strip trailing period)
        - "ii.4.e" → "II.4.E" (uppercase)

        Args:
            code: Original code

        Returns:
            Normalized code (uppercase, no trailing period)
        """
        normalized = code.strip().rstrip('.').upper()
        return normalized

    def get_grouping_summary(
        self,
        grouped: Dict[str, List]
    ) -> Dict:
        """
        Generate summary statistics about the grouping.

        Args:
            grouped: Result from group_mentions_by_provision()

        Returns:
            Dict with summary info
        """
        total_mentions = sum(len(mentions) for mentions in grouped.values())

        provisions_with_mentions = sum(1 for mentions in grouped.values() if mentions)
        provisions_without_mentions = sum(1 for mentions in grouped.values() if not mentions)

        # Section breakdown
        sections_used = defaultdict(int)
        for mentions in grouped.values():
            for mention in mentions:
                sections_used[mention.section] += 1

        return {
            'total_board_provisions': len(grouped),
            'total_mentions': total_mentions,
            'provisions_with_mentions': provisions_with_mentions,
            'provisions_without_mentions': provisions_without_mentions,
            'sections_breakdown': dict(sections_used),
            'average_mentions_per_provision': (
                total_mentions / len(grouped) if grouped else 0
            )
        }

    def format_for_display(
        self,
        grouped: Dict[str, List]
    ) -> List[Dict]:
        """
        Format grouped mentions for UI display.

        Args:
            grouped: Result from group_mentions_by_provision()

        Returns:
            List of dicts with provision info and mentions
        """
        formatted = []

        for provision_code, mentions in grouped.items():
            provision_info = {
                'code_provision': provision_code,
                'mention_count': len(mentions),
                'mentions': [
                    {
                        'section': m.section,
                        'excerpt': m.excerpt,
                        'citation_text': m.citation_text,
                        'match_type': m.match_type,
                        'position': m.position
                    }
                    for m in mentions
                ]
            }
            formatted.append(provision_info)

        # Sort by provision code (I.4 before II.4.e, etc.)
        formatted.sort(key=lambda p: self._sort_key(p['code_provision']))

        return formatted

    def _sort_key(self, code: str) -> tuple:
        """
        Generate sort key for provision codes.

        Args:
            code: Provision code like "II.4.e"

        Returns:
            Tuple for sorting (roman_value, number, letter)
        """
        import re

        # Parse code
        match = re.match(r'^([IVX]+)\.(\d+)(?:\.([a-z]))?', code.upper())
        if not match:
            return (999, 999, 'z')  # Put unparseable codes at end

        roman = match.group(1)
        number = int(match.group(2))
        letter = match.group(3) or ''

        # Convert roman to int
        roman_values = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6}
        roman_int = roman_values.get(roman, 999)

        return (roman_int, number, letter)
