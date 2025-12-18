"""
Academic References Library

Provides structured access to academic frameworks used in ProEthica analysis.
Each framework module contains:
- Full academic citation
- Concept definitions with source text
- Indicator patterns for detection
- Prompt context functions for LLM integration

Frameworks Available:
- transformation_classification: Marchais-Roubelat & Roubelat (2015) scenario transformations
- role_ethics: Oakley & Cocking (2001) virtue ethics and professional roles
- moral_intensity: Jones (1991) issue-contingent ethical decision model
- extensional_principles: McLaren (2003) case-based ethical reasoning
- argument_structure: Toulmin argument model
- line_drawing: Harris et al. line-drawing methodology
"""

from app.academic_references.frameworks import (
    transformation_classification,
    role_ethics,
    moral_intensity,
    extensional_principles,
)

__all__ = [
    'transformation_classification',
    'role_ethics',
    'moral_intensity',
    'extensional_principles',
]
