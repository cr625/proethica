"""Review of the annotation-layer lessons (brief 2 of docs/reviews/lessons/cloud_briefs.md).

Defects found in the merge review, each with the scenario that broke:

1. The inventory ranking took the OntServe source field as an ontology name.
   OntServe writes 'concepts' on a concepts-table row and 'ontology' on an
   ontology row without a name (OntServe storage/concept_manager.py), so such
   a row received ontology_target 'concepts' and the OntServe path
   /entity/concepts/<fragment>, which no page serves. The row now takes the
   target of its URI namespace, as every row did on the base.

2. Two definitional ontologies describing the same URI tied in the ranking
   and the first inventory row won. A class declared by proethica-intermediate
   and by the extended store (classes copied there before the class commit
   refused base copies) took its ontology_target and definition from the row
   order of a SELECT DISTINCT. The ontology whose namespace owns the URI
   wins the tie.

3. The step 5 traversal page serialized its lookup without aliasActors, so
   the shared scanner ran there with the alias actor gate off while the case
   page ran with it on.

4. Twenty-two of the branch tests pass on the base commit because they
   exercise the Python mirror of the scanner, which only source-contract
   tests tie to the JavaScript. The last test runs the real helpers under
   node on the mirror's inputs and compares (skipped where node is absent).

Hermetic: no DB, no LLM, no network.
"""

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.unit import test_annotation_layer_scan as mirror

REPO = Path(__file__).resolve().parents[2]
POPOVERS_JS = REPO / 'app' / 'static' / 'js' / 'ontology-popovers.js'
CASE_TEMPLATE = REPO / 'app' / 'templates' / 'case_detail.html'
STEP5_TEMPLATE = REPO / 'app' / 'templates' / 'scenario_pipeline' / 'step5_traversal.html'

INVENTORY_METHODS = (
    'get_all_role_entities', 'get_all_state_entities', 'get_all_resource_entities',
    'get_all_principle_entities', 'get_all_obligation_entities', 'get_all_constraint_entities',
    'get_all_capability_entities', 'get_all_action_entities', 'get_all_event_entities',
)


def _fake_client(rows_by_method):
    client = MagicMock()
    for method in INVENTORY_METHODS:
        getattr(client, method).return_value = rows_by_method.get(method, [])
    return client


def _fetch(rows_by_method):
    from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

    UnifiedEntityResolver.clear_ontserve_cache()
    try:
        with patch('app.services.ontserve.external_mcp_client.get_external_mcp_client',
                   return_value=_fake_client(rows_by_method)):
            return UnifiedEntityResolver(case_id=None)._get_ontserve_entities()
    finally:
        UnifiedEntityResolver.clear_ontserve_cache()


# ---------------------------------------------------------------------------
# 1. The source field of an inventory row can name a table
# ---------------------------------------------------------------------------

class TestInventorySourceField:

    URI = 'http://proethica.org/ontology/intermediate#DutyOfCare'

    @pytest.mark.parametrize('source', ['concepts', 'ontology'])
    def test_table_name_in_the_source_field_is_not_an_ontology_target(self, source):
        entities = _fetch({'get_all_obligation_entities': [{
            'uri': self.URI, 'label': 'Duty of Care', 'description': 'Professional duty.', 'source': source,
        }]})
        entry = entities[self.URI]
        assert entry['ontology_target'] == 'proethica-intermediate'
        assert entry['ontserve_path'] == '/entity/proethica-intermediate/DutyOfCare'

    @pytest.mark.parametrize('reverse', [False, True])
    def test_concept_row_ranks_below_the_declaring_ontology(self, reverse):
        rows = [
            {'uri': self.URI, 'label': 'Duty of Care', 'description': 'Candidate text.', 'source': 'concepts'},
            {'uri': self.URI, 'label': 'Duty of Care', 'description': 'Curated text.',
             'source': 'proethica-intermediate'},
        ]
        if reverse:
            rows.reverse()
        entities = _fetch({'get_all_obligation_entities': rows})
        assert entities[self.URI]['definition'] == 'Curated text.'
        assert entities[self.URI]['ontology_target'] == 'proethica-intermediate'

    def test_source_helper(self):
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver as R

        assert R._ontserve_row_source({'source': 'concepts'}) == ''
        assert R._ontserve_row_source({'source': 'ontology'}) == ''
        assert R._ontserve_row_source({'source': 'proethica-core'}) == 'proethica-core'
        assert R._ontserve_row_source({'ontology_name': 'engineering-ethics'}) == 'engineering-ethics'
        assert R._ontserve_row_rank({'source': 'concepts', 'description': 'Candidate text.'}) == (False, True, False)


# ---------------------------------------------------------------------------
# 2. Two definitional ontologies describing one URI
# ---------------------------------------------------------------------------

