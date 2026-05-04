"""Tests for app.services.annotation.text_annotator."""

import pytest
from app.services.annotation.text_annotator import TextAnnotator, AnnotatedSpan, SKIP_WORDS


# --- Fixtures: synthetic label indexes (no DB needed) ---

@pytest.fixture
def basic_label_index():
    """Minimal label index with a few entity types."""
    return {
        'engineer a': {
            'label': 'Engineer A',
            'definition': 'Licensed professional engineer retained by Client W.',
            'entity_type': 'Role',
            'extraction_type': 'roles',
            'source': 'case',
            'source_pass': 1,
            'uri': 'http://proethica.org/ontology/case/7#Engineer_A',
            'alias_types': [],
        },
        'engineer b': {
            'label': 'Engineer B',
            'definition': 'Mentor and supervisor who recently retired.',
            'entity_type': 'Role',
            'extraction_type': 'roles',
            'source': 'case',
            'source_pass': 1,
            'uri': 'http://proethica.org/ontology/case/7#Engineer_B',
            'alias_types': [],
        },
        'professional competence': {
            'label': 'Professional Competence',
            'definition': 'Obligation to maintain technical skill and knowledge.',
            'entity_type': 'Capability',
            'extraction_type': 'capabilities',
            'source': 'case',
            'source_pass': 2,
            'uri': 'http://proethica.org/ontology/case/7#Professional_Competence',
            'alias_types': [],
        },
        'public safety': {
            'label': 'Public Safety',
            'definition': 'The paramount obligation to protect the public.',
            'entity_type': 'Principle',
            'extraction_type': 'principles',
            'source': 'case',
            'source_pass': 2,
            'uri': 'http://proethica.org/ontology/case/7#Public_Safety',
            'alias_types': [],
        },
        'client w': {
            'label': 'Client W',
            'definition': 'The client who retained Engineer A.',
            'entity_type': 'Role',
            'extraction_type': 'roles',
            'source': 'case',
            'source_pass': 1,
            'uri': 'http://proethica.org/ontology/case/7#Client_W',
            'alias_types': [],
        },
    }


@pytest.fixture
def overlap_label_index():
    """Label index with overlapping labels for testing precedence."""
    return {
        'engineer': {
            'label': 'Engineer',
            'definition': 'Generic engineer role.',
            'entity_type': 'Role',
            'extraction_type': 'roles',
            'source': 'ontology',
            'source_pass': None,
            'uri': 'http://proethica.org/ontology#Engineer',
            'alias_types': [],
        },
        'engineer a': {
            'label': 'Engineer A',
            'definition': 'Specific engineer in the case.',
            'entity_type': 'Role',
            'extraction_type': 'roles',
            'source': 'case',
            'source_pass': 1,
            'uri': 'http://proethica.org/ontology/case/7#Engineer_A',
            'alias_types': [],
        },
        'engineer in responsible charge': {
            'label': 'Engineer in Responsible Charge',
            'definition': 'The licensed PE overseeing the project.',
            'entity_type': 'Role',
            'extraction_type': 'roles',
            'source': 'case',
            'source_pass': 1,
            'uri': 'http://proethica.org/ontology/case/7#EIRC',
            'alias_types': [],
        },
    }


@pytest.fixture
def annotator(basic_label_index):
    """TextAnnotator with synthetic label index (no DB)."""
    return TextAnnotator(case_id=0, label_index=basic_label_index)


@pytest.fixture
def overlap_annotator(overlap_label_index):
    """TextAnnotator with overlapping labels."""
    return TextAnnotator(case_id=0, label_index=overlap_label_index)


# --- Core matching tests ---

