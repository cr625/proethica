"""Extraction recipe model -- a component's extraction expressed as an ordered list of typed step modules.

This is the Phase-1 SCAFFOLD: a read-only, declarative description of a component's recipe. The interpreter
that EXECUTES recipes, the per-step runtime provenance, and the DB/config backing come in later steps; this
module only names the steps and their sources so the prompt editor can render the recipe and we can co-edit it.

Single source of architecture: OntServe/.claude/plans/extraction-recipe-framework.md (the 12 step-types,
decision 7 ontology-derived ordering, the conform-repair binding gate).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class StepType(str, Enum):
    """The 12 reusable step-types (extraction-recipe-framework.md, decision 2)."""
    ontology_fetch = "ontology-fetch"
    llm_prompt = "llm-prompt"
    parse_schema = "parse->schema"
    filter_validate = "filter/validate"
    transform_canonicalize = "transform/canonicalize"
    reconcile_dedup = "reconcile/dedup"
    synthesize = "synthesize"
    conform_repair = "conform-repair"
    human_gate = "human-gate"
    commit_persist = "commit/persist"
    enrich = "enrich"
    refine = "refine"


@dataclass
class StepDef:
    """One step in a recipe. The `source` names the current implementation that backs it; the interpreter
    will call that code. `is_prompt` marks the llm-prompt step that the prompt editor page is editing."""
    id: str
    type: StepType
    label: str
    source: str
    note: str = ""
    subtype: Optional[str] = None
    is_prompt: bool = False

    @property
    def type_label(self) -> str:
        return self.type.value


@dataclass
class Recipe:
    """A component's extraction recipe (ordered steps). `depends_on` is the ontology-derived component DAG
    (decision 7): which other components must be extracted first."""
    component: str
    symbol: str
    steps: List[StepDef] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)


def role_recipe() -> Recipe:
    """The Role (R) extraction recipe, mapping the live Role pipeline onto the 12 step-types. Declarative
    only for now; `source` points at the code each step will wrap. Ordering note: R is a contextual component
    with no upstream component dependency (depends_on empty); P->O etc. are derived for other components."""
    S = StepType
    return Recipe(
        component="Role", symbol="R", depends_on=[],
        steps=[
            StepDef("fetch", S.ontology_fetch, "Fetch role schema",
                    "external_mcp_client / prompt_building.py",
                    "Load curated role classes; (Phase 2) RoleDefinitionShape + IAO framing from OntServe."),
            StepDef("prompt", S.llm_prompt, "Prompt the LLM",
                    "extraction_prompt_templates id=1 (this page) + config.build_json_wrapper_suffix",
                    "Render the roles template + existing entities + JSON wrapper; stream the call.",
                    subtype="tool-use negotiation (label_only)", is_prompt=True),
            StepDef("parse", S.parse_schema, "Parse to schema",
                    "schemas.CandidateRoleClass / parsing.py",
                    "JSON -> CandidateRoleClass (Pydantic), with truncated-JSON repair."),
            StepDef("filter", S.filter_validate, "Filter / validate",
                    "extractor.py",
                    "Precedent-contamination filter + individual/type filter.",
                    subtype="llm-backed filter"),
            StepDef("canon", S.transform_canonicalize, "Canonicalize labels",
                    "entity_reconciliation_service.canonicalize_labels",
                    "Decompound compound role classes; rewrite labels with the cross-category guard."),
            StepDef("dedup", S.reconcile_dedup, "Reconcile / dedup",
                    "entity_reconciliation_service.py",
                    "Cross-pass many-to-one merge (exact-match + Haiku semantic merge)."),
            StepDef("synth", S.synthesize, "Synthesize edges",
                    "rpo_edges.py / canonicalization.canonicalize_ttl",
                    "Materialize R->P->O hasObligation edges; mint State/Obligation from reference-sheet recipes."),
            StepDef("gate", S.conform_repair, "Conformance gate",
                    "conformance_gate.py -> OntServe repair_conformance_ttl",
                    "Validate->repair vs SHACL/OWL-RL: OWL consistency + case-structure SHACL. THE binding gate."),
            StepDef("review", S.human_gate, "Human review",
                    "pipeline_tasks.py (WAITING_REVIEW)",
                    "Pause for accept/merge/edit (interactive mode; recipe config: on/off)."),
            StepDef("commit", S.commit_persist, "Commit",
                    "ontserve_commit_service.py",
                    "Write TemporaryRDFStorage (intermediate) + OntServe disk TTL + DB sync."),
        ],
    )


# Component -> recipe builder. Only Role exists in Phase 1; the other 8 are added in Phase 4.
RECIPES = {"roles": role_recipe}


def recipe_for_concept(concept: str) -> Optional[Recipe]:
    builder = RECIPES.get(concept)
    return builder() if builder else None
