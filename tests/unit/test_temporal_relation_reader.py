"""Reader-level guard for the temporal_relation_edges family (A/E properties review).

The 2026-06-19 EdgeSpec migration dropped the proeth: prefix from the family's
carrier keys, so _read_temporal matched no field and the family silently
no-opped on every commit. The golden equivalence test constructs SubjectRow
objects directly and bypassed the reader, masking the regression. This test
feeds a REAL-shape rdf_json_ld row (top-level proeth: keys, exactly what the
Step-3 converter stores) through the reader path.
"""
from unittest.mock import MagicMock, patch

from app.services.extraction.edge_spec import EDGE_REGISTRY, _read_temporal


def _spec(name):
    return next(s for s in EDGE_REGISTRY if s.name == name)


def _row(label, rdf):
    r = MagicMock()
    r.entity_label = label
    r.rdf_json_ld = rdf
    return r


def test_read_temporal_matches_prefixed_endpoint_keys():
    spec = _spec("temporal_relation_edges")
    real_shape = {
        "@type": "proeth:TemporalRelation",
        "rdfs:label": "Report Filing before Board Review",
        "proeth:fromEntity": "Report Filing",
        "proeth:toEntity": "Board Review",
        "proeth:allenRelation": "before",
        "proeth:owlTimeProperty": "time:intervalBefore",
        "proeth:evidence": "the report was filed before the board reviewed it",
    }
    with patch("app.models.temporary_rdf_storage.TemporaryRDFStorage") as m:
        m.query.filter_by.return_value.all.return_value = [
            _row("Report Filing before Board Review", real_shape)
        ]
        rows = _read_temporal(8, spec)
    assert len(rows) == 1, "the reader must match the stored proeth:-prefixed keys"
    fields = rows[0].fields
    assert fields.get("fromEntity") == ["Report Filing"]
    assert fields.get("toEntity") == ["Board Review"]


def test_every_registry_predicate_lists_a_prefixed_carrier_key():
    # The Step-3/commit stores prefix top-level keys with proeth:; a bare-only
    # fields tuple can never match them (the exact defect this guards).
    for spec in EDGE_REGISTRY:
        for pred in spec.predicates:
            assert any(k.startswith("proeth:") for k in pred.fields) or \
                   any(":" not in k for k in pred.fields) and spec.name not in ("temporal_relation_edges",), \
                f"{spec.name}.{pred.name} lists no prefixed carrier key: {pred.fields}"
