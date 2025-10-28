"""
Scenario Generation Service

Transforms fully-analyzed cases into interactive teaching scenarios.

Architecture: 9-stage pipeline
1. Eligibility Check & Data Collection
2. Timeline Construction
3. Participant Mapping
4. Decision Point Identification
5. Causal Chain Integration
6. Normative Framework Integration
7. Scenario Assembly & Enrichment
8. Interactive Scenario Model Generation
9. Validation & Quality Assurance

Documentation: docs/SCENARIO_GENERATION_FROM_EXTRACTED_ENTITIES_PLAN.md
Cross-Reference: docs/SCENARIO_GENERATION_CROSS_REFERENCE.md
"""

from .data_collection import ScenarioDataCollector
from .orchestrator import ScenarioGenerationOrchestrator
from .models import (
    ScenarioSourceData,
    RDFEntity,
    TemporalDynamicsData,
    SynthesisData,
    EligibilityReport
)

__all__ = [
    'ScenarioDataCollector',
    'ScenarioGenerationOrchestrator',
    'ScenarioSourceData',
    'RDFEntity',
    'TemporalDynamicsData',
    'SynthesisData',
    'EligibilityReport'
]
