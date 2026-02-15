"""
Unified Dual Extractor for all 9 D-Tuple concepts.

Replaces the 7 near-identical dual_*_extractor.py files with a single
parameterized class. Loads prompts from DB templates, validates LLM output
against Pydantic schemas from schemas.py, and uses PromptVariableResolver
for MCP entity context.

Usage:
    extractor = UnifiedDualExtractor('obligations')
    classes, individuals = extractor.extract(case_text, case_id, 'discussion')
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ValidationError

from app.utils.llm_utils import extract_json_from_response

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-concept configuration
# ---------------------------------------------------------------------------
# Derived from the 7 existing dual extractors. Each entry captures the
# concept-specific settings that were previously hardcoded.

CONCEPT_CONFIG: Dict[str, Dict[str, Any]] = {
    'roles': {
        'step': 1,
        'model_tier': 'powerful',
        'temperature': 0.3,
        'max_tokens': 4000,
        'classes_key': 'new_role_classes',
        'individuals_key': 'role_individuals',
        'class_ref_field': 'role_class',
    },
    'states': {
        'step': 1,
        'model_tier': 'powerful',
        'temperature': 0.3,
        'max_tokens': 8000,
        'classes_key': 'new_state_classes',
        'individuals_key': 'state_individuals',
        'class_ref_field': 'state_class',
    },
    'resources': {
        'step': 1,
        'model_tier': 'powerful',
        'temperature': 0.3,
        'max_tokens': 4000,
        'classes_key': 'new_resource_classes',
        'individuals_key': 'resource_individuals',
        'class_ref_field': 'resource_class',
    },
    'principles': {
        'step': 2,
        'model_tier': 'powerful',
        'temperature': 0.7,
        'max_tokens': 8192,
        'classes_key': 'new_principle_classes',
        'individuals_key': 'principle_individuals',
        'class_ref_field': 'principle_class',
    },
    'obligations': {
        'step': 2,
        'model_tier': 'powerful',
        'temperature': 0.2,
        'max_tokens': 8192,
        'classes_key': 'new_obligation_classes',
        'individuals_key': 'obligation_individuals',
        'class_ref_field': 'obligation_class',
    },
    'constraints': {
        'step': 2,
        'model_tier': 'powerful',
        'temperature': 0.2,
        'max_tokens': 8192,
        'classes_key': 'new_constraint_classes',
        'individuals_key': 'constraint_individuals',
        'class_ref_field': 'constraint_class',
    },
    'capabilities': {
        'step': 2,
        'model_tier': 'powerful',
        'temperature': 0.2,
        'max_tokens': 8192,
        'classes_key': 'new_capability_classes',
        'individuals_key': 'capability_individuals',
        'class_ref_field': 'capability_class',
    },
    'actions': {
        'step': 3,
        'model_tier': 'default',
        'temperature': 0.7,
        'max_tokens': 8192,
        'classes_key': 'new_action_classes',
        'individuals_key': 'action_individuals',
        'class_ref_field': 'action_class',
    },
    'events': {
        'step': 3,
        'model_tier': 'default',
        'temperature': 0.7,
        'max_tokens': 8192,
        'classes_key': 'new_event_classes',
        'individuals_key': 'event_individuals',
        'class_ref_field': 'event_class',
    },
}


class UnifiedDualExtractor:
    """
    Parameterized extractor for any of the 9 D-Tuple concepts.

    Consolidates the shared flow:
        prompt template (DB) -> variable resolution (MCP) -> LLM call ->
        Pydantic validation -> ontology matching -> linking
    """

    def __init__(
        self,
        concept_type: str,
        llm_client: Any = None,
        model: Optional[str] = None,
    ):
        if concept_type not in CONCEPT_CONFIG:
            raise ValueError(
                f"Unknown concept_type '{concept_type}'. "
                f"Valid: {list(CONCEPT_CONFIG.keys())}"
            )

        self.concept_type = concept_type
        self.config = CONCEPT_CONFIG[concept_type]

        # -- Mock / real LLM client --
        from app.services.extraction.mock_llm_provider import (
            get_llm_client_for_extraction,
            get_current_data_source,
        )
        self.llm_client = get_llm_client_for_extraction(llm_client)
        self.data_source = get_current_data_source()

        # -- Model selection --
        from models import ModelConfig
        if model:
            self.model_name = model
        else:
            self.model_name = ModelConfig.get_claude_model(
                self.config['model_tier']
            )

        # -- MCP existing entities --
        self.existing_classes: List[Dict[str, Any]] = []
        self.mcp_client = None
        try:
            from app.services.external_mcp_client import get_external_mcp_client
            self.mcp_client = get_external_mcp_client()
            self.existing_classes = self._load_existing_classes()
            logger.info(
                f"Loaded {len(self.existing_classes)} existing "
                f"{concept_type} classes from MCP"
            )
        except Exception as e:
            logger.warning(f"MCP client unavailable for {concept_type}: {e}")

        # -- DB prompt template --
        self.template = self._load_template()

        # -- Pydantic schemas --
        from app.services.extraction.schemas import CONCEPT_SCHEMAS, CONCEPT_MODELS
        self.result_schema = CONCEPT_SCHEMAS[concept_type]
        self.class_model, self.individual_model = CONCEPT_MODELS[concept_type]

        # -- Response caching for RDF conversion --
        self.last_raw_response: Optional[str] = None
        self.last_prompt: Optional[str] = None

        logger.info(
            f"UnifiedDualExtractor({concept_type}) initialized: "
            f"model={self.model_name}, "
            f"template={'DB' if self.template else 'NONE'}, "
            f"existing_classes={len(self.existing_classes)}"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(
        self,
        case_text: str,
        case_id: int,
        section_type: str = 'discussion',
    ) -> Tuple[List[BaseModel], List[BaseModel]]:
        """
        Extract candidate classes and individuals for this concept.

        Returns:
            (candidate_classes, individuals) -- both are lists of Pydantic
            model instances from schemas.py.
        """
        start = time.time()
        logger.info(
            f"Extracting {self.concept_type} for case {case_id}, "
            f"section={section_type}"
        )
        self._current_section_type = section_type

        # 1. Build prompt
        prompt = self._build_prompt(case_text, section_type)
        self.last_prompt = prompt

        # 2. Call LLM
        raw_json = self._call_llm(prompt)
        if not raw_json:
            logger.warning(f"No LLM result for {self.concept_type}")
            return [], []

        # 3. Parse + validate
        classes, individuals = self._parse_and_validate(raw_json, case_id)

        # 4. Match against existing ontology classes
        self._check_existing_matches(classes)

        # 5. Link individuals to classes
        self._link_individuals_to_classes(individuals, classes)

        elapsed = time.time() - start
        logger.info(
            f"Extracted {len(classes)} classes, {len(individuals)} individuals "
            f"for {self.concept_type} in {elapsed:.1f}s"
        )

        return classes, individuals

    def get_last_raw_response(self) -> Optional[str]:
        """Return the last raw LLM response for RDF conversion."""
        return self.last_raw_response

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _load_template(self):
        """Load the active DB prompt template for this concept."""
        try:
            from app.models.extraction_prompt_template import (
                ExtractionPromptTemplate,
            )
            template = ExtractionPromptTemplate.get_active_template(
                step_number=self.config['step'],
                concept_type=self.concept_type,
            )
            if template:
                logger.info(
                    f"Loaded DB template for {self.concept_type} "
                    f"(v{template.version})"
                )
            else:
                logger.warning(
                    f"No active DB template for step={self.config['step']}, "
                    f"concept={self.concept_type}"
                )
            return template
        except Exception as e:
            logger.error(f"Failed to load DB template: {e}")
            return None

    def _build_prompt(self, case_text: str, section_type: str) -> str:
        """
        Build the extraction prompt.

        Uses the DB template with PromptVariableResolver for variable
        resolution (case text + existing MCP entities).
        """
        if not self.template:
            raise RuntimeError(
                f"No prompt template available for {self.concept_type}. "
                f"Check extraction_prompt_templates table."
            )

        # Format existing entities for the template
        existing_text = self._format_existing_entities()

        # Build variable dict matching the template's Jinja2 variables
        variables = {
            'case_text': case_text,
            'section_type': section_type,
            f'existing_{self.concept_type}_text': existing_text,
            'existing_entities_text': existing_text,
        }

        rendered = self.template.render(**variables)

        # Append wrapper format instruction so the LLM returns a dict with
        # both keys rather than a bare list, enabling full schema validation.
        classes_key = self.config['classes_key']
        individuals_key = self.config['individuals_key']
        rendered += (
            f'\n\nIMPORTANT: Wrap your response as a JSON object with exactly '
            f'two keys:\n'
            f'{{"{ classes_key}": [...], "{individuals_key}": [...]}}\n'
            f'If there are no individuals to report, use an empty array for '
            f'"{individuals_key}".'
        )
        return rendered

    def _format_existing_entities(self) -> str:
        """Format existing ontology entities for prompt inclusion."""
        if not self.existing_classes:
            return f"No existing {self.concept_type} classes found in ontology."

        lines = []
        for entity in self.existing_classes[:20]:
            label = entity.get('label', entity.get('name', 'Unknown'))
            definition = entity.get(
                'definition', entity.get('description', '')
            )
            if definition:
                if len(definition) > 150:
                    definition = definition[:147] + '...'
                lines.append(f"- {label}: {definition}")
            else:
                lines.append(f"- {label}")

        if len(self.existing_classes) > 20:
            lines.append(f"... and {len(self.existing_classes) - 20} more")

        return '\n'.join(lines)

    # ------------------------------------------------------------------
    # MCP entity loading
    # ------------------------------------------------------------------

    def _load_existing_classes(self) -> List[Dict[str, Any]]:
        """Load existing classes from MCP for ontology awareness."""
        if not self.mcp_client:
            return []

        try:
            # The PromptVariableResolver has the concept->MCP method mapping.
            # For simplicity, use get_entities_by_category which works for all.
            category_map = {
                'roles': 'Role',
                'states': 'State',
                'resources': 'Resource',
                'principles': 'Principle',
                'obligations': 'Obligation',
                'constraints': 'Constraint',
                'capabilities': 'Capability',
                'actions': 'Action',
                'events': 'Event',
            }
            category = category_map[self.concept_type]

            # Some concepts have dedicated methods on the MCP client
            method_name = f'get_all_{self.concept_type[:-1] if self.concept_type.endswith("s") else self.concept_type}_entities'
            # e.g. get_all_obligation_entities, get_all_role_entities

            if hasattr(self.mcp_client, method_name):
                entities = getattr(self.mcp_client, method_name)()
                if isinstance(entities, list):
                    return entities

            # Fallback: generic category query
            result = self.mcp_client.get_entities_by_category(category)
            if result.get('success') and result.get('result'):
                return result['result'].get('entities', [])

            return []

        except Exception as e:
            logger.error(
                f"Failed to load existing {self.concept_type} classes: {e}"
            )
            return []

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------

    def _call_llm(self, prompt: str) -> Dict[str, Any]:
        """Call the LLM and parse JSON from the response."""
        try:
            # Mock client path (testing)
            if self.llm_client is not None:
                response = self.llm_client.call(
                    prompt=prompt,
                    extraction_type=self.concept_type,
                    section_type=getattr(
                        self, '_current_section_type', 'facts'
                    ),
                )
                response_text = (
                    response.content
                    if hasattr(response, 'content')
                    else str(response)
                )
                self.last_raw_response = response_text
                return extract_json_from_response(response_text)

            # Real LLM path
            from app.utils.llm_utils import get_llm_client

            client = get_llm_client()
            if not client:
                logger.error("No LLM client available")
                return {}

            response = client.messages.create(
                model=self.model_name,
                max_tokens=self.config['max_tokens'],
                temperature=self.config['temperature'],
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = (
                response.content[0].text if response.content else ""
            )
            self.last_raw_response = response_text

            if response.stop_reason == 'max_tokens':
                logger.warning(
                    f"Response truncated at {self.config['max_tokens']} "
                    f"tokens for {self.concept_type}"
                )
                # Try to repair truncated JSON
                response_text = self._repair_truncated_json(response_text)

            logger.debug(f"LLM response ({len(response_text)} chars)")

            return extract_json_from_response(response_text)

        except Exception as e:
            logger.error(f"LLM call failed for {self.concept_type}: {e}")
            return {}

    # ------------------------------------------------------------------
    # Parsing + validation
    # ------------------------------------------------------------------

    def _parse_and_validate(
        self,
        raw_json: Any,
        case_id: int,
    ) -> Tuple[List[BaseModel], List[BaseModel]]:
        """
        Parse LLM JSON output into Pydantic models.

        Handles multiple response shapes:
        - Dict with classes_key and individuals_key (ideal)
        - Raw list of items (DB template format -- classes only)
        - Partial dict (only one key present)

        Tries full ExtractionResult validation first. Falls back to
        parsing classes and individuals separately if that fails.
        """
        classes_key = self.config['classes_key']
        individuals_key = self.config['individuals_key']

        # Normalize: if the LLM returned a bare list, wrap it
        if isinstance(raw_json, list):
            logger.info(
                f"LLM returned a list of {len(raw_json)} items, "
                f"wrapping as {classes_key}"
            )
            raw_json = {classes_key: raw_json}

        if not isinstance(raw_json, dict):
            logger.error(
                f"Unexpected LLM response type: {type(raw_json).__name__}"
            )
            return [], []

        # Remap legacy flat keys to the expected dual-array keys.
        # Older DB templates used a single array (e.g. "resources" instead of
        # "new_resource_classes" + "resource_individuals"). If neither expected
        # key is present but a legacy key is, treat the flat list as classes.
        if classes_key not in raw_json and individuals_key not in raw_json:
            legacy_key = self.concept_type  # e.g. 'resources', 'roles'
            if legacy_key in raw_json and isinstance(raw_json[legacy_key], list):
                logger.info(
                    f"Remapping legacy '{legacy_key}' key "
                    f"({len(raw_json[legacy_key])} items) to '{classes_key}'"
                )
                raw_json[classes_key] = raw_json.pop(legacy_key)

        # Normalize all items BEFORE validation so the primary path
        # handles enum hyphens, label->identifier, and source_text
        # fallback -- not just the fallback per-item path.
        for key in (classes_key, individuals_key):
            items = raw_json.get(key, [])
            if isinstance(items, list):
                raw_json[key] = [
                    self._normalize_field_names(item)
                    for item in items
                    if isinstance(item, dict)
                ]

        # Try validating the full ExtractionResult
        try:
            result = self.result_schema.model_validate(raw_json)
            classes = getattr(result, classes_key, [])
            individuals = getattr(result, individuals_key, [])
            logger.info(
                f"Pydantic validation OK: {len(classes)} classes, "
                f"{len(individuals)} individuals"
            )
            return classes, individuals
        except ValidationError as e:
            logger.warning(
                f"Full schema validation failed for {self.concept_type}, "
                f"falling back to per-item parsing: {e.error_count()} errors"
            )
            logger.debug(f"Keys in LLM response: {list(raw_json.keys())}")
            for err in e.errors()[:5]:
                logger.debug(f"  Validation error: {err['loc']} - {err['msg']}")

        # Fallback: parse each item individually, skipping invalid ones.
        # Items are already normalized above, but _parse_items calls
        # _normalize_field_names again (idempotent).
        classes = self._parse_items(
            raw_json.get(classes_key, []),
            self.class_model,
            'class',
            case_id,
        )
        individuals = self._parse_items(
            raw_json.get(individuals_key, []),
            self.individual_model,
            'individual',
            case_id,
        )

        return classes, individuals

    def _parse_items(
        self,
        items: List[Dict],
        model_class: type,
        item_type: str,
        case_id: int,
    ) -> List[BaseModel]:
        """Parse a list of raw dicts into Pydantic model instances."""
        parsed = []
        for i, item in enumerate(items):
            try:
                item = self._normalize_field_names(item)
                obj = model_class.model_validate(item)
                parsed.append(obj)
            except ValidationError as e:
                label = item.get('label', item.get('identifier', f'#{i}'))
                logger.warning(
                    f"Skipping invalid {self.concept_type} {item_type} "
                    f"'{label}': {e.error_count()} validation errors"
                )
                for err in e.errors():
                    logger.debug(f"  {err['loc']}: {err['msg']}")
        return parsed

    @staticmethod
    def _normalize_field_names(item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize LLM field names to match Pydantic schema field names.

        DB templates and hardcoded prompts may use different field names
        for the same concept. This maps common aliases.
        """
        # definition/description: handled by Pydantic AliasChoices on BaseCandidate
        # text_references/examples_from_case: handled by Pydantic AliasChoices

        # source_text fallback to first text reference
        refs = item.get('text_references') or item.get('examples_from_case')
        if not item.get('source_text') and refs:
            item['source_text'] = refs[0]

        # name/label -> identifier (for individuals)
        if 'identifier' not in item:
            if 'name' in item:
                item['identifier'] = item['name']
            elif 'label' in item:
                item['identifier'] = item['label']

        # Normalize hyphenated enum values to underscores
        # LLMs sometimes return "non-inertial" instead of "non_inertial"
        for enum_field in ('persistence_type', 'state_category', 'urgency_level',
                           'role_category', 'resource_category', 'resource_type'):
            if enum_field in item and isinstance(item[enum_field], str):
                item[enum_field] = item[enum_field].replace('-', '_')

        return item

    # ------------------------------------------------------------------
    # Ontology matching
    # ------------------------------------------------------------------

    def _check_existing_matches(self, classes: List[BaseModel]) -> None:
        """
        Check candidate classes against existing ontology classes.

        Updates the match_decision field on each candidate.
        """
        if not self.existing_classes:
            return

        for candidate in classes:
            if candidate.match_decision.matches_existing:
                # LLM already identified a match
                continue

            for existing in self.existing_classes:
                existing_label = existing.get('label', '')
                if self._labels_match(candidate.label, existing_label):
                    candidate.match_decision.matches_existing = True
                    candidate.match_decision.matched_uri = existing.get('uri')
                    candidate.match_decision.matched_label = existing_label
                    candidate.match_decision.confidence = 0.9
                    candidate.match_decision.reasoning = (
                        'Label match with existing ontology class'
                    )
                    break

    def _labels_match(self, label1: str, label2: str) -> bool:
        """Case-insensitive exact label matching with normalization.

        Only matches when labels are identical after normalization.
        Substring containment is intentionally excluded -- the LLM
        already sees the full existing class list and makes deliberate
        match decisions.  Overriding with substring matching collapses
        legitimate specializations (e.g. 'Design Engineer Role' would
        falsely match 'Engineer Role').
        """
        norm1 = label1.lower().replace('_', ' ').replace('-', ' ').strip()
        norm2 = label2.lower().replace('_', ' ').replace('-', ' ').strip()
        return norm1 == norm2

    # ------------------------------------------------------------------
    # Individual-to-class linking
    # ------------------------------------------------------------------

    def _link_individuals_to_classes(
        self,
        individuals: List[BaseModel],
        classes: List[BaseModel],
    ) -> None:
        """
        Propagate ontology match info from classes to their individuals.

        When an individual's class reference (e.g. role_class) points to a
        newly extracted class that matched an existing ontology class, the
        individual inherits that match decision. When the reference points
        directly to an existing ontology class label, the individual gets
        a match decision linking it there.
        """
        class_ref_field = self.config['class_ref_field']

        # Build lookup: normalized label -> candidate class
        candidate_by_label = {}
        for c in classes:
            norm = c.label.lower().replace('_', ' ').replace('-', ' ').strip()
            candidate_by_label[norm] = c

        # Build lookup: normalized label -> existing ontology class dict
        existing_by_label = {}
        for existing in self.existing_classes:
            lbl = existing.get('label', '')
            if lbl:
                norm = lbl.lower().replace('_', ' ').replace('-', ' ').strip()
                existing_by_label[norm] = existing

        for individual in individuals:
            ref_value = getattr(individual, class_ref_field, None)
            if not ref_value:
                continue

            ref_norm = ref_value.lower().replace('_', ' ').replace('-', ' ').strip()

            # Case 1: individual references a new candidate class
            matched_candidate = candidate_by_label.get(ref_norm)
            if matched_candidate:
                md = matched_candidate.match_decision
                if md.matches_existing:
                    # Cascade: class matched existing -> individual inherits
                    individual.match_decision.matches_existing = True
                    individual.match_decision.matched_uri = md.matched_uri
                    individual.match_decision.matched_label = md.matched_label
                    individual.match_decision.confidence = md.confidence
                    individual.match_decision.reasoning = (
                        f"Via class '{matched_candidate.label}': "
                        f"{md.reasoning or ''}"
                    )
                    logger.debug(
                        f"Individual '{individual.identifier}' linked to "
                        f"existing '{md.matched_label}' via class "
                        f"'{matched_candidate.label}'"
                    )
                continue

            # Case 2: individual references an existing ontology class directly
            matched_existing = existing_by_label.get(ref_norm)
            if matched_existing:
                individual.match_decision.matches_existing = True
                individual.match_decision.matched_uri = matched_existing.get('uri')
                individual.match_decision.matched_label = matched_existing.get('label')
                individual.match_decision.confidence = 0.95
                individual.match_decision.reasoning = (
                    f"Individual typed as existing ontology class "
                    f"'{matched_existing.get('label')}'"
                )
                logger.debug(
                    f"Individual '{individual.identifier}' directly references "
                    f"existing class '{matched_existing.get('label')}'"
                )

    # ------------------------------------------------------------------
    # JSON repair
    # ------------------------------------------------------------------

    @staticmethod
    def _repair_truncated_json(text: str) -> str:
        """
        Attempt to repair JSON that was truncated by max_tokens.

        Strategy: strip markdown fences, find the last complete object
        in the array, close the array.
        """
        import json
        import re

        # Strip markdown code fences
        cleaned = re.sub(r'^```(?:json)?\s*', '', text.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned)

        # Try parsing as-is first
        try:
            json.loads(cleaned)
            return cleaned
        except json.JSONDecodeError:
            pass

        # Find the last complete object by tracking brace depth
        depth = 0
        last_complete_end = -1
        in_string = False
        escape_next = False

        for i, ch in enumerate(cleaned):
            if escape_next:
                escape_next = False
                continue
            if ch == '\\':
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    last_complete_end = i

        if last_complete_end > 0:
            repaired = cleaned[:last_complete_end + 1]
            # Close any open array
            if repaired.lstrip().startswith('['):
                repaired = repaired.rstrip().rstrip(',') + '\n]'
            try:
                json.loads(repaired)
                logger.info(
                    f"Repaired truncated JSON: kept "
                    f"{last_complete_end + 1}/{len(cleaned)} chars"
                )
                return repaired
            except json.JSONDecodeError:
                pass

        logger.warning("Could not repair truncated JSON")
        return text
