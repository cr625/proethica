"""
Declarative Modular Framework for Ethical Reasoning

Based on: Berreby, Bourgne & Ganascia (2017)

This module provides the academic foundation for representing ethical
scenarios using a modular, Event Calculus-based approach. The framework
supports both consequentialist and deontological ethical reasoning.

Usage:
    from app.academic_references.frameworks.declarative_ethics import (
        get_prompt_context,
        FOUR_MODEL_ARCHITECTURE,
        EVENT_CALCULUS_PREDICATES,
        CITATION
    )

    # Include academic context in LLM prompts
    prompt = f"{get_prompt_context()}\\n\\nAnalyze this case..."
"""

from typing import Dict, List

# Full academic citation
CITATION = """Berreby, F., Bourgne, G., & Ganascia, J.-G. (2017). A Declarative Modular
Framework for Representing and Applying Ethical Principles. 16th Conference on
Autonomous Agents and MultiAgent Systems (AAMAS 2017), Sao Paulo, Brazil.
HAL: hal-01564675"""

CITATION_SHORT = "Berreby et al. (2017)"

# Source context from the paper
SOURCE_CONTEXT = """
From Section 3.1 (p. 3):

"The ethical decision-making process is apprehended as a four-step procedure
captured by four types of interdependent models: an action model, a causal model,
a model of the Good, and a model of the Right. The first two models provide the
agent with an entirely ethics-free understanding of the world, the second two
provide an ethical over-layer that the agent can parse and apply back onto its
knowledge of the world."

From Section 4 (p. 4) - Event Motor:

"The presented event motor corresponds to the full Event Calculus... We introduce
automatic events in addition to actions. These automatic events occur when all
their preconditions, in the form of fluents, hold, without direct input from
the agent."

From Section 5 (p. 5) - Causal Motor:

"A fluent F is a consequence of an event E if E initiates F, and both obtain.
An event E is a consequence of a fluent F if F is a precondition to E, and
both obtain."
"""

# The four-model architecture
FOUR_MODEL_ARCHITECTURE: Dict[str, Dict] = {
    'action_model': {
        'definition': "Enables the agent to represent its environment and the changes that take place in it",
        'source_page': "p. 3",
        'components': [
            'initial_situation - fluents that hold at T=0',
            'specification_of_events - set of events and dependence relations',
            'event_motor - enables simulation to evolve'
        ],
        'output': 'event_trace - events and fluents at each time point'
    },
    'causal_model': {
        'definition': "Tracks the causal powers of actions, enabling reasoning over agent responsibility and accountability",
        'source_page': "p. 3",
        'components': [
            'event_trace - from action model',
            'specification_of_events',
            'causal_motor - creates causal tree'
        ],
        'output': 'causal_trace - causal relations between events and fluents'
    },
    'model_of_good': {
        'definition': "Makes a claim about the intrinsic value of goals or events",
        'source_page': "p. 3",
        'components': [
            'specification_of_modalities',
            'ethical_specification_of_events',
            'theory_of_the_good'
        ],
        'output': 'goodness_assessment - valuation of events as good/bad'
    },
    'model_of_right': {
        'definition': "Considers what an agent should do, or is most justified in doing",
        'source_page': "p. 4",
        'components': [
            'causal_trace - from causal model',
            'goodness_assessment - for consequentialist theories',
            'deontological_specifications - for deontological theories'
        ],
        'output': 'rightness_assessment - permissible/impermissible actions'
    }
}

# Event Calculus predicates adapted from the paper
EVENT_CALCULUS_PREDICATES: Dict[str, Dict] = {
    'initially': {
        'syntax': 'initially(F)',
        'meaning': 'F is true initially (at T=0)',
        'source_page': "p. 4"
    },
    'effect': {
        'syntax': 'effect(E,F)',
        'meaning': 'E can cause F',
        'source_page': "p. 4"
    },
    'initiates': {
        'syntax': 'initiates(S,E,F,T)',
        'meaning': 'E initiates F at T in simulation S',
        'source_page': "p. 4"
    },
    'terminates': {
        'syntax': 'terminates(S,E,F,T)',
        'meaning': 'E terminates F at T in simulation S',
        'source_page': "p. 4"
    },
    'clipped': {
        'syntax': 'clipped(S,F,T)',
        'meaning': 'F is clipped (ended) at T in S',
        'source_page': "p. 4"
    },
    'holds': {
        'syntax': 'holds(S,F,T)',
        'meaning': 'F is true at T in simulation S',
        'source_page': "p. 4"
    },
    'occurs': {
        'syntax': 'occurs(S,E,T)',
        'meaning': 'Event E occurs at T in simulation S',
        'source_page': "p. 5"
    },
    'prec': {
        'syntax': 'prec(F,E)',
        'meaning': 'F is a precondition for E',
        'source_page': "p. 5"
    },
    'possible': {
        'syntax': 'possible(S,E,T)',
        'meaning': 'E is possible at T in S (all preconditions met)',
        'source_page': "p. 5"
    },
    'cons': {
        'syntax': 'cons(S,E,T,F)',
        'meaning': 'F is a consequence of event E at T in S',
        'source_page': "p. 5"
    }
}

