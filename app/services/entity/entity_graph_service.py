"""
Entity Graph and Q&C Extraction Service

Extracted from app/routes/scenario_pipeline/step4/qc_extraction.py (Phase 4b).
Provides:
- Entity graph construction for D3.js visualization
- Q-C flow data for Sankey visualization
- Question & conclusion extraction with entity tagging
- Cross-section synthesis coordination
"""

import logging
import re
import uuid
from datetime import datetime
from typing import Dict, List, Tuple

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.services.step4_synthesis.qc_entity_storage import make_question_storage, make_conclusion_storage
from app.utils.llm_utils import get_llm_client

from app.services.step4_synthesis.question_analyzer import QuestionAnalyzer
from app.services.step4_synthesis.conclusion_analyzer import ConclusionAnalyzer
from app.services.step4_synthesis.question_conclusion_linker import QuestionConclusionLinker

logger = logging.getLogger(__name__)


# Entity type to pass mapping (shared by graph and flow builders)
TYPE_TO_PASS = {
    'roles': 1, 'states': 1, 'resources': 1,
    'principles': 2, 'obligations': 2, 'constraints': 2, 'capabilities': 2,
    'temporal_dynamics_enhanced': 3, 'actions': 3, 'events': 3,
    'code_provision_reference': 4, 'ethical_question': 4, 'ethical_conclusion': 4
}

# Entity type colors - matches docs/reference/color-scheme.md.
# The nine concept colours come from the canonical map (app/concept_meta.py);
# the extra keys below are synthesis/temporal node types specific to this graph.
from app.concept_meta import CONCEPT_COLORS
TYPE_COLORS = {
    **CONCEPT_COLORS,
    'temporal_dynamics_enhanced': '#14b8a6',  # Teal - Pass 3 Temporal
    'code_provision_reference': '#6c757d',     # Gray - Step 4 Synthesis
    'ethical_question': '#0dcaf0',             # Cyan - Step 4 Synthesis
    'ethical_conclusion': '#198754',           # Green - Step 4 Synthesis
}


# Namespaces whose object properties render as graph edges. Class-level and
# annotation triples are excluded naturally: their endpoints' labels are not in
# the node map.
_GRAPH_EDGE_NS = (
    "http://proethica.org/ontology/core#",
    "http://proethica.org/ontology/intermediate#",
    "http://proethica.org/ontology/cases#",
    "http://purl.org/dc/terms/",
)


def _add_committed_graph_edges(case_id: int, nodes: list, edges: list, label_to_node: dict) -> int:
    """Edges (and Agent nodes) from the committed case graph.

    The temp-JSON 'relationships' arrays are a legacy format the
    fresh-architecture extraction rarely populates: across the 15 gold cases
    they yielded 530 edges total and left 79 percent of nodes unconnected --
    with the tab's Hide-unconnected default, four of five entities were
    invisible (2026-07-08 Entities audit). The committed case graph carries
    the authoritative object-property layer between individuals, so it is the
    primary edge source; the JSON path remains for uncommitted cases.

    Agents (the case's parties) are minted at commit and have no temp rows, so
    they are added here as nodes; without them the tab showed no parties.

    Raises FileNotFoundError when the case has no committed TTL (caller treats
    that as the uncommitted-case state and keeps JSON-derived edges only).
    """
    from rdflib import RDF, RDFS, URIRef
    from app.services.entity.committed_case_graph import load_case_graph
    g = load_case_graph(case_id)

    core_agent = URIRef("http://proethica.org/ontology/core#Agent")
    for s in g.subjects(RDF.type, core_agent):
        lbl = g.value(s, RDFS.label)
        label = str(lbl) if lbl else str(s).rsplit('#', 1)[-1].replace('_', ' ')
        key = label.lower()
        if key in label_to_node:
            continue
        node_id = f"agent_{str(s).rsplit('#', 1)[-1]}"
        nodes.append({
            'id': node_id,
            'db_id': 0,
            'type': 'agents',
            'entity_type': 'Agent',
            'label': label,
            'definition': 'Case party (committed graph)',
            'pass': 1,
            'section': 'committed',
            'color': '#f59e0b',
            'is_published': True,
            'is_selected': False,
            'agent': None,
            'temporal_marker': None,
            'entity_uri': str(s),
        })
        label_to_node[key] = node_id
        label_to_node[key.replace(' ', '_')] = node_id

    existing = {(e['source'], e['target'], e['type']) for e in edges}
    added = 0
    for s, p, o in g:
        ps = str(p)
        if not ps.startswith(_GRAPH_EDGE_NS) or not isinstance(o, URIRef):
            continue
        s_l = g.value(s, RDFS.label)
        o_l = g.value(o, RDFS.label)
        if s_l is None or o_l is None:
            continue
        sid = label_to_node.get(str(s_l).lower())
        tid = label_to_node.get(str(o_l).lower())
        if not sid or not tid or sid == tid:
            continue
        etype = ps.rsplit('#', 1)[-1].rsplit('/', 1)[-1]
        key = (sid, tid, etype)
        if key in existing:
            continue
        existing.add(key)
        edges.append({
            'id': f"gedge_{added}",
            'source': sid,
            'target': tid,
            'type': etype,
            'weight': 1.0,
        })
        added += 1
    return added




