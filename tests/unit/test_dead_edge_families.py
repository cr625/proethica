"""Unit tests for the Stage-3 dead-edge-family batch (audit item 9).

Five SHACL-promised edge families were zero in both committed case-7 runs while the
LLMs supplied their content as literals. These tests cover the commit/edge-layer
side: the citedByAgent + isPerformedBy participant-family additions (with the
deterministic NSPE Board Agent fallback), the inverted requiresCapability family,
and the reader-level row handling (temporal row shape, role-parenthetical
normalization). All graphs are mocks lifted from case7_opus_run12.ttl shapes; no
API or DB is touched (the resolver primitives and the temp_rdf readers are stubbed,
mirroring tests/unit/test_edge_spec_equivalence.py). The establishedBy provision
family is covered in tests/unit/test_provision_citation_resolver.py.
"""
import os
import tempfile
from types import SimpleNamespace

from rdflib import Graph, Literal, Namespace, OWL, RDF, RDFS

from app.services.extraction import edge_resolution as er
from app.services.extraction import edge_spec as es
from app.services.extraction.rpo_edges import ALL_EDGE_RANGE

CORE = Namespace("http://proethica.org/ontology/core#")
PROV = Namespace("http://www.w3.org/ns/prov#")
CASE = Namespace("http://proethica.org/ontology/case/99#")
CASE_ID = 99
BOARD = CASE[er.BOARD_AGENT_LOCALNAME]


# --- shared helpers (mirroring test_edge_spec_equivalence) -------------------

def _ind(g, iri, label, category=None):
    g.add((iri, RDF.type, OWL.NamedIndividual))
    g.add((iri, RDFS.label, Literal(label)))
    if category:
        g.add((iri, RDF.type, CORE[category]))


def _agent(g, iri, label):
    _ind(g, iri, label)
    g.add((iri, RDF.type, CORE.Agent))


def _write(g):
    fd, path = tempfile.mkstemp(suffix=".ttl")
    os.close(fd)
    g.serialize(destination=path, format="turtle")
    return path


def _install_deterministic_resolver(monkeypatch, selection_by_desc):
    def fake_embedding_service():
        return object()

    def fake_embed(svc, text):
        return [1.0] if (text or "").strip() else None

    def fake_shortlist(svc, desc, pool, floor, k):
        tgts = selection_by_desc.get(desc, [])
        return [(iri, str(iri).split("#")[-1], 0.9) for iri in tgts][:k]

    def fake_llm_multi(items, client=None, model=None, prompt_builder=None, model_tier="default"):
        return {str(it["id"]): [iri for iri, _l, _s in it["shortlist"]] for it in items}

    monkeypatch.setattr(er, "_embed", fake_embed)
    for m in (er, es):
        for name, fn in (("_embedding_service", fake_embedding_service),
                         ("_shortlist", fake_shortlist),
                         ("_llm_select_multi", fake_llm_multi)):
            if hasattr(m, name):
                monkeypatch.setattr(m, name, fn, raising=False)


def _run_family(monkeypatch, path, spec, reader, selection_by_desc):
    _install_deterministic_resolver(monkeypatch, selection_by_desc)
    saved_reader = spec.reader
    object.__setattr__(spec, "reader", reader)
    try:
        res = es.materialize_edge_family(CASE_ID, path, spec, write_back=True)
    finally:
        object.__setattr__(spec, "reader", saved_reader)
    out = Graph()
    out.parse(path, format="turtle")
    return res, out


# --- Board pattern matching --------------------------------------------------

def test_board_literal_pattern():
    assert es._is_board_literal("NSPE Board of Ethical Review")
    assert es._is_board_literal("the NSPE Board of Ethical Review (BER)")
    assert es._is_board_literal("Board of Ethical Review")
    assert es._is_board_literal("the Board")
    assert es._is_board_literal("NSPE Board")
    assert es._is_board_literal("board")
    # Non-Board boards and ordinary actors must NOT match.
    assert not es._is_board_literal("State Licensing Board")
    assert not es._is_board_literal("Engineer A")
    assert not es._is_board_literal("")
    assert not es._is_board_literal(None)


