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

# Label similarity threshold for sending a pair to LLM evaluation.
# Must be high enough to avoid noise but low enough to catch genuine near-dupes.
LLM_CANDIDATE_THRESHOLD = 0.70


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

        # Phase 3: LLM pair-based evaluation for groups with near-matches
        for group_key, entities in groups.items():
            if len(entities) < 2:
                continue

            pairs = self._find_candidate_pairs(entities)
            if not pairs:
                continue

            try:
                candidates = self._llm_evaluate_pairs(group_key, pairs)
                result.review_candidates.extend(candidates)
            except Exception as e:
                logger.error(
                    f"LLM evaluation failed for group {group_key}: {e}",
                    exc_info=True
                )
                result.errors.append(
                    f"LLM evaluation failed for {group_key[0]} {group_key[1]}: {e}"
                )

        return result

    def merge_entities(self, keep_id: int, merge_id: int) -> Dict[str, Any]:
        """Merge entity merge_id into keep_id, then delete merge_id.

        Delegates property merging to EntityMergeService.merge_entity_properties().
        Returns dict with 'success' bool and 'snapshots' for undo support.
        """
        keep_entity = TemporaryRDFStorage.query.get(keep_id)
        merge_entity = TemporaryRDFStorage.query.get(merge_id)

        if not keep_entity or not merge_entity:
            logger.error(f"Entity not found: keep={keep_id}, merge={merge_id}")
            return {'success': False, 'error': 'Entity not found'}

        if keep_entity.is_published or merge_entity.is_published:
            logger.error("Cannot merge published entities")
            return {'success': False, 'error': 'Cannot merge published entities'}

        # Snapshot both entities before merge for undo support
        keep_snapshot = self._snapshot_entity(keep_entity)
        merge_snapshot = self._snapshot_entity(merge_entity)

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
            return {
                'success': True,
                'snapshots': {
                    'keep': keep_snapshot,
                    'merge': merge_snapshot,
                }
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f"Merge failed: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def unmerge_entities(self, keep_snapshot: Dict, merge_snapshot: Dict) -> bool:
        """Restore both entities to their pre-merge state.

        Restores the kept entity from its snapshot and recreates the deleted entity.
        """
        keep_id = keep_snapshot.get('id')
        keep_entity = TemporaryRDFStorage.query.get(keep_id)

        if not keep_entity:
            logger.error(f"Cannot unmerge: kept entity {keep_id} not found")
            return False

        try:
            # Restore kept entity to pre-merge state
            keep_entity.entity_label = keep_snapshot['entity_label']
            keep_entity.entity_definition = keep_snapshot['entity_definition']
            keep_entity.rdf_json_ld = keep_snapshot['rdf_json_ld']
            keep_entity.property_count = keep_snapshot.get('property_count', 0)
            keep_entity.relationship_count = keep_snapshot.get('relationship_count', 0)

            # Recreate the deleted entity
            restored = TemporaryRDFStorage(
                case_id=merge_snapshot['case_id'],
                extraction_session_id=merge_snapshot['extraction_session_id'],
                extraction_type=merge_snapshot['extraction_type'],
                storage_type=merge_snapshot['storage_type'],
                ontology_target=merge_snapshot.get('ontology_target'),
                entity_label=merge_snapshot['entity_label'],
                entity_type=merge_snapshot.get('entity_type'),
                entity_definition=merge_snapshot.get('entity_definition'),
                entity_uri=merge_snapshot.get('entity_uri'),
                rdf_json_ld=merge_snapshot['rdf_json_ld'],
                extraction_model=merge_snapshot.get('extraction_model'),
                provenance_metadata=merge_snapshot.get('provenance_metadata', {}),
                matched_ontology_uri=merge_snapshot.get('matched_ontology_uri'),
                matched_ontology_label=merge_snapshot.get('matched_ontology_label'),
                match_confidence=merge_snapshot.get('match_confidence'),
                match_method=merge_snapshot.get('match_method'),
                match_reasoning=merge_snapshot.get('match_reasoning'),
                is_selected=merge_snapshot.get('is_selected', True),
                is_published=False,
            )
            db.session.add(restored)
            db.session.commit()

            logger.info(
                f"Unmerged: restored '{merge_snapshot['entity_label']}' "
                f"and reverted '{keep_entity.entity_label}' (id={keep_id})"
            )
            return True

        except Exception as e:
            db.session.rollback()
            logger.error(f"Unmerge failed: {e}", exc_info=True)
            return False

    def _snapshot_entity(self, entity: TemporaryRDFStorage) -> Dict[str, Any]:
        """Capture a full snapshot of an entity for undo support."""
        return {
            'id': entity.id,
            'case_id': entity.case_id,
            'extraction_session_id': entity.extraction_session_id,
            'extraction_type': entity.extraction_type,
            'storage_type': entity.storage_type,
            'ontology_target': entity.ontology_target,
            'entity_label': entity.entity_label,
            'entity_type': entity.entity_type,
            'entity_definition': entity.entity_definition,
            'entity_uri': entity.entity_uri,
            'rdf_json_ld': json.loads(json.dumps(entity.rdf_json_ld or {})),
            'extraction_model': entity.extraction_model,
            'provenance_metadata': json.loads(json.dumps(entity.provenance_metadata or {})),
            'matched_ontology_uri': entity.matched_ontology_uri,
            'matched_ontology_label': entity.matched_ontology_label,
            'match_confidence': float(entity.match_confidence) if entity.match_confidence else None,
            'match_method': entity.match_method,
            'match_reasoning': entity.match_reasoning,
            'is_selected': entity.is_selected,
            'property_count': entity.property_count or 0,
            'relationship_count': entity.relationship_count or 0,
        }

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
                    merge_result = self.merge_entities(keep.id, merge_entity.id)
                    if merge_result.get('success'):
                        merged_count += 1
                    else:
                        result.errors.append(
                            f"Failed to auto-merge '{merge_entity.entity_label}' "
                            f"into '{keep.entity_label}': {merge_result.get('error', '')}"
                        )
                except Exception as e:
                    result.errors.append(str(e))
                    logger.error(f"Auto-merge error: {e}", exc_info=True)

        return merged_count

    # -- Phase 3: LLM pair-based evaluation --

    def _find_candidate_pairs(
        self, entities: List[TemporaryRDFStorage]
    ) -> List[Tuple[TemporaryRDFStorage, TemporaryRDFStorage, float]]:
        """Find all pairs in a group with label similarity >= threshold."""
        pairs = []
        n = len(entities)
        for i in range(n):
            for j in range(i + 1, n):
                sim = self._compute_similarity(
                    entities[i].entity_label or '',
                    entities[j].entity_label or ''
                )
                if sim >= LLM_CANDIDATE_THRESHOLD:
                    pairs.append((entities[i], entities[j], sim))
        return pairs

    def _llm_evaluate_pairs(
        self,
        group_key: Tuple[str, str],
        pairs: List[Tuple[TemporaryRDFStorage, TemporaryRDFStorage, float]]
    ) -> List[ReconciliationCandidate]:
        """Send candidate pairs to Haiku for explicit merge/keep_separate verdicts."""
        extraction_type, storage_type = group_key
        prompt = self._build_pair_eval_prompt(extraction_type, storage_type, pairs)

        try:
            response_json = self._call_llm(prompt)
        except Exception as e:
            logger.error(f"LLM call failed for {group_key}: {e}", exc_info=True)
            raise

        # Parse LLM response into ReconciliationCandidate objects
        candidates = []
        entity_map = {}
        for a, b, _ in pairs:
            entity_map[a.id] = a
            entity_map[b.id] = b

        evaluations = response_json.get('evaluations', [])

        for ev in evaluations:
            pair_ids = ev.get('pair', [])
            verdict = ev.get('verdict', 'keep_separate')
            reason = ev.get('reason', '')

            if len(pair_ids) != 2:
                continue

            a_id, b_id = pair_ids
            if a_id not in entity_map or b_id not in entity_map:
                logger.warning(
                    f"LLM returned invalid pair IDs: {pair_ids}"
                )
                continue

            a = entity_map[a_id]
            b = entity_map[b_id]

            # Map verdict to recommendation
            if verdict == 'merge':
                recommendation = 'merge'
            else:
                recommendation = 'keep_separate'

            candidates.append(ReconciliationCandidate(
                entity_a_id=a.id,
                entity_b_id=b.id,
                entity_a_label=a.entity_label or '',
                entity_b_label=b.entity_label or '',
                similarity=self._compute_similarity(
                    a.entity_label or '', b.entity_label or ''
                ),
                same_concept_type=True,
                recommendation=recommendation,
                llm_reason=reason,
                entity_a_context=self._get_entity_context(a),
                entity_b_context=self._get_entity_context(b),
            ))

        # If LLM missed any pairs, add them with no recommendation
        evaluated_pairs = {
            (ev.get('pair', [None, None])[0], ev.get('pair', [None, None])[1])
            for ev in evaluations if len(ev.get('pair', [])) == 2
        }
        for a, b, sim in pairs:
            if (a.id, b.id) not in evaluated_pairs and (b.id, a.id) not in evaluated_pairs:
                candidates.append(ReconciliationCandidate(
                    entity_a_id=a.id,
                    entity_b_id=b.id,
                    entity_a_label=a.entity_label or '',
                    entity_b_label=b.entity_label or '',
                    similarity=sim,
                    same_concept_type=True,
                    recommendation='review',
                    llm_reason='(LLM did not evaluate this pair)',
                    entity_a_context=self._get_entity_context(a),
                    entity_b_context=self._get_entity_context(b),
                ))

        return candidates

    def _build_pair_eval_prompt(
        self,
        extraction_type: str,
        storage_type: str,
        pairs: List[Tuple[TemporaryRDFStorage, TemporaryRDFStorage, float]]
    ) -> str:
        """Build LLM prompt for per-pair duplicate evaluation."""
        type_label = extraction_type.replace('_', ' ').title()
        storage_label = storage_type

        # Concept category definitions
        concept_defs = {
            'Roles': 'Professional roles and role-bearers (e.g., "Engineer A", "Structural Design Engineer"). Different roles of the same person are DISTINCT.',
            'States': 'States of affairs or conditions (e.g., "Competence Failure", "Design Deficiency"). Different states are DISTINCT even if related.',
            'Resources': 'Resources, standards, or references (e.g., "BER Case 85-3", "Building Code Section 4.2"). Different references are DISTINCT.',
            'Principles': 'Ethical principles or values (e.g., "Public Safety", "Professional Integrity"). Different principles are DISTINCT.',
            'Obligations': 'Professional duties or requirements (e.g., "Competence Maintenance Obligation", "Safety Reporting Obligation"). Different obligations are DISTINCT.',
            'Capabilities': 'Professional competencies or capacities (e.g., "Structural Analysis Capability", "Code Compliance Capability"). Different capabilities are DISTINCT.',
            'Constraints': 'Limitations or restrictions (e.g., "Budget Constraint", "Time Constraint"). Different constraints are DISTINCT.',
            'Actions': 'Actions performed by agents. Different actions are DISTINCT.',
            'Events': 'Events in the case timeline. Different events are DISTINCT.',
        }
        concept_context = concept_defs.get(type_label, '')
        concept_line = f'\nCategory: {concept_context}\n' if concept_context else ''

        # Build pair descriptions
        pair_lines = []
        for idx, (a, b, sim) in enumerate(pairs, 1):
            rdf_a = a.rdf_json_ld or {}
            rdf_b = b.rdf_json_ld or {}
            def_a = (a.entity_definition or rdf_a.get('definition', '') or '')[:250]
            def_b = (b.entity_definition or rdf_b.get('definition', '') or '')[:250]
            sec_a = rdf_a.get('source_section', rdf_a.get('section_type', ''))
            sec_b = rdf_b.get('source_section', rdf_b.get('section_type', ''))

            line = f'Pair {idx}: [ID: {a.id}] "{a.entity_label or ""}"'
            if sec_a:
                line += f' (source: {sec_a})'
            line += f'\n     vs [ID: {b.id}] "{b.entity_label or ""}"'
            if sec_b:
                line += f' (source: {sec_b})'
            if def_a:
                line += f'\n  A: "{def_a}"'
            if def_b:
                line += f'\n  B: "{def_b}"'
            pair_lines.append(line)

        pairs_text = '\n\n'.join(pair_lines)

        return f"""Evaluate each candidate pair for potential duplication among entities extracted from a professional ethics case.

Entity type: {type_label} ({storage_label}){concept_line}

For each pair, determine:
- "merge" if both refer to the SAME specific concept extracted from different document sections (Facts vs Discussion)
- "keep_separate" if they are DISTINCT concepts that should remain as separate entities

{pairs_text}

STRICT RULES -- most pairs should be "keep_separate":
- merge: Same label or trivially rephrased label referring to the exact same specific concept
- keep_separate: Different roles of the same person (e.g., "Engineer A Design Role" vs "Engineer A Safety Role")
- keep_separate: Different BER case references (e.g., "BER 85-3 ..." vs "BER 98-8 ...")
- keep_separate: Related but distinct concepts (e.g., "Safety Obligation" vs "Competence Obligation")
- keep_separate: Different aspects or facets of a broader topic
- keep_separate: General vs specific versions (e.g., "Safety Constraint" vs "Structural Safety Constraint")
- When in doubt, use "keep_separate"

Return ONLY valid JSON:
{{"evaluations": [{{"pair": [id_a, id_b], "verdict": "merge"|"keep_separate", "reason": "brief explanation"}}]}}"""

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
            max_tokens=4096,
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
