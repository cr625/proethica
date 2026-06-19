"""HO-005: obligation compliance_status / capability proficiency_level wiring.

Step 2 extracts and persists obligation ``compliance_status`` and capability
``proficiency_level`` (as ``complianceStatus`` / ``proficiencyLevel`` under
``rdf_json_ld['properties']``), but Phase-3 decision-point synthesis previously
dropped them. ``DecisionPointSynthesizer`` now builds a compact normative-status
block from those individuals and appends it to each synthesis prompt.

These tests are hermetic: ``TemporaryRDFStorage`` is monkeypatched so the parsing
and append logic are exercised without DB state or an LLM call.
"""

# Patch the submodule where TemporaryRDFStorage is actually resolved: after the
# package split, the class's code lives in `.synthesizer`, so monkeypatching the
# package `__init__` would not intercept the name.
import app.services.decision_point_synthesizer.synthesizer as dps
from app.services.decision_point_synthesizer import DecisionPointSynthesizer


class _FakeIndiv:
    def __init__(self, label, props):
        self.entity_label = label
        self.rdf_json_ld = {'properties': props}


class _FakeQuery:
    """Stand-in for TemporaryRDFStorage.query; returns rows by extraction_type."""
    def __init__(self, rows_by_type):
        self._rows = rows_by_type
        self._kw = {}

    def filter_by(self, **kw):
        self._kw = kw
        return self

    def all(self):
        return self._rows.get(self._kw.get('extraction_type'), [])


def _patch_storage(monkeypatch, rows_by_type):
    class _FakeStorage:
        query = _FakeQuery(rows_by_type)
    monkeypatch.setattr(dps, 'TemporaryRDFStorage', _FakeStorage)


def test_append_passthrough_when_no_context():
    s = DecisionPointSynthesizer()
    assert s._append_normative_status('PROMPT') == 'PROMPT'
    s._normative_status_context = ''
    assert s._append_normative_status('PROMPT') == 'PROMPT'


def test_append_adds_block_when_present():
    s = DecisionPointSynthesizer()
    s._normative_status_context = 'NORMATIVE STATUS (x)'
    out = s._append_normative_status('PROMPT BODY')
    assert out.startswith('PROMPT BODY')
    assert out.endswith('NORMATIVE STATUS (x)')
    assert 'PROMPT BODY\n\nNORMATIVE STATUS' in out


def test_build_context_surfaces_both_fields(monkeypatch):
    _patch_storage(monkeypatch, {
        'obligations': [
            _FakeIndiv('Safety Disclosure Obligation', {'complianceStatus': ['met']}),
            _FakeIndiv('Confidentiality Obligation', {'complianceStatus': ['unmet']}),
        ],
        'capabilities': [
            _FakeIndiv('Structural Analysis Competence', {'proficiencyLevel': ['advanced']}),
        ],
    })
    ctx = DecisionPointSynthesizer()._build_normative_status_context(case_id=1)
    assert 'NORMATIVE STATUS' in ctx
    assert 'Obligation compliance:' in ctx
    assert '- Safety Disclosure Obligation: compliance=met' in ctx
    assert '- Confidentiality Obligation: compliance=unmet' in ctx
    assert 'Capability proficiency:' in ctx
    assert '- Structural Analysis Competence: proficiency=advanced' in ctx


def test_build_context_skips_rows_without_field(monkeypatch):
    _patch_storage(monkeypatch, {
        'obligations': [
            _FakeIndiv('Has Status', {'complianceStatus': ['partial']}),
            _FakeIndiv('No Status', {'importance': ['high']}),
        ],
        'capabilities': [],
    })
    ctx = DecisionPointSynthesizer()._build_normative_status_context(case_id=1)
    assert 'Has Status: compliance=partial' in ctx
    assert 'No Status' not in ctx
    assert 'Capability proficiency:' not in ctx  # no capability rows with a level


def test_build_context_empty_when_no_fields(monkeypatch):
    _patch_storage(monkeypatch, {
        'obligations': [_FakeIndiv('Bare', {'importance': ['high']})],
        'capabilities': [_FakeIndiv('Bare Cap', {})],
    })
    assert DecisionPointSynthesizer()._build_normative_status_context(case_id=1) == ''


def test_build_context_pairs_proficiency_with_evidence(monkeypatch):
    """HO-005 follow-on: the capability demonstrated_through literal (already
    stored, previously consumer-less) is paired with the proficiency rating so the
    rating is defensible -- 'proficiency=X (evidenced by: ...)'."""
    _patch_storage(monkeypatch, {
        'obligations': [],
        'capabilities': [
            _FakeIndiv('Engineer L Stormwater Domain Expertise', {
                'proficiencyLevel': ['expert'],
                'demonstratedThrough': ['Applying stormwater design expertise to identify risk concerns.'],
            }),
        ],
    })
    ctx = DecisionPointSynthesizer()._build_normative_status_context(case_id=1)
    assert ('- Engineer L Stormwater Domain Expertise: proficiency=expert '
            '(evidenced by: Applying stormwater design expertise to identify risk concerns.)') in ctx


def test_build_context_surfaces_evidenced_but_unrated_capability(monkeypatch):
    """The broadened (level or evidence) guard surfaces a capability that has
    textual evidence but no proficiency rating -- the evidence is the useful part;
    proficiency is omitted (no fallback) rather than fabricated."""
    _patch_storage(monkeypatch, {
        'obligations': [],
        'capabilities': [
            _FakeIndiv('Unrated Competence', {'demonstratedThrough': ['Did the thing competently.']}),
        ],
    })
    ctx = DecisionPointSynthesizer()._build_normative_status_context(case_id=1)
    assert 'Capability proficiency:' in ctx
    assert '- Unrated Competence: (evidenced by: Did the thing competently.)' in ctx
    assert 'proficiency=' not in ctx  # no rating present, none invented


def test_build_context_dedupes_by_label(monkeypatch):
    _patch_storage(monkeypatch, {
        'obligations': [
            _FakeIndiv('Dup Obligation', {'complianceStatus': ['met']}),
            _FakeIndiv('Dup Obligation', {'complianceStatus': ['unclear']}),
        ],
        'capabilities': [],
    })
    ctx = DecisionPointSynthesizer()._build_normative_status_context(case_id=1)
    assert ctx.count('- Dup Obligation:') == 1  # last value wins, single line
