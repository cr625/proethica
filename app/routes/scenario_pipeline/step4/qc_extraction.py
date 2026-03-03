"""
Step 4 Question & Conclusion Extraction Routes

Handles:
- Unified Q&C extraction (non-streaming and SSE streaming)
- Entity graph API for D3.js visualization
- Q-C flow API for Sankey visualization
- Cross-section synthesis orchestration
"""

import json as json_mod
import logging
import re
import uuid
from datetime import datetime
from typing import Dict, List, Tuple

from flask import jsonify, request, Response, stream_with_context

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.utils.llm_utils import get_llm_client
from app.utils.environment_auth import auth_required_for_llm

from app.services.question_analyzer import QuestionAnalyzer
from app.services.conclusion_analyzer import ConclusionAnalyzer
from app.services.question_conclusion_linker import QuestionConclusionLinker
from app.services.case_synthesis_service import CaseSynthesisService

from app.routes.scenario_pipeline.step4.config import (
    STEP4_SECTION_TYPE, STEP4_DEFAULT_MODEL, STEP4_POWERFUL_MODEL,
)
from app.routes.scenario_pipeline.step4.helpers import (
    get_all_case_entities, _classify_conclusion_type, _count_conclusion_types,
    _count_conclusion_types_from_list, _store_synthesis_results,
)

logger = logging.getLogger(__name__)


# ============================================================================
# STANDALONE FUNCTIONS
# ============================================================================

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
    logger.info(f"Part B: Starting Q&C extraction for case {case_id}")

    # Get ALL entities
    all_entities = get_all_case_entities(case_id)

    # Get Questions and Conclusions section text
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

    # Apply links to conclusions
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
                'questions_with_provisions': len([q for q in questions if q.related_provisions])
            },
            is_active=True,
            times_used=1,
            created_at=datetime.utcnow(),
            last_used_at=datetime.utcnow()
        )
        db.session.add(question_extraction_prompt)

    # Store questions (questions is List[Dict] from QuestionAnalyzer)
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

    # Store conclusions (conclusions is List[Dict] from ConclusionAnalyzer)
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
    logger.info(f"Part C: Starting cross-section synthesis for case {case_id}")

    # Initialize synthesis service
    llm_client = get_llm_client()
    synthesis_service = CaseSynthesisService(llm_client)

    try:
        # Run comprehensive synthesis
        synthesis = synthesis_service.synthesize_case(case_id)

        # Convert to dict for JSON response
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

        # Store synthesis for later viewing
        _store_synthesis_results(case_id, synthesis)

        logger.info(f"Part C complete: Full synthesis performed")

        return synthesis_results

    except Exception as e:
        logger.error(f"Error in synthesis: {e}")
        import traceback
        traceback.print_exc()

        # Return error status
        return {
            'entity_graph': {
                'status': 'error',
                'message': str(e)
            },
            'error': str(e)
        }


def _count_question_types(questions: list) -> dict:
    """Count questions by type (questions is List[Dict])."""
    counts = {}
    for q in questions:
        q_type = q.get('question_type', 'unknown') if isinstance(q, dict) else getattr(q, 'question_type', 'unknown')
        counts[q_type] = counts.get(q_type, 0) + 1
    return counts


# ============================================================================
# ROUTE REGISTRATION
# ============================================================================

