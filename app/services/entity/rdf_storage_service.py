"""
RDF Storage Service

Manages storage of extracted RDF entities with cross-section merge logic.

Extracted from TemporaryRDFStorage model to fix fat-model anti-pattern.
The model retains column definitions and simple ORM queries; this service
owns the business logic for storing and merging extraction results.

Transaction policy: this service does NOT commit. Callers own the
transaction boundary.
"""

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm.attributes import flag_modified

from app.models import db, ExtractionPrompt
from app.models.temporary_rdf_storage import TemporaryRDFStorage

logger = logging.getLogger(__name__)


def store_extraction_results(
    case_id: int,
    extraction_session_id: str,
    extraction_type: str,
    rdf_data: dict,
    extraction_model: str = None,
    provenance_data: dict = None,
) -> List[TemporaryRDFStorage]:
    """
    Store RDF extraction results from the converter.

    Implements cross-section entity merging: when the same entity (e.g., "Engineer K")
    is extracted from both facts and discussion, properties are merged into a single
    record with provenance tracking from each section.

    Does NOT commit -- caller is responsible for db.session.commit().

    Args:
        case_id: The case ID
        extraction_session_id: Unique session identifier
        extraction_type: Type of extraction (roles, states, etc.)
        rdf_data: Dictionary containing classes and individuals from RDF converter
        extraction_model: LLM model used for extraction
        provenance_data: Optional PROV-O provenance metadata

    Returns:
        List of created/updated TemporaryRDFStorage objects
    """
    logger.info(f"store_extraction_results called for {extraction_type} case {case_id}")
    logger.info(
        f"RDF data: {len(rdf_data.get('new_classes', []))} classes, "
        f"{len(rdf_data.get('new_individuals', []))} individuals"
    )

    created_entities = []
    merged_count = 0

    section_type = provenance_data.get('section_type', 'unknown') if provenance_data else 'unknown'

    # Clear uncommitted entities of this extraction_type for this case AND section.
    # Only delete entities from the SAME section_type to preserve entities
    # from other sections (e.g., don't delete facts entities when running discussion).
    same_section_sessions = [
        p.extraction_session_id
        for p in ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type=extraction_type,
            section_type=section_type
        ).all()
        if p.extraction_session_id
    ]

    deleted_count = 0
    if same_section_sessions:
        deleted_count = TemporaryRDFStorage.query.filter(
            TemporaryRDFStorage.case_id == case_id,
            TemporaryRDFStorage.extraction_type == extraction_type,
            TemporaryRDFStorage.is_published == False,
            TemporaryRDFStorage.extraction_session_id.in_(same_section_sessions)
        ).delete(synchronize_session='fetch')

    if deleted_count > 0:
        logger.info(
            f"Cleared {deleted_count} uncommitted {extraction_type} entities "
            f"for case {case_id} section_type={section_type}"
        )

    # Every storage-time merge and every designator-guard refusal is named in the PROV
    # tables at the end of the pass (the case 24-1 review found an individual silently
    # folded into a class row with only a logger line to show for it).
    merge_records = []
    guard_refusals = []

    # Store new classes with merge detection
    for class_info in rdf_data.get('new_classes', []):
        clean_class_info = _clean_json_data(class_info)
        match_decision = class_info.get('match_decision', {})

        trace = {}
        existing = _find_existing_entity(
            case_id, class_info['label'], extraction_type.capitalize(), extraction_session_id,
            definition=class_info.get('definition'), storage_type='class', trace=trace,
        )
        guard_refusals.extend(trace.get('guard_refusals', []))

        if existing:
            _merge_into_existing(existing, clean_class_info, section_type)
            created_entities.append(existing)
            merged_count += 1
            merge_records.append(_merge_record(class_info['label'], 'class', existing, trace))
            logger.info(f"Merged class '{class_info['label']}' from {section_type} into existing entity")
        else:
            clean_class_info['section_sources'] = [section_type]
            if clean_class_info.get('source_text'):
                clean_class_info['source_texts'] = {section_type: clean_class_info['source_text']}

            entity = TemporaryRDFStorage(
                case_id=case_id,
                extraction_session_id=extraction_session_id,
                extraction_type=extraction_type,
                storage_type='class',
                ontology_target='proethica-intermediate',
                entity_label=class_info['label'],
                entity_uri=class_info['uri'],
                entity_type=extraction_type.capitalize(),
                entity_definition=class_info.get('definition', ''),
                rdf_json_ld=clean_class_info,
                extraction_model=extraction_model,
                triple_count=len(class_info.get('properties', {})) + 4,
                property_count=len(class_info.get('properties', {})),
                provenance_metadata=provenance_data or {},
                matched_ontology_uri=match_decision.get('matched_uri'),
                matched_ontology_label=match_decision.get('matched_label'),
                match_confidence=match_decision.get('confidence'),
                match_method='llm' if match_decision.get('matches_existing') else None,
                match_reasoning=match_decision.get('reasoning'),
                is_selected=True
            )
            db.session.add(entity)
            created_entities.append(entity)

    # Store individuals with merge detection
    for indiv_info in rdf_data.get('new_individuals', []):
        clean_indiv_info = _clean_json_data(indiv_info)
        match_decision = indiv_info.get('match_decision', {})

        trace = {}
        existing = _find_existing_entity(
            case_id, indiv_info['label'], extraction_type.capitalize(), extraction_session_id,
            definition=indiv_info.get('definition'), storage_type='individual', trace=trace,
        )
        guard_refusals.extend(trace.get('guard_refusals', []))

        if existing:
            _merge_into_existing(existing, clean_indiv_info, section_type)
            created_entities.append(existing)
            merged_count += 1
            merge_records.append(_merge_record(indiv_info['label'], 'individual', existing, trace))
            logger.info(f"Merged individual '{indiv_info['label']}' from {section_type} into existing entity")
        else:
            clean_indiv_info['section_sources'] = [section_type]
            if clean_indiv_info.get('source_text'):
                clean_indiv_info['source_texts'] = {section_type: clean_indiv_info['source_text']}

            entity = TemporaryRDFStorage(
                case_id=case_id,
                extraction_session_id=extraction_session_id,
                extraction_type=extraction_type,
                storage_type='individual',
                ontology_target=f'proethica-case-{case_id}',
                entity_label=indiv_info['label'],
                entity_uri=indiv_info['uri'],
                entity_type=extraction_type.capitalize(),
                entity_definition=indiv_info.get('definition', ''),
                rdf_json_ld=clean_indiv_info,
                extraction_model=extraction_model,
                triple_count=len(indiv_info.get('properties', {})) + len(indiv_info.get('relationships', [])) + 2,
                property_count=len(indiv_info.get('properties', {})),
                relationship_count=len(indiv_info.get('relationships', [])),
                provenance_metadata=provenance_data or {},
                matched_ontology_uri=match_decision.get('matched_uri'),
                matched_ontology_label=match_decision.get('matched_label'),
                match_confidence=match_decision.get('confidence'),
                match_method='llm' if match_decision.get('matches_existing') else None,
                match_reasoning=match_decision.get('reasoning'),
                is_selected=True
            )
            db.session.add(entity)
            created_entities.append(entity)

    logger.info(f"Stored {len(created_entities)} {extraction_type} entities ({merged_count} merged from other sections)")

    if merge_records or guard_refusals:
        _record_storage_provenance(
            case_id, extraction_session_id, extraction_type, section_type,
            merge_records, guard_refusals,
        )
    return created_entities


