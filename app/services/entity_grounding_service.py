"""
Entity Grounding Service

Post-processes extracted text (questions, conclusions, etc.) to reliably ground
entity references with URIs from the extracted ontology.

Matching Strategy:
1. Exact match: "Engineer A" -> Engineer A entity
2. Partial match: "Engineer" -> Engineer A (if unambiguous)
3. Semantic similarity: Verify matched individual belongs to correct class

Two-level output:
1. Word-level: Entity spans marked in text with positions
2. Item-level: List of all entities involved, grouped by type
"""

import re
import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class EntityMention:
    """A mention of an entity in text."""
    label: str                    # Entity label (e.g., "Engineer A")
    uri: str                      # Entity URI
    entity_type: str              # Type (roles, obligations, etc.)
    start: int                    # Start position in text
    end: int                      # End position in text
    match_type: str               # 'exact', 'partial', or 'semantic'
    confidence: float = 1.0       # Confidence score (1.0 for exact, lower for fuzzy)
    matched_text: str = ""        # The actual text that was matched


@dataclass
class GroundingResult:
    """Result of grounding entity references in text."""
    original_text: str
    grounded_text: str            # Text with entity markers (for display)
    entity_mentions: List[EntityMention] = field(default_factory=list)
    involved_entities: Dict[str, List[Dict]] = field(default_factory=dict)
    grounding_stats: Dict[str, int] = field(default_factory=dict)