class TestAnnotate:
    def test_finds_single_entity(self, annotator):
        spans = annotator.annotate("Engineer A reviewed the report.")
        assert len(spans) == 1
        assert spans[0].matched_text == "Engineer A"
        assert spans[0].entity_type == "roles"

    def test_finds_multiple_entities(self, annotator):
        spans = annotator.annotate(
            "Engineer A discussed public safety with Engineer B."
        )
        labels = {s.matched_text for s in spans}
        assert "Engineer A" in labels
        assert "public safety" in labels or "Public Safety" in labels
        assert "Engineer B" in labels

    def test_case_insensitive_matching(self, annotator):
        spans = annotator.annotate("PUBLIC SAFETY is paramount.")
        assert len(spans) == 1
        assert spans[0].matched_text == "PUBLIC SAFETY"
        assert spans[0].entity_type == "principles"

    def test_preserves_original_case_in_matched_text(self, annotator):
        spans = annotator.annotate("ENGINEER A and engineer a both match.")
        # Both occurrences should match; text preserves original casing
        assert all(s.matched_text.lower() == "engineer a" for s in spans)

    def test_empty_text_returns_empty(self, annotator):
        assert annotator.annotate("") == []
        assert annotator.annotate(None) == []

    def test_no_matches_returns_empty(self, annotator):
        spans = annotator.annotate("The weather is nice today.")
        assert spans == []

    def test_word_boundary_prevents_partial_match(self, annotator):
        # "engineer a" should not match inside "reengineered"
        spans = annotator.annotate("The reengineered approach worked well.")
        assert len(spans) == 0

    def test_span_positions_are_correct(self, annotator):
        text = "Ask Engineer A about it."
        spans = annotator.annotate(text)
        assert len(spans) == 1
        s = spans[0]
        assert text[s.start:s.end] == "Engineer A"

    def test_entity_metadata_populated(self, annotator):
        spans = annotator.annotate("Engineer A was competent.")
        s = spans[0]
        assert s.entity_label == "Engineer A"
        assert s.entity_uri == "http://proethica.org/ontology/case/7#Engineer_A"
        assert s.definition.startswith("Licensed professional")
        assert s.source == "case"
        assert s.source_pass == 1


# --- Overlap resolution tests ---

class TestOverlapResolution:
    def test_longest_match_wins(self, overlap_annotator):
        text = "The engineer in responsible charge approved the design."
        spans = overlap_annotator.annotate(text)
        labels = [s.matched_text.lower() for s in spans]
        assert "engineer in responsible charge" in labels
        # "engineer" alone should NOT appear since it overlaps
        assert "engineer" not in labels

    def test_non_overlapping_matches_preserved(self, overlap_annotator):
        text = "Engineer A consulted the engineer in responsible charge."
        spans = overlap_annotator.annotate(text)
        labels = [s.matched_text.lower() for s in spans]
        assert "engineer a" in labels
        assert "engineer in responsible charge" in labels

    def test_adjacent_matches_both_kept(self, annotator):
        text = "Engineer A and Engineer B discussed it."
        spans = annotator.annotate(text)
        assert len(spans) == 2


# --- Skip words tests ---

class TestSkipWords:
    def test_generic_concept_words_skipped(self):
        # Even if "state" were in the label index, it should be skipped
        label_index = {
            'state': {
                'label': 'State',
                'definition': 'A condition.',
                'entity_type': 'State',
                'extraction_type': 'states',
                'source': 'case',
                'source_pass': 1,
                'uri': 'test#State',
                'alias_types': [],
            },
        }
        annotator = TextAnnotator(case_id=0, label_index=label_index)
        spans = annotator.annotate("The current state of affairs.")
        assert len(spans) == 0

    def test_short_labels_skipped(self):
        label_index = {
            'pe': {
                'label': 'PE',
                'definition': 'Professional Engineer.',
                'entity_type': 'Role',
                'extraction_type': 'roles',
                'source': 'case',
                'source_pass': 1,
                'uri': 'test#PE',
                'alias_types': [],
            },
        }
        annotator = TextAnnotator(case_id=0, label_index=label_index)
        spans = annotator.annotate("The PE reviewed the plans.")
        # "pe" is only 2 chars, below MIN_LABEL_LENGTH of 4
        assert len(spans) == 0


# --- HTML output tests ---