def _add_analysis_product_edges(case_id: int, entities: list, edges: list, label_to_node: dict) -> int:
    """Edges for the Step-4 analysis products from their OWN reference fields.

    question_emergence/resolution_pattern/canonical_decision_point carry their
    links in JSON (question_uri, conclusion_uri, answers_questions,
    addresses_questions, obligation/role labels) using the case-N#Qn/#Cn
    convention -- real references since the 2026-07-08 serialization fixes.
    Without this pass those nodes rendered edgeless (57+46+15 of the residual
    unconnected in the audit sample)."""
    q_rows = [e for e in entities if e.extraction_type == 'ethical_question']
    c_rows = [e for e in entities if e.extraction_type == 'ethical_conclusion']
    ref_map = {}
    for i, e in enumerate(q_rows, 1):
        ref_map[f"case-{case_id}#Q{i}"] = f"ethical_question_{e.id}"
    for i, e in enumerate(c_rows, 1):
        ref_map[f"case-{case_id}#C{i}"] = f"ethical_conclusion_{e.id}"

    def node_for(ref):
        if not ref or not isinstance(ref, str):
            return None
        if ref in ref_map:
            return ref_map[ref]
        frag = ref.rsplit('#', 1)[-1]
        return (label_to_node.get(frag.replace('_', ' ').lower())
                or label_to_node.get(frag.lower()))

    existing = {(e['source'], e['target'], e['type']) for e in edges}
    added = 0

    def add(src, ref, etype):
        nonlocal added
        tid = node_for(ref)
        if tid and tid != src and (src, tid, etype) not in existing:
            existing.add((src, tid, etype))
            edges.append({'id': f"aedge_{added}", 'source': src, 'target': tid,
                          'type': etype, 'weight': 1.0})
            added += 1

    for e in entities:
        rdf = e.rdf_json_ld if isinstance(e.rdf_json_ld, dict) else None
        if not rdf:
            continue
        sid = f"{e.extraction_type}_{e.id}"
        if e.extraction_type == 'question_emergence':
            add(sid, rdf.get('question_uri'), 'emergence_of')
        elif e.extraction_type == 'resolution_pattern':
            add(sid, rdf.get('conclusion_uri'), 'resolves')
            for q in rdf.get('answers_questions') or []:
                add(sid, q, 'answers')
            for p in rdf.get('determinative_principles') or []:
                add(sid, p, 'determined_by')
        elif e.extraction_type == 'canonical_decision_point':
            for q in rdf.get('addresses_questions') or []:
                add(sid, q, 'addresses')
            add(sid, rdf.get('aligned_conclusion_uri'), 'aligned_with')
            add(sid, rdf.get('obligation_label'), 'focuses_on')
            add(sid, rdf.get('role_label'), 'decided_by')
            for a in rdf.get('involved_action_uris') or []:
                add(sid, a, 'involves')
        elif e.extraction_type == 'causal_normative_link':
            add(sid, rdf.get('action_label') or rdf.get('action_id'), 'about_action')
            for o in rdf.get('fulfills_obligations') or []:
                add(sid, o, 'fulfills')
            for o in rdf.get('violates_obligations') or []:
                add(sid, o, 'violates')
    return added

