"""
Role Ethics Framework

Based on: Oakley, J. and Cocking, D. (2001) "Virtue Ethics and Professional Roles"

This module provides the academic foundation for understanding how professional
roles create distinctive ethical obligations. Professional roles generate specific
duties tied to professional goals and practices that general moral theories
do not capture with precision.

Usage:
    from app.academic_references.frameworks.role_ethics import (
        get_prompt_context,
        PROFESSIONAL_VIRTUES,
        ROLE_OBLIGATIONS,
        CITATION
    )
"""

from typing import Dict, List

# Full academic citation
CITATION = """Oakley, J. and Cocking, D. (2001). Virtue Ethics and Professional Roles.
Cambridge: Cambridge University Press."""

CITATION_SHORT = "Oakley & Cocking (2001)"

# Core theoretical framework
SOURCE_CONTEXT = """
From Oakley & Cocking's theoretical framework:

"Professional roles carry distinctive moral obligations that general moral theories
do not capture with precision. These obligations arise from specialized knowledge
and training that create a higher standard of care than that expected of the
general public." (Chapter 1)

"Role morality justifies behaviors within professional contexts that might be
unacceptable otherwise, though not without limits. A lawyer's obligation to
zealously advocate for a client, for example, permits certain actions that would
be impermissible for ordinary citizens." (Chapter 4)

The authors distinguish between:
1. REGULATIVE IDEALS - aspirational standards that guide professional conduct
2. ROLE VIRTUES - character traits appropriate to the professional role
3. ROLE OBLIGATIONS - specific duties arising from role occupancy

Central Thesis (p. 74):
"A good professional is someone who possesses the virtues appropriate to their
role and exercises them in service of the role's proper goals."
"""

# From Kong et al. (2020) analysis of professional codes
PROFESSIONAL_VIRTUES: Dict[str, Dict] = {
    'integrity': {
        'definition': "Adherence to moral and professional standards even under pressure",
        'source_text': """From Oakley & Cocking: "Professional integrity requires maintaining
moral standards even when doing so conflicts with personal interest or external pressure.
The professional must be trustworthy in their role-specific domain."

Kong et al. (2020) found integrity mentioned in 94% of engineering codes analyzed,
making it the most frequently cited professional virtue.""",
        'indicators': [
            "acted with integrity",
            "maintained standards",
            "despite pressure",
            "honest in",
            "truthful about",
            "trustworthy",
            "reliable conduct"
        ],
        'proethica_mapping': "Evaluated through alignment of Actions (A) with Principles (P)"
    },
    'competence': {
        'definition': "Possession and exercise of knowledge, skill, and judgment appropriate to role",
        'source_text': """From Oakley & Cocking: "Competence is not merely technical skill but
includes the judgment to know when one's expertise is sufficient and when to seek help.
The competent professional knows the limits of their knowledge."

This connects to legal standards: Restatement (Third) of Torts requires professionals to
exercise "the skill and knowledge normally possessed by members of that profession
or trade in good standing" (ALI, 2010, S 299A).""",
        'indicators': [
            "within expertise",
            "qualified to",
            "competent in",
            "beyond capability",
            "should have known",
            "standard of care",
            "professional judgment"
        ],
        'proethica_mapping': "Evaluated through Capabilities (Ca) matched to Actions (A)"
    },
    'responsibility': {
        'definition': "Accountability for actions and their consequences within professional scope",
        'source_text': """From Oakley & Cocking: "Professional responsibility extends beyond
immediate actions to foreseeable consequences. The professional must consider how
their work affects others and take ownership of outcomes."

This creates prospective and retrospective dimensions:
- Prospective: Duty to consider consequences before acting
- Retrospective: Accountability for past professional judgments""",
        'indicators': [
            "responsible for",
            "accountable to",
            "duty to ensure",
            "should have anticipated",
            "foreseeable consequences",
            "professional accountability"
        ],
        'proethica_mapping': "Links Roles (R) to Obligations (O) and Actions (A) outcomes"
    },
    'public_welfare_priority': {
        'definition': "Prioritizing public safety and welfare above private interests",
        'source_text': """Engineering-specific from NSPE Code: "Engineers shall hold paramount
the safety, health, and welfare of the public."

Oakley & Cocking frame this as a regulative ideal that shapes how other obligations
are interpreted. When duties conflict, public welfare provides priority ordering.
This is operationalized through precedent cases (McLaren, 2003).""",
        'indicators': [
            "public safety",
            "paramount",
            "welfare of the public",
            "above private interests",
            "public protection",
            "societal benefit"
        ],
        'proethica_mapping': "Primary Principle (P) that constrains other Obligations (O)"
    }
}

