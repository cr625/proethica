"""
Case page annotation layer: label index to text scanner contract.

The scanner lives in app/static/js/ontology-popovers.js (scanTextForEntities
and its helpers). These tests mirror its semantics in Python -- the key
filter, the match pattern, the alias actor gate, the citation anchor rule and
the popover definition rendering -- and run them over a label index built by
UnifiedEntityResolver from a committed-graph fixture shaped after case 8
(NSPE 24-1). The source contract tests pin the JavaScript constructs the
mirror depends on.
"""

import re
from pathlib import Path
from unittest.mock import patch

import pytest
import rdflib

REPO = Path(__file__).resolve().parents[2]
POPOVERS_JS = REPO / 'app' / 'static' / 'js' / 'ontology-popovers.js'
CASE_PAGE_JS = REPO / 'app' / 'static' / 'js' / 'cases' / 'case_detail_page.js'
CASE_TEMPLATE = REPO / 'app' / 'templates' / 'case_detail.html'


# ---------------------------------------------------------------------------
# Python mirror of the scanner (ontology-popovers.js)
# ---------------------------------------------------------------------------

CASE_MIN_LABEL_LENGTH = 3
DEFAULT_MIN_LABEL_LENGTH = 4
DEFAULT_SKIP_WORDS = {
    'state', 'action', 'event', 'role', 'resource', 'principle',
    'obligation', 'constraint', 'capability',
    'nspe code of ethics', 'code of ethics',
}
DEFINITION_LIMIT = 300

# l.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
_JS_SPECIALS = re.compile(r'[.*+?^${}()|\[\]\\]')


def js_escape(label):
    return _JS_SPECIALS.sub(lambda m: '\\' + m.group(0), label)


def scanner_keys(lookup, min_len=DEFAULT_MIN_LABEL_LENGTH, skip_words=DEFAULT_SKIP_WORDS):
    """Keys that enter the pattern: case-declared keys bypass skipWords and
    minLabelLength down to CASE_MIN_LABEL_LENGTH."""
    keys = []
    for key, entry in lookup.items():
        if entry.get('source') == 'case':
            if len(key) >= CASE_MIN_LABEL_LENGTH:
                keys.append(key)
        elif len(key) >= min_len and key.lower() not in skip_words:
            keys.append(key)
    return keys


def scanner_pattern(keys):
    """buildEntityPattern: longest first, leading \\b, trailing non-word lookahead.
    re.ASCII keeps \\b on the JavaScript word class [A-Za-z0-9_]."""
    ordered = sorted(keys, key=len, reverse=True)
    return re.compile(r'\b(' + '|'.join(js_escape(k) for k in ordered) + r')(?![A-Za-z0-9_])',
                      re.IGNORECASE | re.ASCII)


def scan_matches(text, lookup, keys=None):
    """Matched (text, key) pairs, without the alias actor gate."""
    pattern = scanner_pattern(keys if keys is not None else scanner_keys(lookup))
    return [(m.group(1), m.group(1).lower()) for m in pattern.finditer(text)
            if m.group(1).lower() in lookup]


def sentence_window(text, index, length):
    """sentenceWindow(text, index, length)."""
    start = 0
    for m in re.finditer(r'[.!?]\s', text):
        if m.end() > index:
            break
        start = m.end()
    end = len(text)
    after = re.compile(r'[.!?](?=\s|$)').search(text, index + length)
    if after:
        end = after.start() + 1
    return text[start:end]


def alias_actor_present(sentence, actors):
    """aliasActorPresent(sentence, actors)."""
    if not actors:
        return True
    return any(re.search(r'(?<![A-Za-z0-9_])' + re.escape(a) + r'(?![A-Za-z0-9_])', sentence,
                         re.IGNORECASE | re.ASCII) for a in actors if a)


