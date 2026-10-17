"""Type-level recurrence along the rdfs:subClassOf chain (case-8 review, L7).

defeasibility_view_service._relation compared the leaf intermediate class
strings exactly, so cases typed PublicSafetyObligation (rdfs:subClassOf
SafetyObligation) never appeared as recurrences of a SafetyObligation anchor,
and _type_display split CamelCase, rendering "Safety Withdrawaland Notification
Obligation" for a fragment lacking a capital although the class carries a
correct rdfs:label. Types now compare up the chain of the shared ontology tiers
and display through the class label.

Hermetic: the ontology tiers are a fixture graph injected in place of
_intermediate_graph.
"""
from rdflib import Graph, Literal, Namespace, RDF, RDFS, OWL

from unittest.mock import MagicMock, patch

from app.services import defeasibility_view_service as svc
from tests.test_defeasibility_band_dynamic import _Doc, _Row

INT = Namespace("http://proethica.org/ontology/intermediate#")
CORE = Namespace("http://proethica.org/ontology/core#")


def _tiers():
    g = Graph()
    for local, parent in (("SafetyObligation", CORE.Obligation),
                          ("PublicSafetyObligation", INT.SafetyObligation),
                          ("WatershedSafetyObligation", INT.SafetyObligation),
                          ("SafetyWithdrawalandNotificationObligation", INT.SafetyObligation),
                          ("FaithfulAgentObligation", INT.ProfessionalObligation),
                          ("ProfessionalObligation", CORE.Obligation),
                          ("ConfidentialityObligation", CORE.Obligation),
                          ("ObjectivityObligation", CORE.Obligation)):
        g.add((INT[local], RDF.type, OWL.Class))
        g.add((INT[local], RDFS.subClassOf, parent))
    g.add((INT.SafetyWithdrawalandNotificationObligation, RDFS.label,
           Literal("Safety Withdrawal and Notification Obligation", lang="en")))
    g.add((INT.SafetyObligation, RDFS.label, Literal("Safety Obligation", lang="en")))
    return g


def test_type_ancestors_follow_the_intermediate_chain_and_stop_at_core():
    g = _tiers()
    assert svc._type_ancestors("PublicSafetyObligation", g) == {"PublicSafetyObligation", "SafetyObligation"}
    assert svc._type_ancestors("SafetyObligation", g) == {"SafetyObligation"}
    assert svc._type_ancestors("Unknown", g) == {"Unknown"}
    assert svc._type_ancestors(None, g) == set()


def test_types_related_up_and_down_the_chain_but_not_across_siblings():
    g = _tiers()
    anc = lambda local: svc._type_ancestors(local, g)
    assert svc._types_related("PublicSafetyObligation", "SafetyObligation", anc)
    assert svc._types_related("SafetyObligation", "PublicSafetyObligation", anc)
    assert svc._types_related("SafetyObligation", "SafetyObligation", anc)
    # Siblings share a parent but neither specializes the other.
    assert not svc._types_related("PublicSafetyObligation", "WatershedSafetyObligation", anc)
    # Core categories are not ancestors: two obligations are not related merely as obligations.
    assert not svc._types_related("ObjectivityObligation", "SafetyObligation", anc)
    # Multi-typed values match on any pair; empty values never match.
    assert svc._types_related("ObjectivityObligation; PublicSafetyObligation", "SafetyObligation", anc)
    assert not svc._types_related(None, "SafetyObligation", anc)


def test_type_relation_ranks_use_the_chain():
    g = _tiers()
    anc = lambda local: svc._type_ancestors(local, g)
    related = lambda a, b: svc._types_related(a, b, anc)
    wt, lt = "SafetyObligation", "FaithfulAgentObligation"
    assert svc._type_relation("PublicSafetyObligation", "FaithfulAgentObligation", wt, lt, related)[0] == 1
    assert svc._type_relation("FaithfulAgentObligation", "WatershedSafetyObligation", wt, lt, related)[0] == 2
    assert svc._type_relation("FaithfulAgentObligation", "ObjectivityObligation", wt, lt, related)[0] == 3
    assert svc._type_relation("ObjectivityObligation", "SafetyWithdrawalandNotificationObligation", wt, lt, related)[0] == 4
    assert svc._type_relation("ObjectivityObligation", "FaithfulAgentObligation", wt, lt, related)[0] == 5
    assert svc._type_relation("PublicSafetyObligation", "ObjectivityObligation", wt, lt, related)[0] == 6
    # The anchor's loser type specializes ProfessionalObligation, so a row yielding there recurs (rank 5).
    assert svc._type_relation("ObjectivityObligation", "ProfessionalObligation", wt, lt, related)[0] == 5
    assert svc._type_relation("ObjectivityObligation", "ConfidentialityObligation", wt, lt, related) is None


def test_type_display_uses_the_class_label():
    g = _tiers()
    assert svc._type_display("SafetyWithdrawalandNotificationObligation", g) == \
        "Safety Withdrawal and Notification Obligation"
    assert svc._type_display("FaithfulAgentObligation", g) == "Faithful Agent Obligation"
    assert svc._type_display("PublicSafetyObligation; SafetyObligation", g) == \
        "Public Safety Obligation; Safety Obligation"
    assert svc._type_display(None, g) is None


def _run_with_tiers(rows, anchor):
    """tests.test_defeasibility_band_dynamic._run with the fixture tiers in place of
    the empty ontology graph that module pins."""
    vocab = {"W": [1.0, 0.0, 0.0], "L": [0.0, 1.0, 0.0]}
    emb_inst = MagicMock()
    emb_inst.get_embedding.side_effect = lambda text: vocab[text]
    embedding_service = MagicMock()
    embedding_service.get_instance.return_value = emb_inst
    band_index = MagicMock()
    band_index.query.filter.return_value.all.return_value = rows
    document = MagicMock()
    document.query.get.side_effect = lambda cid: _Doc(cid)
    with patch('app.services.embedding.embedding_service.EmbeddingService', embedding_service), \
            patch('app.models.defeasibility_band_index.DefeasibilityBandIndex', band_index), \
            patch('app.models.Document', document), \
            patch.object(svc, '_intermediate_graph', _tiers):
        return svc.get_cross_case_band_dynamic(7, {"conflicts": [anchor]})


def test_band_type_patterns_recur_a_subclass_of_the_anchor_type():
    anchor = {"winner": "W", "loser": "L", "contexts": [], "featured": True,
              "winner_type": "SafetyObligation", "loser_type": "FaithfulAgentObligation"}
    rows = [
        _Row(40, "Wa", "La", [0, 0, 1], [0, 0, 1],
             winner_type="PublicSafetyObligation", loser_type="FaithfulAgentObligation"),
        _Row(41, "Wb", "Lb", [0, 0, 1], [0, 0, 1],
             winner_type="FaithfulAgentObligation", loser_type="SafetyWithdrawalandNotificationObligation"),
        _Row(42, "Wc", "Lc", [0, 0, 1], [0, 0, 1],
             winner_type="ObjectivityObligation", loser_type="ConfidentialityObligation"),
    ]
    band = _run_with_tiers(rows, anchor)
    tp = band["type_patterns"]
    assert [(t["case_id"], t["rank"]) for t in tp["rows"]] == [(40, 1), (41, 2)]
    assert tp["rows"][0]["winner_type_display"] == "Public Safety Obligation"
    assert tp["rows"][1]["loser_type_display"] == "Safety Withdrawal and Notification Obligation"
    assert tp["winner_type_display"] == "Safety Obligation"
