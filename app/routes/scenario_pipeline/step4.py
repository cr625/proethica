"""
Step 4: Whole-Case Synthesis

Analyzes analytical sections (Code Provisions, Questions, Conclusions) with
complete entity context after all 3 passes complete.

Three-Part Synthesis:
  Part A: Code Provisions (References section)
  Part B: Questions & Conclusions
  Part C: Cross-Section Synthesis
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.services.pipeline_status_service import PipelineStatusService
from app.utils.llm_utils import get_llm_client
from app.utils.environment_auth import auth_required_for_llm, auth_optional

# Import synthesis services
from app.services.nspe_references_parser import NSPEReferencesParser
from app.services.universal_provision_detector import UniversalProvisionDetector
from app.services.provision_grouper import ProvisionGrouper
from app.services.provision_group_validator import ProvisionGroupValidator
from app.services.code_provision_linker import CodeProvisionLinker
from app.services.question_analyzer import QuestionAnalyzer
from app.services.entity_grounding_service import EntityGroundingService
from app.services.conclusion_analyzer import ConclusionAnalyzer
from app.services.question_conclusion_linker import QuestionConclusionLinker
from app.services.case_synthesis_service import CaseSynthesisService
from app.services.unified_entity_resolver import get_unified_entity_lookup

# Import streaming synthesis
from app.routes.scenario_pipeline.step4_streaming import synthesize_case_streaming

# Import scenario generation
from app.routes.scenario_pipeline.generate_scenario import generate_scenario_from_case

# Import modular route registrations
from app.routes.scenario_pipeline.step4_questions import register_question_routes
from app.routes.scenario_pipeline.step4_conclusions import register_conclusion_routes
from app.routes.scenario_pipeline.step4_transformation import register_transformation_routes
from app.routes.scenario_pipeline.step4_rich_analysis import register_rich_analysis_routes
from app.routes.scenario_pipeline.step4_phase3 import register_phase3_routes
from app.routes.scenario_pipeline.step4_phase4 import register_phase4_routes
from app.routes.scenario_pipeline.step4_complete_synthesis import register_complete_synthesis_routes
from app.routes.scenario_pipeline.step4_run_all import register_run_all_routes

logger = logging.getLogger(__name__)

bp = Blueprint('step4', __name__, url_prefix='/scenario_pipeline')


def init_step4_csrf_exemption(app):
    """Exempt Step 4 synthesis routes from CSRF protection"""
    if hasattr(app, 'csrf') and app.csrf:
        from app.routes.scenario_pipeline.step4 import (
            save_streaming_results, generate_synthesis_annotations,
            extract_decision_points, generate_arguments, commit_step4_entities,
            synthesize_case, synthesize_complete,
            # Individual extraction endpoints still in step4.py
            extract_provisions_individual, extract_precedents_individual,
            extract_decision_synthesis_individual,
            extract_narrative_individual,
            # Streaming extraction endpoints still in step4.py
            extract_provisions_streaming, extract_precedents_streaming
        )
        from app.routes.scenario_pipeline.generate_scenario import generate_scenario_from_case
        app.csrf.exempt(save_streaming_results)
        app.csrf.exempt(generate_synthesis_annotations)
        app.csrf.exempt(generate_scenario_from_case)
        app.csrf.exempt(extract_decision_points)
        app.csrf.exempt(generate_arguments)
        app.csrf.exempt(commit_step4_entities)
        app.csrf.exempt(synthesize_case)
        app.csrf.exempt(synthesize_complete)
        # Individual extraction endpoints (in step4.py)
        app.csrf.exempt(extract_provisions_individual)
        app.csrf.exempt(extract_precedents_individual)
        app.csrf.exempt(extract_decision_synthesis_individual)
        app.csrf.exempt(extract_narrative_individual)
        # Streaming extraction endpoints (in step4.py)
        app.csrf.exempt(extract_provisions_streaming)
        app.csrf.exempt(extract_precedents_streaming)
        # Modular endpoints - exempt by view name
        app.csrf.exempt('step4.extract_questions_individual')
        app.csrf.exempt('step4.extract_questions_streaming')
        app.csrf.exempt('step4.extract_conclusions_individual')
        app.csrf.exempt('step4.extract_conclusions_streaming')
        app.csrf.exempt('step4.extract_transformation_individual')
        app.csrf.exempt('step4.extract_transformation_streaming')
        app.csrf.exempt('step4.extract_rich_analysis_individual')
        app.csrf.exempt('step4.extract_rich_analysis_streaming')
        # Phase 3 synthesis endpoints
        app.csrf.exempt('step4.synthesize_phase3_individual')
        app.csrf.exempt('step4.synthesize_phase3_streaming')
        # Phase 4 narrative construction endpoints
        app.csrf.exempt('step4.construct_phase4_individual')
        app.csrf.exempt('step4.construct_phase4_streaming')
        app.csrf.exempt('step4.get_phase4_data')
        # Complete synthesis streaming
        app.csrf.exempt('step4.synthesize_complete_streaming')
        # Non-streaming complete synthesis (run all)
        app.csrf.exempt(run_complete_synthesis_func)
        # Utility endpoints
        app.csrf.exempt('step4.clear_step4_data')


@bp.route('/case/<int:case_id>/step4')
def step4_synthesis(case_id):
    """
    Display Step 4 synthesis page.

    Shows entity summary from Passes 1-3 and synthesis status.
    If synthesis has been run, displays saved results.
    """
    import json

    try:
        case = Document.query.get_or_404(case_id)

        # Get entity counts from all passes
        entities_summary = get_entities_summary(case_id)

        # Check synthesis status
        synthesis_status = get_synthesis_status(case_id)

        # Load saved synthesis results if available
        saved_synthesis = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='whole_case_synthesis'
        ).order_by(ExtractionPrompt.created_at.desc()).first()

        # Load saved Phase 4 narrative construction results
        phase4_prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='phase4_narrative'
        ).order_by(ExtractionPrompt.created_at.desc()).first()

        phase4_data = None
        if phase4_prompt and phase4_prompt.raw_response:
            try:
                phase4_data = json.loads(phase4_prompt.raw_response)
            except (json.JSONDecodeError, TypeError):
                pass

        # Get pipeline status for navigation
        pipeline_status = PipelineStatusService.get_step_status(case_id)

        # Commit section data
        unpublished_count = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, is_published=False
        ).count()
        published_count = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, is_published=True
        ).count()
        class_count = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, is_published=False, storage_type='class'
        ).count()
        individual_count = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, is_published=False, storage_type='individual'
        ).count()

        return render_template(
            'scenarios/step4.html',
            case=case,
            entities_summary=entities_summary,
            synthesis_status=synthesis_status,
            saved_synthesis=saved_synthesis,
            phase4_data=phase4_data,
            current_step=4,
            prev_step_url=f"/scenario_pipeline/case/{case_id}/reconcile",
            next_step_url=None,
            next_step_name=None,
            pipeline_status=pipeline_status,
            unpublished_count=unpublished_count,
            published_count=published_count,
            class_count=class_count,
            individual_count=individual_count,
        )

    except Exception as e:
        logger.error(f"Error displaying Step 4 for case {case_id}: {e}")
        return str(e), 500


@bp.route('/case/<int:case_id>/clear_step4', methods=['POST'])
def clear_step4_data(case_id):
    """
    Clear all Step 4 extractions (Phase 2-4) while preserving Steps 1-3 entities.

    Clears from temporary_rdf_storage:
    - Code provisions (2A)
    - Ethical questions and conclusions (2B)
    - Arguments (2D)
    - Rich analysis data (causal links, question emergence, resolution patterns)
    - Decision points (Phase 3)
    - Timeline events (Phase 4)

    Clears from extraction_prompts:
    - All step_number=4 prompts
    """
    try:
        # Define extraction types to clear (Step 4 / Phase 2-4)
        extraction_types_to_clear = [
            # 2A: Provisions
            'code_provision_reference',
            # 2E: Precedent Cases
            'precedent_case_reference',
            # 2B: Questions & Conclusions
            'ethical_question',
            'ethical_conclusion',
            # 2D: Arguments
            'argument_generated',
            'argument_validation',
            # Rich Analysis (2D)
            'question_emergence',
            'resolution_pattern',
            'causal_normative_link',
            'rich_analysis_causal',
            'rich_analysis_qe',
            'rich_analysis_rp',
            # Phase 3: Decision Points
            'canonical_decision_point',
            'decision_point',
            'decision_option',
            # Phase 4: Narrative
            'transformation_analysis',
            'case_summary',
            'timeline_event',
            'narrative_element',
            'scenario_seed',
        ]

        deleted_counts = {}
        total_deleted = 0

        for extraction_type in extraction_types_to_clear:
            count = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type=extraction_type
            ).delete(synchronize_session=False)
            if count > 0:
                deleted_counts[extraction_type] = count
                total_deleted += count

        # Clear ALL Step 4 extraction prompts by step_number
        # This is more reliable than listing individual concept_types
        prompts_deleted = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            step_number=4
        ).delete(synchronize_session=False)

        # Clear Step 4-related fields from CasePrecedentFeatures
        # (transformation, principle tensions, obligation conflicts)
        from app.models import CasePrecedentFeatures
        features = CasePrecedentFeatures.query.filter_by(case_id=case_id).first()
        if features:
            features.transformation_type = None
            features.transformation_pattern = None
            features.principle_tensions = None
            features.obligation_conflicts = None

        # Clear Step 4 provenance data (LLM Interactions)
        from app.models.provenance import ProvenanceActivity, ProvenanceEntity, ProvenanceUsage, ProvenanceDerivation

        # Find all Step 4 activities for this case
        step4_activities = ProvenanceActivity.query.filter(
            ProvenanceActivity.case_id == case_id,
            ProvenanceActivity.activity_name.like('step4%')
        ).all()

        activity_ids = [a.id for a in step4_activities]
        provenance_deleted = 0

        if activity_ids:
            # Delete entities generated by these activities
            entities_deleted = ProvenanceEntity.query.filter(
                ProvenanceEntity.generating_activity_id.in_(activity_ids)
            ).delete(synchronize_session=False)
            provenance_deleted += entities_deleted

            # Delete usage records for these activities
            ProvenanceUsage.query.filter(
                ProvenanceUsage.activity_id.in_(activity_ids)
            ).delete(synchronize_session=False)

            # Delete the activities themselves
            activities_deleted = ProvenanceActivity.query.filter(
                ProvenanceActivity.id.in_(activity_ids)
            ).delete(synchronize_session=False)
            provenance_deleted += activities_deleted

        db.session.commit()

        logger.info(f"Cleared Step 4 data for case {case_id}: {total_deleted} entities, {prompts_deleted} prompts, {provenance_deleted} provenance records")

        return jsonify({
            'success': True,
            'message': f'Cleared {total_deleted} entities, {prompts_deleted} prompts, {provenance_deleted} provenance records',
            'deleted_counts': deleted_counts,
            'prompts_deleted': prompts_deleted,
            'provenance_deleted': provenance_deleted
        })

    except Exception as e:
        logger.error(f"Error clearing Step 4 for case {case_id}: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/case/<int:case_id>/synthesis_results')
def view_synthesis_results(case_id):
    """
    Display detailed synthesis results visualization.

    Shows:
    - Entity graph structure
    - Causal-normative links
    - Question emergence analysis
    - Resolution patterns
    """
    try:
        case = Document.query.get_or_404(case_id)

        # Load synthesis results from database
        synthesis_prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='whole_case_synthesis'
        ).order_by(ExtractionPrompt.created_at.desc()).first()

        if not synthesis_prompt:
            return render_template(
                'scenarios/synthesis_results.html',
                case=case,
                synthesis_data=None,
                error_message="No synthesis results found. Please run synthesis first.",
                current_step=4,
                prev_step_url=f"/scenario_pipeline/case/{case_id}/step4",
                next_step_url="#"
            )

        # Parse synthesis data
        import json
        synthesis_data = json.loads(synthesis_prompt.raw_response)

        # Load entity graph for displaying node details
        entity_graph_data = _load_entity_graph_details(case_id, synthesis_data)

        return render_template(
            'scenarios/synthesis_results.html',
            case=case,
            synthesis_data=synthesis_data,
            entity_graph_data=entity_graph_data,
            synthesis_timestamp=synthesis_prompt.created_at,
            results_summary=synthesis_prompt.results_summary,
            current_step=4,
            prev_step_url=f"/scenario_pipeline/case/{case_id}/step4",
            next_step_url="#"
        )

    except Exception as e:
        logger.error(f"Error viewing synthesis results for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return str(e), 500


def _load_entity_graph_details(case_id: int, synthesis_data: Dict) -> Dict:
    """
    Load detailed entity information for graph visualization

    Returns:
        Dict with entity details indexed by entity_id
    """
    entity_details = {}

    # Load all entities from database
    entities = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        storage_type='individual'
    ).all()

    for entity in entities:
        entity_id = f"{entity.entity_type}_{entity.id}"
        entity_details[entity_id] = {
            'id': entity_id,
            'type': entity.entity_type,
            'label': entity.entity_label,
            'definition': entity.entity_definition,
            'rdf_json_ld': entity.rdf_json_ld
        }

    return entity_details


@bp.route('/case/<int:case_id>/synthesize_streaming')
def synthesize_streaming(case_id):
    """
    Execute whole-case synthesis with Server-Sent Events streaming.

    Real-time progress updates showing:
    - Part A: Code Provisions extraction
    - Part B: Questions & Conclusions extraction
    - Part C: Cross-section synthesis
    - LLM prompts and responses for each stage
    """
    return synthesize_case_streaming(case_id)


@bp.route('/case/<int:case_id>/save_streaming_results', methods=['POST'])
@auth_required_for_llm
def save_streaming_results(case_id):
    """
    Save Step 4 streaming synthesis results to database.

    Called by frontend after SSE streaming completes to persist
    LLM prompts and responses for page refresh persistence.
    """
    from app.routes.scenario_pipeline.step4_streaming import save_step4_streaming_results
    return save_step4_streaming_results(case_id)


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
        import re
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


# ARCHIVED: Standalone Entity Graph view - functionality available in Step 4 Review page
# Template archived to: scenarios/archive/entity_graph.html
# @bp.route('/case/<int:case_id>/entity_graph/view')
# @auth_optional
# def view_entity_graph(case_id):
#     """Display full-page entity graph visualization."""
#     pass


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


def _classify_conclusion_type(text: str) -> str:
    """
    Classify conclusion type based on text content.

    Returns: 'ethical', 'unethical', 'mixed', or 'recommendation'
    """
    text_lower = text.lower()

    # Check for mixed/partial conclusions
    if 'partly ethical' in text_lower or 'partly unethical' in text_lower:
        return 'mixed'
    if 'was not unethical' in text_lower and 'was unethical' in text_lower:
        return 'mixed'

    # Check for clear ethical determination
    if 'was not unethical' in text_lower or 'was ethical' in text_lower:
        if 'was unethical' in text_lower and 'was not unethical' not in text_lower:
            return 'unethical'
        return 'ethical'

    if 'was unethical' in text_lower or 'violated' in text_lower:
        return 'unethical'

    # Check for recommendations
    if 'should' in text_lower or 'obligation to' in text_lower or 'no professional or ethical obligation' in text_lower:
        return 'recommendation'

    return 'unclear'


def _count_conclusion_types(conclusions: list) -> dict:
    """Count conclusions by type (from dict format)."""
    counts = {}
    for c in conclusions:
        t = c.get('type', 'unclear')
        counts[t] = counts.get(t, 0) + 1
    return counts


def _count_conclusion_types_from_list(conclusions: list) -> dict:
    """Count conclusions by type (handles both dicts and dataclass objects)."""
    counts = {}
    for c in conclusions:
        t = c.get('conclusion_type', 'unclear') if isinstance(c, dict) else getattr(c, 'conclusion_type', 'unclear')
        counts[t] = counts.get(t, 0) + 1
    return counts


# ARCHIVED: Standalone Q-C Flow view moved to Step 4 Review page
# Template archived to: scenarios/archive/qc_flow.html
# @bp.route('/case/<int:case_id>/qc_flow/view')
# @auth_optional
# def view_qc_flow(case_id):
#     """Display full-page Question-Conclusion flow visualization."""
#     pass


@bp.route('/case/<int:case_id>/step4/decision_points')
def step4_decision_points(case_id):
    """
    Display Step 4E: Decision Point Composition page.

    Shows E1-E3 pipeline for composing entity-grounded decision points
    from Role + Obligation/Constraint + ActionSet.
    """
    try:
        case = Document.query.get_or_404(case_id)

        # Get pipeline status for navigation
        pipeline_status = PipelineStatusService.get_step_status(case_id)

        return render_template(
            'scenarios/step4_decision_points.html',
            case=case,
            current_step=4,
            step_title='Step 4E: Decision Points',
            prev_step_url=f"/scenario_pipeline/case/{case_id}/step4",
            next_step_url=f"/scenario_pipeline/case/{case_id}/step4/arguments",
            next_step_name='Part F: Arguments',
            pipeline_status=pipeline_status
        )

    except Exception as e:
        logger.error(f"Error displaying Step 4E for case {case_id}: {e}")
        return str(e), 500


@bp.route('/case/<int:case_id>/step4/arguments')
def step4_arguments(case_id):
    """
    Redirect to Step 4 Synthesis page (arguments are now inline).

    Previously displayed Step 4F: Entity-Grounded Arguments as separate page.
    Now arguments generation is part of the main Step 4 Synthesis page.
    """
    return redirect(url_for('step4.step4_synthesis', case_id=case_id))


@bp.route('/case/<int:case_id>/step4/review')
def step4_review(case_id):
    """
    Display comprehensive Step 4 Review page with:
    - Code Provisions (NSPE references with excerpts)
    - Questions & Conclusions (with Q→C links)
    - Entity Graph (Interactive Cytoscape visualization)

    This page shows the synthesis results in a structured, reviewable format.
    """
    try:
        case = Document.query.get_or_404(case_id)

        # Get saved synthesis (optional - page can display with or without)
        saved_synthesis = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='whole_case_synthesis'
        ).order_by(ExtractionPrompt.created_at.desc()).first()

        # Get all entities for graph visualization
        all_entities_objs = _get_all_entities_for_graph(case_id)

        # Convert entities to JSON-serializable dicts
        all_entities = []
        for entity in all_entities_objs:
            all_entities.append({
                'id': entity.id,
                'entity_type': entity.entity_type,
                'entity_label': entity.entity_label,
                'entity_definition': entity.entity_definition,
                'entity_uri': entity.entity_uri,
                'rdf_json_ld': entity.rdf_json_ld or {}
            })

        # Get code provisions and convert to dicts (both committed and uncommitted)
        provisions_objs = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='code_provision_reference'
        ).all()

        provisions = []
        for p in provisions_objs:
            provisions.append({
                'id': p.id,
                'entity_type': p.entity_type,
                'entity_label': p.entity_label,
                'entity_definition': p.entity_definition,
                'entity_uri': p.entity_uri,
                'rdf_json_ld': p.rdf_json_ld or {}
            })

        # Get questions and convert to dicts (both committed and uncommitted)
        questions_objs = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_question'
        ).all()

        questions = []
        for q in questions_objs:
            questions.append({
                'id': q.id,
                'entity_type': q.entity_type,
                'entity_label': q.entity_label,
                'entity_definition': q.entity_definition,
                'entity_uri': q.entity_uri,
                'rdf_json_ld': q.rdf_json_ld or {}
            })

        # Get conclusions and convert to dicts (both committed and uncommitted)
        conclusions_objs = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_conclusion'
        ).all()

        conclusions = []
        for c in conclusions_objs:
            conclusions.append({
                'id': c.id,
                'entity_type': c.entity_type,
                'entity_label': c.entity_label,
                'entity_definition': c.entity_definition,
                'entity_uri': c.entity_uri,
                'rdf_json_ld': c.rdf_json_ld or {}
            })

        # Get precedent case references
        precedents_objs = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='precedent_case_reference'
        ).all()

        precedents_list = []
        for pr in precedents_objs:
            precedents_list.append({
                'id': pr.id,
                'entity_type': pr.entity_type,
                'entity_label': pr.entity_label,
                'entity_definition': pr.entity_definition,
                'entity_uri': pr.entity_uri,
                'rdf_json_ld': pr.rdf_json_ld or {}
            })

        # Sort questions and conclusions by type priority (board_explicit first)
        question_type_order = ['board_explicit', 'implicit', 'principle_tension', 'theoretical', 'counterfactual']
        conclusion_type_order = ['board_explicit', 'analytical_extension', 'question_response', 'principle_synthesis']

        def get_type_priority_dict(item, type_field, type_order):
            item_type = (item.get('rdf_json_ld') or {}).get(type_field, 'unknown')
            try:
                return type_order.index(item_type)
            except ValueError:
                return len(type_order)  # Unknown types go last

        def get_type_priority_obj(obj, type_field, type_order):
            item_type = (obj.rdf_json_ld or {}).get(type_field, 'unknown')
            try:
                return type_order.index(item_type)
            except ValueError:
                return len(type_order)  # Unknown types go last

        # Sort both dict lists and SQLAlchemy object lists
        questions = sorted(questions, key=lambda q: get_type_priority_dict(q, 'questionType', question_type_order))
        conclusions = sorted(conclusions, key=lambda c: get_type_priority_dict(c, 'conclusionType', conclusion_type_order))
        questions_objs = sorted(questions_objs, key=lambda q: get_type_priority_obj(q, 'questionType', question_type_order))
        conclusions_objs = sorted(conclusions_objs, key=lambda c: get_type_priority_obj(c, 'conclusionType', conclusion_type_order))

        # Check if synthesis annotations already exist
        from app.models.document_concept_annotation import DocumentConceptAnnotation
        from sqlalchemy import func

        existing_annotations = DocumentConceptAnnotation.query.filter_by(
            document_type='case',
            document_id=case_id,
            ontology_name='step4_synthesis',
            is_current=True
        ).all()

        # Get annotation breakdown by type
        annotation_counts = {}
        for ann in existing_annotations:
            concept_type = ann.concept_type
            annotation_counts[concept_type] = annotation_counts.get(concept_type, 0) + 1

        # Get transformation classification from precedent features
        transformation_data = None
        precedent_features = None
        try:
            from sqlalchemy import text
            result = db.session.execute(
                text("""
                    SELECT transformation_type, transformation_pattern,
                           outcome_type, outcome_confidence, outcome_reasoning,
                           provisions_cited, subject_tags,
                           principle_tensions, obligation_conflicts,
                           features_version, extracted_at
                    FROM case_precedent_features
                    WHERE case_id = :case_id
                """),
                {'case_id': case_id}
            ).fetchone()
            if result:
                transformation_data = {
                    'type': result[0],
                    'pattern': result[1]
                }
                precedent_features = {
                    'transformation_type': result[0],
                    'transformation_pattern': result[1],
                    'outcome_type': result[2],
                    'outcome_confidence': result[3],
                    'outcome_reasoning': result[4],
                    'provisions_cited': result[5] or [],
                    'subject_tags': result[6] or [],
                    'principle_tensions': result[7] or [],
                    'obligation_conflicts': result[8] or [],
                    'features_version': result[9],
                    'extracted_at': result[10]
                }
        except Exception as e:
            logger.debug(f"No transformation data found for case {case_id}: {e}")

        # Build comprehensive data inventory for downstream services
        # Count entities by type from Passes 1-3
        entity_type_counts = {}
        for entity in all_entities:
            etype = entity.get('entity_type', 'unknown')
            entity_type_counts[etype] = entity_type_counts.get(etype, 0) + 1

        data_inventory = {
            # Source data (Passes 1-3)
            'passes_1_3': {
                'total_entities': len(all_entities),
                'by_type': entity_type_counts,
                'available': len(all_entities) > 0
            },
            # Step 4 Synthesis outputs
            'step4_synthesis': {
                'provisions': len(provisions),
                'questions': len(questions),
                'conclusions': len(conclusions),
                'annotations': len(existing_annotations),
                'available': len(provisions) > 0 or len(questions) > 0
            },
            # Precedent Discovery features
            'precedent_features': {
                'has_features': precedent_features is not None,
                'outcome_type': precedent_features.get('outcome_type') if precedent_features else None,
                'transformation_type': precedent_features.get('transformation_type') if precedent_features else None,
                'provisions_count': len(precedent_features.get('provisions_cited', [])) if precedent_features else 0,
                'subject_tags_count': len(precedent_features.get('subject_tags', [])) if precedent_features else 0,
                'has_principle_tensions': bool(precedent_features.get('principle_tensions')) if precedent_features else False,
                'has_obligation_conflicts': bool(precedent_features.get('obligation_conflicts')) if precedent_features else False,
                'has_embeddings': False  # Updated dynamically below
            },
            # What's needed for scenario generation
            'scenario_ready': {
                'has_roles': entity_type_counts.get('roles', 0) > 0,
                'has_actions': entity_type_counts.get('actions', 0) > 0,
                'has_events': entity_type_counts.get('events', 0) > 0,
                'has_states': entity_type_counts.get('states', 0) > 0,
                'has_questions': len(questions) > 0,
                'has_conclusions': len(conclusions) > 0
            }
        }

        # Check if case has section embeddings
        try:
            from app.models import DocumentSection
            embedding_count = DocumentSection.query.filter(
                DocumentSection.document_id == case_id,
                DocumentSection.embedding.isnot(None)
            ).count()
            data_inventory['precedent_features']['has_embeddings'] = embedding_count > 0
        except Exception as e:
            logger.debug(f"Could not check embeddings for case {case_id}: {e}")

        # Get publish status
        unpublished_count = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            is_published=False
        ).count()

        published_count = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            is_published=True
        ).count()

        # Load rich analysis data
        rich_analysis = None
        causal_links_objs = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='causal_normative_link'
        ).all()
        question_emergence_objs = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='question_emergence'
        ).all()
        resolution_pattern_objs = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='resolution_pattern'
        ).all()

        if causal_links_objs or question_emergence_objs or resolution_pattern_objs:
            rich_analysis = {
                'causal_links': [
                    {
                        'action_label': obj.rdf_json_ld.get('action_label', obj.entity_label),
                        'fulfills_obligations': obj.rdf_json_ld.get('fulfills_obligations', []),
                        'violates_obligations': obj.rdf_json_ld.get('violates_obligations', []),
                        'reasoning': obj.entity_definition
                    }
                    for obj in causal_links_objs
                ],
                'question_emergence': [
                    {
                        'question_text': obj.rdf_json_ld.get('question_text', obj.entity_label),
                        'data_events': obj.rdf_json_ld.get('data_events', []),
                        'data_actions': obj.rdf_json_ld.get('data_actions', []),
                        'competing_warrants': obj.rdf_json_ld.get('competing_warrants', [])
                    }
                    for obj in question_emergence_objs
                ],
                'resolution_patterns': [
                    {
                        'conclusion_text': obj.rdf_json_ld.get('conclusion_text', obj.entity_label),
                        'determinative_principles': obj.rdf_json_ld.get('determinative_principles', []),
                        'determinative_facts': obj.rdf_json_ld.get('determinative_facts', [])
                    }
                    for obj in resolution_pattern_objs
                ]
            }

        # Get pipeline status for publish validation
        pipeline_status = PipelineStatusService.get_step_status(case_id)
        can_publish = pipeline_status.get('step1', {}).get('complete', False) and unpublished_count > 0

        # Build entity lookup dict for ontology label popovers (includes OntServe base classes)
        from app.services.unified_entity_resolver import UnifiedEntityResolver
        resolver = UnifiedEntityResolver(case_id=case_id)
        entity_lookup = resolver.get_lookup_dict()
        entity_lookup_by_label = resolver.get_label_index()

        # Check for validation study mode (from session or query param)
        validation_study_mode = (
            session.get('validation_study_mode') or
            request.args.get('validation_mode') == '1'
        )
        # Also set session flag if query param present (for persistence)
        if request.args.get('validation_mode') == '1':
            session['validation_study_mode'] = True

        context = {
            'case': case,
            'saved_synthesis': saved_synthesis,
            'provisions': provisions_objs,  # Original objects for template iteration
            'provisions_json': provisions,  # JSON-serializable for graph
            'questions': questions_objs,
            'questions_json': questions,
            'conclusions': conclusions_objs,
            'conclusions_json': conclusions,
            'all_entities': all_entities,
            'entity_count': len(all_entities),
            'provision_count': len(provisions),
            'precedents': precedents_objs,
            'precedents_json': precedents_list,
            'precedent_count': len(precedents_list),
            'question_count': len(questions),
            'conclusion_count': len(conclusions),
            'has_synthesis_annotations': len(existing_annotations) > 0,
            'annotation_count': len(existing_annotations),
            'annotation_breakdown': annotation_counts,
            'transformation_data': transformation_data,
            'precedent_features': precedent_features,
            'data_inventory': data_inventory,
            'entity_type_counts': entity_type_counts,
            # Publish status
            'unpublished_count': unpublished_count,
            'published_count': published_count,
            'can_publish': can_publish,
            'pipeline_status': pipeline_status,
            # Pipeline navigation (required by base_step.html)
            'current_step': 4,
            'step_title': 'Synthesis Review',
            'prev_step_url': url_for('step4.step4_synthesis', case_id=case_id),
            'next_step_url': None,
            'next_step_name': None,
            'rich_analysis': rich_analysis,
            'decision_points': _load_decision_points_for_review(case_id),
            'narrative_data': _load_narrative_for_review(case_id),
            # Entity lookup for ontology label macro
            'entity_lookup': entity_lookup,
            'entity_lookup_by_label': entity_lookup_by_label,
            # Validation study mode (for demo panel visibility)
            'validation_study_mode': validation_study_mode
        }

        return render_template('scenario_pipeline/step4_review.html', **context)

    except Exception as e:
        logger.error(f"Error displaying Step 4 review for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return str(e), 500


def _load_decision_points_for_review(case_id: int) -> List[Dict]:
    """Load canonical decision points for the review page with their arguments."""
    decision_points = []
    dp_objs = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='canonical_decision_point'
    ).order_by(TemporaryRDFStorage.created_at).all()

    # Load arguments and validations
    arg_objs = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='argument_generated'
    ).all()
    val_objs = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='argument_validation'
    ).all()

    # Build validation lookup
    validations = {}
    for v in val_objs:
        if v.rdf_json_ld:
            validations[v.rdf_json_ld.get('argument_id')] = v.rdf_json_ld

    # Group arguments by decision point (including all DPs in decision_point_ids array)
    args_by_dp = {}
    for arg in arg_objs:
        if arg.rdf_json_ld:
            arg_data = arg.rdf_json_ld.copy()
            # Attach validation if available
            arg_id = arg_data.get('argument_id')
            if arg_id and arg_id in validations:
                arg_data['validation'] = validations[arg_id]

            # Get all decision point IDs this argument belongs to
            dp_ids = arg.rdf_json_ld.get('decision_point_ids', [])
            if not dp_ids:
                # Fallback to singular decision_point_id
                primary_dp = arg.rdf_json_ld.get('decision_point_id', '')
                if primary_dp:
                    dp_ids = [primary_dp]

            # Add argument to each decision point it belongs to
            for dp_id in dp_ids:
                if dp_id not in args_by_dp:
                    args_by_dp[dp_id] = []
                args_by_dp[dp_id].append(arg_data)

    for obj in dp_objs:
        if obj.rdf_json_ld:
            data = obj.rdf_json_ld
            focus_id = data.get('focus_id', '')
            decision_points.append({
                'focus_id': focus_id,
                'focus_number': data.get('focus_number', 0),
                'description': data.get('description', obj.entity_label),
                'decision_question': data.get('decision_question', obj.entity_definition),
                'entity_label': obj.entity_label,
                'entity_definition': obj.entity_definition,
                'obligation_label': data.get('obligation_label', ''),
                'obligations_in_tension': data.get('obligations_in_tension', []),
                'options': data.get('options', []),
                'qc_alignment_score': data.get('qc_alignment_score', 0),
                'source': data.get('source', 'algorithmic'),
                'arguments': args_by_dp.get(focus_id, [])
            })

    return decision_points


def _load_narrative_for_review(case_id: int) -> Optional[Dict]:
    """Load Phase 4 narrative data for the review page."""
    try:
        phase4_prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='phase4_narrative'
        ).order_by(ExtractionPrompt.created_at.desc()).first()

        if phase4_prompt and phase4_prompt.raw_response:
            import json
            data = json.loads(phase4_prompt.raw_response)

            # Extract narrative_elements
            ne = data.get('narrative_elements', {})
            characters = ne.get('characters', []) if isinstance(ne, dict) else []
            conflicts = ne.get('conflicts', []) if isinstance(ne, dict) else []
            decision_moments = ne.get('decision_moments', []) if isinstance(ne, dict) else []

            # Extract timeline
            tl = data.get('timeline', {})
            events = tl.get('events', []) if isinstance(tl, dict) else (tl if isinstance(tl, list) else [])
            initial_fluents = tl.get('initial_fluents', []) if isinstance(tl, dict) else []
            causal_links = tl.get('causal_links', []) if isinstance(tl, dict) else []
            event_trace = tl.get('event_trace', '') if isinstance(tl, dict) else ''

            # Extract scenario_seeds
            seeds = data.get('scenario_seeds', {})
            opening_context = seeds.get('opening_context', '') if isinstance(seeds, dict) else ''
            protagonist = seeds.get('protagonist_label', '') if isinstance(seeds, dict) else ''

            # Extract insights
            insights = data.get('insights', {})
            key_takeaways = insights.get('key_takeaways', []) if isinstance(insights, dict) else []
            patterns = insights.get('patterns', []) if isinstance(insights, dict) else []

            return {
                'has_data': True,
                'timestamp': phase4_prompt.created_at.isoformat() if phase4_prompt.created_at else None,
                # Narrative elements
                'characters': characters,
                'conflicts': conflicts,
                'decision_moments': decision_moments,
                # Timeline
                'events': events,
                'initial_fluents': initial_fluents,
                'causal_links': causal_links,
                'event_trace': event_trace,
                # Scenario seeds
                'opening_context': opening_context,
                'protagonist': protagonist,
                # Insights
                'key_takeaways': key_takeaways,
                'patterns': patterns,
                # Summary for counts
                'summary': data.get('summary', {})
            }
    except Exception as e:
        logger.debug(f"Could not load narrative for case {case_id}: {e}")

    return {'has_data': False}


def _get_all_entities_for_graph(case_id: int) -> List:
    """
    Get all extracted entities from Passes 1-4 for graph visualization.
    Returns list of entity objects for D3/Cytoscape rendering (both committed and uncommitted).
    """
    # Include all entity types shown in the entity graph (matches entity_graph API)
    extraction_types = [
        'roles', 'states', 'resources',  # Pass 1
        'principles', 'obligations', 'constraints', 'capabilities',  # Pass 2
        'temporal_dynamics_enhanced',  # Pass 3 (all temporal entities)
        'code_provision_reference', 'ethical_question', 'ethical_conclusion',  # Step 4 core
        'causal_normative_link', 'question_emergence', 'resolution_pattern',  # Step 4 rich analysis
        'canonical_decision_point',  # Step 4 decision points
        'precedent_case_reference'  # Step 6 precedent discovery
    ]

    all_entities = []
    # Query by extraction_type to get relevant entities
    entities = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        TemporaryRDFStorage.extraction_type.in_(extraction_types),
        TemporaryRDFStorage.storage_type == 'individual'
    ).all()
    all_entities.extend(entities)

    return all_entities


def _build_entity_lookup_dict(case_id: int) -> Dict[str, Dict]:
    """
    Build a lookup dictionary mapping entity URIs to their metadata.

    DEPRECATED: Use get_unified_entity_lookup() from unified_entity_resolver instead.
    This function is kept for backwards compatibility.

    Args:
        case_id: The case ID to load entities for

    Returns:
        Dict mapping entity_uri -> entity metadata
    """
    return get_unified_entity_lookup(case_id)


@bp.route('/case/<int:case_id>/step4/generate_synthesis_annotations', methods=['POST'])
@auth_required_for_llm
def generate_synthesis_annotations(case_id):
    """
    Generate synthesis annotations for Step 4 artifacts.

    Creates annotations showing:
    - Where questions appear in Questions section
    - Where conclusions appear in Conclusions section
    - Where provisions are cited throughout the case
    - Where synthesis entities are mentioned in Facts/Discussion

    This makes the synthesis reviewable by highlighting evidence in context.
    """
    try:
        from app.services.synthesis_annotation_service import SynthesisAnnotationService

        logger.info(f"Generating synthesis annotations for case {case_id}")

        service = SynthesisAnnotationService(case_id)
        counts = service.generate_all_synthesis_annotations()

        flash(f"Generated {counts['total']} synthesis annotations: {counts['questions']} questions, {counts['conclusions']} conclusions, {counts['provisions']} provisions, {counts['entity_mentions']} entity mentions", 'success')

        return jsonify({
            'success': True,
            'counts': counts,
            'message': f"Successfully generated {counts['total']} synthesis annotations"
        })

    except Exception as e:
        logger.error(f"Error generating synthesis annotations for case {case_id}: {e}")
        import traceback
        traceback.print_exc()

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_entities_summary(case_id: int) -> Dict:
    """
    Get summary of all extracted entities from Passes 1-3.

    Returns:
        Dict with entity counts by type (includes both committed and uncommitted)
    """
    from sqlalchemy import func

    # Use case-insensitive queries with func.lower()
    # Count ALL entities regardless of commit status for synthesis display
    summary = {}

    # Pass 1 - Count all entities (committed or not)
    summary['roles'] = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        func.lower(TemporaryRDFStorage.entity_type) == 'roles',
        TemporaryRDFStorage.storage_type == 'individual'
    ).count()

    summary['states'] = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        func.lower(TemporaryRDFStorage.entity_type) == 'states',
        TemporaryRDFStorage.storage_type == 'individual'
    ).count()

    summary['resources'] = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        func.lower(TemporaryRDFStorage.entity_type) == 'resources',
        TemporaryRDFStorage.storage_type == 'individual'
    ).count()

    # Pass 2 - Count all entities (committed or not)
    summary['principles'] = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        func.lower(TemporaryRDFStorage.entity_type) == 'principles',
        TemporaryRDFStorage.storage_type == 'individual'
    ).count()

    summary['obligations'] = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        func.lower(TemporaryRDFStorage.entity_type) == 'obligations',
        TemporaryRDFStorage.storage_type == 'individual'
    ).count()

    summary['constraints'] = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        func.lower(TemporaryRDFStorage.entity_type) == 'constraints',
        TemporaryRDFStorage.storage_type == 'individual'
    ).count()

    summary['capabilities'] = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        func.lower(TemporaryRDFStorage.entity_type) == 'capabilities',
        TemporaryRDFStorage.storage_type == 'individual'
    ).count()

    # Pass 3 - Handle combined Actions_events or separate actions/events
    actions_events_count = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        func.lower(TemporaryRDFStorage.entity_type) == 'actions_events',
        TemporaryRDFStorage.storage_type == 'individual'
    ).count()

    actions_only = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        func.lower(TemporaryRDFStorage.entity_type) == 'actions',
        TemporaryRDFStorage.storage_type == 'individual'
    ).count()

    events_only = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        func.lower(TemporaryRDFStorage.entity_type) == 'events',
        TemporaryRDFStorage.storage_type == 'individual'
    ).count()

    # If combined, split evenly for display (or query individually)
    if actions_events_count > 0 and actions_only == 0 and events_only == 0:
        summary['actions'] = actions_events_count  # Show all as actions
        summary['events'] = 0  # Combined format
    else:
        summary['actions'] = actions_only
        summary['events'] = events_only

    # Calculate totals
    summary['pass1_total'] = sum([
        summary['roles'],
        summary['states'],
        summary['resources']
    ])
    summary['pass2_total'] = sum([
        summary['principles'],
        summary['obligations'],
        summary['constraints'],
        summary['capabilities']
    ])
    summary['pass3_total'] = sum([
        summary['actions'],
        summary['events']
    ])
    summary['total'] = summary['pass1_total'] + summary['pass2_total'] + summary['pass3_total']

    return summary


def get_synthesis_status(case_id: int) -> Dict:
    """
    Check if synthesis has been completed for this case.

    Returns:
        Dict with synthesis status and results
    """
    # Check for code provisions
    provisions = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='code_provision_reference'
    ).count()

    # Check for questions
    questions = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='ethical_question'
    ).count()

    # Check for conclusions
    conclusions = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='ethical_conclusion'
    ).count()

    # Check for precedent case references
    precedents = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='precedent_case_reference'
    ).count()

    completed = provisions > 0 or questions > 0 or conclusions > 0

    # Get transformation type from case_precedent_features
    from app.models import CasePrecedentFeatures
    transformation_type = None
    features = CasePrecedentFeatures.query.filter_by(case_id=case_id).first()
    if features and features.transformation_type:
        transformation_type = features.transformation_type

    return {
        'completed': completed,
        'provisions_count': provisions,
        'questions_count': questions,
        'conclusions_count': conclusions,
        'precedents_count': precedents,
        'transformation_type': transformation_type
    }


def get_all_case_entities(case_id: int) -> Dict[str, List]:
    """
    Query ALL extracted entities from Passes 1-3.

    Returns:
        Dict with entities by type (lowercase keys):
        {
            'roles': [...],
            'states': [...],
            ...
        }

    Note: Database stores entity_type with capitalized names (Roles, States, etc.)
    but we return lowercase keys for consistency with analyzers.
    """
    # Map lowercase keys to database capitalization
    entity_type_map = {
        'roles': 'Roles',
        'states': 'States',
        'resources': 'Resources',
        'principles': 'Principles',
        'obligations': 'Obligations',
        'constraints': 'Constraints',
        'capabilities': 'Capabilities',
        'actions': 'actions',  # lowercase in DB
        'events': 'events'     # lowercase in DB
    }

    entities = {}
    for key, db_type in entity_type_map.items():
        entities[key] = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            entity_type=db_type,
            storage_type='individual'
        ).all()

    total_count = sum(len(v) for v in entities.values())
    logger.info(f"Loaded entities for case {case_id}: {total_count} total")

    return entities


# Register modular routes
# These modules handle question and conclusion extraction with entity grounding
register_question_routes(bp, get_all_case_entities)
register_conclusion_routes(bp, get_all_case_entities)
register_transformation_routes(bp, get_all_case_entities)
register_rich_analysis_routes(bp, get_all_case_entities)


def load_phase2_data(case_id: int) -> Dict:
    """
    Load Phase 2 data needed for Phase 3 synthesis.

    Returns:
        Dict containing:
        - questions: List of ethical questions
        - conclusions: List of board conclusions
        - question_emergence: List of Toulmin question emergence analyses
        - resolution_patterns: List of resolution pattern analyses
    """
    # Load questions
    questions_raw = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='ethical_question'
    ).all()

    questions = [
        {
            'uri': q.entity_uri or f"case-{case_id}#Q{i+1}",
            'label': q.entity_label,
            'text': q.entity_definition or q.entity_label,
            'mentioned_entities': q.rdf_json_ld.get('mentionedEntities', []) if q.rdf_json_ld else [],
            'related_provisions': q.rdf_json_ld.get('relatedProvisions', []) if q.rdf_json_ld else []
        }
        for i, q in enumerate(questions_raw)
    ]

    # Load conclusions
    conclusions_raw = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='ethical_conclusion'
    ).all()

    conclusions = [
        {
            'uri': c.entity_uri or f"case-{case_id}#C{i+1}",
            'label': c.entity_label,
            'text': c.entity_definition or c.entity_label,
            'cited_provisions': c.rdf_json_ld.get('citedProvisions', []) if c.rdf_json_ld else [],
            'cited_actions': c.rdf_json_ld.get('citedActions', []) if c.rdf_json_ld else [],
            'answers_questions': c.rdf_json_ld.get('answersQuestions', []) if c.rdf_json_ld else []
        }
        for i, c in enumerate(conclusions_raw)
    ]

    # Load question emergence (Toulmin analysis)
    qe_raw = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='question_emergence'
    ).all()

    question_emergence = []
    for qe in qe_raw:
        if qe.rdf_json_ld:
            question_emergence.append(qe.rdf_json_ld)
        else:
            question_emergence.append({
                'question_uri': qe.entity_uri or '',
                'question_text': qe.entity_definition or '',
                'competing_warrants': [],
                'data_events': [],
                'data_actions': [],
                'involves_roles': []
            })

    # Load resolution patterns
    rp_raw = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='resolution_pattern'
    ).all()

    resolution_patterns = []
    for rp in rp_raw:
        if rp.rdf_json_ld:
            resolution_patterns.append(rp.rdf_json_ld)
        else:
            resolution_patterns.append({
                'conclusion_uri': rp.entity_uri or '',
                'conclusion_text': rp.entity_definition or '',
                'determinative_principles': [],
                'resolution_narrative': ''
            })

    logger.info(f"Loaded Phase 2 data for case {case_id}: {len(questions)} Q, {len(conclusions)} C, {len(question_emergence)} QE, {len(resolution_patterns)} RP")

    return {
        'questions': questions,
        'conclusions': conclusions,
        'question_emergence': question_emergence,
        'resolution_patterns': resolution_patterns
    }


# Register Phase 3 routes
register_phase3_routes(bp, get_all_case_entities, load_phase2_data)


# ============================================================================
# PHASE 4: NARRATIVE CONSTRUCTION HELPER FUNCTIONS
# ============================================================================

def build_entity_foundation_for_phase4(case_id: int):
    """Build EntityFoundation for Phase 4 narrative construction."""
    from app.services.case_synthesizer import CaseSynthesizer
    synthesizer = CaseSynthesizer()
    return synthesizer._build_entity_foundation(case_id)


def load_canonical_points_for_phase4(case_id: int) -> List:
    """Load canonical decision points from Phase 3."""
    from app.services.decision_point_synthesizer import CanonicalDecisionPoint

    canonical_raw = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='canonical_decision_point'
    ).all()

    points = []
    for raw in canonical_raw:
        if raw.rdf_json_ld:
            data = raw.rdf_json_ld
            points.append(CanonicalDecisionPoint(
                focus_id=data.get('focus_id', ''),
                focus_number=data.get('focus_number', 0),
                description=data.get('description', ''),
                decision_question=data.get('decision_question', ''),
                role_uri=data.get('role_uri', ''),
                role_label=data.get('role_label', ''),
                obligation_uri=data.get('obligation_uri'),
                obligation_label=data.get('obligation_label'),
                constraint_uri=data.get('constraint_uri'),
                constraint_label=data.get('constraint_label'),
                involved_action_uris=data.get('involved_action_uris', []),
                provision_uris=data.get('provision_uris', []),
                provision_labels=data.get('provision_labels', []),
                options=data.get('options', []),
                intensity_score=data.get('intensity_score', 0.0),
                qc_alignment_score=data.get('qc_alignment_score', 0.0)
            ))

    return points


def load_conclusions_for_phase4(case_id: int) -> List[Dict]:
    """Load conclusions for Phase 4 including mentioned_entities from extraction prompts."""
    import json
    import re

    # Load from RDF storage
    conclusions_raw = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='ethical_conclusion'
    ).all()

    # Also load mentioned_entities from extraction prompts
    mentioned_entities_map = {}
    try:
        from app.models import ExtractionPrompt
        prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='ethical_conclusion'
        ).order_by(ExtractionPrompt.created_at.desc()).first()

        if prompt and prompt.raw_response:
            raw = prompt.raw_response
            # Remove markdown code blocks if present
            raw = re.sub(r'^```json\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw)
            data = json.loads(raw)

            # Build map from conclusion labels to mentioned_entities
            for category in data.values():
                if isinstance(category, list):
                    for c in category:
                        label = c.get('conclusion_text', '')[:50]
                        if c.get('mentioned_entities'):
                            mentioned_entities_map[label] = c.get('mentioned_entities', {})
    except Exception as e:
        logger.debug(f"Could not load mentioned_entities for conclusions: {e}")

    results = []
    for i, c in enumerate(conclusions_raw):
        # Try to match with mentioned_entities by label prefix
        mentioned = {}
        label = c.entity_label or ''
        definition = c.entity_definition or ''
        for key in mentioned_entities_map:
            if key in definition or key in label:
                mentioned = mentioned_entities_map[key]
                break

        results.append({
            'uri': c.entity_uri or f"case-{case_id}#C{i+1}",
            'label': c.entity_label,
            'text': c.entity_definition or c.entity_label,
            'cited_provisions': c.rdf_json_ld.get('citedProvisions', []) if c.rdf_json_ld else [],
            'mentioned_entities': mentioned
        })

    return results


def get_transformation_type_for_phase4(case_id: int) -> Optional[str]:
    """Get transformation classification for Phase 4."""
    from app.models import CasePrecedentFeatures

    # Try to get from case_precedent_features table
    try:
        features = CasePrecedentFeatures.query.filter_by(case_id=case_id).first()
        if features and features.transformation_type:
            return features.transformation_type
    except Exception:
        pass  # Table may not exist or other error

    # Fall back to extraction in temporary_rdf_storage
    trans_raw = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='transformation_analysis'
    ).first()

    if trans_raw and trans_raw.rdf_json_ld:
        return trans_raw.rdf_json_ld.get('transformation_type', 'unknown')

    return None


def load_causal_links_for_phase4(case_id: int) -> List[Dict]:
    """Load causal-normative links for Phase 4."""
    links_raw = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='causal_normative_link'
    ).all()

    return [
        link.rdf_json_ld if link.rdf_json_ld else {
            'action_uri': link.entity_uri or '',
            'action_label': link.entity_label,
            'obligation_uri': '',
            'obligation_label': ''
        }
        for link in links_raw
    ]


# Register Phase 4 routes
register_phase4_routes(
    bp,
    build_entity_foundation_for_phase4,
    load_canonical_points_for_phase4,
    load_conclusions_for_phase4,
    get_transformation_type_for_phase4,
    load_causal_links_for_phase4
)

# Register Complete Synthesis streaming routes
register_complete_synthesis_routes(
    bp,
    build_entity_foundation_for_phase4,
    load_canonical_points_for_phase4,
    load_conclusions_for_phase4,
    get_transformation_type_for_phase4,
    load_causal_links_for_phase4
)

# Register Run All (non-streaming complete synthesis)
_run_all_funcs = register_run_all_routes(bp, get_all_case_entities)
run_complete_synthesis_func = _run_all_funcs['run_complete_synthesis']


# ============================================================================
# PART A: CODE PROVISIONS
# ============================================================================

def extract_and_link_provisions(case_id: int, case: Document) -> List[Dict]:
    """
    Part A: Extract code provisions and link to all entity types.

    Returns:
        List of provision dicts with excerpts and entity links
    """
    logger.info(f"Part A: Starting code provision extraction for case {case_id}")

    # Get references section HTML
    references_html = None
    if case.doc_metadata and 'sections_dual' in case.doc_metadata:
        for section_key, section_content in case.doc_metadata['sections_dual'].items():
            if 'reference' in section_key.lower():
                if isinstance(section_content, dict):
                    references_html = section_content.get('html', '')
                break

    if not references_html:
        logger.warning(f"No references section found for case {case_id}")
        return []

    # Parse HTML to extract provisions
    parser = NSPEReferencesParser()
    provisions = parser.parse_references_html(references_html)

    if not provisions:
        logger.warning(f"No provisions parsed for case {case_id}")
        return []

    logger.info(f"Parsed {len(provisions)} provisions")

    # Get ALL entities (9 types)
    all_entities = get_all_case_entities(case_id)

    # Prepare case sections for mention detection
    case_sections = {}
    if case.doc_metadata and 'sections_dual' in case.doc_metadata:
        sections = case.doc_metadata['sections_dual']
        for section_key in ['facts', 'discussion', 'question', 'conclusion']:
            if section_key in sections:
                section_data = sections[section_key]
                if isinstance(section_data, dict):
                    case_sections[section_key] = section_data.get('text', '')
                else:
                    case_sections[section_key] = str(section_data)

    # Stage 1: Universal detection
    detector = UniversalProvisionDetector()
    all_mentions = detector.detect_all_provisions(case_sections)

    logger.info(f"Detected {len(all_mentions)} provision mentions")

    # Stage 2: Group by provision
    grouper = ProvisionGrouper()
    grouped_mentions = grouper.group_mentions_by_provision(
        all_mentions,
        provisions
    )

    # Stage 3: Validate with LLM
    llm_client = get_llm_client()
    validator = ProvisionGroupValidator(llm_client)

    for provision in provisions:
        code = provision['code_provision']
        mentions = grouped_mentions.get(code, [])

        if not mentions:
            provision['relevant_excerpts'] = []
            continue

        validated = validator.validate_group(
            code,
            provision['provision_text'],
            mentions
        )

        provision['relevant_excerpts'] = [
            {
                'section': v.section,
                'text': v.excerpt,
                'matched_citation': v.citation_text,
                'mention_type': v.content_type,
                'confidence': v.confidence,
                'validation_reasoning': v.reasoning
            }
            for v in validated
        ]

    # Link to entities (ALL 9 types)
    linker = CodeProvisionLinker(llm_client)

    # Format entities for linker
    def format_entities(entity_list):
        return [
            {
                'label': e.entity_label,
                'definition': e.entity_definition
            }
            for e in entity_list
        ]

    linked_provisions = linker.link_provisions_to_entities(
        provisions,
        roles=format_entities(all_entities['roles']),
        states=format_entities(all_entities['states']),
        resources=format_entities(all_entities['resources']),
        principles=format_entities(all_entities['principles']),
        obligations=format_entities(all_entities['obligations']),
        constraints=format_entities(all_entities['constraints']),
        capabilities=format_entities(all_entities['capabilities']),
        actions=format_entities(all_entities['actions']),
        events=format_entities(all_entities['events']),
        case_text_summary=f"Case {case_id}: {case.title}"
    )

    # Store provisions
    session_id = str(uuid.uuid4())

    # Clear old provisions
    TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='code_provision_reference'
    ).delete(synchronize_session=False)

    # Save extraction prompt
    extraction_prompt = ExtractionPrompt(
        case_id=case_id,
        concept_type='code_provision_reference',
        step_number=4,
        section_type='references',
        prompt_text=linker.last_linking_prompt or 'Code provision extraction',
        llm_model='claude-opus-4-20250514',
        extraction_session_id=session_id,
        raw_response=linker.last_linking_response or '',
        results_summary={
            'total_provisions': len(linked_provisions),
            'total_excerpts': sum(len(p.get('relevant_excerpts', [])) for p in linked_provisions)
        },
        is_active=True,
        times_used=1,
        created_at=datetime.utcnow(),
        last_used_at=datetime.utcnow()
    )
    db.session.add(extraction_prompt)

    # Store provisions
    for provision in linked_provisions:
        label = f"NSPE_{provision['code_provision'].replace('.', '_')}"

        rdf_entity = TemporaryRDFStorage(
            case_id=case_id,
            extraction_session_id=session_id,
            extraction_type='code_provision_reference',
            storage_type='individual',
            entity_type='resources',
            entity_label=label,
            entity_definition=provision['provision_text'],
            rdf_json_ld={
                '@type': 'proeth-case:CodeProvisionReference',
                'label': label,
                'codeProvision': provision['code_provision'],
                'provisionText': provision['provision_text'],
                'subjectReferences': provision.get('subject_references', []),
                'appliesTo': provision.get('applies_to', []),
                'relevantExcerpts': provision.get('relevant_excerpts', []),
                'providedBy': 'NSPE Board of Ethical Review',
                'authoritative': True
            },
            is_selected=True
        )
        db.session.add(rdf_entity)

    db.session.commit()

    logger.info(f"Part A complete: Stored {len(linked_provisions)} code provisions")

    return linked_provisions


# ============================================================================
# PART B: QUESTIONS & CONCLUSIONS
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

    # Link Q→C
    linker = QuestionConclusionLinker(llm_client)
    qc_links = linker.link_questions_to_conclusions(questions, conclusions)

    logger.info(f"Created {len(qc_links)} Q→C links")

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
            llm_model='claude-opus-4-20250514',
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
            llm_model='claude-opus-4-20250514',
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


# ============================================================================
# PART C: CROSS-SECTION SYNTHESIS
# ============================================================================

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


def _store_synthesis_results(case_id: int, synthesis) -> None:
    """
    Store synthesis results for later viewing

    Creates a special extraction prompt entry with synthesis results.
    """
    import json
    import uuid
    from datetime import datetime

    session_id = str(uuid.uuid4())

    # Serialize synthesis results
    synthesis_data = {
        'entity_graph': {
            'total_nodes': len(synthesis.entity_graph.nodes),
            'by_type': {k: len(v) for k, v in synthesis.entity_graph.by_type.items()},
            'by_section': {k: len(v) for k, v in synthesis.entity_graph.by_section.items()}
        },
        'causal_normative_links': [
            {
                'action_id': link.action_id,
                'action_label': link.action_label,
                'fulfills_obligations': link.fulfills_obligations,
                'violates_obligations': link.violates_obligations,
                'guided_by_principles': link.guided_by_principles,
                'constrained_by': link.constrained_by,
                'enabled_by_capabilities': link.enabled_by_capabilities,
                'agent_role': link.agent_role,
                'agent_state': link.agent_state,
                'used_resources': link.used_resources,
                'reasoning': link.reasoning,
                'confidence': link.confidence
            }
            for link in synthesis.causal_normative_links
        ],
        'question_emergence': [
            {
                'question_id': qe.question_id,
                'question_text': qe.question_text,
                'question_number': qe.question_number,
                'triggered_by_events': qe.triggered_by_events,
                'triggered_by_actions': qe.triggered_by_actions,
                'involves_states': qe.involves_states,
                'involves_roles': qe.involves_roles,
                'competing_obligations': qe.competing_obligations,
                'competing_principles': qe.competing_principles,
                'emergence_narrative': qe.emergence_narrative,
                'confidence': qe.confidence
            }
            for qe in synthesis.question_emergence
        ],
        'resolution_patterns': [
            {
                'conclusion_id': rp.conclusion_id,
                'conclusion_text': rp.conclusion_text,
                'conclusion_number': rp.conclusion_number,
                'answers_questions': rp.answers_questions,
                'determinative_principles': rp.determinative_principles,
                'determinative_facts': rp.determinative_facts,
                'cited_provisions': rp.cited_provisions,
                'pattern_type': rp.pattern_type,
                'resolution_narrative': rp.resolution_narrative,
                'confidence': rp.confidence
            }
            for rp in synthesis.resolution_patterns
        ]
    }

    # Delete old synthesis results
    ExtractionPrompt.query.filter_by(
        case_id=case_id,
        concept_type='whole_case_synthesis'
    ).delete(synchronize_session=False)

    # Store as extraction prompt
    extraction_prompt = ExtractionPrompt(
        case_id=case_id,
        concept_type='whole_case_synthesis',
        step_number=4,
        section_type='synthesis',
        prompt_text='Whole-case synthesis integrating all passes',
        llm_model='case_synthesis_service',
        extraction_session_id=session_id,
        raw_response=json.dumps(synthesis_data, indent=2),
        results_summary={
            'total_nodes': synthesis.total_nodes,
            'total_links': len(synthesis.causal_normative_links),
            'questions_analyzed': len(synthesis.question_emergence),
            'patterns_extracted': len(synthesis.resolution_patterns)
        },
        is_active=True,
        times_used=1,
        created_at=datetime.utcnow(),
        last_used_at=datetime.utcnow()
    )

    db.session.add(extraction_prompt)
    db.session.commit()

    logger.info(f"Stored synthesis results for case {case_id}")


# ============================================================================
# PART E: DECISION POINT EXTRACTION
# ============================================================================

@bp.route('/case/<int:case_id>/decision_points')
def get_decision_points(case_id):
    """
    API endpoint returning decision points for a case.

    Returns JSON with extracted decision points including:
    - Decision points with options
    - Involved roles and provisions
    - Board resolution and reasoning
    """
    try:
        from app.services.decision_focus_extractor import DecisionFocusExtractor

        extractor = DecisionFocusExtractor()
        points = extractor.load_from_database(case_id)

        # Convert to JSON-serializable format
        points_data = []
        for point in points:
            points_data.append({
                'point_id': point.focus_id,
                'point_number': point.focus_number,
                'description': point.description,
                'decision_question': point.decision_question,
                'involved_roles': point.involved_roles,
                'applicable_provisions': point.applicable_provisions,
                'options': [
                    {
                        'option_id': opt.option_id,
                        'description': opt.description,
                        'is_board_choice': opt.is_board_choice
                    }
                    for opt in point.options
                ],
                'board_resolution': point.board_resolution,
                'board_reasoning': point.board_reasoning,
                'confidence': point.confidence
            })

        return jsonify({
            'success': True,
            'case_id': case_id,
            'decision_points': points_data,
            'count': len(points_data)
        })

    except Exception as e:
        logger.error(f"Error getting decision points for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'decision_points': []
        }), 500


@bp.route('/case/<int:case_id>/extract_decision_points', methods=['POST'])
@auth_required_for_llm
def extract_decision_points(case_id):
    """
    Extract decision points from a case using LLM.

    Part E of Step 4 synthesis - identifies key decision points
    where ethical choices must be made.
    """
    try:
        from app.services.decision_focus_extractor import DecisionFocusExtractor

        case = Document.query.get_or_404(case_id)

        logger.info(f"Extracting decision points for case {case_id}")

        extractor = DecisionFocusExtractor()
        points = extractor.extract_decision_focuses(case_id)

        if points:
            # Save to database
            extractor.save_to_database(case_id, points)

            logger.info(f"Extracted and saved {len(points)} decision points for case {case_id}")

            # Return the decision points
            points_data = []
            for point in points:
                points_data.append({
                    'point_id': point.focus_id,
                    'point_number': point.focus_number,
                    'description': point.description,
                    'decision_question': point.decision_question,
                    'involved_roles': point.involved_roles,
                    'applicable_provisions': point.applicable_provisions,
                    'options': [
                        {
                            'option_id': opt.option_id,
                            'description': opt.description,
                            'is_board_choice': opt.is_board_choice
                        }
                        for opt in point.options
                    ],
                    'board_resolution': point.board_resolution,
                    'board_reasoning': point.board_reasoning,
                    'confidence': point.confidence
                })

            return jsonify({
                'success': True,
                'message': f'Extracted {len(points)} decision points',
                'decision_points': points_data,
                'count': len(points)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No decision points extracted',
                'decision_points': []
            }), 400

    except Exception as e:
        logger.error(f"Error extracting decision points for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/case/<int:case_id>/arguments', methods=['GET'])
def get_arguments(case_id):
    """
    Load existing arguments for a case.

    Part F of Step 4 synthesis - pros/cons for decision options.
    """
    try:
        from app.services.argument_generator import ArgumentGenerator

        generator = ArgumentGenerator()
        arguments = generator.load_from_database(case_id)

        if arguments:
            args_data = []
            for dp_args in arguments:
                args_data.append({
                    'decision_point_id': dp_args.decision_point_id,
                    'decision_description': dp_args.decision_description,
                    'option_id': dp_args.option_id,
                    'option_description': dp_args.option_description,
                    'pro_arguments': [
                        {
                            'argument_id': arg.argument_id,
                            'claim': arg.claim,
                            'provision_citations': arg.provision_citations,
                            'precedent_references': arg.precedent_references,
                            'strength': arg.strength
                        }
                        for arg in dp_args.pro_arguments
                    ],
                    'con_arguments': [
                        {
                            'argument_id': arg.argument_id,
                            'claim': arg.claim,
                            'provision_citations': arg.provision_citations,
                            'precedent_references': arg.precedent_references,
                            'strength': arg.strength
                        }
                        for arg in dp_args.con_arguments
                    ],
                    'evaluation_summary': dp_args.evaluation_summary
                })

            return jsonify({
                'success': True,
                'arguments': args_data,
                'count': len(args_data)
            })
        else:
            return jsonify({
                'success': True,
                'arguments': [],
                'count': 0,
                'message': 'No arguments found. Run "Generate Arguments" first.'
            })

    except Exception as e:
        logger.error(f"Error loading arguments for case {case_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/case/<int:case_id>/generate_arguments', methods=['POST'])
@auth_required_for_llm
def generate_arguments(case_id):
    """
    Generate pro/con arguments for decision points.

    Part F of Step 4 synthesis - creates balanced arguments for each
    decision option, citing code provisions and precedent cases.
    """
    try:
        from app.services.argument_generator import ArgumentGenerator

        case = Document.query.get_or_404(case_id)

        logger.info(f"Generating arguments for case {case_id}")

        generator = ArgumentGenerator()
        arguments = generator.generate_arguments(case_id)

        if arguments:
            # Save to database
            generator.save_to_database(case_id, arguments)

            # Count total arguments
            total_pro = sum(len(a.pro_arguments) for a in arguments)
            total_con = sum(len(a.con_arguments) for a in arguments)

            logger.info(f"Generated {total_pro} pro and {total_con} con arguments for case {case_id}")

            # Return the arguments
            args_data = []
            for dp_args in arguments:
                args_data.append({
                    'decision_point_id': dp_args.decision_point_id,
                    'decision_description': dp_args.decision_description,
                    'option_id': dp_args.option_id,
                    'option_description': dp_args.option_description,
                    'pro_arguments': [
                        {
                            'argument_id': arg.argument_id,
                            'claim': arg.claim,
                            'provision_citations': arg.provision_citations,
                            'precedent_references': arg.precedent_references,
                            'strength': arg.strength
                        }
                        for arg in dp_args.pro_arguments
                    ],
                    'con_arguments': [
                        {
                            'argument_id': arg.argument_id,
                            'claim': arg.claim,
                            'provision_citations': arg.provision_citations,
                            'precedent_references': arg.precedent_references,
                            'strength': arg.strength
                        }
                        for arg in dp_args.con_arguments
                    ],
                    'evaluation_summary': dp_args.evaluation_summary
                })

            return jsonify({
                'success': True,
                'message': f'Generated {total_pro} pro and {total_con} con arguments',
                'arguments': args_data,
                'pro_count': total_pro,
                'con_count': total_con
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No arguments generated. Ensure decision points are extracted first.',
                'arguments': []
            }), 400

    except Exception as e:
        logger.error(f"Error generating arguments for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/case/<int:case_id>/commit_step4', methods=['POST'])
@auth_required_for_llm
def commit_step4_entities(case_id):
    """
    Commit Step 4 entities (decision points) to OntServe.

    Uses AutoCommitService to link and commit entities from
    temporary_rdf_storage to the case TTL file.
    """
    try:
        from app.services.auto_commit_service import AutoCommitService

        case = Document.query.get_or_404(case_id)

        logger.info(f"Committing Step 4 entities for case {case_id}")

        auto_commit_service = AutoCommitService()
        result = auto_commit_service.commit_case_entities(case_id, force=False)

        if result:
            return jsonify({
                'success': True,
                'message': f'Committed {result.total_entities} entities ({result.linked_count} linked, {result.new_class_count} new)',
                'total_entities': result.total_entities,
                'linked_count': result.linked_count,
                'new_class_count': result.new_class_count,
                'ttl_file': result.ttl_file
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No entities to commit or commit failed'
            }), 400

    except Exception as e:
        logger.error(f"Error committing Step 4 entities for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# STEP 4 PROMPTS API
# ============================================================================

@bp.route('/case/<int:case_id>/step4_prompts')
def get_step4_prompts(case_id):
    """
    API endpoint returning Step 4 extraction prompts for provenance display.

    Returns prompts for each substep:
    - code_provision_reference (4a)
    - ethical_question (4b)
    - ethical_conclusion (4c)
    - whole_case_synthesis (4d - combined)
    - decision_point (4e)
    - decision_argument (4f)
    """
    try:
        prompts_data = {}
        concept_types = [
            'code_provision_reference',
            'ethical_question',
            'ethical_conclusion',
            'transformation_classification',
            'rich_analysis',
            'phase3_decision_synthesis',
            'phase4_narrative',
            'whole_case_synthesis',
            'decision_point',
            'decision_argument'
        ]

        for concept_type in concept_types:
            prompt = ExtractionPrompt.query.filter_by(
                case_id=case_id,
                concept_type=concept_type,
                step_number=4
            ).order_by(ExtractionPrompt.created_at.desc()).first()

            if prompt:
                prompts_data[concept_type] = {
                    'id': prompt.id,
                    'concept_type': prompt.concept_type,
                    'section_type': prompt.section_type,
                    'prompt_text': prompt.prompt_text,
                    'raw_response': prompt.raw_response,
                    'llm_model': prompt.llm_model,
                    'created_at': prompt.created_at.isoformat() if prompt.created_at else None,
                    'results_summary': prompt.results_summary,
                    'extraction_session_id': prompt.extraction_session_id
                }

        return jsonify({
            'success': True,
            'case_id': case_id,
            'prompts': prompts_data,
            'available_types': list(prompts_data.keys())
        })

    except Exception as e:
        logger.error(f"Error getting Step 4 prompts for case {case_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'prompts': {}
        }), 500


@bp.route('/case/<int:case_id>/pipeline_state')
def get_pipeline_state_api(case_id):
    """
    Get pipeline state for a case.

    Returns complete state including:
    - Step completion status
    - Task completion within each step
    - Prerequisites met/missing for each task
    - Artifact counts by type

    NeMo Migration: This endpoint can be replaced with nemo.workflows.get_run_state()

    Usage:
        fetch('/scenario_pipeline/case/7/pipeline_state')
            .then(r => r.json())
            .then(state => {
                if (state.steps.step4.tasks.questions.can_start) {
                    enableButton('extractQuestionsBtn');
                }
            });
    """
    try:
        from app.services.pipeline_state_manager import get_pipeline_state

        state = get_pipeline_state(case_id)
        return jsonify({
            'success': True,
            **state.to_dict()
        })

    except Exception as e:
        logger.error(f"Error getting pipeline state for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# ENTITY-GROUNDED ARGUMENTS (F1-F3 Pipeline)
# ============================================================================

@bp.route('/case/<int:case_id>/entity_arguments')
def get_entity_grounded_arguments(case_id):
    """
    Get entity-grounded Toulmin-structured arguments for a case.

    Runs the full E1-F3 pipeline:
    - E1: Obligation coverage analysis
    - E2: Action-option mapping with Jones intensity
    - E3: Decision point composition
    - F1: Principle-provision alignment
    - F2: Argument generation (Toulmin structure)
    - F3: Argument validation (3-tier)

    Returns JSON with arguments, decision points, and validation results.
    """
    try:
        from app.services.entity_analysis import (
            compose_decision_points,
            get_principle_provision_alignment,
            ArgumentGenerator,
            ArgumentValidator
        )
        from app.services.entity_analysis.argument_generator import load_canonical_decision_points
        from app.domains import get_domain_config
        from app.models import TemporaryRDFStorage, ExtractionPrompt

        logger.info(f"Running E1-F3 pipeline for case {case_id}")

        # Run pipeline
        domain_config = get_domain_config('engineering')

        # Use canonical decision points if available, otherwise compose fresh
        decision_points = load_canonical_decision_points(case_id)
        if decision_points is None:
            logger.info(f"No canonical decision points found, composing from entities")
            decision_points = compose_decision_points(case_id)
        else:
            logger.info(f"Using {len(decision_points.decision_points)} canonical decision points")

        alignment_map = get_principle_provision_alignment(case_id)

        # Use class methods to pass decision_points and alignment_map
        generator = ArgumentGenerator(domain_config)
        arguments = generator.generate_arguments(case_id, decision_points, alignment_map)

        validator = ArgumentValidator(domain_config)
        validation = validator.validate_arguments(case_id, arguments)

        # Build response
        response_data = {
            'success': True,
            'case_id': case_id,
            'pipeline_summary': {
                'decision_points_count': len(decision_points.decision_points),
                'alignment_rate': alignment_map.alignment_rate,
                'total_arguments': len(arguments.arguments),
                'pro_arguments': arguments.pro_argument_count,
                'con_arguments': arguments.con_argument_count,
                'valid_arguments': validation.valid_arguments,
                'invalid_arguments': validation.invalid_arguments,
                'average_score': validation.average_score
            },
            'decision_points': [
                {
                    'focus_id': dp.focus_id,
                    'description': dp.description,
                    'decision_question': dp.decision_question,
                    'role_label': dp.grounding.role_label,
                    'obligation_label': dp.grounding.obligation_label,
                    'constraint_label': dp.grounding.constraint_label,
                    'intensity_score': dp.intensity_score,
                    'options': [
                        {
                            'option_id': opt.option_id,
                            'action_label': opt.action_label,
                            'description': opt.description,
                            'is_extracted': opt.is_extracted_action
                        }
                        for opt in dp.options
                    ],
                    'board_conclusion': dp.board_conclusion_text
                }
                for dp in decision_points.decision_points
            ],
            'arguments': [arg.to_dict() for arg in arguments.arguments],
            'validations': [v.to_dict() for v in validation.validations],
            'validation_summary': {
                'entity_test_pass_rate': validation.entity_test_pass_rate,
                'founding_test_pass_rate': validation.founding_test_pass_rate,
                'virtue_test_pass_rate': validation.virtue_test_pass_rate
            }
        }

        # Persist results to database
        import uuid
        from datetime import datetime

        session_id = str(uuid.uuid4())

        # Clear previous arguments and validations for this case
        TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='argument_generated'
        ).delete()
        TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='argument_validation'
        ).delete()

        # Save each argument to temporary storage
        for arg in arguments.arguments:
            rdf_entity = TemporaryRDFStorage(
                case_id=case_id,
                extraction_session_id=session_id,
                extraction_type='argument_generated',
                storage_type='individual',
                entity_type='Argument',
                entity_label=arg.argument_id,
                entity_definition=arg.claim.text if arg.claim else '',
                entity_uri=f"case-{case_id}#{arg.argument_id}",
                rdf_json_ld=arg.to_dict(),
                is_selected=True
            )
            db.session.add(rdf_entity)

        # Save validations
        for val in validation.validations:
            rdf_entity = TemporaryRDFStorage(
                case_id=case_id,
                extraction_session_id=session_id,
                extraction_type='argument_validation',
                storage_type='individual',
                entity_type='ArgumentValidation',
                entity_label=f"val_{val.argument_id}",
                entity_definition=f"Valid: {val.is_valid}, Score: {val.validation_score:.2f}",
                entity_uri=f"case-{case_id}#val_{val.argument_id}",
                rdf_json_ld=val.to_dict(),
                is_selected=True
            )
            db.session.add(rdf_entity)

        # Record the pipeline run
        pipeline_record = ExtractionPrompt(
            case_id=case_id,
            concept_type='entity_arguments',
            step_number=4,
            section_type='synthesis',
            extraction_session_id=session_id,
            prompt_text='E1-F3 algorithmic pipeline (no LLM)',
            llm_model='algorithmic',
            raw_response=f'Generated {len(arguments.arguments)} arguments, {validation.valid_arguments} valid',
            created_at=datetime.utcnow()
        )
        db.session.add(pipeline_record)
        db.session.commit()

        logger.info(
            f"E1-F3 pipeline complete for case {case_id}: "
            f"{len(arguments.arguments)} arguments, {validation.valid_arguments} valid (persisted)"
        )

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error running E1-F3 pipeline for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'arguments': [],
            'decision_points': []
        }), 500


@bp.route('/case/<int:case_id>/llm_decision_points')
def get_llm_decision_points(case_id):
    """
    Get LLM-extracted decision points from Step 4 Synthesis.

    These are the quality decision points extracted by LLM, not algorithmic composition.
    """
    try:
        from app.models import TemporaryRDFStorage, ExtractionPrompt

        # Load decision points extracted by LLM
        decision_point_entities = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='decision_point'
        ).all()

        # Load options for these decision points
        option_entities = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='decision_option'
        ).all()

        # Get the extraction prompt for provenance
        extraction_prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='decision_point',
            section_type='synthesis'
        ).order_by(ExtractionPrompt.created_at.desc()).first()

        # Build response
        decision_points = []
        for dp in decision_point_entities:
            json_ld = dp.rdf_json_ld or {}

            # Find options for this decision point
            dp_options = []
            dp_label = dp.entity_label
            for opt in option_entities:
                opt_json = opt.rdf_json_ld or {}
                opt_for = opt_json.get('optionFor', '') or opt.entity_definition or ''
                # Match options to decision points by text similarity
                if dp_label.lower() in opt_for.lower() or any(
                    word in opt_for.lower() for word in dp_label.lower().split()[:5]
                ):
                    dp_options.append({
                        'option_id': f"O{len(dp_options)+1}",
                        'label': opt.entity_label,
                        'description': opt.entity_definition,
                        'is_extracted': True,
                        'json_ld': opt_json
                    })

            decision_points.append({
                'id': dp.id,
                'focus_id': f"DP{len(decision_points)+1}",
                'label': dp.entity_label,
                'description': dp.entity_definition,
                'decision_question': dp.entity_label,  # The label IS the question
                'options': dp_options,
                'json_ld': json_ld,
                'is_selected': dp.is_selected
            })

        return jsonify({
            'success': True,
            'case_id': case_id,
            'source': 'llm_extraction',
            'count': len(decision_points),
            'decision_points': decision_points,
            'extraction_info': {
                'model': extraction_prompt.llm_model if extraction_prompt else None,
                'created_at': extraction_prompt.created_at.isoformat() if extraction_prompt else None,
                'prompt_preview': (extraction_prompt.prompt_text[:200] + '...') if extraction_prompt and extraction_prompt.prompt_text else None
            }
        })

    except Exception as e:
        logger.error(f"Error loading LLM decision points for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'decision_points': []
        }), 500


@bp.route('/case/<int:case_id>/entity_arguments/decision_points')
def get_composed_decision_points(case_id):
    """
    Get algorithmically composed decision points (E1-E3 pipeline).

    Alternative to LLM extraction - composes from extracted entities.
    Useful for entity grounding analysis.
    """
    try:
        from app.services.entity_analysis import compose_decision_points
        from app.models import TemporaryRDFStorage, ExtractionPrompt
        import uuid
        from datetime import datetime

        decision_points = compose_decision_points(case_id)

        # Persist the composed decision points
        session_id = str(uuid.uuid4())

        # Clear any previous E1-E3 composed decision points for this case
        TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='decision_point_composed'
        ).delete()

        # Save each decision point to temporary storage
        for dp in decision_points.decision_points:
            rdf_entity = TemporaryRDFStorage(
                case_id=case_id,
                extraction_session_id=session_id,
                extraction_type='decision_point_composed',
                storage_type='individual',
                entity_type='DecisionPoint',
                entity_label=dp.focus_id,
                entity_definition=dp.description,
                entity_uri=f"case-{case_id}#{dp.focus_id}",
                rdf_json_ld={
                    '@type': 'proethica-int:DecisionPoint',
                    'focus_id': dp.focus_id,
                    'focus_number': dp.focus_number,
                    'description': dp.description,
                    'decision_question': dp.decision_question,
                    'intensity_score': dp.intensity_score,
                    'grounding': dp.grounding.to_dict(),
                    'options': [opt.to_dict() for opt in dp.options],
                    'provision_uris': dp.provision_uris,
                    'provision_labels': dp.provision_labels,
                    'board_conclusion_text': dp.board_conclusion_text
                },
                is_selected=True
            )
            db.session.add(rdf_entity)

        # Record the composition run (no LLM prompt, but track metadata)
        composition_record = ExtractionPrompt(
            case_id=case_id,
            concept_type='decision_point_composed',
            step_number=4,
            section_type='synthesis',
            extraction_session_id=session_id,
            prompt_text='E1-E3 algorithmic composition (no LLM)',
            llm_model='algorithmic',
            raw_response=f'Composed {len(decision_points.decision_points)} decision points',
            created_at=datetime.utcnow()
        )
        db.session.add(composition_record)
        db.session.commit()

        logger.info(f"Persisted {len(decision_points.decision_points)} composed decision points for case {case_id}")

        return jsonify({
            'success': True,
            'case_id': case_id,
            'count': len(decision_points.decision_points),
            'unmatched_obligations': decision_points.unmatched_obligations,
            'unmatched_actions': decision_points.unmatched_actions,
            'decision_points': [
                {
                    'focus_id': dp.focus_id,
                    'description': dp.description,
                    'decision_question': dp.decision_question,
                    'intensity_score': dp.intensity_score,
                    'grounding': {
                        'role_uri': dp.grounding.role_uri,
                        'role_label': dp.grounding.role_label,
                        'obligation_uri': dp.grounding.obligation_uri,
                        'obligation_label': dp.grounding.obligation_label,
                        'constraint_uri': dp.grounding.constraint_uri,
                        'constraint_label': dp.grounding.constraint_label
                    },
                    'options': [
                        {
                            'option_id': opt.option_id,
                            'action_uri': opt.action_uri,
                            'action_label': opt.action_label,
                            'description': opt.description,
                            'is_extracted': opt.is_extracted_action,
                            'downstream_event_uris': opt.downstream_event_uris
                        }
                        for opt in dp.options
                    ],
                    'provision_uris': dp.provision_uris,
                    'provision_labels': dp.provision_labels,
                    'board_conclusion': dp.board_conclusion_text
                }
                for dp in decision_points.decision_points
            ]
        })

    except Exception as e:
        logger.error(f"Error getting composed decision points for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'decision_points': []
        }), 500


@bp.route('/case/<int:case_id>/entity_arguments/alignment')
def get_principle_alignment(case_id):
    """
    Get principle-provision alignment map (F1 only).

    Returns alignment between principles and code provisions.
    """
    try:
        from app.services.entity_analysis import get_principle_provision_alignment

        alignment_map = get_principle_provision_alignment(case_id)

        return jsonify({
            'success': True,
            'case_id': case_id,
            'total_principles': alignment_map.total_principles,
            'total_provisions': alignment_map.total_provisions,
            'alignment_rate': alignment_map.alignment_rate,
            'unaligned_principles': alignment_map.unaligned_principles,
            'unaligned_provisions': alignment_map.unaligned_provisions,
            'alignments': [a.to_dict() for a in alignment_map.alignments]
        })

    except Exception as e:
        logger.error(f"Error getting principle alignment for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'alignments': []
        }), 500


@bp.route('/case/<int:case_id>/entity_arguments/coverage')
def get_obligation_coverage_api(case_id):
    """
    Get obligation/constraint coverage analysis (E1 only).

    Returns coverage matrix, conflicts, and role-obligation bindings.
    """
    try:
        from app.services.entity_analysis import get_obligation_coverage as e1_coverage

        coverage = e1_coverage(case_id)

        return jsonify({
            'success': True,
            'case_id': case_id,
            'obligations': [
                {
                    'uri': o.entity_uri,
                    'label': o.entity_label,
                    'definition': o.entity_definition,
                    'role_uri': o.bound_role_uri,
                    'role_label': o.bound_role,
                    'decision_type': o.decision_type,
                    'provisions': o.related_provisions,
                    'is_decision_relevant': o.decision_relevant,
                    'is_instantiated': o.is_instantiated
                }
                for o in coverage.obligations
            ],
            'constraints': [
                {
                    'uri': c.entity_uri,
                    'label': c.entity_label,
                    'definition': c.entity_definition,
                    'role_uri': c.constrained_role_uri,
                    'role_label': c.constrained_role,
                    'founding_value_limit': c.founding_value_limit,
                    'is_instantiated': c.is_instantiated
                }
                for c in coverage.constraints
            ],
            'conflict_pairs': coverage.conflict_pairs,
            'role_obligation_map': coverage.role_obligation_map,
            'decision_relevant_count': coverage.decision_relevant_count
        })

    except Exception as e:
        logger.error(f"Error getting obligation coverage for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Scenario Generation Route
@bp.route("/case/<int:case_id>/generate_scenario")
def generate_scenario_route(case_id):
    """
    SSE endpoint for scenario generation.

    Streams progress through all 9 stages of scenario generation.
    """
    return generate_scenario_from_case(case_id)


# =============================================================================
# UNIFIED SYNTHESIS PIPELINE
# =============================================================================

@bp.route('/case/<int:case_id>/synthesize', methods=['POST'])
@auth_required_for_llm
def synthesize_case(case_id):
    """
    Execute unified case synthesis pipeline.

    Replaces fragmented Part E (LLM) / Part F (algorithmic) approaches
    with single coherent pipeline producing canonical decision points.

    Pipeline:
    1. Load ALL extracted entities (Passes 1-3 + Parts A-D)
    2. Run E1-E3 algorithmic composition for candidates
    3. Use LLM to refine with Q&C as ground truth
    4. Produce canonical decision points
    5. Generate arguments using F1-F3 (optional)

    Reference: docs-internal/UNIFIED_CASE_ANALYSIS_PIPELINE.md
    """
    try:
        from app.services.case_synthesizer import CaseSynthesizer

        case = Document.query.get_or_404(case_id)

        # Check if arguments should be generated
        generate_args = request.args.get('generate_arguments', 'true').lower() == 'true'

        logger.info(f"Starting unified synthesis for case {case_id} (generate_arguments={generate_args})")

        synthesizer = CaseSynthesizer()
        result = synthesizer.synthesize(case_id, generate_arguments=generate_args)

        logger.info(
            f"Synthesis complete: {len(result.canonical_decision_points)} canonical points, "
            f"{result.qc_aligned_count} Q&C aligned"
        )

        return jsonify({
            'success': True,
            'case_id': case_id,
            'message': f'Synthesized {len(result.canonical_decision_points)} canonical decision points',
            'canonical_decision_points': [dp.to_dict() for dp in result.canonical_decision_points],
            'count': len(result.canonical_decision_points),
            'algorithmic_candidates_count': result.algorithmic_candidates_count,
            'qc_aligned_count': result.qc_aligned_count,
            'has_arguments': result.arguments is not None,
            'extraction_session_id': result.extraction_session_id
        })

    except Exception as e:
        logger.error(f"Error in unified synthesis for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/case/<int:case_id>/canonical_decision_points')
def get_canonical_decision_points(case_id):
    """
    Load canonical decision points from the unified pipeline.

    Returns decision points that were produced by the synthesize endpoint,
    which combines algorithmic composition with LLM refinement.
    """
    try:
        from app.services.case_synthesizer import CaseSynthesizer

        synthesizer = CaseSynthesizer()
        canonical_points = synthesizer.load_canonical_points(case_id)

        if canonical_points:
            return jsonify({
                'success': True,
                'case_id': case_id,
                'canonical_decision_points': [dp.to_dict() for dp in canonical_points],
                'count': len(canonical_points),
                'qc_aligned_count': sum(1 for dp in canonical_points if dp.aligned_question_uri),
                'source': 'unified_synthesis'
            })
        else:
            return jsonify({
                'success': True,
                'case_id': case_id,
                'canonical_decision_points': [],
                'count': 0,
                'message': 'No canonical decision points found. Run "Synthesize" first.'
            })

    except Exception as e:
        logger.error(f"Error loading canonical decision points for case {case_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'canonical_decision_points': []
        }), 500


# =============================================================================
# COMPLETE CASE SYNTHESIS (FOUR PHASES)
# =============================================================================

@bp.route('/case/<int:case_id>/entity_foundation')
def get_entity_foundation(case_id):
    """
    Get entity foundation (Phase 1) without running full synthesis.

    Returns all entities from Passes 1-3 organized for display.
    """
    try:
        from app.services.case_synthesizer import CaseSynthesizer

        synthesizer = CaseSynthesizer()
        foundation = synthesizer._build_entity_foundation(case_id)

        return jsonify({
            'success': True,
            'case_id': case_id,
            'entity_foundation': foundation.to_dict()
        })

    except Exception as e:
        logger.error(f"Error getting entity foundation for case {case_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/case/<int:case_id>/synthesize_complete', methods=['POST'])
@auth_required_for_llm
def synthesize_complete(case_id):
    """
    Execute complete four-phase synthesis.

    Phases:
    1. Entity Foundation - gather all entities from Passes 1-3
    2. Analytical Extraction - load provisions, Q&C, transformation type
    3. Decision Point Synthesis - E1-E3 composition + LLM refinement
    4. Narrative Construction - build timeline and scenario seeds

    Returns complete CaseSynthesisModel.
    """
    try:
        from app.services.case_synthesizer import CaseSynthesizer

        case = Document.query.get_or_404(case_id)

        # Check if LLM synthesis should be skipped (for testing)
        skip_llm = request.args.get('skip_llm', 'false').lower() == 'true'

        logger.info(f"Starting complete synthesis for case {case_id} (skip_llm={skip_llm})")

        synthesizer = CaseSynthesizer()
        model = synthesizer.synthesize_complete(case_id, skip_llm_synthesis=skip_llm)

        logger.info(f"Complete synthesis done: {model.summary()}")

        return jsonify({
            'success': True,
            'case_id': case_id,
            'case_title': model.case_title,
            'synthesis': model.to_dict(),
            'summary': model.summary()
        })

    except Exception as e:
        logger.error(f"Error in complete synthesis for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/case/<int:case_id>/synthesis_model')
def get_synthesis_model(case_id):
    """
    Load existing synthesis model from database.

    Returns the stored synthesis results without re-running.
    Includes rich analysis if previously generated.
    """
    try:
        from app.services.case_synthesizer import (
            CaseSynthesizer, CaseSynthesisModel, EntityFoundation,
            CaseNarrative, TimelineEvent, ScenarioSeeds, TransformationAnalysis
        )

        # Get case
        case = Document.query.get_or_404(case_id)

        synthesizer = CaseSynthesizer()

        # Build model from stored data
        foundation = synthesizer._build_entity_foundation(case_id)
        provisions = synthesizer._load_provisions(case_id)
        questions, conclusions = synthesizer._load_qc(case_id)
        transformation = synthesizer._get_transformation_type(case_id)
        canonical_points = synthesizer.load_canonical_points(case_id)

        # Load rich analysis from database
        causal_links, question_emergence, resolution_patterns = synthesizer._load_rich_analysis(case_id)

        # Reconstruct narrative if we have canonical points
        narrative = None
        if canonical_points:
            narrative = synthesizer._construct_narrative(case_id, foundation, canonical_points, conclusions)

        model = CaseSynthesisModel(
            case_id=case_id,
            case_title=case.title,
            entity_foundation=foundation,
            provisions=provisions,
            questions=questions,
            conclusions=conclusions,
            transformation=TransformationAnalysis(
                transformation_type=transformation,
                confidence=0.8,
                reasoning="",
                pattern_description="",
                evidence=[]
            ) if transformation else None,
            # Rich analysis from database
            causal_normative_links=causal_links,
            question_emergence=question_emergence,
            resolution_patterns=resolution_patterns,
            # Decision points
            canonical_decision_points=canonical_points,
            algorithmic_candidates_count=len(canonical_points),  # Approximation
            narrative=narrative
        )

        # Check if we have any rich analysis
        has_rich_analysis = len(causal_links) > 0 or len(question_emergence) > 0 or len(resolution_patterns) > 0

        return jsonify({
            'success': True,
            'case_id': case_id,
            'case_title': model.case_title,
            'synthesis': model.to_dict(),
            'summary': model.summary(),
            'has_synthesis': len(canonical_points) > 0,
            'has_rich_analysis': has_rich_analysis
        })

    except Exception as e:
        logger.error(f"Error loading synthesis model for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# INDIVIDUAL EXTRACTION ENDPOINTS (for step4.html task-by-task display)
# ============================================================================

@bp.route('/case/<int:case_id>/extract_provisions_stream', methods=['POST'])
@auth_required_for_llm
def extract_provisions_streaming(case_id):
    """
    Extract code provisions with SSE streaming for real-time progress.
    """
    import json
    from flask import Response, stream_with_context
    from app.services.nspe_references_parser import NSPEReferencesParser
    from app.services.universal_provision_detector import UniversalProvisionDetector
    from app.services.provision_grouper import ProvisionGrouper
    from app.services.provision_group_validator import ProvisionGroupValidator
    from app.services.code_provision_linker import CodeProvisionLinker

    def sse_msg(data):
        return f"data: {json.dumps(data)}\n\n"

    def generate():
        try:
            case = Document.query.get_or_404(case_id)
            llm_client = get_llm_client()

            # Clear existing provisions
            TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='code_provision_reference'
            ).delete(synchronize_session=False)
            db.session.commit()

            yield sse_msg({'stage': 'START', 'progress': 5, 'messages': ['Starting provisions extraction...']})

            # Get references HTML
            sections_dual = case.doc_metadata.get('sections_dual', {}) if case.doc_metadata else {}
            references_html = None
            for section_key, section_content in sections_dual.items():
                if 'reference' in section_key.lower():
                    references_html = section_content.get('html', '') if isinstance(section_content, dict) else ''
                    break

            if not references_html:
                yield sse_msg({'stage': 'ERROR', 'progress': 100, 'messages': ['No references section found'], 'error': True})
                return

            # Parse provisions
            parser = NSPEReferencesParser()
            provisions = parser.parse_references_html(references_html)
            yield sse_msg({'stage': 'PARSED', 'progress': 15, 'messages': [f'Parsed {len(provisions)} NSPE code provisions']})

            # Get case sections for detection
            case_sections = {}
            for section_key in ['facts', 'discussion', 'question', 'conclusion']:
                if section_key in sections_dual:
                    section_data = sections_dual[section_key]
                    case_sections[section_key] = section_data.get('text', '') if isinstance(section_data, dict) else str(section_data)

            # Detect mentions
            detector = UniversalProvisionDetector()
            all_mentions = detector.detect_all_provisions(case_sections)
            yield sse_msg({'stage': 'DETECTED', 'progress': 25, 'messages': [f'Detected {len(all_mentions)} provision mentions in case text']})

            # Group mentions
            grouper = ProvisionGrouper()
            grouped_mentions = grouper.group_mentions_by_provision(all_mentions, provisions)
            yield sse_msg({'stage': 'GROUPED', 'progress': 30, 'messages': ['Grouped mentions by provision code']})

            # Validate each provision
            validator = ProvisionGroupValidator(llm_client)
            for i, provision in enumerate(provisions):
                code = provision['code_provision']
                mentions = grouped_mentions.get(code, [])

                if mentions:
                    yield sse_msg({'stage': 'VALIDATING', 'progress': 30 + int((i / len(provisions)) * 30),
                                   'messages': [f'Validating {code}: {len(mentions)} mentions...']})

                    validated = validator.validate_group(code, provision['provision_text'], mentions)
                    provision['relevant_excerpts'] = [
                        {
                            'section': v.section,
                            'text': v.excerpt,
                            'matched_citation': v.citation_text,
                            'mention_type': v.content_type,
                            'confidence': v.confidence,
                            'validation_reasoning': v.reasoning
                        }
                        for v in validated
                    ]

                    yield sse_msg({'stage': 'VALIDATED', 'progress': 30 + int(((i + 1) / len(provisions)) * 30),
                                   'messages': [f'Validation complete for {code}: {len(validated)}/{len(mentions)} mentions relevant']})
                else:
                    provision['relevant_excerpts'] = []

            # Link to entities
            yield sse_msg({'stage': 'LINKING', 'progress': 65, 'messages': ['Linking provisions to extracted entities...']})

            all_entities = get_all_case_entities(case_id)
            linker = CodeProvisionLinker(llm_client)
            provisions = linker.link_provisions_to_entities(
                provisions,
                roles=_format_entities_for_linking(all_entities.get('roles', [])),
                states=_format_entities_for_linking(all_entities.get('states', [])),
                resources=_format_entities_for_linking(all_entities.get('resources', [])),
                principles=_format_entities_for_linking(all_entities.get('principles', [])),
                obligations=_format_entities_for_linking(all_entities.get('obligations', [])),
                constraints=_format_entities_for_linking(all_entities.get('constraints', [])),
                capabilities=_format_entities_for_linking(all_entities.get('capabilities', [])),
                actions=_format_entities_for_linking(all_entities.get('actions', [])),
                events=_format_entities_for_linking(all_entities.get('events', [])),
                case_text_summary=f"Case {case_id}: {case.title}"
            )

            # Count links
            total_links = sum(len(p.get('applies_to', [])) for p in provisions)
            yield sse_msg({'stage': 'LINKED', 'progress': 85, 'messages': [f'Linked provisions to {total_links} entities']})

            # Store provisions
            yield sse_msg({'stage': 'STORING', 'progress': 90, 'messages': ['Storing provisions in database...']})
            session_id = str(uuid.uuid4())
            store_provisions_to_rdf(case_id, provisions, session_id)

            # Build final status
            status_messages = []
            for p in provisions:
                code = p.get('code_provision', 'Unknown')
                excerpts = len(p.get('relevant_excerpts', []))
                applies_to = len(p.get('applies_to', []))
                status_messages.append(f'Provision {code}: {applies_to} entity links, {excerpts} excerpts')

            # Build formatted results for display
            results_text = f"Extracted {len(provisions)} NSPE Code Provisions\n"
            results_text += "=" * 40 + "\n\n"
            for p in provisions:
                code = p.get('code_provision', 'Unknown')
                text = p.get('provision_text', '')[:100]
                excerpts = len(p.get('relevant_excerpts', []))
                applies_to = len(p.get('applies_to', []))
                results_text += f"{code}\n"
                results_text += f"  Text: {text}...\n" if len(p.get('provision_text', '')) > 100 else f"  Text: {text}\n"
                results_text += f"  Excerpts found: {excerpts}\n"
                results_text += f"  Entity links: {applies_to}\n\n"

            yield sse_msg({
                'stage': 'COMPLETE',
                'progress': 100,
                'messages': [f'Extraction complete: {len(provisions)} provisions'],
                'status_messages': status_messages,
                'prompt': 'Algorithmic extraction from References section (HTML parsing + pattern matching)',
                'raw_llm_response': results_text,
                'result': {
                    'count': len(provisions),
                    'provisions': [
                        {
                            'code': p.get('code_provision', ''),
                            'excerpts': len(p.get('relevant_excerpts', [])),
                            'applies_to': len(p.get('applies_to', []))
                        }
                        for p in provisions
                    ]
                }
            })

        except Exception as e:
            logger.error(f"Streaming provisions error: {e}")
            import traceback
            traceback.print_exc()
            yield sse_msg({'stage': 'ERROR', 'progress': 100, 'messages': [f'Error: {str(e)}'], 'error': True})

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


def _format_entities_for_linking(entities):
    """Format entities for the provision linker."""
    return [
        {
            'label': e.entity_label,
            'definition': e.entity_definition or '',
            'uri': e.rdf_json_ld.get('@id', '') if e.rdf_json_ld else ''
        }
        for e in entities
    ]


def store_provisions_to_rdf(case_id, provisions, session_id):
    """Store provisions to TemporaryRDFStorage."""
    for provision in provisions:
        rdf_entity = TemporaryRDFStorage(
            case_id=case_id,
            extraction_session_id=session_id,
            extraction_type='code_provision_reference',
            storage_type='individual',
            entity_type='provisions',
            entity_label=provision.get('code_provision', 'Unknown'),
            entity_definition=provision.get('provision_text', ''),
            rdf_json_ld={
                '@type': 'proeth-case:CodeProvisionReference',
                'codeProvision': provision.get('code_provision', ''),
                'provisionText': provision.get('provision_text', ''),
                'relevantExcerpts': provision.get('relevant_excerpts', []),
                'appliesTo': provision.get('applies_to', [])
            },
            is_selected=True
        )
        db.session.add(rdf_entity)
    db.session.commit()


@bp.route('/case/<int:case_id>/extract_provisions', methods=['POST'])
@auth_required_for_llm
def extract_provisions_individual(case_id):
    """
    Extract code provisions individually (Part A).
    Returns prompt and response for UI display like step1.html.
    """
    try:
        case = Document.query.get_or_404(case_id)

        # Clear existing provisions first
        TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='code_provision_reference'
        ).delete(synchronize_session=False)
        db.session.commit()

        # Run extraction
        provisions = extract_and_link_provisions(case_id, case)

        # Get the saved prompt/response from ExtractionPrompt
        prompt_record = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='code_provision_reference'
        ).order_by(ExtractionPrompt.created_at.desc()).first()

        # Build status messages for UI display
        status_messages = []
        for p in provisions:
            code = p.get('code_provision', 'Unknown')
            excerpts = len(p.get('relevant_excerpts', []))
            applies_to = len(p.get('applies_to', []))
            status_messages.append(f"Provision {code}: {applies_to} entity links, {excerpts} excerpts")

        return jsonify({
            'success': True,
            'prompt': prompt_record.prompt_text if prompt_record else 'Provision extraction',
            'raw_llm_response': prompt_record.raw_response if prompt_record else '',
            'status_messages': status_messages,
            'result': {
                'count': len(provisions),
                'provisions': [
                    {
                        'code': p.get('code_provision', ''),
                        'text': p.get('provision_text', '')[:200] + '...' if len(p.get('provision_text', '')) > 200 else p.get('provision_text', ''),
                        'excerpts': len(p.get('relevant_excerpts', [])),
                        'applies_to': len(p.get('applies_to', []))
                    }
                    for p in provisions[:10]  # Limit for UI
                ]
            },
            'metadata': {
                'model': prompt_record.llm_model if prompt_record else 'unknown',
                'timestamp': prompt_record.created_at.isoformat() if prompt_record else None
            }
        })

    except Exception as e:
        logger.error(f"Error extracting provisions for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# PART A2: PRECEDENT CASE REFERENCES
# ============================================================================

PRECEDENT_EXTRACTION_PROMPT = """You are analyzing an ethics case from the NSPE Board of Ethical Review (BER).
Identify ALL prior cases, decisions, or rulings cited by the board in their discussion.

