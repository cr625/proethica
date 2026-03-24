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

from app.models import db, ExtractionPrompt
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.services.entity_merge_service import EntityMergeService

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
    merge_service = EntityMergeService()

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

    # Store new classes with merge detection
    for class_info in rdf_data.get('new_classes', []):
        clean_class_info = _clean_json_data(class_info)
        match_decision = class_info.get('match_decision', {})

        existing = _find_existing_entity(
            case_id, class_info['label'], extraction_type.capitalize(), extraction_session_id
        )

        if existing:
            _merge_into_existing(existing, clean_class_info, section_type)
            created_entities.append(existing)
            merged_count += 1
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

        existing = _find_existing_entity(
            case_id, indiv_info['label'], extraction_type.capitalize(), extraction_session_id
        )

        if existing:
            _merge_into_existing(existing, clean_indiv_info, section_type)
            created_entities.append(existing)
            merged_count += 1
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
    return created_entities


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_existing_entity(
    case_id: int, entity_label: str, entity_type: str, current_session_id: str
) -> Optional[TemporaryRDFStorage]:
    """Find an existing uncommitted entity with same label."""
    return TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        TemporaryRDFStorage.entity_label == entity_label,
        TemporaryRDFStorage.entity_type == entity_type,
        TemporaryRDFStorage.is_published == False
    ).first()


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

    # Update the entity
    existing_entity.rdf_json_ld = existing_json
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
