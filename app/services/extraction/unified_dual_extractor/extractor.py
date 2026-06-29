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

from pydantic import BaseModel

from app.services.extraction.unified_dual_extractor.config import CONCEPT_CONFIG
from app.services.extraction.unified_dual_extractor.prompt_building import (
    PromptBuildingMixin,
)
from app.services.extraction.unified_dual_extractor.llm_calls import (
    LLMCallMixin,
)
from app.services.extraction.unified_dual_extractor.parsing import (
    ParsingMixin,
)
from app.services.extraction.unified_dual_extractor.matching import (
    MatchingMixin,
)

logger = logging.getLogger(__name__)


class UnifiedDualExtractor(
    PromptBuildingMixin, LLMCallMixin, ParsingMixin, MatchingMixin,
):
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
        apply_filters: bool = True,
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
            from app.services.ontserve.external_mcp_client import get_external_mcp_client
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
        from app.services.extraction.schemas import (
            CONCEPT_SCHEMAS, CONCEPT_MODELS, to_structured_output_schema,
        )
        self.result_schema = CONCEPT_SCHEMAS[concept_type]
        self.class_model, self.individual_model = CONCEPT_MODELS[concept_type]
        # Structured-outputs schema, computed once: the cleaned JSON Schema handed to the
        # main LLM call as output_config.format so a complete response is guaranteed to be
        # parseable JSON. None when no result_schema is available, in which case _call_llm
        # falls back to the free-form (no output_config) path.
        self._structured_output_schema = (
            to_structured_output_schema(self.result_schema)
            if self.result_schema is not None else None
        )

        # -- Response caching for RDF conversion --
        self.last_raw_response: Optional[str] = None
        self.last_prompt: Optional[str] = None

        # -- Injection mode (Phase 2 label-only support) --
        self.injection_mode = injection_mode
        # -- Deterministic extraction filters (default ON = live behavior). When
        # False, .extract returns the parsed entities raw (precedent, quote-grounding,
        # and individual/type filters are skipped). Used by the offline A/B audit
        # harness to capture pre-filter extractions; the live pipeline leaves this True.
        self.apply_filters = apply_filters
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

        # 3a/3b. Deterministic precedent-contamination + quote-grounding filters.
        # Gated by self.apply_filters (default True = live behavior); the offline
        # A/B audit sets it False to capture the raw, pre-filter extraction.
        if self.apply_filters:
            classes, individuals = self._apply_text_filters(
                classes, individuals, case_id, section_type)

        # 4. Match against existing ontology classes
        self._check_existing_matches(classes)

        # 5. Collect ontology definitions for matched entities
        self.ontology_definitions = self._collect_ontology_definitions(classes)

        # 6. Link individuals to classes
        self._link_individuals_to_classes(individuals, classes)

        # 6b. Drop TYPES emitted as individuals (self-instance / wrong component).
        # Gated by self.apply_filters (default True = live behavior); skipped in the
        # offline A/B raw-capture path.
        if self.apply_filters:
            individuals = self._filter_types_as_individuals(
                individuals, case_id, section_type)

        elapsed = time.time() - start
        logger.info(
            f"Extracted {len(classes)} classes, {len(individuals)} individuals "
            f"for {self.concept_type} in {elapsed:.1f}s"
        )

        return classes, individuals

    # ------------------------------------------------------------------
    # Deterministic filters (gated by self.apply_filters in extract())
    # ------------------------------------------------------------------

    def _apply_text_filters(self, classes, individuals, case_id, section_type):
        """Step 3a: precedent-contamination filter (quote-grounding 3b removed 2026-06-29; see below).

        Gated by self.apply_filters so the live path and the offline raw-capture path
        (apply_filters=False, skips this) share one body. Returns (classes, individuals)."""
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

        # Quote-grounding (former step 3b) was REMOVED 2026-06-29 (user decision after the model A/B).
        # It fired 0x on Sonnet (verbatim quotes always ground) and only over-corrected on Opus, dropping
        # legitimate paraphrased obligations (e.g. Confidentiality, Safety) because Opus quotes the case
        # abstractively. A semantic-grounding rewrite still could not separate faithful paraphrase from
        # fabrication on Opus's output distribution (legitimate paraphrases scored cosine 0.46-0.69,
        # overlapping where a same-domain fabrication would fall), and Opus does not fabricate: anti-
        # fabrication is carried by the _SHARED_NO_FABRICATION_DIRECTIVE prompt directive. The (now
        # semantic) quote_grounding module is retained for the offline A/B audit harness and as a
        # candidate for commit-time / review-gate grounding, but is no longer wired into live extraction.
        return classes, individuals

    def _filter_types_as_individuals(self, individuals, case_id, section_type):
        """Step 6b: drop TYPES emitted as individuals (self-instance / wrong component).

        Relocated verbatim from extract(); the multi-purpose individual/type filter is
        generic across concept types via a CRITERIA row (it only runs for a type that
        has one), deterministic-first with one batched LLM call over the ambiguous
        remainder only. Best-effort: a failure never breaks extraction. Returns individuals."""
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

        return individuals

    def get_last_raw_response(self) -> Optional[str]:
        """Return the last raw LLM response for RDF conversion."""
        return self.last_raw_response
