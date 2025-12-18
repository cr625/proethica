"""
Academic Framework Modules

Each module provides structured access to a specific academic framework:
- Citation information
- Concept definitions with source text
- Indicator patterns
- Functions for generating LLM prompt context
"""

from app.academic_references.frameworks import transformation_classification
from app.academic_references.frameworks import role_ethics
from app.academic_references.frameworks import moral_intensity
from app.academic_references.frameworks import extensional_principles

__all__ = [
    'transformation_classification',
    'role_ethics',
    'moral_intensity',
    'extensional_principles',
]
