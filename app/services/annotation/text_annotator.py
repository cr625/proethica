"""
Text Annotator -- matches terms in arbitrary text to ontology entities.

Server-side equivalent of the client-side JS matching in case_detail.html.
Uses UnifiedEntityResolver for entity data, then applies longest-first
word-boundary matching with overlap resolution.

Usage:
    annotator = TextAnnotator(case_id=7)
    spans = annotator.annotate("Engineer A had a duty to report the safety concerns.")
    for span in spans:
        print(f"{span.matched_text} -> {span.entity_label} ({span.entity_type})")

    # Or get pre-rendered HTML:
    html = annotator.annotate_html("Engineer A had a duty to report the safety concerns.")
"""

import re
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from markupsafe import Markup, escape

logger = logging.getLogger(__name__)


# Generic concept-type words that should not be highlighted as entities
SKIP_WORDS = frozenset({
    'state', 'action', 'event', 'role', 'resource', 'principle',
    'obligation', 'constraint', 'capability', 'states', 'actions',
    'events', 'roles', 'resources', 'principles', 'obligations',
    'constraints', 'capabilities',
    'nspe code of ethics', 'code of ethics',
})

MIN_LABEL_LENGTH = 4


@dataclass
class AnnotatedSpan:
    """A matched entity span within annotated text."""
    start: int
    end: int
    matched_text: str
    entity_label: str
    entity_type: str
    entity_uri: str
    definition: str
    source: str  # 'case' or 'ontology'
    source_pass: Optional[int] = None
    alias_types: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class TextAnnotator:
    """Annotate arbitrary text by matching terms to ontology entities.

    Wraps UnifiedEntityResolver to get entity labels, then applies
    longest-first regex matching with word boundaries and overlap resolution.
    """

    def __init__(self, case_id: int, label_index: Dict[str, Dict] = None):
        """
        Args:
            case_id: Case ID for loading entities from TemporaryRDFStorage.
            label_index: Optional pre-built label index (bypasses resolver).
                         Useful when the caller already has the data.
        """
        self.case_id = case_id

        if label_index is not None:
            self._label_index = label_index
        else:
            from app.services.unified_entity_resolver import UnifiedEntityResolver
            resolver = UnifiedEntityResolver(case_id=case_id)
            self._label_index = resolver.get_label_index()

        # Build sorted labels and compiled regex once
        self._sorted_labels = self._build_sorted_labels()
        self._pattern = self._compile_pattern()

    def _build_sorted_labels(self) -> List[str]:
        """Filter and sort labels: longest first, skip generic terms."""
        labels = [
            label for label in self._label_index
            if len(label) >= MIN_LABEL_LENGTH and label.lower() not in SKIP_WORDS
        ]
        labels.sort(key=len, reverse=True)
        return labels

    def _compile_pattern(self) -> Optional[re.Pattern]:
        """Compile a single regex alternation for all entity labels."""
        if not self._sorted_labels:
            return None
        escaped = [re.escape(label) for label in self._sorted_labels]
        return re.compile(r'\b(' + '|'.join(escaped) + r')\b', re.IGNORECASE)

    def annotate(self, text: str) -> List[AnnotatedSpan]:
        """Find all entity matches in text.

        Returns non-overlapping AnnotatedSpan list sorted by position.
        Longest matches win when spans overlap.
        """
        if not text or not self._pattern:
            return []

        raw_matches = []
        for match in self._pattern.finditer(text):
            label_key = match.group(1).lower()
            entity = self._label_index.get(label_key)
            if not entity:
                continue
            raw_matches.append(AnnotatedSpan(
                start=match.start(),
                end=match.end(),
                matched_text=match.group(1),
                entity_label=entity.get('label', ''),
                entity_type=entity.get('extraction_type', entity.get('entity_type', '')),
                entity_uri=entity.get('uri', ''),
                definition=entity.get('definition', ''),
                source=entity.get('source', 'case'),
                source_pass=entity.get('source_pass'),
                alias_types=entity.get('alias_types', []),
            ))

        return self._resolve_overlaps(raw_matches)

    def annotate_html(self, text: str) -> Markup:
        """Annotate text and return HTML with onto-label spans.

        Produces the same markup as the client-side JS in case_detail.html,
        so ontology-popovers.js can initialize popovers on the result.
        """
        spans = self.annotate(text)
        if not spans:
            return Markup(escape(text))

        parts = []
        last_end = 0
        for span in spans:
            # Text before this span
            if span.start > last_end:
                parts.append(escape(text[last_end:span.start]))
            # Build onto-label span
            parts.append(self._render_span(span))
            last_end = span.end

        # Trailing text
        if last_end < len(text):
            parts.append(escape(text[last_end:]))

        return Markup(''.join(str(p) for p in parts))

    def get_entity_count(self) -> int:
        """Number of matchable entity labels."""
        return len(self._sorted_labels)

    @staticmethod
    def _resolve_overlaps(matches: List[AnnotatedSpan]) -> List[AnnotatedSpan]:
        """Remove overlapping spans, keeping the longest match."""
        if not matches:
            return []
        matches.sort(key=lambda m: (m.start, -(m.end - m.start)))
        result = [matches[0]]
        for m in matches[1:]:
            if m.start >= result[-1].end:
                result.append(m)
        return result

    @staticmethod
    def _render_span(span: AnnotatedSpan) -> Markup:
        """Render an AnnotatedSpan as an HTML onto-label element."""
        css_class = 'onto-label'
        if span.source == 'ontology':
            css_class += ' onto-source-ontology'

        truncated_def = span.definition
        if len(truncated_def) > 200:
            truncated_def = truncated_def[:200] + '...'

        return Markup(
            '<span class="{css_class}" tabindex="0"'
            ' data-bs-toggle="popover"'
            ' data-bs-trigger="hover focus"'
            ' data-bs-html="true"'
            ' data-bs-placement="top"'
            ' data-entity-type="{entity_type}"'
            ' data-entity-source="{source}"'
            ' data-entity-definition="{definition}"'
            ' data-entity-uri="{uri}"'
            ' title="{title}">{text}</span>'.format(
                css_class=escape(css_class),
                entity_type=escape(span.entity_type),
                source=escape(span.source),
                definition=escape(truncated_def),
                uri=escape(span.entity_uri),
                title=escape(span.entity_label or span.matched_text),
                text=escape(span.matched_text),
            )
        )