def decorated_spans(text, lookup):
    """Spans the scanner decorates in a block of text, alias actor gate included."""
    pattern = scanner_pattern(scanner_keys(lookup))
    spans = []
    for m in pattern.finditer(text):
        entry = lookup.get(m.group(1).lower())
        if entry is None:
            continue
        actors = entry.get('alias_actors') or []
        if actors and not alias_actor_present(sentence_window(text, m.start(), len(m.group(1))), actors):
            continue
        spans.append(m.group(1))
    return spans


def anchor_entity(anchor_text, lookup):
    """decorateCitationAnchors: the longest key in the anchor text, accepted
    when it accounts for at least half of the text."""
    text = re.sub(r'\s+', ' ', anchor_text).strip()
    pattern = scanner_pattern(scanner_keys(lookup))
    best = None
    for m in pattern.finditer(text):
        if m.group(1).lower() in lookup and (best is None or len(m.group(1)) > len(best)):
            best = m.group(1)
    if best is None or len(best) * 2 < len(text):
        return None
    return lookup[best.lower()]


def truncate_definition(text, limit=DEFINITION_LIMIT):
    """truncateDefinition(text, limit)."""
    if len(text) <= limit:
        return text
    cut = text.rfind(' ', 0, limit + 1)
    if cut < limit / 2:
        cut = limit
    return text[:cut] + '...'


def split_agent_facets(definition):
    """splitAgentFacets(definition)."""
    facets = [f for f in re.split(r';\s+', definition) if f.strip()]
    lead = ''
    if facets:
        colon = facets[0].find(': ')
        if colon != -1:
            lead = facets[0][:colon]
            facets[0] = facets[0][colon + 2:]
    return lead, [re.sub(r'\.$', '', f.strip()) for f in facets]


# ---------------------------------------------------------------------------
# Committed-graph fixture shaped after case 8
# ---------------------------------------------------------------------------

AGENT_DEFINITION = (
    "Participant in this case: performs Contract Acceptance, Nondisclosure at Suspension and "
    "Refusal to Acquiesce and 3 more; bears Engineer L Faithful Agent Duty, Engineer L Risk "
    "Disclosure Duty and Engineer L Unsuccessful Project Advisory Duty and 1 more; possesses "
    "Engineer L Protective Measures Advisory, Engineer L Risk Assessment and Engineer L Risk "
    "Disclosure and 3 more; is constrained by Engineer L Acquiescence Prohibition and Engineer L "
    "Faithful Agent Limit; is affected by Client X Budget Constraint, Public Safety Faithful Agent "
    "Conflict and Stormwater Contract Work Suspension and 1 more; has access to NSPE Code of "
    "Ethics; is the responsible agent in Contract Acceptance."
)

CANON_QUOTE = (
    "the present case illustrates a conflict between Fundamental Canon I.1, the engineer's "
    "obligation to hold paramount the safety, health and welfare of the public; and Canon I.4, "
    "the engineer's obligation to act for each employer or client as a faithful agent or trustee"
)

PROVISIONS = ['I.1.', 'I.4.', 'II.1.a.', 'II.3.a.', 'II.3.b.', 'III.1.b.', 'III.3.a.']

