"""
Entity Reconciliation Service

Three-phase deduplication of entities extracted across Steps 1-3:

Phase 1: Pre-filter -- group by (extraction_type, storage_type), skip temporal dynamics.
Phase 2: Exact-match auto-merge -- identical normalized labels within a group.
Phase 3: LLM semantic evaluation -- Haiku batch dedup for groups with near-matches.

Two modes:
- reconcile_auto(): batch processing -- exact-match merges + LLM auto-merge, no review
- reconcile_with_review(): interactive -- exact-match merges, LLM candidates for review
"""

import json
import logging
import os
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from app.models import db
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.services.entity_merge_service import EntityMergeService

logger = logging.getLogger(__name__)

# Pattern to strip trailing parenthetical qualifiers like "(Present Case)"
PAREN_SUFFIX_RE = re.compile(r'\s*\([^)]*\)\s*$')

# Extraction types excluded from reconciliation (different structure, no URIs)
SKIP_EXTRACTION_TYPES = {'temporal_dynamics_enhanced', 'temporal_dynamics'}

# Label similarity threshold for triggering LLM evaluation on a group.
# At least one pair in the group must exceed this to justify an LLM call.
LLM_CANDIDATE_THRESHOLD = 0.55


@dataclass
class ReconciliationCandidate:
    """A pair of entities that may be duplicates."""
    entity_a_id: int
    entity_b_id: int
    entity_a_label: str
    entity_b_label: str
    similarity: float
    same_concept_type: bool
    recommendation: str  # 'auto_merge', 'review', 'keep_separate'
    llm_reason: str = ''
    entity_a_context: Dict[str, Any] = field(default_factory=dict)
    entity_b_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReconciliationResult:
    """Result of reconciliation for a case."""
    case_id: int
    auto_merged: int = 0
    review_candidates: List[ReconciliationCandidate] = field(default_factory=list)
    skipped: int = 0
    errors: List[str] = field(default_factory=list)


