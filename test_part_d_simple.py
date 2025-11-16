"""
Simple test for Part D API call without full Flask app initialization
"""

import sys
import os
import time
from anthropic import Anthropic

# Mock entity class
class MockEntity:
    def __init__(self, label, definition, uri, is_obligation=False):
        self.entity_label = label
        self.entity_definition = definition
        self.entity_uri = uri
        if is_obligation:
            self.rdf_json_ld = {
                'properties': {
                    'obligationStatement': [definition],
                    'derivedFrom': ['III.1.a']
                }
            }
        else:
            self.rdf_json_ld = {'properties': {}}

def build_institutional_prompt(principles, obligations, constraints):
    """Simplified version of _build_analysis_prompt"""

    def format_principles(principles):
        if not principles:
            return "None available"
        lines = []
        for i, p in enumerate(principles[:20], 1):
            label = getattr(p, 'entity_label', 'Unknown')
            definition = getattr(p, 'entity_definition', '')
            uri = getattr(p, 'entity_uri', '')
            lines.append(f"{i}. **{label}**: {definition}\n   URI: {uri}")
        if len(principles) > 20:
            lines.append(f"... and {len(principles) - 20} more")
        return "\n".join(lines)

    def format_obligations(obligations):
        if not obligations:
            return "None available"
        lines = []
        for i, o in enumerate(obligations[:20], 1):
            label = getattr(o, 'entity_label', 'Unknown')
            rdf_data = getattr(o, 'rdf_json_ld', {}) or {}
            props = rdf_data.get('properties', {})
            statement = props.get('obligationStatement', [''])[0] if 'obligationStatement' in props else ''
            code_section = props.get('derivedFrom', [''])[0] if 'derivedFrom' in props else ''
            uri = getattr(o, 'entity_uri', '')
            lines.append(f"{i}. **{label}**: {statement}\n   Code: {code_section}, URI: {uri}")
        if len(obligations) > 20:
            lines.append(f"... and {len(obligations) - 20} more")
        return "\n".join(lines)

    def format_constraints(constraints):
        if not constraints:
            return "None available"
        lines = []
        for i, c in enumerate(constraints[:20], 1):
            label = getattr(c, 'entity_label', 'Unknown')
            definition = getattr(c, 'entity_definition', '')
            uri = getattr(c, 'entity_uri', '')
            lines.append(f"{i}. **{label}**: {definition}\n   URI: {uri}")
        if len(constraints) > 20:
            lines.append(f"... and {len(constraints) - 20} more")
        return "\n".join(lines)

    prompt = f"""Analyze the institutional rules (normative framework) for this engineering ethics case.

**Context**: Professional engineering ethics case published by NSPE Board of Ethical Review.

**Available Principles** ({len(principles)} total):
{format_principles(principles)}

**Available Obligations** ({len(obligations)} total):
{format_obligations(obligations)}

**Available Constraints** ({len(constraints)} total):
{format_constraints(constraints)}

**Task**: Identify the institutional rule structure that makes this case ethically significant.

**Analysis Questions**:
1. Which principles are in tension? (not just mentioned, but actually conflicting)
2. Which professional obligations conflict? (competing duties from NSPE Code)
3. What constraints shaped the decision space? (legal, professional, organizational limits)
4. Why did the NSPE Board publish this case? What strategic ethical issue does it represent?

**Output Format** (JSON only, no markdown):
{{
  "principle_tensions": [
    {{
      "principle1": "Principle Name",
      "principle1_uri": "uri",
      "principle2": "Principle Name 2",
      "principle2_uri": "uri",
      "tension_description": "Clear description of how these principles create ethical tension",
      "symbolic_significance": "What this tension represents for the profession"
    }}
  ],
  "principle_conflict_description": "Overall narrative of how principles structure this case",
  "obligation_conflicts": [
    {{
      "obligation1": "Obligation Name",
      "obligation1_uri": "uri",
      "obligation1_code_section": "III.2.a",
      "obligation2": "Obligation Name 2",
      "obligation2_uri": "uri",
      "obligation2_code_section": "III.9",
      "conflict_description": "How these obligations conflict in this case"
    }}
  ],
  "obligation_conflict_description": "Overall narrative of obligation tensions",
  "constraining_factors": [
    {{
      "constraint": "Constraint Name",
      "constraint_uri": "uri",
      "constraint_type": "legal|professional|organizational|resource",
      "impact_description": "How this constraint shaped choices"
    }}
  ],
  "constraint_influence_description": "How constraints shaped the decision space",
  "case_significance": "Why this case matters - what strategic ethical issue it represents for professional engineering practice"
}}

Respond with valid JSON only. Focus on ACTUAL tensions and conflicts, not just lists of concepts."""

    return prompt