def test_strip_role_parenthetical():
    assert es._strip_role_parenthetical("John Smith (Senior Engineer)") == "John Smith"
    assert es._strip_role_parenthetical("Engineer A") == "Engineer A"
    assert es._strip_role_parenthetical("Engineer A (Licensed Environmental Engineer) ") == "Engineer A"
    assert es._strip_role_parenthetical("") == ""


# --- citedByAgent: Board fallback + normal resolution ------------------------

def test_cited_by_agent_board_fallback_mints_agent_and_edge(monkeypatch):
    g = Graph()
    _ind(g, CASE["BER_Case_90-6"], "BER Case 90-6", category="Resource")
    _agent(g, CASE["Agent_Engineer_A"], "Engineer A")

    def reader(cid, spec):
        return [es.SubjectRow(label="BER Case 90-6",
                              fields={"citedByAgent": ["NSPE Board of Ethical Review"]},
                              extra={"subj_label": "BER Case 90-6"})]

    path = _write(g)
    try:
        res, out = _run_family(monkeypatch, path, es._PARTICIPANT_SPEC, reader, {})
    finally:
        os.unlink(path)

    # The single case-scoped Board Agent exists, typed as the participant range class.
    assert (BOARD, RDF.type, CORE.Agent) in out
    assert (BOARD, RDF.type, OWL.NamedIndividual) in out
    assert next(out.objects(BOARD, RDFS.label)) == Literal(es.BOARD_AGENT_LABEL)
    # It carries provenance like other materialized nodes.
    assert list(out.objects(BOARD, PROV.wasAttributedTo))
    # The edge and its PROV Derivation are present, with the verbatim literal.
    assert (CASE["BER_Case_90-6"], CORE.citedByAgent, BOARD) in out
    prov_nodes = [n for n in out.subjects(RDF.type, PROV.Derivation)
                  if "citedByAgent" in str(n)]
    assert len(prov_nodes) == 1
    assert next(out.objects(prov_nodes[0], PROV.value)) == Literal(
        "NSPE Board of Ethical Review")
    assert res["citedByAgent"]["edges"] == 1
    assert res["citedByAgent"]["board_agent_edges"] == 1


def test_board_agent_not_minted_for_non_board_institution(monkeypatch):
    """A non-Board institution goes through normal resolution; when it matches no
    case agent it is unresolved -- no edge, no Board Agent, only a log."""
    g = Graph()
    _ind(g, CASE["Res_Standard"], "Design Standard", category="Resource")
    _agent(g, CASE["Agent_Engineer_A"], "Engineer A")

    def reader(cid, spec):
        return [es.SubjectRow(label="Design Standard",
                              fields={"citedByAgent": ["State Licensing Board"]},
                              extra={"subj_label": "Design Standard"})]

    path = _write(g)
    try:
        res, out = _run_family(monkeypatch, path, es._PARTICIPANT_SPEC, reader, {})
    finally:
        os.unlink(path)

    assert (BOARD, RDF.type, CORE.Agent) not in out
    assert res["citedByAgent"]["edges"] == 0
    assert res["citedByAgent"]["unresolved"] == 1


