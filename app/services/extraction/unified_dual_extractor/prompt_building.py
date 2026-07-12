"""Prompt construction and MCP entity loading for the unified dual extractor.

PromptBuildingMixin: builds the extraction prompt (DB template + variable
resolution + cross-concept context + JSON wrapper suffix), carries forward
prior-section classes/actors, and loads the curated existing-class list from MCP.
Methods relocated verbatim from the former unified_dual_extractor.py;
UnifiedDualExtractor inherits this mixin so every ``self.`` reference (sibling
methods and instance attributes) resolves unchanged via MRO.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.prompt_variable_resolver import format_existing_entities

from app.services.extraction.unified_dual_extractor.config import (
    CONCEPT_TYPE_TO_CORE_CATEGORY,
    build_json_wrapper_suffix,
    format_cross_concept_context,
)

logger = logging.getLogger(__name__)


class PromptBuildingMixin:
    """Prompt assembly + MCP existing-class loading for UnifiedDualExtractor."""


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
                # Expected for pass-split components: their 'all'-pass row is
                # deactivated by design and the per-pass (facts/discussion)
                # template loads in _build_prompt. A warning here produced 14
                # misleading log lines per case (the pilot's
                # no_active_db_template signal).
                logger.debug(
                    f"No 'all'-pass DB template for step={self.config['step']}, "
                    f"concept={self.concept_type}; the per-pass template loads "
                    f"at prompt-build time"
                )
            return template
        except Exception as e:
            logger.error(f"Failed to load DB template: {e}")
            return None

    def _build_prompt(
        self, case_text: str, section_type: str, case_id: int = None,
    ) -> str:
        """
        Build the extraction prompt.

        Uses the DB template with PromptVariableResolver for variable
        resolution (case text + existing MCP entities).

        When section_type is not 'facts', classes already extracted from
        earlier sections (e.g. facts) are appended to the existing-entities
        list so the LLM can reference them rather than re-extracting.
        """
        # Use the pre-loaded template if one was set (tests / explicit caller); otherwise load the
        # PASS-SPECIFIC template (facts/discussion) for split components -- get_active_template falls back
        # to the 'all' template for unsplit ones. (Split components deactivate their 'all' row, so the
        # init-time no-pass load leaves self.template None and this picks the right per-pass template.)
        template = self.template
        if template is None:
            from app.models.extraction_prompt_template import ExtractionPromptTemplate
            template = ExtractionPromptTemplate.get_active_template(
                step_number=self.config['step'], concept_type=self.concept_type, pass_type=section_type)
        if not template:
            raise RuntimeError(
                f"No prompt template available for {self.concept_type} (pass={section_type}). "
                f"Check extraction_prompt_templates table."
            )

        # Format existing entities for the template
        existing_text = self._format_existing_entities()

        # For non-facts sections, include classes extracted from prior sections
        if section_type != 'facts' and case_id is not None:
            prior_text = self._format_prior_section_classes(case_id, section_type)
            if prior_text:
                existing_text += prior_text
            # Roles: also carry forward prior-section ACTORS so the discussion
            # pass reuses an actor identity instead of fragmenting it (Option C).
            prior_actors = self._format_prior_section_individuals(case_id, section_type)
            if prior_actors:
                existing_text += prior_actors

        # Load cross-concept context (e.g., roles for principles, etc.)
        cross_context = ''
        if case_id is not None:
            cross_context = format_cross_concept_context(
                self.concept_type, case_id
            )

        # Handle dict input from _format_section_for_llm()
        if isinstance(case_text, dict):
            case_text = case_text.get('llm_text') or case_text.get('html', '')
            logger.warning("case_text was a dict, extracted llm_text")

        # Strip non-printable control characters (except newline, tab, CR)
        # that may be present in source documents from PDF extraction.
        import re
        case_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', case_text)

        # Build variable dict matching the template's Jinja2 variables
        variables = {
            'case_text': case_text,
            'section_type': section_type,
            f'existing_{self.concept_type}_text': existing_text,
            'existing_entities_text': existing_text,
            'cross_concept_context': cross_context,
        }
        # Ontology-derived slots (role_definition, role_schema, role_directives, role_category_vocab),
        # resolved from the curated ontology + SHACL shapes by the SAME builder the editor preview uses, so
        # what the LLM receives is byte-identical to the preview. This also fixes the prior bug where
        # {{ role_schema }} was set only on the editor path and rendered to '' during real extraction.
        from app.services.prompt_variable_resolver import concept_ontology_slots
        variables.update(concept_ontology_slots(self.concept_type, section_type))

        rendered = template.render(**variables)
        # Render the optional system prompt with the same variables; _call_llm passes it as system=.
        # getattr-guarded so a render-only template-like object (e.g. a test fixture) does not break.
        self._rendered_system = (template.render_system(**variables)
                                 if hasattr(template, 'render_system') else '')

        # Append JSON wrapper instruction so the LLM returns a dict with
        # both keys rather than a bare list.  Kept in code (not in the
        # editable template) so the keys always match CONCEPT_CONFIG.
        rendered += build_json_wrapper_suffix(self.concept_type)
        return rendered

    def _format_existing_entities(self) -> str:
        """Format existing ontology entities for prompt inclusion."""
        return format_existing_entities(
            self.existing_classes, self.concept_type,
            label_only_tier2=(self.injection_mode == 'label_only'),
        )

    def _present_case_actor_letters(self, case_id: int) -> frozenset:
        """Present-case engineer letters for this case, cached per case on the instance.
        Delegates to the shared case_actors loader (see its docstring for why the discussion
        section is excluded)."""
        cache = getattr(self, '_pc_actor_cache', None)
        if cache is None:
            cache = self._pc_actor_cache = {}
        if case_id not in cache:
            from app.services.extraction.case_actors import present_case_engineer_letters
            cache[case_id] = present_case_engineer_letters(case_id)
        return cache[case_id]

    def _present_case_placeholders(self, case_id: int) -> frozenset:
        """Present-case Doe/Roe placeholder surnames, cached per case on the instance
        (non-empty only for pre-1980s opinions whose own parties are Doe/Roe)."""
        cache = getattr(self, '_pc_placeholder_cache', None)
        if cache is None:
            cache = self._pc_placeholder_cache = {}
        if case_id not in cache:
            from app.services.extraction.case_actors import present_case_placeholders
            cache[case_id] = present_case_placeholders(case_id)
        return cache[case_id]

    def _format_prior_section_classes(
        self, case_id: int, current_section: str,
    ) -> str:
        """
        Format classes extracted from earlier sections for this case.

        When extracting from discussion, the facts-extracted classes are
        included so the LLM can reference them instead of re-extracting.
        """
        try:
            from app.models.temporary_rdf_storage import TemporaryRDFStorage
            from app.models.extraction_prompt import ExtractionPrompt

            # Determine which prior sections to include
            section_order = ['facts', 'discussion', 'questions', 'conclusions']
            current_idx = section_order.index(current_section) if current_section in section_order else 0
            prior_sections = section_order[:current_idx]

            if not prior_sections:
                return ''

            # Find extraction sessions for prior sections
            prior_sessions = [
                p.extraction_session_id
                for p in ExtractionPrompt.query.filter_by(
                    case_id=case_id,
                    concept_type=self.concept_type,
                    is_active=True,
                ).all()
                if p.extraction_session_id and p.section_type in prior_sections
            ]

            if not prior_sessions:
                return ''

            # Query classes from those sessions
            prior_classes = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.extraction_type == self.concept_type,
                TemporaryRDFStorage.storage_type == 'class',
                TemporaryRDFStorage.extraction_session_id.in_(prior_sessions),
            ).all()

            if not prior_classes:
                return ''

            # Format as text block with multi-source definitions
            lines = [
                f'\n\n--- {self.concept_type.upper()} CLASSES ALREADY EXTRACTED FROM PRIOR SECTIONS OF THIS CASE ---',
                'These classes were captured from earlier sections and ARE ALREADY RECORDED. Your job in this',
                'pass is to AUGMENT: extract only classes that are genuinely NEW and absent from the list below.',
                'If a class you find is the SAME concept as one below, even under a different label or paraphrase',
                '(e.g. "AI Report Disclosure Duty" vs "AI Tool Disclosure Report Duty"), do NOT emit it as a new',
                'class; instead set match_decision.matches_existing=true with its matched_label from the list.',
                'Re-emitting an already-recorded concept under a reworded label creates a duplicate and is an',
                'extraction error. Add the discussion-only concepts the facts pass could not have seen.\n',
            ]
            for cls in prior_classes:
                json_ld = cls.rdf_json_ld or {}
                definitions = json_ld.get('definitions', [])
                if definitions and len(definitions) > 1:
                    # Show each definition with source tag
                    lines.append(f'- {cls.entity_label}')
                    for defn_entry in definitions:
                        source_tag = defn_entry.get('source_section') or defn_entry.get('source_type', 'unknown')
                        text = defn_entry.get('text', '')
                        if text:
                            lines.append(f'  [{source_tag}] {text}')
                else:
                    defn = cls.entity_definition or ''
                    lines.append(f'- {cls.entity_label}: {defn}')

            logger.info(
                f"Added {len(prior_classes)} prior-section {self.concept_type} "
                f"classes to prompt for case {case_id}"
            )
            return '\n'.join(lines)

        except Exception as e:
            logger.warning(f"Could not load prior-section classes: {e}")
            return ''

    def _format_prior_section_individuals(
        self, case_id: int, current_section: str,
    ) -> str:
        """Format role ACTORS already extracted as individuals in earlier
        sections, so the discussion pass reuses the same actor identity rather
        than minting a parallel, unlinked individual for the same person.

        Roles only (the Agent layer is role-scoped). An actor (e.g. "Engineer A")
        is stable across sections; each section may surface a different role facet
        of that actor. The block lists the actor, the facet seen, the section, and
        a one-line involvement so the LLM can tie a new facet to the existing
        actor via the role individual's ``actor`` field.
        """
        if (self.concept_type or '').lower() != 'roles':
            return ''
        try:
            from app.models.temporary_rdf_storage import TemporaryRDFStorage
            from app.models.extraction_prompt import ExtractionPrompt

            section_order = ['facts', 'discussion', 'questions', 'conclusions']
            current_idx = section_order.index(current_section) if current_section in section_order else 0
            prior_sections = section_order[:current_idx]
            if not prior_sections:
                return ''

            prior_sessions = [
                p.extraction_session_id
                for p in ExtractionPrompt.query.filter_by(
                    case_id=case_id, concept_type=self.concept_type, is_active=True,
                ).all()
                if p.extraction_session_id and p.section_type in prior_sections
            ]
            if not prior_sessions:
                return ''

            prior_individuals = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.extraction_type == self.concept_type,
                TemporaryRDFStorage.storage_type == 'individual',
                TemporaryRDFStorage.extraction_session_id.in_(prior_sessions),
            ).all()
            if not prior_individuals:
                return ''

            lines = [
                '\n\n--- ACTORS ALREADY IDENTIFIED IN PRIOR SECTIONS ---',
                'These actors (people / organizations filling roles) were identified',
                'in earlier sections. If a role here is the SAME actor, set the role',
                'individual\'s "actor" field to the SAME actor identity shown below,',
                'and create a new role facet only if the role genuinely differs. Do',
                'NOT invent a parallel actor for someone already listed.\n',
            ]
            for ind in prior_individuals:
                json_ld = ind.rdf_json_ld or {}
                props = json_ld.get('properties', {}) or {}
                actor_vals = props.get('actor')
                actor = (actor_vals[0] if isinstance(actor_vals, list) and actor_vals
                         else actor_vals) or ind.entity_label
                sections = json_ld.get('section_sources') or []
                section_tag = ', '.join(sections) if sections else 'prior'
                involvement = (ind.entity_definition or '').strip()
                if len(involvement) > 160:
                    involvement = involvement[:157] + '...'
                line = f'- actor "{actor}" | role facet: {ind.entity_label} | section: {section_tag}'
                if involvement:
                    line += f' | {involvement}'
                lines.append(line)

            logger.info(
                f"Added {len(prior_individuals)} prior-section role actors "
                f"to prompt for case {case_id}"
            )
            return '\n'.join(lines)

        except Exception as e:
            logger.warning(f"Could not load prior-section individuals: {e}")
            return ''

    # ------------------------------------------------------------------
    # MCP entity loading
    # ------------------------------------------------------------------

    def _load_existing_classes(self) -> List[Dict[str, Any]]:
        """Load the CURATED existing classes from MCP for ontology awareness.

        Restricted to the curated vocabulary (core + intermediate + intermediate-
        extended + external references) and de-duplicated by URI; per-case
        self-containment copies are excluded. self.existing_classes feeds THREE
        paths -- the prompt injection (format_existing_entities), the class matcher
        (_check_existing_matches), and the definition collection
        (_collect_ontology_definitions, which feeds the case-tagged scopeNote) --
        so filtering here is what keeps matches and definitions consolidating onto a
        curated class with its real definition, instead of a case copy's "Ontology
        class for Role" fallback. Mirrors the prompt-side filter."""
        if not self.mcp_client:
            return []

        try:
            # The PromptVariableResolver has the concept->MCP method mapping.
            # For simplicity, use get_entities_by_category which works for all.
            category = CONCEPT_TYPE_TO_CORE_CATEGORY[self.concept_type]

            # Some concepts have dedicated methods on the MCP client
            method_name = f'get_all_{self.concept_type[:-1] if self.concept_type.endswith("s") else self.concept_type}_entities'
            # e.g. get_all_obligation_entities, get_all_role_entities

            entities: List[Dict[str, Any]] = []
            if hasattr(self.mcp_client, method_name):
                got = getattr(self.mcp_client, method_name)()
                if isinstance(got, list):
                    entities = got
            if not entities:
                # Fallback: generic category query
                result = self.mcp_client.get_entities_by_category(category)
                if result.get('success') and result.get('result'):
                    entities = result['result'].get('entities', [])

            # Restrict to the curated vocabulary (drop per-case copies) and collapse
            # duplicate URIs to the highest-authority source, so the matcher and the
            # definition lookup never resolve to a case copy.
            from app.services.prompt_variable_resolver import (
                _curated_only, _dedup_entities_by_uri,
            )
            return _dedup_entities_by_uri(_curated_only(entities))

        except Exception as e:
            logger.error(
                f"Failed to load existing {self.concept_type} classes: {e}"
            )
            return []