class TestDefinitionalTie:

    URI = 'http://proethica.org/ontology/intermediate#SafetyObligation'

    @pytest.mark.parametrize('reverse', [False, True])
    def test_namespace_owner_wins_a_described_tie_in_either_order(self, reverse):
        rows = [
            {'uri': self.URI, 'label': 'Safety Obligation',
             'description': 'Copied into the extended store with case context.',
             'source': 'proethica-intermediate-extended'},
            {'uri': self.URI, 'label': 'Safety Obligation', 'description': 'Curated definition.',
             'source': 'proethica-intermediate'},
        ]
        if reverse:
            rows.reverse()
        entities = _fetch({'get_all_obligation_entities': rows})
        entry = entities[self.URI]
        assert entry['definition'] == 'Curated definition.'
        assert entry['ontology_target'] == 'proethica-intermediate'
        assert entry['ontserve_path'] == '/entity/proethica-intermediate/SafetyObligation'

    def test_class_declared_by_the_extended_store_alone_keeps_its_target(self):
        uri = 'http://proethica.org/ontology/intermediate#NovelCredentialAccuracyObligation'
        entities = _fetch({'get_all_obligation_entities': [{
            'uri': uri, 'label': 'Novel Credential Accuracy Obligation',
            'description': 'Minted by the pipeline.', 'source': 'proethica-intermediate-extended',
        }]})
        assert entities[uri]['ontology_target'] == 'proethica-intermediate-extended'

    def test_rank_carries_the_namespace_owner(self):
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver as R

        owner = {'uri': self.URI, 'source': 'proethica-intermediate', 'description': 'x'}
        copy = {'uri': self.URI, 'source': 'proethica-intermediate-extended', 'description': 'x'}
        assert R._ontserve_row_rank(owner) == (True, True, True)
        assert R._ontserve_row_rank(copy) == (True, True, False)
        assert R._ontserve_row_rank(owner) > R._ontserve_row_rank(copy)
        # a described row still outranks an undescribed owner
        assert R._ontserve_row_rank(copy) > R._ontserve_row_rank({**owner, 'description': ''})


# ---------------------------------------------------------------------------
# 3. Every page that feeds the scanner serializes the alias actors
# ---------------------------------------------------------------------------

class TestLookupSerialization:

    ACTORS_LINE = 'aliasActors: {{ (entity.alias_actors or [])|tojson }},'

    def test_both_scanner_pages_serialize_alias_actors(self):
        assert self.ACTORS_LINE in CASE_TEMPLATE.read_text()
        assert self.ACTORS_LINE in STEP5_TEMPLATE.read_text()

    def test_scanner_reads_the_actors_from_the_lookup_entry(self):
        source = POPOVERS_JS.read_text()
        assert 'var actors = entity.aliasActors || [];' in source
        assert 'var actors = best.entity.aliasActors || [];' in source


# ---------------------------------------------------------------------------
# 4. The Python mirror against the real helpers under node
# ---------------------------------------------------------------------------

HARNESS_JS = r"""
const fs = require('fs');
const vm = require('vm');
const [,, jsPath, inputPath] = process.argv;
const data = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
const sandbox = {
  window: {},
  document: { addEventListener() {}, querySelectorAll() { return []; }, dispatchEvent() {} },
  NodeFilter: { SHOW_TEXT: 4 },
  console,
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(jsPath, 'utf8'), sandbox, { filename: 'ontology-popovers.js' });
const W = sandbox.window;
const pattern = W.buildEntityPattern(data.keys);
const out = {
  pattern: data.texts.map(function (t) {
    const r = []; pattern.lastIndex = 0; let m;
    while ((m = pattern.exec(t)) !== null) r.push([m[1], m.index]);
    return r;
  }),
  windows: data.windows.map(function (w) { return W.sentenceWindow(w[0], w[1], w[2]); }),
  actors: data.actors.map(function (a) { return W.aliasActorPresent(a[0], a[1]); }),
  truncation: data.truncation.map(function (t) { return W.truncateDefinition(t, 300); }),
  facets: data.facets.map(function (f) { const r = W.splitAgentFacets(f); return [r.lead, r.facets]; }),
};
process.stdout.write(JSON.stringify(out));
"""

KEYS = [
    'iii.1.b.', 'iii.1.b', 'i.1', 'case 76-4', 'ber case 76-4', 'engineer l', 'faithful agent',
    'nspe code of ethics', 'dp1', 'analysis-record edge (addressesquestion)',
    "analytical conclusion 1: the board's finding that engineer l acted ethically in st...",
    'x (y)', 'a+b', 'c++', '$cost', 'end.',
]
CONTEXTS = ['{k}', 'see {k} here', 'see {k}, here', '({k})', 'see {k}; here', '{k}.', 'x{k}', '{k}x', '{k}5',
            'the {k}-based view', '"{k}"', 'Engineer Lé and {k}', 'A {k}, a {k}; a {k}.']