def test_api_call():
    """Test the API call with mock data"""

    print("=" * 80)
    print("TESTING PART D: INSTITUTIONAL RULE ANALYZER API CALL")
    print("=" * 80)

    # Create mock entities (similar size to real Case 8 data)
    print("\n[1] Creating mock entities...")
    principles = [
        MockEntity(
            f"Principle_{i}",
            f"Definition for principle {i} " * 20,  # ~400 chars each
            f"http://proethica.org/ontology/case/8#Principle_{i}"
        )
        for i in range(13)
    ]

    obligations = [
        MockEntity(
            f"Obligation_{i}",
            f"Obligation statement {i} " * 20,  # ~400 chars each
            f"http://proethica.org/ontology/case/8#Obligation_{i}",
            is_obligation=True
        )
        for i in range(13)
    ]

    constraints = [
        MockEntity(
            f"Constraint_{i}",
            f"Definition for constraint {i} " * 20,  # ~400 chars each
            f"http://proethica.org/ontology/case/8#Constraint_{i}"
        )
        for i in range(11)
    ]

    print(f"    Principles: {len(principles)}")
    print(f"    Obligations: {len(obligations)}")
    print(f"    Constraints: {len(constraints)}")

    # Build prompt
    print("\n[2] Building LLM prompt...")
    prompt = build_institutional_prompt(principles, obligations, constraints)

    print(f"    Prompt size: {len(prompt)} characters")
    print(f"    Prompt size: {len(prompt.encode('utf-8'))} bytes")

    # Get API key
    print("\n[3] Checking Anthropic API configuration...")
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("    ERROR: ANTHROPIC_API_KEY not set in environment!")
        return False

    print(f"    API key found: {api_key[:10]}...{api_key[-4:]}")

    # Create client
    print("\n[4] Creating Anthropic client...")
    client = Anthropic(api_key=api_key)
    print(f"    Client base URL: {client.base_url}")
    print(f"    Client timeout: {client.timeout}")
    print(f"    Client max retries: {client.max_retries}")

    # Make API call
    print("\n[5] Making API call to /v1/messages...")
    print(f"    Endpoint: {client.base_url}/v1/messages")
    print(f"    Model: claude-sonnet-4-5-20250929")
    print(f"    Max tokens: 4000")
    print(f"    Waiting for response...")

    start_time = time.time()

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        elapsed = time.time() - start_time

        print(f"\n[6] ✓ API call successful!")
        print(f"    Time elapsed: {elapsed:.2f} seconds")
        print(f"    Response ID: {response.id}")
        print(f"    Response model: {response.model}")
        print(f"    Stop reason: {response.stop_reason}")
        print(f"    Input tokens: {response.usage.input_tokens}")
        print(f"    Output tokens: {response.usage.output_tokens}")

        response_text = response.content[0].text
        print(f"    Response length: {len(response_text)} characters")
        print(f"\n    Response preview (first 500 chars):")
        print(f"    {response_text[:500]}")

        return True

    except Exception as e:
        elapsed = time.time() - start_time

        print(f"\n[6] ✗ API call FAILED!")
        print(f"    Time elapsed: {elapsed:.2f} seconds")
        print(f"    Error type: {type(e).__name__}")
        print(f"    Error message: {str(e)}")

        import traceback
        print(f"\n    Full traceback:")
        traceback.print_exc()

        return False

if __name__ == '__main__':
    success = test_api_call()

    print("\n" + "=" * 80)
    if success:
        print("TEST PASSED ✓")
    else:
        print("TEST FAILED ✗")
    print("=" * 80)

    sys.exit(0 if success else 1)