class TestAnnotateHtml:
    def test_produces_onto_label_spans(self, annotator):
        html = annotator.annotate_html("Engineer A reviewed the report.")
        html_str = str(html)
        assert 'class="onto-label"' in html_str
        assert 'data-entity-type="roles"' in html_str
        assert 'data-entity-definition=' in html_str
        assert '>Engineer A</span>' in html_str

    def test_escapes_surrounding_text(self, annotator):
        html = annotator.annotate_html("Use <script> with Engineer A.")
        html_str = str(html)
        assert '<script>' not in html_str
        assert '&lt;script&gt;' in html_str

    def test_no_matches_returns_escaped_text(self, annotator):
        html = annotator.annotate_html("Plain text with no entities.")
        assert str(html) == "Plain text with no entities."

    def test_ontology_source_gets_css_class(self):
        label_index = {
            'duty of care': {
                'label': 'Duty of Care',
                'definition': 'Base ontology concept.',
                'entity_type': 'Principle',
                'extraction_type': 'principles',
                'source': 'ontology',
                'source_pass': None,
                'uri': 'http://proethica.org/ontology#DutyOfCare',
                'alias_types': [],
            },
        }
        annotator = TextAnnotator(case_id=0, label_index=label_index)
        html = annotator.annotate_html("The duty of care applies here.")
        assert 'onto-source-ontology' in str(html)

    def test_definition_truncated_at_200_chars(self):
        long_def = "A" * 300
        label_index = {
            'test entity': {
                'label': 'Test Entity',
                'definition': long_def,
                'entity_type': 'Role',
                'extraction_type': 'roles',
                'source': 'case',
                'source_pass': 1,
                'uri': 'test#TestEntity',
                'alias_types': [],
            },
        }
        annotator = TextAnnotator(case_id=0, label_index=label_index)
        html = str(annotator.annotate_html("The test entity was found."))
        # Definition in data attribute should be truncated
        assert "A" * 200 + "..." in html
        assert "A" * 201 not in html


# --- AnnotatedSpan tests ---

class TestAnnotatedSpan:
    def test_to_dict(self):
        span = AnnotatedSpan(
            start=0, end=10, matched_text="Engineer A",
            entity_label="Engineer A", entity_type="roles",
            entity_uri="test#EA", definition="A role.",
            source="case", source_pass=1, alias_types=[]
        )
        d = span.to_dict()
        assert d['start'] == 0
        assert d['end'] == 10
        assert d['entity_type'] == 'roles'
        assert d['source_pass'] == 1


# --- Entity count ---

class TestEntityCount:
    def test_entity_count(self, annotator):
        # basic_label_index has 5 entries, all >= 4 chars, none in skip list
        assert annotator.get_entity_count() == 5

    def test_entity_count_excludes_short_and_skipped(self):
        label_index = {
            'pe': {'label': 'PE', 'definition': 'x', 'entity_type': 'Role',
                    'extraction_type': 'roles', 'source': 'case',
                    'source_pass': 1, 'uri': 'x', 'alias_types': []},
            'state': {'label': 'State', 'definition': 'x', 'entity_type': 'State',
                      'extraction_type': 'states', 'source': 'case',
                      'source_pass': 1, 'uri': 'x', 'alias_types': []},
            'valid term': {'label': 'Valid Term', 'definition': 'x', 'entity_type': 'Role',
                           'extraction_type': 'roles', 'source': 'case',
                           'source_pass': 1, 'uri': 'x', 'alias_types': []},
        }
        annotator = TextAnnotator(case_id=0, label_index=label_index)
        assert annotator.get_entity_count() == 1  # only "valid term"


# --- Live integration test: requires populated dev DB plus OntServe MCP. ---
# Deselected by default (see pytest.ini live_db marker); run with `pytest -m live_db`.

@pytest.mark.live_db
class TestLiveAnnotation:
    @pytest.fixture(autouse=True)
    def _dev_app_context(self):
        from app import create_app
        app = create_app("development")
        with app.app_context():
            yield

    def test_annotate_case7_text(self):
        annotator = TextAnnotator(case_id=7)
        spans = annotator.annotate(
            "Engineer A had an obligation to ensure public safety "
            "through professional competence."
        )
        assert len(spans) >= 2
        labels = {s.matched_text.lower() for s in spans}
        assert 'engineer a' in labels