SENTENCES = [
    'Code section III.1.b requires Engineer L to advise the client.',
    'Section III.1.b. requires advice.',
    'Consistent with Code sections I.4, II.3.a, II.3.b, III.1.b, and III.3.a, Engineer L notified Client X.',
    'In BER Case 76-4, Engineer Doe acted as a faithful agent. See Case 76-45 and Case 76-4.',
    'The NSPE Code of Ethics and the Code of Ethics. DP1 and dp1 and DP12.',
]
BLOCKS = [
    'First sentence about Engineer L. Second one names a faithful agent. Third one.',
    'Engineer L, P.E. acted as a faithful agent. The client refused.',
    'In BER Case 76-4, Engineer Doe, retained by a client, acted as a faithful agent. Engineer L did not.',
    'Section III.1.b. requires Engineer L to act as a faithful agent.',
    'No terminator here faithful agent',
    'faithful agent. faithful agent.faithful agent! x? faithful agent',
    'Mr. Smith, Dr. Jones and Engineer L: a faithful agent?  Two spaces.   Three.',
    'Tab\tseparated. faithful agent\tagain.',
]
ACTOR_CASES = [
    ["ENGINEER L's duty as a faithful agent", ['Engineer L']],
    ['Engineer Lee acted as a faithful agent', ['Engineer L']],
    ['anything', []],
    ['xEngineer L', ['Engineer L']],
    ['Engineer L_', ['Engineer L']],
    ['Engineer L.', ['Engineer L']],
    ['the Board of Ethical Review said', ['Board of Ethical Review', 'Engineer L']],
    ['Client X (Inc.) said', ['Client X (Inc.)']],
    ['a.b matters', ['a.b']],
    ['axb matters', ['a.b']],
    ['', ['Engineer L']],
    ['Engineer L', ['', 'Engineer L']],
    ['Engineer L', ['Engineer L']],
    ['Engineer Lé', ['Engineer L']],
]
TRUNCATION_CASES = [
    '', 'short', 'a' * 300, 'a' * 301, 'a' * 299 + ' b', 'a' * 300 + ' b', 'a' * 150 + ' ' + 'b' * 200,
    'a' * 149 + ' ' + 'b' * 200, ('loyalty ' * 60).strip(), ' ' * 301, mirror.AGENT_DEFINITION,
]
FACET_CASES = [
    mirror.AGENT_DEFINITION,
    'The deliberative body whose analysis this case record captures.',
    'Lead: a; b', 'a;b', 'a; b; ', '; leading', '', 'No colon; but facets; here.',
    'Participant (Agent) in this case.', 'x: y: z; w', 'Trailing period..; next.',
]


@pytest.mark.skipif(shutil.which('node') is None, reason='node is not installed')
class TestMirrorAgainstNode:

    def test_real_helpers_match_the_mirror(self, tmp_path):
        texts = [c.format(k=k) for k in KEYS for c in CONTEXTS] + SENTENCES
        windows = []
        for block in BLOCKS:
            for key in ('faithful agent', 'Engineer L', 'Case 76-4', 'III.1.b.'):
                start = block.find(key)
                while start != -1:
                    windows.append([block, start, len(key)])
                    start = block.find(key, start + 1)

        pattern = mirror.scanner_pattern(KEYS)
        expected = {
            'pattern': [[[m.group(1), m.start()] for m in pattern.finditer(t)] for t in texts],
            'windows': [mirror.sentence_window(b, i, n) for b, i, n in windows],
            'actors': [mirror.alias_actor_present(s, a) for s, a in ACTOR_CASES],
            'truncation': [mirror.truncate_definition(t) for t in TRUNCATION_CASES],
            'facets': [list(mirror.split_agent_facets(f)) for f in FACET_CASES],
        }

        harness = tmp_path / 'harness.js'
        harness.write_text(HARNESS_JS)
        inputs = tmp_path / 'inputs.json'
        inputs.write_text(json.dumps({
            'keys': KEYS, 'texts': texts, 'windows': windows, 'actors': ACTOR_CASES,
            'truncation': TRUNCATION_CASES, 'facets': FACET_CASES,
        }))
        run = subprocess.run([shutil.which('node'), str(harness), str(POPOVERS_JS), str(inputs)],
                             capture_output=True, text=True, timeout=60)
        assert run.returncode == 0, run.stderr
        actual = json.loads(run.stdout)

        for section, values in expected.items():
            assert actual[section] == values, section
