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


from app.services.commit import naming
from app.services.commit.match_policy import linked_existing_class, match_link_threshold
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

# Maps concept type to the category field on its candidate class model.
_CONCEPT_CATEGORY_FIELD = {
    'roles': 'role_category',
    'principles': 'principle_category',
    'obligations': 'obligation_type',
    'states': 'state_category',
    'resources': 'resource_category',
    'actions': 'action_category',
    'events': 'event_category',
    # capabilities: the kind rides the class label via match_decision (no category field)
    'constraints': 'constraint_type',
}


# Maps concept type to the core parent class URI (fallback when no category).
_CORE_PARENT = {
    'roles': f'{CORE_NS}Role',
    'principles': f'{CORE_NS}Principle',
    'obligations': f'{CORE_NS}Obligation',
    'states': f'{CORE_NS}State',
    'resources': f'{CORE_NS}Resource',
    'actions': f'{CORE_NS}Action',
    'events': f'{CORE_NS}Event',
    'capabilities': f'{CORE_NS}Capability',
    'constraints': f'{CORE_NS}Constraint',
}



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
        # The class IRI is minted with the commit path's sanitizer (naming.safe_local_name)
        # so the working store carries the IRI the commit will write and the individuals
        # typed to this class (below) reference the same IRI. The former hyphen-keeping
        # sanitizer minted intermediate#Provider-ClientRole here while the commit wrote
        # ProviderClientRole (case 24-1 review, defect D).
        uri = f'{INTERMEDIATE_NS}{naming.safe_local_name(label)}'

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
            types.append(individual_type_iri(class_ref, ind_obj.match_decision))

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


def individual_type_iri(class_ref: str, match_decision) -> str:
    """The rdf:type IRI an individual carries in the working store.

    When the matcher LINKED the class reference to an EXISTING ontology class, that
    class is the type: it is the class the commit honors, so the store and the
    committed graph name the same class. Otherwise the IRI is minted from the class
    reference with the commit path's sanitizer, ``naming.safe_local_name``, so a
    label such as "Provider-Client Role" yields ``intermediate#ProviderClientRole``
    here as at commit, not the ``#Provider-ClientRole`` the former hyphen-keeping
    sanitizer produced (an IRI that exists in no ontology) while ``match_decision``
    held the real one (case 24-1 review, defect D).

    A decision counts as a link under the conditions the honoring rule of the
    commit (``_matched_class_override``) checks before it retypes an individual: a
    confidence at or above the shared link threshold
    (``match_policy.match_link_threshold``), a ``matched_uri`` in the intermediate
    namespace the commit writes types in, and a local name the URI sanitizer leaves
    unchanged. The conditions matter because the commit treats a row whose type
    already is the matched class as "nothing to honor" and skips its floor and
    chain checks for it. Adopting every matched IRI here typed a 0.75 match
    ("matched to parent with medium confidence") at storage time, where the floor
    keeps the minted type, and stored a core# or concepts# match under that
    namespace, which the commit re-mints as a new intermediate class named after
    the matched local name. Such a row now keeps the minted type here and the
    commit applies its own rule to it, as to every other row.
    """
    md = {
        'matches_existing': getattr(match_decision, 'matches_existing', False),
        'matched_uri': getattr(match_decision, 'matched_uri', None),
        'confidence': getattr(match_decision, 'confidence', None),
    }
    local = linked_existing_class({'match_decision': md}, match_link_threshold())
    iri = str(md['matched_uri'] or '')
    if local and iri == f'{INTERMEDIATE_NS}{local}' and naming.safe_local_name(local) == local:
        return iri
    return f'{INTERMEDIATE_NS}{naming.safe_local_name(class_ref)}'


def extraction_activity_name(concept_type: str) -> str:
    """Provenance activity name of a step 1 or 2 concept extraction
    (``dual_<concept>_extraction``): the name the provenance page resolves, together
    with the prompt's session id, through its CONCEPT_ACTIVITY_MAP."""
    return f'dual_{concept_type}_extraction'


