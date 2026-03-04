"""
Entity Review Views

Review pages for displaying extracted entities across passes and sessions.
"""

import logging
import os

from flask import render_template, request, redirect, url_for, flash
from app.models import Document, db, TemporaryRDFStorage
from app.services.case_entity_storage_service import CaseEntityStorageService
from app.utils.environment_auth import auth_optional

logger = logging.getLogger(__name__)


def register_review_view_routes(bp):
    """Register entity review view routes on the given blueprint."""

    @bp.route('/case/<int:case_id>/entities/review/all')
    @auth_optional
    def review_all_case_entities(case_id):
        """Display summary and links to ALL pass reviews."""
        try:
            case_doc = Document.query.get(case_id)
            if not case_doc:
                flash(f'Case {case_id} not found', 'error')
                return redirect(url_for('index.index'))

            # Get entity counts from Step 4 helper
            from app.routes.scenario_pipeline.step4.helpers import get_entities_summary
            entities_summary = get_entities_summary(case_id)

            return render_template(
                'scenarios/entity_review_all.html',
                case=case_doc,
                entities_summary=entities_summary
            )

        except Exception as e:
            logger.error(f"Error displaying all entity review for case {case_id}: {e}")
            flash(f'Error loading entity review: {str(e)}', 'error')
            return redirect(url_for('index.index'))

    @bp.route('/case/<int:case_id>/extraction_history')
    @bp.route('/case/<int:case_id>/extraction_history/<int:step_number>')
    @bp.route('/case/<int:case_id>/extraction_history/<int:step_number>/<section_type>')
    @auth_optional
    def extraction_history(case_id, step_number=None, section_type=None):
        """Redirect to unified provenance view."""
        params = {}
        if step_number:
            params['step'] = step_number
        elif request.args.get('steps'):
            # Take first step from comma-separated list
            try:
                params['step'] = int(request.args['steps'].split(',')[0].strip())
            except (ValueError, IndexError):
                pass
        if section_type:
            params['section'] = section_type
        if request.args.get('concept_type'):
            params['concept'] = request.args['concept_type']
        return redirect(url_for('provenance.case_provenance', case_id=case_id, **params))

    @bp.route('/case/<int:case_id>/entities/review')
    @bp.route('/case/<int:case_id>/entities/review/pass1')  # Explicit Pass 1
    @auth_optional  # Allow viewing without auth
    def review_case_entities(case_id, section_type='facts'):
        """Display PASS 1 (Contextual Framework) extracted entities for a case.

        Args:
            case_id: The case ID
            section_type: Which section to show entities from ('facts' or 'discussion')
        """
        try:
            # Get section_type from query param if provided
            from flask import request
            section_type = request.args.get('section_type', 'facts')

            # Get case information
            case_doc = Document.query.get(case_id)
            if not case_doc:
                flash(f'Case {case_id} not found', 'error')
                return redirect(url_for('index.index'))

            # Pass 1 base types -- extended below for questions/conclusions sections
            pass1_types = ['roles', 'states', 'resources']

            # For Questions section, also include special extraction types
            if section_type == 'questions':
                pass1_types.extend([
                    'questions_entity_refs',
                    'roles_new_from_questions',
                    'states_new_from_questions',
                    'resources_new_from_questions',
                    'roles_matching',
                    'states_matching',
                    'resources_matching'
                ])

            # For Conclusions section, also include special extraction types
            if section_type == 'conclusions':
                pass1_types.extend([
                    'conclusions_entity_refs',
                    'roles_new_from_conclusions',
                    'states_new_from_conclusions',
                    'resources_new_from_conclusions',
                    'roles_matching',
                    'states_matching',
                    'resources_matching'
                ])

            # Query RDF entities by extraction_type, then filter by section_sources
            all_rdf_entities = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.extraction_type.in_(pass1_types)
            ).all()

            # Filter to entities whose section_sources includes the requested section.
            # Before discussion extraction runs, this returns empty for discussion.
            if section_type:
                all_rdf_entities = [
                    e for e in all_rdf_entities
                    if section_type in (e.rdf_json_ld or {}).get('section_sources', [])
                ]
            logger.info(f"Retrieved {len(all_rdf_entities)} RDF entities for pass 1 ({section_type})")

            rdf_by_type = {
                'roles': {'classes': [], 'individuals': [], 'relationships': []},
                'states': {'classes': [], 'individuals': [], 'relationships': []},
                'resources': {'classes': [], 'individuals': [], 'relationships': []}
            }

            # Count only Pass 1 entities
            pass1_entity_count = 0

            for entity in all_rdf_entities:
                extraction_type = entity.extraction_type or 'unknown'
                storage_type = entity.storage_type

                # Map Questions-specific types to their base types
                base_type = extraction_type

                # For questions_entity_refs or conclusions_entity_refs, check the entityType field in JSON
                if extraction_type in ['questions_entity_refs', 'conclusions_entity_refs'] and entity.rdf_json_ld:
                    json_entity_type = entity.rdf_json_ld.get('entityType', '')
                    json_entity_type_lower = json_entity_type.lower()
                    logger.info(f"Processing entity_ref: {entity.entity_label}, JSON entityType: {json_entity_type}, storage_type: {storage_type}")
                    if 'role' in json_entity_type_lower:
                        base_type = 'roles'
                    elif 'state' in json_entity_type_lower:
                        base_type = 'states'
                    elif 'resource' in json_entity_type_lower:
                        base_type = 'resources'
                    else:
                        base_type = 'roles'  # Default to roles for backward compatibility
                    logger.info(f"  -> Mapped to base_type: {base_type}")
                elif 'roles' in extraction_type:
                    base_type = 'roles'
                elif 'states' in extraction_type:
                    base_type = 'states'
                elif 'resources' in extraction_type:
                    base_type = 'resources'

                # Case-insensitive check for extraction_type
                if extraction_type.lower() in pass1_types:
                    pass1_entity_count += 1
                    if storage_type == 'class':
                        rdf_by_type[base_type]['classes'].append(entity.to_dict())
                    elif storage_type == 'individual':
                        rdf_by_type[base_type]['individuals'].append(entity.to_dict())
                    elif storage_type == 'relationship':
                        rdf_by_type[base_type]['relationships'].append(entity.to_dict())
                        logger.info(f"  -> Added to {base_type}/relationships")

            # Get all entities grouped by section (old format for backward compatibility)
            entities_by_section = CaseEntityStorageService.get_all_case_entities(
                case_id=case_id,
                status='pending',
                group_by_section=True
            )

            # Get section information
            sections_info = CaseEntityStorageService.NSPE_SECTIONS

            # Prepare data for template
            section_data = {}
            total_entities = 0

            for section_type, entities in entities_by_section.items():
                if section_type == 'all':
                    continue

                section_data[section_type] = {
                    'info': sections_info.get(section_type, {
                        'label': section_type.title(),
                        'description': 'Unknown section type',
                        'primary_entities': []
                    }),
                    'entities': entities,
                    'count': len(entities),
                    'selected_count': sum(1 for e in entities if e.concept_data.get('selected', False))
                }
                total_entities += len(entities)

            # Detect cross-section duplicates
            # Get entities from OTHER sections for comparison
            from app.models import ExtractionPrompt
            other_sections = ['facts', 'discussion', 'questions', 'conclusions', 'dissenting_opinion']
            other_sections.remove(section_type) if section_type in other_sections else None

            cross_section_entities = {}
            for other_section in other_sections:
                other_prompts = ExtractionPrompt.query.filter_by(
                    case_id=case_id,
                    section_type=other_section
                ).all()
                other_session_ids = {p.extraction_session_id for p in other_prompts if p.extraction_session_id}

                if other_session_ids:
                    other_entities = TemporaryRDFStorage.query.filter(
                        TemporaryRDFStorage.case_id == case_id,
                        TemporaryRDFStorage.extraction_session_id.in_(other_session_ids)
                    ).all()

                    cross_section_entities[other_section] = {
                        e.entity_label.lower(): {
                            'label': e.entity_label,
                            'section': other_section,
                            'type': e.entity_type,
                            'id': e.id
                        } for e in other_entities
                    }

            # Add cross-section duplicate info to each entity
            for concept_type in rdf_by_type:
                for entity in rdf_by_type[concept_type]['classes']:
                    entity['cross_section_matches'] = []
                    entity_label_lower = entity['entity_label'].lower()

                    for other_section, other_entities in cross_section_entities.items():
                        if entity_label_lower in other_entities:
                            entity['cross_section_matches'].append({
                                'section': other_section,
                                'section_label': other_section.replace('_', ' ').title()
                            })

                for entity in rdf_by_type[concept_type]['individuals']:
                    entity['cross_section_matches'] = []
                    entity_label_lower = entity['entity_label'].lower()

                    for other_section, other_entities in cross_section_entities.items():
                        if entity_label_lower in other_entities:
                            entity['cross_section_matches'].append({
                                'section': other_section,
                                'section_label': other_section.replace('_', ' ').title()
                            })

            # Prepare RDF data organized by concept type
            rdf_data = {
                'by_type': rdf_by_type,
                'total_rdf_entities': pass1_entity_count  # Use Pass 1 count, not all entities
            }

            # For Conclusions section, also get Question->Conclusion links
            question_conclusion_links = []
            if section_type == 'conclusions' and section_session_ids:
                qc_links = TemporaryRDFStorage.query.filter(
                    TemporaryRDFStorage.case_id == case_id,
                    TemporaryRDFStorage.extraction_type == 'question_conclusion_link',
                    TemporaryRDFStorage.extraction_session_id.in_(section_session_ids)
                ).all()

                for link in qc_links:
                    if link.rdf_json_ld:
                        question_conclusion_links.append({
                            'question_number': link.rdf_json_ld.get('questionNumber'),
                            'question_text': link.rdf_json_ld.get('questionText', ''),
                            'conclusion_text': link.rdf_json_ld.get('conclusionText', ''),
                            'confidence': link.rdf_json_ld.get('confidence', 0),
                            'reasoning': link.rdf_json_ld.get('reasoning', '')
                        })

                logger.info(f"Found {len(question_conclusion_links)} Question->Conclusion links")

            # Fetch existing classes from OntServe for reference display
            ontserve_classes = {
                'roles': [],
                'states': [],
                'resources': []
            }
            try:
                from app.services.external_mcp_client import get_external_mcp_client
                mcp_client = get_external_mcp_client()

                # Fetch existing role classes
                existing_roles = mcp_client.get_all_role_entities()
                for role in existing_roles:
                    ontserve_classes['roles'].append({
                        'label': role.get('label', ''),
                        'description': role.get('description', role.get('comment', '')),
                        'uri': role.get('uri', '')
                    })

                # Fetch existing state classes
                existing_states = mcp_client.get_all_state_entities()
                for state in existing_states:
                    ontserve_classes['states'].append({
                        'label': state.get('label', ''),
                        'description': state.get('description', state.get('comment', '')),
                        'uri': state.get('uri', '')
                    })

                # Fetch existing resource classes
                existing_resources = mcp_client.get_all_resource_entities()
                for resource in existing_resources:
                    ontserve_classes['resources'].append({
                        'label': resource.get('label', ''),
                        'description': resource.get('description', resource.get('comment', '')),
                        'uri': resource.get('uri', '')
                    })

                logger.info(f"Fetched OntServe classes: {len(ontserve_classes['roles'])} roles, "
                           f"{len(ontserve_classes['states'])} states, {len(ontserve_classes['resources'])} resources")
            except Exception as e:
                logger.warning(f"Could not fetch OntServe classes: {e}")

            # Get pipeline status for navigation
            from app.services.pipeline_status_service import PipelineStatusService
            pipeline_status = PipelineStatusService.get_step_status(case_id)

            ontserve_web_url = os.environ.get('ONTSERVE_WEB_URL', 'http://localhost:5003')

            return render_template(
                'scenarios/entity_review.html',
                case=case_doc,
                section_data=section_data,
                total_entities=total_entities,
                sections_info=sections_info,
                rdf_data=rdf_data,
                section_type=section_type,  # Pass section_type to template
                section_label=section_type.replace('_', ' ').title(),  # 'facts' -> 'Facts', 'discussion' -> 'Discussion'
                question_conclusion_links=question_conclusion_links,  # Pass Q->C links for Conclusions section
                ontserve_classes=ontserve_classes,  # Pass OntServe classes for reference
                pipeline_status=pipeline_status,  # For navigation toggle
                ontserve_web_url=ontserve_web_url
            )

        except Exception as e:
            logger.error(f"Error displaying entity review for case {case_id}: {e}")
            flash(f'Error loading entity review: {str(e)}', 'error')
            return redirect(url_for('index.index'))

    @bp.route('/case/<int:case_id>/entities/review/pass2')
    @auth_optional  # Allow viewing without auth
    def review_case_entities_pass2(case_id, section_type=None):
        """Display PASS 2 (Normative Requirements) extracted entities for a case.

        Args:
            case_id: The case ID
            section_type: Optional section filter ('facts', 'discussion', 'questions', 'conclusions', 'references')
        """
        try:
            # Get case information
            case_doc = Document.query.get(case_id)
            if not case_doc:
                flash(f'Case {case_id} not found', 'error')
                return redirect(url_for('index.index'))

            # Get section_type from query params if not provided as argument
            if section_type is None:
                section_type = request.args.get('section_type')

            # Pass 2 extraction types
            pass2_types = ['principles', 'obligations', 'constraints', 'capabilities']

            # Query Pass 2 entities, then filter by section_sources
            all_rdf_entities = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.extraction_type.in_(pass2_types)
            ).all()

            # Filter to entities whose section_sources includes the requested section
            if section_type:
                all_rdf_entities = [
                    e for e in all_rdf_entities
                    if section_type in (e.rdf_json_ld or {}).get('section_sources', [])
                ]

            # Group entities by extraction_type and storage_type
            # PASS 2 entities only (Normative Requirements)
            rdf_by_type = {
                'principles': {'classes': [], 'individuals': []},
                'obligations': {'classes': [], 'individuals': []},
                'constraints': {'classes': [], 'individuals': []},
                'capabilities': {'classes': [], 'individuals': []}
            }

            for entity in all_rdf_entities:
                extraction_type = entity.extraction_type or 'unknown'
                storage_type = entity.storage_type

                if extraction_type in rdf_by_type:
                    if storage_type == 'class':
                        rdf_by_type[extraction_type]['classes'].append(entity.to_dict())
                    elif storage_type == 'individual':
                        rdf_by_type[extraction_type]['individuals'].append(entity.to_dict())

            # Count total RDF entities for this pass
            total_rdf_entities = sum(
                len(type_data['classes']) + len(type_data['individuals'])
                for type_data in rdf_by_type.values()
            )

            # Check for any entities
            has_entities = total_rdf_entities > 0

            # Prepare RDF data with total count
            rdf_data = {
                'by_type': rdf_by_type,
                'total_rdf_entities': total_rdf_entities
            }

            # Determine section display name
            section_display = section_type.capitalize() if section_type else "All Sections"

            # Fetch existing classes from OntServe for Pass 2 concept types
            ontserve_classes = {
                'principles': [],
                'obligations': [],
                'constraints': [],
                'capabilities': []
            }
            try:
                from app.services.external_mcp_client import get_external_mcp_client
                mcp_client = get_external_mcp_client()

                # Fetch existing principle classes
                existing_principles = mcp_client.get_all_principle_entities()
                for p in existing_principles:
                    ontserve_classes['principles'].append({
                        'label': p.get('label', ''),
                        'description': p.get('description', p.get('comment', '')),
                        'uri': p.get('uri', '')
                    })

                # Fetch existing obligation classes
                existing_obligations = mcp_client.get_all_obligation_entities()
                for o in existing_obligations:
                    ontserve_classes['obligations'].append({
                        'label': o.get('label', ''),
                        'description': o.get('description', o.get('comment', '')),
                        'uri': o.get('uri', '')
                    })

                # Fetch existing constraint classes
                existing_constraints = mcp_client.get_all_constraint_entities()
                for c in existing_constraints:
                    ontserve_classes['constraints'].append({
                        'label': c.get('label', ''),
                        'description': c.get('description', c.get('comment', '')),
                        'uri': c.get('uri', '')
                    })

                # Fetch existing capability classes
                existing_capabilities = mcp_client.get_all_capability_entities()
                for cap in existing_capabilities:
                    ontserve_classes['capabilities'].append({
                        'label': cap.get('label', ''),
                        'description': cap.get('description', cap.get('comment', '')),
                        'uri': cap.get('uri', '')
                    })

                logger.info(f"Fetched OntServe Pass 2 classes: {len(ontserve_classes['principles'])} principles, "
                           f"{len(ontserve_classes['obligations'])} obligations, {len(ontserve_classes['constraints'])} constraints, "
                           f"{len(ontserve_classes['capabilities'])} capabilities")
            except Exception as e:
                logger.warning(f"Could not fetch OntServe Pass 2 classes: {e}")

            # Get pipeline status for navigation
            from app.services.pipeline_status_service import PipelineStatusService
            pipeline_status = PipelineStatusService.get_step_status(case_id)

            ontserve_web_url = os.environ.get('ONTSERVE_WEB_URL', 'http://localhost:5003')

            # Return the entity review page for Pass 2
            return render_template('scenarios/entity_review_pass2.html',
                                 case=case_doc,
                                 rdf_data=rdf_data,
                                 section_data={},  # Empty for new RDF format
                                 has_entities=has_entities,
                                 pass_number=2,
                                 pass_name="Normative Requirements",
                                 section_type=section_type,
                                 section_display=section_display,
                                 ontserve_classes=ontserve_classes,
                                 pipeline_status=pipeline_status,
                                 ontserve_web_url=ontserve_web_url)

        except Exception as e:
            logger.error(f"Error displaying Pass 2 entity review for case {case_id}: {e}")
            flash(f'Error loading entity review: {str(e)}', 'error')
            return redirect(url_for('index.index'))

    # DEPRECATED: Old Pass 3 review route - replaced by review_enhanced_temporal
    # Route removed as entity_review_pass3.html template has been archived
    # Use /case/<int:case_id>/enhanced_temporal/review instead

    @bp.route('/case/<int:case_id>/entities/session/<session_id>')
    def review_session_entities(case_id, session_id):
        """Display entities for a specific extraction session."""
        try:
            # Get case information
            case_doc = Document.query.get(case_id)
            if not case_doc:
                flash(f'Case {case_id} not found', 'error')
                return redirect(url_for('index.index'))

            # Get session entities
            entities = CaseEntityStorageService.get_case_session_entities(
                case_id=case_id,
                session_id=session_id,
                status='pending'
            )

            if not entities:
                flash(f'No entities found for session {session_id}', 'warning')
                return redirect(url_for('entity_review.review_case_entities', case_id=case_id))

            # Get session summary
            session_summary = CaseEntityStorageService.create_entity_extraction_session_summary(
                case_id=case_id,
                session_id=session_id
            )

            return render_template(
                'scenarios/session_review.html',
                case=case_doc,
                entities=entities,
                session_summary=session_summary,
                session_id=session_id
            )

        except Exception as e:
            logger.error(f"Error displaying session review for {session_id}: {e}")
            flash(f'Error loading session review: {str(e)}', 'error')
            return redirect(url_for('entity_review.review_case_entities', case_id=case_id))
