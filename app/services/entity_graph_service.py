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
from app.utils.llm_utils import get_llm_client

from app.services.question_analyzer import QuestionAnalyzer
from app.services.conclusion_analyzer import ConclusionAnalyzer
from app.services.question_conclusion_linker import QuestionConclusionLinker
from app.services.case_synthesis_service import CaseSynthesisService

logger = logging.getLogger(__name__)


# Entity type to pass mapping (shared by graph and flow builders)
TYPE_TO_PASS = {
    'roles': 1, 'states': 1, 'resources': 1,
    'principles': 2, 'obligations': 2, 'constraints': 2, 'capabilities': 2,
    'temporal_dynamics_enhanced': 3, 'actions': 3, 'events': 3,
    'code_provision_reference': 4, 'ethical_question': 4, 'ethical_conclusion': 4
}

# Entity type colors - matches docs/reference/color-scheme.md
TYPE_COLORS = {
    'roles': '#0d6efd',              # Blue - Pass 1 Context
    'states': '#6f42c1',             # Purple - Pass 1 Context
    'resources': '#20c997',          # Teal - Pass 1 Context
    'principles': '#fd7e14',         # Orange - Pass 2 Normative
    'obligations': '#dc3545',        # Red - Pass 2 Normative
    'constraints': '#6c757d',        # Gray - Pass 2 Normative
    'capabilities': '#0dcaf0',       # Cyan - Pass 2 Normative
    'temporal_dynamics_enhanced': '#14b8a6',  # Teal - Pass 3 Temporal
    'actions': '#198754',            # Green - Pass 3 Temporal
    'events': '#ffc107',             # Yellow - Pass 3 Temporal
    'code_provision_reference': '#6c757d',  # Gray - Step 4 Synthesis
    'ethical_question': '#0dcaf0',   # Cyan - Step 4 Synthesis
    'ethical_conclusion': '#198754'  # Green - Step 4 Synthesis
}


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
                if not definition and rdf.get('proeth:hasCompetingPriorities'):
                    cp = rdf.get('proeth:hasCompetingPriorities', {})
                    if isinstance(cp, dict):
                        definition = cp.get('proeth:priorityConflict', '')

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
    # Lazy import to avoid circular dependency via step4/__init__.py
    from app.routes.scenario_pipeline.step4.helpers import (
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
    # Lazy imports to avoid circular dependency via step4/__init__.py
    from app.routes.scenario_pipeline.step4.config import (
        STEP4_POWERFUL_MODEL,
    )
    from app.routes.scenario_pipeline.step4.helpers import (
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
            llm_model=STEP4_POWERFUL_MODEL,
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

    # Store questions
    for question in questions:
        rdf_entity = TemporaryRDFStorage(
            case_id=case_id,
            extraction_session_id=session_id,
            extraction_type='ethical_question',
            storage_type='individual',
            entity_type='questions',
            entity_label=f"Question_{question['question_number']}",
            entity_definition=question['question_text'],
            rdf_json_ld={
                '@type': 'proeth-case:EthicalQuestion',
                'questionNumber': question['question_number'],
                'questionText': question['question_text'],
                'questionType': question.get('question_type', 'unknown'),
                'mentionedEntities': question.get('mentioned_entities', {}),
                'relatedProvisions': question.get('related_provisions', []),
                'extractionReasoning': question.get('extraction_reasoning', '')
            },
            is_selected=True
        )
        db.session.add(rdf_entity)

    # Store ExtractionPrompt for conclusions (Step 4c)
    conclusion_prompt_response = conclusion_analyzer.get_last_prompt_and_response()
    if conclusion_prompt_response.get('prompt'):
        conclusion_extraction_prompt = ExtractionPrompt(
            case_id=case_id,
            concept_type='ethical_conclusion',
            step_number=4,
            section_type='conclusions',
            prompt_text=conclusion_prompt_response.get('prompt', ''),
            llm_model=STEP4_POWERFUL_MODEL,
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

    # Store conclusions
    for conclusion in conclusions:
        rdf_entity = TemporaryRDFStorage(
            case_id=case_id,
            extraction_session_id=session_id,
            extraction_type='ethical_conclusion',
            storage_type='individual',
            entity_type='conclusions',
            entity_label=f"Conclusion_{conclusion['conclusion_number']}",
            entity_definition=conclusion['conclusion_text'],
            rdf_json_ld={
                '@type': 'proeth-case:EthicalConclusion',
                'conclusionNumber': conclusion['conclusion_number'],
                'conclusionText': conclusion['conclusion_text'],
                'conclusionType': conclusion.get('conclusion_type', 'unknown'),
                'mentionedEntities': conclusion.get('mentioned_entities', {}),
                'citedProvisions': conclusion.get('cited_provisions', []),
                'answersQuestions': conclusion.get('answers_questions', []),
                'extractionReasoning': conclusion.get('extraction_reasoning', '')
            },
            is_selected=True
        )
        db.session.add(rdf_entity)

    db.session.commit()

    logger.info(f"Part B complete: Stored {len(questions)} questions, {len(conclusions)} conclusions")

    return questions, conclusions


def perform_cross_section_synthesis(
    case_id: int,
    provisions: List[Dict],
    questions: List,
    conclusions: List
) -> Dict:
    """
    Part C: Cross-section synthesis operations.

    Uses CaseSynthesisService to:
    - Build entity knowledge graph
    - Link causal chains to normative requirements
    - Analyze question emergence
    - Extract resolution patterns

    Returns:
        Dict with synthesis results
    """
    # Lazy import to avoid circular dependency via step4/__init__.py
    from app.routes.scenario_pipeline.step4.helpers import _store_synthesis_results

    logger.info(f"Part C: Starting cross-section synthesis for case {case_id}")

    llm_client = get_llm_client()
    synthesis_service = CaseSynthesisService(llm_client)

    try:
        synthesis = synthesis_service.synthesize_case(case_id)

        synthesis_results = {
            'entity_graph': {
                'status': 'complete',
                'total_nodes': synthesis.total_nodes,
                'node_types': len(synthesis.entity_graph.by_type),
                'sections': len(synthesis.entity_graph.by_section)
            },
            'causal_normative_links': {
                'status': 'complete',
                'total_links': len(synthesis.causal_normative_links),
                'actions_linked': len([l for l in synthesis.causal_normative_links if 'actions' in l.action_id]),
                'events_linked': len([l for l in synthesis.causal_normative_links if 'events' in l.action_id])
            },
            'question_emergence': {
                'status': 'complete',
                'total_questions': len(synthesis.question_emergence),
                'questions_with_triggers': len([q for q in synthesis.question_emergence
                                                if q.triggered_by_events or q.triggered_by_actions])
            },
            'resolution_patterns': {
                'status': 'complete',
                'total_patterns': len(synthesis.resolution_patterns),
                'pattern_types': list(set([p.pattern_type for p in synthesis.resolution_patterns]))
            },
            'statistics': {
                'synthesis_timestamp': synthesis.synthesis_timestamp.isoformat(),
                'total_entities': synthesis.total_nodes,
                'total_provisions': len(provisions),
                'total_questions': len(questions),
                'total_conclusions': len(conclusions)
            }
        }

        _store_synthesis_results(case_id, synthesis)

        logger.info(f"Part C complete: Full synthesis performed")

        return synthesis_results

    except Exception as e:
        logger.error(f"Error in synthesis: {e}")
        import traceback
        traceback.print_exc()

        return {
            'entity_graph': {
                'status': 'error',
                'message': str(e)
            },
            'error': str(e)
        }


def count_question_types(questions: list) -> dict:
    """Count questions by type (questions is List[Dict])."""
    counts = {}
    for q in questions:
        q_type = q.get('question_type', 'unknown') if isinstance(q, dict) else getattr(q, 'question_type', 'unknown')
        counts[q_type] = counts.get(q_type, 0) + 1
    return counts
