"""Unit tests for the existing-class dedup in prompt_variable_resolver.

The MCP category query returns one row per (ontology, entity); every case ontology
self-contains a copy of each class it uses under the SAME canonical URI, so the
injected class list was dominated by redundant per-case copies (case 15 roles: 852
rows -> 521 distinct). _dedup_entities_by_uri collapses them losslessly, preferring
the highest-authority source so the survivor classifies into the right tier.
"""
from app.services.prompt_variable_resolver import (
    _dedup_entities_by_uri,
    format_existing_entities,
)

CANON_URI = "http://proethica.org/ontology/intermediate#StakeholderRole"
EXT_URI = "http://proethica.org/ontology/intermediate#DiscoveredEngineerRole"


def test_dedup_collapses_per_case_copies_losslessly():
    """21 case copies of one URI collapse to a single entry; distinct URIs survive."""
    rows = [
        {"uri": CANON_URI, "label": "StakeholderRole", "ontology_name": f"proethica-case-{i}"}
        for i in range(21)
    ]
    rows.append({"uri": EXT_URI, "label": "DiscoveredEngineerRole",
                 "ontology_name": "proethica-case-5"})
    out = _dedup_entities_by_uri(rows)
    assert len(out) == 2
    assert {e["uri"] for e in out} == {CANON_URI, EXT_URI}


def test_dedup_prefers_authoritative_source():
    """When a URI appears in both a case copy and intermediate-extended, the
    extended row wins so it lands in the PREVIOUSLY EXTRACTED tier with its
    canonical definition."""
    rows = [
        {"uri": EXT_URI, "label": "DiscoveredEngineerRole",
         "ontology_name": "proethica-case-9", "definition": "case copy def"},
        {"uri": EXT_URI, "label": "DiscoveredEngineerRole",
         "ontology_name": "proethica-intermediate-extended", "definition": "canonical def"},
    ]
    out = _dedup_entities_by_uri(rows)
    assert len(out) == 1
    assert out[0]["ontology_name"] == "proethica-intermediate-extended"
    assert out[0]["definition"] == "canonical def"


def test_dedup_keeps_no_uri_entities_by_label():
    rows = [
        {"label": "LabelOnlyRole"},
        {"label": "LabelOnlyRole"},   # duplicate label, no URI -> collapse
        {"label": "OtherRole"},
    ]
    out = _dedup_entities_by_uri(rows)
    labels = sorted(e["label"] for e in out)
    assert labels == ["LabelOnlyRole", "OtherRole"]


def test_format_existing_entities_has_no_duplicate_lines():
    """The formatted block (what the prompt injects) carries no duplicate class lines
    and routes the extended class into PREVIOUSLY EXTRACTED, the case-only archetype
    into CANONICAL."""
    rows = [
        {"uri": CANON_URI, "label": "StakeholderRole", "ontology_name": "proethica-case-1"},
        {"uri": CANON_URI, "label": "StakeholderRole", "ontology_name": "proethica-case-2"},
        {"uri": EXT_URI, "label": "DiscoveredEngineerRole",
         "ontology_name": "proethica-intermediate-extended"},
    ]
    block = format_existing_entities(rows, "roles")
    class_lines = [l for l in block.splitlines() if l.startswith("- ")]
    assert len(class_lines) == len(set(class_lines)) == 2
    assert "=== CANONICAL ONTOLOGY CLASSES" in block
    assert "=== PREVIOUSLY EXTRACTED CLASSES" in block
