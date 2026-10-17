"""Review of the prompts-and-filters lessons (brief 2): the defects fixed on the review branch.

1. A role individual whose ``generates_obligations`` arrived as a bare string or a null failed
   validation and was skipped by the per-item parser, so the new routing input of lesson L9
   could drop a role the model had extracted (the free-form fallback path carries no grammar
   that enforces the array). The field now folds a string into one entry and a null into none.
2. The actor cue of the segmenter (lesson L3) split a recap paragraph at the first sentence naming
   a present-case engineer letter whenever the opening sentence did not name it. A precedent
   whose own engineer first appears in its second sentence and shares the letter of the present case
   (Engineer A in most of the corpus) therefore leaked the rest of its recap into the
   present-case text. The actor cue now applies only when the opening sentence names an
   engineer foreign to the present case.
3. The verification gate recorded a quote that was verbatim and only snapped to the case's
   spelling (lesson L5) under the same review-notes marker as a re-grounded paraphrase. The gate
   now reports the snapped-only rows and the commit task marks them as snapped.
4. The integration merge put the two L5 lessons side by side: the commit-definitions skip of a
   linked row whose quotes pass the token test ran before the prompts-and-filters snap, so a
   matched row with the case 8 spelling ("Engineer L" newline "'s scope of work") kept it in the
   committed literal. The skipped row keeps its skip (no model call) and still gets the snap.

DB/LLM-free: the schemas and the segmenter run as pure functions, the span-finding call of the
gate is mocked (every quote passes the token test locally).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.extraction.discussion_segmenter import (
    _actor_cues, _split_recap_tail, segment_discussion,
)
from app.services.extraction.schemas import RoleExtractionResult, RoleIndividual
from app.services.extraction.verification_gate import gate_quote_marker, verify_case_entities

_HREF = 'https://www.nspe.org/resources/ethics/ethics-resources/board-ethical-review-cases/'


# ---------------------------------------------------------------------------
# 1. generates_obligations as a bare string or a null
# ---------------------------------------------------------------------------

def test_bare_string_generates_obligations_is_one_entry():
    ind = RoleIndividual.model_validate({
        "identifier": "Engineer L Design Engineer", "role_kind": "professional",
        "generates_obligations": "hold paramount the safety, health and welfare of the public",
    })
    assert ind.generates_obligations == ["hold paramount the safety, health and welfare of the public"]
    assert RoleIndividual.model_validate({"identifier": "X", "generates_obligations": ""}).generates_obligations == []
    assert RoleIndividual.model_validate({"identifier": "X", "generates_obligations": None}).generates_obligations == []
    # a list passes through unchanged
    assert RoleIndividual.model_validate(
        {"identifier": "X", "generates_obligations": ["a", "b"]}).generates_obligations == ["a", "b"]


def test_full_result_keeps_a_role_whose_generates_obligations_is_a_string():
    """The full-schema parse (the first attempt of parse_and_validate) accepts the response; before
    the fix it raised and the per-item fallback skipped the individual."""
    result = RoleExtractionResult.model_validate({
        "new_role_classes": [],
        "role_individuals": [
            {"identifier": "Engineer L Design Engineer", "actor": "Engineer L",
             "role_class": "Design Engineer Role", "role_kind": "professional",
             "generates_obligations": "hold paramount the public welfare"},
            {"identifier": "Client X Developer", "actor": "Client X", "role_class": "Client Role",
             "role_kind": "participant", "generates_obligations": []},
        ],
    })
    assert [i.identifier for i in result.role_individuals] == ["Engineer L Design Engineer", "Client X Developer"]
    assert result.role_individuals[0].generates_obligations == ["hold paramount the public welfare"]


# ---------------------------------------------------------------------------
# 2. the actor cue needs a foreign engineer in the opening sentence of the recap
# ---------------------------------------------------------------------------

def test_shared_letter_named_after_the_opening_sentence_stays_recap():
    """The engineer of the present case is A (the usual letter). The recap of BER Case 82-5 names its
    own Engineer A in its second sentence; that sentence and the rest of the recap must not become
    present-case text."""
    html = (
        f'<p>In <a href="{_HREF}82-5">BER Case 82-5</a>, the Board reviewed a dispute over a building '
        f'design. Engineer A had prepared the drawings and refused to seal them after the owner altered '
        f'them. The Board found that Engineer A acted properly.</p>'
        f'<p>Turning to the present case, Engineer A faces a similar demand from the client.</p>'
    )
    r = segment_discussion(html, present_actors=["Engineer A"])
    assert r.method == "deterministic"
    assert "Engineer A had prepared the drawings" not in r.present_case_text
    assert "acted properly" not in r.present_case_text
    assert r.present_case_text == "Turning to the present case, Engineer A faces a similar demand from the client."
    assert r.paragraphs[0].present_tail == ""
    assert "Engineer A had prepared the drawings" in r.precedent_recaps[0]['text']


def test_continuation_paragraph_of_a_precedent_keeps_its_sentences():
    """A second paragraph on the same precedent opens without a letter and names the shared
    letter next; nothing splits."""
    text = ("The Board reasoned that the duty to the public is paramount. Engineer A therefore had to "
            "report the hazard. The Board found no violation.")
    assert _split_recap_tail(text, _actor_cues(["Engineer A"])) == (text, "")


def test_actor_cue_still_splits_after_a_foreign_engineer_in_the_opening_sentence():
    """The branch behaviour stands when the opening sentence names the engineer of the precedent itself:
    a later sentence naming the present engineer is the present-case tail."""
    text = ("In BER Case 84-5, Engineer B reported a hazard to the authorities. The Board held that "
            "Engineer B owed a duty to the public. Engineer L faces the same choice on the stormwater "
            "safeguards.")
    head, tail = _split_recap_tail(text, _actor_cues(["Engineer L"]))
    assert tail == "Engineer L faces the same choice on the stormwater safeguards."
    assert head.endswith("owed a duty to the public.")
    # the phrase cues are independent of the actor cue
    phrase = "In BER Case 76-4, the Board considered a similar situation. We note a direct parallel here."
    assert _split_recap_tail(phrase, _actor_cues(["Engineer A"]))[1] == "We note a direct parallel here."


# ---------------------------------------------------------------------------
# 3. snapped-only rows are reported and marked as snapped, not re-grounded
# ---------------------------------------------------------------------------

CASE_TEXT = ("Facts: the developer insisted that the work fell within Engineer L’s scope of work. "
             "Engineer L signed the report before the review began.")


def _gate(entities):
    with patch('app.services.extraction.extraction_verifier._structured_stream_json') as llm, \
         patch('app.utils.llm_utils.get_llm_client', return_value=MagicMock()), \
         patch('model_config.ModelConfig') as cfg:
        cfg.get_claude_model.return_value = 'test-model'
        res = verify_case_entities(entities, CASE_TEXT, case_id=8)
        llm.assert_not_called()
    return res


def test_gate_reports_snapped_only_rows():
    entities = [
        {'id': 1, 'label': 'Engineer L Scope Duty', 'definition': 'x', 'component': 'obligations',
         'storage_type': 'individual', 'quotes': ["Engineer L\n's scope of work"], 'class_ref': ''},
        {'id': 2, 'label': 'Report Signing', 'definition': 'x', 'component': 'roles',
         'storage_type': 'individual', 'quotes': ["Engineer L signed the report"], 'class_ref': ''},
    ]
    res = _gate(entities)
    assert res.corrected_quotes == {1: ["Engineer L’s scope of work"]}
    assert res.snapped_only == {1}
    assert res.report['snapped_ids'] == [1]
    assert gate_quote_marker(res, 1) == 'quotes snapped to the case span at gate'


def test_linked_row_skipped_by_the_gate_is_still_snapped():
    """A row the matcher linked at 0.95 with a token-verbatim quote is left unjudged (the
    commit-definitions skip) and its quote is still rewritten to the characters of the case text."""
    entities = [
        {'id': 5, 'label': 'Engineer L Scope Duty', 'definition': 'x', 'component': 'obligations',
         'storage_type': 'individual', 'quotes': ["Engineer L\n's scope of work"], 'class_ref': '',
         'match_confidence': 0.95},
        {'id': 6, 'label': 'Report Signing', 'definition': 'x', 'component': 'roles',
         'storage_type': 'individual', 'quotes': ["Engineer L signed the report"], 'class_ref': '',
         'match_confidence': 0.95},
    ]
    res = _gate(entities)
    assert [s[0] for s in res.skipped] == [5, 6]
    assert res.corrected_quotes == {5: ["Engineer L’s scope of work"]}
    assert res.snapped_only == {5}
    assert res.report['snapped'] == 1 and res.report['snapped_ids'] == [5]
    assert res.dropped == []


def test_gate_quote_marker_distinguishes_the_three_cases():
    gate = SimpleNamespace(repaired_quoteless={7}, snapped_only={1})
    assert gate_quote_marker(gate, 7) == 'quotes ATTACHED at gate (model emitted none)'
    assert gate_quote_marker(gate, 1) == 'quotes snapped to the case span at gate'
    assert gate_quote_marker(gate, 3) == 'quotes re-grounded at gate'
    # a result object without the new field (an older double) falls back to re-grounded
    assert gate_quote_marker(SimpleNamespace(repaired_quoteless=set()), 1) == 'quotes re-grounded at gate'
