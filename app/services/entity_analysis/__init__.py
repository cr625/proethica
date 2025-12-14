"""
Entity Analysis Services for ProEthica.

This module provides entity-grounded analysis services that compose
decision points and generate arguments FROM extracted entities rather
than using free-form LLM generation.

Services:
    ObligationCoverageAnalyzer (E1): Analyzes obligation/constraint coverage
    ActionOptionMapper (E2): Maps actions to decision options with intensity scoring
    DecisionPointComposer (E3): Composes entity-grounded decision points
    PrincipleProvisionAligner (F1): Aligns principles with code provisions
    ArgumentGenerator (F2): Generates Toulmin-structured arguments
    ArgumentValidator (F3): Validates arguments using role ethics tests
"""

# E1: Obligation Coverage Analysis
from app.services.entity_analysis.obligation_coverage_analyzer import (
    ObligationCoverageAnalyzer,
    ObligationAnalysis,
    ConstraintAnalysis,
    CoverageMatrix,
    get_obligation_coverage
)

# E2: Action-Option Mapping
from app.services.entity_analysis.action_option_mapper import (
    ActionOptionMapper,
    ActionOption,
    ActionSet,
    ActionOptionMap,
    MoralIntensityScore,
    get_action_option_map
)

# E3: Decision Point Composition
from app.services.entity_analysis.decision_point_composer import (
    DecisionPointComposer,
    EntityGroundedDecisionPoint,
    DecisionPointGrounding,
    DecisionPointOption,
    ComposedDecisionPoints,
    compose_decision_points
)

# F1-F3: To be implemented
# from app.services.entity_analysis.principle_provision_aligner import PrincipleProvisionAligner
# from app.services.entity_analysis.argument_generator import ArgumentGenerator
# from app.services.entity_analysis.argument_validator import ArgumentValidator

__all__ = [
    # E1
    'ObligationCoverageAnalyzer',
    'ObligationAnalysis',
    'ConstraintAnalysis',
    'CoverageMatrix',
    'get_obligation_coverage',
    # E2
    'ActionOptionMapper',
    'ActionOption',
    'ActionSet',
    'ActionOptionMap',
    'MoralIntensityScore',
    'get_action_option_map',
    # E3
    'DecisionPointComposer',
    'EntityGroundedDecisionPoint',
    'DecisionPointGrounding',
    'DecisionPointOption',
    'ComposedDecisionPoints',
    'compose_decision_points',
]
