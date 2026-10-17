"""Case-8 (NSPE 24-1) review lessons on the filters and quote hygiene: L4 (the individual/type
filter) and L5 (the verbatim snap in the verifier and gate, the Allen evidence requirement).

DB/LLM-free: the Tier-2 judge is a fake streaming client, the gate's span-finding call is
mocked (no pending quotes reach it here), the Allen grounding is a pure function.
"""
from unittest.mock import MagicMock, patch

from app.services.extraction import individual_type_filter as f
from app.services.extraction.individual_type_filter import (
    CRITERIA, filter_individuals, judge_dict, referenced_labels,
)
from app.services.extraction.quote_grounding import verbatim_span
from app.services.extraction.schemas import ResourceIndividual
from app.services.extraction.verification_gate import verify_case_entities
from app.services.temporal_dynamics.extractors.temporal_marker_extractor import (
    _ground_allen_evidence,
)

RES = "resources"

_STANDARDS = {
    "label": "Local Environmental Standards", "resource_class": "Legal Resource",
    "used_by": "Engineer L", "topic": "safeguarding public water sources from stormwater impacts",
    "quote": "local environmental standards require steps to safeguard public water sources",
}


# ---------------------------------------------------------------------------
# L4: the relied-on resource is a Tier-1 keep; the judge sees the detail and the quote
# ---------------------------------------------------------------------------

def test_relied_on_resource_is_kept_deterministically():
    res = filter_individuals([_STANDARDS], RES, use_llm=False)
    assert [i["label"] for i in res["kept"]] == ["Local Environmental Standards"]
    assert res["dropped"] == []
    assert res["resolver"] == "deterministic-only"  # nothing was ambiguous


def test_relied_on_resource_never_reaches_the_judge():
    judge = MagicMock(side_effect=AssertionError("the judge must not be called"))
    with patch.object(f, "_llm_classify", judge):
        res = filter_individuals([_STANDARDS], RES, use_llm=True, client=object(), model="x")
    assert len(res["kept"]) == 1 and res["llm_items"] == 0


def test_without_reliance_the_item_stays_ambiguous():
    bare = {k: v for k, v in _STANDARDS.items() if k not in ("used_by",)}
    res = filter_individuals([bare], RES, use_llm=False)
    assert len(res["kept"]) == 1
    assert res["resolver"] == "deterministic"  # ambiguous, kept without the LLM


def test_self_instance_with_reliance_is_still_judged_not_kept_outright():
    """A reliance signal on a self-instance does not make it a clear keep (the type-as-instance
    dodge could carry a used_by); it is ambiguous, so the judge decides."""
    item = {"label": "Peer Review Conduct Standard Instance",
            "resource_class": "Peer Review Conduct Standard", "used_by": "Engineer A"}
    res = filter_individuals([item], RES, use_llm=False)
    assert res["resolver"] == "deterministic" and len(res["kept"]) == 1


def test_self_instance_without_signal_still_drops():
    item = {"label": "Peer Review Conduct Standard Instance",
            "resource_class": "Peer Review Conduct Standard"}
    res = filter_individuals([item], RES, use_llm=False)
    assert res["dropped"][0][1] == "deterministic:self-instance"


def test_judge_dict_carries_topic_used_by_and_quote():
    ind = ResourceIndividual.model_validate({
        "identifier": "Local Environmental Standards", "resource_class": "Legal Resource",
        "topic": "safeguarding public water sources from stormwater impacts", "used_by": "Engineer L",
        "text_references": ["local environmental standards require steps to safeguard public water sources"],
    })
    d = judge_dict(ind, RES)
    assert d["label"] == "Local Environmental Standards" and d["instance_of"] == "Legal Resource"
    assert d["definition"] == ("topic: safeguarding public water sources from stormwater impacts; "
                               "used_by: Engineer L")
    assert d["quote"] == "local environmental standards require steps to safeguard public water sources"
    assert d["used_by"] == "Engineer L"


def test_judge_dict_other_components_use_their_statement_fields():
    from app.services.extraction.schemas import ObligationIndividual
    ind = ObligationIndividual.model_validate({
        "identifier": "Engineer L Public Welfare Duty", "obligation_class": "Public Welfare Obligation",
        "obligation_statement": "Engineer L shall hold paramount the public welfare.",
        "obligated_party": "Engineer L"})
    d = judge_dict(ind, "obligations")
    assert d["definition"] == ("obligation_statement: Engineer L shall hold paramount the public welfare.; "
                               "obligated_party: Engineer L")


class _StubTemplate:
    def render(self, **kw):
        return "CRITERIA: " + kw.get("drop_kinds", "") + "\nITEMS:\n" + kw.get("items", "")


