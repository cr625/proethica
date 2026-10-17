"""Case-8 (NSPE 24-1) review lessons on parsing and the schemas: L2 (facts-pass compliance
status, the tension_resolution validator), L5 (escape decoding, stray tail), L8 (the action
modality field), L9 (the generates_obligations slot and the role post-parse checks).

DB/LLM-free: the parser mixin is exercised on a bare extractor, the schemas directly.
"""
from app.services.extraction.schemas import (
    ActionIndividual, PrincipleIndividual, RoleIndividual, RoleKind,
)
from app.services.extraction.unified_dual_extractor import UnifiedDualExtractor, CONCEPT_CONFIG
from app.services.extraction.unified_dual_extractor.parsing import (
    decode_unicode_escapes, strip_stray_tail,
)
from app.services.extraction import role_checks
from app.services.extraction.field_classification import FieldKind, classify


def _bare(concept_type, section=None):
    ext = object.__new__(UnifiedDualExtractor)
    ext.concept_type = concept_type
    ext.config = CONCEPT_CONFIG[concept_type]
    ext.existing_classes = []
    ext.injection_mode = "full"
    ext.apply_filters = True
    if section:
        ext._current_section_type = section
    return ext


# ---------------------------------------------------------------------------
# L5: literal hygiene in _normalize_field_names
# ---------------------------------------------------------------------------

def test_decode_unicode_escapes_restores_the_curly_apostrophe():
    assert decode_unicode_escapes("Engineer L\\u2019s scope of work") == "Engineer L’s scope of work"
    assert decode_unicode_escapes(["a\\u2019b", "plain"]) == ["a’b", "plain"]
    assert decode_unicode_escapes("\\ud83d\\ude00") == "\U0001F600"
    assert decode_unicode_escapes("no escapes") == "no escapes"
    assert decode_unicode_escapes(3) == 3


def test_normalize_decodes_escapes_in_quote_fields():
    ext = _bare("obligations", "discussion")
    item = ext._normalize_field_names({
        "identifier": "Engineer L Scope Duty",
        "source_text": "within Engineer L\\u2019s scope of work",
        "text_references": ["within Engineer L\\u2019s scope of work"],
    })
    assert item["source_text"] == "within Engineer L’s scope of work"
    assert item["text_references"] == ["within Engineer L’s scope of work"]


def test_strip_stray_tail_observed_string():
    assert strip_stray_tail("Engineer L objected to the developer's insistence.on") == \
        "Engineer L objected to the developer's insistence.on"[:-2]
    # untouched: a clean sentence, a code designation, a domain tail
    assert strip_stray_tail("Engineer L objected.") == "Engineer L objected."
    assert strip_stray_tail("NSPE Code Section II.1.a") == "NSPE Code Section II.1.a"
    assert strip_stray_tail("see proethica.org") == "see proethica.org"
    assert strip_stray_tail(None) is None


def test_normalize_strips_stray_tail_from_case_context_only():
    ext = _bare("obligations", "discussion")
    item = ext._normalize_field_names({
        "identifier": "Engineer L Scope Duty",
        "case_context": "The developer pressed Engineer L despite the engineer's insistence.on",
        "text_references": ["the engineer's insistence.on"],
    })
    assert item["case_context"].endswith("insistence.")
    # quotes are left to the commit-time verbatim snap
    assert item["text_references"] == ["the engineer's insistence.on"]


# ---------------------------------------------------------------------------
# L2: facts-pass compliance status is always "unclear"
# ---------------------------------------------------------------------------

def test_facts_pass_resets_compliance_status_to_unclear():
    ext = _bare("obligations", "facts")
    item = ext._normalize_field_names({"identifier": "Engineer L Public Welfare Duty",
                                       "compliance_status": "partial"})
    assert item["compliance_status"] == "unclear"


def test_discussion_pass_keeps_compliance_status():
    ext = _bare("obligations", "discussion")
    item = ext._normalize_field_names({"identifier": "Engineer L Public Welfare Duty",
                                       "compliance_status": "partial"})
    assert item["compliance_status"] == "partial"


def test_other_components_untouched_by_the_facts_reset():
    ext = _bare("constraints", "facts")
    item = ext._normalize_field_names({"identifier": "X", "compliance_status": "met"})
    assert item["compliance_status"] == "met"


# ---------------------------------------------------------------------------
# L2: a populated tension_resolution needs a balancing_with
# ---------------------------------------------------------------------------

def test_orphan_tension_resolution_is_rejected():
    ind = PrincipleIndividual.model_validate({
        "identifier": "Public Welfare Paramountcy", "principle_class": "Public Welfare Principle",
        "tension_resolution": "Unresolved in the facts; the Board has not yet weighed the values.",
        "balancing_with": [],
    })
    assert ind.tension_resolution is None
    assert ind.identifier == "Public Welfare Paramountcy"


def test_paired_tension_resolution_is_kept():
    ind = PrincipleIndividual.model_validate({
        "identifier": "Public Welfare Paramountcy", "principle_class": "Public Welfare Principle",
        "tension_resolution": "Public welfare prevailed over the developer's schedule.",
        "balancing_with": ["Faithful Agent Principle"],
    })
    assert ind.tension_resolution == "Public welfare prevailed over the developer's schedule."
    assert ind.balancing_with == ["Faithful Agent Principle"]