CASE8_TTL = '''
@prefix case8: <http://proethica.org/ontology/case/8#> .
@prefix proeth: <http://proethica.org/ontology/intermediate#> .
@prefix proeth-core: <http://proethica.org/ontology/core#> .
@prefix proeth-cases: <http://proethica.org/ontology/cases#> .
@prefix proeth-prov: <http://proethica.org/provenance#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .

case8:Agent_Engineer_L a proeth-core:Agent, owl:NamedIndividual ;
    rdfs:label "Engineer L" ;
    skos:definition """%(agent_definition)s""" .

case8:Agent_Client_X a proeth-core:Agent, owl:NamedIndividual ;
    rdfs:label "Client X" ;
    skos:definition "Participant in this case: performs Safeguard Refusal and Work Suspension Request; bears Client X Environmental Compliance Duty." .

case8:Engineer_L_Faithful_Agent a proeth-core:Role, owl:NamedIndividual ;
    rdfs:label "Engineer L Faithful Agent" ;
    skos:definition "Engineer L as the faithful agent or trustee of Client X under Canon I.4." ;
    proeth:textReferences "When asked in good faith to stop the design work, in the absence of facts to the contrary, there is no reason for Engineer L not to respect the client's request.",
        "under Fundamental Canon I.4, Engineer L has an affirmative obligation to act as the client's faithful agent or trustee" ;
    proeth-prov:discoveredInStep 1 .

case8:Engineer_L_Design_Engineer a proeth-core:Role, owl:NamedIndividual ;
    rdfs:label "Engineer L Design Engineer" ;
    skos:definition "Engineer L, retained by Client X to design the stormwater system." ;
    proeth:textReferences "Engineer L is retained by Client X to design a stormwater management system for a development." ;
    proeth-prov:discoveredInStep 1 .

case8:Engineer_L_Faithful_Agent_Duty a proeth-core:Obligation, owl:NamedIndividual ;
    rdfs:label "Engineer L Faithful Agent Duty" ;
    skos:definition "Engineer L must act for Client X as a faithful agent or trustee." ;
    proeth:textReferences "Beyond the fact limitation, under Fundamental Canon I.4, Engineer L has an affirmative obligation to act as the client's faithful agent or trustee." ;
    proeth-prov:discoveredInStep 2 .

case8:Public_Safety_Faithful_Agent_Conflict a proeth-core:State, owl:NamedIndividual ;
    rdfs:label "Public Safety Faithful Agent Conflict" ;
    skos:definition "The tension between Canon I.1 and Canon I.4 once the runoff risk is established as fact." ;
    proeth:textReferences """%(canon_quote)s""" ;
    proeth-prov:discoveredInStep 1 .

case8:NSPE_Code_of_Ethics a proeth-core:Resource, owl:NamedIndividual ;
    rdfs:label "NSPE Code of Ethics" ;
    skos:definition "The professional code the Board applies to the facts of the case." ;
    proeth-prov:discoveredInStep 1 .

case8:BER_Case_76-4 a proeth-cases:PrecedentCaseReference, proeth-core:Resource, proeth:CasePrecedent, owl:NamedIndividual ;
    rdfs:label "BER Case 76-4" ;
    skos:definition "Cited as foundational precedent establishing that an engineer's duty to public welfare is paramount." ;
    proeth-prov:discoveredInStep 1 .

case8:BER_Case_84-5 a proeth-cases:PrecedentCaseReference, proeth-core:Resource, proeth:CasePrecedent, owl:NamedIndividual ;
    rdfs:label "BER Case 84-5" ;
    skos:definition "Cited for the duty to report when a client refuses to act on a confirmed public risk." ;
    proeth-prov:discoveredInStep 1 .

case8:DP1 a proeth-cases:DecisionPoint, owl:NamedIndividual ;
    rdfs:label "DP1" ;
    skos:definition "Whether to respect the request to suspend the design work." .

case8:Analytical_conclusion_1 a proeth-cases:AnalyticalConclusion, owl:NamedIndividual ;
    rdfs:label "Analytical conclusion 1: The Board's finding that Engineer L acted ethically in st..." ;
    skos:definition "The Board's finding that Engineer L acted ethically in stopping the work rests on the fact limitation." .

case8:Edge_1 a proeth-cases:AnalysisRecordEdge, owl:NamedIndividual ;
    rdfs:label "Analysis-record edge (addressesQuestion)" ;
    skos:definition "Conclusion 1 addresses Question 1." .

%(provisions)s
''' % {
    'agent_definition': AGENT_DEFINITION,
    'canon_quote': CANON_QUOTE,
    'provisions': '\n'.join(
        '<http://proethica.org/ontology/case/8#%s> a proeth-cases:CodeProvisionReference, owl:NamedIndividual ;\n'
        '    rdfs:label "%s" ;\n'
        '    skos:definition "Provision %s of the NSPE Code of Ethics as applied by the Board." .\n'
        % (label, label, label) for label in PROVISIONS),
}


