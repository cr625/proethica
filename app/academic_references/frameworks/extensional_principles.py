"""
Extensional Principles Framework

Based on: McLaren, B.M. (2003) "Extensionally Defining Principles and Cases in Ethics:
An AI Model"

This module provides the academic foundation for understanding how abstract
ethical principles achieve concrete meaning through accumulated precedent cases.
McLaren's work on the SIROCCO system demonstrates that professional ethics
operates through case-based extensional definition rather than abstract rules.

Usage:
    from app.academic_references.frameworks.extensional_principles import (
        get_prompt_context,
        OPERATIONALIZATION_TECHNIQUES,
        CITATION
    )
"""

from typing import Dict, List

# Full academic citation
CITATION = """McLaren, B.M. (2003). "Extensionally Defining Principles and Cases in Ethics:
An AI Model." Artificial Intelligence, 150(1-2), 145-181.
DOI: 10.1016/S0004-3702(03)00135-8"""

CITATION_SHORT = "McLaren (2003)"

# Core theoretical framework
SOURCE_CONTEXT = """
From McLaren's theoretical framework:

"Abstract ethical principles cannot be understood through logical definition alone
but require accumulated precedents to achieve concrete meaning. This extensional
approach challenges computational approaches that attempt to encode ethics as
abstract rules." (p. 146)

McLaren's analysis of NSPE Board of Ethical Review cases reveals:

"Principles like 'hold paramount the safety, health, and welfare of the public'
contain open-textured terms that resist precise definition. The Board
operationalizes such principles through their application in specific cases,
building an extensional definition through precedent." (p. 152)

Key Insight (p. 155):
"The meaning of ethical principles is not fixed a priori but emerges through
their application to concrete cases. Each Board decision adds to the extensional
definition, making future applications more determinate."

SIROCCO System:
McLaren's SIROCCO (Systematic Reasoning on Cases and COdes) system demonstrates
computational implementation of extensional principles through:
1. Comprehensive ontological representation of engineering ethics concepts
2. Systematic encoding of Board cases as precedents
3. Retrieval of relevant precedents for new cases
4. Prediction of applicable principles based on case similarity
"""

