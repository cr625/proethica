"""Unit tests for the participant-edge applier helpers (participant_edges.py).

The full apply_participant_edges path needs the DB (temporary_rdf_storage) and the
embedding service, and is exercised end-to-end by the case-15 commit. These tests
lock the mockable logic: the four specs (Ca/Cs flip guard), the per-spec prompt
wording, the reused multi-select mapping, provenance idempotency, and that every
participant property is covered by the domain/range guard registry.
"""
from rdflib import Graph, Namespace, RDF, RDFS

from app.services.extraction import participant_edges as pe_
from app.services.extraction import resource_edges as re_
from app.services.extraction.rpo_edges import ALL_EDGE_RANGE

CORE = Namespace("http://proethica.org/ontology/core#")
PROV = Namespace("http://www.w3.org/ns/prov#")
CASE = Namespace("http://proethica.org/ontology/case/15#")


def _items():
    return [
        {"id": 1, "subj": CASE["Public_Safety_Obligation"], "desc": "Engineer B; the public",
         "subj_label": "Engineer B Public Safety Obligation",
         "shortlist": [(CASE["Agent_Engineer_B"], "Engineer B", 0.9),
                       (CASE["Agent_Owner"], "Owner", 0.4),
                       (CASE["Agent_Engineer_A"], "Engineer A", 0.35)]},
    ]


class _FakeStream:
    def __init__(self, text): self._text = text
    def __enter__(self): return self
    def __exit__(self, *a): return False
    @property
    def text_stream(self): return [self._text]


class _FakeClient:
    def __init__(self, text):
        self.messages = type("M", (), {"stream": lambda _self, **kw: _FakeStream(text)})()


def test_specs_cover_the_four_components_with_correct_categories():
    """The applier must wire exactly the four Pass-2 participant edges, and must not
    confuse Ca (Capabilities) with Cs (Constraints)."""
    by_prop = {s.prop: s for s in pe_.PARTICIPANT_SPECS}
    assert set(by_prop) == {"obligatedParty", "constrainedEntity", "possessedBy", "invokedBy"}
    assert by_prop["obligatedParty"].category == "Obligation"
    assert by_prop["obligatedParty"].extraction_type == "obligations"
    assert by_prop["constrainedEntity"].category == "Constraint"
    assert by_prop["constrainedEntity"].extraction_type == "constraints"
    # Ca/Cs flip guard: possessedBy is the CAPABILITY edge, constrainedEntity the CONSTRAINT one.
    assert by_prop["possessedBy"].category == "Capability"
    assert by_prop["possessedBy"].extraction_type == "capabilities"
    assert by_prop["invokedBy"].category == "Principle"
    assert by_prop["invokedBy"].extraction_type == "principles"


def test_all_participant_edges_are_guarded():
    """Every minted participant property must be in ALL_EDGE_RANGE so the unified
    domain/range guard validates its subject (range Agent is intentionally outside
    the nine disjoint categories, so the object is unconstrained)."""
    for prop in ("obligatedParty", "constrainedEntity", "possessedBy", "invokedBy"):
        sub, obj = ALL_EDGE_RANGE[CORE[prop]]
        assert obj == "Agent", (prop, obj)
    assert ALL_EDGE_RANGE[CORE.obligatedParty][0] == "Obligation"
    assert ALL_EDGE_RANGE[CORE.constrainedEntity][0] == "Constraint"
    assert ALL_EDGE_RANGE[CORE.possessedBy][0] == "Capability"
    assert ALL_EDGE_RANGE[CORE.invokedBy][0] == "Principle"


def test_prompt_wording_is_spec_specific_and_excludes_generics():
    """Each spec's prompt names its component noun + relation verb and includes the
    party text verbatim, and instructs the model to drop generic/institutional
    parties (which is how a non-case party yields no edge)."""
    spec = {s.prop: s for s in pe_.PARTICIPANT_SPECS}["obligatedParty"]
    p = pe_._build_participant_prompt(spec)(_items())
    assert "obligation" in p.lower()
    assert "BEARS" in p
    assert "the public" in p          # request text included verbatim
    assert "generic" in p.lower()

    inv = {s.prop: s for s in pe_.PARTICIPANT_SPECS}["invokedBy"]
    pi = pe_._build_participant_prompt(inv)(_items())
    assert "principle" in pi.lower()
    assert "INVOKES" in pi


def test_multi_select_maps_chosen_agents():
    """The applier reuses resource_edges._llm_select_multi with its per-spec prompt
    builder; chosen candidate numbers map to Agent IRIs, [] to none."""
    spec = {s.prop: s for s in pe_.PARTICIPANT_SPECS}["obligatedParty"]
    client = _FakeClient('{"1": [1]}')   # Engineer B only; not the public/Owner/Engineer A
    out = re_._llm_select_multi(_items(), client=client, model="x",
                                prompt_builder=pe_._build_participant_prompt(spec))
    assert out["1"] == [CASE["Agent_Engineer_B"]]


def test_emit_prov_idempotent_and_property_scoped():
    """The participant prov node is deterministic from (subj, prop, obj); a second
    emission must not duplicate it, and two different properties between the same
    pair get distinct prov nodes."""
    g = Graph()
    s, o = CASE["Public_Safety_Obligation"], CASE["Agent_Engineer_B"]
    pe_._emit_prov(g, 15, "obligatedParty", s, o, "Engineer B")
    pe_._emit_prov(g, 15, "obligatedParty", s, o, "Engineer B")
    provs = [x for x in g.subjects(RDF.type, PROV.Derivation)
             if "participant_edge_provenance" in str(x) and "obligatedParty" in str(x)]
    assert len(provs) == 1, provs
    assert len(list(g.objects(provs[0], PROV.value))) == 1
    assert (provs[0], PROV.wasDerivedFrom, s) in g
    assert (provs[0], PROV.wasDerivedFrom, o) in g
    # A different property between the same pair is a distinct node.
    pe_._emit_prov(g, 15, "possessedBy", s, o, "Engineer B")
    all_provs = [x for x in g.subjects(RDF.type, PROV.Derivation)
                 if "participant_edge_provenance" in str(x)]
    assert len(all_provs) == 2, all_provs
