"""
Synthesis View Builder for the ProEthica user-study interface.

Builds the five synthesis views evaluated in the IRB-approved study:
Provisions, Q&C, Decisions, Timeline, and Narrative.

Split from a single 1,739-line module into a package; the public surface is
unchanged and re-exported below, so `from app.services.validation.synthesis_view_builder
import X` resolves exactly as before. Internals:
  - builder.py        (SynthesisViewBuilder: provisions/qc/decisions/timeline/facts/
                      conclusions views, eligibility, get_all_views orchestrator)
  - narrative_view.py (NarrativeViewMixin: get_narrative_view, Step-4 Phase-4)
  - text_helpers.py   (shared citation regex / stopwords / tokenizer)

`ExtractionPrompt` and `_CITATION_RE` are re-exported here because tests reference
them through this module path (a patch target and a direct import, respectively).
"""

from app.models.extraction_prompt import ExtractionPrompt  # noqa: F401 -- narrative-test patch target
from .text_helpers import _CITATION_RE  # noqa: F401 -- imported directly by integration tests
from .builder import SynthesisViewBuilder

__all__ = ["SynthesisViewBuilder", "ExtractionPrompt", "_CITATION_RE"]