def test_string_balancing_with_counts_as_populated():
    ind = PrincipleIndividual.model_validate({
        "identifier": "P", "principle_class": "C",
        "tension_resolution": "Resolved.", "balancing_with": "Loyalty Principle",
    })
    assert ind.tension_resolution == "Resolved."
    assert ind.balancing_with == ["Loyalty Principle"]


# ---------------------------------------------------------------------------
# L8: the action modality field
# ---------------------------------------------------------------------------

def test_action_modality_round_trips_by_alias_and_name():
    a = ActionIndividual.model_validate({"rdfs:label": "Acquiescence", "proeth:modality": "prescribed"})
    assert a.modality == "prescribed"
    b = ActionIndividual.model_validate({"label": "Report Signing", "modality": "performed"})
    assert b.modality == "performed"
    c = ActionIndividual.model_validate({"label": "Report Signing", "modality": ""})
    assert c.modality is None


# ---------------------------------------------------------------------------
# L9: generates_obligations slot and the role post-parse checks
# ---------------------------------------------------------------------------

def test_generates_obligations_slot_is_a_relation_routing_input():
    ind = RoleIndividual.model_validate({"identifier": "Engineer L Design Engineer",
                                         "generates_obligations": ["Hold paramount the public welfare"]})
    assert ind.generates_obligations == ["Hold paramount the public welfare"]
    assert RoleIndividual.model_validate({"identifier": "X"}).generates_obligations == []
    # classified RELATION so the commit emitter never writes it as a literal
    assert classify("generatesObligations") is FieldKind.RELATION


def _role(identifier, actor, role_class, kind=None, rels=(), category=None, obligations=()):
    return RoleIndividual.model_validate({
        "identifier": identifier, "actor": actor, "role_class": role_class,
        "role_kind": kind, "role_category": category,
        "relationships": [{"type": t, "target": g, "quote": q} for t, g, q in rels],
        "generates_obligations": list(obligations),
    })


def test_professional_without_named_obligation_is_rejected():
    board = _role("NSPE Board Ethics Reviewer", "NSPE Board of Ethical Review",
                  "Ethics Review Board Role", kind="professional")
    engineer = _role("Engineer L Design Engineer", "Engineer L", "Design Engineer Role",
                     kind="professional", obligations=["hold paramount the public welfare"])
    participant = _role("Developer Client", "Developer", "Client Role", kind="participant")
    changed = role_checks.reject_unsupported_professional([board, engineer, participant])
    assert changed == ["NSPE Board Ethics Reviewer"]
    assert board.role_kind is None
    assert engineer.role_kind is RoleKind.professional
    assert participant.role_kind is RoleKind.participant


def test_duplicate_relational_facet_is_folded_into_the_existing_facet():
    design = _role("Engineer L Design Engineer", "Engineer L", "Design Engineer Role",
                   kind="professional", obligations=["public welfare"],
                   rels=[("hasClient", "Developer", "retained by the developer")])
    faithful = _role("Engineer L Faithful Agent", "Engineer L", "Faithful Agent Role",
                     category="provider_client",
                     rels=[("hasClient", "Developer", "faithful agent of the developer"),
                           ("relatedTo", "Developer", "owes candor to the developer")])
    other_actor = _role("Engineer M Faithful Agent", "Engineer M", "Faithful Agent Role",
                        rels=[("hasClient", "Developer", "x")])
    witness = _role("Engineer L Expert Witness", "Engineer L", "Expert Witness Role",
                    rels=[("hasClient", "Developer", "testified for the developer")])
    kept, folded = role_checks.fold_duplicate_relational_facets([design, faithful, other_actor, witness])
    assert [k.identifier for k in kept] == ["Engineer L Design Engineer", "Engineer M Faithful Agent",
                                            "Engineer L Expert Witness"]
    assert folded == [{"dropped": "Engineer L Faithful Agent", "into": "Engineer L Design Engineer"}]
    # the standing travels onto the existing facet: the new (type, target) pair and the category
    assert [(r.type, r.target) for r in design.relationships] == [("hasClient", "Developer"),
                                                                  ("relatedTo", "Developer")]
    assert design.role_category is not None and design.role_category.value == "provider_client"


def test_relational_facet_toward_a_new_counterparty_is_kept():
    design = _role("Engineer L Design Engineer", "Engineer L", "Design Engineer Role",
                   rels=[("hasClient", "Developer", "q")])
    public = _role("Engineer L Public Responsibility", "Engineer L", "Public Responsibility Role",
                   rels=[("owesDutyToward", "the public", "q")])
    kept, folded = role_checks.fold_duplicate_relational_facets([design, public])
    assert len(kept) == 2 and folded == []


def test_apply_role_checks_reports_both():
    board = _role("Board", "NSPE Board of Ethical Review", "Ethics Review Board Role", kind="professional")
    design = _role("Engineer L Design Engineer", "Engineer L", "Design Engineer Role",
                   rels=[("hasClient", "Developer", "q")])
    faithful = _role("Engineer L Faithful Agent", "Engineer L", "Faithful Agent Role",
                     rels=[("hasClient", "Developer", "q")])
    kept, report = role_checks.apply_role_checks([board, design, faithful])
    assert [k.identifier for k in kept] == ["Board", "Engineer L Design Engineer"]
    assert report == {"professional_rejected": ["Board"],
                      "facets_folded": [{"dropped": "Engineer L Faithful Agent",
                                         "into": "Engineer L Design Engineer"}]}
