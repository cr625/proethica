"""
Step 4 Run All - Complete Synthesis with SSE Streaming Progress

Calls the same services as the individual UI buttons.
Provides two endpoints:
  - run_complete_synthesis (POST, blocking JSON) -- legacy
  - run_complete_synthesis_stream (POST, SSE) -- progressive UI updates

Independent phases run in parallel:
  2A||2B -> 2C -> 2D||2E -> Phase 3 -> Phase 4

Usage: Called by "Run Complete Synthesis" button.
"""

import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from flask import jsonify, Response, stream_with_context, current_app

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.utils.environment_auth import auth_required_for_llm
from app.utils.llm_utils import get_llm_client
from app.services.provenance_service import get_provenance_service
from app.routes.scenario_pipeline.step4_config import (
    STEP4_SECTION_TYPE, STEP4_DEFAULT_MODEL, STEP4_POWERFUL_MODEL,
    reset_step4_case_features,
)

logger = logging.getLogger(__name__)


def _sse_msg(data):
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


def _run_in_context(app, func, *args, **kwargs):
    """Run a function inside a Flask app context (for ThreadPoolExecutor)."""
    with app.app_context():
        return func(*args, **kwargs)


def register_run_all_routes(bp, get_all_case_entities):
    """
    Register the run-all-synthesis route on the blueprint.

    Args:
        bp: The Flask Blueprint to register routes on
        get_all_case_entities: Helper function to load entities for a case
    """

    @bp.route('/case/<int:case_id>/run_complete_synthesis', methods=['POST'])
    @auth_required_for_llm
    def run_complete_synthesis(case_id):
        """
        Run complete Step 4 synthesis by calling the same services as UI buttons.

        Non-streaming - runs to completion, returns JSON result.
        """
        try:
            case = Document.query.get_or_404(case_id)
            results = {'stages': [], 'success': False}
            llm_client = get_llm_client()

            # =====================================================================
            # STEP 1: Clear existing Step 4 data
            # =====================================================================
            logger.info(f"[RunAll] Clearing Step 4 data for case {case_id}")
            clear_result = _clear_step4_data(case_id)
            results['clear'] = clear_result
            results['stages'].append('CLEAR')

            # =====================================================================
            # STEP 2A: Provisions
            # =====================================================================
            logger.info(f"[RunAll] Running provisions extraction for case {case_id}")
            provisions_result = _run_provisions(case_id, llm_client, get_all_case_entities)
            results['provisions'] = provisions_result
            results['stages'].append('PROVISIONS')

            if provisions_result.get('error'):
                logger.error(f"[RunAll] Provisions failed: {provisions_result}")
                return jsonify({
                    'success': False,
                    'error': f"Provisions failed: {provisions_result.get('error')}",
                    'results': results
                }), 500

            # =====================================================================
            # STEP 2B: Precedent Cases
            # =====================================================================
            logger.info(f"[RunAll] Running precedent case extraction for case {case_id}")
            precedents_result = _run_precedents(case_id, llm_client)
            results['precedents'] = precedents_result
            results['stages'].append('PRECEDENTS')

            # Non-blocking - continue even on error

            # =====================================================================
            # STEP 2C: Q&C Unified
            # =====================================================================
            logger.info(f"[RunAll] Running Q&C extraction for case {case_id}")
            qc_result = _run_qc_unified(case_id, llm_client, get_all_case_entities)
            results['qc'] = qc_result
            results['stages'].append('QC')

            if qc_result.get('error'):
                logger.error(f"[RunAll] Q&C failed: {qc_result}")
                return jsonify({
                    'success': False,
                    'error': f"Q&C failed: {qc_result.get('error')}",
                    'results': results
                }), 500

            # =====================================================================
            # STEP 2D: Transformation
            # =====================================================================
            logger.info(f"[RunAll] Running transformation classification for case {case_id}")
            transformation_result = _run_transformation(case_id, llm_client)
            results['transformation'] = transformation_result
            results['stages'].append('TRANSFORMATION')

            # Non-blocking - continue even on error

            # =====================================================================
            # STEP 2E: Rich Analysis
            # =====================================================================
            logger.info(f"[RunAll] Running rich analysis for case {case_id}")
            rich_result = _run_rich_analysis(case_id)
            results['rich_analysis'] = rich_result
            results['stages'].append('RICH_ANALYSIS')

            # Non-blocking - continue even on error

            # =====================================================================
            # PHASE 3: Decision Synthesis
            # =====================================================================
            logger.info(f"[RunAll] Running Phase 3 decision synthesis for case {case_id}")
            phase3_result = _run_phase3(case_id)
            results['phase3'] = phase3_result
            results['stages'].append('PHASE3')

            # Non-blocking - continue even on error

            # =====================================================================
            # PHASE 4: Narrative Construction
            # =====================================================================
            logger.info(f"[RunAll] Running Phase 4 narrative construction for case {case_id}")
            phase4_result = _run_phase4(case_id)
            results['phase4'] = phase4_result
            results['stages'].append('PHASE4')

            # Non-blocking - continue even on error

            # =====================================================================
            # COMPLETE
            # =====================================================================
            logger.info(f"[RunAll] Complete synthesis finished for case {case_id}")
            results['success'] = True

            # Collect warnings from all phases
            all_warnings = []
            for phase_key in ['qc', 'rich_analysis', 'phase3', 'phase4']:
                phase_result = results.get(phase_key, {})
                if isinstance(phase_result, dict) and 'warnings' in phase_result:
                    all_warnings.extend(phase_result['warnings'])
            if all_warnings:
                results['warnings'] = all_warnings
                logger.warning(f"[RunAll] Completed with {len(all_warnings)} warnings")

            return jsonify(results)

        except Exception as e:
            logger.error(f"[RunAll] Error in run_complete_synthesis for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/run_complete_synthesis_stream', methods=['POST'])
    @auth_required_for_llm
    def run_complete_synthesis_stream(case_id):
        """Run complete Step 4 synthesis with SSE streaming progress.

        Parallelizes independent phases (2A||2B, 2D||2E) and yields
        progress events so the frontend can update the UI incrementally.
        """
        app = current_app._get_current_object()

        def generate():
            try:
                case = Document.query.get_or_404(case_id)
                yield _sse_msg({'stage': 'START', 'progress': 0,
                                'messages': ['Starting complete synthesis...']})

                # -- CLEAR --
                yield _sse_msg({'stage': 'CLEARING', 'progress': 2,
                                'messages': ['Clearing old Step 4 data...'],
                                'clear_ui': True})
                clear_result = _clear_step4_data(case_id)
                deleted = clear_result.get('entities_deleted', 0)
                yield _sse_msg({'stage': 'CLEARED', 'progress': 5,
                                'messages': [f'Cleared {deleted} entities, {clear_result.get("prompts_deleted", 0)} prompts']})

                llm_client = get_llm_client()

                # -- 2A + 2B in parallel --
                yield _sse_msg({'stage': 'PHASE2_AB', 'progress': 8,
                                'messages': ['2A+2B: Extracting provisions and precedents...'],
                                'active_dots': ['provisions', 'precedents']})

                with ThreadPoolExecutor(max_workers=2) as executor:
                    future_a = executor.submit(
                        _run_in_context, app, _run_provisions,
                        case_id, llm_client, get_all_case_entities)
                    future_b = executor.submit(
                        _run_in_context, app, _run_precedents,
                        case_id, llm_client)
                    provisions_result = future_a.result()
                    precedents_result = future_b.result()

                prov_count = provisions_result.get('provisions_count', 0)
                prov_links = provisions_result.get('entity_links', 0)
                yield _sse_msg({'stage': 'PROVISIONS_DONE', 'progress': 20,
                                'messages': [f'2A: {prov_count} provisions, {prov_links} entity links'],
                                'completed_dot': 'provisions',
                                'result': provisions_result})

                prec_count = precedents_result.get('precedents_count', 0)
                yield _sse_msg({'stage': 'PRECEDENTS_DONE', 'progress': 25,
                                'messages': [f'2B: {prec_count} precedent cases'],
                                'completed_dot': 'precedents',
                                'result': precedents_result})

                # Provisions error is blocking
                if provisions_result.get('error'):
                    yield _sse_msg({'stage': 'ERROR', 'progress': 100, 'error': True,
                                    'messages': [f'Provisions failed: {provisions_result["error"]}']})
                    return

                # -- 2C: Q&C (depends on provisions) --
                yield _sse_msg({'stage': 'QC_START', 'progress': 28,
                                'messages': ['2C: Extracting Questions & Conclusions...'],
                                'active_dots': ['questions', 'conclusions']})
                qc_result = _run_qc_unified(case_id, llm_client, get_all_case_entities)

                q_count = qc_result.get('questions_count', 0)
                c_count = qc_result.get('conclusions_count', 0)
                links = qc_result.get('links_count', 0)
                yield _sse_msg({'stage': 'QC_DONE', 'progress': 45,
                                'messages': [f'2C: {q_count} questions, {c_count} conclusions, {links} Q-C links'],
                                'completed_dots': ['questions', 'conclusions'],
                                'result': qc_result})

                if qc_result.get('error'):
                    yield _sse_msg({'stage': 'ERROR', 'progress': 100, 'error': True,
                                    'messages': [f'Q&C failed: {qc_result["error"]}']})
                    return

                # Report warnings
                qc_warnings = qc_result.get('warnings', [])
                if qc_warnings:
                    yield _sse_msg({'stage': 'QC_WARNINGS', 'progress': 46,
                                    'messages': [f'Warning: {w}' for w in qc_warnings]})

                # -- 2D + 2E in parallel --
                yield _sse_msg({'stage': 'PHASE2_DE', 'progress': 48,
                                'messages': ['2D+2E: Transformation + Rich Analysis...'],
                                'active_dots': ['transformation', 'rich_analysis']})

                with ThreadPoolExecutor(max_workers=2) as executor:
                    future_d = executor.submit(
                        _run_in_context, app, _run_transformation,
                        case_id, llm_client)
                    future_e = executor.submit(
                        _run_in_context, app, _run_rich_analysis,
                        case_id)
                    transformation_result = future_d.result()
                    rich_result = future_e.result()

                t_type = transformation_result.get('transformation_type', '?')
                yield _sse_msg({'stage': 'TRANSFORMATION_DONE', 'progress': 55,
                                'messages': [f'2D: Transformation type = {t_type}'],
                                'completed_dot': 'transformation',
                                'result': transformation_result})

                cl = rich_result.get('causal_links', 0)
                qe = rich_result.get('question_emergence', 0)
                rp = rich_result.get('resolution_patterns', 0)
                yield _sse_msg({'stage': 'RICH_DONE', 'progress': 60,
                                'messages': [f'2E: {cl} causal links, {qe} question emergence, {rp} resolution patterns'],
                                'completed_dot': 'rich_analysis',
                                'result': rich_result})

                # -- Phase 3 --
                yield _sse_msg({'stage': 'PHASE3_START', 'progress': 63,
                                'messages': ['Phase 3: Decision Point Synthesis (E1-E3 + LLM)...'],
                                'active_phase': 'phase3'})
                phase3_result = _run_phase3(case_id)

                canonical = phase3_result.get('canonical_count', 0)
                candidates = phase3_result.get('candidates_count', 0)
                yield _sse_msg({'stage': 'PHASE3_DONE', 'progress': 78,
                                'messages': [f'Phase 3: {canonical} canonical decision points (from {candidates} candidates)'],
                                'completed_phase': 'phase3',
                                'result': phase3_result})

                # -- Phase 4 --
                yield _sse_msg({'stage': 'PHASE4_START', 'progress': 80,
                                'messages': ['Phase 4: Narrative Construction...'],
                                'active_phase': 'phase4'})
                phase4_result = _run_phase4(case_id)

                chars = phase4_result.get('characters_count', 0)
                events = phase4_result.get('timeline_events', 0)
                yield _sse_msg({'stage': 'PHASE4_DONE', 'progress': 95,
                                'messages': [f'Phase 4: {chars} characters, {events} timeline events'],
                                'completed_phase': 'phase4',
                                'result': phase4_result})

                # -- COMPLETE --
                all_results = {
                    'provisions': provisions_result,
                    'precedents': precedents_result,
                    'qc': qc_result,
                    'transformation': transformation_result,
                    'rich_analysis': rich_result,
                    'phase3': phase3_result,
                    'phase4': phase4_result,
                }
                yield _sse_msg({'stage': 'COMPLETE', 'progress': 100,
                                'messages': ['Synthesis complete!'],
                                'result': all_results})

            except Exception as e:
                logger.error(f"[RunAll-Stream] Error: {e}")
                import traceback
                traceback.print_exc()
                yield _sse_msg({'stage': 'ERROR', 'progress': 100, 'error': True,
                                'messages': [f'Error: {str(e)}']})

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',
            }
        )

    return {
        'run_complete_synthesis': run_complete_synthesis,
        'run_complete_synthesis_stream': run_complete_synthesis_stream,
    }