def build_entity_graph(case_id: int, show_type_hubs: bool = False) -> dict:
    """
    Build entity graph data for D3.js visualization.

    Returns dict with nodes, edges, metadata, and success flag.
    """
    case = Document.query.get_or_404(case_id)

    entities = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        TemporaryRDFStorage.storage_type == 'individual'
    ).all()

    nodes = []
    node_ids = set()

    for entity in entities:
        node_id = f"{entity.extraction_type}_{entity.id}"
        node_ids.add(node_id)

        section = 'unknown'
        definition = entity.entity_definition or ''
        agent = None
        temporal_marker = None

        if entity.rdf_json_ld and isinstance(entity.rdf_json_ld, dict):
            rdf = entity.rdf_json_ld
            section = rdf.get('sourceSection', rdf.get('section', 'unknown'))

            if not definition:
                definition = (
                    rdf.get('proeth:description') or
                    rdf.get('description') or
                    rdf.get('rdfs:comment') or
                    rdf.get('proeth-scenario:ethicalTension') or
                    ''
                )
                if not definition and rdf.get('properties'):
                    props = rdf.get('properties', {})
                    if props.get('caseInvolvement'):
                        inv = props.get('caseInvolvement')
                        definition = inv[0] if isinstance(inv, list) else inv
                    elif props.get('hasEthicalTension'):
                        tension = props.get('hasEthicalTension')
                        definition = tension[0] if isinstance(tension, list) else tension
                if not definition and rdf.get('source_text'):
                    definition = rdf.get('source_text')
                # Last resort: the entity's own label. (Replaced the action
                # competing_priorities/priorityConflict fallback, dropped 2026-06-01 with
                # that field; the node already carries the label.)
                if not definition:
                    definition = entity.entity_label or ''

            agent = rdf.get('proeth:hasAgent')
            temporal_marker = rdf.get('proeth:temporalMarker')

        nodes.append({
            'id': node_id,
            'db_id': entity.id,
            'type': entity.extraction_type,
            'entity_type': entity.entity_type,
            'label': entity.entity_label or f"Entity {entity.id}",
            'definition': definition,
            'pass': TYPE_TO_PASS.get(entity.extraction_type, 0),
            'section': section,
            'color': TYPE_COLORS.get(entity.extraction_type, '#999999'),
            'is_published': entity.is_published,
            'is_selected': entity.is_selected,
            'agent': agent,
            'temporal_marker': temporal_marker,
            'entity_uri': entity.entity_uri or ''
        })

    # Build edges from RDF relationships
    edges = []
    edge_id = 0

    # Label to node_id mapping
    label_to_node = {}
    for node in nodes:
        label_to_node[node['label'].lower()] = node['id']
        label_to_node[node['label'].lower().replace(' ', '_')] = node['id']

    for entity in entities:
        if not entity.rdf_json_ld or not isinstance(entity.rdf_json_ld, dict):
            continue

        source_id = f"{entity.extraction_type}_{entity.id}"
        rdf = entity.rdf_json_ld

        # PRIMARY: Extract from 'relationships' array (new format)
        if 'relationships' in rdf and isinstance(rdf['relationships'], list):
            for rel in rdf['relationships']:
                if isinstance(rel, dict) and 'target' in rel:
                    target_label = rel.get('target', '').lower()
                    rel_type = rel.get('type', 'related_to')

                    target_id = label_to_node.get(target_label)
                    if not target_id:
                        target_id = label_to_node.get(target_label.replace(' ', '_'))

                    if target_id and target_id != source_id:
                        edges.append({
                            'id': f"edge_{edge_id}",
                            'source': source_id,
                            'target': target_id,
                            'type': rel_type,
                            'weight': 1.0
                        })
                        edge_id += 1

        # SECONDARY: Extract from flat RDF fields (legacy format)
        relationship_fields = [
            ('performedBy', 'performed_by'),
            ('agent', 'has_agent'),
            ('involves', 'involves'),
            ('affectedBy', 'affected_by'),
            ('triggers', 'triggers'),
            ('enabledBy', 'enabled_by'),
            ('constrainedBy', 'constrained_by'),
            ('governedBy', 'governed_by'),
            ('appliesTo', 'applies_to'),
            ('relatedTo', 'related_to'),
            ('answersQuestions', 'answers'),
            ('citedProvisions', 'cites'),
            ('mentionedEntities', 'mentions')
        ]

        for rdf_field, edge_type in relationship_fields:
            if rdf_field in rdf:
                targets = rdf[rdf_field]
                if not isinstance(targets, list):
                    targets = [targets]

                for target in targets:
                    target_label = str(target).lower() if not isinstance(target, dict) else target.get('label', str(target)).lower()
                    target_id = label_to_node.get(target_label)
                    if not target_id:
                        target_id = label_to_node.get(target_label.replace(' ', '_'))

                    if target_id and target_id != source_id:
                        existing = any(e['source'] == source_id and e['target'] == target_id and e['type'] == edge_type for e in edges)
                        if not existing:
                            edges.append({
                                'id': f"edge_{edge_id}",
                                'source': source_id,
                                'target': target_id,
                                'type': edge_type,
                                'weight': 1.0
                            })
                            edge_id += 1

    # Q-C edges from answersQuestions (question numbers, not labels)
    question_num_to_node = {}
    for entity in entities:
        if entity.extraction_type == 'ethical_question':
            label = entity.entity_label or ''
            match = re.search(r'(\d+)', label)
            if match:
                q_num = int(match.group(1))
                question_num_to_node[q_num] = f"ethical_question_{entity.id}"

    for entity in entities:
        if entity.extraction_type == 'ethical_conclusion':
            if entity.rdf_json_ld and isinstance(entity.rdf_json_ld, dict):
                rdf = entity.rdf_json_ld

                answers = rdf.get('answersQuestions', [])

                if not answers:
                    answers = rdf.get('relatedAnalyticalQuestions', [])

                if not answers:
                    label = entity.entity_label or ''
                    match = re.match(r'C(\d+)', label)
                    if match:
                        inferred_q_num = int(match.group(1))
                        if inferred_q_num in question_num_to_node:
                            answers = [inferred_q_num]

                if answers:
                    source_id = f"ethical_conclusion_{entity.id}"
                    for q_num in answers:
                        if isinstance(q_num, (int, str)):
                            q_num_int = int(q_num) if isinstance(q_num, str) else q_num
                            target_id = question_num_to_node.get(q_num_int)
                            if target_id and target_id != source_id:
                                existing = any(
                                    e['source'] == source_id and e['target'] == target_id and e['type'] == 'answers'
                                    for e in edges
                                )
                                if not existing:
                                    edges.append({
                                        'id': f"edge_{edge_id}",
                                        'source': source_id,
                                        'target': target_id,
                                        'type': 'answers',
                                        'weight': 1.0
                                    })
                                    edge_id += 1

    # Analysis-product edges from their own JSON reference fields.
    try:
        analysis_edges = _add_analysis_product_edges(case_id, entities, edges, label_to_node)
        logger.info(f"Entity graph case {case_id}: {analysis_edges} analysis-product edges added")
    except Exception as exc:  # noqa: BLE001 - additive, never fatal
        logger.warning(f"Entity graph case {case_id}: analysis-product edges failed: {exc}")

    # Committed-graph edges + Agent nodes (primary edge source; see helper).
    try:
        graph_edges = _add_committed_graph_edges(case_id, nodes, edges, label_to_node)
        logger.info(f"Entity graph case {case_id}: {graph_edges} committed-graph edges added")
    except FileNotFoundError:
        logger.info(f"Entity graph case {case_id}: no committed TTL, JSON-derived edges only")
    except Exception as exc:  # noqa: BLE001 - graph edges are additive, never fatal
        logger.warning(f"Entity graph case {case_id}: committed-graph edge derivation failed: {exc}")

    # Optional type hub nodes
    if show_type_hubs:
        type_hub_colors = {
            'roles': '#3b82f6', 'states': '#8b5cf6', 'resources': '#2dd4bf',
            'principles': '#f97316', 'obligations': '#ef4444', 'constraints': '#9ca3af',
            'capabilities': '#22d3ee', 'temporal_dynamics_enhanced': '#14b8a6',
            'actions': '#22c55e', 'events': '#facc15',
            'code_provision_reference': '#9ca3af', 'ethical_question': '#22d3ee',
            'ethical_conclusion': '#22c55e'
        }
        type_labels = {
            'roles': 'R (Roles)', 'states': 'S (States)', 'resources': 'Rs (Resources)',
            'principles': 'P (Principles)', 'obligations': 'O (Obligations)',
            'constraints': 'Cs (Constraints)', 'capabilities': 'Ca (Capabilities)',
            'temporal_dynamics_enhanced': 'A/E (Actions/Events)',
            'code_provision_reference': 'Provisions', 'ethical_question': 'Questions',
            'ethical_conclusion': 'Conclusions'
        }

        for etype in TYPE_TO_PASS.keys():
            if any(n['type'] == etype for n in nodes):
                hub_id = f"hub_{etype}"
                nodes.append({
                    'id': hub_id,
                    'db_id': 0,
                    'type': 'hub',
                    'entity_type': 'TypeHub',
                    'label': type_labels.get(etype, etype),
                    'definition': f'Type hub for {etype}',
                    'pass': TYPE_TO_PASS.get(etype, 0),
                    'section': 'hub',
                    'color': type_hub_colors.get(etype, '#999'),
                    'is_hub': True,
                    'is_published': False,
                    'is_selected': False
                })
                for node in [n for n in nodes if n['type'] == etype]:
                    edges.append({
                        'id': f"edge_{edge_id}",
                        'source': node['id'],
                        'target': hub_id,
                        'type': 'instance_of',
                        'weight': 0.3
                    })
                    edge_id += 1

    # Build metadata
    type_counts = {}
    pass_counts = {1: 0, 2: 0, 3: 0, 4: 0}

    for node in nodes:
        etype = node['type']
        type_counts[etype] = type_counts.get(etype, 0) + 1
        pass_counts[node['pass']] = pass_counts.get(node['pass'], 0) + 1

    metadata = {
        'case_id': case_id,
        'case_title': case.title,
        'total_nodes': len(nodes),
        'total_edges': len(edges),
        'type_counts': type_counts,
        'pass_counts': pass_counts,
        'type_colors': TYPE_COLORS
    }

    return {
        'success': True,
        'nodes': nodes,
        'edges': edges,
        'metadata': metadata
    }