def register_qc_routes(bp):
    """Register Q&C extraction and visualization routes on the blueprint."""

    @bp.route('/case/<int:case_id>/entity_graph')
    def get_entity_graph_api(case_id):
        """
        API endpoint returning entity graph data for D3.js visualization.

        Returns JSON with:
        - nodes: All entities with type, label, definition, pass info
        - edges: Relationships between entities (from RDF data)
        - metadata: Case info and entity counts
        """
        try:
            case = Document.query.get_or_404(case_id)

            # Get all entities
            entities = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.storage_type == 'individual'
            ).all()

            # Build nodes
            nodes = []
            node_ids = set()

            # Entity type to pass mapping
            type_to_pass = {
                'roles': 1, 'states': 1, 'resources': 1,
                'principles': 2, 'obligations': 2, 'constraints': 2, 'capabilities': 2,
                'temporal_dynamics_enhanced': 3, 'actions': 3, 'events': 3,
                'code_provision_reference': 4, 'ethical_question': 4, 'ethical_conclusion': 4
            }

            # Entity type colors - matches docs/reference/color-scheme.md
            type_colors = {
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

            for entity in entities:
                node_id = f"{entity.extraction_type}_{entity.id}"
                node_ids.add(node_id)

                # Get section and definition from RDF if available
                section = 'unknown'
                definition = entity.entity_definition or ''
                agent = None
                temporal_marker = None

                if entity.rdf_json_ld and isinstance(entity.rdf_json_ld, dict):
                    rdf = entity.rdf_json_ld
                    section = rdf.get('sourceSection', rdf.get('section', 'unknown'))

                    # Fall back to RDF fields for definition if database field is empty
                    if not definition:
                        # Try standard RDF fields first
                        definition = (
                            rdf.get('proeth:description') or
                            rdf.get('description') or
                            rdf.get('rdfs:comment') or
                            rdf.get('proeth-scenario:ethicalTension') or
                            ''
                        )
                        # For Pass 1-2 entities, try properties fields
                        if not definition and rdf.get('properties'):
                            props = rdf.get('properties', {})
                            # Try caseInvolvement first (describes role in case)
                            if props.get('caseInvolvement'):
                                inv = props.get('caseInvolvement')
                                definition = inv[0] if isinstance(inv, list) else inv
                            # Try hasEthicalTension
                            elif props.get('hasEthicalTension'):
                                tension = props.get('hasEthicalTension')
                                definition = tension[0] if isinstance(tension, list) else tension
                        # Try source_text as last resort
                        if not definition and rdf.get('source_text'):
                            definition = rdf.get('source_text')
                        # For competing priorities, extract the conflict description
                        if not definition and rdf.get('proeth:hasCompetingPriorities'):
                            cp = rdf.get('proeth:hasCompetingPriorities', {})
                            if isinstance(cp, dict):
                                definition = cp.get('proeth:priorityConflict', '')

                    # Extract additional metadata for richer display
                    agent = rdf.get('proeth:hasAgent')
                    temporal_marker = rdf.get('proeth:temporalMarker')

                nodes.append({
                    'id': node_id,
                    'db_id': entity.id,
                    'type': entity.extraction_type,
                    'entity_type': entity.entity_type,
                    'label': entity.entity_label or f"Entity {entity.id}",
                    'definition': definition,
                    'pass': type_to_pass.get(entity.extraction_type, 0),
                    'section': section,
                    'color': type_colors.get(entity.extraction_type, '#999999'),
                    'is_published': entity.is_published,
                    'is_selected': entity.is_selected,
                    'agent': agent,
                    'temporal_marker': temporal_marker,
                    'entity_uri': entity.entity_uri or ''
                })

            # Build edges from RDF relationships
            edges = []
            edge_id = 0

            # Create label to node_id mapping for efficient lookup
            label_to_node = {}
            for node in nodes:
                label_to_node[node['label'].lower()] = node['id']
                # Also map without spaces and with underscores
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

                            # Find target node by label
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
                                # Avoid duplicate edges
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

            # SPECIAL: Create Q-C edges from answersQuestions (contains question numbers, not labels)
            # Build a mapping from question number to node_id
            question_num_to_node = {}
            for entity in entities:
                if entity.extraction_type == 'ethical_question':
                    label = entity.entity_label or ''
                    # Extract number from label like "Question_1", "Q1_board_explicit", etc.
                    match = re.search(r'(\d+)', label)
                    if match:
                        q_num = int(match.group(1))
                        question_num_to_node[q_num] = f"ethical_question_{entity.id}"

            # Now create edges from conclusions to questions
            for entity in entities:
                if entity.extraction_type == 'ethical_conclusion':
                    if entity.rdf_json_ld and isinstance(entity.rdf_json_ld, dict):
                        rdf = entity.rdf_json_ld

                        # Try multiple sources for question linkage (in priority order):
                        # 1. answersQuestions (current format)
                        # 2. relatedAnalyticalQuestions (legacy format)
                        # 3. Infer from label naming pattern (C1_* -> Q1, etc.)
                        answers = rdf.get('answersQuestions', [])

                        if not answers:
                            # Fallback to relatedAnalyticalQuestions
                            answers = rdf.get('relatedAnalyticalQuestions', [])

                        if not answers:
                            # Fallback: infer from conclusion label naming pattern
                            # Labels like "C1_board_explicit" -> Q1, "C101_analytical" -> Q101
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
                                        # Check for duplicates
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

            # OPTIONAL: Add type hub nodes if requested via query param
            show_type_hubs = request.args.get('type_hubs', 'false').lower() == 'true'
            if show_type_hubs:
                # Hub colors - brighter variants for visual distinction from entity nodes
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

                # Add hub nodes and connect entities to their type hubs
                for etype in type_to_pass.keys():
                    if any(n['type'] == etype for n in nodes):
                        hub_id = f"hub_{etype}"
                        nodes.append({
                            'id': hub_id,
                            'db_id': 0,
                            'type': 'hub',
                            'entity_type': 'TypeHub',
                            'label': type_labels.get(etype, etype),
                            'definition': f'Type hub for {etype}',
                            'pass': type_to_pass.get(etype, 0),
                            'section': 'hub',
                            'color': type_hub_colors.get(etype, '#999'),
                            'is_hub': True,
                            'is_published': False,
                            'is_selected': False
                        })
                        # Connect all entities of this type to the hub
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
                'type_colors': type_colors
            }

            return jsonify({
                'success': True,
                'nodes': nodes,
                'edges': edges,
                'metadata': metadata
            })

        except Exception as e:
            logger.error(f"Error getting entity graph for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/qc_flow')
    def get_qc_flow_api(case_id):
        """
        API endpoint returning Question-Conclusion flow data for Sankey visualization.

        Returns JSON with:
        - questions: All ethical questions with metadata
        - conclusions: All ethical conclusions with type classification
        - links: Mappings between questions and conclusions
        """
        try:
            case = Document.query.get_or_404(case_id)

            # Get questions
            questions_query = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.entity_type == 'questions'
            ).all()

            # Get conclusions
            conclusions_query = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.entity_type == 'conclusions'
            ).all()

            if not questions_query and not conclusions_query:
                return jsonify({
                    'success': False,
                    'error': 'No questions or conclusions found. Run Step 4 synthesis first.',
                    'questions': [],
                    'conclusions': [],
                    'links': []
                })

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

                # Classify conclusion type based on text content
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
                    # Find matching question
                    matching_q = next((q for q in questions if q['number'] == q_num), None)
                    if matching_q:
                        links.append({
                            'source': matching_q['id'],
                            'target': c['id'],
                            'value': 1,  # Link weight for Sankey
                            'confidence': 0.95  # Based on structural matching
                        })

            # Sort by number
            questions.sort(key=lambda x: x['number'])
            conclusions.sort(key=lambda x: x['number'])

            return jsonify({
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
            })

        except Exception as e:
            logger.error(f"Error building Q-C flow for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e),
                'questions': [],
                'conclusions': [],
                'links': []
            }), 500

    @bp.route('/case/<int:case_id>/extract_qc_unified', methods=['POST'])
    @auth_required_for_llm
    def extract_qc_unified(case_id):
        """
        Part B UNIFIED: Extract Questions, Conclusions, and Link them atomically.

        This endpoint ensures Q-C consistency by:
        1. Clearing old Q&C data
        2. Extracting questions with entity tagging
        3. Extracting conclusions with entity tagging
        4. Linking Q to C
        5. Storing links on conclusions
        6. Committing all in one transaction

        Use this instead of separate extract_questions + extract_conclusions + link endpoints.
        """
        try:
            case = Document.query.get_or_404(case_id)

            # Get provisions for context (load existing, don't re-extract)
            provisions_records = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='code_provision_reference'
            ).all()
            provisions = [r.rdf_json_ld for r in provisions_records if r.rdf_json_ld]

            # Run unified extraction (clears old, extracts both, links, stores)
            questions, conclusions = extract_questions_conclusions(case_id, case, provisions)

            # Get prompts for display
            q_prompt = ExtractionPrompt.query.filter_by(
                case_id=case_id,
                concept_type='ethical_question'
            ).order_by(ExtractionPrompt.created_at.desc()).first()

            c_prompt = ExtractionPrompt.query.filter_by(
                case_id=case_id,
                concept_type='ethical_conclusion'
            ).order_by(ExtractionPrompt.created_at.desc()).first()

            # Count Q-C links (conclusions is List[Dict])
            linked_conclusions = [c for c in conclusions if c.get('answers_questions', [])]

            return jsonify({
                'success': True,
                'prompt': f"Questions extraction:\n{q_prompt.prompt_text[:500] if q_prompt else 'N/A'}...\n\nConclusions extraction:\n{c_prompt.prompt_text[:500] if c_prompt else 'N/A'}...",
                'raw_llm_response': f"Questions: {len(questions)} extracted\nConclusions: {len(conclusions)} extracted\nLinks: {len(linked_conclusions)} conclusions linked to questions",
                'status_messages': [
                    f"Extracted {len(questions)} questions (board_explicit + analytical)",
                    f"Extracted {len(conclusions)} conclusions (board_explicit + analytical)",
                    f"Linked {len(linked_conclusions)} conclusions to questions"
                ],
                'result': {
                    'questions': len(questions),
                    'conclusions': len(conclusions),
                    'links': len(linked_conclusions),
                    'question_types': _count_question_types(questions),
                    'conclusion_types': _count_conclusion_types_from_list(conclusions)
                },
                'metadata': {
                    'q_model': q_prompt.llm_model if q_prompt else 'unknown',
                    'c_model': c_prompt.llm_model if c_prompt else 'unknown',
                    'timestamp': q_prompt.created_at.isoformat() if q_prompt else None
                }
            })

        except Exception as e:
            logger.error(f"Error in unified Q+C extraction for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/extract_qc_unified_stream', methods=['POST'])
    @auth_required_for_llm
    def extract_qc_unified_streaming(case_id):
        """
        Part B UNIFIED with SSE streaming: Extract Questions, Conclusions, and Link them.

        Provides real-time progress updates via Server-Sent Events.
        """
        def sse_msg(data):
            return f"data: {json_mod.dumps(data)}\n\n"

        def generate():
            try:
                case = Document.query.get_or_404(case_id)

                yield sse_msg({'stage': 'START', 'progress': 0, 'messages': ['Starting Q&C extraction...']})

                # Load provisions (don't clear them!)
                yield sse_msg({'stage': 'LOADING_PROVISIONS', 'progress': 5, 'messages': ['Loading code provisions...']})
                provisions_records = TemporaryRDFStorage.query.filter_by(
                    case_id=case_id,
                    extraction_type='code_provision_reference'
                ).all()
                provisions = [r.rdf_json_ld for r in provisions_records if r.rdf_json_ld]
                yield sse_msg({'stage': 'PROVISIONS_LOADED', 'progress': 8, 'messages': [f'Loaded {len(provisions)} provisions']})

                # Get all entities for context
                yield sse_msg({'stage': 'LOADING_ENTITIES', 'progress': 10, 'messages': ['Loading extracted entities...']})
                all_entities = get_all_case_entities(case_id)
                entity_count = sum(len(v) for v in all_entities.values() if isinstance(v, list))
                yield sse_msg({'stage': 'ENTITIES_LOADED', 'progress': 15, 'messages': [f'Loaded {entity_count} entities']})

                # Get section text
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

                # Clear old Q&C
                yield sse_msg({'stage': 'CLEARING', 'progress': 18, 'messages': ['Clearing previous Q&C extractions...']})
                TemporaryRDFStorage.query.filter_by(
                    case_id=case_id,
                    extraction_type='ethical_question'
                ).delete(synchronize_session=False)
                TemporaryRDFStorage.query.filter_by(
                    case_id=case_id,
                    extraction_type='ethical_conclusion'
                ).delete(synchronize_session=False)
                db.session.commit()

                llm_client = get_llm_client()

                # Get facts section for context
                facts_text = ""
                if case.doc_metadata and 'sections_dual' in case.doc_metadata:
                    sections = case.doc_metadata['sections_dual']
                    if 'facts' in sections:
                        f_data = sections['facts']
                        facts_text = f_data.get('text', '') if isinstance(f_data, dict) else str(f_data)

                # Extract questions (with analytical generation)
                yield sse_msg({'stage': 'EXTRACTING_QUESTIONS', 'progress': 25, 'messages': ['Stage 1: Extracting Board questions...']})
                question_analyzer = QuestionAnalyzer(llm_client)

                # Log what we're passing to the analyzer
                logger.info(f"Calling extract_questions_with_analysis with {len(all_entities)} entity types")

                questions_result = question_analyzer.extract_questions_with_analysis(
                    questions_text=questions_text,
                    all_entities=all_entities,
                    code_provisions=provisions,
                    case_facts=facts_text,
                    case_conclusion=conclusions_text
                )

                # Log what we got back
                for q_type in ['board_explicit', 'implicit', 'principle_tension', 'theoretical', 'counterfactual']:
                    count = len(questions_result.get(q_type, []))
                    logger.info(f"  {q_type}: {count} questions")

                yield sse_msg({'stage': 'QUESTIONS_STAGE1', 'progress': 35, 'messages': [f'Stage 1 complete: {len(questions_result.get("board_explicit", []))} Board questions']})
                yield sse_msg({'stage': 'QUESTIONS_STAGE2', 'progress': 40, 'messages': [f'Stage 2: Generated {len(questions_result.get("implicit", []))} implicit, {len(questions_result.get("principle_tension", []))} principle_tension, {len(questions_result.get("theoretical", []))} theoretical, {len(questions_result.get("counterfactual", []))} counterfactual']})

                # Flatten all question types into single list
                questions = []
                for q_type in ['board_explicit', 'implicit', 'principle_tension', 'theoretical', 'counterfactual']:
                    for q in questions_result.get(q_type, []):
                        q_dict = question_analyzer._question_to_dict(q) if hasattr(q, 'question_number') else q
                        questions.append(q_dict)

                board_count = len(questions_result.get('board_explicit', []))
                analytical_count = len(questions) - board_count
                q_messages = [f'Total: {board_count} Board + {analytical_count} analytical = {len(questions)} questions']
                if getattr(question_analyzer, 'analytical_failed', False):
                    q_messages.append('WARNING: Analytical question generation failed after retries')
                elif analytical_count == 0 and board_count > 0:
                    q_messages.append('WARNING: No analytical questions were generated')
                yield sse_msg({'stage': 'QUESTIONS_DONE', 'progress': 45, 'messages': q_messages})

                # Get board questions for conclusion context
                board_questions = [question_analyzer._question_to_dict(q) if hasattr(q, 'question_number') else q
                                  for q in questions_result.get('board_explicit', [])]
                analytical_questions = [q for q in questions if q.get('question_type') != 'board_explicit']

                # Extract conclusions (with analytical generation)
                yield sse_msg({'stage': 'EXTRACTING_CONCLUSIONS', 'progress': 50, 'messages': ['Extracting Board conclusions + generating analytical conclusions...']})
                conclusion_analyzer = ConclusionAnalyzer(llm_client)
                conclusions_result = conclusion_analyzer.extract_conclusions_with_analysis(
                    conclusions_text=conclusions_text,
                    all_entities=all_entities,
                    code_provisions=provisions,
                    board_questions=board_questions,
                    analytical_questions=analytical_questions,
                    case_facts=facts_text
                )

                # Flatten all conclusion types into single list
                conclusions = []
                for c_type in ['board_explicit', 'analytical_extension', 'question_response', 'principle_synthesis']:
                    for c in conclusions_result.get(c_type, []):
                        c_dict = conclusion_analyzer._conclusion_to_dict(c) if hasattr(c, 'conclusion_number') else c
                        conclusions.append(c_dict)

                board_c_count = len(conclusions_result.get('board_explicit', []))
                analytical_c_count = len(conclusions) - board_c_count
                c_messages = [f'Extracted {board_c_count} Board + {analytical_c_count} analytical = {len(conclusions)} total conclusions']
                if getattr(conclusion_analyzer, 'analytical_failed', False):
                    c_messages.append('WARNING: Analytical conclusion generation failed after retries')
                elif analytical_c_count == 0 and board_c_count > 0:
                    c_messages.append('WARNING: No analytical conclusions were generated')
                yield sse_msg({'stage': 'CONCLUSIONS_DONE', 'progress': 70, 'messages': c_messages})

                # Link Q to C
                yield sse_msg({'stage': 'LINKING', 'progress': 75, 'messages': ['Linking questions to conclusions...']})
                linker = QuestionConclusionLinker(llm_client)
                qc_links = linker.link_questions_to_conclusions(questions, conclusions)
                conclusions = linker.apply_links_to_conclusions(conclusions, qc_links)
                yield sse_msg({'stage': 'LINKING_DONE', 'progress': 85, 'messages': [f'Created {len(qc_links)} Q-C links']})

                # Store everything
                yield sse_msg({'stage': 'STORING', 'progress': 88, 'messages': ['Storing extractions...']})
                session_id = str(uuid.uuid4())

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

                # Build formatted results for display
                results_text = f"Questions & Conclusions Extraction\n"
                results_text += "=" * 40 + "\n\n"
                results_text += f"QUESTIONS ({len(questions)}):\n"
                for q in questions:
                    q_num = q.get('question_number', '?')
                    q_type = q.get('question_type', 'unknown')
                    q_text = q.get('question_text', '')[:80]
                    results_text += f"  Q{q_num} [{q_type}]: {q_text}...\n" if len(q.get('question_text', '')) > 80 else f"  Q{q_num} [{q_type}]: {q_text}\n"
                results_text += f"\nCONCLUSIONS ({len(conclusions)}):\n"
                for c in conclusions:
                    c_num = c.get('conclusion_number', '?')
                    c_type = c.get('conclusion_type', 'unknown')
                    c_text = c.get('conclusion_text', '')[:80]
                    answers = c.get('answers_questions', [])
                    answers_str = f" -> answers Q{answers}" if answers else ""
                    results_text += f"  C{c_num} [{c_type}]{answers_str}: {c_text}...\n" if len(c.get('conclusion_text', '')) > 80 else f"  C{c_num} [{c_type}]{answers_str}: {c_text}\n"

                status_messages = [
                    f"Extracted {len(questions)} questions (board_explicit + analytical)",
                    f"Extracted {len(conclusions)} conclusions (board_explicit + analytical)",
                    f"Linked {len(qc_links)} Q-C pairs"
                ]

                # Capture actual LLM prompts from analyzers
                actual_prompts = []
                if question_analyzer.last_prompt:
                    actual_prompts.append("=== QUESTIONS EXTRACTION PROMPT ===\n" + question_analyzer.last_prompt)
                if conclusion_analyzer.last_prompt:
                    actual_prompts.append("=== CONCLUSIONS EXTRACTION PROMPT ===\n" + conclusion_analyzer.last_prompt)
                combined_prompt = "\n\n".join(actual_prompts) if actual_prompts else "No prompts captured"

                yield sse_msg({
                    'stage': 'COMPLETE',
                    'progress': 100,
                    'messages': [
                        f'Extraction complete!',
                        f'Questions: {len(questions)}',
                        f'Conclusions: {len(conclusions)}',
                        f'Links: {len(qc_links)}'
                    ],
                    'status_messages': status_messages,
                    'prompt': combined_prompt,
                    'raw_llm_response': results_text,
                    'result': {
                        'questions': len(questions),
                        'conclusions': len(conclusions),
                        'links': len(qc_links)
                    }
                })

            except Exception as e:
                logger.error(f"Error in streaming Q+C extraction for case {case_id}: {e}")
                import traceback
                traceback.print_exc()
                yield sse_msg({
                    'stage': 'ERROR',
                    'progress': 100,
                    'messages': [f'Error: {str(e)}'],
                    'error': True
                })

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )
