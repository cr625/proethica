"""Unit tests for the predicate classification source of truth.

Guards the registry-derived classification used by serialization, the provenance view,
the temporal review, and the synthesis hand-off (see
docs-internal/reextraction/review-vs-synthesis-fields.md).
"""
import pytest

from app.services.extraction.field_classification import (
    FieldKind,
    classify,
    is_synthesis_literal,
    synthesis_literals,
    partition,
)


@pytest.mark.parametrize("predicate,expected", [
    # RELATION: relationships to individuals (edges, or temp_rdf label sources of edges)
    ("proeth:fulfillsObligation", FieldKind.RELATION),
    ("proeth:obligatedParty", FieldKind.RELATION),
    ("proeth:initiates", FieldKind.RELATION),
    ("proeth:cause", FieldKind.RELATION),
    ("proeth:effect", FieldKind.RELATION),
    ("proeth:responsibleAgent", FieldKind.RELATION),
    ("proeth:guidedByPrinciple", FieldKind.RELATION),
    ("affectedParties", FieldKind.RELATION),
    ("citedBy", FieldKind.RELATION),                  # resolved to the citedByAgent edge
    ("requiredForObligations", FieldKind.RELATION),   # resolved to requiresCapability edges
    ("proeth-core:requiresCapability", FieldKind.RELATION),  # the edge itself
    ("proeth-core:hasObligation", FieldKind.RELATION),
    ("answersQuestion3", FieldKind.RELATION),         # numbered, normalized
    ("claimEntity", FieldKind.RELATION),
    # CONTENT: irreducible source content (default)
    ("proeth:necessaryFactors", FieldKind.CONTENT),
    ("proeth:counterfactual", FieldKind.CONTENT),
    ("proeth:causalLanguage", FieldKind.CONTENT),
    ("obligationStatement", FieldKind.CONTENT),
    ("proeth:description", FieldKind.CONTENT),
    ("proeth:eventType", FieldKind.CONTENT),
    ("questionText", FieldKind.CONTENT),
    ("proeth:fulfillsObligationText", FieldKind.CONTENT),   # demoted literal of a relation
    ("proeth:triggeringEvent", FieldKind.CONTENT),    # irregular shadow of activatedByEvent
    ("terminatedBy", FieldKind.CONTENT),              # irregular shadow of terminatedByEvent
    # ASSESSMENT: LLM judgments
    ("proeth:confidence", FieldKind.ASSESSMENT),
    ("proeth:severity", FieldKind.ASSESSMENT),
    ("proeth:urgencyLevel", FieldKind.ASSESSMENT),
    ("proeth:complianceStatus", FieldKind.ASSESSMENT),
    ("proeth:withinCompetence", FieldKind.ASSESSMENT),
    ("proeth:responsibilityType", FieldKind.ASSESSMENT),
    ("proeth:withinAgentControl", FieldKind.ASSESSMENT),
    ("isValid", FieldKind.ASSESSMENT),
    ("validationNote2", FieldKind.ASSESSMENT),
    # DERIVED: reconstructable from the graph
    ("proeth:totalElements", FieldKind.DERIVED),
    ("proeth:actionCount", FieldKind.DERIVED),
    ("owlTimeProperty", FieldKind.DERIVED),
    ("citedProvision1", FieldKind.DERIVED),
    ("provisionCodes", FieldKind.DERIVED),
    ("proeth:requiresCapabilityText", FieldKind.DERIVED),   # Text sibling registered DERIVED
    ("conclusionNumber", FieldKind.DERIVED),
    ("obligationActivation", FieldKind.DERIVED),
    ("fromEntityText", FieldKind.DERIVED),
    # PROVENANCE: bookkeeping + XAI annotations
    ("proeth-prov:sourceText", FieldKind.PROVENANCE),
    ("generatedAtTime", FieldKind.PROVENANCE),
    ("matchReasoning", FieldKind.PROVENANCE),
    ("discoveredInSection", FieldKind.PROVENANCE),
    ("synthesisLiteral", FieldKind.PROVENANCE),
])
def test_classify(predicate, expected):
    assert classify(predicate) == expected


def test_empty_predicate_defaults_to_content():
    assert classify("") == FieldKind.CONTENT
    assert classify(None) == FieldKind.CONTENT  # type: ignore[arg-type]


def test_is_synthesis_literal():
    assert is_synthesis_literal("proeth:severity")            # ASSESSMENT
    assert is_synthesis_literal("proeth:necessaryFactors")    # CONTENT
    assert not is_synthesis_literal("proeth:fulfillsObligation")  # RELATION
    assert not is_synthesis_literal("proeth:totalElements")   # DERIVED
    assert not is_synthesis_literal("sourceText")             # PROVENANCE


def test_synthesis_literals_filters_and_dedupes():
    got = synthesis_literals([
        "proeth:severity", "proeth:fulfillsObligation", "proeth:necessaryFactors",
        "proeth:totalElements", "sourceText", "proeth:severity",
    ])
    assert got == ["proeth:severity", "proeth:necessaryFactors"]


def test_partition_groups_by_kind():
    groups = partition([
        "proeth:fulfillsObligation", "proeth:severity", "proeth:necessaryFactors",
        "proeth:totalElements", "sourceText",
    ])
    assert groups[FieldKind.RELATION.value] == ["proeth:fulfillsObligation"]
    assert groups[FieldKind.ASSESSMENT.value] == ["proeth:severity"]
    assert groups[FieldKind.CONTENT.value] == ["proeth:necessaryFactors"]
    assert groups[FieldKind.DERIVED.value] == ["proeth:totalElements"]
    assert groups[FieldKind.PROVENANCE.value] == ["sourceText"]


def test_group_properties_temporal_shape():
    from app.services.extraction.field_classification import group_properties
    g = group_properties({
        "@type": "proeth:CausalChain", "rdfs:label": "X",
        "proeth:cause": "Assignment", "proeth:necessaryFactors": ["a", "b"],
        "proeth:responsibilityType": "direct", "proeth:totalElements": 5,
        "proeth:description": "",  # empty -> skipped
    })
    assert g[FieldKind.RELATION.value] == [("proeth:cause", "Assignment")]
    assert g[FieldKind.CONTENT.value] == [("proeth:necessaryFactors", ["a", "b"])]
    assert g[FieldKind.ASSESSMENT.value] == [("proeth:responsibilityType", "direct")]
    assert g[FieldKind.DERIVED.value] == [("proeth:totalElements", 5)]


def test_group_properties_pass12_shape():
    from app.services.extraction.field_classification import group_properties
    g = group_properties({
        "label": "Y",
        "properties": {
            "obligationStatement": ["must X"],
            "confidence": [0.9],
            "obligatedParty": ["Engineer A"],
        },
    })
    assert g[FieldKind.RELATION.value] == [("obligatedParty", ["Engineer A"])]
    assert g[FieldKind.CONTENT.value] == [("obligationStatement", ["must X"])]
    assert g[FieldKind.ASSESSMENT.value] == [("confidence", [0.9])]
