"""
Toulmin Argumentation Framework

Based on: Toulmin, S.E. (1958) "The Uses of Argument"
Updated: Toulmin, S.E. (2003) "The Uses of Argument" (Updated Edition)

This module provides the academic foundation for understanding ethical
arguments through Toulmin's practical logic model. Unlike formal logic,
Toulmin's approach captures how real-world arguments work in professional
ethics contexts.

Usage:
    from app.academic_references.frameworks.toulmin_argumentation import (
        get_prompt_context,
        ARGUMENT_COMPONENTS,
        CITATION
    )
"""

from typing import Dict, List

# Full academic citation
CITATION = """Toulmin, S.E. (2003). The Uses of Argument (Updated Edition).
Cambridge University Press. (Original work published 1958)
ISBN: 978-0521534833"""

CITATION_SHORT = "Toulmin (1958/2003)"

# Core theoretical framework
SOURCE_CONTEXT = """
From Toulmin's argumentation model:

"The pattern of an argument - setting out the grounds, relating them to
the backing of the warrants we invoke, and so indicating the force which
the warrants lend to our conclusion - corresponds closely with the pattern
of analysis appropriate to evaluating the cogency of the argument." (p. 96)

Key insight for professional ethics:
"The backing for warrants can be expressed in the form of categorical
statements of fact... In the case of warrants about conduct, the backing
will include references to rules, codes of practice, or standards of
professional ethics." (p. 98)

Toulmin specifically addresses how this applies to ethical reasoning:
"Questions about what we ought to do, no less than questions about what
is the case, have to be settled by the production of 'reasons' or
'arguments', and the same logical categories - grounds, warrants,
backing, qualifiers, and possible rebuttals - prove relevant." (p. 150)
"""

# The six components of Toulmin's model
ARGUMENT_COMPONENTS: Dict[str, Dict] = {
    'claim': {
        'definition': "The conclusion being argued for - what we are trying to establish",
        'source_page': "pp. 90-91",
        'source_text': """From Toulmin (p. 90): "The claim is what we are seeking to
establish by our argument. It may be a factual assertion, a moral judgment,
or a recommendation for action."

In ethical cases, the claim is typically about what an engineer should
or should not do, or whether conduct was ethical or unethical.""",
        'proethica_mapping': """
Claims in NSPE cases typically take the form:
- "Engineer A acted ethically/unethically in [action]"
- "Engineer A should have [alternative action]"
- "It was/was not ethical to [specific conduct]"
The Board's conclusions are claims that resolve the posed questions.""",
        'entity_source': "Board Conclusions, Decision Options"
    },
    'data': {
        'definition': "The grounds - facts, evidence, or circumstances that support the claim",
        'source_page': "pp. 90-92",
        'source_text': """From Toulmin (p. 90): "Data are the facts we appeal to as a
foundation for the claim - the particular facts about the situation which
we cite in support of our conclusion."

The data answers the question: "What have you got to go on?"

In ethics cases, data includes: what happened, who was involved, what
circumstances existed, what the agent knew, and what alternatives existed.""",
        'proethica_mapping': """
Data in NSPE cases comes from:
- Pass 1 States: Initial conditions and situational facts
- Pass 3 Events: Things that happened in the case
- Pass 3 Actions: Things agents did or failed to do
- Case Facts section: The factual circumstances presented""",
        'entity_source': "States (S), Events (E), Actions (A)"
    },
    'warrant': {
        'definition': "The principle, rule, or inference that authorizes moving from data to claim",
        'source_page': "pp. 91-94",
        'source_text': """From Toulmin (p. 91): "Warrants are the general, hypothetical
statements which can act as bridges, and authorize the sort of step to
which our particular argument commits us."

The warrant answers: "How do you get there from here?"

Warrants are often implicit in everyday argument but must be explicit
in professional ethics. They take the form: "If [data], then [claim]"
or "Given [data], one may/must [claim]".""",
        'proethica_mapping': """
Warrants in NSPE cases come from:
- Obligations: Professional duties that bridge facts to conclusions
- Principles: Abstract ethical commitments that guide action
- The warrant shows WHY the facts lead to the ethical conclusion""",
        'entity_source': "Obligations (O), Principles (P)"
    },
    'backing': {
        'definition': "The authority, source, or credential that supports the warrant itself",
        'source_page': "pp. 96-98",
        'source_text': """From Toulmin (p. 96): "Standing behind our warrants there will
normally be other assurances, without which the warrants themselves would
possess neither authority nor currency."

In professional ethics, backing typically comes from:
- Professional codes (NSPE Code of Ethics)
- Legal requirements and regulations
- Professional standards and practices
- Precedent cases with similar reasoning

The backing answers: "Why is this warrant authoritative?".""",
        'proethica_mapping': """
Backing in NSPE cases comes from:
- Code Provisions: Specific sections of the NSPE Code cited
- Precedent cases: Prior Board decisions with similar facts
- Professional standards: Industry practices and expectations""",
        'entity_source': "Code Provisions (References section)"
    },
    'qualifier': {
        'definition': "Words or phrases expressing the degree of force the claim has",
        'source_page': "pp. 93-94",
        'source_text': """From Toulmin (p. 93): "Some warrants authorize us to accept a
claim unequivocally, given the appropriate data; others authorize us to
accept the claim provisionally, subject to exceptions, or only in the
absence of specific counter-indications."

Qualifiers include: "necessarily", "probably", "presumably", "unless...",
"in most cases", "when circumstances permit".""",
        'proethica_mapping': """
Qualifiers in NSPE cases relate to:
- Constraints: Limitations on what was possible
- Capabilities: What the agent was able to do
- Conditions: Specific circumstances that modify the analysis
Common qualifiers: "generally", "in this situation", "absent other factors"
""",
        'entity_source': "Constraints (Cs), Capabilities (Ca)"
    },
    'rebuttal': {
        'definition': "Conditions under which the claim would not hold",
        'source_page': "pp. 93-95",
        'source_text': """From Toulmin (p. 94): "To qualify a claim is to allow for
possible rebuttal - to indicate the circumstances in which the general
authority of the warrant would have to be set aside."

Rebuttals specify: "Unless..." or "Except when..."

In ethics, rebuttals often arise from competing obligations or
exceptional circumstances that override the primary warrant.""",
        'proethica_mapping': """
Rebuttals in NSPE cases arise from:
- Conflicting Obligations: When duties pull in different directions
- Exception conditions: Circumstances that override normal duties
- Competing principles: When multiple code provisions apply differently
The rebuttal explains why a valid warrant might not apply here""",
        'entity_source': "Conflicting Obligations, Constraints"
    }
}