# Role-specific obligations that emerge from professional positions
ROLE_OBLIGATIONS: Dict[str, Dict] = {
    'confidentiality': {
        'definition': "Duty to protect client/employer information from unauthorized disclosure",
        'source_text': """Oakley & Cocking note that confidentiality obligations vary by role:
"The lawyer's duty of confidentiality is near-absolute, while the engineer's duty
may be overridden by public safety concerns."

This creates potential for obligation conflict when confidential information
reveals safety risks.""",
        'scope': "client_employer",
        'typical_conflicts': ["public_safety", "disclosure_to_authorities"],
        'indicators': [
            "confidential information",
            "client secrets",
            "proprietary",
            "disclosure would",
            "duty of confidence"
        ]
    },
    'loyalty': {
        'definition': "Duty to act in the interests of client/employer within ethical bounds",
        'source_text': """From Oakley & Cocking: "Professional loyalty is not unlimited.
The professional owes loyalty to clients but this does not extend to assisting
in unlawful or unethical conduct."

Engineering codes typically subordinate loyalty to public welfare:
"Engineers shall not be bound by their allegiance to client/employer when
violation of their professional integrity or public safety would result." """,
        'scope': "client_employer",
        'typical_conflicts': ["public_safety", "professional_integrity"],
        'indicators': [
            "client interests",
            "employer's wishes",
            "loyalty to",
            "allegiance",
            "serve the client"
        ]
    },
    'disclosure': {
        'definition': "Duty to reveal information that others need to make informed decisions",
        'source_text': """Multiple disclosure obligations exist:
1. To clients: Material facts affecting their interests
2. To public: Safety hazards within professional knowledge
3. To authorities: Violations of codes or regulations

Disclosure duties often conflict with confidentiality, requiring professional
judgment about which obligation prevails.""",
        'scope': "multiple_parties",
        'typical_conflicts': ["confidentiality", "loyalty"],
        'indicators': [
            "should have disclosed",
            "obligation to inform",
            "duty to warn",
            "failed to reveal",
            "should have been told"
        ]
    },
    'diligence': {
        'definition': "Duty to pursue professional work with appropriate care and attention",
        'source_text': """From Oakley & Cocking: "Diligence requires not merely completing
tasks but doing so with appropriate thoroughness. The diligent professional
investigates adequately, documents carefully, and follows through."

This connects to negligence standards - failure of diligence may constitute
breach of professional duty.""",
        'scope': "professional_work",
        'typical_conflicts': ["resource_constraints", "time_pressure"],
        'indicators': [
            "thorough review",
            "adequate investigation",
            "proper documentation",
            "failed to check",
            "should have verified"
        ]
    }
}


def get_prompt_context(
    include_virtues: bool = True,
    include_obligations: bool = True,
    focus_virtues: List[str] = None
) -> str:
    """
    Generate academic context for LLM prompts about role ethics.

    Args:
        include_virtues: Include professional virtues section
        include_obligations: Include role obligations section
        focus_virtues: Specific virtues to emphasize (None = all)

    Returns:
        Formatted string for inclusion in LLM prompts
    """
    context = f"""ACADEMIC FRAMEWORK: Role Ethics and Professional Obligations
{CITATION}

{SOURCE_CONTEXT}

"""

    if include_virtues:
        context += "PROFESSIONAL VIRTUES:\n\n"
        virtues_to_include = focus_virtues or PROFESSIONAL_VIRTUES.keys()

        for virtue_name in virtues_to_include:
            if virtue_name in PROFESSIONAL_VIRTUES:
                virtue = PROFESSIONAL_VIRTUES[virtue_name]
                context += f"""{virtue_name.upper().replace('_', ' ')}
Definition: {virtue['definition']}
{virtue['source_text']}
Indicators: {', '.join(virtue['indicators'][:4])}

"""

    if include_obligations:
        context += "\nROLE-SPECIFIC OBLIGATIONS:\n\n"
        for obl_name, obligation in ROLE_OBLIGATIONS.items():
            context += f"""{obl_name.upper()}
Definition: {obligation['definition']}
{obligation['source_text']}
Potential conflicts: {', '.join(obligation['typical_conflicts'])}

"""

    return context


def get_virtue_definition(virtue_name: str) -> Dict:
    """Get full definition for a specific professional virtue."""
    return PROFESSIONAL_VIRTUES.get(virtue_name, {})


def get_obligation_definition(obligation_name: str) -> Dict:
    """Get full definition for a specific role obligation."""
    return ROLE_OBLIGATIONS.get(obligation_name, {})


def get_conflict_pairs() -> List[Dict]:
    """
    Get common obligation conflict pairs for analysis.

    Returns:
        List of dicts with obligation1, obligation2, description
    """
    return [
        {
            'obligation1': 'confidentiality',
            'obligation2': 'public_safety',
            'description': "Duty to protect client information vs. duty to warn of hazards"
        },
        {
            'obligation1': 'loyalty',
            'obligation2': 'integrity',
            'description': "Duty to client interests vs. duty to maintain professional standards"
        },
        {
            'obligation1': 'confidentiality',
            'obligation2': 'disclosure',
            'description': "Duty to keep secrets vs. duty to inform affected parties"
        },
        {
            'obligation1': 'loyalty',
            'obligation2': 'public_welfare',
            'description': "Duty to employer vs. paramount duty to public safety"
        }
    ]


def format_citation(style: str = 'apa') -> str:
    """Format the citation in specified style."""
    if style == 'short':
        return CITATION_SHORT
    elif style == 'chicago':
        return """Oakley, Justin, and Dean Cocking. Virtue Ethics and Professional Roles.
Cambridge: Cambridge University Press, 2001."""
    else:  # apa
        return """Oakley, J., & Cocking, D. (2001). Virtue ethics and professional roles.
Cambridge University Press."""