def storage_summary(
    case_id: int, extraction_session_id: str, extraction_type: str,
    extracted_classes: int, extracted_individuals: int,
) -> dict:
    """The results_summary for an extraction prompt, computed AFTER storage from the rows the
    session actually stored. ``classes``/``individuals`` are the extracted counts, ``stored_*``
    the rows created under this session, and ``merged_into_existing`` the difference: entities
    folded into a row from another pass (exact label or semantic dedup) instead of becoming a
    row of their own. The provenance card can then explain an extracted-versus-stored gap
    instead of showing two numbers that disagree."""
    rows = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        TemporaryRDFStorage.extraction_session_id == extraction_session_id,
        TemporaryRDFStorage.extraction_type == extraction_type,
    ).all()
    stored_classes = sum(1 for r in rows if r.storage_type == 'class')
    stored_individuals = sum(1 for r in rows if r.storage_type == 'individual')
    return {
        'classes': extracted_classes,
        'individuals': extracted_individuals,
        'stored_classes': stored_classes,
        'stored_individuals': stored_individuals,
        'merged_into_existing': max(
            0, extracted_classes + extracted_individuals - stored_classes - stored_individuals),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

from functools import lru_cache

_DEDUP_THRESHOLD = 0.88  # conservative cosine for cross-pass semantic merge (precision over recall)


def _embedding_service():
    """Lazy singleton sentence-transformer service (loads the model once)."""
    global _EMB_SVC
    try:
        return _EMB_SVC
    except NameError:
        from app.services.embedding.embedding_service import EmbeddingService
        _EMB_SVC = EmbeddingService()
        return _EMB_SVC


@lru_cache(maxsize=4096)
def _embed_text(text: str) -> tuple:
    """Cached embedding (a hashable tuple) for an entity's (label + definition) text."""
    return tuple(_embedding_service().get_embedding(text))


def _entity_text(label, definition) -> str:
    label = (label or '').strip()
    definition = (definition or '').strip()
    return f"{label}: {definition}" if definition else label


# Designators are textual identities: two labels carrying DIFFERENT case
# numbers ("BER Case 62-21" vs "BER Case 62-7") or provision codes ("II.3.a"
# vs "III.9.a") denote different documents no matter how close their
# embeddings sit -- citation strings differ by a couple of characters, so
# cosine runs ~0.99 between distinct citations (batch-2 review: the dedup
# collapsed two of case 143's four cited precedents into a third). The guard
# also refuses to merge a designator-bearing label with a designator-free one:
# citation identity is textual, and over-splitting stays reviewable where
# silent fusion does not.
import re as _re_desig

_DESIGNATOR_RE = _re_desig.compile(r"\b\d{2}-\d{1,2}\b|\b[IVX]+\.\d+(?:\.[a-z])?\b")


def _label_designators(label) -> frozenset:
    return frozenset(m.group(0).upper() for m in _DESIGNATOR_RE.finditer(label or ""))


def _find_semantic_match(
    case_id: int, label: str, definition, entity_type: str,
    threshold: float = _DEDUP_THRESHOLD,
    storage_type: Optional[str] = None,
    trace: Optional[dict] = None,
) -> Optional[TemporaryRDFStorage]:
    """The best existing same-case, same-type, same-storage-type, unpublished entity whose
    (label+definition) embedding cosine to the new entity is >= threshold, else None. Catches the
    same concept paraphrased across the facts and discussion passes that the exact-label merge
    misses (the over-split problem). The high threshold plus same-type scoping favors leaving a
    duplicate over fusing two genuinely distinct concepts; survivors stay deletable in review.
    Labels whose citation designators differ are NEVER merged (_DESIGNATOR_RE).

    ``storage_type`` ('class' | 'individual') scopes the candidates: a class row never absorbs an
    individual and an individual never absorbs a class row. Without it the role individual
    "Community Affected Public" (case 24-1, facts pass) matched the CLASS row "Affected Community"
    at cos 0.893 and vanished into it. ``trace``, when given, receives ``method``/``cosine`` for a
    match and ``guard_refusals`` (candidates above the threshold kept apart by the designator
    guard, with the candidate row id) so the caller can record them in provenance.

    Best-effort: any embedding failure returns None (no merge) and never blocks storage."""
    try:
        from app.services.embedding.similarity_utils import cosine_similarity_list
        new_emb = list(_embed_text(_entity_text(label, definition)))
        new_designators = _label_designators(label)
        clauses = [
            TemporaryRDFStorage.case_id == case_id,
            TemporaryRDFStorage.entity_type == entity_type,
            TemporaryRDFStorage.is_published == False,
        ]
        if storage_type:
            clauses.append(TemporaryRDFStorage.storage_type == storage_type)
        candidates = TemporaryRDFStorage.query.filter(*clauses).all()
        best, best_sim = None, threshold
        for cand in candidates:
            if (cand.entity_label or '') == (label or ''):
                continue  # exact-label is handled before this fallback
            if storage_type and cand.storage_type != storage_type:
                continue  # never fuse a class row with an individual (or the reverse)
            cand_designators = _label_designators(cand.entity_label)
            if (new_designators or cand_designators) and new_designators != cand_designators:
                # Different citation identities; never fuse. When tracing, name the pair the
                # guard kept apart although the cosine would have merged it.
                if trace is not None:
                    sim = cosine_similarity_list(
                        new_emb,
                        list(_embed_text(_entity_text(cand.entity_label, cand.entity_definition))))
                    if sim >= threshold:
                        trace.setdefault('guard_refusals', []).append({
                            'label': label,
                            'kept_separate_from': cand.entity_label,
                            'kept_separate_from_id': cand.id,
                            'cosine': round(sim, 3),
                        })
                continue
            sim = cosine_similarity_list(
                new_emb, list(_embed_text(_entity_text(cand.entity_label, cand.entity_definition))))
            if sim >= best_sim:
                best, best_sim = cand, sim
        if best is not None:
            logger.info("semantic dedup: '%s' ~ '%s' (cos=%.3f) -> merge",
                        label, best.entity_label, best_sim)
            if trace is not None:
                trace['method'] = 'semantic'
                trace['cosine'] = round(best_sim, 3)
        return best
    except Exception as e:
        logger.debug("semantic dedup skipped for '%s': %s", label, e)
        return None


def _find_existing_entity(
    case_id: int, entity_label: str, entity_type: str, current_session_id: str,
    definition=None,
    storage_type: Optional[str] = None,
    trace: Optional[dict] = None,
) -> Optional[TemporaryRDFStorage]:
    """Find an existing uncommitted entity to merge into: exact label first, then a conservative
    cross-pass semantic match (the same concept paraphrased between the facts and discussion passes).
    Both lookups are scoped by ``storage_type`` when given, so a class row and an individual never
    merge into each other. ``trace`` (see _find_semantic_match) names how the match was made."""
    clauses = [
        TemporaryRDFStorage.case_id == case_id,
        TemporaryRDFStorage.entity_label == entity_label,
        TemporaryRDFStorage.entity_type == entity_type,
        TemporaryRDFStorage.is_published == False,
    ]
    if storage_type:
        clauses.append(TemporaryRDFStorage.storage_type == storage_type)
    exact = TemporaryRDFStorage.query.filter(*clauses).first()
    if exact:
        if trace is not None:
            trace['method'] = 'exact_label'
        return exact
    return _find_semantic_match(
        case_id, entity_label, definition, entity_type,
        storage_type=storage_type, trace=trace,
    )


def _merge_record(label: str, storage_type: str, existing: TemporaryRDFStorage, trace: dict) -> dict:
    """One named storage-time merge: the incoming label, the surviving row, and how they matched."""
    return {
        'label': label,
        'storage_type': storage_type,
        'into_label': existing.entity_label,
        'into_row': existing,  # resolved to into_id after the flush that assigns ids
        'method': trace.get('method', 'exact_label'),
        'cosine': trace.get('cosine'),
    }


def _record_storage_provenance(
    case_id: int, extraction_session_id: str, extraction_type: str, section_type: str,
    merge_records: list, guard_refusals: list,
) -> None:
    """Write the storage-time dedup decisions of one pass to the PROV tables, the way the
    individual-type and precedent filters already record their drops: one ``merge`` activity
    naming every merged label with the surviving row id, and one ``filter`` activity naming
    every pair the citation-designator guard kept apart. Best-effort: never fails storage."""
    try:
        from app.services.provenance_service import get_provenance_service
        db.session.flush()  # rows created in this pass need their ids
        plan_base = {'concept_type': extraction_type, 'section': section_type}
        prov = get_provenance_service()
        if merge_records:
            merges = [{
                'label': m['label'],
                'storage_type': m['storage_type'],
                'into_label': m['into_label'],
                'into_id': m['into_row'].id,
                'into_uri': m['into_row'].entity_uri,
                'method': m['method'],
                'cosine': m['cosine'],
            } for m in merge_records]
            prov.track_pass(
                activity_type='merge', activity_name='storage_dedup_merge',
                case_id=case_id, session_id=extraction_session_id,
                agent_type='extraction_service', agent_name='rdf_storage_service',
                execution_plan={
                    **plan_base,
                    'rule': 'merge an entity into the existing same-case, same-type, '
                            'same-storage-type row: exact label first, else label+definition '
                            f'cosine >= {_DEDUP_THRESHOLD} with the citation-designator guard',
                    'threshold': _DEDUP_THRESHOLD,
                },
                result={'merges': merges, 'count': len(merges)},
            )
        if guard_refusals:
            prov.track_pass(
                activity_type='filter', activity_name='designator_guard',
                case_id=case_id, session_id=extraction_session_id,
                agent_type='extraction_service', agent_name='rdf_storage_service',
                execution_plan={
                    **plan_base,
                    'rule': 'labels whose citation designators (case numbers, provision codes) '
                            'differ are never merged, whatever their cosine',
                    'threshold': _DEDUP_THRESHOLD,
                },
                result={'kept_separate': guard_refusals, 'count': len(guard_refusals)},
            )
    except Exception:
        logger.debug("storage dedup provenance skipped", exc_info=True)


def _merge_into_existing(
    existing_entity: TemporaryRDFStorage, new_json_ld: dict, new_section_type: str
) -> None:
    """Merge properties from new extraction into existing entity."""
    existing_json = existing_entity.rdf_json_ld or {}

    # Initialize section_sources if not present
    if 'section_sources' not in existing_json:
        existing_json['section_sources'] = []
        if existing_entity.provenance_metadata and existing_entity.provenance_metadata.get('section_type'):
            existing_json['section_sources'].append(existing_entity.provenance_metadata['section_type'])

    if new_section_type not in existing_json['section_sources']:
        existing_json['section_sources'].append(new_section_type)

    # Merge properties
    existing_props = existing_json.get('properties', {})
    new_props = new_json_ld.get('properties', {})

    for prop_name, new_values in new_props.items():
        if not isinstance(new_values, list):
            new_values = [new_values]

        if prop_name not in existing_props:
            existing_props[prop_name] = new_values
        else:
            existing_values = existing_props[prop_name]
            if not isinstance(existing_values, list):
                existing_values = [existing_values]

            for val in new_values:
                if val and val not in existing_values and val != "None":
                    existing_values.append(val)

            existing_props[prop_name] = existing_values

    existing_json['properties'] = existing_props

    # Merge source texts with section labels
    if 'source_texts' not in existing_json:
        existing_json['source_texts'] = {}
        if existing_json.get('source_text') and existing_json.get('section_sources'):
            first_section = existing_json['section_sources'][0] if existing_json['section_sources'] else 'unknown'
            existing_json['source_texts'][first_section] = existing_json['source_text']

    if new_json_ld.get('source_text'):
        existing_json['source_texts'][new_section_type] = new_json_ld['source_text']

    combined_sources = []
    for section, text in existing_json.get('source_texts', {}).items():
        combined_sources.append(f"[{section}] {text}")
    if combined_sources:
        existing_json['source_text'] = " | ".join(combined_sources)

    # Merge definitions array
    existing_defs = existing_json.get('definitions', [])
    new_defs = new_json_ld.get('definitions', [])

    if not existing_defs and existing_json.get('definition'):
        existing_defs = [{
            'text': existing_json['definition'],
            'source_type': 'extraction',
            'source_section': existing_json.get('section_sources', ['unknown'])[0],
            'is_primary': True,
        }]

    existing_texts = {d.get('text', '') for d in existing_defs}
    for new_def in new_defs:
        new_text = new_def.get('text', '')
        if new_text and new_text not in existing_texts:
            new_def['is_primary'] = False
            existing_defs.append(new_def)
            existing_texts.add(new_text)

    existing_json['definitions'] = existing_defs

    # Merge relationships
    existing_rels = existing_json.get('relationships', [])
    new_rels = new_json_ld.get('relationships', [])

    existing_rel_keys = {(r.get('type'), r.get('target_uri')) for r in existing_rels}
    for rel in new_rels:
        rel_key = (rel.get('type'), rel.get('target_uri'))
        if rel_key not in existing_rel_keys:
            existing_rels.append(rel)

    existing_json['relationships'] = existing_rels

    # Merge types
    existing_types = set(existing_json.get('types', []))
    new_types = set(new_json_ld.get('types', []))
    existing_json['types'] = list(existing_types | new_types)

    # Update the entity. The dict was edited in place, so flag the column explicitly (the
    # MutableDict column type does the same; both are kept so the UPDATE is emitted even if
    # one of them is ever removed).
    existing_entity.rdf_json_ld = existing_json
    flag_modified(existing_entity, 'rdf_json_ld')
    existing_entity.updated_at = db.func.now()

    existing_entity.property_count = sum(
        len(v) if isinstance(v, list) else 1
        for v in existing_props.values()
    )
    existing_entity.relationship_count = len(existing_rels)


def _clean_json_data(data):
    """Clean data to ensure it's JSON-serializable."""
    import json

    def clean_value(value):
        if callable(value):
            return None
        elif isinstance(value, dict):
            return {k: clean_value(v) for k, v in value.items() if clean_value(v) is not None}
        elif isinstance(value, (list, tuple)):
            cleaned = [clean_value(v) for v in value]
            return [v for v in cleaned if v is not None]
        elif isinstance(value, (str, int, float, bool, type(None))):
            return value
        else:
            try:
                str_val = str(value)
                if 'built-in method' in str_val or 'method' in str_val:
                    return None
                return str_val
            except Exception:
                logger.debug("Failed to convert value to string during serialization", exc_info=True)
                return None

    if isinstance(data, dict):
        return {k: clean_value(v) for k, v in data.items() if clean_value(v) is not None}
    return data