@pytest.fixture(scope='module')
def case8_graph():
    g = rdflib.Graph()
    g.parse(data=CASE8_TTL, format='turtle')
    return g


@pytest.fixture(scope='module')
def label_index(case8_graph):
    """Label index of the fixture as the case page receives it (no OntServe)."""
    from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

    with patch('app.services.entity.committed_case_graph.load_case_graph', return_value=case8_graph), \
            patch.object(UnifiedEntityResolver, '_get_ontserve_entities', return_value={}):
        resolver = UnifiedEntityResolver(case_id=8, case_source='committed')
        resolver.get_lookup_dict()
        return dict(resolver.get_label_index())


def with_ontology_entries(index):
    """The fixture index plus generic ontology entries, as the live page sees them."""
    merged = dict(index)
    for label in ('Code of Ethics', 'State', 'Law', 'Case Precedent'):
        merged.setdefault(label.lower(), {
            'label': label, 'definition': 'Ontology definition of ' + label,
            'source': 'ontology', 'entity_type': 'resources', 'extraction_type': 'resources',
            'uri': 'http://proethica.org/ontology/intermediate#' + label.replace(' ', ''),
        })
    return merged


# ---------------------------------------------------------------------------
# L2: provision labels with a trailing period
# ---------------------------------------------------------------------------

class TestProvisionLabels:

    def test_provision_keys_are_indexed_with_and_without_the_period(self, label_index):
        for label in PROVISIONS:
            assert label.lower() in label_index
            assert label.lower().rstrip('.') in label_index
            assert label_index[label.lower().rstrip('.')]['label'] == label

    @pytest.mark.parametrize('sentence, expected', [
        ('Code section III.1.b requires Engineer L to advise the client.', ['III.1.b']),
        ('Canon I.1, the paramountcy of public safety, governs.', ['I.1']),
        ('Consistent with Code sections I.4, II.3.a, II.3.b, III.1.b, and III.3.a, Engineer L notified Client X of this risk.',
         ['I.4', 'II.3.a', 'II.3.b', 'III.1.b', 'III.3.a']),
    ])
    def test_provision_citations_match_in_case_text(self, label_index, sentence, expected):
        matched = [text for text, key in scan_matches(sentence, label_index)
                   if label_index[key]['label'] in PROVISIONS]
        assert matched == expected

    def test_original_label_with_period_matches_before_a_space(self, label_index):
        matched = scan_matches('Section III.1.b. requires advice.', label_index)
        assert ('III.1.b.', 'iii.1.b.') in matched

    def test_trailing_word_boundary_would_have_failed(self, label_index):
        """The former pattern ended in \\b, which a key ending in a period cannot
        satisfy before a space."""
        old = re.compile(r'\b(' + js_escape('iii.1.b.') + r')\b', re.IGNORECASE | re.ASCII)
        assert old.search('Section III.1.b. requires advice.') is None
        assert scanner_pattern(['iii.1.b.']).search('Section III.1.b. requires advice.')


# ---------------------------------------------------------------------------
# L3: skipWords and the length floor apply to ontology entries only
# ---------------------------------------------------------------------------

class TestCaseEntriesBypassGenericFilters:

    def test_case_resource_named_like_a_skip_word_stays(self, label_index):
        keys = scanner_keys(with_ontology_entries(label_index))
        assert 'nspe code of ethics' in keys
        assert 'code of ethics' not in keys
        assert 'state' not in keys

    def test_short_case_keys_stay_short_ontology_keys_go(self, label_index):
        keys = scanner_keys(with_ontology_entries(label_index))
        assert 'i.1' in keys and 'dp1' in keys
        assert 'law' not in keys

    def test_the_case_code_of_ethics_is_decorated(self, label_index):
        text = 'Engineer L consulted the NSPE Code of Ethics before responding.'
        spans = decorated_spans(text, with_ontology_entries(label_index))
        assert 'NSPE Code of Ethics' in spans
        assert 'Code of Ethics' not in spans