def build_qc_flow(case_id: int) -> dict:
    """
    Build Question-Conclusion flow data for Sankey visualization.

    Returns dict with questions, conclusions, links, metadata, and success flag.
    """
    from app.services.step4_synthesis.step4_data_helpers import (
        _classify_conclusion_type, _count_conclusion_types,
    )

    case = Document.query.get_or_404(case_id)

    questions_query = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        TemporaryRDFStorage.entity_type == 'questions'
    ).all()

    conclusions_query = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        TemporaryRDFStorage.entity_type == 'conclusions'
    ).all()

    if not questions_query and not conclusions_query:
        return {
            'success': False,
            'error': 'No questions or conclusions found. Run Step 4 synthesis first.',
            'questions': [],
            'conclusions': [],
            'links': []
        }

    # Build questions array
    questions = []
    for q in questions_query:
        rdf = q.rdf_json_ld or {}
        questions.append({
            'id': f"Q{rdf.get('questionNumber', q.id)}",
            'db_id': q.id,
            'number': rdf.get('questionNumber', 0),
            'text': rdf.get('questionText', q.entity_definition or ''),
            'label': q.entity_label,
            'provisions': rdf.get('relatedProvisions', []),
            'mentioned_entities': rdf.get('mentionedEntities', {})
        })

    # Build conclusions array with type classification
    conclusions = []
    for c in conclusions_query:
        rdf = c.rdf_json_ld or {}
        conclusion_text = rdf.get('conclusionText', c.entity_definition or '')
        conclusion_type = _classify_conclusion_type(conclusion_text)

        conclusions.append({
            'id': f"C{rdf.get('conclusionNumber', c.id)}",
            'db_id': c.id,
            'number': rdf.get('conclusionNumber', 0),
            'text': conclusion_text,
            'label': c.entity_label,
            'type': conclusion_type,
            'provisions': rdf.get('citedProvisions', []),
            'answers_questions': rdf.get('answersQuestions', []),
            'mentioned_entities': rdf.get('mentionedEntities', {})
        })

    # Build links from conclusions' answersQuestions field
    links = []
    for c in conclusions:
        for q_num in c.get('answers_questions', []):
            matching_q = next((q for q in questions if q['number'] == q_num), None)
            if matching_q:
                links.append({
                    'source': matching_q['id'],
                    'target': c['id'],
                    'value': 1,
                    'confidence': 0.95
                })

    questions.sort(key=lambda x: x['number'])
    conclusions.sort(key=lambda x: x['number'])

    return {
        'success': True,
        'case_id': case_id,
        'case_title': case.title,
        'questions': questions,
        'conclusions': conclusions,
        'links': links,
        'metadata': {
            'question_count': len(questions),
            'conclusion_count': len(conclusions),
            'link_count': len(links),
            'conclusion_types': _count_conclusion_types(conclusions)
        }
    }