def test_board_agent_created_once_and_rematerialization_dedupes(monkeypatch):
    """invokedBy AND citedByAgent Board literals in one run share ONE Board Agent;
    a second materialization over the written file adds nothing."""
    g = Graph()
    _ind(g, CASE["Prin_PublicSafety"], "Public Safety Paramount", category="Principle")
    _ind(g, CASE["Res_Code"], "NSPE Code of Ethics", category="Resource")
    _agent(g, CASE["Agent_Engineer_A"], "Engineer A")

    def reader(cid, spec):
        return [
            es.SubjectRow(label="Public Safety Paramount",
                          fields={"invokedBy": ["the Board", "Engineer A"]},
                          extra={"subj_label": "Public Safety Paramount"}),
            es.SubjectRow(label="NSPE Code of Ethics",
                          fields={"citedByAgent": ["NSPE Board of Ethical Review"]},
                          extra={"subj_label": "NSPE Code of Ethics"}),
        ]

    sel = {"Engineer A": [CASE["Agent_Engineer_A"]]}
    path = _write(g)
    try:
        res1, out1 = _run_family(monkeypatch, path, es._PARTICIPANT_SPEC, reader, sel)
        # Exactly one Board Agent node (one label triple).
        assert len(list(out1.objects(BOARD, RDFS.label))) == 1
        assert (CASE["Prin_PublicSafety"], CORE.invokedBy, BOARD) in out1
        assert (CASE["Res_Code"], CORE.citedByAgent, BOARD) in out1
        # The non-Board party still resolves through the normal path.
        assert (CASE["Prin_PublicSafety"], CORE.invokedBy, CASE["Agent_Engineer_A"]) in out1
        assert res1["invokedBy"]["edges"] == 2
        assert res1["invokedBy"]["board_agent_edges"] == 1
        assert res1["citedByAgent"]["board_agent_edges"] == 1

        # Re-materialization over the SAME file: nothing new (edge + node dedupe).
        res2, out2 = _run_family(monkeypatch, path, es._PARTICIPANT_SPEC, reader, sel)
        assert res2["invokedBy"]["edges"] == 0
        assert res2["citedByAgent"]["edges"] == 0
        assert len(list(out2.objects(BOARD, RDFS.label))) == 1
        assert len([n for n in out2.subjects(RDF.type, PROV.Derivation)]) == \
               len([n for n in out1.subjects(RDF.type, PROV.Derivation)])
    finally:
        os.unlink(path)


def test_board_agent_excluded_from_agent_pool(monkeypatch):
    """The materialized Board Agent must never enter _agent_pool, so it can never be
    matched as a used_by/availableTo reliance actor or any embedding-resolved actor."""
    g = Graph()
    _agent(g, CASE["Agent_Engineer_A"], "Engineer A")
    assert es._ensure_board_agent(g, CASE_ID) == BOARD

    monkeypatch.setattr(er, "_embed", lambda svc, text: [1.0] if text else None)
    pool = er._agent_pool(g, object())
    iris = {iri for iri, _t, _e in pool}
    assert CASE["Agent_Engineer_A"] in iris
    assert BOARD not in iris
    assert not any(str(i).endswith(er.BOARD_AGENT_LOCALNAME) for i in iris)


# --- isPerformedBy -----------------------------------------------------------

def test_is_performed_by_golden(monkeypatch):
    g = Graph()
    _ind(g, CASE["Action_AI_Tool_Adoption"], "AI Tool Adoption", category="Action")
    _agent(g, CASE["Agent_Engineer_A"], "Engineer A")

    def reader(cid, spec):
        # _read_participants has already normalized "Engineer A (Senior Engineer)".
        return [es.SubjectRow(label="AI Tool Adoption",
                              fields={"isPerformedBy": ["Engineer A"]},
                              extra={"subj_label": "AI Tool Adoption"})]

    sel = {"Engineer A": [CASE["Agent_Engineer_A"]]}
    path = _write(g)
    try:
        res, out = _run_family(monkeypatch, path, es._PARTICIPANT_SPEC, reader, sel)
    finally:
        os.unlink(path)

    assert (CASE["Action_AI_Tool_Adoption"], CORE.isPerformedBy,
            CASE["Agent_Engineer_A"]) in out
    assert res["isPerformedBy"]["edges"] == 1
    prov_nodes = [n for n in out.subjects(RDF.type, PROV.Derivation)
                  if "isPerformedBy" in str(n)]
    assert len(prov_nodes) == 1


def test_is_performed_by_unresolved_agent_yields_no_edge(monkeypatch):
    """Endpoint chain failure (no case Agent matches the hasAgent text) falls back to
    no-edge; the count is reported, the graph gains nothing."""
    g = Graph()
    _ind(g, CASE["Action_Review"], "Cursory Plan Review", category="Action")
    _agent(g, CASE["Agent_Client_W"], "Client W")

    def reader(cid, spec):
        return [es.SubjectRow(label="Cursory Plan Review",
                              fields={"isPerformedBy": ["Unknown Contractor"]},
                              extra={"subj_label": "Cursory Plan Review"})]

    path = _write(g)
    try:
        res, out = _run_family(monkeypatch, path, es._PARTICIPANT_SPEC, reader, {})
    finally:
        os.unlink(path)

    assert res["isPerformedBy"]["edges"] == 0
    assert res["isPerformedBy"]["unresolved"] == 1
    assert not list(out.objects(CASE["Action_Review"], CORE.isPerformedBy))


