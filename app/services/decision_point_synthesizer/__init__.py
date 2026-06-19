"""
Decision Point Synthesizer (Phase 3)

Unified synthesis pipeline that produces canonical decision points from
algorithmic composition (E1-E3), Q&C alignment scoring, LLM refinement with
Toulmin structure, and storage to the database.

Reference: docs-internal/PHASE3_DECISION_POINT_SYNTHESIS_PLAN.md

Split from a single 1,822-line module into a package; the public surface is
unchanged and re-exported below, so `from app.services.decision_point_synthesizer
import X` resolves exactly as before. Internals:
  - models.py       (the data contracts: ToulminStructure / QCAlignmentScore /
                    CanonicalDecisionPoint / Phase3SynthesisResult / SynthesisTrace)
  - synthesizer.py  (DecisionPointSynthesizer + the synthesize_decision_points entry point)
"""

from .models import (
    ToulminStructure,
    QCAlignmentScore,
    CanonicalDecisionPoint,
    Phase3SynthesisResult,
    SynthesisTrace,
)
from .synthesizer import DecisionPointSynthesizer, synthesize_decision_points

__all__ = [
    "ToulminStructure",
    "QCAlignmentScore",
    "CanonicalDecisionPoint",
    "Phase3SynthesisResult",
    "SynthesisTrace",
    "DecisionPointSynthesizer",
    "synthesize_decision_points",
]
