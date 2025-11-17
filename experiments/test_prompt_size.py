"""
Quick test to check institutional analyzer prompt size
"""

import sys
sys.path.insert(0, '/home/chris/onto/proethica')

# Mock entity class
class MockEntity:
    def __init__(self, label, definition, uri):
        self.entity_label = label
        self.entity_definition = definition
        self.entity_uri = uri
        self.rdf_json_ld = {
            'properties': {
                'obligationStatement': ['Test obligation statement'],
                'derivedFrom': ['III.1.a']
            }
        }

# Create mock entities
principles = [MockEntity(f"Principle {i}", f"Definition for principle {i}" * 10, f"uri:principle:{i}") for i in range(13)]
obligations = [MockEntity(f"Obligation {i}", f"Definition for obligation {i}" * 10, f"uri:obligation:{i}") for i in range(13)]
constraints = [MockEntity(f"Constraint {i}", f"Definition for constraint {i}" * 10, f"uri:constraint:{i}") for i in range(11)]

# Import the analyzer class (just the class, not the full app)
from app.services.case_analysis.institutional_rule_analyzer import InstitutionalRuleAnalyzer

# Create analyzer (will fail on LLM init, but that's ok)
try:
    analyzer = InstitutionalRuleAnalyzer()
except Exception as e:
    print(f"Expected LLM init error: {e}")
    # Create a minimal instance
    class MinimalAnalyzer:
        def _format_principles(self, principles):
            from app.services.case_analysis.institutional_rule_analyzer import InstitutionalRuleAnalyzer
            return InstitutionalRuleAnalyzer._format_principles(self, principles)

        def _format_obligations(self, obligations):
            from app.services.case_analysis.institutional_rule_analyzer import InstitutionalRuleAnalyzer
            return InstitutionalRuleAnalyzer._format_obligations(self, obligations)

        def _format_constraints(self, constraints):
            from app.services.case_analysis.institutional_rule_analyzer import InstitutionalRuleAnalyzer
            return InstitutionalRuleAnalyzer._format_constraints(self, constraints)

        def _build_analysis_prompt(self, principles, obligations, constraints, case_context):
            from app.services.case_analysis.institutional_rule_analyzer import InstitutionalRuleAnalyzer
            return InstitutionalRuleAnalyzer._build_analysis_prompt(self, principles, obligations, constraints, case_context)

    analyzer = MinimalAnalyzer()

# Build prompt
prompt = analyzer._build_analysis_prompt(principles, obligations, constraints, None)

print(f"\n=== PROMPT ANALYSIS ===")
print(f"Prompt size: {len(prompt)} characters")
print(f"Prompt size: {len(prompt.encode('utf-8'))} bytes")
print(f"\n=== FIRST 1000 CHARACTERS ===")
print(prompt[:1000])
print(f"\n=== LAST 500 CHARACTERS ===")
print(prompt[-500:])