# --- the participant reader (temporal row shape + normalization) -------------

class _StubQuery:
    """Minimal TemporaryRDFStorage.query stand-in keyed by extraction_type."""

    def __init__(self, rows_by_type):
        self._rows_by_type = rows_by_type
        self._rows = []

    def filter_by(self, **kw):
        q = _StubQuery(self._rows_by_type)
        q._rows = self._rows_by_type.get(kw.get("extraction_type"), [])
        return q

    def all(self):
        return self._rows


def _row(entity_label, rdf_json_ld):
    return SimpleNamespace(entity_label=entity_label, rdf_json_ld=rdf_json_ld)


def test_read_participants_temporal_shape_and_normalization(monkeypatch):
    """isPerformedBy reads Step-3 rows (top-level proeth: keys, @type-filtered to
    Action) and strips the role parenthetical; citedByAgent reads the Pass-1/2
    'properties' wrapper. Event/TemporalRelation rows are skipped."""
    import app.models.temporary_rdf_storage as trs

    rows_by_type = {
        "temporal_dynamics_enhanced": [
            _row("AI Tool Adoption",
                 {"@type": "proeth:Action", "rdfs:label": "AI Tool Adoption",
                  "proeth:hasAgent": "Engineer A (Senior Engineer)"}),
            _row("Mentor Retirement",
                 {"@type": "proeth:Event", "rdfs:label": "Mentor Retirement",
                  "proeth:hasAgent": "Engineer B"}),
            _row("memo before request",
                 {"@type": "proeth:TemporalRelation"}),
        ],
        "resources": [
            _row("BER Case 90-6",
                 {"properties": {"citedBy": ["NSPE Board of Ethical Review"]}}),
        ],
    }
    # The readers import TemporaryRDFStorage at call time; patch the MODULE
    # attribute (patching the class 'query' descriptor needs an app context).
    monkeypatch.setattr(trs, "TemporaryRDFStorage",
                        SimpleNamespace(query=_StubQuery(rows_by_type)))

    rows = es._read_participants(7, es._PARTICIPANT_SPEC)
    by_pred = {}
    for r in rows:
        for k, v in r.fields.items():
            by_pred.setdefault(k, []).append((r.label, v))

    # Only the Action row feeds isPerformedBy, with the parenthetical stripped.
    assert by_pred["isPerformedBy"] == [("AI Tool Adoption", ["Engineer A"])]
    # The resource row feeds citedByAgent through the properties wrapper.
    assert by_pred["citedByAgent"] == [("BER Case 90-6",
                                        ["NSPE Board of Ethical Review"])]


def test_read_capability_requirements_reader(monkeypatch):
    """The capability-loop reader consumes requiredForObligations from the capability
    INDIVIDUAL rows (properties wrapper) per the capability-loop contract."""
    import app.models.temporary_rdf_storage as trs

    rows_by_type = {
        "capabilities": [
            _row("Engineering Analysis Capability",
                 {"properties": {"requiredForObligations":
                                 ["Safety Obligation", "Responsible Charge Obligation"]}}),
            _row("Fact Gathering", {"properties": {"possessedBy": ["Engineer A"]}}),
        ],
    }
    monkeypatch.setattr(trs, "TemporaryRDFStorage",
                        SimpleNamespace(query=_StubQuery(rows_by_type)))

    rows = es._read_capability_requirements(7, es._REQUIRES_CAPABILITY_SPEC)
    assert len(rows) == 1
    assert rows[0].label == "Engineering Analysis Capability"
    assert rows[0].fields["requiresCapability"] == [
        "Safety Obligation", "Responsible Charge Obligation"]


# --- requiresCapability (inverted emission) -----------------------------------