class EntityReconciliationService:
    """Three-phase entity deduplication for a case."""

    def __init__(self):
        self._merge_service = EntityMergeService()

    def reconcile_auto(self, case_id: int) -> ReconciliationResult:
        """Batch mode: exact-match merges only, no LLM, no review candidates."""
        result = ReconciliationResult(case_id=case_id)
        groups = self._group_entities(case_id)

        for group_key, entities in groups.items():
            merged = self._auto_merge_exact_matches(entities, result)
            result.auto_merged += merged

        return result

    def reconcile_with_review(self, case_id: int) -> ReconciliationResult:
        """Interactive mode: exact-match merges + LLM candidates for human review."""
        result = ReconciliationResult(case_id=case_id)
        groups = self._group_entities(case_id)

        for group_key, entities in groups.items():
            # Phase 2: Exact-match auto-merge
            merged = self._auto_merge_exact_matches(entities, result)
            result.auto_merged += merged

        # Re-fetch groups after merges (entities were deleted)
        groups = self._group_entities(case_id)

        # Phase 3: LLM semantic evaluation for groups with near-matches
        for group_key, entities in groups.items():
            if len(entities) < 2:
                continue

            if self._group_has_near_matches(entities):
                try:
                    candidates = self._llm_batch_dedup(group_key, entities)
                    result.review_candidates.extend(candidates)
                except Exception as e:
                    logger.error(
                        f"LLM dedup failed for group {group_key}: {e}",
                        exc_info=True
                    )
                    result.errors.append(
                        f"LLM evaluation failed for {group_key[0]} {group_key[1]}: {e}"
                    )

        return result

    def merge_entities(self, keep_id: int, merge_id: int) -> bool:
        """Merge entity merge_id into keep_id, then delete merge_id.

        Delegates property merging to EntityMergeService.merge_entity_properties().
        """
        keep_entity = TemporaryRDFStorage.query.get(keep_id)
        merge_entity = TemporaryRDFStorage.query.get(merge_id)

        if not keep_entity or not merge_entity:
            logger.error(f"Entity not found: keep={keep_id}, merge={merge_id}")
            return False

        if keep_entity.is_published or merge_entity.is_published:
            logger.error("Cannot merge published entities")
            return False

        try:
            self._merge_service.merge_entity_properties(
                keep_entity,
                merge_entity.rdf_json_ld or {},
                merge_entity.extraction_session_id
            )

            # Adopt the shorter/cleaner label if the merge entity has one
            keep_label = keep_entity.entity_label or ''
            merge_label = merge_entity.entity_label or ''
            preferred = self._pick_preferred_label(keep_label, merge_label)
            if preferred != keep_label:
                keep_entity.entity_label = preferred
                if keep_entity.rdf_json_ld:
                    keep_entity.rdf_json_ld['label'] = preferred

            db.session.delete(merge_entity)
            db.session.commit()

            logger.info(
                f"Merged entity '{merge_label}' (id={merge_id}) "
                f"into '{keep_entity.entity_label}' (id={keep_id})"
            )
            return True

        except Exception as e:
            db.session.rollback()
            logger.error(f"Merge failed: {e}", exc_info=True)
            return False

    # -- Phase 1: Grouping --

    def _group_entities(self, case_id: int) -> Dict[Tuple[str, str], List[TemporaryRDFStorage]]:
        """Group unpublished entities by (extraction_type, storage_type).

        Skips temporal dynamics entities (different structure, no URIs).
        """
        entities = TemporaryRDFStorage.query.filter(
            TemporaryRDFStorage.case_id == case_id,
            TemporaryRDFStorage.is_published == False  # noqa: E712
        ).all()

        groups: Dict[Tuple[str, str], List[TemporaryRDFStorage]] = {}
        for e in entities:
            if e.extraction_type in SKIP_EXTRACTION_TYPES:
                continue
            key = (e.extraction_type or 'unknown', e.storage_type or 'unknown')
            groups.setdefault(key, []).append(e)

        return groups

    # -- Phase 2: Exact-match auto-merge --

    def _auto_merge_exact_matches(
        self, entities: List[TemporaryRDFStorage], result: ReconciliationResult
    ) -> int:
        """Find and merge entities with identical normalized labels within a group."""
        # Build normalized-label → entity list mapping
        label_groups: Dict[str, List[TemporaryRDFStorage]] = {}
        for e in entities:
            norm = self._normalize_label(e.entity_label or '')
            label_groups.setdefault(norm, []).append(e)

        merged_count = 0
        for norm_label, group in label_groups.items():
            if len(group) < 2:
                continue

            # Keep first, merge rest into it
            keep = group[0]
            for merge_entity in group[1:]:
                try:
                    success = self.merge_entities(keep.id, merge_entity.id)
                    if success:
                        merged_count += 1
                    else:
                        result.errors.append(
                            f"Failed to auto-merge '{merge_entity.entity_label}' "
                            f"into '{keep.entity_label}'"
                        )
                except Exception as e:
                    result.errors.append(str(e))
                    logger.error(f"Auto-merge error: {e}", exc_info=True)

        return merged_count

    # -- Phase 3: LLM semantic evaluation --

    def _group_has_near_matches(self, entities: List[TemporaryRDFStorage]) -> bool:
        """Check if any pair in the group has label similarity >= threshold."""
        n = len(entities)
        for i in range(n):
            for j in range(i + 1, n):
                sim = self._compute_similarity(
                    entities[i].entity_label or '',
                    entities[j].entity_label or ''
                )
                if sim >= LLM_CANDIDATE_THRESHOLD:
                    return True
        return False

    def _llm_batch_dedup(
        self,
        group_key: Tuple[str, str],
        entities: List[TemporaryRDFStorage]
    ) -> List[ReconciliationCandidate]:
        """Send a group of entities to Haiku for batch duplicate detection."""
        extraction_type, storage_type = group_key
        prompt = self._build_dedup_prompt(extraction_type, storage_type, entities)

        try:
            response_json = self._call_llm(prompt)
        except Exception as e:
            logger.error(f"LLM call failed for {group_key}: {e}", exc_info=True)
            raise

        # Parse LLM response into ReconciliationCandidate objects
        candidates = []
        entity_map = {e.id: e for e in entities}
        duplicate_groups = response_json.get('duplicate_groups', [])

        for dup_group in duplicate_groups:
            ids = dup_group.get('ids', [])
            reason = dup_group.get('reason', '')

            if len(ids) < 2:
                continue

            # Validate all IDs exist in our entity map
            valid_ids = [eid for eid in ids if eid in entity_map]
            if len(valid_ids) < 2:
                logger.warning(
                    f"LLM returned invalid entity IDs: {ids} "
                    f"(valid: {valid_ids})"
                )
                continue

            # Create pairwise candidates from the group
            # First entity is the keep candidate, paired with each subsequent
            for k in range(1, len(valid_ids)):
                a = entity_map[valid_ids[0]]
                b = entity_map[valid_ids[k]]
                candidates.append(ReconciliationCandidate(
                    entity_a_id=a.id,
                    entity_b_id=b.id,
                    entity_a_label=a.entity_label or '',
                    entity_b_label=b.entity_label or '',
                    similarity=1.0,  # LLM-confirmed match
                    same_concept_type=True,
                    recommendation='review',
                    llm_reason=reason,
                    entity_a_context=self._get_entity_context(a),
                    entity_b_context=self._get_entity_context(b),
                ))

        return candidates

    def _build_dedup_prompt(
        self,
        extraction_type: str,
        storage_type: str,
        entities: List[TemporaryRDFStorage]
    ) -> str:
        """Build the LLM prompt for batch duplicate detection."""
        entity_lines = []
        for i, e in enumerate(entities, 1):
            rdf = e.rdf_json_ld or {}
            definition = (
                e.entity_definition
                or rdf.get('definition', '')
                or ''
            )[:300]
            section = rdf.get('source_section', rdf.get('section_type', ''))
            line = f'{i}. [ID: {e.id}] "{e.entity_label or ""}"'
            if definition:
                line += f'\n   Definition: "{definition}"'
            if section:
                line += f' (source: {section})'
            entity_lines.append(line)

        entity_list = '\n'.join(entity_lines)
        type_label = extraction_type.replace('_', ' ').title()
        storage_label = storage_type

        return f"""You are checking for EXACT DUPLICATES among entities extracted from a professional ethics case.

The only valid duplicates are entities where the SAME specific concept was extracted twice from different document sections (Facts vs Discussion). These will have nearly identical labels or clearly refer to the identical specific thing.

Entity type: {type_label} ({storage_label})

Entities:
{entity_list}

STRICT RULES -- most entities are NOT duplicates:
- DUPLICATE: Same label or trivially rephrased label referring to the exact same specific concept
- NOT duplicate: Different roles of the same person (e.g., "Engineer A Design Role" vs "Engineer A Safety Role")
- NOT duplicate: Different BER case references (e.g., "BER 85-3 ..." vs "BER 98-8 ...")
- NOT duplicate: Related but distinct concepts (e.g., "Safety Obligation" vs "Competence Obligation")
- NOT duplicate: Different aspects, perspectives, or facets of a broader topic
- NOT duplicate: General vs specific versions of a concept (e.g., "Safety Constraint" vs "Structural Safety Constraint")
- When in doubt, they are NOT duplicates

Return ONLY valid JSON (no other text):
{{"duplicate_groups": [{{"ids": [id1, id2], "reason": "brief explanation"}}]}}

If no duplicates exist (the most common result), return:
{{"duplicate_groups": []}}"""

    def _call_llm(self, prompt: str) -> Dict[str, Any]:
        """Call Haiku for dedup evaluation."""
        from models import ModelConfig
        from app.utils.llm_utils import extract_json_from_response

        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            try:
                from flask import current_app
                api_key = current_app.config.get('ANTHROPIC_API_KEY')
            except RuntimeError:
                pass

        if not api_key:
            raise RuntimeError("No ANTHROPIC_API_KEY available for reconciliation")

        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        model = ModelConfig.get_claude_model("fast")

        logger.info(f"Calling {model} for entity reconciliation")

        response = client.messages.create(
            model=model,
            max_tokens=2048,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text
        usage = response.usage
        logger.info(
            f"LLM reconciliation: {usage.input_tokens} input, "
            f"{usage.output_tokens} output tokens"
        )

        return extract_json_from_response(response_text)

    # -- Entity context for display --

    def _get_entity_context(self, entity: TemporaryRDFStorage) -> Dict[str, Any]:
        """Extract definition, source section, and source text from entity for display."""
        rdf = entity.rdf_json_ld or {}
        definition = entity.entity_definition or rdf.get('definition', '') or ''
        section = rdf.get('source_section', rdf.get('section_type', ''))
        source_text = (rdf.get('source_text', '') or '')[:200]
        return {
            'definition': definition[:300],
            'source_section': section,
            'source_text_preview': source_text,
            'extraction_type': entity.extraction_type or '',
            'storage_type': entity.storage_type or '',
        }

    # -- Label helpers --

    def _compute_similarity(self, label_a: str, label_b: str) -> float:
        """SequenceMatcher ratio on normalized labels."""
        norm_a = self._normalize_label(label_a)
        norm_b = self._normalize_label(label_b)
        return SequenceMatcher(None, norm_a, norm_b).ratio()

    def _normalize_label(self, label: str) -> str:
        """Normalize a label for comparison."""
        label = label.lower().strip()
        label = PAREN_SUFFIX_RE.sub('', label)
        return label.strip()

    def _pick_preferred_label(self, label_a: str, label_b: str) -> str:
        """Pick the preferred label -- shorter and without parenthetical suffixes."""
        a_has_paren = bool(PAREN_SUFFIX_RE.search(label_a))
        b_has_paren = bool(PAREN_SUFFIX_RE.search(label_b))

        if a_has_paren and not b_has_paren:
            return label_b
        if b_has_paren and not a_has_paren:
            return label_a

        if len(label_a) <= len(label_b):
            return label_a
        return label_b