CASE TEXT:
{case_text}

For each cited case, extract:
1. caseCitation: The exact citation as it appears in the text (e.g., "BER Case 94-8", "Case No. 85-3")
2. caseNumber: Normalized case number (e.g., "94-8", "85-3")
3. citationContext: A 1-2 sentence summary of WHY the board cited this case -- what point it supports
4. citationType: One of: "supporting" (cited to support the current analysis), "distinguishing" (cited to show how the current case differs), "analogizing" (cited as a parallel situation), "overruling" (cited as being superseded)
5. principleEstablished: The key principle, holding, or precedent that the cited case establishes
6. relevantExcerpts: Array of objects with "section" (facts/discussion/question/conclusion) and "text" (the exact passage where the citation appears, up to 200 characters)

Return a JSON array. If no prior cases are cited, return an empty array [].

Example output:
[
  {{
    "caseCitation": "BER Case 94-8",
    "caseNumber": "94-8",
    "citationContext": "The Board cited this case to establish that engineers must have an objective basis to assess another engineer's competency before delegating work.",
    "citationType": "supporting",
    "principleEstablished": "Engineers must verify that colleagues have sufficient education, experience, and training before delegating professional responsibilities.",
    "relevantExcerpts": [
      {{"section": "discussion", "text": "In BER Case 94-8, Engineer A, a professional engineer, was working with..."}}
    ]
  }}
]