def _clear_step4_data(case_id: int) -> dict:
    """Clear all Step 4 data (Phase 2-4) while preserving Phase 1 entities.

    Must stay in sync with clear_step4_data() in step4.py.
    """
    try:
        extraction_types_to_clear = [
            # 2A: Provisions
            'code_provision_reference',
            # 2B: Precedent Cases
            'precedent_case_reference',
            # 2C: Questions & Conclusions
            'ethical_question',
            'ethical_conclusion',
            # Phase 3: Arguments
            'argument_generated',
            'argument_validation',
            # 2E: Rich Analysis
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
        prompts_deleted = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            step_number=4
        ).delete(synchronize_session=False)

        # Clear Step 4-populated fields from CasePrecedentFeatures
        reset_step4_case_features(case_id)

        # Clear Step 4 provenance data
        from app.models.provenance import (
            ProvenanceActivity, ProvenanceEntity,
            ProvenanceUsage, ProvenanceDerivation
        )

        step4_activities = ProvenanceActivity.query.filter(
            ProvenanceActivity.case_id == case_id,
            ProvenanceActivity.activity_name.like('step4%')
        ).all()

        activity_ids = [a.id for a in step4_activities]
        provenance_deleted = 0

        if activity_ids:
            step4_entity_ids = [
                e.id for e in ProvenanceEntity.query.filter(
                    ProvenanceEntity.generating_activity_id.in_(activity_ids)
                ).all()
            ]

            # Delete usage FIRST (FK: usage.entity_id -> entities)
            ProvenanceUsage.query.filter(
                ProvenanceUsage.activity_id.in_(activity_ids)
            ).delete(synchronize_session=False)

            if step4_entity_ids:
                ProvenanceDerivation.query.filter(
                    db.or_(
                        ProvenanceDerivation.derived_entity_id.in_(step4_entity_ids),
                        ProvenanceDerivation.source_entity_id.in_(step4_entity_ids)
                    )
                ).delete(synchronize_session=False)

                entities_deleted = ProvenanceEntity.query.filter(
                    ProvenanceEntity.id.in_(step4_entity_ids)
                ).delete(synchronize_session=False)
                provenance_deleted += entities_deleted

            activities_deleted = ProvenanceActivity.query.filter(
                ProvenanceActivity.id.in_(activity_ids)
            ).delete(synchronize_session=False)
            provenance_deleted += activities_deleted

        db.session.commit()

        logger.info(f"[RunAll] Cleared: {total_deleted} entities, {prompts_deleted} prompts, {provenance_deleted} provenance records")

        return {
            'entities_deleted': total_deleted,
            'prompts_deleted': prompts_deleted,
            'provenance_deleted': provenance_deleted
        }

    except Exception as e:
        logger.error(f"[RunAll] Error clearing data: {e}")
        db.session.rollback()
        return {'error': str(e)}


