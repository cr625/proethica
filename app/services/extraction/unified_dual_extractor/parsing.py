"""LLM-output parsing, validation, and JSON repair for the unified dual extractor.

ParsingMixin: validates raw LLM JSON into Pydantic models with a per-item
fallback (_parse_and_validate, _parse_items), normalizes LLM field-name and enum
variants (_normalize_field_names, including the category-enum inference and the
compliance-status mapping), and repairs JSON truncated by max_tokens
(_repair_truncated_json). Methods relocated verbatim from the former
unified_dual_extractor.py; UnifiedDualExtractor inherits this mixin so self.
resolution (e.g. self.config, self.result_schema, self.concept_type) is
unchanged via MRO. _repair_truncated_json is a staticmethod called by
LLMCallMixin via MRO.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from pydantic import BaseModel, ValidationError

from app.services.extraction.unified_dual_extractor.config import (
    _CATEGORY_INFERENCE,
    _infer_category_enum,
)

logger = logging.getLogger(__name__)


class ParsingMixin:
    """LLM-output parsing, validation, and JSON repair for UnifiedDualExtractor."""


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

    def _normalize_field_names(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize LLM field names to match Pydantic schema field names.

        DB templates and hardcoded prompts may use different field names
        for the same concept. This maps common aliases. Uses
        self.concept_type for concept-aware category inference.
        """
        # definition/description: handled by Pydantic AliasChoices on BaseCandidate
        # text_references/examples_from_case: handled by Pydantic AliasChoices

        # Bidirectional fallback between source_text and text_references
        refs = item.get('text_references') or item.get('examples_from_case')
        if not item.get('source_text') and refs:
            item['source_text'] = refs[0]
        elif item.get('source_text') and not refs:
            item['text_references'] = [item['source_text']]

        # name/label -> identifier (for individuals)
        if 'identifier' not in item:
            if 'name' in item:
                item['identifier'] = item['name']
            elif 'label' in item:
                item['identifier'] = item['label']

        # --- Remap commonly hallucinated class fields ---
        # LLM returns "balancing_requirements" instead of "potential_conflicts"
        if 'balancing_requirements' in item and 'potential_conflicts' not in item:
            item['potential_conflicts'] = item.pop('balancing_requirements')
        # LLM returns "application_context" -- no direct match, drop it
        # (this data is partially captured by extensional_examples)
        item.pop('application_context', None)
        # LLM returns "case_relevance" on individuals -- not a schema field
        item.pop('case_relevance', None)

        # NOTE: examples_from_case is NOT dropped here. Pydantic AliasChoices
        # on BaseCandidate.text_references handles it:
        #   AliasChoices('text_references', 'examples_from_case')
        # Dropping it would lose data when text_references is absent.

        # --- Default confidence when LLM omits it ---
        if 'confidence' not in item:
            item['confidence'] = 0.75

        # --- Ensure match_decision has required subfields ---
        md = item.get('match_decision')
        if isinstance(md, dict):
            md.setdefault('matches_existing', False)
            md.setdefault('confidence', 0.5)
            if not md.get('reasoning'):
                md['reasoning'] = 'No reasoning provided by LLM'
            # Remap LLM variants of matched_label
            if not md.get('matched_label'):
                for alt_key in ('matched_class', 'matched_name', 'match_label'):
                    if alt_key in md:
                        md['matched_label'] = md.pop(alt_key)
                        break
        # If LLM omits match_decision entirely on a class (has "label" key),
        # add a default so Pydantic populates the field
        if 'match_decision' not in item and 'label' in item:
            item['match_decision'] = {
                'matches_existing': False,
                'confidence': 0.5,
                'reasoning': 'match_decision omitted by LLM; post-hoc matching will resolve',
            }

        # --- Infer missing category enum from item text ---
        inferred = _infer_category_enum(self.concept_type, item)
        if inferred:
            spec = _CATEGORY_INFERENCE[self.concept_type]
            item.setdefault(spec[0], inferred)

        # Normalize hyphenated enum values to underscores
        # LLMs sometimes return "non-inertial" instead of "non_inertial"
        for enum_field in (
            'persistence_type', 'state_category', 'urgency_level',
            'role_category', 'resource_category', 'resource_type',
            'principle_category', 'obligation_type', 'enforcement_level',
            'compliance_status', 'constraint_type', 'flexibility', 'severity',
            'capability_category', 'skill_level', 'proficiency_level',
        ):
            if enum_field in item and isinstance(item[enum_field], str):
                item[enum_field] = item[enum_field].replace('-', '_')

        # Normalize compliance_status to valid ComplianceStatus enum values.
        # LLMs produce semantically equivalent but syntactically invalid values
        # (e.g. "potentially_violated", "met_after_objection"). Two-stage:
        # 1. Exact synonym map for known variants
        # 2. Keyword fallback for any novel LLM invention
        _COMPLIANCE_VALID = {'met', 'unmet', 'partial', 'unclear'}
        _COMPLIANCE_STATUS_MAP = {
            'not_met': 'unmet',
            'unknown': 'unclear',
            'partially_met': 'partial',
            'in_progress': 'partial',
            'pending': 'unclear',
            'violated': 'unmet',
            'fulfilled': 'met',
            'compliant': 'met',
            'non_compliant': 'unmet',
            'potentially_violated': 'partial',
            'met_after_objection': 'met',
        }
        cs = item.get('compliance_status')
        if cs and isinstance(cs, str) and cs not in _COMPLIANCE_VALID:
            if cs in _COMPLIANCE_STATUS_MAP:
                item['compliance_status'] = _COMPLIANCE_STATUS_MAP[cs]
            else:
                # Keyword fallback for novel LLM values.
                # Split on underscores to get word tokens, avoiding
                # substring false positives (e.g. "so_met_hing").
                tokens = set(cs.lower().replace('-', '_').split('_'))
                if tokens & {'violated', 'violation', 'breached', 'breach'}:
                    item['compliance_status'] = 'unmet'
                elif tokens & {'partial', 'partially', 'progress'}:
                    item['compliance_status'] = 'partial'
                elif tokens & {'unclear', 'unknown', 'undetermined', 'indeterminate'}:
                    item['compliance_status'] = 'unclear'
                elif tokens & {'met', 'fulfilled', 'satisfied', 'complied'}:
                    item['compliance_status'] = 'met'
                else:
                    item['compliance_status'] = 'unclear'

        return item

    # ------------------------------------------------------------------
    # JSON repair
    # ------------------------------------------------------------------

    @staticmethod
    def _repair_truncated_json(text: str) -> str:
        """
        Attempt to repair JSON that was truncated by max_tokens.

        Strategy: strip markdown fences, find the last complete nested
        object, close any open arrays and the outer object.
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

        # Track brace/bracket depth and find last complete nested object
        depth = 0
        bracket_depth = 0
        last_complete_at_depth = {}  # depth -> last position where an object closed
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
                last_complete_at_depth[depth] = i
            elif ch == '[':
                bracket_depth += 1
            elif ch == ']':
                bracket_depth -= 1

        # Best case: outer object completed at depth 0
        if 0 in last_complete_at_depth:
            repaired = cleaned[:last_complete_at_depth[0] + 1]
            if repaired.lstrip().startswith('['):
                repaired = repaired.rstrip().rstrip(',') + '\n]'
            try:
                json.loads(repaired)
                logger.info(
                    f"Repaired truncated JSON: kept "
                    f"{last_complete_at_depth[0] + 1}/{len(cleaned)} chars"
                )
                return repaired
            except json.JSONDecodeError:
                pass

        # Dict-style truncation: find last complete object at depth 1
        # (inside the outer dict), then close open arrays and outer dict
        if 1 in last_complete_at_depth:
            cut_pos = last_complete_at_depth[1] + 1
            repaired = cleaned[:cut_pos]
            # Close any open array brackets, then close outer dict
            repaired = repaired.rstrip().rstrip(',')
            # Count unclosed brackets and braces
            bd, bkd = 0, 0
            s_in_str, s_esc = False, False
            for ch in repaired:
                if s_esc:
                    s_esc = False
                    continue
                if ch == '\\':
                    s_esc = True
                    continue
                if ch == '"':
                    s_in_str = not s_in_str
                    continue
                if s_in_str:
                    continue
                if ch == '{': bd += 1
                elif ch == '}': bd -= 1
                elif ch == '[': bkd += 1
                elif ch == ']': bkd -= 1
            repaired += '\n' + ']' * bkd + '}' * bd
            try:
                json.loads(repaired)
                logger.info(
                    f"Repaired truncated dict JSON: kept "
                    f"{cut_pos}/{len(cleaned)} chars, "
                    f"closed {bkd} arrays + {bd} objects"
                )
                return repaired
            except json.JSONDecodeError:
                pass

        logger.warning("Could not repair truncated JSON")
        return text