def extract_questions_conclusions(
    case_id: int,
    case: Document,
    provisions: List[Dict]
) -> Tuple[List, List]:
    """
    Part B: Extract questions and conclusions with entity tagging.

    Returns:
        Tuple of (questions, conclusions)
    """
    # The Q/C analyzers resolve the DEFAULT tier internally (QuestionAnalyzer/
    # ConclusionAnalyzer hardcode ModelConfig.get_claude_model("default")); the
    # prompt rows below record what actually ran, not the step-4 powerful tier
    # this function mis-stamped until 2026-07-11.
    from app.routes.scenario_pipeline.step4.config import (
        STEP4_DEFAULT_MODEL,
    )
    from app.services.step4_synthesis.step4_data_helpers import (
        get_all_case_entities, _count_conclusion_types_from_list,
    )

    logger.info(f"Part B: Starting Q&C extraction for case {case_id}")

    all_entities = get_all_case_entities(case_id)

    questions_text = ""
    conclusions_text = ""

    if case.doc_metadata and 'sections_dual' in case.doc_metadata:
        sections = case.doc_metadata['sections_dual']

        if 'question' in sections:
            q_data = sections['question']
            questions_text = q_data.get('text', '') if isinstance(q_data, dict) else str(q_data)

        if 'conclusion' in sections:
            c_data = sections['conclusion']
            conclusions_text = c_data.get('text', '') if isinstance(c_data, dict) else str(c_data)

    llm_client = get_llm_client()

    # Extract questions
    question_analyzer = QuestionAnalyzer(llm_client)
    questions = question_analyzer.extract_questions(
        questions_text,
        all_entities,
        provisions
    )

    logger.info(f"Extracted {len(questions)} questions")

    # Extract conclusions
    conclusion_analyzer = ConclusionAnalyzer(llm_client)
    conclusions = conclusion_analyzer.extract_conclusions(
        conclusions_text,
        all_entities,
        provisions
    )

    logger.info(f"Extracted {len(conclusions)} conclusions")

    # Link Q->C
    linker = QuestionConclusionLinker(llm_client)
    qc_links = linker.link_questions_to_conclusions(questions, conclusions)

    logger.info(f"Created {len(qc_links)} Q->C links")

    conclusions = linker.apply_links_to_conclusions(conclusions, qc_links)

    # Store questions and conclusions
    session_id = str(uuid.uuid4())

    # Clear old Q&C
    TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='ethical_question'
    ).delete(synchronize_session=False)

    TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='ethical_conclusion'
    ).delete(synchronize_session=False)

    # Store ExtractionPrompt for questions (Step 4b)
    question_prompt_response = question_analyzer.get_last_prompt_and_response()
    if question_prompt_response.get('prompt'):
        question_extraction_prompt = ExtractionPrompt(
            case_id=case_id,
            concept_type='ethical_question',
            step_number=4,
            section_type='questions',
            prompt_text=question_prompt_response.get('prompt', ''),
            llm_model=STEP4_DEFAULT_MODEL,
            extraction_session_id=session_id,
            raw_response=question_prompt_response.get('response', ''),
            results_summary={
                'total_questions': len(questions),
                'questions_with_provisions': len([q for q in questions if q.get('related_provisions', [])])
            },
            is_active=True,
            times_used=1,
            created_at=datetime.utcnow(),
            last_used_at=datetime.utcnow()
        )
        db.session.add(question_extraction_prompt)

    # Store questions via the shared row builder (see app/services/step4_synthesis/qc_entity_storage.py;
    # identical to step4_synthesis_service's).
    for question in questions:
        db.session.add(make_question_storage(case_id, session_id, question))

    # Store ExtractionPrompt for conclusions (Step 4c)
    conclusion_prompt_response = conclusion_analyzer.get_last_prompt_and_response()
    if conclusion_prompt_response.get('prompt'):
        conclusion_extraction_prompt = ExtractionPrompt(
            case_id=case_id,
            concept_type='ethical_conclusion',
            step_number=4,
            section_type='conclusions',
            prompt_text=conclusion_prompt_response.get('prompt', ''),
            llm_model=STEP4_DEFAULT_MODEL,
            extraction_session_id=session_id,
            raw_response=conclusion_prompt_response.get('response', ''),
            results_summary={
                'total_conclusions': len(conclusions),
                'conclusions_by_type': _count_conclusion_types_from_list(conclusions)
            },
            is_active=True,
            times_used=1,
            created_at=datetime.utcnow(),
            last_used_at=datetime.utcnow()
        )
        db.session.add(conclusion_extraction_prompt)

    # Store conclusions via the shared row builder (see app/services/step4_synthesis/qc_entity_storage.py).
    for conclusion in conclusions:
        db.session.add(make_conclusion_storage(case_id, session_id, conclusion))

    db.session.commit()

    logger.info(f"Part B complete: Stored {len(questions)} questions, {len(conclusions)} conclusions")

    return questions, conclusions


def count_question_types(questions: list) -> dict:
    """Count questions by type (questions is List[Dict])."""
    counts = {}
    for q in questions:
        q_type = q.get('question_type', 'unknown') if isinstance(q, dict) else getattr(q, 'question_type', 'unknown')
        counts[q_type] = counts.get(q_type, 0) + 1
    return counts
