"""
Entity Reconciliation Service

Three-phase deduplication of entities extracted across Steps 1-3:

Phase 1: Pre-filter -- group by (extraction_type, storage_type), skip temporal dynamics.
Phase 2: Exact-match auto-merge -- identical normalized labels within a group.
Phase 3: LLM semantic evaluation -- Haiku batch dedup for groups with near-matches.

Two modes:
- reconcile_auto(): batch processing -- exact-match merges + LLM auto-merge, no review
- reconcile_with_review(): interactive -- exact-match merges, LLM candidates for review

Merge-stage guards (the case 24-1 / ProEthica case 8 review, 2026-10):
- A class row the matcher already linked to an existing ontology class is canonical and is
  never relabeled (canonicalize_labels skips it, L1).
- A canonicalization decision is vetoed when its target differs from the row's matched class,
  when a GENERALIZE lands on a strict specialization or on a class the reference sheet never
  offered, when the target IRI is held by another class row the auto merge cannot fold, when the
  target is an extended-store IRI carrying a different definition, or when a role would cross
  the professional/participant axis. Every veto is recorded under
  provenance_metadata['canonicalization'] with a reason (L2).
- The exact-match auto merge groups by entity_uri as well as by normalized label, refuses to
  fold two rows whose matched classes differ, and reports the merged pairs (L3).
- The class-rename map never repoints an individual whose own match decision names an existing
  class: the type of such an individual is its matched_uri (L4).
- Two individuals of one principle class, or two constraints of one class and one constrained
  entity with near-identical statements, are returned as review candidates, never merged (L5).
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
from app.services.entity.entity_merge_service import EntityMergeService
from app.services.extraction.entity_matcher import HIGH_BAND_MIN

logger = logging.getLogger(__name__)

# Pattern to strip trailing parenthetical qualifiers like "(Present Case)"
PAREN_SUFFIX_RE = re.compile(r'\s*\([^)]*\)\s*$')

# Extraction types excluded from reconciliation (different structure, no URIs)
SKIP_EXTRACTION_TYPES = {'temporal_dynamics_enhanced', 'temporal_dynamics'}

# Label similarity threshold for sending a pair to LLM evaluation.
# Must be high enough to avoid noise but low enough to catch genuine near-dupes.
LLM_CANDIDATE_THRESHOLD = 0.70

# The matcher's auto-link band floor (entity_matcher.HIGH_BAND_MIN, 0.85): a class row whose
# matched_ontology_uri carries at least this confidence is linked to an existing class and is
# already canonical, whatever the canonicalization model proposes (L1).
MATCH_LINK_THRESHOLD = HIGH_BAND_MIN

# Minimum content-word Jaccard overlap between a row's definition and the definition the
# extended store already attaches to the target IRI. Below it the two are different concepts
# and the canonicalization would put both on one IRI (L2, the RegulatoryComplianceObligation
# collision). Generous on purpose: paraphrases of one concept share well over a fifth of their
# content words, unrelated duties of one category share almost none.
EXTENDED_DEFINITION_OVERLAP_MIN = 0.20

# Two constraint individuals of one class and one constrained entity whose statements reach
# this SequenceMatcher ratio are surfaced as a review candidate (L5), never auto-merged.
CONSTRAINT_STATEMENT_SIMILARITY_MIN = 0.60

# Content words ignored by the definition-overlap measure.
_DEFINITION_STOPWORDS = frozenset("""
the and for with that this from into which when where who whose are was were been being has
have had not but than then their they them its his her our you your any all each such here
there these those also over under upon about after before between within without through
during while may must shall should can could will would one per via onto out off
""".split())
_DEFINITION_WORD_RE = re.compile(r"[a-z]{3,}")


def _local_name(ref: Optional[str]) -> str:
    """Bare local name of a URI, prefixed name, or label."""
    s = str(ref or '').strip()
    if '#' in s:
        s = s.rsplit('#', 1)[-1]
    elif '/' in s:
        s = s.rsplit('/', 1)[-1]
    elif ':' in s and ' ' not in s:
        s = s.rsplit(':', 1)[-1]
    return s


def _norm_class_name(ref: Optional[str]) -> str:
    """Local name reduced to lowercase alphanumerics, so a label ("Disclosure Capability"), a
    minted local name ("DisclosureCapability") and a full IRI compare equal."""
    return re.sub(r'[^a-z0-9]', '', _local_name(ref).lower())


def _same_class(ref_a: Optional[str], ref_b: Optional[str]) -> bool:
    """Whether two class references name one class: equal IRIs, or equal normalized local names."""
    if not ref_a or not ref_b:
        return False
    if str(ref_a).strip() == str(ref_b).strip():
        return True
    return _norm_class_name(ref_a) == _norm_class_name(ref_b)


def _definition_overlap(text_a: Optional[str], text_b: Optional[str]) -> float:
    """Jaccard overlap of the content words of two definitions (0.0 to 1.0)."""
    words_a = set(_DEFINITION_WORD_RE.findall((text_a or '').lower())) - _DEFINITION_STOPWORDS
    words_b = set(_DEFINITION_WORD_RE.findall((text_b or '').lower())) - _DEFINITION_STOPWORDS
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def _load_merge_pair_eval_template():
    """Load the editable 'merge_pair_eval' prompt template (prompt editor -> Shared prompts ->
    Entity passes -> Reconciliation (pair-merge)). Separate function so a test can inject a stub
    without a DB / app context. Raises (no fallback) if unseeded."""
    from app.models.extraction_prompt_template import ExtractionPromptTemplate
    tmpl = ExtractionPromptTemplate.get_active_template(0, 'merge_pair_eval')
    if tmpl is None:
        raise RuntimeError(
            "No 'merge_pair_eval' prompt template in extraction_prompt_templates. "
            "Seed it: docs-internal/scripts/seed_merge_pair_eval_template.py")
    return tmpl


def _load_merge_canonicalize_template():
    """Load the editable 'merge_canonicalize' prompt template (prompt editor -> Shared prompts ->
    Entity passes -> Canonicalization (de-compounding)). Separate function so a test can inject a stub
    without a DB / app context. Raises (no fallback) if unseeded. The reference-sheet block stays a
    rendered {{ reuse_block }} variable fed from source at render time (canonical-binding rule)."""
    from app.models.extraction_prompt_template import ExtractionPromptTemplate
    tmpl = ExtractionPromptTemplate.get_active_template(0, 'merge_canonicalize')
    if tmpl is None:
        raise RuntimeError(
            "No 'merge_canonicalize' prompt template in extraction_prompt_templates. "
            "Seed it: docs-internal/scripts/seed_merge_canonicalize_template.py")
    return tmpl


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
    # Deterministic rule that raised the candidate ('' for LLM pair verdicts):
    # 'principle_per_value' or 'constraint_statement_similarity' (L5).
    rule: str = ''


@dataclass
class ReconciliationResult:
    """Result of reconciliation for a case."""
    case_id: int
    auto_merged: int = 0
    review_candidates: List[ReconciliationCandidate] = field(default_factory=list)
    skipped: int = 0
    errors: List[str] = field(default_factory=list)
    # Exact-match auto merges as pairs (merged id + old label, kept id + surviving label,
    # the grouping basis) and the folds refused because the matched classes differ (L3).
    merged_pairs: List[Dict[str, Any]] = field(default_factory=list)
    merge_refusals: List[Dict[str, Any]] = field(default_factory=list)


class EntityReconciliationService:
    """Three-phase entity deduplication for a case."""

    def __init__(self):
        self._merge_service = EntityMergeService()

    def reconcile_auto(self, case_id: int) -> ReconciliationResult:
        """Batch mode: exact-match merges, no LLM. The only review candidates are the
        deterministic L5 detections (per-value principle duplicates, near-identical
        constraints), which are reported and never merged."""
        result = ReconciliationResult(case_id=case_id)
        groups = self._group_entities(case_id)

        for group_key, entities in groups.items():
            merged = self._auto_merge_exact_matches(entities, result)
            result.auto_merged += merged

        # Re-fetch after merges (entities were deleted) for the rule-based detection.
        groups = self._group_entities(case_id)
        result.review_candidates.extend(self._detect_review_candidates(groups))

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

        # Rule-based review candidates (L5): reported alongside the LLM verdicts, never merged.
        result.review_candidates.extend(self._detect_review_candidates(groups))

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

    def _exact_match_groups(
        self, entities: List[TemporaryRDFStorage]
    ) -> List[List[TemporaryRDFStorage]]:
        """Partition a group's rows into fold sets: rows connected by an identical normalized
        label OR an identical entity_uri belong together (L3). Two rows carrying one IRI are
        one node in the committed graph whatever their labels say ("disclosurecapability" and
        "Disclosure Capability" on the case-8 DisclosureCapability IRI), so label equality
        alone is not the merge key. Preserves input order inside and across sets."""
        parent = list(range(len(entities)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i: int, j: int) -> None:
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[max(ri, rj)] = min(ri, rj)

        first_by_label: Dict[str, int] = {}
        first_by_uri: Dict[str, int] = {}
        for i, e in enumerate(entities):
            norm = self._normalize_label(e.entity_label or '')
            if norm:
                if norm in first_by_label:
                    union(i, first_by_label[norm])
                else:
                    first_by_label[norm] = i
            uri = (e.entity_uri or '').strip()
            if uri:
                if uri in first_by_uri:
                    union(i, first_by_uri[uri])
                else:
                    first_by_uri[uri] = i

        sets: Dict[int, List[TemporaryRDFStorage]] = {}
        for i, e in enumerate(entities):
            sets.setdefault(find(i), []).append(e)
        return [members for _, members in sorted(sets.items())]

    @staticmethod
    def _merge_refusal(keep, other) -> Optional[str]:
        """Why two rows of one group must not be folded, or None when they may be. Two rows the
        matcher linked to DIFFERENT existing classes are two concepts even when their labels
        coincide (case 8: ConfirmedRiskFindingState folded into UnquantifiedRiskState)."""
        if (keep.extraction_type, keep.storage_type) != (other.extraction_type, other.storage_type):
            return 'different_group'
        keep_match = getattr(keep, 'matched_ontology_uri', None)
        other_match = getattr(other, 'matched_ontology_uri', None)
        if keep_match and other_match and not _same_class(keep_match, other_match):
            return 'matched_ontology_uri_differs'
        return None

    def _auto_merge_exact_matches(
        self, entities: List[TemporaryRDFStorage], result: ReconciliationResult
    ) -> int:
        """Merge rows that share a normalized label or an entity_uri within a group, keeping the
        first row of each fold set. A fold whose two rows are matched to different ontology
        classes is refused and reported. Every merge is reported as a pair (merged id and
        label, kept id and surviving label, basis) on ``result`` (L3)."""
        merged_count = 0
        for group in self._exact_match_groups(entities):
            if len(group) < 2:
                continue

            # Keep first, merge rest into it
            keep = group[0]
            keep_norm = self._normalize_label(keep.entity_label or '')
            keep_uri = (keep.entity_uri or '').strip()
            for merge_entity in group[1:]:
                refusal = self._merge_refusal(keep, merge_entity)
                if refusal:
                    result.merge_refusals.append({
                        'kept_id': keep.id, 'kept_label': keep.entity_label,
                        'kept_matched_uri': getattr(keep, 'matched_ontology_uri', None),
                        'refused_id': merge_entity.id, 'refused_label': merge_entity.entity_label,
                        'refused_matched_uri': getattr(merge_entity, 'matched_ontology_uri', None),
                        'reason': refusal,
                    })
                    logger.info(
                        "Auto-merge refused: '%s' (id=%s) not folded into '%s' (id=%s): %s",
                        merge_entity.entity_label, merge_entity.id,
                        keep.entity_label, keep.id, refusal,
                    )
                    continue
                same_label = bool(keep_norm) and (
                    self._normalize_label(merge_entity.entity_label or '') == keep_norm)
                same_uri = bool(keep_uri) and (
                    (merge_entity.entity_uri or '').strip() == keep_uri)
                basis = ('label+entity_uri' if same_label and same_uri
                         else 'entity_uri' if same_uri else 'label')
                old_label = merge_entity.entity_label
                try:
                    merge_result = self.merge_entities(keep.id, merge_entity.id)
                    if merge_result.get('success'):
                        merged_count += 1
                        result.merged_pairs.append({
                            'merged_id': merge_entity.id, 'merged_label': old_label,
                            'kept_id': keep.id, 'surviving_label': keep.entity_label,
                            'basis': basis,
                        })
                    else:
                        result.errors.append(
                            f"Failed to auto-merge '{old_label}' "
                            f"into '{keep.entity_label}': {merge_result.get('error', '')}"
                        )
                except Exception as e:
                    result.errors.append(str(e))
                    logger.error(f"Auto-merge error: {e}", exc_info=True)

        return merged_count

    # -- Rule-based review candidates (L5) --

    @staticmethod
    def _individual_class_ref(entity) -> str:
        """Normalized class reference of an individual row: its first rdf:type, else the
        concept-specific class field (principleClass, constraintClass, ...) in properties."""
        rdf = entity.rdf_json_ld or {}
        types = rdf.get('types')
        if isinstance(types, list) and types:
            return _norm_class_name(types[0])
        props = rdf.get('properties') or {}
        for key in ('principleClass', 'constraintClass', 'obligationClass', 'roleClass',
                    'stateClass', 'resourceClass', 'capabilityClass'):
            val = props.get(key)
            if val:
                return _norm_class_name(val[0] if isinstance(val, list) else val)
        return ''

    @staticmethod
    def _first_property(entity, *keys) -> str:
        """First non-empty value among the given rdf_json_ld property keys, as a string."""
        props = (entity.rdf_json_ld or {}).get('properties') or {}
        for key in keys:
            val = props.get(key)
            if val:
                val = val[0] if isinstance(val, list) else val
                if val:
                    return str(val)
        return ''

    def _detect_review_candidates(
        self, groups: Dict[Tuple[str, str], List[TemporaryRDFStorage]]
    ) -> List[ReconciliationCandidate]:
        """Deterministic review candidates that are never auto-merged (L5).

        Principles: the principles prompt states a per-value rule (at most one principle
        individual per distinct value per case), so two individuals of one principle class are
        a review candidate. Constraints: two constraint individuals of one class and one
        constrainedEntity whose statements reach CONSTRAINT_STATEMENT_SIMILARITY_MIN are a
        review candidate. Each candidate carries the rule name and a reason.
        """
        candidates: List[ReconciliationCandidate] = []

        def _pair(a, b, sim, rule, reason):
            return ReconciliationCandidate(
                entity_a_id=a.id, entity_b_id=b.id,
                entity_a_label=a.entity_label or '', entity_b_label=b.entity_label or '',
                similarity=sim, same_concept_type=True, recommendation='review',
                llm_reason=reason, rule=rule,
                entity_a_context=self._get_entity_context(a),
                entity_b_context=self._get_entity_context(b),
            )

        by_class: Dict[str, List[TemporaryRDFStorage]] = {}
        for e in groups.get(('principles', 'individual'), []) or []:
            ref = self._individual_class_ref(e)
            if ref:
                by_class.setdefault(ref, []).append(e)
        for ref, members in by_class.items():
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    a, b = members[i], members[j]
                    candidates.append(_pair(
                        a, b,
                        self._compute_similarity(a.entity_label or '', b.entity_label or ''),
                        'principle_per_value',
                        f"two principle individuals of one class ({ref}) in one case. The "
                        f"principles prompt yields at most one individual per value per case, so "
                        f"these are one value recorded twice or one class covering two values",
                    ))

        by_key: Dict[Tuple[str, str], List[TemporaryRDFStorage]] = {}
        for e in groups.get(('constraints', 'individual'), []) or []:
            ref = self._individual_class_ref(e)
            who = self._normalize_label(
                self._first_property(e, 'constrainedEntity', 'constrained_entity'))
            if ref and who:
                by_key.setdefault((ref, who), []).append(e)
        for (ref, who), members in by_key.items():
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    a, b = members[i], members[j]
                    stmt_a = (self._first_property(a, 'constraintStatement', 'constraint_statement')
                              or a.entity_definition
                              or (a.rdf_json_ld or {}).get('definition', '') or '')
                    stmt_b = (self._first_property(b, 'constraintStatement', 'constraint_statement')
                              or b.entity_definition
                              or (b.rdf_json_ld or {}).get('definition', '') or '')
                    if not stmt_a or not stmt_b:
                        continue
                    sim = SequenceMatcher(None, self._normalize_label(stmt_a),
                                          self._normalize_label(stmt_b)).ratio()
                    if sim >= CONSTRAINT_STATEMENT_SIMILARITY_MIN:
                        candidates.append(_pair(
                            a, b, sim, 'constraint_statement_similarity',
                            f"two constraints of one class ({ref}) and one constrained entity "
                            f"({who}) with statements at similarity {sim:.2f} "
                            f"(threshold {CONSTRAINT_STATEMENT_SIMILARITY_MIN:.2f})",
                        ))

        return candidates

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

        return _load_merge_pair_eval_template().render(
            type_label=type_label,
            storage_label=storage_label,
            concept_line=concept_line,
            pairs_text=pairs_text,
        )

    # -- Phase 4: LLM label canonicalization (de-compounding) --

    def _group_for_canonicalization(
        self, case_id: int, include_published: bool,
        storage_types: Tuple[str, ...],
    ) -> Dict[Tuple[str, str], List[TemporaryRDFStorage]]:
        """Group a case's entities by (extraction_type, storage_type) for canonicalization.

        Unlike _group_entities (dedup), this scopes to the given storage_types and can
        include already-published rows (for dry-run calibration). Skips temporal types.
        """
        q = TemporaryRDFStorage.query.filter(
            TemporaryRDFStorage.case_id == case_id,
            TemporaryRDFStorage.storage_type.in_(list(storage_types)),
        )
        if not include_published:
            q = q.filter(TemporaryRDFStorage.is_published == False)  # noqa: E712

        groups: Dict[Tuple[str, str], List[TemporaryRDFStorage]] = {}
        for e in q.all():
            if e.extraction_type in SKIP_EXTRACTION_TYPES:
                continue
            groups.setdefault((e.extraction_type, e.storage_type), []).append(e)
        return groups

    def canonicalize_labels(
        self, case_id: int, dry_run: bool = False,
        include_published: bool = False,
        storage_types: Tuple[str, ...] = ('class',),
    ) -> Dict[str, Any]:
        """LLM round-trip label canonicalization over a case's extracted entities.

        Strips case-specific context the extractor baked into CLASS identity -- a particular
        tool/technology, a named actor, a material, a jurisdiction, a code-section number --
        which the curated reference sheet cannot pre-enumerate. This is the open-ended
        generalization of the deterministic sheet folds: per component group the fast model
        sees every extracted label+definition alongside the sheet's canonical classes and the
        global hygiene rules (reference_sheet.reuse_block_for_concept), and returns for each
        entity one of REUSE (an existing canonical class), GENERALIZE (a tool/actor-neutral
        class, with the stripped context externalized), or KEEP. Rewrites entity_label and
        records the original label + externalized context under
        provenance_metadata['canonicalization'] so nothing is lost and the commit path can
        materialize the context as a State / otherAttribute.

        Scoped to ``storage_types`` (default class-level only -- class identity is what must
        be reusable; individual-level labels legitimately carry the actor/context and are
        handled by the deferred individual-layer hygiene). ``include_published`` re-processes
        already-published rows (used for dry-run calibration over committed extractions).

        dry_run=True computes and returns the proposed changes without writing.
        Fails loud (no swallow) -- this is a dev-time calibration pass.

        Merge-stage guards (case 8 review). A row the matcher already linked to an existing
        class (``_matched_class``) is canonical: it is left out of the prompt and reported under
        ``kept_matched`` (L1). For the rows that are canonicalized, ``_canonicalization_veto``
        rejects a target that differs from the row's matched class, a GENERALIZE onto a strict
        specialization or onto a class the reference sheet never offered, a target IRI another
        class row holds unless the auto merge can fold the two, an extended-store IRI carrying a
        different definition, and a role target on the other side of the professional/participant
        axis. Every rejection is reported under ``rejected`` and written to
        provenance_metadata['canonicalization'] with its reason (L2). The rename map never
        repoints an individual whose own match decision names an existing class (L4).
        """
        from app.services.extraction.reference_sheet import reuse_block_for_concept, get_sheet
        from app.services.extraction.core_vocab import CONCEPT_TYPE_TO_CORE_CATEGORY
        from app.services.extraction.category_resolver import resolve_core_category
        from app.services.extraction.entity_matcher import category_compatible
        from app.services.extraction.domain_config import active_domain

        cfg = active_domain()
        groups = self._group_for_canonicalization(case_id, include_published, storage_types)
        # Renaming a class is a graph op: the identity is referenced from the class row's
        # label+IRI AND from every individual's rdf:type (rdf_json_ld['types']). Collect
        # {old_class_uri -> new_class_uri} as changes apply, then repoint the individuals so
        # the committed case TTL types them to the canonical class (not the compound).
        rename_map: Dict[str, str] = {}
        summary: Dict[str, Any] = {
            "case_id": case_id, "dry_run": dry_run,
            "groups": 0, "entities": 0, "changed": 0, "individuals_repointed": 0,
            "individuals_protected": 0,
            "by_action": {}, "changes": [], "rejected_cross_category": [],
            "kept_matched": [], "rejected": [],
        }
        # Every class row of the case by its current IRI, maintained as renames apply, so a
        # decision landing on an IRI another row already holds is visible to the veto (L2).
        rows_by_uri: Dict[str, List[TemporaryRDFStorage]] = {}
        for rows in groups.values():
            for e in rows:
                if e.entity_uri:
                    rows_by_uri.setdefault(e.entity_uri, []).append(e)

        for (extraction_type, storage_type), entities in groups.items():
            if not entities:
                continue
            reuse_block = reuse_block_for_concept(extraction_type)
            if not reuse_block:
                continue  # component maps to no sheet category -> nothing to canonicalize against
            entity_category = CONCEPT_TYPE_TO_CORE_CATEGORY.get(extraction_type)
            summary["entities"] += len(entities)

            # L1: a row the matcher linked to an existing class is already canonical. It is
            # neither sent to the model nor relabeled.
            candidates: List[TemporaryRDFStorage] = []
            for e in entities:
                matched = self._matched_class(e)
                if matched:
                    summary["kept_matched"].append({
                        "id": e.id, "type": extraction_type, "label": e.entity_label,
                        "matched_uri": matched, "confidence": self._match_confidence(e),
                    })
                else:
                    candidates.append(e)
            if not candidates:
                continue
            offered = get_sheet().offered_targets(entity_category) if entity_category else None

            prompt = self._build_canonicalize_prompt(extraction_type, reuse_block, candidates)
            response = self._call_llm(prompt)  # fail-loud
            decisions = {
                d.get("id"): d
                for d in response.get("entities", [])
                if isinstance(d, dict) and d.get("id") is not None
            }
            summary["groups"] += 1

            for e in candidates:
                d = decisions.get(e.id)
                if not d:
                    continue
                action = (d.get("action") or "keep").strip().lower()
                summary["by_action"][action] = summary["by_action"].get(action, 0) + 1
                new_label = (d.get("canonical_label") or "").strip()
                old_label = (e.entity_label or "").strip()
                if action not in ("reuse", "generalize") or not new_label or new_label == old_label:
                    continue
                new_uri = cfg.class_iri(new_label)

                # Same-category guardrail: the live matcher's consolidated guard in
                # chain-only mode (marker_fallback=False). Rejects only a target that
                # positively resolves to a different core category (e.g. a Constraint
                # folding into an Obligation -- the deterministic sheet's job, not this
                # pass); a novel in-category label the chain cannot place yet is trusted
                # (the prompt keeps the model in category; the commit-time matcher is the
                # deterministic backstop). Single predicate, shared with matching.py.
                if not category_compatible(entity_category, new_label,
                                           chain_resolver=resolve_core_category,
                                           marker_fallback=False):
                    resolved = resolve_core_category(new_label)
                    summary["rejected_cross_category"].append({
                        "id": e.id, "type": extraction_type, "resolved": resolved,
                        "old": e.entity_label, "proposed": new_label,
                    })
                    self._reject_canonicalization(
                        e, summary, d, action, new_label, new_uri, "cross_category",
                        f"target resolves to {resolved}, the row is a {entity_category}",
                        dry_run)
                    continue

                veto = self._canonicalization_veto(
                    e, extraction_type, action, new_label, new_uri, offered, rows_by_uri)
                if veto:
                    code, detail = veto
                    self._reject_canonicalization(
                        e, summary, d, action, new_label, new_uri, code, detail, dry_run)
                    continue

                change = {
                    "id": e.id, "type": extraction_type,
                    "old": e.entity_label, "new": new_label, "action": action,
                    "old_uri": e.entity_uri, "new_uri": new_uri,
                    "externalized": d.get("externalized_context"),
                    "reason": d.get("reason", ""),
                }
                co_holders = [o.id for o in rows_by_uri.get(new_uri, []) if o is not e]
                if co_holders:
                    # Another row holds the target IRI and the auto merge can fold the two
                    # in this same reconcile step (the veto admitted the collision).
                    change["merge_expected_with"] = co_holders
                summary["changes"].append(change)
                summary["changed"] += 1
                if e.entity_uri and e.entity_uri != new_uri:
                    rename_map[e.entity_uri] = new_uri
                    rows_by_uri[e.entity_uri] = [
                        o for o in rows_by_uri.get(e.entity_uri, []) if o is not e]
                    rows_by_uri.setdefault(new_uri, []).append(e)

                if not dry_run:
                    meta = dict(e.provenance_metadata or {})
                    meta["canonicalization"] = {
                        "status": "applied",
                        "original_label": e.entity_label,
                        "original_uri": e.entity_uri,
                        "action": action,
                        "externalized_context": d.get("externalized_context"),
                        "reason": d.get("reason", ""),
                    }
                    e.provenance_metadata = meta
                    e.entity_label = new_label
                    e.entity_uri = new_uri

        # Propagate the class renames to every individual that types to a renamed class.
        summary["individuals_repointed"], summary["individuals_protected"] = (
            self._repoint_individual_types(case_id, rename_map, write=not dry_run))

        if not dry_run and (summary["changed"] or summary["individuals_repointed"]
                            or summary["rejected"]):
            db.session.commit()
        return summary

    # -- Canonicalization guards (L1, L2, L4) --

    @staticmethod
    def _match_confidence(entity) -> Optional[float]:
        """The matcher's confidence for a row, from the column or the stored match decision."""
        conf = getattr(entity, 'match_confidence', None)
        if conf is None:
            conf = ((entity.rdf_json_ld or {}).get('match_decision') or {}).get('confidence')
        try:
            return float(conf) if conf is not None else None
        except (TypeError, ValueError):
            return None

    def _matched_class(self, entity) -> Optional[str]:
        """The existing ontology class a row is linked to when that link makes the row
        canonical (L1): its match decision says matches_existing with a matched_uri, or
        matched_ontology_uri carries at least MATCH_LINK_THRESHOLD. None otherwise."""
        md = (entity.rdf_json_ld or {}).get('match_decision') or {}
        if md.get('matches_existing') and md.get('matched_uri'):
            return str(md['matched_uri'])
        uri = getattr(entity, 'matched_ontology_uri', None)
        if uri:
            conf = self._match_confidence(entity)
            if conf is not None and conf >= MATCH_LINK_THRESHOLD:
                return str(uri)
        return None

    @staticmethod
    def _row_matched_uri(entity) -> Optional[str]:
        """Any matched class recorded on a row, whatever its confidence."""
        uri = getattr(entity, 'matched_ontology_uri', None)
        if uri:
            return str(uri)
        md = (entity.rdf_json_ld or {}).get('match_decision') or {}
        return str(md['matched_uri']) if md.get('matched_uri') else None

    @staticmethod
    def _role_axis_of_row(entity) -> Optional[str]:
        """The professional/participant axis of a role class row: the extraction's own
        roleKind when stated, else the curated axis of its matched class or of its own IRI."""
        from app.services.extraction import category_resolver as _cr
        rdf = entity.rdf_json_ld or {}
        props = rdf.get('properties') or {}
        rk = props.get('roleKind') or props.get('role_kind') or rdf.get('role_kind')
        if isinstance(rk, list):
            rk = rk[0] if rk else None
        rk = str(rk).lower().strip() if rk else None
        if rk in ('professional', 'participant'):
            return rk
        for ref in (getattr(entity, 'matched_ontology_uri', None), entity.entity_uri):
            if ref:
                axis = _cr.resolve_role_axis(ref)
                if axis:
                    return axis
        return None

    def _canonicalization_veto(
        self, entity, extraction_type: str, action: str, new_label: str, new_uri: str,
        offered: Optional[set], rows_by_uri: Dict[str, List[TemporaryRDFStorage]],
    ) -> Optional[Tuple[str, str]]:
        """The (reason, detail) a canonicalization decision is rejected for, or None (L2).

        Order: the matched class is authoritative (a row with any matched_ontology_uri may only
        be relabeled to that class), a GENERALIZE may neither land on a strict specialization of
        the original or matched class nor on a class the reference sheet did not offer, a target
        IRI held by another class row is rejected unless the auto merge can fold the two rows in
        this same step, an extended-store IRI whose definition differs from the row's is a
        collision, and a role may not cross the professional/participant axis.
        """
        from app.services.extraction import category_resolver as _cr

        matched = self._row_matched_uri(entity)
        if matched and not _same_class(new_uri, matched):
            return ('target_differs_from_match',
                    f"row is matched to {_local_name(matched)} "
                    f"(confidence {self._match_confidence(entity)}), target "
                    f"{_local_name(new_uri)} is a different class")

        if action == 'generalize':
            # The original class is named by the row's IRI, by its label (minted the same way,
            # but a merged row may carry another IRI) and by its matched class.
            from app.services.extraction.domain_config import sanitize
            bases = (entity.entity_uri, sanitize(entity.entity_label or ''), matched)
            for base in bases:
                if base and _cr.is_strict_subclass(new_uri, base):
                    return ('generalize_to_specialization',
                            f"{_local_name(new_uri)} is a strict rdfs:subClassOf* descendant "
                            f"of {_local_name(base)}")
            if (offered is not None and _norm_class_name(new_label) not in offered
                    and _norm_class_name(new_uri) not in offered):
                return ('generalize_target_not_offered',
                        f"{new_label} is not a class the reference sheet offers for "
                        f"{extraction_type}")

        # A relabel that keeps the IRI changes no graph identity, so the IRI-level checks
        # below do not apply to it.
        same_iri = bool(entity.entity_uri) and _same_class(new_uri, entity.entity_uri)
        if not same_iri:
            for other in rows_by_uri.get(new_uri, []):
                if other is entity:
                    continue
                refusal = self._merge_refusal(entity, other)
                if refusal:
                    return ('entity_uri_collision',
                            f"{_local_name(new_uri)} is held by row {other.id} "
                            f"'{other.entity_label}', which the auto merge cannot fold "
                            f"into this row ({refusal})")
            ext_def = _cr.extended_class_definition(new_uri)
            row_def = (entity.entity_definition
                       or (entity.rdf_json_ld or {}).get('definition') or '')
            if ext_def and row_def:
                overlap = _definition_overlap(row_def, ext_def)
                if overlap < EXTENDED_DEFINITION_OVERLAP_MIN:
                    return ('extended_iri_collision',
                            f"the extended store already defines {_local_name(new_uri)} "
                            f"differently (content-word overlap {overlap:.2f} below "
                            f"{EXTENDED_DEFINITION_OVERLAP_MIN:.2f}): {ext_def[:160]}")

        if extraction_type == 'roles':
            row_axis = self._role_axis_of_row(entity)
            target_axis = _cr.resolve_role_axis(new_uri)
            if row_axis and target_axis and row_axis != target_axis:
                return ('role_axis_conflict',
                        f"the row is a {row_axis} role, {_local_name(new_uri)} is on the "
                        f"{target_axis} side of the ProfessionalRole/ParticipantRole axis")
        return None

    @staticmethod
    def _reject_canonicalization(
        entity, summary: Dict[str, Any], decision: Dict[str, Any], action: str,
        new_label: str, new_uri: str, reason: str, detail: str, dry_run: bool,
    ) -> None:
        """Report a vetoed decision in the summary and, unless dry-run, record it with its
        reason under provenance_metadata['canonicalization'] (L2). The row keeps its label."""
        summary["rejected"].append({
            "id": entity.id, "type": entity.extraction_type,
            "old": entity.entity_label, "proposed": new_label, "proposed_uri": new_uri,
            "action": action, "reason": reason, "detail": detail,
        })
        logger.info(
            "Canonicalization vetoed for '%s' (id=%s) -> '%s': %s (%s)",
            entity.entity_label, entity.id, new_label, reason, detail,
        )
        if dry_run:
            return
        meta = dict(entity.provenance_metadata or {})
        meta["canonicalization"] = {
            "status": "rejected",
            "original_label": entity.entity_label,
            "original_uri": entity.entity_uri,
            "proposed_label": new_label,
            "proposed_uri": new_uri,
            "action": action,
            "externalized_context": decision.get("externalized_context"),
            "reason": reason,
            "detail": detail,
            "model_reason": decision.get("reason", ""),
        }
        entity.provenance_metadata = meta

    @staticmethod
    def _individual_names_existing_class(entity) -> bool:
        """Whether an individual's own match decision names an existing ontology class."""
        md = (entity.rdf_json_ld or {}).get('match_decision') or {}
        if md.get('matches_existing') and md.get('matched_uri'):
            return True
        return bool(getattr(entity, 'matched_ontology_uri', None))

    def _load_individuals(self, case_id: int) -> List[TemporaryRDFStorage]:
        return (TemporaryRDFStorage.query
                .filter_by(case_id=case_id, storage_type='individual').all())

    def _repoint_individual_types(
        self, case_id: int, rename_map: Dict[str, str], write: bool
    ) -> Tuple[int, int]:
        """Rewrite individual rdf:type references (rdf_json_ld['types']) through a
        class-rename map {old_class_uri -> new_class_uri}, so the committed case TTL types
        each individual to the canonical class rather than the original compound. An
        individual whose own match decision names an existing class is never repointed: its
        type is that matched_uri, which the commit honors (L4). Returns (rows changed, rows
        protected), both computed even when write=False, for dry-run."""
        if not rename_map:
            return 0, 0
        changed = 0
        protected = 0
        for e in self._load_individuals(case_id):
            rdf = e.rdf_json_ld or {}
            types = rdf.get('types')
            if not isinstance(types, list) or not types:
                continue
            new_types = [rename_map.get(t, t) for t in types]
            if new_types == types:
                continue
            if self._individual_names_existing_class(e):
                protected += 1
                logger.info(
                    "Rename map not applied to individual '%s' (id=%s): its match decision "
                    "names existing class %s", e.entity_label, e.id,
                    self._row_matched_uri(e))
                continue
            changed += 1
            if write:
                rdf = dict(rdf)
                rdf['types'] = new_types
                e.rdf_json_ld = rdf
        return changed, protected

    def _build_canonicalize_prompt(
        self, extraction_type: str, reuse_block: str,
        entities: List[TemporaryRDFStorage]
    ) -> str:
        """Per-component prompt: reuse / generalize / keep each label, externalizing context."""
        type_label = extraction_type.replace('_', ' ').title()

        lines = []
        for e in entities:
            rdf = e.rdf_json_ld or {}
            defn = (e.entity_definition or rdf.get('definition', '') or '')[:200]
            line = f'[ID: {e.id}] "{e.entity_label or ""}"'
            if defn:
                line += f' -- {defn}'
            lines.append(line)
        entities_text = '\n'.join(lines)

        return _load_merge_canonicalize_template().render(
            type_label=type_label,
            reuse_block=reuse_block,
            entities_text=entities_text,
        )

    def _call_llm(self, prompt: str) -> Dict[str, Any]:
        """Call the fast tier for dedup evaluation."""
        from app.utils.llm_utils import extract_json_from_response

        from app.services.llm.factory import get_tier_provider

        try:
            provider = get_tier_provider("fast")
        except Exception as e:
            raise RuntimeError(f"No LLM provider available for reconciliation: {e}") from e
        model = provider.model

        logger.info(f"Calling {model} for entity reconciliation")

        response = provider.complete(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096, temperature=0, model=model,
        )

        response_text = response.text
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
        """Normalize a label for comparison.

        Routed through the shared ``entity_matcher.normalize_label`` (matcher
        unification 2026-06). The shared normalizer applies the SAME
        lowercase+strip and trailing-parenthetical drop this used to do inline
        (its paren regex is byte-identical to the local PAREN_SUFFIX_RE) and
        additionally collapses internal whitespace runs. Whitespace-collapse is a
        no-op over the corpus -- zero temporary_rdf_storage labels contain
        internal multi-whitespace -- so the auto-mode exact-match merge decision
        is unchanged. Behavior-preserving for both the auto-mode exact merge and
        the review-mode SequenceMatcher path.
        """
        from app.services.extraction.entity_matcher import normalize_label
        return normalize_label(label)

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