# ---------------------------------------------------------------------------
# L4: cited cases inside external anchors
# ---------------------------------------------------------------------------

class TestCitationAnchors:

    def test_cited_case_is_indexed_as_cited_in_text(self, label_index):
        assert label_index['case 76-4']['label'] == 'BER Case 76-4'
        assert label_index['ber case 76-4'] is label_index['case 76-4']

    @pytest.mark.parametrize('anchor_text', ['BER Case 76-4', 'Case 76-4', ' BER  Case 76-4 ', 'BER Case 76-4 (1976)'])
    def test_anchor_text_naming_a_cited_case_is_decorated(self, label_index, anchor_text):
        entity = anchor_entity(anchor_text, label_index)
        assert entity is not None and entity['label'] == 'BER Case 76-4'

    def test_anchor_text_mostly_about_something_else_is_left_alone(self, label_index):
        assert anchor_entity('the Board of Ethical Review opinions collected since Case 76-4 and later', label_index) is None
        assert anchor_entity('Read the full opinion', label_index) is None

    def test_case_page_requests_anchor_decoration(self):
        source = CASE_PAGE_JS.read_text()
        assert 'decorateAnchors: true' in source


# ---------------------------------------------------------------------------
# L5: text-grounded aliases bound to their actor
# ---------------------------------------------------------------------------

class TestAliasActors:

    def test_faithful_agent_alias_names_engineer_l_only(self, label_index):
        alias = label_index['faithful agent']
        assert alias['alias_actors'] == ['Engineer L']
        contributors = {e['label'] for e in alias['alias_entities']}
        assert contributors == {'Engineer L Faithful Agent', 'Engineer L Faithful Agent Duty'}
        # grounded only by the generic Canon I.4 quotation
        assert 'Public Safety Faithful Agent Conflict' not in contributors

    def test_alias_is_decorated_only_where_the_actor_is_named(self, label_index):
        recap = ('In BER Case 76-4, Engineer Doe, retained by a client, acted as a faithful agent '
                 'when he declined to disclose the findings.')
        canon = ('Canon I.4 requires engineers to act for each employer or client as faithful agents '
                 'or trustees.')
        own = ('Under Fundamental Canon I.4, Engineer L has an affirmative obligation to act as the '
               "client's faithful agent or trustee.")
        assert 'faithful agent' not in [s.lower() for s in decorated_spans(recap, label_index)]
        assert 'faithful agent' not in [s.lower() for s in decorated_spans(canon, label_index)]
        assert 'faithful agent' in [s.lower() for s in decorated_spans(own, label_index)]

    def test_sentence_window_is_bounded_by_terminators(self):
        text = 'First sentence about Engineer L. Second one names a faithful agent. Third one.'
        at = text.index('faithful agent')
        assert sentence_window(text, at, len('faithful agent')) == 'Second one names a faithful agent.'
        assert not alias_actor_present(sentence_window(text, at, len('faithful agent')), ['Engineer L'])

    def test_actor_check_is_whole_word_and_case_insensitive(self):
        assert alias_actor_present("ENGINEER L's duty as a faithful agent", ['Engineer L'])
        assert not alias_actor_present('Engineer Lee acted as a faithful agent', ['Engineer L'])
        assert alias_actor_present('anything', [])

    def test_full_labels_carry_no_actor_gate(self, label_index):
        assert label_index['engineer l faithful agent duty'].get('alias_actors') is None
        text = 'The Engineer L Faithful Agent Duty is discussed in the recap about Engineer Doe.'
        assert decorated_spans(text, label_index) == ['Engineer L Faithful Agent Duty']


# ---------------------------------------------------------------------------
# L6: popover definition rendering
# ---------------------------------------------------------------------------

