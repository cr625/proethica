from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence


# ---- Data contracts (DTOs) ----

@dataclass
class ConceptCandidate:
    label: str
    description: Optional[str] = None
    primary_type: Optional[str] = None  # e.g., 'role', 'obligation', 'principle'
    category: Optional[str] = None
    spans: Optional[List[Dict[str, Any]]] = None  # e.g., [{"start": 0, "end": 20, "section": "Responsibilities"}]
    confidence: Optional[float] = None
    debug: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MatchedConcept:
    candidate: ConceptCandidate
    ontology_match: Optional[Dict[str, Any]] = None  # e.g., {"uri": str, "label": str, "score": float}
    chosen_parent: Optional[str] = None
    similarity: Optional[float] = None
    normalized_label: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class SemanticTriple:
    subject_uri: str
    predicate_uri: str
    object_uri: str
    context: Dict[str, Any] = field(default_factory=dict)
    is_approved: bool = False


# ---- Interfaces ----

class Extractor(Protocol):
    def extract(self, text: str, *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        ...


class PostProcessor(Protocol):
    def process(self, candidates: Sequence[ConceptCandidate]) -> List[ConceptCandidate]:
        ...


class Matcher(Protocol):
    def match(self, candidates: Sequence[ConceptCandidate], *, world_id: Optional[int] = None) -> List[MatchedConcept]:
        ...


class Linker(Protocol):
    def link(self, matches: Sequence[MatchedConcept], *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[SemanticTriple]:
        ...


# ---- Utilities: simple base implementations ----

class NoopPostProcessor(PostProcessor):
    def process(self, candidates: Sequence[ConceptCandidate]) -> List[ConceptCandidate]:
        return list(candidates)


class NoopMatcher(Matcher):
    def match(self, candidates: Sequence[ConceptCandidate], *, world_id: Optional[int] = None) -> List[MatchedConcept]:
        return [MatchedConcept(candidate=c) for c in candidates]
