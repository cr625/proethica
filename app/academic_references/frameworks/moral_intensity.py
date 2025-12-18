"""
Moral Intensity Framework

Based on: Jones, T.M. (1991) "Ethical Decision Making by Individuals in Organizations:
An Issue-Contingent Model"

This module provides the academic foundation for scoring the moral salience of
decision points. Jones's model identifies six components that determine how
"intense" an ethical issue is perceived to be, affecting likelihood of ethical
behavior.

Usage:
    from app.academic_references.frameworks.moral_intensity import (
        get_prompt_context,
        INTENSITY_COMPONENTS,
        calculate_intensity_score,
        CITATION
    )
"""

from typing import Dict, List, Optional

# Full academic citation
CITATION = """Jones, T.M. (1991). "Ethical Decision Making by Individuals in Organizations:
An Issue-Contingent Model." Academy of Management Review, 16(2), 366-395."""

CITATION_SHORT = "Jones (1991)"

# Core theoretical framework
SOURCE_CONTEXT = """
From Jones's theoretical framework (pp. 371-378):

"The moral intensity of an issue is defined as a construct that captures the
extent of issue-related moral imperative in a situation." (p. 372)

Jones argues that ethical behavior depends not only on individual characteristics
but also on characteristics of the moral issue itself. Issues with higher moral
intensity are more likely to be recognized as ethical issues, more likely to
trigger moral reasoning, and more likely to result in ethical behavior.

The model synthesizes prior ethical decision-making models (Rest, 1986; Trevino, 1986)
with characteristics of the moral issue. Jones identifies six components that
together determine moral intensity:

"These characteristics of the moral issue are expected to influence every stage
of moral decision-making and behavior." (p. 374)

The six components are:
1. Magnitude of Consequences
2. Social Consensus
3. Probability of Effect
4. Temporal Immediacy
5. Proximity
6. Concentration of Effect
"""