class TestDefinitionRendering:

    def test_agent_definition_splits_into_lead_and_facets(self):
        lead, facets = split_agent_facets(AGENT_DEFINITION)
        assert lead == 'Participant in this case'
        assert len(facets) == 7
        assert facets[0].startswith('performs Contract Acceptance')
        assert facets[1].startswith('bears Engineer L Faithful Agent Duty')
        assert facets[-1] == 'is the responsible agent in Contract Acceptance'
        assert len(AGENT_DEFINITION) > DEFINITION_LIMIT

    def test_prose_definition_is_not_split(self):
        lead, facets = split_agent_facets('The deliberative body whose analysis this case record captures.')
        assert lead == '' and len(facets) == 1

    def test_truncation_lands_on_a_word_boundary(self):
        words = ('loyalty ' * 60).strip()
        cut = truncate_definition(words)
        assert cut.endswith('...') and not cut[:-3].endswith(' ')
        assert cut[:-3] == words[:len(cut) - 3]
        assert words.startswith(cut[:-3] + ' ')
        assert truncate_definition('short') == 'short'

    def test_scanner_sets_the_pass_attribute_from_the_lookup(self):
        source = POPOVERS_JS.read_text()
        assert "span.setAttribute('data-entity-pass', entity.sourcePass ? String(entity.sourcePass) : '')" in source
        assert 'sourcePass: {{ entity.source_pass or \'null\' }}' in CASE_TEMPLATE.read_text()
        assert 'aliasActors: {{ (entity.alias_actors or [])|tojson }}' in CASE_TEMPLATE.read_text()


# ---------------------------------------------------------------------------
# L8: every emitted key matches under the scanner's boundary rule
# ---------------------------------------------------------------------------

class TestEveryKeyMatches:

    CONTEXTS = ['{key}', 'see {key} here', 'see {key}, here', '({key})', 'see {key}; here']

    def test_every_index_key_matches_in_running_text(self, label_index):
        lookup = with_ontology_entries(label_index)
        keys = scanner_keys(lookup)
        pattern = scanner_pattern(keys)
        failures = []
        for key in keys:
            for context in self.CONTEXTS:
                text = context.format(key=key)
                hit = next((m for m in pattern.finditer(text) if m.group(1).lower() == key), None)
                if hit is None:
                    failures.append((key, context))
        assert not failures, failures

    def test_fixture_covers_the_boundary_cases(self, label_index):
        keys = set(scanner_keys(label_index))
        assert any(k.endswith('.') for k in keys)
        assert any(k.endswith(')') for k in keys)
        assert any(k.endswith('...') for k in keys)
        assert any('-' in k for k in keys)


# ---------------------------------------------------------------------------
# Source contract: the constructs the mirror depends on
# ---------------------------------------------------------------------------

class TestScannerSourceContract:

    def test_pattern_uses_the_non_word_lookahead(self):
        source = POPOVERS_JS.read_text()
        assert "')(?![A-Za-z0-9_])'" in source
        assert "l.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')" in source
        assert "')\\\\b'" not in source

    def test_case_entries_bypass_the_generic_filters(self):
        source = POPOVERS_JS.read_text()
        assert 'var CASE_MIN_LABEL_LENGTH = %d;' % CASE_MIN_LABEL_LENGTH in source
        assert "if (entry.source === 'case') return l.length >= CASE_MIN_LABEL_LENGTH;" in source

    def test_alias_gate_and_anchor_pass_exist(self):
        source = POPOVERS_JS.read_text()
        assert 'function sentenceWindow(text, index, length)' in source
        assert 'function aliasActorPresent(sentence, actors)' in source
        assert 'function decorateCitationAnchors(cardBody, pattern, entityLookup, excludeSelector)' in source
        assert 'if (ontserveUrl && !el.dataset.entityAnchor)' in source

    def test_definition_limit_matches(self):
        source = POPOVERS_JS.read_text()
        assert 'var DEFINITION_LIMIT = %d;' % DEFINITION_LIMIT in source
        assert "displayDef.substring(0, 300)" not in source
