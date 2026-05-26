"""Unit tests for the Allen-relation -> OWL-Time property mapper.

Covers the 2026-05-26 consistency fix: precedes/before and after/preceded_by now
map to the Allen INTERVAL relations time:intervalBefore / time:intervalAfter
(consistent with the other 11 time:interval* relations), not the general
time:before / time:after ordering properties.
"""
from app.services.temporal_dynamics.utils.allen_owl_time_mapper import (
    ALLEN_TO_OWL_TIME,
    ALLEN_13_BASIC_RELATIONS,
    map_allen_to_owl_time,
    get_owl_time_uri,
    create_allen_relation_metadata,
)


def test_precedes_and_before_map_to_interval_before():
    assert map_allen_to_owl_time("precedes") == "time:intervalBefore"
    assert map_allen_to_owl_time("before") == "time:intervalBefore"
    assert get_owl_time_uri("time:intervalBefore") == "http://www.w3.org/2006/time#intervalBefore"


def test_after_and_preceded_by_map_to_interval_after():
    assert map_allen_to_owl_time("after") == "time:intervalAfter"
    assert map_allen_to_owl_time("preceded_by") == "time:intervalAfter"
    assert get_owl_time_uri("time:intervalAfter") == "http://www.w3.org/2006/time#intervalAfter"


def test_other_relations_unchanged():
    assert map_allen_to_owl_time("meets") == "time:intervalMeets"
    assert map_allen_to_owl_time("during") == "time:intervalDuring"
    assert map_allen_to_owl_time("overlaps") == "time:intervalOverlaps"
    assert map_allen_to_owl_time("equals") == "time:intervalEquals"


def test_metadata_carries_interval_property_and_uri():
    meta = create_allen_relation_metadata("precedes")
    assert meta["owl_time_property"] == "time:intervalBefore"
    assert meta["owl_time_uri"] == "http://www.w3.org/2006/time#intervalBefore"
    assert meta["proeth_relation"] == "precedes"


def test_all_allen_mappings_are_interval_specific():
    """Regression guard: no Allen relation may map to a general ordering property.

    The whole point of the fix is that all 13 interval relations (and their
    aliases) use time:interval*; a future edit reintroducing time:before/time:after
    in the Allen map should fail here.
    """
    offenders = {rel: prop for rel, prop in ALLEN_TO_OWL_TIME.items()
                 if not prop.startswith("time:interval")}
    assert offenders == {}, f"non-interval OWL-Time mappings remain: {offenders}"


def test_all_13_basic_relations_resolve_to_a_uri():
    for rel in ALLEN_13_BASIC_RELATIONS:
        prop = map_allen_to_owl_time(rel)
        assert prop is not None, f"{rel} has no OWL-Time mapping"
        assert get_owl_time_uri(prop) is not None, f"{prop} has no URI"