def test_requires_capability_inverted_golden(monkeypatch):
    """The committed edge runs Obligation -> Capability (core v2.8.0 domain/range)
    even though the reader row subject is the Capability."""
    g = Graph()
    _ind(g, CASE["Cap_Analysis"], "Engineering Analysis Capability", category="Capability")
    _ind(g, CASE["Obl_Safety"], "Safety Obligation", category="Obligation")
    _ind(g, CASE["Obl_Charge"], "Responsible Charge Obligation", category="Obligation")

    labels = ["Safety Obligation", "Responsible Charge Obligation"]
    desc = "; ".join(labels)
    sel = {desc: [CASE["Obl_Safety"], CASE["Obl_Charge"]]}

    def reader(cid, spec):
        return [es.SubjectRow(label="Engineering Analysis Capability",
                              fields={"requiresCapability": labels},
                              extra={"subj_label": "Engineering Analysis Capability"})]

    path = _write(g)
    try:
        res, out = _run_family(monkeypatch, path, es._REQUIRES_CAPABILITY_SPEC, reader, sel)
    finally:
        os.unlink(path)

    # Direction: Obligation --requiresCapability--> Capability.
    assert (CASE["Obl_Safety"], CORE.requiresCapability, CASE["Cap_Analysis"]) in out
    assert (CASE["Obl_Charge"], CORE.requiresCapability, CASE["Cap_Analysis"]) in out
    # The un-inverted direction must NOT exist.
    assert (CASE["Cap_Analysis"], CORE.requiresCapability, CASE["Obl_Safety"]) not in out
    assert res["requiresCapability"]["edges"] == 2
    # PROV nodes follow the emitted (obligation, capability) direction.
    prov_nodes = {str(n) for n in out.subjects(RDF.type, PROV.Derivation)}
    assert str(CASE["capability_requirement_provenance_Obl_Safety_"
                    "requiresCapability_Cap_Analysis"]) in prov_nodes


def test_requires_capability_unresolved_falls_back_to_no_edge(monkeypatch):
    g = Graph()
    _ind(g, CASE["Cap_Writing"], "Technical Writing Capability", category="Capability")
    _ind(g, CASE["Obl_Safety"], "Safety Obligation", category="Obligation")

    def reader(cid, spec):
        return [es.SubjectRow(label="Technical Writing Capability",
                              fields={"requiresCapability": ["A duty never extracted"]},
                              extra={"subj_label": "Technical Writing Capability"})]

    path = _write(g)
    try:
        res, out = _run_family(monkeypatch, path, es._REQUIRES_CAPABILITY_SPEC, reader, {})
    finally:
        os.unlink(path)

    assert res["requiresCapability"]["edges"] == 0
    assert res["requiresCapability"]["unresolved"] == 1
    assert not list(out.subjects(CORE.requiresCapability, CASE["Cap_Writing"]))


def test_requires_capability_subject_not_committed_is_skipped(monkeypatch):
    """A capability row whose label matches no committed Capability individual is
    skipped (subject chain validation), never emitted against a guessed IRI."""
    g = Graph()
    _ind(g, CASE["Obl_Safety"], "Safety Obligation", category="Obligation")

    def reader(cid, spec):
        return [es.SubjectRow(label="Phantom Capability",
                              fields={"requiresCapability": ["Safety Obligation"]},
                              extra={"subj_label": "Phantom Capability"})]

    sel = {"Safety Obligation": [CASE["Obl_Safety"]]}
    path = _write(g)
    try:
        res, out = _run_family(monkeypatch, path, es._REQUIRES_CAPABILITY_SPEC, reader, sel)
    finally:
        os.unlink(path)

    assert res["requiresCapability"]["edges"] == 0
    assert not list(out.subject_objects(CORE.requiresCapability))


# --- guard registry -----------------------------------------------------------

def test_new_edge_families_are_guarded():
    assert ALL_EDGE_RANGE[CORE.requiresCapability] == ("Obligation", "Capability")
    dom, rng = ALL_EDGE_RANGE[CORE.establishedBy]
    assert dom == {"Principle", "Obligation", "Constraint"}
    assert rng == "CodeProvision"


def test_registry_contains_requires_capability_family():
    names = [s.name for s in es.EDGE_REGISTRY]
    assert "requires_capability_edges" in names
    spec = next(s for s in es.EDGE_REGISTRY if s.name == "requires_capability_edges")
    assert spec.extraction_type == "capabilities"
    assert spec.subject_category == "Capability"
    (pred,) = spec.predicates
    assert pred.invert
    assert pred.range_category == "Obligation"
    assert pred.fields == ("requiredForObligations", "required_for_obligations")
