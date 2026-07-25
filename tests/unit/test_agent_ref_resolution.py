"""decidedByAgent reference resolution (batch-3 review promotion).

Phase-3 refs miss the committed Agent two ways: omitted Agent_ prefix and
generic role tokens. Unique-prefix disambiguation resolves; ambiguity stays
a recorded miss.
"""
from rdflib import Namespace

from app.services.extraction.analysis_edges import _resolve_agent_ref

NS = Namespace("http://proethica.org/ontology/case/92#")


def _agents(*frags):
    return {NS[f] for f in frags}


def test_exact_and_prefixed_fragments_resolve():
    agents = _agents("Agent_Engineer_D", "Agent_City")
    assert _resolve_agent_ref(NS, "case-92#Agent_Engineer_D", agents) == NS.Agent_Engineer_D
    assert _resolve_agent_ref(NS, "case-92#Engineer_D", agents) == NS.Agent_Engineer_D


def test_generic_token_resolves_when_unique():
    agents = _agents("Agent_Engineer_A", "Agent_City", "Agent_Technician_B")
    assert _resolve_agent_ref(NS, "case-92#Engineer", agents) == NS.Agent_Engineer_A
    assert _resolve_agent_ref(NS, "case-92#The_Engineer", agents) == NS.Agent_Engineer_A


def test_ambiguous_generic_token_stays_miss():
    agents = _agents("Agent_Engineer_A", "Agent_Engineer_B")
    assert _resolve_agent_ref(NS, "case-92#Engineer", agents) is None


def test_unknown_and_short_tokens_stay_miss():
    agents = _agents("Agent_Engineer_A")
    assert _resolve_agent_ref(NS, "case-92#Attorney", agents) is None
    assert _resolve_agent_ref(NS, "case-92#Zz", agents) is None
    assert _resolve_agent_ref(NS, "", agents) is None


def test_token_boundary_excludes_engineering_firm():
    """'engineer' must not read 'Engineering_Firm' as a second engineer
    (case 163: the char-prefix match skipped a resolvable ref as ambiguous)."""
    agents = _agents("Agent_Engineer_A", "Agent_Engineering_Firm",
                     "Agent_Graduate_Engineers")
    assert _resolve_agent_ref(NS, "case-163#Engineer", agents) == NS.Agent_Engineer_A