def _run_provisions(case_id: int, llm_client, get_all_case_entities) -> dict:
    """
    Run provisions extraction - SAME code as extract_provisions_streaming.
    """
    from app.services.nspe_references_parser import NSPEReferencesParser
    from app.services.universal_provision_detector import UniversalProvisionDetector
    from app.services.provision_grouper import ProvisionGrouper
    from app.services.provision_group_validator import ProvisionGroupValidator
    from app.services.code_provision_linker import CodeProvisionLinker

    prov = get_provenance_service()

    try:
        case = Document.query.get_or_404(case_id)

        # Get references HTML
        sections_dual = case.doc_metadata.get('sections_dual', {}) if case.doc_metadata else {}
        references_html = None
        for section_key, section_content in sections_dual.items():
            if 'reference' in section_key.lower():
                references_html = section_content.get('html', '') if isinstance(section_content, dict) else ''
                break

        if not references_html:
            return {'error': 'No references section found'}

        # Parse provisions
        parser = NSPEReferencesParser()
        provisions = parser.parse_references_html(references_html)
        logger.info(f"[RunAll] Parsed {len(provisions)} NSPE code provisions")

        # Get case sections for detection
        case_sections = {}
        for section_key in ['facts', 'discussion', 'question', 'conclusion']:
            if section_key in sections_dual:
                section_data = sections_dual[section_key]
                case_sections[section_key] = section_data.get('text', '') if isinstance(section_data, dict) else str(section_data)

        # Detect mentions
        detector = UniversalProvisionDetector()
        all_mentions = detector.detect_all_provisions(case_sections)
        logger.info(f"[RunAll] Detected {len(all_mentions)} provision mentions")

        # Group mentions
        grouper = ProvisionGrouper()
        grouped_mentions = grouper.group_mentions_by_provision(all_mentions, provisions)

        # Validate each provision
        validator = ProvisionGroupValidator(llm_client)
        for provision in provisions:
            code = provision['code_provision']
            mentions = grouped_mentions.get(code, [])

            if mentions:
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
            else:
                provision['relevant_excerpts'] = []

        # Link to entities
        all_entities = get_all_case_entities(case_id)
        linker = CodeProvisionLinker(llm_client)

        def format_entities(entities):
            return [
                {
                    'label': e.entity_label,
                    'definition': e.entity_definition or '',
                    'uri': e.rdf_json_ld.get('@id', '') if e.rdf_json_ld else ''
                }
                for e in entities
            ]

        provisions = linker.link_provisions_to_entities(
            provisions,
            roles=format_entities(all_entities.get('roles', [])),
            states=format_entities(all_entities.get('states', [])),
            resources=format_entities(all_entities.get('resources', [])),
            principles=format_entities(all_entities.get('principles', [])),
            obligations=format_entities(all_entities.get('obligations', [])),
            constraints=format_entities(all_entities.get('constraints', [])),
            capabilities=format_entities(all_entities.get('capabilities', [])),
            actions=format_entities(all_entities.get('actions', [])),
            events=format_entities(all_entities.get('events', [])),
            case_text_summary=f"Case {case_id}: {case.title}"
        )

        total_links = sum(len(p.get('applies_to', [])) for p in provisions)
        logger.info(f"[RunAll] Linked provisions to {total_links} entities")

        # Store provisions with provenance tracking
        session_id = str(uuid.uuid4())

        with prov.track_activity(
            activity_type='extraction',
            activity_name='step4_provisions',
            case_id=case_id,
            session_id=session_id,
            agent_type='extraction_service',
            agent_name='provisions_extractor',
            execution_plan={'provisions_count': len(provisions), 'entity_links': total_links}
        ) as activity:
            # Record the extraction results
            prov.record_extraction_results(
                results=[{
                    'code_provision': p.get('code_provision'),
                    'provision_text': p.get('provision_text'),
                    'excerpts_count': len(p.get('relevant_excerpts', [])),
                    'entity_links_count': len(p.get('applies_to', []))
                } for p in provisions],
                activity=activity,
                entity_type='extracted_provisions',
                metadata={'total_links': total_links}
            )

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
            logger.info(f"[RunAll] Stored {len(provisions)} provisions with provenance")

        return {
            'provisions_count': len(provisions),
            'entity_links': total_links
        }

    except Exception as e:
        logger.error(f"[RunAll] Provisions error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


def _run_precedents(case_id: int, llm_client) -> dict:
    """Run precedent case extraction -- same logic as extract_precedents_streaming."""
    import json as json_mod
    from app.routes.scenario_pipeline.step4 import (
        PRECEDENT_EXTRACTION_PROMPT, _update_cited_cases
    )

    prov = get_provenance_service()

    try:
        case = Document.query.get_or_404(case_id)

        # Gather case text
        sections_dual = case.doc_metadata.get('sections_dual', {}) if case.doc_metadata else {}
        case_text_parts = []
        for section_key in ['facts', 'discussion', 'question', 'conclusion']:
            section_data = sections_dual.get(section_key, {})
            text = section_data.get('text', '') if isinstance(section_data, dict) else str(section_data)
            if text:
                case_text_parts.append(f"=== {section_key.upper()} ===\n{text}")

        if not case_text_parts:
            return {'error': 'No case sections found'}

        case_text = '\n\n'.join(case_text_parts)
        prompt = PRECEDENT_EXTRACTION_PROMPT.format(case_text=case_text)

        # Call LLM (streaming to prevent WSL2 TCP idle timeout)
        from app.utils.llm_utils import streaming_completion
        raw_response = streaming_completion(
            llm_client, model=STEP4_DEFAULT_MODEL, max_tokens=4096, prompt=prompt
        )

        # Parse JSON
        cleaned = raw_response.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3].strip()
        precedents = json_mod.loads(cleaned)
        if not isinstance(precedents, list):
            precedents = []

        # Resolve case numbers
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

        # Store with provenance
        session_id = str(uuid.uuid4())

        with prov.track_activity(
            activity_type='extraction',
            activity_name='step4_precedents',
            case_id=case_id,
            session_id=session_id,
            agent_type='llm',
            agent_name='precedent_extractor',
            execution_plan={'precedents_count': len(precedents)}
        ) as activity:
            prov.record_extraction_results(
                results=[{
                    'caseCitation': p.get('caseCitation'),
                    'citationType': p.get('citationType'),
                    'resolved': p.get('resolved', False)
                } for p in precedents],
                activity=activity,
                entity_type='extracted_precedents',
                metadata={'total_precedents': len(precedents)}
            )

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

            # Save extraction prompt
            from app.models import ExtractionPrompt
            from datetime import datetime
            extraction_prompt = ExtractionPrompt(
                case_id=case_id,
                concept_type='precedent_case_reference',
                step_number=4,
                section_type=STEP4_SECTION_TYPE,
                prompt_text=prompt,
                llm_model=STEP4_DEFAULT_MODEL,
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
            logger.info(f"[RunAll] Stored {len(precedents)} precedent references with provenance")

        _update_cited_cases(case_id, precedents)

        return {
            'precedents_count': len(precedents),
            'resolved_count': sum(1 for p in precedents if p.get('resolved'))
        }

    except Exception as e:
        logger.error(f"[RunAll] Precedents error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


def _run_qc_unified(case_id: int, llm_client, get_all_case_entities) -> dict:
    """
    Run Q&C unified extraction - SAME code as extract_qc_unified_streaming.
    """
    from app.services.question_analyzer import QuestionAnalyzer
    from app.services.conclusion_analyzer import ConclusionAnalyzer
    from app.services.question_conclusion_linker import QuestionConclusionLinker

    prov = get_provenance_service()

    try:
        case = Document.query.get_or_404(case_id)

        # Load provisions
        provisions_records = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='code_provision_reference'
        ).all()
        provisions = [r.rdf_json_ld for r in provisions_records if r.rdf_json_ld]
        logger.info(f"[RunAll] Loaded {len(provisions)} provisions")

        # Get all entities
        all_entities = get_all_case_entities(case_id)

        # Get section text
        questions_text = ""
        conclusions_text = ""
        facts_text = ""
        if case.doc_metadata and 'sections_dual' in case.doc_metadata:
            sections = case.doc_metadata['sections_dual']
            if 'question' in sections:
                q_data = sections['question']
                questions_text = q_data.get('text', '') if isinstance(q_data, dict) else str(q_data)
            if 'conclusion' in sections:
                c_data = sections['conclusion']
                conclusions_text = c_data.get('text', '') if isinstance(c_data, dict) else str(c_data)
            if 'facts' in sections:
                f_data = sections['facts']
                facts_text = f_data.get('text', '') if isinstance(f_data, dict) else str(f_data)

        # Clear old Q&C
        TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_question'
        ).delete(synchronize_session=False)
        TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_conclusion'
        ).delete(synchronize_session=False)
        db.session.commit()

        # Extract questions
        question_analyzer = QuestionAnalyzer(llm_client)
        questions_result = question_analyzer.extract_questions_with_analysis(
            questions_text=questions_text,
            all_entities=all_entities,
            code_provisions=provisions,
            case_facts=facts_text,
            case_conclusion=conclusions_text
        )

        # Flatten all question types
        questions = []
        for q_type in ['board_explicit', 'implicit', 'principle_tension', 'theoretical', 'counterfactual']:
            for q in questions_result.get(q_type, []):
                q_dict = question_analyzer._question_to_dict(q) if hasattr(q, 'question_number') else q
                questions.append(q_dict)

        board_q_count = len(questions_result.get('board_explicit', []))
        logger.info(f"[RunAll] Extracted {board_q_count} Board + {len(questions) - board_q_count} analytical = {len(questions)} questions")

        # Get questions for conclusion context
        board_questions = [question_analyzer._question_to_dict(q) if hasattr(q, 'question_number') else q
                          for q in questions_result.get('board_explicit', [])]
        analytical_questions = [q for q in questions if q.get('question_type') != 'board_explicit']

        # Extract conclusions
        conclusion_analyzer = ConclusionAnalyzer(llm_client)
        conclusions_result = conclusion_analyzer.extract_conclusions_with_analysis(
            conclusions_text=conclusions_text,
            all_entities=all_entities,
            code_provisions=provisions,
            board_questions=board_questions,
            analytical_questions=analytical_questions,
            case_facts=facts_text
        )

        # Flatten all conclusion types
        conclusions = []
        for c_type in ['board_explicit', 'analytical_extension', 'question_response', 'principle_synthesis']:
            for c in conclusions_result.get(c_type, []):
                c_dict = conclusion_analyzer._conclusion_to_dict(c) if hasattr(c, 'conclusion_number') else c
                conclusions.append(c_dict)

        board_c_count = len(conclusions_result.get('board_explicit', []))
        logger.info(f"[RunAll] Extracted {board_c_count} Board + {len(conclusions) - board_c_count} analytical = {len(conclusions)} conclusions")

        # Link Q to C
        linker = QuestionConclusionLinker(llm_client)
        qc_links = linker.link_questions_to_conclusions(questions, conclusions)
        conclusions = linker.apply_links_to_conclusions(conclusions, qc_links)
        logger.info(f"[RunAll] Created {len(qc_links)} Q-C links")

        # Store everything with provenance tracking
        session_id = str(uuid.uuid4())

        # Track questions extraction
        with prov.track_activity(
            activity_type='extraction',
            activity_name='step4_questions',
            case_id=case_id,
            session_id=session_id,
            agent_type='llm_model',
            agent_name='question_analyzer',
            execution_plan={'board_count': board_q_count, 'analytical_count': len(questions) - board_q_count}
        ) as q_activity:
            # Record prompt and response if available
            q_prompt_text = getattr(question_analyzer, 'last_prompt', None)
            q_response_text = getattr(question_analyzer, 'last_response', None)

            prompt_entity = None
            if q_prompt_text:
                prompt_entity = prov.record_prompt(q_prompt_text[:10000], q_activity, entity_name='questions_extraction_prompt')
            if q_response_text:
                prov.record_response(q_response_text[:10000], q_activity, derived_from=prompt_entity, entity_name='questions_extraction_response')

            # Record extraction results
            prov.record_extraction_results(
                results=[{
                    'question_number': q['question_number'],
                    'question_type': q.get('question_type', 'unknown'),
                    'question_text': q['question_text'][:200]
                } for q in questions],
                activity=q_activity,
                entity_type='extracted_questions',
                metadata={'total': len(questions), 'board_explicit': board_q_count}
            )

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

        # Track conclusions extraction
        with prov.track_activity(
            activity_type='extraction',
            activity_name='step4_conclusions',
            case_id=case_id,
            session_id=session_id,
            agent_type='llm_model',
            agent_name='conclusion_analyzer',
            execution_plan={'board_count': board_c_count, 'analytical_count': len(conclusions) - board_c_count}
        ) as c_activity:
            # Record prompt and response if available
            c_prompt_text = getattr(conclusion_analyzer, 'last_prompt', None)
            c_response_text = getattr(conclusion_analyzer, 'last_response', None)

            prompt_entity = None
            if c_prompt_text:
                prompt_entity = prov.record_prompt(c_prompt_text[:10000], c_activity, entity_name='conclusions_extraction_prompt')
            if c_response_text:
                prov.record_response(c_response_text[:10000], c_activity, derived_from=prompt_entity, entity_name='conclusions_extraction_response')

            # Record extraction results
            prov.record_extraction_results(
                results=[{
                    'conclusion_number': c['conclusion_number'],
                    'conclusion_type': c.get('conclusion_type', 'unknown'),
                    'conclusion_text': c['conclusion_text'][:200]
                } for c in conclusions],
                activity=c_activity,
                entity_type='extracted_conclusions',
                metadata={'total': len(conclusions), 'board_explicit': board_c_count, 'qc_links': len(qc_links)}
            )

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
        logger.info(f"[RunAll] Stored {len(questions)} questions and {len(conclusions)} conclusions with provenance")

        # Save ExtractionPrompts for UI display (questions and conclusions)
        # Capture actual LLM prompts from analyzers
        try:
            # Get actual LLM prompt/response from question analyzer
            q_prompt_text = getattr(question_analyzer, 'last_prompt', None) or f'LLM extraction of {len(questions)} questions'
            q_response_text = getattr(question_analyzer, 'last_response', None) or ''

            questions_prompt = ExtractionPrompt(
                case_id=case_id,
                concept_type='ethical_question',
                step_number=4,
                section_type=STEP4_SECTION_TYPE,
                prompt_text=q_prompt_text[:10000] if q_prompt_text else 'Question extraction',
                llm_model=STEP4_DEFAULT_MODEL,
                extraction_session_id=session_id,
                raw_response=q_response_text[:10000] if q_response_text else '',
                results_summary=json.dumps({
                    'total': len(questions),
                    'board_explicit': board_q_count,
                    'analytical': len(questions) - board_q_count
                })
            )
            db.session.add(questions_prompt)

            # Get actual LLM prompt/response from conclusion analyzer
            c_prompt_text = getattr(conclusion_analyzer, 'last_prompt', None) or f'LLM extraction of {len(conclusions)} conclusions'
            c_response_text = getattr(conclusion_analyzer, 'last_response', None) or ''

            conclusions_prompt = ExtractionPrompt(
                case_id=case_id,
                concept_type='ethical_conclusion',
                step_number=4,
                section_type=STEP4_SECTION_TYPE,
                prompt_text=c_prompt_text[:10000] if c_prompt_text else 'Conclusion extraction',
                llm_model=STEP4_DEFAULT_MODEL,
                extraction_session_id=session_id,
                raw_response=c_response_text[:10000] if c_response_text else '',
                results_summary=json.dumps({
                    'total': len(conclusions),
                    'board_explicit': board_c_count,
                    'analytical': len(conclusions) - board_c_count,
                    'qc_links': len(qc_links)
                })
            )
            db.session.add(conclusions_prompt)
            db.session.commit()
            logger.info(f"[RunAll] Saved Q&C ExtractionPrompts with LLM prompts")
        except Exception as e:
            logger.warning(f"[RunAll] Could not save Q&C prompts: {e}")

        result = {
            'questions_count': len(questions),
            'conclusions_count': len(conclusions),
            'links_count': len(qc_links)
        }

        # Detect degraded results from connection failures
        warnings = []
        if getattr(question_analyzer, 'analytical_failed', False):
            warnings.append('Analytical question generation failed (connection error after retries)')
        if getattr(conclusion_analyzer, 'analytical_failed', False):
            warnings.append('Analytical conclusion generation failed (connection error after retries)')
        analytical_q = len(questions) - board_q_count
        analytical_c = len(conclusions) - board_c_count
        if analytical_q == 0 and board_q_count > 0:
            warnings.append(f'No analytical questions generated (only {board_q_count} board questions)')
        if analytical_c == 0 and board_c_count > 0:
            warnings.append(f'No analytical conclusions generated (only {board_c_count} board conclusions)')
        if warnings:
            result['warnings'] = warnings
            for w in warnings:
                logger.warning(f"[RunAll] Q&C WARNING: {w}")

        return result

    except Exception as e:
        logger.error(f"[RunAll] Q&C error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


def _run_transformation(case_id: int, llm_client) -> dict:
    """
    Run transformation classification - SAME code as extract_transformation_streaming.
    """
    from app.services.case_analysis.transformation_classifier import TransformationClassifier

    prov = get_provenance_service()

    try:
        case = Document.query.get_or_404(case_id)

        # Load Q&C
        questions = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_question'
        ).all()
        conclusions = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_conclusion'
        ).all()

        if not questions or not conclusions:
            return {'error': 'No Q&C found - run Q&C extraction first'}

        # Convert to format expected by classifier
        q_list = [
            {
                'question_number': r.rdf_json_ld.get('questionNumber', 0),
                'question_text': r.rdf_json_ld.get('questionText', r.entity_definition),
                'question_type': r.rdf_json_ld.get('questionType', 'unknown')
            }
            for r in questions if r.rdf_json_ld
        ]
        c_list = [
            {
                'conclusion_number': r.rdf_json_ld.get('conclusionNumber', 0),
                'conclusion_text': r.rdf_json_ld.get('conclusionText', r.entity_definition),
                'conclusion_type': r.rdf_json_ld.get('conclusionType', 'unknown')
            }
            for r in conclusions if r.rdf_json_ld
        ]

        # Get facts section
        facts_text = ""
        if case.doc_metadata and 'sections_dual' in case.doc_metadata:
            sections = case.doc_metadata['sections_dual']
            if 'facts' in sections:
                f_data = sections['facts']
                facts_text = f_data.get('text', '') if isinstance(f_data, dict) else str(f_data)

        # Get all entities for context
        from app.routes.scenario_pipeline.step4 import get_all_case_entities
        all_entities = get_all_case_entities(case_id)

        # Classify transformation
        classifier = TransformationClassifier(llm_client)
        result = classifier.classify(
            case_id=case_id,
            questions=q_list,
            conclusions=c_list,
            case_title=case.title,
            case_facts=facts_text,
            all_entities=all_entities
        )

        logger.info(f"[RunAll] Transformation type: {result.transformation_type} (confidence: {result.confidence})")

        # Save with provenance tracking
        session_id = str(uuid.uuid4())

        with prov.track_activity(
            activity_type='analysis',
            activity_name='step4_transformation',
            case_id=case_id,
            session_id=session_id,
            agent_type='llm_model',
            agent_name='transformation_classifier',
            execution_plan={'questions_count': len(q_list), 'conclusions_count': len(c_list)}
        ) as activity:
            # Record prompt and response if available
            prompt_entity = None
            if hasattr(classifier, 'last_prompt') and classifier.last_prompt:
                prompt_entity = prov.record_prompt(
                    classifier.last_prompt[:10000],
                    activity,
                    entity_name='transformation_prompt'
                )
            if hasattr(classifier, 'last_response') and classifier.last_response:
                prov.record_response(
                    classifier.last_response[:10000],
                    activity,
                    derived_from=prompt_entity,
                    entity_name='transformation_response'
                )

            # Record classification result
            prov.record_extraction_results(
                results={
                    'transformation_type': result.transformation_type,
                    'confidence': result.confidence
                },
                activity=activity,
                entity_type='transformation_classification',
                metadata={'transformation_type': result.transformation_type}
            )

            # Save ExtractionPrompt for UI
            if hasattr(classifier, 'last_prompt') and classifier.last_prompt:
                try:
                    transformation_prompt = ExtractionPrompt(
                        case_id=case_id,
                        concept_type='transformation_classification',
                        step_number=4,
                        section_type=STEP4_SECTION_TYPE,
                        prompt_text=classifier.last_prompt,
                        llm_model=STEP4_DEFAULT_MODEL,
                        extraction_session_id=session_id,
                        raw_response=getattr(classifier, 'last_response', ''),
                        results_summary=json.dumps({'transformation_type': result.transformation_type, 'confidence': result.confidence})
                    )
                    db.session.add(transformation_prompt)
                    db.session.commit()
                except Exception as e:
                    logger.warning(f"[RunAll] Could not save transformation prompt: {e}")

        return {
            'transformation_type': result.transformation_type,
            'confidence': result.confidence
        }

    except Exception as e:
        logger.error(f"[RunAll] Transformation error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


def _run_rich_analysis(case_id: int) -> dict:
    """
    Run rich analysis - SAME code as extract_rich_analysis_streaming.
    """
    from app.services.case_synthesizer import CaseSynthesizer

    prov = get_provenance_service()

    try:
        case = Document.query.get_or_404(case_id)
        synthesizer = CaseSynthesizer()

        # Build foundation
        foundation = synthesizer._build_entity_foundation(case_id)
        if not foundation or foundation.summary()['total'] == 0:
            return {'error': 'No entities found - run Passes 1-3 first'}

        # Load Q&C
        questions, conclusions = synthesizer._load_qc(case_id)
        if not questions and not conclusions:
            return {'error': 'No Q&C found - run Q&C extraction first'}

        # Load provisions
        provisions = synthesizer._load_provisions(case_id)

        # Run rich analysis (same as streaming endpoint)
        llm_traces = []

        # Causal-normative links
        causal_links = synthesizer._analyze_causal_normative_links(foundation, llm_traces)
        logger.info(f"[RunAll] Causal links: {len(causal_links)}")

        # Question emergence
        question_emergence = []
        for i, q in enumerate(questions):
            batch_results = synthesizer._analyze_question_batch([q], foundation, llm_traces, i)
            question_emergence.extend(batch_results)
        logger.info(f"[RunAll] Question emergence: {len(question_emergence)}")

        # Resolution patterns
        resolution_patterns = synthesizer._analyze_resolution_patterns(
            conclusions, questions, provisions, llm_traces
        )
        logger.info(f"[RunAll] Resolution patterns: {len(resolution_patterns)}")

        # Store rich analysis with provenance tracking
        session_id = str(uuid.uuid4())

        with prov.track_activity(
            activity_type='analysis',
            activity_name='step4_rich_analysis',
            case_id=case_id,
            session_id=session_id,
            agent_type='llm_model',
            agent_name='case_synthesizer',
            execution_plan={
                'causal_links': len(causal_links),
                'question_emergence': len(question_emergence),
                'resolution_patterns': len(resolution_patterns)
            }
        ) as activity:
            # Record combined prompts and responses from LLM traces
            combined_prompt = ""
            combined_response = ""
            for trace in llm_traces:
                combined_prompt += f"\n--- {trace.stage.upper()} ---\n{trace.prompt}\n"
                combined_response += f"\n--- {trace.stage.upper()} ---\n{trace.response}\n"

            prompt_entity = None
            if combined_prompt:
                prompt_entity = prov.record_prompt(
                    combined_prompt[:10000],
                    activity,
                    entity_name='rich_analysis_prompt'
                )
            if combined_response:
                prov.record_response(
                    combined_response[:10000],
                    activity,
                    derived_from=prompt_entity,
                    entity_name='rich_analysis_response'
                )

            # Record analysis results
            prov.record_extraction_results(
                results={
                    'causal_links': len(causal_links),
                    'question_emergence': len(question_emergence),
                    'resolution_patterns': len(resolution_patterns)
                },
                activity=activity,
                entity_type='rich_analysis_results',
                metadata={'llm_traces_count': len(llm_traces)}
            )

            # Store the actual rich analysis data
            synthesizer._store_rich_analysis(case_id, causal_links, question_emergence, resolution_patterns)

            # Save ExtractionPrompt for UI display
            try:
                saved_prompt = ExtractionPrompt.save_prompt(
                    case_id=case_id,
                    concept_type='rich_analysis',
                    prompt_text=combined_prompt,
                    raw_response=combined_response,
                    step_number=4,
                    section_type=STEP4_SECTION_TYPE,
                    llm_model=STEP4_DEFAULT_MODEL,
                    extraction_session_id=session_id
                )
                logger.info(f"[RunAll] Saved rich analysis prompt id={saved_prompt.id} with provenance")
            except Exception as e:
                logger.warning(f"[RunAll] Could not save rich analysis prompt: {e}")

        return {
            'causal_links': len(causal_links),
            'question_emergence': len(question_emergence),
            'resolution_patterns': len(resolution_patterns)
        }

    except Exception as e:
        logger.error(f"[RunAll] Rich analysis error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


def _run_phase3(case_id: int) -> dict:
    """
    Run Phase 3 decision synthesis - SAME code as synthesize_phase3_streaming.
    """
    from app.services.decision_point_synthesizer import synthesize_decision_points
    from app.services.case_synthesizer import CaseSynthesizer
    from app.services.entity_analysis.obligation_coverage_analyzer import get_obligation_coverage
    from app.services.entity_analysis.action_option_mapper import get_action_option_map

    prov = get_provenance_service()

    try:
        case = Document.query.get_or_404(case_id)
        synthesizer = CaseSynthesizer()

        # Load Q&C
        questions, conclusions = synthesizer._load_qc(case_id)
        if not questions:
            return {'error': 'No questions found - run Phase 2 extraction first'}

        # Load rich analysis data
        causal_links, question_emergence, resolution_patterns = synthesizer._load_rich_analysis(case_id)

        # Convert to dict format expected by synthesize_decision_points
        qe_dicts = [qe.to_dict() if hasattr(qe, 'to_dict') else vars(qe) for qe in question_emergence]
        rp_dicts = [rp.to_dict() if hasattr(rp, 'to_dict') else vars(rp) for rp in resolution_patterns]

        # Run E1-E2 separately to capture intermediate values for UI display
        e1_obligations = 0
        e1_decision_relevant = 0
        e2_action_sets = 0
        try:
            coverage = get_obligation_coverage(case_id, 'engineering')
            e1_obligations = len(coverage.obligations)
            e1_decision_relevant = coverage.decision_relevant_count
            logger.info(f"[RunAll] E1: {e1_obligations} obligations, {e1_decision_relevant} decision-relevant")

            action_map = get_action_option_map(case_id, 'engineering')
            e2_action_sets = len(action_map.action_sets)
            logger.info(f"[RunAll] E2: {e2_action_sets} action sets")
        except Exception as e:
            logger.warning(f"[RunAll] Could not get E1-E2 values: {e}")

        # Run Phase 3 synthesis
        result = synthesize_decision_points(
            case_id=case_id,
            questions=questions,
            conclusions=conclusions,
            question_emergence=qe_dicts,
            resolution_patterns=rp_dicts,
            domain='engineering',
            skip_llm=False
        )

        logger.info(f"[RunAll] Phase 3: {result.canonical_count} canonical decision points")

        # Save with provenance tracking
        session_id = result.extraction_session_id or str(uuid.uuid4())

        with prov.track_activity(
            activity_type='synthesis',
            activity_name='step4_phase3_decision',
            case_id=case_id,
            session_id=session_id,
            agent_type='llm_model' if result.llm_prompt else 'algorithmic',
            agent_name='decision_point_synthesizer',
            execution_plan={
                'questions_count': len(questions),
                'conclusions_count': len(conclusions),
                'question_emergence': len(qe_dicts),
                'resolution_patterns': len(rp_dicts)
            }
        ) as activity:
            # Build description of what Phase 3 did
            if result.llm_prompt:
                prompt_text = result.llm_prompt[:10000]
                raw_response = result.llm_response[:10000] if result.llm_response else ''
            else:
                prompt_text = f'Phase 3 Decision Point Synthesis (E1-E3 Algorithmic Composition)\n\nInput:\n- Questions: {len(questions)}\n- Conclusions: {len(conclusions)}\n- Question Emergence: {len(qe_dicts)}\n- Resolution Patterns: {len(rp_dicts)}\n\nE1-E3 Algorithm found 0 matching candidates.\nLLM fallback using causal_normative_links was attempted but produced no results.'
                raw_response = f'Phase 3 Result:\n- Algorithmic candidates: 0\n- Canonical decision points: {result.canonical_count}'

            # Record prompt and response
            prompt_entity = None
            if prompt_text:
                prompt_entity = prov.record_prompt(prompt_text, activity, entity_name='phase3_prompt')
            if raw_response:
                prov.record_response(raw_response, activity, derived_from=prompt_entity, entity_name='phase3_response')

            # Record synthesis results
            prov.record_extraction_results(
                results={
                    'canonical_count': result.canonical_count,
                    'candidates_count': result.candidates_count,
                    'high_alignment_count': result.high_alignment_count
                },
                activity=activity,
                entity_type='decision_synthesis_results',
                metadata={'used_llm': bool(result.llm_prompt)}
            )

            # Save ExtractionPrompt for UI
            try:
                extraction_prompt = ExtractionPrompt(
                    case_id=case_id,
                    concept_type='phase3_decision_synthesis',
                    step_number=4,
                    section_type=STEP4_SECTION_TYPE,
                    prompt_text=prompt_text,
                    llm_model=STEP4_DEFAULT_MODEL if result.llm_prompt else 'algorithmic',
                    extraction_session_id=session_id,
                    raw_response=raw_response,
                    results_summary=json.dumps({
                        'canonical_count': result.canonical_count,
                        'candidates_count': result.candidates_count,
                        'high_alignment_count': result.high_alignment_count,
                        'e1_obligations': e1_obligations,
                        'e1_decision_relevant': e1_decision_relevant,
                        'e2_action_sets': e2_action_sets,
                        'e3_candidates': result.candidates_count
                    })
                )
                db.session.add(extraction_prompt)
                db.session.commit()
                logger.info(f"[RunAll] Saved Phase 3 prompt with provenance (candidates: {result.candidates_count})")
            except Exception as e:
                logger.warning(f"[RunAll] Could not save Phase 3 prompt: {e}")

        return {
            'canonical_count': result.canonical_count,
            'candidates_count': result.candidates_count,
            'high_alignment_count': result.high_alignment_count,
            'e1_obligations': e1_obligations,
            'e1_decision_relevant': e1_decision_relevant,
            'e2_action_sets': e2_action_sets,
            'e3_candidates': result.candidates_count
        }

    except Exception as e:
        logger.error(f"[RunAll] Phase 3 error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


def _run_phase4(case_id: int) -> dict:
    """
    Run Phase 4 narrative construction - SAME code as construct_phase4_streaming.
    """
    from app.services.narrative import construct_phase4_narrative
    from app.services.precedent import update_precedent_features_from_phase4
    from app.services.case_synthesizer import CaseSynthesizer

    prov = get_provenance_service()

    try:
        case = Document.query.get_or_404(case_id)
        synthesizer = CaseSynthesizer()

        # Build foundation
        foundation = synthesizer._build_entity_foundation(case_id)
        if not foundation or foundation.summary()['total'] == 0:
            return {'error': 'No entities found - run Passes 1-3 first'}

        # Load Phase 2-3 data
        canonical_points = synthesizer.load_canonical_points(case_id)
        _, conclusions = synthesizer._load_qc(case_id)

        # Get transformation type
        transformation_record = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='transformation_classification'
        ).order_by(ExtractionPrompt.created_at.desc()).first()
        transformation_type = None
        if transformation_record and transformation_record.results_summary:
            try:
                summary = json.loads(transformation_record.results_summary) if isinstance(transformation_record.results_summary, str) else transformation_record.results_summary
                transformation_type = summary.get('transformation_type')
            except:
                pass

        # Load causal links (from database, as dicts)
        links_raw = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='causal_normative_link'
        ).all()
        causal_links = [
            link.rdf_json_ld if link.rdf_json_ld else {
                'action_uri': link.entity_uri or '',
                'action_label': link.entity_label,
                'obligation_uri': '',
                'obligation_label': ''
            }
            for link in links_raw
        ]

        # Run Phase 4 pipeline
        result = construct_phase4_narrative(
            case_id=case_id,
            foundation=foundation,
            canonical_points=canonical_points,
            conclusions=conclusions,
            transformation_type=transformation_type,
            causal_normative_links=causal_links,
            use_llm=True
        )

        logger.info(f"[RunAll] Phase 4: {len(result.narrative_elements.characters)} characters, {len(result.timeline.events)} events")

        # Save with provenance tracking
        session_id = str(uuid.uuid4())

        with prov.track_activity(
            activity_type='synthesis',
            activity_name='step4_phase4_narrative',
            case_id=case_id,
            session_id=session_id,
            agent_type='llm_model',
            agent_name='narrative_constructor',
            execution_plan={
                'canonical_points': len(canonical_points),
                'causal_links': len(causal_links),
                'transformation_type': transformation_type
            }
        ) as activity:
            # Extract actual LLM prompts from llm_traces
            actual_prompts = []
            actual_responses = []
            if hasattr(result, 'llm_traces') and result.llm_traces:
                for trace in result.llm_traces:
                    if isinstance(trace, dict):
                        if trace.get('prompt'):
                            stage = trace.get('stage', 'UNKNOWN')
                            actual_prompts.append(f"=== {stage} ===\n{trace['prompt']}")
                        if trace.get('response'):
                            stage = trace.get('stage', 'UNKNOWN')
                            actual_responses.append(f"=== {stage} ===\n{trace['response']}")

            prompt_text = "\n\n".join(actual_prompts) if actual_prompts else f"Phase 4 Narrative Construction - {len(result.stages_completed)} stages"
            response_text = "\n\n".join(actual_responses) if actual_responses else ""

            # Truncate to fit database field (10000 chars)
            if len(prompt_text) > 10000:
                prompt_text = prompt_text[:9950] + "\n... [truncated]"

            # Record prompt and response
            prompt_entity = None
            if prompt_text:
                prompt_entity = prov.record_prompt(prompt_text, activity, entity_name='phase4_prompt')
            if response_text:
                prov.record_response(response_text[:10000], activity, derived_from=prompt_entity, entity_name='phase4_response')

            # Record narrative results
            prov.record_extraction_results(
                results={
                    'characters_count': len(result.narrative_elements.characters),
                    'timeline_events_count': len(result.timeline.events),
                    'scenario_branches_count': len(result.scenario_seeds.branches),
                    'stages_completed': result.stages_completed
                },
                activity=activity,
                entity_type='narrative_construction_results',
                metadata={'transformation_type': transformation_type}
            )

            # Save ExtractionPrompt for UI
            extraction_prompt = ExtractionPrompt(
                case_id=case_id,
                concept_type='phase4_narrative',
                step_number=4,
                section_type=STEP4_SECTION_TYPE,
                prompt_text=prompt_text,
                llm_model=STEP4_DEFAULT_MODEL,
                extraction_session_id=session_id,
                raw_response=json.dumps(result.to_dict()),
                results_summary=json.dumps(result.summary())
            )
            db.session.add(extraction_prompt)

            # Save whole_case_synthesis to mark as complete
            synthesis_summary = {
                'characters_count': len(result.narrative_elements.characters),
                'timeline_events_count': len(result.timeline.events),
                'scenario_branches_count': len(result.scenario_seeds.branches)
            }
            whole_case_prompt = ExtractionPrompt(
                case_id=case_id,
                concept_type='whole_case_synthesis',
                step_number=4,
                section_type=STEP4_SECTION_TYPE,
                prompt_text='Complete Four-Phase Synthesis',
                llm_model=STEP4_DEFAULT_MODEL,
                extraction_session_id=session_id,
                raw_response=json.dumps(synthesis_summary),
                results_summary=json.dumps(synthesis_summary)
            )
            db.session.add(whole_case_prompt)
            db.session.commit()
            logger.info(f"[RunAll] Saved Phase 4 prompts with provenance")

        # Update precedent features
        try:
            update_precedent_features_from_phase4(
                case_id=case_id,
                narrative_result=result,
                transformation_type=transformation_type
            )
            logger.info(f"[RunAll] Updated precedent features from Phase 4")
        except Exception as e:
            logger.warning(f"[RunAll] Failed to update precedent features: {e}")

        return {
            'characters_count': len(result.narrative_elements.characters),
            'timeline_events': len(result.timeline.events),
            'branches_count': len(result.scenario_seeds.branches)
        }

    except Exception as e:
        logger.error(f"[RunAll] Phase 4 error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}