def _record_llm_query_provenance(prompt_row, extractor, classes: list, individuals: list,
                                 origin: Optional[str]) -> None:
    """Record the model call behind a saved extraction prompt as one ``llm_query``
    activity (the row's session id, agent = the model, the extractor's call timestamps
    and the derived duration, case id, concept type and section) with the prompt and
    response as provenance entities, the way the temporal pass records its calls.

    Best-effort inside a savepoint: a failure here never costs the extraction its
    entities, and the activity is committed on its own because the model call did
    happen whatever the later storage steps do.
    """
    from app.models import db
    from app.services.provenance_service import get_provenance_service

    try:
        ended_at = getattr(extractor, 'last_llm_ended_at', None) or datetime.utcnow()
        started_at = getattr(extractor, 'last_llm_started_at', None) or ended_at
        metadata = {
            'concept_type': prompt_row.concept_type,
            'section_type': prompt_row.section_type,
            'step_number': prompt_row.step_number,
            'extraction_prompt_id': prompt_row.id,
            'classes': len(classes),
            'individuals': len(individuals),
        }
        if origin:
            metadata['origin'] = origin
        with db.session.begin_nested():
            get_provenance_service().record_llm_query(
                activity_name=extraction_activity_name(prompt_row.concept_type),
                case_id=prompt_row.case_id,
                session_id=prompt_row.extraction_session_id,
                model_name=prompt_row.llm_model or getattr(extractor, 'model_name', None),
                prompt_text=prompt_row.prompt_text,
                response_text=prompt_row.raw_response,
                started_at=started_at,
                ended_at=ended_at,
                execution_plan={
                    'concept_type': prompt_row.concept_type,
                    'section': prompt_row.section_type,
                    'step': prompt_row.step_number,
                    'injection_mode': getattr(prompt_row, 'injection_mode', None),
                },
                activity_metadata=metadata,
            )
        db.session.commit()
    except Exception:
        logger.warning("llm_query provenance skipped for %s (best-effort)",
                       getattr(prompt_row, 'concept_type', '?'), exc_info=True)


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
    origin: Optional[str] = None,
) -> None:
    """
    Persist extraction results to the database.

    Consolidates the storage pattern used by both streaming and
    non-streaming extraction paths:
      1. ExtractionPrompt.save_prompt() (prompt, raw response, extracted counts)
      2. one llm_query provenance activity for the model call, keyed by the
         saved prompt's session id (_record_llm_query_provenance)
      3. pydantic_to_rdf_data()
      4. TemporaryRDFStorage.store_extraction_results()
      5. results_summary rewritten from the stored rows (stored and merged counts)

    Args:
        case_id: Case database ID.
        concept_type: e.g. roles, states, resources, principles, obligations,
                      constraints, capabilities.
        step_number: Pipeline step (1 for contextual, 2 for normative).
        section_type: Source section (facts, discussion, etc.).
        session_id: UUID extraction session identifier.
        extractor: UnifiedDualExtractor instance (provides last_prompt,
                   last_raw_response, model_name, and the call bounds
                   last_llm_started_at / last_llm_ended_at).
        classes: Pydantic candidate class model instances.
        individuals: Pydantic individual model instances.
        pass_number: Extraction pass number (1 or 2).
        extraction_pass: Provenance label ('contextual_framework' or
                         'normative_requirements').
        origin: Provenance origin stored on the activity
                ('automated_pipeline' for the Celery pipeline). None leaves
                the origin to the display heuristics.
    """
    from app.models import db
    from app.models.extraction_prompt import ExtractionPrompt
    from app.models.temporary_rdf_storage import TemporaryRDFStorage
    from app.services.entity.rdf_storage_service import storage_summary

    model_name = extractor.model_name

    # 1. Save prompt + raw response. The extracted counts go in now so the prompt
    #    record is complete even if storage fails; step 5 replaces them with the
    #    stored and merged counts once the rows exist.
    prompt_row = None
    try:
        prompt_row = ExtractionPrompt.save_prompt(
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

    # 2. The model call as an llm_query activity of the prompt's session
    if prompt_row is not None:
        _record_llm_query_provenance(prompt_row, extractor, classes, individuals, origin)

    # 3 + 4. Convert Pydantic models to rdf_data, then store
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

        # 5. The summary the provenance card shows is written AFTER storage, from the
        #    stored rows, so an extracted-versus-stored difference carries its own
        #    explanation (merged_into_existing). Written before storage it read
        #    "individuals 4" beside 3 stored rows (case 24-1 review, defect C).
        if prompt_row is not None:
            prompt_row.results_summary = storage_summary(
                case_id, session_id, concept_type,
                extracted_classes=len(classes), extracted_individuals=len(individuals),
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
        # The value is the pipeline STEP that discovered the entity
        # (1 contextual, 2 normative, 3 temporal) -- not the facts/discussion
        # pass within a step. The property was named discoveredInPass until
        # the 2026-07-11 rename aligned it with the step terminology.
        props['discoveredInStep'] = [str(pass_number)]

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