# Theories of the Right from Section 7
THEORIES_OF_RIGHT: Dict[str, Dict] = {
    'pure_bad': {
        'name': 'Prohibiting Purely Detrimental Actions',
        'type': 'consequentialist',
        'definition': 'Actions with purely detrimental effects are impermissible',
        'source_page': "p. 6"
    },
    'least_bad': {
        'name': 'Principle of Least Bad Consequence',
        'type': 'consequentialist',
        'definition': 'Impermissible if worst consequence is worse than any alternative',
        'source_page': "p. 6"
    },
    'benefits_costs': {
        'name': 'Principle of Benefits vs. Costs',
        'type': 'consequentialist',
        'definition': 'Permissible only if overall beneficial',
        'source_page': "p. 7"
    },
    'act_utilitarianism': {
        'name': 'Act Utilitarianism',
        'type': 'consequentialist',
        'definition': 'Permissible if it has the best consequences overall',
        'source_page': "p. 7"
    },
    'rule_utilitarianism': {
        'name': 'Rule Utilitarianism',
        'type': 'consequentialist',
        'definition': 'Permissible if sanctioned by a utility-maximizing rule',
        'source_page': "p. 7"
    },
    'code_of_conduct': {
        'name': 'Codes of Conduct',
        'type': 'deontological',
        'definition': 'Rules outlining obligations, prohibitions, or responsibilities',
        'source_page': "p. 7"
    },
    'kantian_fei': {
        'name': 'Formula of the End in Itself',
        'type': 'deontological',
        'definition': 'Never treat humanity merely as a means',
        'source_page': "p. 8"
    },
    'double_effect': {
        'name': 'Doctrine of Double Effect',
        'type': 'mixed',
        'definition': 'Criteria for permitting actions with both good and bad effects',
        'conditions': [
            'Action itself good or indifferent',
            'Good effect intended, not bad effect',
            'Good effect not produced by means of bad effect',
            'Proportionately grave reason for permitting bad effect'
        ],
        'source_page': "p. 8"
    }
}


def get_prompt_context() -> str:
    """Return formatted context for LLM prompts using Berreby framework."""
    return f"""
ACADEMIC FRAMEWORK: {CITATION_SHORT}

This analysis uses the declarative modular framework for ethical reasoning.

FOUR-MODEL ARCHITECTURE:
1. Action Model: Represents environment and changes via Event Calculus
2. Causal Model: Tracks causal powers and accountability
3. Model of the Good: Assesses intrinsic value (rights-based or value-based)
4. Model of the Right: Determines permissibility (consequentialist or deontological)

EVENT CALCULUS CONCEPTS:
- Fluents: States that persist until terminated (e.g., "engineer_has_duty")
- Events: Actions or automatic occurrences that change fluents
- Preconditions: Fluents that must hold for an event to occur
- Consequences: Causal chains linking events to outcomes

When analyzing ethical scenarios:
1. Identify initial fluents (starting state)
2. Trace events and their effects on fluents
3. Build causal chains using cons(event, consequence)
4. Apply relevant theory of the Right to assess permissibility
"""


def get_event_trace_template() -> str:
    """Return template for Event Calculus-style event trace."""
    return """
EVENT TRACE TEMPLATE:

Initial State (T=0):
- initially(fluent_1)
- initially(fluent_2)
...

Time Point 1:
- occurs(sim, event_1, 1)
- initiates(sim, event_1, fluent_3, 1)
- terminates(sim, event_1, fluent_1, 1)

Time Point 2:
- occurs(sim, event_2, 2)  // automatic event triggered by fluent_3
- cons(sim, event_1, 1, event_2)  // causal link
...
"""


def get_causal_analysis_template() -> str:
    """Return template for causal chain analysis."""
    return """
CAUSAL CHAIN ANALYSIS:

For each action, identify:
1. Direct effects: effect(action, fluent)
2. Initiated states: initiates(S, action, fluent, T)
3. Terminated states: terminates(S, action, fluent, T)
4. Downstream consequences: cons(S, action, T, consequence)

Accountability Assessment:
- Agent performed action A at time T
- Action A initiated fluent F
- Fluent F was precondition for event E
- Event E caused outcome O
- Therefore: Agent accountable for O via causal chain A -> F -> E -> O
"""


__all__ = [
    'CITATION',
    'CITATION_SHORT',
    'SOURCE_CONTEXT',
    'FOUR_MODEL_ARCHITECTURE',
    'EVENT_CALCULUS_PREDICATES',
    'THEORIES_OF_RIGHT',
    'get_prompt_context',
    'get_event_trace_template',
    'get_causal_analysis_template',
]
