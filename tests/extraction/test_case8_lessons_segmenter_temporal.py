"""Case-8 (NSPE 24-1) review lessons on the discussion segmenter (L3) and the Step-3 happenings
(L8): recap-paragraph tail splitting, the resources exemption, action modality routing, fluent
link validation, the closed state list in the prompts, and the modality field in the JSON-LD.

DB/LLM-free: the segmenter runs its deterministic path, the happening checks are pure functions,
the prompt builders read only the ontology TTL / SHACL files.
"""
from app.services.extraction.discussion_segmenter import (
    SEGMENTATION_EXEMPT_CONCEPTS, _split_recap_tail, _actor_cues, section_text_for_concept,
    segment_discussion,
)
from app.services.temporal_dynamics.utils.happening_checks import (
    apply_action_modality, classify_action_modality, finalize_events, state_label_block,
    validate_fluent_links,
)
from app.services.temporal_dynamics.utils.rdf_converter import convert_action_to_rdf
from app.services.temporal_dynamics.extractors.action_extractor import _build_phase1_prompt
from app.services.temporal_dynamics.extractors.event_extractor import _build_event_extraction_prompt

_HREF = 'https://www.nspe.org/resources/ethics/ethics-resources/board-ethical-review-cases/'


def _link(case):
    return f'<a href="{_HREF}{case}" target="_blank">BER Case {case}</a>'


# A fixture built from the sentences the case-8 review quoted: two recap paragraphs whose tails
# turn to the present case, then the present-case cue paragraph.
CASE8_HTML = (
    f"<p>In {_link('67-10')}, Engineer A was retained by a developer to design the drainage of a "
    f"subdivision. The Board found that Engineer A, relying on Section II.1.a, acted properly in "
    f"refusing to certify the plans. We note a direct parallel between the 1984 case and the facts "
    f"under consideration.</p>"
    f"<p>In {_link('84-5')}, Engineer B reported a hazard to the authorities. The Board held that "
    f"Engineer B owed a duty to the public. Engineer L faces the same choice on the stormwater "
    f"safeguards.</p>"
    f"<p>Turning to the facts of the present situation, Engineer L must weigh the local "
    f"environmental standards against the developer's insistence.</p>"
)


def _sections(r):
    full = "\n\n".join(p.text for p in r.paragraphs)
    return {'facts': 'Engineer L was retained.', 'discussion': r.present_case_text,
            'discussion_full': full, 'precedent_recaps': r.precedent_recaps}


# ---------------------------------------------------------------------------
# L3: recap tails that turn to the present case stay in the present-case text
# ---------------------------------------------------------------------------

def test_case8_recap_tails_are_kept_as_present_case_text():
    r = segment_discussion(CASE8_HTML, present_actors=["Engineer L"])
    assert r.method == "deterministic"
    assert [p.label for p in r.paragraphs] == ["recap", "recap", "present"]
    # the phrase cue ("We note") and the actor cue ("Engineer L") each release a tail
    assert "We note a direct parallel between the 1984 case and the facts under consideration." in r.present_case_text
    assert "Engineer L faces the same choice on the stormwater safeguards." in r.present_case_text
    assert "Turning to the facts of the present situation" in r.present_case_text
    # the recap heads stay out of the present-case text
    assert "Engineer A was retained by a developer" not in r.present_case_text
    assert "Engineer B reported a hazard" not in r.present_case_text
    # and the recap spans carry only the heads
    assert len(r.precedent_recaps) == 2
    assert r.precedent_recaps[0]['cited_case'] == '67-10'
    assert "We note" not in r.precedent_recaps[0]['text']
    assert r.paragraphs[0].present_tail.startswith("We note")
    # document order is preserved
    assert r.present_case_text.index("We note") < r.present_case_text.index("Engineer L faces") \
        < r.present_case_text.index("Turning to")


def test_without_actor_cues_only_phrase_cues_split():
    r = segment_discussion(CASE8_HTML)
    assert "We note a direct parallel" in r.present_case_text
    assert "Engineer L faces the same choice" not in r.present_case_text
    assert r.paragraphs[1].present_tail == ""


