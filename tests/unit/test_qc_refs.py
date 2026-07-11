"""qc_refs contract lock-in (pre-rebuild checklist item 2, 2026-07-10).

The single source for Step-4 question/conclusion reference lists must key
references by the COMMITTED URI whenever the row carries its number, so
stored references resolve to committed individuals directly; entity_uri and
the legacy positional key are fallbacks in that order. analysis_edges must
accept both the committed-URI form and the legacy positional form.
"""
import types

from app.services.step4_synthesis.qc_refs import question_refs, conclusion_refs


def _row(label, uri=None, definition=None, **json_ld):
    return types.SimpleNamespace(entity_label=label, entity_uri=uri,
                                 entity_definition=definition,
                                 rdf_json_ld=json_ld or None)


def test_committed_uri_key_when_number_present():
    rows = [_row('Question_101', questionNumber=101,
                 questionText='Should the constraint have been disclosed?')]
    refs = question_refs(9, rows)
    assert refs[0]['uri'] == 'case-9#Question_101'
    assert refs[0]['number'] == 101
    assert refs[0]['text'] == 'Should the constraint have been disclosed?'


def test_entity_uri_then_positional_fallbacks():
    rows = [_row('Q-with-uri', uri='case-9#Something', definition='text a'),
            _row('Q-bare', definition='text b')]
    refs = question_refs(9, rows)
    assert refs[0]['uri'] == 'case-9#Something'
    assert refs[1]['uri'] == 'case-9#Q2'          # legacy positional, 1-based
    assert refs[1]['number'] is None
    assert refs[1]['text'] == 'text b'


def test_conclusion_refs_mirror():
    rows = [_row('Conclusion_2', conclusionNumber=2,
                 conclusionText='It was ethical.')]
    refs = conclusion_refs(4, rows)
    assert refs[0]['uri'] == 'case-4#Conclusion_2'
    assert refs[0]['text'] == 'It was ethical.'


def test_analysis_edges_accepts_both_key_forms():
    from app.services.extraction.analysis_edges import _DIRECT, _POS
    m = _DIRECT.search('case-9#Question_101')
    assert m and m.group(1) == 'Question' and m.group(2) == '101'
    m = _DIRECT.search('case-9#Conclusion_3')
    assert m and m.group(1) == 'Conclusion'
    assert _DIRECT.search('case-9#Q4') is None      # legacy form is positional
    m = _POS.search('case-9#Q4')
    assert m and m.group(1) == 'Q' and m.group(2) == '4'
    # QuestionEmergence_1 fallback entity_uris must match NEITHER form
    assert _DIRECT.search('case-9#QuestionEmergence_1') is None
    assert _POS.search('case-9#QuestionEmergence_1') is None
