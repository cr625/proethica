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

from app.services.prompt_variable_resolver import format_existing_entities

from app.utils.llm_utils import extract_json_from_response

from app.services.extraction.unified_dual_extractor.config import (
    CONCEPT_CONFIG,
    CONCEPT_TYPE_TO_CORE_CATEGORY,
    _CATEGORY_INFERENCE,
    _infer_category_enum,
    build_json_wrapper_suffix,
    format_cross_concept_context,
)
from app.services.extraction.unified_dual_extractor.prompt_building import (
    PromptBuildingMixin,
)
from app.services.extraction.unified_dual_extractor.llm_calls import (
    LLMCallMixin,
)
from app.services.extraction.unified_dual_extractor.parsing import (
    ParsingMixin,
)

logger = logging.getLogger(__name__)


class UnifiedDualExtractor(PromptBuildingMixin, LLMCallMixin, ParsingMixin):
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
        injection_mode: str = 'full',
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
        from model_config import ModelConfig
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

        # -- Injection mode (Phase 2 label-only support) --
        self.injection_mode = injection_mode
        self.tool_call_count = 0
        self.tool_call_log: List[Dict[str, Any]] = []

        logger.info(
            f"UnifiedDualExtractor({concept_type}) initialized: "
            f"model={self.model_name}, "
            f"injection_mode={self.injection_mode}, "
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
        prompt = self._build_prompt(case_text, section_type, case_id=case_id)
        self.last_prompt = prompt

        # 2. Call LLM
        raw_json = self._call_llm(prompt)
        if not raw_json:
            logger.warning(f"No LLM result for {self.concept_type}")
            return [], []

        # 3. Parse + validate
        classes, individuals = self._parse_and_validate(raw_json, case_id)

        # 3a. Drop phantom entities pulled from cited precedent cases: they belong to the
        # precedent, not the case under analysis. One contamination check (precedent_filter)
        # covers three rules -- a citation marker in the label (e.g. "Defendant Attorney BER
        # Case 19-3", any concept type); for fact concepts, a clean-label provenance rule (every
        # supporting quote sits in cited-precedent context, e.g. "Public Works Director" attested
        # only by "BER Case No. 00-5 ..."); and the present-case actor rule (an engineer letter
        # absent from this case's facts/question/conclusion, e.g. "Engineer A" in a case whose
        # engineer is L -- a precedent actor recapped in the Discussion that the first two rules
        # miss). This is the LIVE Step 1-2 path; the same check runs in the Step-3 temporal and
        # Step-4 narrative passes via the shared drop_contaminated_entities entry point.
        from app.services.extraction.precedent_filter import drop_contaminated_entities
        present_letters = self._present_case_actor_letters(case_id)
        classes, dropped_c = drop_contaminated_entities(
            classes, lambda c: getattr(c, 'label', None),
            get_quotes=lambda c: getattr(c, 'text_references', None),
            concept_type=self.concept_type, present_letters=present_letters)
        individuals, dropped_i = drop_contaminated_entities(
            individuals, lambda i: getattr(i, 'identifier', None) or getattr(i, 'label', None),
            get_quotes=lambda i: getattr(i, 'text_references', None),
            concept_type=self.concept_type, present_letters=present_letters)
        if dropped_c or dropped_i:
            logger.info(
                f"Contamination filter ({self.concept_type}): present-case engineers "
                f"{sorted(present_letters)}, dropped {len(dropped_c)} class(es) + "
                f"{len(dropped_i)} individual(s): {dropped_c + dropped_i}")
            try:  # provenance: record the filter PASS (what was rejected + why). Best-effort.
                from app.services.provenance_service import get_provenance_service
                get_provenance_service().track_pass(
                    activity_type='filter', activity_name='precedent_filter',
                    case_id=case_id, agent_type='extraction_service', agent_name='precedent_filter',
                    execution_plan={'concept_type': self.concept_type, 'section': section_type,
                                    'present_case_engineers': sorted(present_letters),
                                    'rule': 'drop entities derived from a cited precedent case '
                                            '(citation marker in label; for fact concepts, all '
                                            'supporting quotes in precedent context; or a foreign '
                                            'present-case engineer letter)'},
                    result={'dropped': dropped_c + dropped_i,
                            'dropped_classes': len(dropped_c),
                            'dropped_individuals': len(dropped_i)})
            except Exception:
                logger.debug("precedent_filter provenance skipped", exc_info=True)

        # 4. Match against existing ontology classes
        self._check_existing_matches(classes)

        # 5. Collect ontology definitions for matched entities
        self.ontology_definitions = self._collect_ontology_definitions(classes)

        # 6. Link individuals to classes
        self._link_individuals_to_classes(individuals, classes)

        # 6b. Drop TYPES emitted as individuals: an individual that is a relabeling of
        # its own class (a self-instance), or content that belongs to another
        # component. The multi-purpose individual/type filter is generic across
        # concept types via a CRITERIA row (it only runs for a type that has one),
        # deterministic-first with one batched LLM call over the ambiguous remainder
        # only. Runs here at extraction time so the dropped types never reach
        # temporary_rdf_storage and the review UI shows the filtered set. Best-effort,
        # like the precedent filter above: a failure never breaks extraction.
        try:
            from app.services.extraction.individual_type_filter import filter_individuals, CRITERIA
            if self.concept_type in CRITERIA and individuals:
                def _fdict(ind):
                    cls = ''
                    for k in ('resource_class', 'instance_of', 'state_class', 'role_class',
                              'principle_class', 'obligation_class', 'constraint_class',
                              'capability_class'):
                        v = getattr(ind, k, None)
                        if v:
                            cls = str(v)
                            break
                    return {
                        'label': (getattr(ind, 'identifier', None) or getattr(ind, 'name', None)
                                  or getattr(ind, 'label', '') or ''),
                        'instance_of': cls,
                        'definition': (getattr(ind, 'used_in_context', None)
                                       or getattr(ind, 'description', None) or ''),
                    }
                _dicts = [_fdict(ind) for ind in individuals]
                _fres = filter_individuals(_dicts, self.concept_type)
                if _fres['dropped']:
                    _kept_ids = {id(d) for d in _fres['kept']}
                    individuals = [ind for ind, d in zip(individuals, _dicts) if id(d) in _kept_ids]
                    logger.info(
                        f"Individual/type filter ({self.concept_type}): dropped "
                        f"{len(_fres['dropped'])} type-as-individual "
                        f"(resolver={_fres['resolver']}, llm_items={_fres['llm_items']}): "
                        f"{[it.get('label') for it, _why in _fres['dropped']]}")
                    try:  # provenance: record the filter PASS. Best-effort.
                        from app.services.provenance_service import get_provenance_service
                        get_provenance_service().track_pass(
                            activity_type='filter', activity_name='individual_type_filter',
                            case_id=case_id, agent_type='extraction_service',
                            agent_name='individual_type_filter',
                            execution_plan={'concept_type': self.concept_type, 'section': section_type,
                                            'resolver': _fres['resolver'], 'llm_items': _fres['llm_items'],
                                            'rule': 'drop a class minted as an individual '
                                                    '(self-instance / wrong component)'},
                            result={'dropped': [it.get('label') for it, _why in _fres['dropped']],
                                    'count': len(_fres['dropped'])})
                    except Exception:
                        logger.debug("individual_type_filter provenance skipped", exc_info=True)
        except Exception as e:
            logger.warning(f"individual/type filter skipped for {self.concept_type}: {e}")

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
    # Ontology matching
    # ------------------------------------------------------------------

    def _check_existing_matches(self, classes: List[BaseModel]) -> None:
        """
        Check candidate classes against existing ontology classes.

        Updates the match_decision field on each candidate.

        For classes where the LLM already set matches_existing=True but
        provided a label (not a full URI) in matched_uri, resolves the
        proper URI from self.existing_classes.
        """
        if not self.existing_classes:
            return

        # Build label -> existing entity lookup for URI resolution
        existing_by_label = {}
        for existing in self.existing_classes:
            lbl = existing.get('label', '')
            if lbl:
                norm = lbl.lower().replace('_', ' ').replace('-', ' ').strip()
                existing_by_label[norm] = existing

        for candidate in classes:
            if candidate.match_decision.matches_existing:
                # LLM already identified a match -- resolve URI if missing
                # or invalid (LLM only sees labels, not full URIs)
                uri = candidate.match_decision.matched_uri or ''
                if not uri.startswith('http'):
                    resolve_label = (
                        candidate.match_decision.matched_label
                        or candidate.match_decision.matched_uri
                        or ''
                    )
                    norm = resolve_label.lower().replace(
                        '_', ' '
                    ).replace('-', ' ').strip()
                    resolved = existing_by_label.get(norm)
                    if resolved:
                        candidate.match_decision.matched_uri = resolved.get('uri')
                        candidate.match_decision.matched_label = (
                            resolved.get('label')
                        )
                        logger.debug(
                            f"Resolved URI for LLM-matched class "
                            f"'{candidate.label}': {resolved.get('uri')}"
                        )
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

        # Cleanup: zero out ALL orphaned match data where no URI was resolved.
        # The LLM sometimes matches against sibling extractions (from prior
        # sections) rather than the ontology list.  Those siblings have no
        # OntServe URI, so the match is invalid.  Clear everything so the DB
        # columns stay strictly "matched to an OntServe ontology entity."
        for candidate in classes:
            if not candidate.match_decision.matched_uri:
                candidate.match_decision.confidence = 0.0
                candidate.match_decision.matches_existing = False
                candidate.match_decision.matched_label = None
                candidate.match_decision.reasoning = None

        # Cross-category gate (Layer 1). Both branches above can establish a
        # match the LLM or a label match proposed; deterministically reject any
        # match whose matched class chains (via the curated subClassOf* chain) to
        # a core category disjoint from this candidate's category. This stops a
        # genuine Obligation being merged into a class an earlier extraction
        # mis-established as a Principle, which otherwise forces a Pellet
        # disjointness clash. Runs LAST so its rejection reasoning survives the
        # orphan-cleanup pass above. See
        # docs-internal/reextraction/matcher-category-authority-design.md.
        for candidate in classes:
            self._reject_cross_category_match(candidate)

    def _candidate_core_category(self) -> Optional[str]:
        """The core category a candidate of this extractor's concept_type is."""
        return CONCEPT_TYPE_TO_CORE_CATEGORY.get(self.concept_type)

    def _reject_cross_category_match(self, candidate: BaseModel) -> None:
        """Reject a prefer-existing match that crosses a disjoint core category.

        Resolves the matched class's curated subClassOf* CHAIN core category
        (anchored in proethica-core+intermediate[-extended], NOT the stored
        OntServe entity-table category or conceptCategory literal, which are
        extraction-derived and can lie) and compares it to the candidate's core
        category. Two distinct core categories are mutually disjoint under the
        nine-way AllDisjointClasses, so the match would force an OWL-DL clash;
        drop it and let the candidate be treated as a new class. A same-category
        match, or a match whose chain category cannot be resolved, is left
        unchanged.
        """
        md = candidate.match_decision
        if not md.matches_existing:
            return

        matched_ref = md.matched_uri or md.matched_label
        if not matched_ref:
            return

        candidate_cat = self._candidate_core_category()
        if not candidate_cat:
            return

        from app.services.extraction.category_resolver import resolve_core_category
        from app.services.extraction.entity_matcher import category_compatible
        chain_cat = resolve_core_category(matched_ref)
        if not chain_cat:
            # Chain category unknown (class not in the curated tiers); cannot
            # prove a conflict, so leave the match in place.
            return

        # Compatibility decided by the shared guard. The control flow above
        # already mirrors category_compatible's chain path (early-return-keep on
        # an unresolved chain), so feed it the already-resolved chain category
        # via a constant resolver: it then compares chain_cat against this
        # concept_type's marker, which for the nine D-tuple types is exactly the
        # old ``chain_cat == candidate_cat`` test (CONCEPT_TYPE_TO_CORE_CATEGORY
        # values are the marker tokens). Behavior-preserving; normalization +
        # comparison now live in entity_matcher.
        if category_compatible(
            self.concept_type, matched_ref, chain_resolver=lambda _ref: chain_cat,
        ):
            return

        logger.warning(
            "Matcher rejected cross-category match for '%s': existing class %s "
            "chains to %s but candidate is %s",
            getattr(candidate, 'label', None) or getattr(candidate, 'identifier', '?'),
            matched_ref, chain_cat, candidate_cat,
        )
        md.matches_existing = False
        md.matched_uri = None
        md.matched_label = None
        md.confidence = 0.0
        md.reasoning = (
            f"rejected cross-category match: existing class chains to "
            f"{chain_cat} but candidate is {candidate_cat}"
        )

    def _collect_ontology_definitions(
        self, classes: List[BaseModel],
    ) -> Dict[str, Dict[str, str]]:
        """Collect definitions from matched ontology entities.

        For each candidate class that matched an existing ontology class,
        look up the ontology entity's comment (rdfs:comment) and return it
        keyed by label.

        Returns:
            Dict mapping label -> {text, source_uri, source_ontology}
        """
        result = {}
        if not self.existing_classes:
            return result

        # Build lookup: URI -> existing entity dict
        existing_by_uri = {}
        existing_by_label = {}
        for ent in self.existing_classes:
            uri = ent.get('uri', '')
            label = ent.get('label', '')
            if uri:
                existing_by_uri[uri] = ent
            if label:
                norm = label.lower().replace('_', ' ').replace('-', ' ').strip()
                existing_by_label[norm] = ent

        for candidate in classes:
            md = candidate.match_decision
            if not md.matches_existing:
                continue

            # Find the ontology entity via matched_uri or matched_label
            ont_entity = None
            if md.matched_uri:
                ont_entity = existing_by_uri.get(md.matched_uri)
            if not ont_entity and md.matched_label:
                norm = md.matched_label.lower().replace('_', ' ').replace('-', ' ').strip()
                ont_entity = existing_by_label.get(norm)

            ont_def = (
                ont_entity.get('description')
                or ont_entity.get('comment', '')
            ) if ont_entity else ''
            if ont_def:
                result[candidate.label] = {
                    'text': ont_def,
                    'source_uri': ont_entity.get('uri', ''),
                    'source_ontology': (
                        ont_entity.get('ontology_name')
                        or ont_entity.get('source')
                        or (ont_entity.get('metadata', {}) or {}).get('ontology', '')
                    ),
                }

        return result

    def _labels_match(self, label1: str, label2: str) -> bool:
        """Case-insensitive exact label matching with normalization.

        Only matches when labels are identical after normalization.
        Substring containment is intentionally excluded -- the LLM
        already sees the full existing class list and makes deliberate
        match decisions.  Overriding with substring matching collapses
        legitimate specializations (e.g. 'Design Engineer Role' would
        falsely match 'Engineer Role').

        BEHAVIOR-PRESERVING NOTE (matcher unification 2026-06): faithful
        unification through the shared ``entity_matcher.normalize_label`` is NOT
        possible here without changing commit decisions, so the old inline
        normalization is intentionally retained.  Two divergences:
          1. This site folds '_' and '-' to spaces; ``normalize_label`` does not.
          2. ``normalize_label`` ALSO drops a trailing parenthetical and
             collapses internal whitespace; this site does NOT.
        681 candidate labels in the corpus carry a trailing '(...)' while no
        existing OntServe class label does, so routing the candidate side
        through ``normalize_label`` would drop that suffix and let
        "Foo Role (Present Case)" newly exact-match an existing "Foo Role",
        flipping a commit decision.  The separator fold IS shared with the
        ``_reject_cross_category_match`` pre-clean below.  Decision preserved;
        do not re-route through ``normalize_label``.  See the equivalence test
        ``test_labels_match_*`` in tests/extraction/test_matcher_unification.py.
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
                # Apply the same chain-category gate as _check_existing_matches:
                # existing_by_label is keyed off get_entities_by_category (the
                # STORED category), which can disagree with the curated subClassOf
                # CHAIN (the F2 root cause), so a direct individual->existing-class
                # link can still cross a disjoint category. Reject if so.
                self._reject_cross_category_match(individual)
