"""
Synthesis Module

Unified extraction and synthesis pipeline for Step 4.
Each phase has extractors that can:
- Yield progress events (for SSE streaming)
- Execute and return results (for non-streaming)
- Store to database

Architecture:
- Phase 2: Provisions, Questions, Conclusions, Transformation, Rich Analysis
- Phase 3: Decision Point Synthesis
- Phase 4: Narrative Construction (delegates to app/services/narrative/)
"""

from .base import (
    SynthesisEvent,
    SynthesisResult,
    BaseSynthesizer,
)

from .phase2_extractor import (
    Phase2Extractor,
    Phase2Result,
    extract_phase2,
    extract_phase2_streaming,
)

__all__ = [
    # Base classes
    'SynthesisEvent',
    'SynthesisResult',
    'BaseSynthesizer',

    # Phase 2
    'Phase2Extractor',
    'Phase2Result',
    'extract_phase2',
    'extract_phase2_streaming',
]