class EntityGroundingService:
    """
    Ground entity references in extracted text with URIs.

    Uses three-tier matching:
    1. Exact match for individuals
    2. Partial match for shortened references
    3. Semantic similarity for paraphrased references
    """

    def __init__(self, embedding_service=None):
        """
        Initialize grounding service.

        Args:
            embedding_service: Optional embedding service for semantic matching
        """
        self.embedding_service = embedding_service
        self._entity_cache = {}  # Cache entity embeddings

    def ground_text(
        self,
        text: str,
        all_entities: Dict[str, List],
        min_confidence: float = 0.6
    ) -> GroundingResult:
        """
        Ground entity references in text.

        Args:
            text: Text to ground (question, conclusion, etc.)
            all_entities: Dict of entities by type from get_all_case_entities()
            min_confidence: Minimum confidence for fuzzy matches

        Returns:
            GroundingResult with mentions and involved entities
        """
        if not text or not text.strip():
            return GroundingResult(
                original_text=text,
                grounded_text=text,
                grounding_stats={'total': 0}
            )

        # Build entity index for matching
        entity_index = self._build_entity_index(all_entities)

        # Find all mentions
        mentions = []

        # Phase 1: Exact matches (highest priority)
        exact_mentions = self._find_exact_matches(text, entity_index)
        mentions.extend(exact_mentions)

        # Phase 2: Partial matches (for shortened references)
        # Only look for partials where we didn't find exact matches
        matched_spans = [(m.start, m.end) for m in mentions]
        partial_mentions = self._find_partial_matches(text, entity_index, matched_spans)
        mentions.extend(partial_mentions)

        # Phase 3: Semantic matches (for paraphrased references)
        # Only if embedding service available and not too many entities
        if self.embedding_service and len(entity_index) < 100:
            all_matched_spans = [(m.start, m.end) for m in mentions]
            semantic_mentions = self._find_semantic_matches(
                text, entity_index, all_matched_spans, min_confidence
            )
            mentions.extend(semantic_mentions)

        # Sort by position and remove overlaps (prefer higher confidence)
        mentions = self._resolve_overlaps(mentions)

        # Build grounded text with entity markers
        grounded_text = self._build_grounded_text(text, mentions)

        # Group involved entities by type
        involved = self._group_by_type(mentions)

        # Calculate stats
        stats = {
            'total': len(mentions),
            'exact': len([m for m in mentions if m.match_type == 'exact']),
            'partial': len([m for m in mentions if m.match_type == 'partial']),
            'semantic': len([m for m in mentions if m.match_type == 'semantic'])
        }

        return GroundingResult(
            original_text=text,
            grounded_text=grounded_text,
            entity_mentions=mentions,
            involved_entities=involved,
            grounding_stats=stats
        )

    def ground_items(
        self,
        items: List[Dict],
        text_field: str,
        all_entities: Dict[str, List],
        min_confidence: float = 0.6
    ) -> List[Dict]:
        """
        Ground entity references in a list of items (questions, conclusions, etc.).

        Args:
            items: List of dicts with text to ground
            text_field: Field name containing text (e.g., 'question_text')
            all_entities: Dict of entities by type
            min_confidence: Minimum confidence for fuzzy matches

        Returns:
            Items with added grounding fields
        """
        grounded_items = []

        for item in items:
            text = item.get(text_field, '')
            result = self.ground_text(text, all_entities, min_confidence)

            # Add grounding data to item
            grounded_item = dict(item)
            grounded_item['grounded_text'] = result.grounded_text
            grounded_item['entity_mentions'] = [
                {
                    'label': m.label,
                    'uri': m.uri,
                    'entity_type': m.entity_type,
                    'start': m.start,
                    'end': m.end,
                    'match_type': m.match_type,
                    'confidence': m.confidence,
                    'matched_text': m.matched_text
                }
                for m in result.entity_mentions
            ]
            grounded_item['involved_entities'] = result.involved_entities
            grounded_item['grounding_stats'] = result.grounding_stats

            grounded_items.append(grounded_item)

        return grounded_items

    def _build_entity_index(self, all_entities: Dict[str, List]) -> Dict[str, Dict]:
        """
        Build index of entities for efficient matching.

        Returns:
            Dict mapping lowercase labels to entity info
        """
        index = {}

        for entity_type, entities in all_entities.items():
            for entity in entities:
                # Extract label and URI
                if isinstance(entity, dict):
                    label = entity.get('label', entity.get('entity_label', ''))
                    uri = entity.get('uri', entity.get('entity_uri', ''))
                    definition = entity.get('definition', entity.get('entity_definition', ''))
                else:
                    # SQLAlchemy model object
                    label = getattr(entity, 'entity_label', '')
                    uri = getattr(entity, 'entity_uri', '')
                    definition = getattr(entity, 'entity_definition', '')

                if label and uri:
                    # Index by lowercase for case-insensitive matching
                    key = label.lower()
                    index[key] = {
                        'label': label,
                        'uri': uri,
                        'entity_type': entity_type,
                        'definition': definition
                    }

                    # Also index by significant words for partial matching
                    # Skip stopwords, short words, and domain-generic words that cause false positives
                    stopwords = {'a', 'an', 'the', 'of', 'in', 'on', 'at', 'to', 'for', 'by',
                                 'is', 'it', 'as', 'or', 'and', 'but', 'not', 'be', 'was', 'were'}
                    # Domain-generic words that appear in entity names but shouldn't trigger partial matches
                    domain_generic = {'ethical', 'professional', 'public', 'review', 'case',
                                      'general', 'specific', 'primary', 'secondary', 'standard',
                                      'principle', 'obligation', 'constraint', 'capability',
                                      'safety', 'welfare', 'integrity', 'competence'}
                    words = label.split()
                    if len(words) > 1:
                        for word in words:
                            word_lower = word.lower()
                            # Skip stopwords, short words (< 3 chars), and domain-generic words
                            if word_lower in stopwords or len(word_lower) < 3 or word_lower in domain_generic:
                                continue
                            word_key = f"_partial_{word_lower}"
                            if word_key not in index:
                                index[word_key] = []
                            index[word_key].append({
                                'label': label,
                                'uri': uri,
                                'entity_type': entity_type,
                                'definition': definition
                            })

        return index

    def _find_exact_matches(
        self,
        text: str,
        entity_index: Dict[str, Dict]
    ) -> List[EntityMention]:
        """Find exact matches of entity labels in text."""
        mentions = []
        text_lower = text.lower()

        # Sort by label length (longest first) to handle overlaps
        sorted_labels = sorted(
            [k for k in entity_index.keys() if not k.startswith('_partial_')],
            key=len,
            reverse=True
        )

        for label_lower in sorted_labels:
            entity_info = entity_index[label_lower]

            # Find all occurrences
            start = 0
            while True:
                pos = text_lower.find(label_lower, start)
                if pos == -1:
                    break

                # Check word boundaries
                if self._is_word_boundary(text_lower, pos, pos + len(label_lower)):
                    mentions.append(EntityMention(
                        label=entity_info['label'],
                        uri=entity_info['uri'],
                        entity_type=entity_info['entity_type'],
                        start=pos,
                        end=pos + len(label_lower),
                        match_type='exact',
                        confidence=1.0,
                        matched_text=text[pos:pos + len(label_lower)]
                    ))

                start = pos + 1

        return mentions

    def _find_partial_matches(
        self,
        text: str,
        entity_index: Dict[str, Dict],
        excluded_spans: List[Tuple[int, int]]
    ) -> List[EntityMention]:
        """
        Find partial matches (e.g., "Engineer" -> "Engineer A").
        Only match if unambiguous (single candidate).
        """
        mentions = []
        text_lower = text.lower()

        # Get all partial keys
        partial_keys = [k for k in entity_index.keys() if k.startswith('_partial_')]

        for partial_key in partial_keys:
            word = partial_key.replace('_partial_', '')
            candidates = entity_index[partial_key]

            # Only use partial match if unambiguous
            if len(candidates) != 1:
                continue

            entity_info = candidates[0]

            # Find occurrences of the word
            pattern = r'\b' + re.escape(word) + r'\b'
            for match in re.finditer(pattern, text_lower):
                pos = match.start()
                end = match.end()

                # Skip if overlaps with existing match
                if any(self._spans_overlap((pos, end), span) for span in excluded_spans):
                    continue

                mentions.append(EntityMention(
                    label=entity_info['label'],
                    uri=entity_info['uri'],
                    entity_type=entity_info['entity_type'],
                    start=pos,
                    end=end,
                    match_type='partial',
                    confidence=0.8,
                    matched_text=text[pos:end]
                ))

        return mentions

    def _find_semantic_matches(
        self,
        text: str,
        entity_index: Dict[str, Dict],
        excluded_spans: List[Tuple[int, int]],
        min_confidence: float
    ) -> List[EntityMention]:
        """
        Find semantic matches using embedding similarity.
        Looks for noun phrases that might refer to entities.
        """
        if not self.embedding_service:
            return []

        mentions = []

        # Simple noun phrase extraction (could be improved with NLP)
        # Look for capitalized phrases that might be entity references
        pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'

        for match in re.finditer(pattern, text):
            phrase = match.group(1)
            pos = match.start()
            end = match.end()

            # Skip if overlaps with existing match
            if any(self._spans_overlap((pos, end), span) for span in excluded_spans):
                continue

            # Skip if it's already an exact match
            if phrase.lower() in entity_index:
                continue

            # Find most similar entity
            best_match = self._find_similar_entity(phrase, entity_index, min_confidence)

            if best_match:
                mentions.append(EntityMention(
                    label=best_match['label'],
                    uri=best_match['uri'],
                    entity_type=best_match['entity_type'],
                    start=pos,
                    end=end,
                    match_type='semantic',
                    confidence=best_match['confidence'],
                    matched_text=phrase
                ))

        return mentions

    def _find_similar_entity(
        self,
        phrase: str,
        entity_index: Dict[str, Dict],
        min_confidence: float
    ) -> Optional[Dict]:
        """Find most similar entity to phrase using embeddings."""
        try:
            # Get phrase embedding
            phrase_embedding = self.embedding_service.get_embedding(phrase)

            best_match = None
            best_score = min_confidence

            for key, entity_info in entity_index.items():
                if key.startswith('_partial_'):
                    continue

                # Get entity label embedding (use cache)
                label = entity_info['label']
                if label not in self._entity_cache:
                    self._entity_cache[label] = self.embedding_service.get_embedding(label)

                entity_embedding = self._entity_cache[label]

                # Calculate cosine similarity
                similarity = self._cosine_similarity(phrase_embedding, entity_embedding)

                if similarity > best_score:
                    best_score = similarity
                    best_match = {
                        **entity_info,
                        'confidence': similarity
                    }

            return best_match

        except Exception as e:
            logger.warning(f"Semantic matching failed for '{phrase}': {e}")
            return None

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not a or not b:
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def _is_word_boundary(self, text: str, start: int, end: int) -> bool:
        """Check if match is at word boundaries."""
        if start > 0 and text[start - 1].isalnum():
            return False
        if end < len(text) and text[end].isalnum():
            return False
        return True

    def _spans_overlap(self, span1: Tuple[int, int], span2: Tuple[int, int]) -> bool:
        """Check if two spans overlap."""
        return not (span1[1] <= span2[0] or span2[1] <= span1[0])

    def _resolve_overlaps(self, mentions: List[EntityMention]) -> List[EntityMention]:
        """Remove overlapping mentions, preferring higher confidence."""
        if not mentions:
            return []

        # Sort by confidence (desc) then by start position
        sorted_mentions = sorted(mentions, key=lambda m: (-m.confidence, m.start))

        result = []
        used_spans = []

        for mention in sorted_mentions:
            span = (mention.start, mention.end)
            if not any(self._spans_overlap(span, used) for used in used_spans):
                result.append(mention)
                used_spans.append(span)

        # Sort by position for output
        return sorted(result, key=lambda m: m.start)

    def _build_grounded_text(self, text: str, mentions: List[EntityMention]) -> str:
        """
        Build text with entity markers for display.

        Format: <entity uri="..." type="...">matched text</entity>
        """
        if not mentions:
            return text

        result = []
        last_end = 0

        for mention in sorted(mentions, key=lambda m: m.start):
            # Add text before this mention
            result.append(text[last_end:mention.start])

            # Add marked entity
            result.append(
                f'<entity uri="{mention.uri}" type="{mention.entity_type}" '
                f'label="{mention.label}" confidence="{mention.confidence:.2f}">'
                f'{text[mention.start:mention.end]}</entity>'
            )

            last_end = mention.end

        # Add remaining text
        result.append(text[last_end:])

        return ''.join(result)

    def _group_by_type(self, mentions: List[EntityMention]) -> Dict[str, List[Dict]]:
        """Group mentions by entity type, deduplicating."""
        grouped = {}
        seen = set()

        for mention in mentions:
            entity_type = mention.entity_type
            if entity_type not in grouped:
                grouped[entity_type] = []

            # Deduplicate by URI
            if mention.uri not in seen:
                seen.add(mention.uri)
                grouped[entity_type].append({
                    'label': mention.label,
                    'uri': mention.uri
                })

        return grouped
