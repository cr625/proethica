"""
LangGraph StateGraph for D-Tuple extraction pipeline.

Orchestrates the 3-pass extraction system:
  Pass 1 (Contextual): roles, states, resources
  Pass 2 (Normative):  principles, obligations, constraints, capabilities
  Pass 3 (Temporal):   actions, events

Within each pass, concepts are extracted sequentially (the LLM calls are the
bottleneck, not orchestration overhead). Between passes, earlier results are
available for cross-concept context.

Usage:
    from app.services.extraction.extraction_graph import run_extraction_pipeline
    result = run_extraction_pipeline(case_id=7, model='claude-haiku-4-5-20251022')
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, END

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

class ConceptResult(TypedDict, total=False):
    """Result from a single concept extraction."""
    concept: str
    classes_count: int
    individuals_count: int
    elapsed: float
    error: Optional[str]
    session_id: str


class ExtractionState(TypedDict, total=False):
    """LangGraph state for the full pipeline."""
    case_id: int
    model: str
    sections: Dict[str, str]           # facts, discussion
    pass1_results: Dict[str, ConceptResult]   # R, S, Rs
    pass2_results: Dict[str, ConceptResult]   # P, O, Cs, Ca
    pass3_results: Dict[str, ConceptResult]   # A, E
    errors: List[str]
    started_at: str
    completed_at: Optional[str]


# ---------------------------------------------------------------------------
# Pydantic model -> rdf_data conversion
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
    'capabilities': 'capability_category',
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

        class_info = {
            'uri': uri,
            'label': label,
            'definition': cls_obj.definition,
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
        # for principles, obligation_statement for obligations).
        _INDIVIDUAL_DESCRIPTOR = {
            'roles': 'case_involvement',
            'states': 'subject',
            'resources': 'used_in_context',
            'principles': 'concrete_expression',
            'obligations': 'obligation_statement',
            'constraints': 'constraint_statement',
            'capabilities': 'capability_statement',
        }
        ind_definition = ''
        descriptor_field = _INDIVIDUAL_DESCRIPTOR.get(concept_type)
        if descriptor_field:
            ind_definition = getattr(ind_obj, descriptor_field, None) or ''
        if not ind_definition:
            ind_definition = (
                getattr(ind_obj, 'description', None)
                or getattr(ind_obj, 'definition', None)
                or ''
            )

        indiv_info = {
            'uri': ind_uri,
            'label': identifier,
            'definition': ind_definition,
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
        )
    except Exception as e:
        logger.warning(f"Could not save extraction prompt for {concept_type}: {e}")

    # 2 + 3. Convert Pydantic models to rdf_data, then store
    try:
        rdf_data = pydantic_to_rdf_data(
            classes=classes,
            individuals=individuals,
            concept_type=concept_type,
            case_id=case_id,
            section_type=section_type,
            pass_number=pass_number,
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
    """Convert snake_case to camelCase."""
    parts = snake_str.split('_')
    return parts[0] + ''.join(p.capitalize() for p in parts[1:])


# ---------------------------------------------------------------------------
# Extraction node factory
# ---------------------------------------------------------------------------

def _make_extraction_node(concept_type: str, step_number: int):
    """
    Create a LangGraph node function for a single concept extraction.

    The returned function:
    1. Loads case text from state
    2. Calls UnifiedDualExtractor
    3. Converts Pydantic output to rdf_data
    4. Stores to TemporaryRDFStorage
    5. Returns updated state
    """
    pass_key = f'pass{step_number}_results'

    def node_fn(state: ExtractionState) -> dict:
        case_id = state['case_id']
        model = state.get('model')
        sections = state.get('sections', {})
        errors = list(state.get('errors', []))

        # Primary section for this pass
        if step_number == 1:
            section_type = 'facts'
        elif step_number == 2:
            section_type = 'discussion'
        else:
            section_type = 'discussion'

        case_text = sections.get(section_type, '')
        if not case_text:
            errors.append(f"No {section_type} text for {concept_type}")
            result = ConceptResult(
                concept=concept_type,
                classes_count=0,
                individuals_count=0,
                elapsed=0.0,
                error=f"No {section_type} text",
                session_id='',
            )
            current_results = dict(state.get(pass_key, {}))
            current_results[concept_type] = result
            return {pass_key: current_results, 'errors': errors}

        session_id = str(uuid.uuid4())
        start = time.time()

        try:
            from app.services.extraction.unified_dual_extractor import UnifiedDualExtractor

            extractor = UnifiedDualExtractor(
                concept_type=concept_type,
                model=model,
            )

            classes, individuals = extractor.extract(
                case_text=case_text,
                case_id=case_id,
                section_type=section_type,
            )

            # Save prompt/response record
            _save_extraction_prompt(
                case_id=case_id,
                concept_type=concept_type,
                step_number=step_number,
                section_type=section_type,
                extractor=extractor,
                session_id=session_id,
                model=model or extractor.model_name,
                classes_count=len(classes),
                individuals_count=len(individuals),
            )

            # Convert and store
            rdf_data = pydantic_to_rdf_data(
                classes=classes,
                individuals=individuals,
                concept_type=concept_type,
                case_id=case_id,
                section_type=section_type,
            )

            from app.models import TemporaryRDFStorage
            extraction_type = CONCEPT_EXTRACTION_TYPES.get(concept_type, concept_type)

            TemporaryRDFStorage.store_extraction_results(
                case_id=case_id,
                extraction_session_id=session_id,
                extraction_type=extraction_type,
                rdf_data=rdf_data,
                extraction_model=model or extractor.model_name,
                provenance_data={'section_type': section_type},
            )

            from app import db
            db.session.commit()

            elapsed = time.time() - start
            logger.info(
                f"[Pass {step_number}] {concept_type}: "
                f"{len(classes)} classes, {len(individuals)} individuals "
                f"({elapsed:.1f}s)"
            )

            result = ConceptResult(
                concept=concept_type,
                classes_count=len(classes),
                individuals_count=len(individuals),
                elapsed=elapsed,
                session_id=session_id,
            )

        except Exception as e:
            elapsed = time.time() - start
            error_msg = f"{concept_type} extraction failed: {e}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
            result = ConceptResult(
                concept=concept_type,
                classes_count=0,
                individuals_count=0,
                elapsed=elapsed,
                error=str(e),
                session_id=session_id,
            )

        current_results = dict(state.get(pass_key, {}))
        current_results[concept_type] = result
        return {pass_key: current_results, 'errors': errors}

    node_fn.__name__ = f'extract_{concept_type}'
    return node_fn


def _save_extraction_prompt(
    case_id: int,
    concept_type: str,
    step_number: int,
    section_type: str,
    extractor: Any,
    session_id: str,
    model: str,
    classes_count: int,
    individuals_count: int,
) -> None:
    """Save the prompt and LLM response to the extraction_prompts table."""
    try:
        from app.models.extraction_prompt import ExtractionPrompt
        ExtractionPrompt.save_prompt(
            case_id=case_id,
            concept_type=concept_type,
            prompt_text=extractor.last_prompt or f'[Pipeline] {concept_type}',
            raw_response=extractor.last_raw_response,
            step_number=step_number,
            section_type=section_type,
            llm_model=model,
            extraction_session_id=session_id,
            results_summary={
                'classes': classes_count,
                'individuals': individuals_count,
            },
        )
    except Exception as e:
        logger.warning(f"Could not save extraction prompt for {concept_type}: {e}")


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_extraction_graph() -> StateGraph:
    """
    Build the LangGraph StateGraph for the 3-pass extraction pipeline.

    Pass 1 (Contextual): roles -> states -> resources
    Pass 2 (Normative):  principles -> obligations -> constraints -> capabilities
    Pass 3 (Temporal):   actions -> events

    Within each pass, concepts run sequentially to avoid LLM rate limits
    and to allow each concept's context to build on the previous.
    """
    graph = StateGraph(ExtractionState)

    # Add a loader node that reads case sections from the DB
    graph.add_node('load_case', _load_case_node)

    # Pass 1 nodes
    pass1_concepts = EXTRACTION_STEPS[1]
    for concept in pass1_concepts:
        graph.add_node(f'extract_{concept}', _make_extraction_node(concept, 1))

    # Pass 2 nodes
    pass2_concepts = EXTRACTION_STEPS[2]
    for concept in pass2_concepts:
        graph.add_node(f'extract_{concept}', _make_extraction_node(concept, 2))

    # Pass 3 nodes
    pass3_concepts = EXTRACTION_STEPS[3]
    for concept in pass3_concepts:
        graph.add_node(f'extract_{concept}', _make_extraction_node(concept, 3))

    # Edges: load -> pass1 -> pass2 -> pass3 -> END
    graph.set_entry_point('load_case')

    # Chain pass 1
    graph.add_edge('load_case', f'extract_{pass1_concepts[0]}')
    for i in range(len(pass1_concepts) - 1):
        graph.add_edge(f'extract_{pass1_concepts[i]}', f'extract_{pass1_concepts[i+1]}')

    # Pass 1 -> Pass 2
    graph.add_edge(f'extract_{pass1_concepts[-1]}', f'extract_{pass2_concepts[0]}')
    for i in range(len(pass2_concepts) - 1):
        graph.add_edge(f'extract_{pass2_concepts[i]}', f'extract_{pass2_concepts[i+1]}')

    # Pass 2 -> Pass 3
    graph.add_edge(f'extract_{pass2_concepts[-1]}', f'extract_{pass3_concepts[0]}')
    for i in range(len(pass3_concepts) - 1):
        graph.add_edge(f'extract_{pass3_concepts[i]}', f'extract_{pass3_concepts[i+1]}')

    # Pass 3 -> END
    graph.add_edge(f'extract_{pass3_concepts[-1]}', END)

    return graph.compile()


def _load_case_node(state: ExtractionState) -> dict:
    """Load case sections from the database."""
    from app.models.document import Document

    case_id = state['case_id']
    case = Document.query.get(case_id)
    if not case:
        return {
            'errors': [f'Case {case_id} not found'],
            'sections': {},
        }

    metadata = case.doc_metadata or {}
    sections_data = metadata.get('sections_dual', {})

    sections = {}
    for key in ('facts', 'discussion', 'questions', 'conclusion'):
        val = sections_data.get(key, '')
        if isinstance(val, dict):
            val = val.get('text', '')
        sections[key] = val

    return {
        'sections': sections,
        'started_at': datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_extraction_pipeline(
    case_id: int,
    model: Optional[str] = None,
    concepts: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run the full D-Tuple extraction pipeline for a case.

    Args:
        case_id: The case to extract from
        model: LLM model override (default: per-concept config)
        concepts: Optional list to extract only specific concepts
                  (e.g., ['roles', 'obligations']). If None, extracts all 9.

    Returns:
        Final ExtractionState dict with results from all passes
    """
    graph = build_extraction_graph()

    initial_state: ExtractionState = {
        'case_id': case_id,
        'model': model or '',
        'sections': {},
        'pass1_results': {},
        'pass2_results': {},
        'pass3_results': {},
        'errors': [],
    }

    logger.info(f"Starting extraction pipeline for case {case_id}")
    start = time.time()

    result = graph.invoke(initial_state)

    elapsed = time.time() - start
    result['completed_at'] = datetime.now(timezone.utc).isoformat()

    # Summary
    total_classes = sum(
        r.get('classes_count', 0)
        for pass_results in [result.get('pass1_results', {}),
                             result.get('pass2_results', {}),
                             result.get('pass3_results', {})]
        for r in pass_results.values()
    )
    total_individuals = sum(
        r.get('individuals_count', 0)
        for pass_results in [result.get('pass1_results', {}),
                             result.get('pass2_results', {}),
                             result.get('pass3_results', {})]
        for r in pass_results.values()
    )

    logger.info(
        f"Pipeline complete for case {case_id}: "
        f"{total_classes} classes, {total_individuals} individuals "
        f"in {elapsed:.1f}s"
    )

    return result
