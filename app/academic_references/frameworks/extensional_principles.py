"""
Extensional Principles Framework

Based on: McLaren, B.M. (2003) "Extensionally Defining Principles and Cases in Ethics:
An AI Model." Artificial Intelligence, 150(1-2), 145-181.

This module provides the academic foundation for how abstract ethical principles achieve
concrete meaning through accumulated precedent cases. McLaren's SIROCCO system shows that
professional ethics operates through case-based extensional definition rather than
abstract rules.

The operationalization techniques below are quoted verbatim from McLaren (2003), Figure 1
("Operationalization Techniques used by the NSPE BER"). Do NOT add page-specific quotations
that are not in the paper, and do NOT rename or invent techniques; the canonical list is
exactly these nine.

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

# Core theoretical framework. No page-specific quotations are asserted here; the paraphrase
# reflects McLaren (2003), secs. 1-3, and the SIROCCO description.
SOURCE_CONTEXT = """
McLaren's framework is built around the SIROCCO system (SIROCCO = "System for Intelligent
Retrieval of Operationalized Cases and COdes"), which models how the NSPE Board of Ethical
Review (BER) reasons about engineering-ethics cases.

Core thesis: abstract ethical principles contain open-textured terms (for example, "hold
paramount the safety, health, and welfare of the public") that cannot be applied
deductively from an intensional definition. The Board instead OPERATIONALIZES a principle
by repeatedly linking it to the specific questioned and critical facts of cases and to
precedent cases. Accumulated across many cases, these expert-defined associations between a
principle and case facts constitute an EXTENSIONAL definition of the principle: the
principle means the set of fact patterns it has been applied to.

SIROCCO does not decide cases. Given a new case it retrieves likely-relevant NSPE code
provisions and past BER cases for a human reasoner, using the operationalization
information to predict relevance.
"""

# McLaren's nine operationalization techniques, quoted verbatim from McLaren (2003), Fig. 1.
# The five marked core=True are the ones SIROCCO computationally implements for retrieval;
# the other four supply explanatory information. The 'definition', 'example', and
# 'proethica_application' fields are ProEthica's own paraphrase, illustration, and mapping,
# NOT McLaren's text; only 'source_text' is McLaren's verbatim wording.
OPERATIONALIZATION_TECHNIQUES: Dict[str, Dict] = {
    'principle_instantiation': {
        'definition': "Linking a principle to clusters of questioned and critical facts that instantiate it",
        'source_page': "McLaren (2003), Fig. 1",
        'source_text': 'McLaren (2003), Fig. 1: "Instantiating a principle by linking it to clusters of questioned and critical facts."',
        'core': True,
        'example': "Illustrative: a public-safety principle is instantiated in a case by linking it to the facts that establish a hazard and the engineer's knowledge of it.",
        'proethica_application': "Links Principles (P) to the States (S) and Events (E) whose facts instantiate them"
    },
    'fact_hypotheses': {
        'definition': "Hypothesizing facts that would change how a principle applies",
        'source_page': "McLaren (2003), Fig. 1",
        'source_text': 'McLaren (2003), Fig. 1: "Hypothesizing facts that affect how a principle applies."',
        'core': False,
        'example': "Illustrative: considering how the analysis would change if a key fact (prior notice, immediacy of danger) were different.",
        'proethica_application': "Informs counterfactual questions and scenario variations"
    },
    'principle_revision': {
        'definition': "Revising a principle over time in light of new cases or cultural change",
        'source_page': "McLaren (2003), Fig. 1",
        'source_text': 'McLaren (2003), Fig. 1: "Revising a principle over time in light of new cases or changes in culture."',
        'core': False,
        'example': "Illustrative: an established principle is re-read as new case types (for example, new technologies) enter the record.",
        'proethica_application': "Contextualizes precedent relevance by era; underwrites EvolvingStandardsResponsiveness"
    },
    'conflicting_principles_resolution': {
        'definition': "Resolving conflicting principles in a specific case (which principle prevails)",
        'source_page': "McLaren (2003), Fig. 1",
        'source_text': 'McLaren (2003), Fig. 1: "Resolving conflicting principles in a specific case."',
        'core': False,
        'example': "Illustrative: public safety overriding confidentiality where a threat is imminent and verified; the Board records this as an Overrides relation.",
        'proethica_application': "Maps to the defeasibility edges (prevailsOver / competesWith / defeasibleUnder) over Obligations"
    },
    'principle_grouping': {
        'definition': "Grouping principles in a specific case to bolster an argument",
        'source_page': "McLaren (2003), Fig. 1",
        'source_text': 'McLaren (2003), Fig. 1: "Grouping principles in a specific case to bolster an argument."',
        'core': True,
        'example': "Illustrative: citing several mutually reinforcing principles together to support one conclusion.",
        'proethica_application': "Informs grouping of co-cited Principles (P) / Obligations (O)"
    },
    'case_instantiation': {
        'definition': "Instantiating a case as a precedent by linking it to critical facts and analogizing or distinguishing it",
        'source_page': "McLaren (2003), Fig. 1",
        'source_text': 'McLaren (2003), Fig. 1: "Instantiating a case as a precedent by linking it to clusters of questioned and critical facts, and by analogizing or distinguishing it."',
        'core': True,
        'example': "Illustrative: treating a prior case as a template for a new one that shares its critical facts.",
        'proethica_application': "Foundation for precedent retrieval and similarity matching"
    },
    'principle_elaboration': {
        'definition': "Applying, defining, or elaborating issues and principles from past cases",
        'source_page': "McLaren (2003), Fig. 1",
        'source_text': 'McLaren (2003), Fig. 1: "Applying, defining or elaborating issues and principles from past cases."',
        'core': False,
        'example': "Illustrative: drawing out a finer reading of a principle from how earlier cases elaborated it.",
        'proethica_application': "Refines Principle (P) / Obligation (O) extraction from precedent"
    },
    'case_grouping': {
        'definition': "Grouping cases to bolster an argument",
        'source_page': "McLaren (2003), Fig. 1",
        'source_text': 'McLaren (2003), Fig. 1: "Grouping cases to bolster an argument."',
        'core': True,
        'example': "Illustrative: a cluster of same-outcome cases provides stronger extensional support than a single precedent.",
        'proethica_application': "Informs precedent clustering and pattern extraction"
    },
    'operationalization_reuse': {
        'definition': "Reusing a specific application of any of the above techniques from previous analyses",
        'source_page': "McLaren (2003), Fig. 1",
        'source_text': 'McLaren (2003), Fig. 1: "Reusing a specific application of any of the above techniques from previous analyses."',
        'core': True,
        'example': "Illustrative: re-applying a principle-to-fact linkage established in an earlier case to a new, similar case.",
        'proethica_application': "Underwrites reuse of prior principle/case associations across cases"
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

THE NINE OPERATIONALIZATION TECHNIQUES (McLaren 2003, Fig. 1):

The Board uses these nine techniques to bridge abstract principles to concrete
application. The five marked "core" are the ones SIROCCO implements for retrieval.

"""

    techniques_to_include = focus_techniques or OPERATIONALIZATION_TECHNIQUES.keys()

    for i, name in enumerate(techniques_to_include, 1):
        if name not in OPERATIONALIZATION_TECHNIQUES:
            continue

        technique = OPERATIONALIZATION_TECHNIQUES[name]
        core_tag = " [core]" if technique.get('core') else ""
        context += f"""{i}. {name.upper().replace('_', ' ')}{core_tag}
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

1. PRINCIPLE INSTANTIATION - Question emerges when facts trigger a principle:
{OPERATIONALIZATION_TECHNIQUES['principle_instantiation']['source_text']}

2. CONFLICTING PRINCIPLES RESOLUTION - Question emerges from tension between duties:
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

2. CONFLICTING PRINCIPLES RESOLUTION - Weighing which principle prevails:
{OPERATIONALIZATION_TECHNIQUES['conflicting_principles_resolution']['source_text']}

3. CASE GROUPING - Clusters of precedent that reinforce a resolution:
{OPERATIONALIZATION_TECHNIQUES['case_grouping']['source_text']}

When analyzing resolution patterns, identify:
- Which precedent cases guided the resolution?
- Which principles were weighed, and which prevailed?
- Did a group of cases reinforce the outcome?
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
