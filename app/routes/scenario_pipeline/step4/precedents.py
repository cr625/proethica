"""
Step 4 Precedent Case Reference Extraction (Part A2)

Identifies prior BER cases, decisions, or rulings cited by the board in
their discussion.  Each cited case is stored as a precedent_case_reference
entity with citation type (supporting, distinguishing, analogizing,
overruling) and the principle the cited case establishes.

Resolved case numbers are cross-referenced against internal Document
records so downstream tools can link to the full case text.
"""

import json as json_mod
import logging
import uuid
from datetime import datetime

from flask import jsonify, Response, stream_with_context

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.utils.llm_utils import get_llm_client
from app.utils.llm_json_utils import parse_json_response
from app.utils.environment_auth import auth_required_for_llm
from app.routes.scenario_pipeline.step4.config import (
    STEP4_SECTION_TYPE, STEP4_DEFAULT_MODEL,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_precedent_routes(bp):
    """Register precedent case reference extraction routes on the blueprint.

    Args:
        bp: The Flask Blueprint to register routes on
    """

    @bp.route('/case/<int:case_id>/extract_precedents_stream', methods=['POST'])
    @auth_required_for_llm
    def extract_precedents_streaming(case_id):
        """Extract precedent case references with SSE streaming for real-time progress."""

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
                    model=STEP4_DEFAULT_MODEL,
                    max_tokens=4096,
                    temperature=0.1,
                    messages=[{'role': 'user', 'content': prompt}]
                )
                raw_response = response.content[0].text
                yield sse_msg({'stage': 'RECEIVED', 'progress': 60, 'messages': ['LLM response received, parsing...']})

                # Parse JSON response
                precedents = parse_json_response(raw_response, context="precedent_extraction")
                if precedents is None:
                    logger.error(f"Failed to parse precedent extraction response: {raw_response[:500]}")
                    yield sse_msg({'stage': 'ERROR', 'progress': 100,
                                   'messages': ['Failed to parse LLM response as JSON'], 'error': True})
                    return

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
                model=STEP4_DEFAULT_MODEL,
                max_tokens=4096,
                temperature=0.1,
                messages=[{'role': 'user', 'content': prompt}]
            )
            raw_response = response.content[0].text

            # Parse
            precedents = parse_json_response(raw_response, context="precedent_extraction")
            if precedents is None:
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
