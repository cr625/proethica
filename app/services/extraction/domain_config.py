"""Domain-config seam: the per-domain parameters of the extraction pipeline.

A second professional-ethics domain (legal ethics) is onboarded by adding a `DomainConfig` instance
here plus a reference-sheet directory, a domain ontology, and `domain='legal'` prompt rows. The
nine-component upper model and the core property vocabulary stay shared (see `core_vocab.py`).

Scope note (2026-06-24): this seam is the home for the domain parameters the NEW canonicalization code
reads. The existing extractor still has its own copies of the namespace constants (schemas.py,
ontserve_commit_service.py, etc.); re-pointing those at this seam is the documented legal-ethics
onboarding refactor (see `.claude/plans/domain-config-seam-design.md` and `legal-ethics-expansion.md`).
The ENGINEERING values below are byte-identical to those existing constants, so there is no drift.

Per the global "no fallbacks in development" rule, an unknown domain selection RAISES; it never
silently falls back to engineering.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

try:  # works both as a package member (live extractor) and as a standalone file (tooling/judge)
    from .core_vocab import COMPONENTS
except ImportError:  # pragma: no cover - tooling path
    from core_vocab import COMPONENTS

# IRI local-name sanitizer; mirrors extraction_graph._sanitize_label (spaces -> sep, strip punctuation).
_STRIP = str.maketrans({c: None for c in '()"\'<>&,'})


def sanitize(label: str, sep: str = "") -> str:
    return (label or "").translate(_STRIP).replace(" ", sep).strip()


@dataclass(frozen=True)
class DomainConfig:
    domain_label: str                      # the prompt-set selector + the OntServe attribution tag
    core_ns: str                           # Tier B: usually shared (the upper model)
    intermediate_ns: str                   # Tier A: per-domain
    cases_ns: str
    prov_ns: str                           # Tier B: usually shared
    case_iri_template: str                 # uses {case_id} and {frag}
    ont_names: dict                        # core / intermediate / extended / case_prefix OntServe names
    ontserve_domain_name: str              # the `domains` row name (commit hard-requires it to exist)
    reference_sheet_dir: str
    embedding_model: str                   # Tier B
    match_thresholds: dict                 # Tier B (HIGH/MEDIUM/EXACT/SUBSTRING; recalibrate per domain only if needed)

    # --- IRI minting helpers (the single place the new code mints under a domain's namespaces) ---
    def class_iri(self, label: str) -> str:
        return f"{self.intermediate_ns}{sanitize(label, sep='')}"

    def case_iri(self, case_id, frag: str) -> str:
        return self.case_iri_template.format(case_id=case_id, frag=sanitize(frag, sep="_"))

    def core(self, local_name: str) -> str:
        return f"{self.core_ns}{local_name}"

    def intermediate(self, local_name: str) -> str:
        return f"{self.intermediate_ns}{local_name}"

    @property
    def components(self) -> tuple:
        return COMPONENTS


# ----------------------------------------------------------------------------
# Registered domains
# ----------------------------------------------------------------------------
ENGINEERING = DomainConfig(
    domain_label="engineering",
    core_ns="http://proethica.org/ontology/core#",
    intermediate_ns="http://proethica.org/ontology/intermediate#",
    cases_ns="http://proethica.org/ontology/cases#",
    prov_ns="http://proethica.org/provenance#",
    case_iri_template="http://proethica.org/ontology/case/{case_id}#{frag}",
    ont_names={
        "core": "proethica-core",
        "intermediate": "proethica-intermediate",
        "extended": "proethica-intermediate-extended",
        "case_prefix": "proethica-case-",
    },
    ontserve_domain_name="engineering-ethics",
    reference_sheet_dir=os.environ.get(
        "REFERENCE_SHEET_DIR", "/home/chris/onto/OntServe/ontologies/reference-sheet"
    ),
    embedding_model=os.environ.get("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
    match_thresholds={"HIGH": 0.85, "MEDIUM": 0.70, "EXACT": 1.0, "SUBSTRING": 0.87},
)

# Legal ethics is NOT registered yet (no ontology / sheet / prompt rows). When onboarded, add a
# DomainConfig('legal', intermediate_ns='http://legalethics.org/ontology/intermediate#', ...) here.
_DOMAINS: dict[str, DomainConfig] = {
    "engineering": ENGINEERING,
}


def active_domain() -> DomainConfig:
    """The DomainConfig for the current run. Selected by env PROETHICA_DOMAIN (default engineering).
    Raises on an unknown domain (no silent fallback)."""
    name = os.environ.get("PROETHICA_DOMAIN", "engineering").strip().lower()
    try:
        return _DOMAINS[name]
    except KeyError:
        raise ValueError(
            f"Unknown extraction domain {name!r}; registered domains: {sorted(_DOMAINS)}. "
            f"Register a DomainConfig in domain_config.py before selecting it."
        )


__all__ = ["DomainConfig", "ENGINEERING", "active_domain", "sanitize"]