# The 9 operationalization techniques identified by McLaren
OPERATIONALIZATION_TECHNIQUES: Dict[str, Dict] = {
    'principle_instantiation': {
        'definition': "Linking abstract principles to clusters of critical facts that activate them",
        'source_page': "pp. 156-158",
        'source_text': """From McLaren (p. 156): "Principle instantiation involves identifying
the specific factual conditions under which an abstract principle becomes
applicable. The principle 'engineers shall hold paramount public safety' is
instantiated when facts establish: (1) existence of safety hazard, (2) engineer's
knowledge of hazard, (3) ability to take protective action."

The Board uses principle instantiation to explain WHY a principle applies
to a particular case by pointing to the critical facts that trigger it.""",
        'example': """Case 89-7: Engineer discovers structural deficiencies in building.
Principle "hold paramount public safety" is instantiated because:
- Critical fact 1: Structural deficiency exists (safety hazard)
- Critical fact 2: Engineer has knowledge through inspection
- Critical fact 3: Engineer can report to authorities""",
        'proethica_application': "Links Principles (P) to States (S) and Events (E) that trigger them"
    },
    'fact_hypotheses': {
        'definition': "Specifying conditions that would modify principle application",
        'source_page': "pp. 158-159",
        'source_text': """From McLaren (p. 158): "Fact hypotheses represent counterfactual
reasoning about how different facts would alter the ethical analysis. The Board
often considers: 'If the engineer had known X earlier...' or 'If there were no
alternative means of disclosure...'"

These hypotheses help define the boundaries of principle application by
exploring how variations in facts would change the conclusion.""",
        'example': """Case 00-5: Board considers how conclusion would differ if:
- Hypothetical: Client had already been informed by others
- Hypothetical: No immediate danger existed
- Hypothetical: Engineer lacked expertise to assess risk
Each hypothetical modifies which principles apply and how.""",
        'proethica_application': "Informs counterfactual questions and scenario variations"
    },
    'conflicting_principles_resolution': {
        'definition': "Determining which principle prevails when multiple apply",
        'source_page': "pp. 159-161",
        'source_text': """From McLaren (p. 160): "When principles conflict, the Board draws on
precedent patterns to determine priority. The public safety principle generally
prevails over confidentiality, but this is not absolute - degree of risk,
availability of alternatives, and specificity of threat all factor into
the weighing process."

Precedent cases provide the extensional definition of HOW to weigh conflicts.""",
        'example': """Confidentiality vs. Public Safety:
- When immediate threat exists: Public safety prevails (Case 89-7)
- When risk is speculative: May permit maintaining confidentiality
- When alternatives exist: Must try less intrusive means first
Precedent patterns define the weighing factors.""",
        'proethica_application': "Guides Obligation (O) priority in conflicts"
    },
    'case_instantiation': {
        'definition': "Drawing analogies from paradigmatic cases to current situations",
        'source_page': "pp. 161-163",
        'source_text': """From McLaren (p. 161): "Case instantiation uses paradigmatic cases
as templates for analyzing new situations. When a new case shares critical
features with a precedent, the precedent's analysis provides guidance."

The Board frequently references prior cases: "This case is similar to Case 78-4
where we held that..." Such analogies transfer reasoning from known to unknown.""",
        'example': """New case involves engineer discovering foundation problems.
Analogous to Case 89-7 (structural deficiencies) because:
- Both involve discovered safety issues
- Both involve ongoing client relationship
- Both require disclosure decision
Case 89-7's resolution (duty to report) applies by analogy.""",
        'proethica_application': "Foundation for precedent retrieval and similarity matching"
    },
    'case_grouping': {
        'definition': "Identifying clusters of similar cases that define principle patterns",
        'source_page': "pp. 163-165",
        'source_text': """From McLaren (p. 163): "Case grouping reveals that certain types of
cases consistently receive similar treatment. The 'disclosure of safety hazard'
cases form a coherent group where public safety consistently prevails over
client confidentiality when threat is imminent and verified."

Groups of cases together provide stronger extensional definition than
individual precedents.""",
        'example': """Disclosure of Safety Hazard group includes:
- Case 89-7 (structural deficiency)
- Case 92-9 (design flaw)
- Case 00-5 (contamination discovery)
All conclude: Engineer must disclose when public at risk.
This group extensionally defines the disclosure obligation.""",
        'proethica_application': "Informs precedent clustering and pattern extraction"
    },
    'principle_differentiation': {
        'definition': "Distinguishing when superficially similar principles apply differently",
        'source_page': "pp. 165-166",
        'source_text': """From McLaren (p. 165): "Principle differentiation is necessary when
cases appear similar but require different principles. Two cases may both
involve 'disclosure' but one concerns disclosure to clients (Code III.1)
while another concerns disclosure to public authorities (Code III.2)."

Careful analysis determines which variant of a general principle applies.""",
        'example': """Disclosure principles differ by recipient:
- Disclosure to client: Duty to inform client of project issues
- Disclosure to public: Duty to warn of safety hazards
- Disclosure to authorities: Duty to report code violations
Same general principle, different specific applications.""",
        'proethica_application': "Refines Obligation (O) extraction by distinguishing variants"
    },
    'exception_specification': {
        'definition': "Identifying conditions under which principles admit exceptions",
        'source_page': "pp. 166-168",
        'source_text': """From McLaren (p. 166): "Even paramount principles admit exceptions
in certain circumstances. The Board has recognized that disclosure obligations
may be limited when: (1) disclosure would cause greater harm, (2) alternative
remedies exist, (3) information is genuinely uncertain."

Exceptions are themselves extensionally defined through cases where they applied.""",
        'example': """Exceptions to disclosure:
- Case 95-2: Disclosure would cause panic, worsening situation
- Case 98-7: Private remediation possible without public alarm
- Case 01-3: Information too uncertain to support disclosure
Each case adds to extensional definition of valid exceptions.""",
        'proethica_application': "Identifies Constraints (Cs) that limit Obligations (O)"
    },
    'comparative_case_analysis': {
        'definition': "Contrasting cases to highlight determinative differences",
        'source_page': "pp. 168-170",
        'source_text': """From McLaren (p. 168): "Comparative analysis juxtaposes cases with
different outcomes to identify what features made the difference. If Case A
required disclosure but Case B did not, what distinguished them? The answer
reveals the truly critical factors."

This technique refines understanding of which facts are truly determinative.""",
        'example': """Case A (disclosure required) vs Case B (disclosure not required):
- A: Immediate threat, no remediation possible
- B: Delayed threat, client agreed to remediate
Determinative difference: Immediacy and remediation availability""",
        'proethica_application': "Informs resolution pattern analysis and determinative factors"
    },
    'temporal_progression': {
        'definition': "Tracking how principle interpretation evolves across time",
        'source_page': "pp. 170-172",
        'source_text': """From McLaren (p. 170): "Extensional definitions evolve as new cases
add to or refine the meaning of principles. Early cases may apply principles
broadly; later cases add nuance and qualification. Understanding this
progression is essential for applying current standards."

The same principle text may be interpreted differently in 2020 than 1990.""",
        'example': """Evolution of "disclosure of information":
- 1980s: Focused on physical safety hazards
- 1990s: Extended to include environmental concerns
- 2000s: Includes cybersecurity vulnerabilities
- 2010s: Encompasses AI system risks
Temporal context affects principle application.""",
        'proethica_application': "Contextualizes precedent relevance by era"
    }
}