INTENSITY_COMPONENTS: Dict[str, Dict] = {
    'magnitude_of_consequences': {
        'definition': "Sum of harms (or benefits) done to victims (or beneficiaries) of the moral act",
        'source_page': "p. 374",
        'source_text': """From p. 374: "The magnitude of consequences of a moral act is defined
as the sum of the harms (or benefits) done to victims (or beneficiaries) of the
moral act in question."

Jones notes: "An act that causes 1,000 people to suffer a particular injury is of
greater magnitude of consequences than an act that causes 10 people to suffer the
same injury." Similarly, an act causing death has greater magnitude than one
causing minor injury.

In professional ethics: This maps to severity of safety events and scope of impact.
Death > serious injury > minor injury > property damage > inconvenience.""",
        'scale_anchors': {
            0.0: "No harm or benefit",
            0.25: "Minor inconvenience or small benefit",
            0.5: "Moderate harm (property damage, temporary injury) or benefit",
            0.75: "Serious harm (significant injury, major financial loss) or benefit",
            1.0: "Severe harm (death, permanent disability, catastrophic loss) or major benefit"
        },
        'proethica_mapping': "Scored from Events (E) outcome severity and scope",
        'engineering_examples': [
            "Bridge collapse causing deaths (1.0)",
            "Product defect causing injuries (0.75)",
            "Design flaw causing property damage (0.5)",
            "Minor code violation with no harm (0.25)"
        ]
    },
    'social_consensus': {
        'definition': "Degree of social agreement that a proposed act is evil (or good)",
        'source_page': "p. 375",
        'source_text': """From p. 375: "Social consensus is defined as the degree of social
agreement that a proposed act is evil (or good)."

Jones explains: "Evil acts about which there is greater social consensus will be
more intense... Acts about which there is clear consensus are likely to be
recognized as ethical issues."

In professional ethics: High consensus exists when professional codes explicitly
address the issue. Lower consensus when codes are silent or ambiguous.
Explicit code provisions indicate clearer social agreement on ethical valence.""",
        'scale_anchors': {
            0.0: "No consensus; highly contested ethical question",
            0.25: "Weak consensus; reasonable professionals disagree",
            0.5: "Moderate consensus; general agreement with exceptions",
            0.75: "Strong consensus; professional codes clearly address",
            1.0: "Complete consensus; universal agreement on ethical status"
        },
        'proethica_mapping': "Scored by Provision (Rs) citation strength and explicitness",
        'engineering_examples': [
            "Falsifying test data (1.0 - universal condemnation)",
            "Reporting unsafe conditions (0.9 - strong consensus to report)",
            "Accepting gifts from contractors (0.6 - varies by value/context)",
            "Competing with former employer (0.3 - complex, context-dependent)"
        ]
    },
    'probability_of_effect': {
        'definition': "Joint probability that the act will occur and cause predicted harm (or benefit)",
        'source_page': "p. 375",
        'source_text': """From p. 375: "Probability of effect of the moral act in question is a
joint function of the probability that the act in question will actually take
place and the act will actually cause the harm (benefit) predicted."

Jones emphasizes: "An act that is certain to cause one person's death is more
intense than one that has only a 10 percent chance of causing the same person's
death."

In professional ethics: This relates to risk assessment - how likely is the harm
to actually materialize? Immediate, certain harms score higher than speculative risks.""",
        'scale_anchors': {
            0.0: "Extremely unlikely (< 1%)",
            0.25: "Unlikely (1-25%)",
            0.5: "Possible (25-50%)",
            0.75: "Likely (50-75%)",
            1.0: "Certain or near-certain (> 75%)"
        },
        'proethica_mapping': "Assessed from States (S) and conditional analysis",
        'engineering_examples': [
            "Defect causes certain failure under normal use (1.0)",
            "Defect may cause failure under extreme conditions (0.5)",
            "Theoretical vulnerability, no documented failures (0.25)"
        ]
    },
    'temporal_immediacy': {
        'definition': "Length of time between the present and onset of consequences",
        'source_page': "p. 376",
        'source_text': """From p. 376: "Temporal immediacy of a moral act is the length of time
between the present and the onset of consequences of the moral act in question
(shorter length of time implies greater immediacy)."

Jones notes: "An act that will cause harm tomorrow is more intense than one that
will cause the same harm in 10 years." This affects both recognition and
urgency of response.

In professional ethics: Imminent risks demand immediate action; delayed consequences
may permit more deliberate response but also risk being overlooked.""",
        'scale_anchors': {
            0.0: "Distant future (> 10 years)",
            0.25: "Long-term (1-10 years)",
            0.5: "Medium-term (months to 1 year)",
            0.75: "Near-term (days to months)",
            1.0: "Immediate (happening now or imminent)"
        },
        'proethica_mapping': "Derived from Events (E) temporal relationships",
        'engineering_examples': [
            "Bridge may collapse during current traffic (1.0)",
            "Building safety issue - occupants at risk daily (0.9)",
            "Design flaw - problems in 2 years (0.5)",
            "Theoretical issue - may matter in 20 years (0.1)"
        ]
    },
    'proximity': {
        'definition': "Feeling of nearness (social, cultural, psychological, or physical) to victims/beneficiaries",
        'source_page': "p. 376",
        'source_text': """From p. 376: "Proximity is the feeling of nearness (social, cultural,
psychological, or physical) that the moral agent has for victims (or
beneficiaries) of the moral act in question."

Jones explains: "Americans will be more concerned about the moral intensity of
an act that kills 10 people in their own town than one that kills 100 people
in a town of similar size in a foreign country."

In professional ethics: Direct relationships (client, team, community served)
create higher proximity than abstract or distant stakeholders.""",
        'scale_anchors': {
            0.0: "Abstract/unknown stakeholders",
            0.25: "Identifiable but distant groups",
            0.5: "Known community or professional peers",
            0.75: "Direct professional relationship (clients, team)",
            1.0: "Close personal/professional relationship (named individuals)"
        },
        'proethica_mapping': "Derived from Roles (R) relationships and stakeholder mapping",
        'engineering_examples': [
            "Risk to team members working on project (1.0)",
            "Risk to named client personnel (0.9)",
            "Risk to building occupants generally (0.6)",
            "Risk to abstract future users (0.3)"
        ]
    },
    'concentration_of_effect': {
        'definition': "Inverse function of number of people affected by act of given magnitude",
        'source_page': "p. 377",
        'source_text': """From p. 377: "Concentration of effect of a moral act is an inverse
function of the number of people affected by an act of given magnitude."

Jones clarifies: "A change in health plan that will result in a $10,000 increase
in costs to 1 person is more concentrated than one that will result in a $10
increase in costs to 1,000 people, even though the total costs are the same."

In professional ethics: Concentrated harms to few individuals may be perceived as
more intense than diffuse harms across many, even at equivalent total magnitude.""",
        'scale_anchors': {
            0.0: "Diffuse effect across very large population",
            0.25: "Spread across large group (hundreds)",
            0.5: "Affects moderate number (dozens)",
            0.75: "Concentrated on small group (few individuals)",
            1.0: "Focused on single individual"
        },
        'proethica_mapping': "Inverse of stakeholder count from Roles (R) analysis",
        'engineering_examples': [
            "Single resident affected by design flaw (1.0)",
            "Small group of workers exposed (0.8)",
            "Building occupants generally (0.5)",
            "General public as abstract class (0.2)"
        ]
    }
}


