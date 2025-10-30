"""
Step 4: Enhanced Case Analysis Services

Provides comprehensive case-level analysis services for understanding
ethical reasoning in professional engineering cases.

Theoretical foundations:
- Marchais-Roubelat & Roubelat (2015): Action-based scenario analysis
- Sohrabi et al. (2018): AI planning for scenario generation

Components:
- InstitutionalRuleAnalyzer: Analyze P, O, Cs tensions
- ActionRuleMapper: Map three-rule framework  
- TransformationClassifier: Classify case transformation type
"""

from .institutional_rule_analyzer import InstitutionalRuleAnalyzer

__all__ = ['InstitutionalRuleAnalyzer']
