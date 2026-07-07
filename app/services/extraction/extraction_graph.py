"""
Conversion and storage helpers for the extraction pipeline.

The live pipeline is Celery (steps) + the temporal_dynamics LangGraph (Step 3
only); this module supplies the shared Pydantic-to-RDF conversion and
temporary_rdf_storage persistence they use (pydantic_to_rdf_data,
store_extraction_result, _extract_properties, and the label/name helpers).

The former single-graph orchestrator (build_extraction_graph /
run_extraction_pipeline and its per-concept nodes) was deleted 2026-07-07
(A/E properties review): it had zero callers, and its Pass-3 nodes would have
stored actions/events in a row shape every A/E reader mis-reads.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


from app.services.extraction.schemas import (
    CATEGORY_TO_ONTOLOGY_IRI,
    CONCEPT_EXTRACTION_TYPES,
    CONCEPT_MODELS,
    CONCEPT_SCHEMAS,
    CORE_NS,
    EXTRACTION_STEPS,
    INTERMEDIATE_NS,
)
from app.services.extraction.unified_dual_extractor import CONCEPT_CONFIG

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------

def pydantic_to_rdf_data(
    classes: list,
    individuals: list,
    concept_type: str,
    case_id: int,
    section_type: str = 'discussion',
    pass_number: int = None,
    step_number: int = None,
    ontology_definitions: Dict[str, Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Convert Pydantic model lists from UnifiedDualExtractor to the rdf_data dict
    expected by TemporaryRDFStorage.store_extraction_results().

    Args:
        classes: List of Pydantic candidate class models
        individuals: List of Pydantic individual models
        concept_type: One of the 9 D-Tuple concept names
        case_id: Case ID for URI construction
        section_type: Section source (facts, discussion)
        pass_number: Extraction pass number (1, 2, or 3)
        step_number: Pipeline step (1, 2, or 3)
        ontology_definitions: Dict mapping label -> {text, source_uri, source_ontology}
            from matched OntServe entities. Appended to definitions array.

    Returns:
        Dict with 'new_classes' and 'new_individuals' lists
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    new_classes = []
    new_individuals = []

    category_field = _CONCEPT_CATEGORY_FIELD.get(concept_type)
    parent_uri = _CORE_PARENT.get(concept_type, f'{CORE_NS}Thing')
    iri_map_key = concept_type  # same name in CATEGORY_TO_ONTOLOGY_IRI

    for cls_obj in classes:
        label = cls_obj.label
        safe_label = _sanitize_label(label, space_char='')
        uri = f'{INTERMEDIATE_NS}{safe_label}'

        # Resolve parent from category if available
        resolved_parent = parent_uri
        if category_field:
            cat_val = getattr(cls_obj, category_field, None)
            if cat_val:
                cat_str = cat_val.value if hasattr(cat_val, 'value') else str(cat_val)
                iri_map = CATEGORY_TO_ONTOLOGY_IRI.get(iri_map_key, {})
                resolved_parent = iri_map.get(cat_str, parent_uri)

        # Build properties dict from all non-base fields
        properties = _extract_properties(
            cls_obj, concept_type, timestamp, case_id, section_type, pass_number,
        )

        # Ensure source_text is populated -- when full schema validation
        # succeeds, _normalize_field_names is skipped and source_text may
        # be None even though text_references has values.
        source_text = cls_obj.source_text
        if not source_text and cls_obj.text_references:
            source_text = cls_obj.text_references[0]

        # Build definitions array with provenance
        definition_entry = {
            'text': cls_obj.definition,
            'source_type': 'extraction',
            'source_section': section_type,
            'source_step': step_number,
            'source_case': case_id,
            'is_primary': True,
            'timestamp': timestamp,
        }

        class_info = {
            'uri': uri,
            'label': label,
            'definition': cls_obj.definition,
            'definitions': [definition_entry],
            'parent': resolved_parent,
            'properties': properties,
            'source_text': source_text,
            'section_sources': [section_type],
            'source_texts': {section_type: source_text} if source_text else {},
            'match_decision': {
                'matches_existing': cls_obj.match_decision.matches_existing,
                'matched_uri': cls_obj.match_decision.matched_uri,
                'matched_label': cls_obj.match_decision.matched_label,
                'confidence': cls_obj.match_decision.confidence,
                'reasoning': cls_obj.match_decision.reasoning,
            },
        }

        # Append ontology definition if this class matched an existing entity
        if ontology_definitions and label in ontology_definitions:
            ont_def = ontology_definitions[label]
            ont_def_text = ont_def.get('text', '')
            # Skip if identical to extraction definition
            if ont_def_text and ont_def_text != cls_obj.definition:
                class_info['definitions'].append({
                    'text': ont_def_text,
                    'source_type': 'ontology',
                    'source_uri': ont_def.get('source_uri', ''),
                    'source_ontology': ont_def.get('source_ontology', ''),
                    'is_primary': False,
                    'timestamp': timestamp,
                })

        # Store category at top level for commit service lookup
        # (commit service checks rdf_data.get(category_field) as fallback)
        # Do NOT add to properties -- _extract_properties already adds the
        # camelCase version (roleCategory, stateCategory, etc.) for display.
        if category_field:
            cat_val = getattr(cls_obj, category_field, None)
            if cat_val:
                cat_str = cat_val.value if hasattr(cat_val, 'value') else str(cat_val)
                class_info[category_field] = cat_str

        new_classes.append(class_info)

    for ind_obj in individuals:
        identifier = getattr(ind_obj, 'identifier', '') or getattr(ind_obj, 'name', 'Unknown')
        safe_id = _sanitize_label(identifier, space_char='_')
        ind_uri = f'http://proethica.org/ontology/case/{case_id}#{safe_id}'

        # Determine type URIs from the class reference field
        class_ref_field = CONCEPT_CONFIG[concept_type]['class_ref_field']
        class_ref = getattr(ind_obj, class_ref_field, None)
        types = []
        if class_ref:
            safe_class = _sanitize_label(class_ref, space_char='')
            types.append(f'{INTERMEDIATE_NS}{safe_class}')

        properties = _extract_properties(
            ind_obj, concept_type, timestamp, case_id, section_type, pass_number,
        )

        # Same source_text fallback as classes
        ind_source_text = ind_obj.source_text
        if not ind_source_text:
            refs = getattr(ind_obj, 'text_references', None)
            if refs:
                ind_source_text = refs[0]

        # Build individual definition from concept-specific descriptor fields.
        # Individuals don't have a 'definition' field like classes do -- the
        # meaningful descriptor varies by concept type (e.g. concrete_expression
        # for principles, obligation_statement for obligations). The field named
        # here becomes rdfs:comment + skos:definition on the committed individual
        # (via the definitions entry below), so it must be a description of the
        # individual, not a pointer to another entity. States have no such
        # descriptor field (subject is who the state is about, not a description),
        # so they take the description/definition fallback or no comment at all.
        _INDIVIDUAL_DESCRIPTOR = {
            'roles': 'case_involvement',
            # resources: no single descriptor field survives the Rs spec (used_in_context
            # was dropped 2026-06); composed below from document_title + topic instead.
            'principles': 'concrete_expression',
            'obligations': 'obligation_statement',
            'constraints': 'constraint_statement',
            'capabilities': 'case_context',
        }
        ind_definition = ''
        descriptor_field = _INDIVIDUAL_DESCRIPTOR.get(concept_type)
        if descriptor_field:
            ind_definition = getattr(ind_obj, descriptor_field, None) or ''
        if not ind_definition and concept_type == 'resources':
            title = getattr(ind_obj, 'document_title', None) or ''
            topic = getattr(ind_obj, 'topic', None) or ''
            if title and topic:
                ind_definition = f"{title} (topic: {topic})"
            else:
                ind_definition = title or topic
        if not ind_definition:
            ind_definition = (
                getattr(ind_obj, 'description', None)
                or getattr(ind_obj, 'definition', None)
                or ''
            )

        # Build definitions array with provenance for individuals
        ind_definition_entry = {
            'text': ind_definition,
            'source_type': 'extraction',
            'source_section': section_type,
            'source_step': step_number,
            'source_case': case_id,
            'is_primary': True,
            'timestamp': timestamp,
        }

        indiv_info = {
            'uri': ind_uri,
            'label': identifier,
            'definition': ind_definition,
            'definitions': [ind_definition_entry],
            'types': types,
            'properties': properties,
            'source_text': ind_source_text,
            'section_sources': [section_type],
            'source_texts': {section_type: ind_source_text} if ind_source_text else {},
            'match_decision': {
                'matches_existing': ind_obj.match_decision.matches_existing,
                'matched_uri': ind_obj.match_decision.matched_uri,
                'matched_label': ind_obj.match_decision.matched_label,
                'confidence': ind_obj.match_decision.confidence,
                'reasoning': ind_obj.match_decision.reasoning,
            },
        }

        new_individuals.append(indiv_info)

    return {
        'new_classes': new_classes,
        'new_individuals': new_individuals,
    }


def store_extraction_result(
    case_id: int,
    concept_type: str,
    step_number: int,
    section_type: str,
    session_id: str,
    extractor,
    classes: list,
    individuals: list,
    pass_number: int = None,
    extraction_pass: str = None,
) -> None:
    """
    Persist extraction results to the database.

    Consolidates the 3-call storage pattern used by both streaming and
    non-streaming extraction paths:
      1. ExtractionPrompt.save_prompt()
      2. pydantic_to_rdf_data()
      3. TemporaryRDFStorage.store_extraction_results()

    Args:
        case_id: Case database ID.
        concept_type: e.g. roles, states, resources, principles, obligations,
                      constraints, capabilities.
        step_number: Pipeline step (1 for contextual, 2 for normative).
        section_type: Source section (facts, discussion, etc.).
        session_id: UUID extraction session identifier.
        extractor: UnifiedDualExtractor instance (provides last_prompt,
                   last_raw_response, model_name).
        classes: Pydantic candidate class model instances.
        individuals: Pydantic individual model instances.
        pass_number: Extraction pass number (1 or 2).
        extraction_pass: Provenance label ('contextual_framework' or
                         'normative_requirements').
    """
    from app.models import db
    from app.models.extraction_prompt import ExtractionPrompt
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    model_name = extractor.model_name

    # 1. Save prompt + raw response
    try:
        ExtractionPrompt.save_prompt(
            case_id=case_id,
            concept_type=concept_type,
            prompt_text=extractor.last_prompt or f'[streaming] {concept_type}',
            raw_response=extractor.last_raw_response,
            step_number=step_number,
            section_type=section_type,
            llm_model=model_name,
            extraction_session_id=session_id,
            results_summary={
                'classes': len(classes),
                'individuals': len(individuals),
            },
            injection_mode=getattr(extractor, 'injection_mode', 'full'),
            tool_call_log=getattr(extractor, 'tool_call_log', None) or None,
        )
    except Exception as e:
        logger.warning(f"Could not save extraction prompt for {concept_type}: {e}")

    # 2 + 3. Convert Pydantic models to rdf_data, then store
    try:
        # Collect ontology definitions from the extractor if available
        ont_defs = getattr(extractor, 'ontology_definitions', None)

        rdf_data = pydantic_to_rdf_data(
            classes=classes,
            individuals=individuals,
            concept_type=concept_type,
            case_id=case_id,
            section_type=section_type,
            pass_number=pass_number,
            step_number=step_number,
            ontology_definitions=ont_defs,
        )

        provenance_data = {
            'section_type': section_type,
            'extracted_at': datetime.now(timezone.utc).isoformat(),
            'model_used': model_name,
            'concept_type': concept_type,
        }
        if extraction_pass:
            provenance_data['extraction_pass'] = extraction_pass

        TemporaryRDFStorage.store_extraction_results(
            case_id=case_id,
            extraction_session_id=session_id,
            extraction_type=concept_type,
            rdf_data=rdf_data,
            extraction_model=model_name,
            provenance_data=provenance_data,
        )

        db.session.commit()
        logger.info(
            f"Stored {len(rdf_data.get('new_classes', []))} classes + "
            f"{len(rdf_data.get('new_individuals', []))} individuals "
            f"for {concept_type} (case {case_id})"
        )
    except Exception as e:
        logger.error(f"Failed to store {concept_type} entities: {e}")
        import traceback
        logger.error(traceback.format_exc())


def _extract_properties(
    obj: Any,
    concept_type: str,
    timestamp: str,
    case_id: int,
    section_type: str,
    pass_number: int = None,
) -> Dict[str, list]:
    """
    Extract non-base fields from a Pydantic model as a properties dict.

    Mirrors the format produced by RDFExtractionConverter.get_temporary_triples():
    each property value is a list of strings.

    The entity review template iterates ``rdf_json_ld.properties`` to display
    concept-specific details (e.g. activation conditions for states,
    distinguishing features for roles).  Fields that are already stored at the
    top level of rdf_json_ld (label, definition, source_text) are excluded.
    Confidence and text_references are included so the review page shows them.
    """
    # Fields stored at the top level of the rdf_json_ld dict -- skip here
    skip_fields = {
        'label', 'definition', 'match_decision',
        'source_text', 'identifier', 'name',
    }

    props: Dict[str, list] = {}

    model_data = obj.model_dump(exclude_none=True, exclude_unset=False)
    for field_name, value in model_data.items():
        if field_name in skip_fields:
            continue
        if value is None:
            continue
        # Skip empty collections (e.g. attributes: {}, relationships: [])
        if isinstance(value, (dict, list)) and not value:
            continue

        # Normalize to list of strings
        if isinstance(value, list):
            str_values = [str(v) for v in value if v is not None]
        elif isinstance(value, dict):
            str_values = [str(value)]
        elif hasattr(value, 'value'):
            str_values = [value.value]
        else:
            str_values = [str(value)]

        if str_values:
            # Convert field_name to camelCase for consistency with RDF converter
            camel = _to_camel_case(field_name)
            props[camel] = str_values

    # Add provenance properties
    props['generatedAtTime'] = [timestamp]
    props['wasAttributedTo'] = [f'Case {case_id} Extraction']
    props['firstDiscoveredInCase'] = [str(case_id)]
    props['firstDiscoveredAt'] = [timestamp]
    props['discoveredInCase'] = [str(case_id)]
    props['discoveredInSection'] = [section_type]

    if pass_number is not None:
        props['discoveredInPass'] = [str(pass_number)]

    # Add source text to properties as well
    source_text = getattr(obj, 'source_text', None)
    if source_text:
        props['sourceText'] = [source_text]

    return props


def _sanitize_label(label: str, space_char: str = '') -> str:
    """Sanitize a label for use in URIs."""
    result = label.replace(' ', space_char)
    for ch in '()"\'<>&,':
        result = result.replace(ch, '')
    return result


def _to_camel_case(snake_str: str) -> str:
    """Convert snake_case to camelCase. Delegates to the single shared converter
    (R3) so storage and commit cannot drift. Behavior-preserving for the
    lowercase snake_case field names this receives."""
    from app.utils.predicate_naming import to_camel_case
    return to_camel_case(snake_str)


# ---------------------------------------------------------------------------
# Extraction node factory
# ---------------------------------------------------------------------------
