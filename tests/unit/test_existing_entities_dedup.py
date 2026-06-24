"""Unit tests for the existing-class dedup in prompt_variable_resolver.

The MCP category query returns one row per (ontology, entity); every case ontology
self-contains a copy of each class it uses under the SAME canonical URI, so the
injected class list was dominated by redundant per-case copies (case 15 roles: 852
rows -> 521 distinct). _dedup_entities_by_uri collapses them losslessly, preferring
the highest-authority source so the survivor classifies into the right tier.
"""
from app.services.prompt_variable_resolver import (
    _dedup_entities_by_uri,
    _curated_only,
    _is_case_copy,
    format_existing_entities,
)

CANON_URI = "http://proethica.org/ontology/intermediate#StakeholderRole"
EXT_URI = "http://proethica.org/ontology/intermediate#DiscoveredEngineerRole"


def test_curated_only_drops_case_copies_keeps_curated():
    """The injected matching vocabulary is the curated layers only; per-case
    self-containment copies are excluded even though they carry a canonical URI."""
    rows = [
        {"uri": CANON_URI, "label": "Stakeholder Role", "ontology_name": "proethica-intermediate"},
        {"uri": CANON_URI, "label": "StakeholderRole", "ontology_name": "proethica-case-15"},
        {"uri": EXT_URI, "label": "Discovered Engineer Role",
         "ontology_name": "proethica-intermediate-extended"},
        {"uri": "http://x#CaseOnly", "label": "Case Only Compound Role",
         "ontology_name": "proethica-case-72"},
    ]
    assert _is_case_copy(rows[1]) and not _is_case_copy(rows[0])
    cur = _curated_only(rows)
    srcs = sorted(r["ontology_name"] for r in cur)
    # both case-sourced rows dropped (incl. the case-only compound class)
    assert srcs == ["proethica-intermediate", "proethica-intermediate-extended"]


def test_format_excludes_case_copies_end_to_end():
    rows = [
        {"uri": CANON_URI, "label": "Stakeholder Role", "ontology_name": "proethica-intermediate"},
        {"uri": "http://x#C1", "label": "Compound One", "ontology_name": "proethica-case-1"},
        {"uri": "http://x#C2", "label": "Compound Two", "ontology_name": "proethica-case-2"},
    ]
    block = format_existing_entities(rows, "roles")
    assert "Stakeholder Role" in block
    assert "Compound One" not in block and "Compound Two" not in block


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
    """Within the curated vocabulary the formatted block carries no duplicate class
    lines: the same URI in intermediate and intermediate-extended collapses (kept in
    the canonical tier), and the extended-only class lands in PREVIOUSLY EXTRACTED."""
    rows = [
        {"uri": CANON_URI, "label": "Stakeholder Role", "ontology_name": "proethica-intermediate"},
        {"uri": CANON_URI, "label": "Stakeholder Role", "ontology_name": "proethica-intermediate-extended"},
        {"uri": EXT_URI, "label": "Discovered Engineer Role",
         "ontology_name": "proethica-intermediate-extended"},
    ]
    block = format_existing_entities(rows, "roles")
    assert "=== CANONICAL ONTOLOGY CLASSES" in block
    assert "=== PREVIOUSLY EXTRACTED CLASSES" in block
    # Scope to the inventory: format_existing_entities now prepends the reference-sheet
    # reuse block (its own "- " lines), so count class lines from the inventory header on.
    inventory = block.split("=== CANONICAL ONTOLOGY CLASSES", 1)[1]
    class_lines = [l for l in inventory.splitlines() if l.startswith("- ")]
    assert len(class_lines) == len(set(class_lines)) == 2


def test_reuse_block_prepended_with_canonical_guidance():
    """format_existing_entities leads with the reference-sheet reuse-bias block: the canonical
    classes to reuse, the synonym folds, and the compound anti-patterns that reduce LLM minting
    of context-laden classes (step 2 of the canonicalization calibration)."""
    rows = [{"uri": CANON_URI, "label": "Stakeholder Role",
             "ontology_name": "proethica-intermediate"}]
    block = format_existing_entities(rows, "roles")
    # Reuse guidance comes first, the live inventory after it.
    assert block.index("REUSE THESE CANONICAL ROLE") < block.index("=== CANONICAL ONTOLOGY CLASSES")
    # A known role anti-pattern is present (compound role -> canonical role).
    assert "AI Tool Reliant Engineer -> EngineerRole" in block
    # Constraint folds reach the constraint prompt (manifest cross-component redirect).
    cblock = format_existing_entities([], "constraints")
    assert "AI Tool Disclosure Constraint -> AIToolDisclosureObligation" in cblock