def get_prompt_context(
    include_examples: bool = True,
    focus_components: List[str] = None
) -> str:
    """
    Generate academic context for LLM prompts about Toulmin argumentation.

    Args:
        include_examples: Include ProEthica mappings
        focus_components: Specific components to include (None = all)

    Returns:
        Formatted string for inclusion in LLM prompts
    """
    context = f"""ACADEMIC FRAMEWORK: Toulmin Argumentation Model
{CITATION}

{SOURCE_CONTEXT}

THE SIX COMPONENTS OF PRACTICAL ARGUMENT:

Toulmin's model shows how real-world arguments move from evidence to
conclusion through authoritative principles:

"""

    components_to_include = focus_components or ARGUMENT_COMPONENTS.keys()

    for name in components_to_include:
        if name not in ARGUMENT_COMPONENTS:
            continue

        component = ARGUMENT_COMPONENTS[name]
        context += f"""{name.upper()}
Definition: {component['definition']}
Source: {component['source_page']}

{component['source_text']}
"""
        if include_examples:
            context += f"""
ProEthica Mapping:
{component['proethica_mapping']}
Entity Source: {component['entity_source']}
"""
        context += "\n"

    return context


def get_question_emergence_context() -> str:
    """
    Get specialized Toulmin context for analyzing WHY ethical questions emerge.

    Ethical questions emerge when there is uncertainty about:
    - Which WARRANT applies to the DATA
    - How competing WARRANTS should be weighed
    - Whether REBUTTALS override the primary warrant
    """
    return f"""QUESTION EMERGENCE THROUGH TOULMIN'S LENS (based on {CITATION_SHORT})

An ethical question emerges when the argument structure is incomplete or contested:

1. DATA-WARRANT TENSION: The facts (data) could activate multiple warrants
{ARGUMENT_COMPONENTS['warrant']['source_text']}

2. COMPETING CLAIMS: Multiple valid conclusions could follow from the same data
{ARGUMENT_COMPONENTS['claim']['source_text']}

3. REBUTTAL CONDITIONS: Circumstances exist that might override the primary warrant
{ARGUMENT_COMPONENTS['rebuttal']['source_text']}

When analyzing question emergence, identify:
- What DATA (facts/events/actions) created the ethical situation?
- What competing WARRANTS (obligations/principles) could apply?
- What REBUTTALS exist that create uncertainty about which warrant governs?
"""


def get_concise_emergence_context() -> str:
    """
    Get a concise Toulmin context for prompts (reduces token usage).
    """
    return """TOULMIN ANALYSIS: Questions emerge when argument structure is contested.

- DATA: Facts/events/actions that created the ethical situation
- WARRANT: Obligation/principle that authorizes moving from data to conclusion
- REBUTTAL: Conditions under which the warrant would not apply

Analyze: What DATA triggered the question? What competing WARRANTs could apply?
What REBUTTAL conditions create uncertainty?"""


def get_argument_structure_context() -> str:
    """
    Get context for analyzing the complete argument structure of a case.
    """
    return f"""ARGUMENT STRUCTURE ANALYSIS (based on {CITATION_SHORT})

For each ethical conclusion, identify the complete Toulmin structure:

1. CLAIM: What the Board concluded
2. DATA: What facts supported this conclusion
3. WARRANT: What principle/obligation authorized the move from data to claim
4. BACKING: What code provisions or precedents supported the warrant
5. QUALIFIER: What conditions limited the claim
6. REBUTTAL: What circumstances could have led to a different conclusion

This structure reveals HOW the Board reasoned, not just WHAT they concluded.
"""


def get_component_definition(component_name: str) -> Dict:
    """Get full definition for a specific argument component."""
    return ARGUMENT_COMPONENTS.get(component_name.lower(), {})


def get_all_components() -> List[str]:
    """Get list of all component names."""
    return list(ARGUMENT_COMPONENTS.keys())


def get_proethica_mappings() -> Dict[str, str]:
    """Get ProEthica entity mappings for all components."""
    return {
        name: comp['entity_source']
        for name, comp in ARGUMENT_COMPONENTS.items()
    }


def format_citation(style: str = 'apa') -> str:
    """Format the citation in specified style."""
    if style == 'short':
        return CITATION_SHORT
    elif style == 'chicago':
        return """Toulmin, Stephen E. The Uses of Argument. Updated ed.
Cambridge: Cambridge University Press, 2003."""
    else:  # apa
        return """Toulmin, S. E. (2003). The uses of argument (Updated ed.).
Cambridge University Press. (Original work published 1958)"""