def test_actor_cue_disabled_when_the_recap_head_names_the_same_letter():
    """Case 60 and BER Case 19-3 both lead with Engineer A: the letter cannot separate them, so the
    actor cue is not used for that paragraph (the collision the segmenter exists for)."""
    head = "In BER Case 19-3, Engineer A chairs a boiler code committee while Engineer B is retained."
    tail = "Engineer A later testified against the plaintiff in that proceeding."
    assert _split_recap_tail(f"{head} {tail}", _actor_cues(["Engineer A"])) == (f"{head} {tail}", "")
    # the phrase cue still applies to the same paragraph
    assert _split_recap_tail(f"{head} In contrast, the present engineer never testified.",
                             _actor_cues(["Engineer A"]))[1] == "In contrast, the present engineer never testified."


def test_opening_sentence_of_a_recap_never_splits():
    text = "We note that in BER Case 19-3 the Board found no violation. The Board reasoned at length."
    assert _split_recap_tail(text, []) == (text, "")
    assert _split_recap_tail("One sentence only.", _actor_cues(["Engineer L"])) == ("One sentence only.", "")


def test_citation_abbreviations_do_not_split_sentences():
    text = "In BER Case No. 67-10, Engineer A refused. We note the parallel to the present case."
    head, tail = _split_recap_tail(text, [])
    assert head == "In BER Case No. 67-10, Engineer A refused."
    assert tail == "We note the parallel to the present case."


def test_sentences_ending_in_a_closing_quote_still_split():
    """A recap whose sentences end in quotations (case 56, BER Case 95-10) releases the
    present-case analysis after it: the split also breaks after a closing quotation mark, so the
    cue sentence no longer merges into the opening sentence of the recap."""
    head = ("BER Case 95-10 considered an engineering firm that listed key personnel with titles "
            "including “Engineer” and “Design Engineer.”")
    middle = "The case discussion indicated that “we in the profession must not.”"
    tail = ("It should be noted that in the present case, NSPE Code of Ethics Section II.5.a. is "
            "very clear. Engineer A is obligated to report the violation of Engineer B.")
    assert _split_recap_tail(f"{head} {middle} {tail}", []) == (f"{head} {middle}", tail)
    # a straight quote mark and a closing parenthesis end a sentence as well
    assert _split_recap_tail('In BER Case 92-2, the Board said "no." (See II.1.f.) In the present '
                             'case, the facts differ.', [])[1] == "In the present case, the facts differ."


def test_no_precedent_links_segmentation_unchanged():
    html = "<p>Engineer L was retained to evaluate the design.</p><p>We note nothing here.</p>"
    r = segment_discussion(html, present_actors=["Engineer L"])
    assert r.method == "none" and r.precedent_recaps == []
    assert "We note nothing here." in r.present_case_text


# ---------------------------------------------------------------------------
# L3: the resources pass receives the full discussion
# ---------------------------------------------------------------------------

def test_resources_pass_is_exempt_from_segmentation():
    assert SEGMENTATION_EXEMPT_CONCEPTS == frozenset({"resources"})
    r = segment_discussion(CASE8_HTML, present_actors=["Engineer L"])
    sections = _sections(r)
    # the segmented text lost the recap-only mentions of II.1.a and BER Case 67-10 ...
    assert "II.1.a" not in sections['discussion'] and "67-10" not in sections['discussion']
    # ... which the resources pass still receives
    resources_text = section_text_for_concept(sections, 'discussion', 'resources')
    assert resources_text == sections['discussion_full']
    assert "Section II.1.a" in resources_text and "BER Case 67-10" in resources_text
    # the other Step-1 concepts and the facts pass are unchanged
    assert section_text_for_concept(sections, 'discussion', 'roles') == sections['discussion']
    assert section_text_for_concept(sections, 'discussion', 'states') == sections['discussion']
    assert section_text_for_concept(sections, 'facts', 'resources') == 'Engineer L was retained.'


def test_section_text_falls_back_when_no_full_discussion_stored():
    sections = {'facts': 'f', 'discussion': 'present only'}
    assert section_text_for_concept(sections, 'discussion', 'resources') == 'present only'
    assert section_text_for_concept({}, 'discussion', 'roles') == ''


# ---------------------------------------------------------------------------
# L8: action modality routing
# ---------------------------------------------------------------------------

DISCUSSION = ("The Board concluded that Engineer L cannot ethically acquiesce in the developer's "
              "insistence on a design below the local environmental standards.")