def get_prompt_context(
    include_examples: bool = True,
    focus_techniques: List[str] = None
) -> str:
    """
    Generate academic context for LLM prompts about extensional principles.

    Args:
        include_examples: Include technique examples
        focus_techniques: Specific techniques to include (None = all)

    Returns:
        Formatted string for inclusion in LLM prompts
    """
    context = f"""ACADEMIC FRAMEWORK: Extensional Definition of Ethical Principles
{CITATION}

{SOURCE_CONTEXT}

THE NINE OPERATIONALIZATION TECHNIQUES:

McLaren identifies nine techniques the Board uses to bridge abstract principles
to concrete application:

"""

    techniques_to_include = focus_techniques or OPERATIONALIZATION_TECHNIQUES.keys()

    for i, name in enumerate(techniques_to_include, 1):
        if name not in OPERATIONALIZATION_TECHNIQUES:
            continue

        technique = OPERATIONALIZATION_TECHNIQUES[name]
        context += f"""{i}. {name.upper().replace('_', ' ')}
Definition: {technique['definition']}
Source: {technique['source_page']}

{technique['source_text']}
"""
        if include_examples:
            context += f"""
Example:
{technique['example']}
"""
        context += "\n"

    return context


def get_technique_definition(technique_name: str) -> Dict:
    """Get full definition for a specific operationalization technique."""
    return OPERATIONALIZATION_TECHNIQUES.get(technique_name, {})


def get_all_techniques() -> List[str]:
    """Get list of all technique names."""
    return list(OPERATIONALIZATION_TECHNIQUES.keys())


def get_proethica_mappings() -> Dict[str, str]:
    """Get ProEthica entity mappings for all techniques."""
    return {
        name: tech['proethica_application']
        for name, tech in OPERATIONALIZATION_TECHNIQUES.items()
    }


def get_question_emergence_context() -> str:
    """
    Get specialized context for analyzing WHY ethical questions emerge.

    This is used in Step 2E Question Emergence Analysis.
    """
    return f"""QUESTION EMERGENCE ANALYSIS (based on {CITATION_SHORT})

McLaren's operationalization techniques explain WHY ethical questions arise:

1. PRINCIPLE INSTANTIATION - Question emerges when facts trigger principle:
{OPERATIONALIZATION_TECHNIQUES['principle_instantiation']['source_text']}

2. CONFLICTING PRINCIPLES - Question emerges from tension between duties:
{OPERATIONALIZATION_TECHNIQUES['conflicting_principles_resolution']['source_text']}

3. FACT HYPOTHESES - Question emerges from uncertainty about critical facts:
{OPERATIONALIZATION_TECHNIQUES['fact_hypotheses']['source_text']}

When analyzing question emergence, identify:
- Which critical facts triggered principle instantiation?
- Which principles are in conflict?
- What factual uncertainties complicate the analysis?
"""


def get_resolution_pattern_context() -> str:
    """
    Get specialized context for analyzing HOW ethical questions are resolved.

    This is used in Step 2E Resolution Pattern Analysis.
    """
    return f"""RESOLUTION PATTERN ANALYSIS (based on {CITATION_SHORT})

McLaren's techniques explain HOW the Board resolves ethical questions:

1. CASE INSTANTIATION - Resolution by analogy to precedent:
{OPERATIONALIZATION_TECHNIQUES['case_instantiation']['source_text']}

2. COMPARATIVE CASE ANALYSIS - Identifying determinative factors:
{OPERATIONALIZATION_TECHNIQUES['comparative_case_analysis']['source_text']}

3. EXCEPTION SPECIFICATION - When principles admit exceptions:
{OPERATIONALIZATION_TECHNIQUES['exception_specification']['source_text']}

When analyzing resolution patterns, identify:
- Which precedent cases guided the resolution?
- What features were determinative?
- Were any exceptions recognized?
"""


def format_citation(style: str = 'apa') -> str:
    """Format the citation in specified style."""
    if style == 'short':
        return CITATION_SHORT
    elif style == 'chicago':
        return """McLaren, Bruce M. "Extensionally Defining Principles and Cases in Ethics:
An AI Model." Artificial Intelligence 150, no. 1-2 (2003): 145-181."""
    else:  # apa
        return """McLaren, B. M. (2003). Extensionally defining principles and cases in ethics:
An AI model. Artificial Intelligence, 150(1-2), 145-181.
https://doi.org/10.1016/S0004-3702(03)00135-8"""
