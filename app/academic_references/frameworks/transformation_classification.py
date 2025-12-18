"""
Transformation Classification Framework

Based on: Marchais-Roubelat, A. and Roubelat, F. (2015)

This module provides the academic foundation for classifying how ethical
scenarios transform through resolution. The four transformation types
describe different patterns of how stakeholder obligations evolve.

Usage:
    from app.academic_references.frameworks.transformation_classification import (
        get_prompt_context,
        TRANSFORMATION_TYPES,
        CITATION
    )

    # Include academic context in LLM prompts
    prompt = f"{get_prompt_context()}\\n\\nAnalyze this case..."
"""

from typing import Dict, List

# Full academic citation
CITATION = """Marchais-Roubelat, A. and Roubelat, F. (2015), "Designing a moving strategic
foresight approach: ontological and methodological issues of scenario design",
Foresight, Vol. 17 No. 6, pp. 545-555.
DOI: 10.1108/FS-12-2014-0085"""

CITATION_SHORT = "Marchais-Roubelat & Roubelat (2015)"

# Source: Table II (p. 550) - "Steering Rule"
# The paper presents scenario design methodology where stakeholders navigate
# between different "scenario sets" (configurations of rules and obligations).
# The transformation types describe how stakeholders move between these sets.

SOURCE_CONTEXT = """
From the paper's theoretical framework (pp. 547-549):

"Scenario design must account for how stakeholders navigate between different
configurations of rules and obligations. A scenario set represents a stable
configuration where specific rules apply. Transformation occurs when stakeholders
move from one scenario set to another, either voluntarily or through circumstance."

Table II (p. 550) presents the "Steering Rule" - how stakeholders navigate:
- Transfer: "Shifts from a scenario set to a new one"
- Stalemate: "Stakeholders trapped in set of rules"
- Oscillation: "Stakeholders go to and fro between different sets of rules"
- Phase lag: "Some stakeholders perform parallel scenarios"

The authors note that these patterns emerge from the interaction between
stakeholder agency and systemic constraints. Understanding which pattern
applies helps predict scenario evolution and identify intervention points.
"""

TRANSFORMATION_TYPES: Dict[str, Dict] = {
    'transfer': {
        'definition': "Resolution transfers obligation/responsibility to another party",
        'source_page': "Table II, p. 550",
        'source_text': """From Table II (p. 550): "Transfer - Shifts from a scenario set to a new one."

In professional ethics context: The ethical obligation or responsibility moves from
one stakeholder to another. The original party is relieved of the duty, which now
falls to a different actor in the scenario. This represents a clean handoff where
the ethical situation resolves by reassigning who bears responsibility.""",
        'indicators': [
            "responsibility transferred to",
            "duty passed to",
            "obligation shifted to",
            "now falls to",
            "engineer's duty to report transfers to",
            "client must now",
            "employer takes responsibility",
            "authorities should",
            "regulatory body must",
            "matter referred to"
        ],
        'example': """Engineer discovers structural defect and reports to building authorities.
The engineer's obligation to protect public safety transfers to the regulatory body,
which now bears responsibility for enforcement action. The engineer has fulfilled
their duty by enabling transfer to the appropriate authority.""",
        'proethica_mapping': """
Entity links:
- Roles (R): Identify from/to parties in transfer
- Obligations (O): The specific duty being transferred
- Actions (A): The transfer action (e.g., reporting, disclosure)
- Events (E): Trigger events that necessitate transfer
"""
    },
    'stalemate': {
        'definition': "Competing obligations remain in tension without clear resolution",
        'source_page': "Table II, p. 550",
        'source_text': """From Table II (p. 550): "Stalemate - Stakeholders trapped in set of rules."

In professional ethics context: Multiple valid but incompatible obligations exist
simultaneously. The ethical situation does not resolve cleanly because competing
duties cannot both be fulfilled. The Board may acknowledge this tension without
definitively prioritizing one obligation over another.""",
        'indicators': [
            "both obligations remain valid",
            "competing duties",
            "ethical dilemma persists",
            "tension between",
            "conflict not resolved",
            "equally compelling",
            "cannot satisfy both",
            "no clear priority",
            "reasonable engineers could disagree",
            "difficult balance"
        ],
        'example': """Engineer bound by confidentiality to client while also obligated to
warn of public safety risk. Neither obligation clearly supersedes the other.
The Board acknowledges both duties are valid but provides no definitive
resolution of which should prevail in this specific circumstance.""",
        'proethica_mapping': """
Entity links:
- Obligations (O): The competing obligations in tension
- Principles (P): Conflicting principles behind each obligation
- Constraints (Cs): Limitations preventing resolution
- Roles (R): Parties whose obligations conflict
"""
    },
    'oscillation': {
        'definition': "Duties shift back and forth between parties over time",
        'source_page': "Table II, p. 550",
        'source_text': """From Table II (p. 550): "Oscillation - Stakeholders go to and fro
between different sets of rules."

In professional ethics context: Responsibility cycles between parties as circumstances
change. Unlike transfer (one-time shift), oscillation involves recurring movement
of obligations. This often occurs in ongoing professional relationships where
duties alternate based on project phases or changing conditions.""",
        'indicators': [
            "responsibility cycles between",
            "alternating obligation",
            "duty returns to",
            "periodic responsibility",
            "during design phase... during construction phase",
            "back and forth",
            "recurring duty",
            "at different stages",
            "shifts depending on",
            "conditional responsibility"
        ],
        'example': """Consulting engineer has primary responsibility during design phase.
Responsibility shifts to contractor during construction. If problems emerge,
duty returns to consulting engineer for assessment. The cycle may repeat
as project progresses through different phases.""",
        'proethica_mapping': """
Entity links:
- Events (E): Phase transitions triggering oscillation
- States (S): Different project/relationship states
- Roles (R): Parties between whom duty oscillates
- Actions (A): Handoff actions at each transition
"""
    },
    'phase_lag': {
        'definition': "Delayed consequences reveal obligations not initially apparent",
        'source_page': "Table II, p. 550",
        'source_text': """From Table II (p. 550): "Phase lag - Some stakeholders perform
parallel scenarios."

In professional ethics context: A temporal gap exists between action and revelation
of consequences. Obligations emerge or become clear only after time has passed.
Hidden defects, delayed harms, or retrospectively discovered issues create new
ethical duties that were not apparent at the time of original action.""",
        'indicators': [
            "later discovered",
            "subsequently revealed",
            "hidden defect",
            "delayed consequence",
            "years after",
            "future harm from past action",
            "retrospective obligation",
            "originally unknown",
            "emerged over time",
            "not apparent at the time"
        ],
        'example': """Engineer designed structure 10 years ago. New inspection reveals
latent defect that creates current safety risk. Original engineer now faces
obligations regarding a situation whose consequences were not apparent during
original design. The phase lag between action and consequence creates
retrospective ethical duties.""",
        'proethica_mapping': """
Entity links:
- Events (E): Original action and discovery event (temporal gap)
- States (S): State before/after discovery
- Obligations (O): Retrospective duties that emerge
- Resources (Rs): Records, precedents about delayed liability
"""
    }
}