def test_board_normative_sentence_from_the_discussion_is_prescribed():
    action = {"label": "Acquiescence Refusal", "source_section": "discussion",
              "temporal_marker": "Present, unresolved endpoint",
              "text_references": ["Engineer L cannot ethically acquiesce in the developer's insistence"]}
    assert classify_action_modality(action, DISCUSSION) == "prescribed"
    # without source_section the discussion text itself places the quote
    del action["source_section"]
    assert classify_action_modality(action, DISCUSSION) == "prescribed"
    # a facts quote is not routed
    assert classify_action_modality(action, "Engineer L signed the report.") == "performed"


def test_narrated_act_stays_performed_and_explicit_modality_is_kept():
    performed = {"label": "Report Signing", "source_section": "facts",
                 "text_references": ["Engineer L signed the report"]}
    assert classify_action_modality(performed, DISCUSSION) == "performed"
    explicit = {"label": "Disclosure", "modality": "prescribed", "text_references": []}
    assert classify_action_modality(explicit, DISCUSSION) == "prescribed"
    mixed = {"label": "Objection", "source_section": "discussion",
             "text_references": ["Engineer L must not acquiesce", "Engineer L objected to the developer"]}
    assert classify_action_modality(mixed, DISCUSSION) == "performed"  # one narrated reference


def test_apply_action_modality_sets_every_action():
    actions = [{"label": "A", "source_section": "discussion", "text_references": ["Engineer L must not acquiesce"]},
               {"label": "B", "text_references": ["Engineer L signed"]}]
    apply_action_modality(actions, DISCUSSION)
    assert [a["modality"] for a in actions] == ["prescribed", "performed"]


def test_modality_is_emitted_in_the_action_json_ld():
    rdf = convert_action_to_rdf({"label": "Acquiescence Refusal", "modality": "prescribed",
                                 "agent": "Engineer L"}, 8)
    assert rdf["proeth:modality"] == "prescribed"
    assert "proeth:modality" not in convert_action_to_rdf({"label": "Signing", "agent": "Engineer L"}, 8)
    assert "proeth:modality" not in convert_action_to_rdf({"label": "Signing", "modality": "maybe"}, 8)


# ---------------------------------------------------------------------------
# L8: initiates / terminates against the closed state list and the happening labels
# ---------------------------------------------------------------------------

def test_fluent_links_validated_against_states_and_happening_labels():
    events = [{"label": "Permit Denial", "initiates": ["Public Safety Risk", "Report Signing", "Imaginary Condition"],
               "terminates": ["Project Active State"]}]
    actions = [{"label": "Report Signing"}]
    _, report = finalize_events(events, actions, state_labels=["Public Safety Risk State", "Project Active State"])
    assert events[0]["initiates"] == ["Public Safety Risk"]       # suffix-insensitive state match
    assert events[0]["terminates"] == ["Project Active State"]
    reasons = {(r["value"], r["reason"]) for r in report}
    assert ("Report Signing", "names a happening, not a state") in reasons
    assert ("Imaginary Condition", "not a State label of this case") in reasons


def test_empty_closed_list_only_rejects_happening_labels():
    happenings = [{"label": "Permit Denial", "initiates": ["Any Condition", "Permit Denial"]}]
    report = validate_fluent_links(happenings, state_labels=[], other_labels=["Permit Denial"], kind="event")
    assert happenings[0]["initiates"] == ["Any Condition"]
    assert report[0]["value"] == "Permit Denial"


# ---------------------------------------------------------------------------
# L8: the prompts carry the closed list and the modality item
# ---------------------------------------------------------------------------

_NARRATIVE = {"unified_timeline_summary": "Engineer L refused.", "decision_points": [],
              "competing_priorities_mentioned": []}


def test_action_prompt_carries_modality_and_closed_state_list():
    prompt = _build_phase1_prompt(_NARRATIVE, {"absolute": [], "relative": []},
                                  facts_text="f", discussion_text="d",
                                  state_labels=["Public Safety Risk State"])
    assert "13. modality:" in prompt and '"modality": "performed"' in prompt
    assert "CASE STATE LABELS (the closed list for initiates / terminates):" in prompt
    assert "- Public Safety Risk State" in prompt


def test_event_prompt_carries_closed_state_list_only_when_known():
    with_states = _build_event_extraction_prompt(_NARRATIVE, {}, [], facts_text="f", discussion_text="d",
                                                 state_labels=["Project Active State"])
    assert "- Project Active State" in with_states
    without = _build_event_extraction_prompt(_NARRATIVE, {}, [], facts_text="f", discussion_text="d")
    assert "CASE STATE LABELS" not in without
    assert state_label_block([]) == "" and state_label_block(None) == ""
