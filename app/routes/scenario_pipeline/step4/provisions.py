"""
Step 4 Provisions Routes

Code provision extraction (streaming + individual), store_provisions_to_rdf, helpers.
"""

import json
import logging
import uuid
from datetime import datetime

from flask import request, jsonify, Response, stream_with_context

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.services.nspe_references_parser import NSPEReferencesParser
from app.services.universal_provision_detector import UniversalProvisionDetector
from app.services.provision_grouper import ProvisionGrouper
from app.services.provision_group_validator import ProvisionGroupValidator
from app.services.code_provision_linker import CodeProvisionLinker
from app.utils.llm_utils import get_llm_client
from app.utils.environment_auth import auth_required_for_llm

from app.routes.scenario_pipeline.step4.config import STEP4_POWERFUL_MODEL
from app.routes.scenario_pipeline.step4.helpers import get_all_case_entities

logger = logging.getLogger(__name__)


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


def extract_and_link_provisions(case_id: int, case: Document):
    """Part A: Extract code provisions and link to all entity types."""
    logger.info(f"Part A: Starting code provision extraction for case {case_id}")

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

    parser = NSPEReferencesParser()
    provisions = parser.parse_references_html(references_html)

    if not provisions:
        logger.warning(f"No provisions parsed for case {case_id}")
        return []

    logger.info(f"Parsed {len(provisions)} provisions")

    all_entities = get_all_case_entities(case_id)

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

    detector = UniversalProvisionDetector()
    all_mentions = detector.detect_all_provisions(case_sections)
    logger.info(f"Detected {len(all_mentions)} provision mentions")

    grouper = ProvisionGrouper()
    grouped_mentions = grouper.group_mentions_by_provision(all_mentions, provisions)

    llm_client = get_llm_client()
    validator = ProvisionGroupValidator(llm_client)

    for provision in provisions:
        code = provision['code_provision']
        mentions = grouped_mentions.get(code, [])

        if not mentions:
            provision['relevant_excerpts'] = []
            continue

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

    linker = CodeProvisionLinker(llm_client)

    def format_entities(entity_list):
        return [
            {'label': e.entity_label, 'definition': e.entity_definition}
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

    session_id = str(uuid.uuid4())

    TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='code_provision_reference'
    ).delete(synchronize_session=False)

    extraction_prompt = ExtractionPrompt(
        case_id=case_id,
        concept_type='code_provision_reference',
        step_number=4,
        section_type='references',
        prompt_text=linker.last_linking_prompt or 'Code provision extraction',
        llm_model=STEP4_POWERFUL_MODEL,
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


def register_provision_routes(bp):
    """Register provision extraction routes on the blueprint."""

    @bp.route('/case/<int:case_id>/extract_provisions_stream', methods=['POST'])
    @auth_required_for_llm
    def extract_provisions_streaming(case_id):
        """Extract code provisions with SSE streaming for real-time progress."""
        def sse_msg(data):
            return f"data: {json.dumps(data)}\n\n"

        def generate():
            try:
                case = Document.query.get_or_404(case_id)
                llm_client = get_llm_client()

                TemporaryRDFStorage.query.filter_by(
                    case_id=case_id,
                    extraction_type='code_provision_reference'
                ).delete(synchronize_session=False)
                db.session.commit()

                yield sse_msg({'stage': 'START', 'progress': 5, 'messages': ['Starting provisions extraction...']})

                sections_dual = case.doc_metadata.get('sections_dual', {}) if case.doc_metadata else {}
                references_html = None
                for section_key, section_content in sections_dual.items():
                    if 'reference' in section_key.lower():
                        references_html = section_content.get('html', '') if isinstance(section_content, dict) else ''
                        break

                if not references_html:
                    yield sse_msg({'stage': 'ERROR', 'progress': 100, 'messages': ['No references section found'], 'error': True})
                    return

                parser = NSPEReferencesParser()
                provisions = parser.parse_references_html(references_html)
                yield sse_msg({'stage': 'PARSED', 'progress': 15, 'messages': [f'Parsed {len(provisions)} NSPE code provisions']})

                case_sections = {}
                for section_key in ['facts', 'discussion', 'question', 'conclusion']:
                    if section_key in sections_dual:
                        section_data = sections_dual[section_key]
                        case_sections[section_key] = section_data.get('text', '') if isinstance(section_data, dict) else str(section_data)

                detector = UniversalProvisionDetector()
                all_mentions = detector.detect_all_provisions(case_sections)
                yield sse_msg({'stage': 'DETECTED', 'progress': 25, 'messages': [f'Detected {len(all_mentions)} provision mentions in case text']})

                grouper = ProvisionGrouper()
                grouped_mentions = grouper.group_mentions_by_provision(all_mentions, provisions)
                yield sse_msg({'stage': 'GROUPED', 'progress': 30, 'messages': ['Grouped mentions by provision code']})

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

                total_links = sum(len(p.get('applies_to', [])) for p in provisions)
                yield sse_msg({'stage': 'LINKED', 'progress': 85, 'messages': [f'Linked provisions to {total_links} entities']})

                yield sse_msg({'stage': 'STORING', 'progress': 90, 'messages': ['Storing provisions in database...']})
                session_id = str(uuid.uuid4())
                store_provisions_to_rdf(case_id, provisions, session_id)

                status_messages = []
                for p in provisions:
                    code = p.get('code_provision', 'Unknown')
                    excerpts = len(p.get('relevant_excerpts', []))
                    applies_to = len(p.get('applies_to', []))
                    status_messages.append(f'Provision {code}: {applies_to} entity links, {excerpts} excerpts')

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

    @bp.route('/case/<int:case_id>/extract_provisions', methods=['POST'])
    @auth_required_for_llm
    def extract_provisions_individual(case_id):
        """Extract code provisions individually (Part A)."""
        try:
            case = Document.query.get_or_404(case_id)

            TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='code_provision_reference'
            ).delete(synchronize_session=False)
            db.session.commit()

            provisions = extract_and_link_provisions(case_id, case)

            prompt_record = ExtractionPrompt.query.filter_by(
                case_id=case_id,
                concept_type='code_provision_reference'
            ).order_by(ExtractionPrompt.created_at.desc()).first()

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
                        for p in provisions[:10]
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