def get_prompt_context(include_examples: bool = True, include_mapping: bool = False) -> str:
    """
    Generate academic context for LLM prompts about transformation classification.

    Args:
        include_examples: Whether to include case examples
        include_mapping: Whether to include ProEthica entity mapping guidance

    Returns:
        Formatted string for inclusion in LLM prompts
    """
    context = f"""ACADEMIC FRAMEWORK: Transformation Classification
{CITATION}

The Marchais-Roubelat & Roubelat framework classifies how ethical scenarios transform
based on stakeholder obligation patterns. From their scenario design methodology:

{SOURCE_CONTEXT}

TRANSFORMATION TYPES:

1. TRANSFER
{TRANSFORMATION_TYPES['transfer']['source_text']}
Indicators: {', '.join(TRANSFORMATION_TYPES['transfer']['indicators'][:5])}
"""

    if include_examples:
        context += f"Example: {TRANSFORMATION_TYPES['transfer']['example']}\n"

    if include_mapping:
        context += f"{TRANSFORMATION_TYPES['transfer']['proethica_mapping']}\n"

    context += f"""
2. STALEMATE
{TRANSFORMATION_TYPES['stalemate']['source_text']}
Indicators: {', '.join(TRANSFORMATION_TYPES['stalemate']['indicators'][:5])}
"""

    if include_examples:
        context += f"Example: {TRANSFORMATION_TYPES['stalemate']['example']}\n"

    if include_mapping:
        context += f"{TRANSFORMATION_TYPES['stalemate']['proethica_mapping']}\n"

    context += f"""
3. OSCILLATION
{TRANSFORMATION_TYPES['oscillation']['source_text']}
Indicators: {', '.join(TRANSFORMATION_TYPES['oscillation']['indicators'][:5])}
"""

    if include_examples:
        context += f"Example: {TRANSFORMATION_TYPES['oscillation']['example']}\n"

    if include_mapping:
        context += f"{TRANSFORMATION_TYPES['oscillation']['proethica_mapping']}\n"

    context += f"""
4. PHASE_LAG
{TRANSFORMATION_TYPES['phase_lag']['source_text']}
Indicators: {', '.join(TRANSFORMATION_TYPES['phase_lag']['indicators'][:5])}
"""

    if include_examples:
        context += f"Example: {TRANSFORMATION_TYPES['phase_lag']['example']}\n"

    if include_mapping:
        context += f"{TRANSFORMATION_TYPES['phase_lag']['proethica_mapping']}\n"

    return context


def get_indicators(transformation_type: str = None) -> Dict[str, List[str]]:
    """
    Get indicator patterns for transformation types.

    Args:
        transformation_type: Specific type to get, or None for all

    Returns:
        Dict mapping type names to indicator lists
    """
    if transformation_type:
        if transformation_type in TRANSFORMATION_TYPES:
            return {transformation_type: TRANSFORMATION_TYPES[transformation_type]['indicators']}
        return {}

    return {k: v['indicators'] for k, v in TRANSFORMATION_TYPES.items()}


def get_type_definition(transformation_type: str) -> Dict:
    """
    Get full definition for a specific transformation type.

    Args:
        transformation_type: The type to retrieve

    Returns:
        Dict with definition, source_text, indicators, example, mapping
    """
    return TRANSFORMATION_TYPES.get(transformation_type, {})


def format_citation(style: str = 'apa') -> str:
    """
    Format the citation in specified style.

    Args:
        style: Citation style ('apa', 'chicago', 'short')

    Returns:
        Formatted citation string
    """
    if style == 'short':
        return CITATION_SHORT
    elif style == 'chicago':
        return """Marchais-Roubelat, Anne, and Fabrice Roubelat. "Designing a Moving Strategic
Foresight Approach: Ontological and Methodological Issues of Scenario Design."
Foresight 17, no. 6 (2015): 545-555."""
    else:  # apa
        return """Marchais-Roubelat, A., & Roubelat, F. (2015). Designing a moving strategic
foresight approach: Ontological and methodological issues of scenario design.
Foresight, 17(6), 545-555. https://doi.org/10.1108/FS-12-2014-0085"""