def get_prompt_context(
    include_examples: bool = True,
    include_scales: bool = True
) -> str:
    """
    Generate academic context for LLM prompts about moral intensity.

    Args:
        include_examples: Include engineering examples
        include_scales: Include scoring scale anchors

    Returns:
        Formatted string for inclusion in LLM prompts
    """
    context = f"""ACADEMIC FRAMEWORK: Moral Intensity
{CITATION}

{SOURCE_CONTEXT}

THE SIX COMPONENTS OF MORAL INTENSITY:

"""

    for i, (name, component) in enumerate(INTENSITY_COMPONENTS.items(), 1):
        context += f"""{i}. {name.upper().replace('_', ' ')}
Definition: {component['definition']}
Source: {component['source_page']}

{component['source_text']}
"""
        if include_scales:
            context += "\nScale:\n"
            for score, description in component['scale_anchors'].items():
                context += f"  {score}: {description}\n"

        if include_examples and component.get('engineering_examples'):
            context += f"\nEngineering Examples:\n"
            for ex in component['engineering_examples'][:2]:
                context += f"  - {ex}\n"

        context += "\n"

    return context


def calculate_intensity_score(
    magnitude: float,
    consensus: float,
    probability: float,
    immediacy: float,
    proximity: float,
    concentration: float,
    weights: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
    """
    Calculate overall moral intensity score.

    Args:
        magnitude: Magnitude of consequences (0-1)
        consensus: Social consensus (0-1)
        probability: Probability of effect (0-1)
        immediacy: Temporal immediacy (0-1)
        proximity: Proximity to affected parties (0-1)
        concentration: Concentration of effect (0-1)
        weights: Optional custom weights (default: equal weighting)

    Returns:
        Dict with component scores and overall intensity
    """
    if weights is None:
        weights = {
            'magnitude_of_consequences': 1/6,
            'social_consensus': 1/6,
            'probability_of_effect': 1/6,
            'temporal_immediacy': 1/6,
            'proximity': 1/6,
            'concentration_of_effect': 1/6
        }

    # Validate inputs
    scores = {
        'magnitude_of_consequences': max(0, min(1, magnitude)),
        'social_consensus': max(0, min(1, consensus)),
        'probability_of_effect': max(0, min(1, probability)),
        'temporal_immediacy': max(0, min(1, immediacy)),
        'proximity': max(0, min(1, proximity)),
        'concentration_of_effect': max(0, min(1, concentration))
    }

    # Calculate weighted average
    overall = sum(scores[k] * weights.get(k, 1/6) for k in scores)

    return {
        'component_scores': scores,
        'weights': weights,
        'overall_intensity': overall,
        'intensity_level': _classify_intensity(overall)
    }


def _classify_intensity(score: float) -> str:
    """Classify intensity level from score."""
    if score >= 0.8:
        return "very_high"
    elif score >= 0.6:
        return "high"
    elif score >= 0.4:
        return "moderate"
    elif score >= 0.2:
        return "low"
    else:
        return "very_low"


def get_component_definition(component_name: str) -> Dict:
    """Get full definition for a specific intensity component."""
    return INTENSITY_COMPONENTS.get(component_name, {})


def get_all_components() -> List[str]:
    """Get list of all component names."""
    return list(INTENSITY_COMPONENTS.keys())


def format_citation(style: str = 'apa') -> str:
    """Format the citation in specified style."""
    if style == 'short':
        return CITATION_SHORT
    elif style == 'chicago':
        return """Jones, Thomas M. "Ethical Decision Making by Individuals in Organizations:
An Issue-Contingent Model." Academy of Management Review 16, no. 2 (1991): 366-395."""
    else:  # apa
        return """Jones, T. M. (1991). Ethical decision making by individuals in organizations:
An issue-contingent model. Academy of Management Review, 16(2), 366-395."""
