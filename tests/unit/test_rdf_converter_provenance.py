"""
Unit tests for the B10 temporal-provenance emission in rdf_converter.

The Step-3 prompts request source_section on actions, events, and causal chains,
and agent_knowledge / intervening_factors inside the chain responsibility block,
but the converters dropped everything except the chain's source_section before
storage. Because the converter runs before temp_rdf, a dropped field is
unrecoverable after the once-only rebuild; these tests lock the emission.
"""

from app.services.temporal_dynamics.utils.rdf_converter import (
    convert_action_to_rdf,
    convert_causal_chain_to_rdf,
    convert_event_to_rdf,
)


def test_action_emits_source_section():
    action = {'label': 'Assign Task', 'source_section': 'facts'}
    rdf = convert_action_to_rdf(action, 9)
    assert rdf['proeth:discoveredInSection'] == 'facts'


def test_event_emits_source_section():
    event = {'label': 'Structural Failure', 'source_section': 'discussion'}
    rdf = convert_event_to_rdf(event, 9)
    assert rdf['proeth:discoveredInSection'] == 'discussion'


def test_absent_source_section_not_minted():
    """A defaulted section would be indistinguishable from a real attribution."""
    for rdf in (convert_action_to_rdf({'label': 'A'}, 9),
                convert_event_to_rdf({'label': 'E'}, 9),
                convert_causal_chain_to_rdf({'cause': 'c', 'effect': 'e'}, 9, 1)):
        assert 'proeth:discoveredInSection' not in rdf


def test_chain_still_emits_source_section():
    """Refactor guard: the chain emission moved to the shared helper."""
    chain = {'cause': 'c', 'effect': 'e', 'source_section': 'facts'}
    rdf = convert_causal_chain_to_rdf(chain, 9, 1)
    assert rdf['proeth:discoveredInSection'] == 'facts'


def test_chain_emits_responsibility_knowledge_fields():
    chain = {
        'cause': 'Task Assignment', 'effect': 'Design Flaw',
        'responsibility': {
            'responsible_agent': 'Engineer A',
            'responsibility_type': 'direct',
            'within_control': True,
            'agent_knowledge': 'Knew the intern lacked experience',
            'intervening_factors': ['Tight deadline', ' Limited staffing ', ''],
        },
    }
    rdf = convert_causal_chain_to_rdf(chain, 9, 1)
    assert rdf['proeth:agentKnowledge'] == 'Knew the intern lacked experience'
    assert rdf['proeth:interveningFactors'] == ['Tight deadline', 'Limited staffing']


def test_chain_absent_knowledge_fields_not_minted():
    chain = {
        'cause': 'c', 'effect': 'e',
        'responsibility': {'responsible_agent': 'X', 'within_control': False},
    }
    rdf = convert_causal_chain_to_rdf(chain, 9, 1)
    assert 'proeth:agentKnowledge' not in rdf
    assert 'proeth:interveningFactors' not in rdf


def test_chain_single_string_intervening_factor_normalized():
    """Model drift: a bare string instead of a list becomes a one-item list."""
    chain = {
        'cause': 'c', 'effect': 'e',
        'responsibility': {'responsible_agent': 'X',
                           'intervening_factors': 'Budget pressure'},
    }
    rdf = convert_causal_chain_to_rdf(chain, 9, 1)
    assert rdf['proeth:interveningFactors'] == ['Budget pressure']
