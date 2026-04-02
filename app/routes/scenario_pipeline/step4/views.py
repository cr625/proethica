"""
Step 4 View Routes

Page renders: step4 landing, entities, review, decision_points, synthesis_results.
"""

import json
import logging
import os
import re
from typing import Dict, List

from flask import render_template, request, jsonify, redirect, url_for, session as flask_session, current_app

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.services.pipeline_status_service import PipelineStatusService
from app.utils.environment_auth import auth_optional

from app.routes.scenario_pipeline.step4.helpers import (
    get_entities_summary,
    get_synthesis_status,
    _load_phase2_entity_summaries,
    _build_step4_entity_groups,
    _load_narrative_for_review,
    _get_all_entities_for_graph,
    _load_decision_points_for_review,
    _classify_conclusion_type,
    _count_conclusion_types,
)

logger = logging.getLogger(__name__)


def register_view_routes(bp):
    """Register all page-rendering routes on the blueprint."""

    @bp.route('/case/<int:case_id>/step4')
    def step4_synthesis(case_id):
        """Display Step 4 synthesis page."""
        try:
            case = Document.query.get_or_404(case_id)
            entities_summary = get_entities_summary(case_id)
            synthesis_status = get_synthesis_status(case_id)

            saved_synthesis = ExtractionPrompt.query.filter_by(
                case_id=case_id,
                concept_type='whole_case_synthesis'
            ).order_by(ExtractionPrompt.created_at.desc()).first()

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

            pipeline_status = PipelineStatusService.get_step_status(case_id)
            phase2_entities = _load_phase2_entity_summaries(case_id)

            return render_template(
                'scenarios/step4.html',
                case=case,
                entities_summary=entities_summary,
                synthesis_status=synthesis_status,
                saved_synthesis=saved_synthesis,
                phase4_data=phase4_data,
                phase2_entities=phase2_entities,
                current_step=4,
                prev_step_url=f"/scenario_pipeline/case/{case_id}/reconcile",
                next_step_url=None,
                next_step_name=None,
                pipeline_status=pipeline_status,
            )
        except Exception as e:
            logger.error(f"Error displaying Step 4 for case {case_id}: {e}")
            return str(e), 500

    @bp.route('/case/<int:case_id>/step4/phase2_entities_json')
    @auth_optional
    def step4_phase2_entities_json(case_id):
        """Return Phase 2 entity summaries as JSON for live card refresh during SSE synthesis."""
        return jsonify(_load_phase2_entity_summaries(case_id))

    @bp.route('/case/<int:case_id>/step4/entities')
    @auth_optional
    def step4_entities(case_id):
        """Display Step 4 entity review page."""
        try:
            case = Document.query.get_or_404(case_id)

            phase_groups = _build_step4_entity_groups(case_id)
            synthesis_status = get_synthesis_status(case_id)
            pipeline_status = PipelineStatusService.get_step_status(case_id)
            narrative_data = _load_narrative_for_review(case_id)

            # Commit counts
            rejected_count = TemporaryRDFStorage.query.filter_by(
                case_id=case_id, is_published=False, is_selected=False, is_reviewed=True
            ).count()
            total_unpublished = TemporaryRDFStorage.query.filter_by(
                case_id=case_id, is_published=False
            ).count()
            unpublished_count = total_unpublished - rejected_count
            published_count = TemporaryRDFStorage.query.filter_by(
                case_id=case_id, is_published=True
            ).count()
            class_count = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.is_published == False,  # noqa: E712
                TemporaryRDFStorage.storage_type == 'class',
                db.not_(db.and_(
                    TemporaryRDFStorage.is_selected == False,  # noqa: E712
                    TemporaryRDFStorage.is_reviewed == True     # noqa: E712
                ))
            ).count()
            individual_count = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.is_published == False,  # noqa: E712
                TemporaryRDFStorage.storage_type == 'individual',
                db.not_(db.and_(
                    TemporaryRDFStorage.is_selected == False,  # noqa: E712
                    TemporaryRDFStorage.is_reviewed == True     # noqa: E712
                ))
            ).count()

            ontserve_web_url = current_app.config.get('ONTSERVE_WEB_URL', 'http://localhost:5003')

            # Entity change detection (compare committed hashes vs OntServe current)
            from app.services.entity_change_detector import get_changed_entity_uris
            changed_entity_uris = get_changed_entity_uris(case_id) if published_count > 0 else set()

            return render_template(
                'scenario_pipeline/step4_entities.html',
                case=case,
                phase_groups=phase_groups,
                narrative_data=narrative_data,
                synthesis_status=synthesis_status,
                pipeline_status=pipeline_status,
                unpublished_count=unpublished_count,
                rejected_count=rejected_count,
                published_count=published_count,
                class_count=class_count,
                individual_count=individual_count,
                ontserve_web_url=ontserve_web_url,
                changed_entity_uris=changed_entity_uris,
                current_step=4,
                step_title='Step 4 Entities',
                prev_step_url=url_for('step4.step4_synthesis', case_id=case_id),
                next_step_url=url_for('step4.step4_review', case_id=case_id),
                next_step_name='Review',
            )
        except Exception as e:
            logger.error(f"Error displaying Step 4 entities for case {case_id}: {e}")
            return str(e), 500

    @bp.route('/case/<int:case_id>/step4/decision_points')
    def step4_decision_points(case_id):
        """Display Step 4E: Decision Point Composition page."""
        try:
            case = Document.query.get_or_404(case_id)
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
        """Redirect to Step 4 Synthesis page (arguments are now inline)."""
        return redirect(url_for('step4.step4_synthesis', case_id=case_id))

    @bp.route('/case/<int:case_id>/step4/review')
    def step4_review(case_id):
        """Display comprehensive Step 4 Review page."""
        try:
            case = Document.query.get_or_404(case_id)

            saved_synthesis = ExtractionPrompt.query.filter_by(
                case_id=case_id,
                concept_type='whole_case_synthesis'
            ).order_by(ExtractionPrompt.created_at.desc()).first()

            all_entities_objs = _get_all_entities_for_graph(case_id)

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
                    return len(type_order)

            def get_type_priority_obj(obj, type_field, type_order):
                item_type = (obj.rdf_json_ld or {}).get(type_field, 'unknown')
                try:
                    return type_order.index(item_type)
                except ValueError:
                    return len(type_order)

            questions = sorted(questions, key=lambda q: get_type_priority_dict(q, 'questionType', question_type_order))
            conclusions = sorted(conclusions, key=lambda c: get_type_priority_dict(c, 'conclusionType', conclusion_type_order))
            questions_objs = sorted(questions_objs, key=lambda q: get_type_priority_obj(q, 'questionType', question_type_order))
            conclusions_objs = sorted(conclusions_objs, key=lambda c: get_type_priority_obj(c, 'conclusionType', conclusion_type_order))

            # Check if synthesis annotations already exist
            from app.models.document_concept_annotation import DocumentConceptAnnotation

            existing_annotations = DocumentConceptAnnotation.query.filter_by(
                document_type='case',
                document_id=case_id,
                ontology_name='step4_synthesis',
                is_current=True
            ).all()

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
                               features_version, extracted_at,
                               cited_case_ids
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
                        'extracted_at': result[10],
                        'cited_case_ids': result[11] or []
                    }
            except Exception as e:
                logger.debug(f"No transformation data found for case {case_id}: {e}")

            # Cross-case context for Precedents tab
            cited_cases = []
            similar_cases = []
            try:
                # Resolve cited case IDs to titles
                cited_ids = precedent_features.get('cited_case_ids', []) if precedent_features else []
                if cited_ids:
                    cited_docs = Document.query.filter(Document.id.in_(cited_ids)).all()
                    for doc in cited_docs:
                        case_number = (doc.doc_metadata or {}).get('case_number', '')
                        cited_cases.append({
                            'id': doc.id,
                            'title': doc.title,
                            'case_number': case_number
                        })

                # Top 10 similar cases using paper weights (ICCBR 2026)
                # Paper formula: 0.40*embedding + 0.25*provisions + 0.15*outcome + 0.10*tags + 0.10*principles
                from app.routes.precedents import _find_precedents_for_case
                PAPER_WEIGHTS = {
                    'component_similarity': 0.40,
                    'provision_overlap': 0.25,
                    'outcome_alignment': 0.15,
                    'tag_overlap': 0.10,
                    'principle_overlap': 0.10,
                }
                from app.services.precedent.similarity_service import PrecedentSimilarityService
                sim_svc = PrecedentSimilarityService()
                sim_results = sim_svc.find_similar_cases(
                    case_id, limit=10, min_score=0.1,
                    weights=PAPER_WEIGHTS, use_component_embedding=True
                )
                # Enrich with citation flags and case metadata
                source_cited_ids = set(cited_ids)
                for r in sim_results:
                    target_doc = Document.query.get(r.target_case_id)
                    target_title = target_doc.title if target_doc else f'Case {r.target_case_id}'
                    # Check if target cites the source
                    target_cited_ids = set()
                    try:
                        t_result = db.session.execute(
                            text("SELECT cited_case_ids FROM case_precedent_features WHERE case_id = :cid"),
                            {'cid': r.target_case_id}
                        ).fetchone()
                        if t_result and t_result[0]:
                            target_cited_ids = set(t_result[0])
                    except Exception:
                        pass
                    similar_cases.append({
                        'case_id': r.target_case_id,
                        'title': target_title,
                        'overall_score': round(r.overall_similarity, 3),
                        'component_scores': {k: round(v, 3) for k, v in r.component_scores.items()},
                        'matching_provisions': r.matching_provisions or [],
                        'outcome_match': r.outcome_match,
                        'target_outcome': r.component_scores.get('outcome_alignment', 0) > 0,
                        'is_cited_precedent': r.target_case_id in source_cited_ids,
                        'is_cited_by': case_id in target_cited_ids,
                        'overlapping_tags': [],
                        'overlapping_citations': [],
                        'transformation_match': False,
                    })
            except Exception as e:
                logger.debug(f"Cross-case context unavailable for case {case_id}: {e}")

            # Build comprehensive data inventory for downstream services
            entity_type_counts = {}
            for entity in all_entities:
                etype = entity.get('entity_type', 'unknown')
                entity_type_counts[etype] = entity_type_counts.get(etype, 0) + 1

            data_inventory = {
                'passes_1_3': {
                    'total_entities': len(all_entities),
                    'by_type': entity_type_counts,
                    'available': len(all_entities) > 0
                },
                'step4_synthesis': {
                    'provisions': len(provisions),
                    'questions': len(questions),
                    'conclusions': len(conclusions),
                    'annotations': len(existing_annotations),
                    'available': len(provisions) > 0 or len(questions) > 0
                },
                'precedent_features': {
                    'has_features': precedent_features is not None,
                    'outcome_type': precedent_features.get('outcome_type') if precedent_features else None,
                    'transformation_type': precedent_features.get('transformation_type') if precedent_features else None,
                    'provisions_count': len(precedent_features.get('provisions_cited', [])) if precedent_features else 0,
                    'subject_tags_count': len(precedent_features.get('subject_tags', [])) if precedent_features else 0,
                    'has_principle_tensions': bool(precedent_features.get('principle_tensions')) if precedent_features else False,
                    'has_obligation_conflicts': bool(precedent_features.get('obligation_conflicts')) if precedent_features else False,
                    'has_embeddings': False
                },
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

            unpublished_count = TemporaryRDFStorage.query.filter_by(
                case_id=case_id, is_published=False
            ).count()
            published_count = TemporaryRDFStorage.query.filter_by(
                case_id=case_id, is_published=True
            ).count()

            # Load rich analysis data
            rich_analysis = None
            causal_links_objs = TemporaryRDFStorage.query.filter_by(
                case_id=case_id, extraction_type='causal_normative_link'
            ).all()
            question_emergence_objs = TemporaryRDFStorage.query.filter_by(
                case_id=case_id, extraction_type='question_emergence'
            ).all()
            resolution_pattern_objs = TemporaryRDFStorage.query.filter_by(
                case_id=case_id, extraction_type='resolution_pattern'
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

            pipeline_status = PipelineStatusService.get_step_status(case_id)
            can_publish = pipeline_status.get('step1', {}).get('complete', False) and unpublished_count > 0

            from app.services.unified_entity_resolver import UnifiedEntityResolver
            resolver = UnifiedEntityResolver(case_id=case_id)
            entity_lookup = resolver.get_lookup_dict()
            entity_lookup_by_label = resolver.get_label_index()

            # Check for validation study mode
            validation_study_mode = (
                flask_session.get('validation_study_mode') or
                request.args.get('validation_mode') == '1'
            )
            if request.args.get('validation_mode') == '1':
                flask_session['validation_study_mode'] = True

            context = {
                'case': case,
                'saved_synthesis': saved_synthesis,
                'provisions': provisions_objs,
                'provisions_json': provisions,
                'questions': questions_objs,
                'questions_json': questions,
                'conclusions': conclusions_objs,
                'conclusions_json': conclusions,
                'all_entities': all_entities,
                'entity_count': TemporaryRDFStorage.query.filter_by(case_id=case_id).count(),
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
                'cited_cases': cited_cases,
                'similar_cases': similar_cases,
                'data_inventory': data_inventory,
                'entity_type_counts': entity_type_counts,
                'pipeline_status': pipeline_status,
                'current_step': 4,
                'step_title': 'Synthesis Review',
                'prev_step_url': url_for('step4.step4_entities', case_id=case_id),
                'next_step_url': None,
                'next_step_name': None,
                'rich_analysis': rich_analysis,
                'decision_points': _load_decision_points_for_review(case_id),
                'narrative_data': _load_narrative_for_review(case_id),
                'entity_lookup': entity_lookup,
                'entity_lookup_by_label': entity_lookup_by_label,
                'validation_study_mode': validation_study_mode,
                'ontserve_web_url': current_app.config.get('ONTSERVE_WEB_URL', 'http://localhost:5003')
            }

            # Print mode: chromeless view for paper screenshots
            context['print_mode'] = request.args.get('print', '') == '1'
            context['print_tab'] = request.args.get('tab', '')
            context['print_preset'] = request.args.get('preset', 'column')

            return render_template('scenario_pipeline/step4_review.html', **context)

        except Exception as e:
            logger.error(f"Error displaying Step 4 review for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return str(e), 500

    @bp.route('/case/<int:case_id>/synthesis_results')
    def view_synthesis_results(case_id):
        """Display detailed synthesis results visualization."""
        try:
            case = Document.query.get_or_404(case_id)

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

            synthesis_data = json.loads(synthesis_prompt.raw_response)

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
    """Load detailed entity information for graph visualization."""
    entity_details = {}

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