def test_judge_prompt_shows_detail_quote_and_reliance_signal(monkeypatch):
    monkeypatch.setattr(f, "_load_filter_template", lambda: _StubTemplate())
    item = dict(_STANDARDS, definition="topic: safeguarding public water sources; used_by: Engineer L")
    flags = f.compute_flags([item], CRITERIA[RES].instance_marker, CRITERIA[RES].reliance_fields)
    prompt = f._build_prompt([item], flags, CRITERIA[RES])
    assert 'detail: "topic: safeguarding public water sources; used_by: Engineer L"' in prompt
    assert 'quote: "local environmental standards require steps to safeguard public water sources"' in prompt
    assert "the case ties it to an actor (used_by / cited_by)" in prompt
    # the CRITERIA text states the reliance rule
    assert "relied on, used, or was bound by is an INSTANCE" in prompt


def test_depended_on_label_is_protected_from_the_drop():
    item = {"label": "Peer Review Conduct Standard Instance",
            "resource_class": "Peer Review Conduct Standard"}
    res = filter_individuals([item], RES, use_llm=False,
                             depended_on={"peer review conduct standard instance"})
    assert res["dropped"] == [] and len(res["kept"]) == 1


def test_referenced_labels_collects_reference_fields():
    dicts = [{"label": "Engineer L Scope Duty", "source": "Local Environmental Standards"},
             {"label": "Stormwater Review Capability", "required_for_obligations": ["Engineer L Scope Duty"]}]
    assert referenced_labels(dicts) == {"local environmental standards", "engineer l scope duty"}


# ---------------------------------------------------------------------------
# L5: the verbatim snap
# ---------------------------------------------------------------------------

CASE_TEXT = ("Facts: the developer insisted that the work fell within Engineer L’s scope of work. "
             "Engineer L signed the report before the review began. "
             "The Board concluded that Engineer L cannot ethically acquiesce in the developer’s insistence.")


def test_verbatim_span_returns_the_cases_own_characters():
    stored = "Engineer L\n's scope of work"
    assert verbatim_span(stored, CASE_TEXT) == "Engineer L’s scope of work"
    assert verbatim_span("Engineer L signed the report", CASE_TEXT) == "Engineer L signed the report"
    assert verbatim_span("signed the contract", CASE_TEXT) is None
    assert verbatim_span("", CASE_TEXT) is None
    # token-boundary anchored: a mid-word fragment does not match
    assert verbatim_span("gineer L signed", CASE_TEXT) is None


def _gate(entities):
    with patch('app.services.extraction.extraction_verifier._structured_stream_json') as llm, \
         patch('app.utils.llm_utils.get_llm_client', return_value=MagicMock()), \
         patch('model_config.ModelConfig') as cfg:
        cfg.get_claude_model.return_value = 'test-model'
        res = verify_case_entities(entities, CASE_TEXT, case_id=8)
        llm.assert_not_called()  # every quote passed the token test locally
    return res


def test_gate_snaps_a_token_verbatim_quote_to_the_case_span():
    entities = [{'id': 1, 'label': 'Engineer L Scope Duty', 'definition': 'x', 'component': 'obligations',
                 'storage_type': 'individual', 'quotes': ["Engineer L\n's scope of work"], 'class_ref': ''}]
    res = _gate(entities)
    assert res.dropped == []
    assert res.corrected_quotes[1] == ["Engineer L’s scope of work"]
    assert res.report['snapped'] == 1


def test_gate_leaves_an_exact_quote_alone():
    entities = [{'id': 2, 'label': 'Report Signing', 'definition': 'x', 'component': 'roles',
                 'storage_type': 'individual', 'quotes': ["Engineer L signed the report"], 'class_ref': ''}]
    res = _gate(entities)
    assert res.corrected_quotes == {}
    assert res.report['snapped'] == 0


# ---------------------------------------------------------------------------
# L5: Allen relation evidence must be a verbatim span
# ---------------------------------------------------------------------------

def test_allen_evidence_hedge_is_removed_and_span_snapped():
    markers = {'allen_relations': [
        {'entity1': 'report signing', 'relation': 'before', 'entity2': 'review',
         'evidence': "Engineer L (apparently) signed the report before the review began"},
        {'entity1': 'insistence', 'relation': 'before', 'entity2': 'signing',
         'evidence': "the developer insisted that the work fell within Engineer L's scope of work"},
        {'entity1': 'x', 'relation': 'after', 'entity2': 'y',
         'evidence': "a sentence the case never states"},
    ]}
    out = _ground_allen_evidence(markers, CASE_TEXT)
    rels = out['allen_relations']
    assert [r['evidence'] for r in rels] == [
        "Engineer L signed the report before the review began",
        "the developer insisted that the work fell within Engineer L’s scope of work",
    ]


def test_allen_evidence_untouched_when_all_verbatim():
    markers = {'allen_relations': [{'entity1': 'a', 'relation': 'before', 'entity2': 'b',
                                    'evidence': "Engineer L signed the report before the review began"}],
               'explicit_dates': []}
    out = _ground_allen_evidence(markers, CASE_TEXT)
    assert out['allen_relations'][0]['evidence'] == "Engineer L signed the report before the review began"
    assert out['explicit_dates'] == []
