"""
Case Synthesizer (Step 4) -- unified case synthesis pipeline.

Split from a single 1,514-line module into a package; the public surface is
unchanged and re-exported below, so `from app.services.case_synthesizer import X`
resolves exactly as before. This includes the case_synthesis_models dataclasses,
which this module has always re-exported for backward compatibility (consumers
import EntityFoundation / CaseNarrative / CaseSynthesisModel / ... from here).

Internals:
  - synthesizer.py  (CaseSynthesizer orchestrator + entity/QC loaders + Phase-2
                    extraction + the synthesize_case entry point)
  - narrative.py    (NarrativeConstructionMixin: Phase-4 narrative construction)
"""

from app.services.case_synthesis_models import (  # noqa: F401 -- re-exported for backward compatibility
    EntitySummary, EntityFoundation, TimelineEvent, ScenarioSeeds,
    CaseNarrative, LLMTrace, CausalNormativeLink, QuestionEmergenceAnalysis,
    ResolutionPatternAnalysis, TransformationAnalysis, CaseSynthesisModel,
    SynthesisResult,
)
from .synthesizer import CaseSynthesizer, synthesize_case

__all__ = [
    "CaseSynthesizer",
    "synthesize_case",
    "EntitySummary",
    "EntityFoundation",
    "TimelineEvent",
    "ScenarioSeeds",
    "CaseNarrative",
    "LLMTrace",
    "CausalNormativeLink",
    "QuestionEmergenceAnalysis",
    "ResolutionPatternAnalysis",
    "TransformationAnalysis",
    "CaseSynthesisModel",
    "SynthesisResult",
]