Respond ONLY with the JSON array, no other text."""


@bp.route('/case/<int:case_id>/extract_precedents_stream', methods=['POST'])
@auth_required_for_llm
def extract_precedents_streaming(case_id):
    """Extract precedent case references with SSE streaming for real-time progress."""
    import json as json_mod
    from flask import Response, stream_with_context

    def sse_msg(data):
        return f"data: {json_mod.dumps(data)}\n\n"

    def generate():
        try:
            case = Document.query.get_or_404(case_id)
            llm_client = get_llm_client()

            # Clear existing precedent references
            TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='precedent_case_reference'
            ).delete(synchronize_session=False)
            db.session.commit()

            yield sse_msg({'stage': 'START', 'progress': 5, 'messages': ['Starting precedent case extraction...']})

            # Gather case text from all sections
            sections_dual = case.doc_metadata.get('sections_dual', {}) if case.doc_metadata else {}
            case_text_parts = []
            for section_key in ['facts', 'discussion', 'question', 'conclusion']:
                section_data = sections_dual.get(section_key, {})
                text = section_data.get('text', '') if isinstance(section_data, dict) else str(section_data)
                if text:
                    case_text_parts.append(f"=== {section_key.upper()} ===\n{text}")

            if not case_text_parts:
                yield sse_msg({'stage': 'ERROR', 'progress': 100, 'messages': ['No case sections found'], 'error': True})
                return

            case_text = '\n\n'.join(case_text_parts)
            yield sse_msg({'stage': 'PREPARED', 'progress': 15, 'messages': [f'Prepared {len(case_text_parts)} case sections for analysis']})

            # Build prompt
            prompt = PRECEDENT_EXTRACTION_PROMPT.format(case_text=case_text)
            yield sse_msg({'stage': 'PROMPTING', 'progress': 25, 'messages': ['Sending to LLM for precedent analysis...']})

            # Call LLM
            response = llm_client.messages.create(
                model='claude-sonnet-4-20250514',
                max_tokens=4096,
                messages=[{'role': 'user', 'content': prompt}]
            )
            raw_response = response.content[0].text
            yield sse_msg({'stage': 'RECEIVED', 'progress': 60, 'messages': ['LLM response received, parsing...']})

            # Parse JSON response
            try:
                # Handle potential markdown code blocks
                cleaned = raw_response.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
                    if cleaned.endswith('```'):
                        cleaned = cleaned[:-3].strip()
                precedents = json_mod.loads(cleaned)
            except json_mod.JSONDecodeError:
                logger.error(f"Failed to parse precedent extraction response: {raw_response[:500]}")
                yield sse_msg({'stage': 'ERROR', 'progress': 100,
                               'messages': ['Failed to parse LLM response as JSON'], 'error': True})
                return

            if not isinstance(precedents, list):
                precedents = []

            yield sse_msg({'stage': 'PARSED', 'progress': 70,
                           'messages': [f'Found {len(precedents)} cited precedent cases']})

            # Attempt to resolve case numbers to internal document IDs
            for p in precedents:
                case_number = p.get('caseNumber', '')
                if case_number:
                    try:
                        resolved = Document.query.filter(
                            Document.doc_metadata['case_number'].astext == case_number
                        ).first()
                        if resolved:
                            p['internalCaseId'] = resolved.id
                            p['resolved'] = True
                        else:
                            p['internalCaseId'] = None
                            p['resolved'] = False
                    except Exception:
                        p['internalCaseId'] = None
                        p['resolved'] = False

            yield sse_msg({'stage': 'RESOLVED', 'progress': 80,
                           'messages': [f'Resolved {sum(1 for p in precedents if p.get("resolved"))} of {len(precedents)} to internal cases']})

            # Store precedent entities
            session_id = str(uuid.uuid4())
            for p in precedents:
                rdf_entity = TemporaryRDFStorage(
                    case_id=case_id,
                    extraction_session_id=session_id,
                    extraction_type='precedent_case_reference',
                    storage_type='individual',
                    entity_type='precedent_references',
                    entity_label=p.get('caseCitation', 'Unknown Case'),
                    entity_definition=p.get('citationContext', ''),
                    rdf_json_ld={
                        '@type': 'proeth-case:PrecedentCaseReference',
                        'caseCitation': p.get('caseCitation', ''),
                        'caseNumber': p.get('caseNumber', ''),
                        'citationContext': p.get('citationContext', ''),
                        'citationType': p.get('citationType', 'supporting'),
                        'principleEstablished': p.get('principleEstablished', ''),
                        'relevantExcerpts': p.get('relevantExcerpts', []),
                        'internalCaseId': p.get('internalCaseId'),
                        'resolved': p.get('resolved', False)
                    },
                    is_selected=True
                )
                db.session.add(rdf_entity)

            # Save extraction prompt record
            extraction_prompt = ExtractionPrompt(
                case_id=case_id,
                concept_type='precedent_case_reference',
                step_number=4,
                section_type='discussion',
                prompt_text=prompt,
                llm_model='claude-sonnet-4-20250514',
                extraction_session_id=session_id,
                raw_response=raw_response,
                results_summary={'total_precedents': len(precedents)},
                is_active=True,
                times_used=1,
                created_at=datetime.utcnow(),
                last_used_at=datetime.utcnow()
            )
            db.session.add(extraction_prompt)
            db.session.commit()

            # Update case_precedent_features with cited case numbers
            _update_cited_cases(case_id, precedents)

            yield sse_msg({'stage': 'STORED', 'progress': 90,
                           'messages': [f'Stored {len(precedents)} precedent references']})

            # Build results text for display
            results_text = f"Extracted {len(precedents)} Precedent Case References\n"
            results_text += "=" * 40 + "\n\n"
            for p in precedents:
                citation = p.get('caseCitation', 'Unknown')
                ctype = p.get('citationType', 'unknown')
                principle = p.get('principleEstablished', '')[:120]
                resolved_str = ' [resolved]' if p.get('resolved') else ''
                results_text += f"{citation} ({ctype}){resolved_str}\n"
                results_text += f"  Principle: {principle}\n"
                results_text += f"  Context: {p.get('citationContext', '')[:150]}\n\n"

            yield sse_msg({
                'stage': 'COMPLETE',
                'progress': 100,
                'messages': [f'Extraction complete: {len(precedents)} precedent cases'],
                'prompt': prompt[:500] + '...',
                'raw_llm_response': results_text,
                'result': {
                    'count': len(precedents),
                    'precedents': [
                        {
                            'citation': p.get('caseCitation', ''),
                            'type': p.get('citationType', ''),
                            'resolved': p.get('resolved', False)
                        }
                        for p in precedents
                    ]
                }
            })

        except Exception as e:
            logger.error(f"Streaming precedents error: {e}")
            import traceback
            traceback.print_exc()
            yield sse_msg({'stage': 'ERROR', 'progress': 100, 'messages': [f'Error: {str(e)}'], 'error': True})

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


def _update_cited_cases(case_id: int, precedents: list):
    """Update case_precedent_features with cited case numbers from extraction."""
    from app.models import CasePrecedentFeatures

    if not precedents:
        return

    case_numbers = [p.get('caseNumber', '') for p in precedents if p.get('caseNumber')]
    case_ids = [p.get('internalCaseId') for p in precedents if p.get('internalCaseId')]

    try:
        features = CasePrecedentFeatures.query.filter_by(case_id=case_id).first()
        if features:
            features.cited_case_numbers = case_numbers
            features.cited_case_ids = case_ids if case_ids else None
        else:
            features = CasePrecedentFeatures(
                case_id=case_id,
                cited_case_numbers=case_numbers,
                cited_case_ids=case_ids if case_ids else None,
                outcome_type='unclear',
                outcome_confidence=0.0,
                outcome_reasoning='',
                extraction_method='precedent_extraction'
            )
            db.session.add(features)
        db.session.commit()
    except Exception as e:
        logger.error(f"Error updating cited cases for case {case_id}: {e}")
        db.session.rollback()


@bp.route('/case/<int:case_id>/extract_precedents', methods=['POST'])
@auth_required_for_llm
def extract_precedents_individual(case_id):
    """Extract precedent case references (non-streaming fallback)."""
    try:
        case = Document.query.get_or_404(case_id)
        llm_client = get_llm_client()

        # Clear existing
        TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='precedent_case_reference'
        ).delete(synchronize_session=False)
        db.session.commit()

        # Gather case text
        sections_dual = case.doc_metadata.get('sections_dual', {}) if case.doc_metadata else {}
        case_text_parts = []
        for section_key in ['facts', 'discussion', 'question', 'conclusion']:
            section_data = sections_dual.get(section_key, {})
            text = section_data.get('text', '') if isinstance(section_data, dict) else str(section_data)
            if text:
                case_text_parts.append(f"=== {section_key.upper()} ===\n{text}")

        if not case_text_parts:
            return jsonify({'success': False, 'error': 'No case sections found'}), 400

        case_text = '\n\n'.join(case_text_parts)
        prompt = PRECEDENT_EXTRACTION_PROMPT.format(case_text=case_text)

        # Call LLM
        response = llm_client.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=4096,
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw_response = response.content[0].text

        # Parse
        import json as json_mod
        cleaned = raw_response.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3].strip()
        precedents = json_mod.loads(cleaned)
        if not isinstance(precedents, list):
            precedents = []

        # Resolve + store
        session_id = str(uuid.uuid4())
        for p in precedents:
            case_number = p.get('caseNumber', '')
            if case_number:
                try:
                    resolved = Document.query.filter(
                        Document.doc_metadata['case_number'].astext == case_number
                    ).first()
                    p['internalCaseId'] = resolved.id if resolved else None
                    p['resolved'] = resolved is not None
                except Exception:
                    p['internalCaseId'] = None
                    p['resolved'] = False

            rdf_entity = TemporaryRDFStorage(
                case_id=case_id,
                extraction_session_id=session_id,
                extraction_type='precedent_case_reference',
                storage_type='individual',
                entity_type='precedent_references',
                entity_label=p.get('caseCitation', 'Unknown Case'),
                entity_definition=p.get('citationContext', ''),
                rdf_json_ld={
                    '@type': 'proeth-case:PrecedentCaseReference',
                    'caseCitation': p.get('caseCitation', ''),
                    'caseNumber': p.get('caseNumber', ''),
                    'citationContext': p.get('citationContext', ''),
                    'citationType': p.get('citationType', 'supporting'),
                    'principleEstablished': p.get('principleEstablished', ''),
                    'relevantExcerpts': p.get('relevantExcerpts', []),
                    'internalCaseId': p.get('internalCaseId'),
                    'resolved': p.get('resolved', False)
                },
                is_selected=True
            )
            db.session.add(rdf_entity)

        extraction_prompt = ExtractionPrompt(
            case_id=case_id,
            concept_type='precedent_case_reference',
            step_number=4,
            section_type='discussion',
            prompt_text=prompt,
            llm_model='claude-sonnet-4-20250514',
            extraction_session_id=session_id,
            raw_response=raw_response,
            results_summary={'total_precedents': len(precedents)},
            is_active=True,
            times_used=1,
            created_at=datetime.utcnow(),
            last_used_at=datetime.utcnow()
        )
        db.session.add(extraction_prompt)
        db.session.commit()

        _update_cited_cases(case_id, precedents)

        return jsonify({
            'success': True,
            'prompt': prompt[:500] + '...',
            'raw_llm_response': raw_response,
            'result': {'count': len(precedents)}
        })

    except Exception as e:
        logger.error(f"Error extracting precedents for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


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


def _count_question_types(questions: list) -> dict:
    """Count questions by type (questions is List[Dict])."""
    counts = {}
    for q in questions:
        q_type = q.get('question_type', 'unknown') if isinstance(q, dict) else getattr(q, 'question_type', 'unknown')
        counts[q_type] = counts.get(q_type, 0) + 1
    return counts


@bp.route('/case/<int:case_id>/extract_qc_unified_stream', methods=['POST'])
@auth_required_for_llm
def extract_qc_unified_streaming(case_id):
    """
    Part B UNIFIED with SSE streaming: Extract Questions, Conclusions, and Link them.

    Provides real-time progress updates via Server-Sent Events.
    """
    import json as json_mod
    from flask import Response, stream_with_context

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
            yield sse_msg({'stage': 'QUESTIONS_DONE', 'progress': 45, 'messages': [f'Total: {board_count} Board + {analytical_count} analytical = {len(questions)} questions']})

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
            yield sse_msg({'stage': 'CONCLUSIONS_DONE', 'progress': 70, 'messages': [f'Extracted {board_c_count} Board + {analytical_c_count} analytical = {len(conclusions)} total conclusions']})

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


@bp.route('/case/<int:case_id>/extract_decision_synthesis', methods=['POST'])
@auth_required_for_llm
def extract_decision_synthesis_individual(case_id):
    """
    Run decision point synthesis (E1-E3 + LLM refinement).
    Returns algorithmic results + LLM prompt/response.
    """
    try:
        from app.services.case_synthesizer import CaseSynthesizer

        case = Document.query.get_or_404(case_id)
        synthesizer = CaseSynthesizer()

        # Build foundation
        foundation = synthesizer._build_entity_foundation(case_id)

        # Load Q&C for ground truth
        questions, conclusions = synthesizer._load_qc(case_id)

        # Run algorithmic composition (E1-E3)
        e1_result = synthesizer._run_e1_coverage(case_id)
        e2_result = synthesizer._run_e2_mapping(case_id)
        candidates = synthesizer._run_e3_composition(e1_result, e2_result, case_id)

        # LLM refinement with Q&C as ground truth
        canonical_points, llm_trace = synthesizer._llm_synthesize_decision_points(
            candidates, questions, conclusions, foundation, case_id
        )

        # Store canonical points
        synthesizer._store_canonical_points(canonical_points, case_id)

        return jsonify({
            'success': True,
            'result': {
                'e1_decision_relevant': e1_result.get('decision_relevant_count', 0),
                'e2_action_sets': e2_result.get('action_set_count', 0),
                'e3_candidates': len(candidates),
                'canonical_count': len(canonical_points),
                'qc_aligned': sum(1 for dp in canonical_points if dp.get('qc_aligned', False))
            },
            'llm_trace': {
                'stage': llm_trace.stage if llm_trace else 'decision_synthesis',
                'prompt': llm_trace.prompt if llm_trace else '',
                'response': llm_trace.response if llm_trace else '',
                'model': llm_trace.model if llm_trace else 'unknown'
            } if llm_trace else None,
            'metadata': {
                'timestamp': datetime.utcnow().isoformat()
            }
        })

    except Exception as e:
        logger.error(f"Error in decision synthesis for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/case/<int:case_id>/extract_narrative', methods=['POST'])
@auth_required_for_llm
def extract_narrative_individual(case_id):
    """
    Run narrative construction (timeline, summary, scenario seeds).
    Returns LLM prompt/response.
    """
    try:
        from app.services.case_synthesizer import CaseSynthesizer

        case = Document.query.get_or_404(case_id)
        synthesizer = CaseSynthesizer()

        # Build foundation
        foundation = synthesizer._build_entity_foundation(case_id)

        # Load canonical points
        canonical_points = synthesizer.load_canonical_points(case_id)

        # Load conclusions
        _, conclusions = synthesizer._load_qc(case_id)

        # Construct narrative with LLM
        narrative, llm_trace = synthesizer._construct_narrative_with_llm(
            case_id, foundation, canonical_points, conclusions
        )

        return jsonify({
            'success': True,
            'result': {
                'has_summary': bool(narrative.case_summary),
                'timeline_events': len(narrative.timeline),
                'has_scenario_seeds': bool(narrative.scenario_seeds)
            },
            'narrative': {
                'case_summary': narrative.case_summary,
                'timeline': [
                    {
                        'sequence': e.sequence,
                        'phase_label': e.phase_label,
                        'description': e.description[:100] + '...' if len(e.description) > 100 else e.description,
                        'event_type': e.event_type
                    }
                    for e in narrative.timeline
                ],
                'scenario_seeds': narrative.scenario_seeds.to_dict() if narrative.scenario_seeds else None
            },
            'llm_trace': {
                'stage': llm_trace.stage if llm_trace else 'narrative',
                'prompt': llm_trace.prompt if llm_trace else '',
                'response': llm_trace.response if llm_trace else '',
                'model': llm_trace.model if llm_trace else 'unknown'
            } if llm_trace else None,
            'metadata': {
                'timestamp': datetime.utcnow().isoformat()
            }
        })

    except Exception as e:
        logger.error(f"Error in narrative construction for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/case/<int:case_id>/get_saved_step4_prompt')
def get_saved_step4_prompt(case_id):
    """
    Get saved prompt/response for a specific step4 task.
    Similar to step1's get_saved_prompt endpoint.
    """
    try:
        task_type = request.args.get('task_type', '')

        if not task_type:
            return jsonify({
                'success': False,
                'error': 'task_type parameter required'
            }), 400

        # Provisions are stored in temporary_rdf_storage, not extraction_prompts
        if task_type == 'provisions':
            provisions = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='code_provision_reference'
            ).all()

            if provisions:
                # Build a summary of provisions
                provision_list = [p.entity_label for p in provisions]
                return jsonify({
                    'success': True,
                    'prompt_text': f'Extracted {len(provisions)} code provisions from case references',
                    'raw_response': '\n'.join(provision_list),
                    'results_summary': f'{len(provisions)} provisions extracted',
                    'model': 'regex-parser',
                    'timestamp': provisions[0].created_at.isoformat() if provisions[0].created_at else None
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'No provisions extracted'
                })

        # Map task types to concept types for extraction_prompts lookup
        concept_type_map = {
            'questions': 'ethical_question',
            'conclusions': 'ethical_conclusion',
            'transformation': 'transformation_classification',
            'rich_analysis': 'rich_analysis',
            'decision_synthesis': 'phase3_decision_synthesis',  # Updated to match run_all saves
            'narrative': 'phase4_narrative'  # Updated to match phase4 saves
        }

        concept_type = concept_type_map.get(task_type, task_type)

        # For decision_synthesis, try both concept_type names (old and new)
        prompt_record = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type=concept_type
        ).order_by(ExtractionPrompt.created_at.desc()).first()

        if not prompt_record:
            return jsonify({
                'success': False,
                'message': f'No saved prompt for {task_type}'
            })

        return jsonify({
            'success': True,
            'prompt_text': prompt_record.prompt_text,
            'raw_response': prompt_record.raw_response,
            'results_summary': prompt_record.results_summary,
            'model': prompt_record.llm_model,
            'timestamp': prompt_record.created_at.isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting saved step4 prompt for case {case_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
