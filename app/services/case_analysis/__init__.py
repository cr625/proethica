"""
Case Analysis Services

Deep analysis services for Step 4 Enhanced Synthesis:
- TransformationClassifier: Classify case transformation type
- InstitutionalRuleAnalyzer: Analyze principle tensions and obligation conflicts (planned)
- ActionRuleMapper: Map actions to institutional rules (planned)
"""

from .transformation_classifier import TransformationClassifier, TransformationResult

__all__ = ['TransformationClassifier', 'TransformationResult']
