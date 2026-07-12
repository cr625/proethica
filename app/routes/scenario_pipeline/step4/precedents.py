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
import re
import uuid
from datetime import datetime

from flask import jsonify, Response, stream_with_context

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.utils.llm_utils import get_llm_client, text_from_message, direct_call_params
from app.utils.llm_json_utils import parse_json_response
from app.utils.environment_auth import auth_required_for_llm
from app.routes.scenario_pipeline.step4.config import (
    STEP4_SECTION_TYPE, STEP4_DEFAULT_MODEL,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

# Citation treatment vocabulary. AUTHORITATIVE SOURCE:
# OntServe/ontologies/proethica-cases.ttl (skos:definition on the
# CitationTreatment concepts; browsable at /ontology/proethica-cases).
# tests/unit/test_precedent_vocabulary.py asserts this dict matches the
# ontology, so edits here or there fail the suite instead of drifting.
# The terms follow the treatment-signal convention of citator services
# (Shepard's); the correspondence is recorded per term in the ontology.
CITATION_TREATMENTS = {
    'supporting': 'The Board cites the prior case as authority for the position taken in the present analysis, applying its principle to reach the same result.',
    'distinguishing': 'The Board cites the prior case to show that its facts or principle do not govern the present case, explaining the material difference.',
    'analogizing': 'The Board cites the prior case as a parallel fact situation and reasons from the similarity, without treating it as controlling authority.',
    'overruling': 'The Board cites the prior case as superseded: its holding is disapproved, limited, or no longer reflects the Code as applied.',
}

def _treatments_block() -> str:
    """The indented treatment-term lines injected into the prompt template."""
    return "\n".join(
        f'   - "{term}": {defn}' for term, defn in CITATION_TREATMENTS.items())


def build_precedent_prompt(case_text: str) -> str:
    """Render the precedent-extraction prompt from the seeded template.

    Render-time replacement for the former module-level
    PRECEDENT_EXTRACTION_PROMPT constant (which baked the treatments block
    in at import time). Used by both routes here and by
    step4_synthesis_service._run_precedents.
    """
    from app.services.step4_synthesis.template_loader import get_step4_template
    return get_step4_template('step4_precedents').render(
        case_text=case_text,
        citation_treatments_block=_treatments_block(),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BER_NUMBER = re.compile(r'\b\d{2}-\d{1,2}\b')


def normalize_precedents(precedents: list) -> list:
    """Split joint citations into one entry per case number.

    The board frequently cites cases jointly ("Cases 65-9 and 73-9") and the
    LLM intermittently emits ONE entry with caseNumber "65-9, 73-9" despite
    the one-number-per-entry prompt rule (2026-07-09 Precedents audit,
    case 4). A combined number can never resolve to an internal document, so
    the split is enforced deterministically here: entries whose caseNumber
    carries several BER numbers become one entry per number with the shared
    context duplicated. Entries with zero or one number pass through.
    """
    out = []
    for p in precedents:
        if not isinstance(p, dict):
            continue
        numbers = _BER_NUMBER.findall(str(p.get('caseNumber', '')))
        if len(numbers) <= 1:
            out.append(p)
            continue
        for n in numbers:
            split = dict(p)
            split['caseNumber'] = n
            split['caseCitation'] = f"BER Case {n}"
            out.append(split)
    return out


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
                prompt = build_precedent_prompt(case_text)
                yield sse_msg({'stage': 'PROMPTING', 'progress': 25, 'messages': ['Sending to LLM for precedent analysis...']})

                # Call LLM
                response = llm_client.messages.create(
                    **direct_call_params(STEP4_DEFAULT_MODEL, max_tokens=4096, temperature=0.1),
                    messages=[{'role': 'user', 'content': prompt}]
                )
                raw_response = text_from_message(response)
                yield sse_msg({'stage': 'RECEIVED', 'progress': 60, 'messages': ['LLM response received, parsing...']})

                # Parse JSON response
                precedents = parse_json_response(raw_response, context="precedent_extraction")
                if precedents is None:
                    logger.error(f"Failed to parse precedent extraction response: {raw_response[:500]}")
                    yield sse_msg({'stage': 'ERROR', 'progress': 100,
                                   'messages': ['Failed to parse LLM response as JSON'], 'error': True})
                    return

                precedents = normalize_precedents(precedents)
                yield sse_msg({'stage': 'PARSED', 'progress': 70,
                               'messages': [f'Found {len(precedents)} cited precedent cases']})

                # Attempt to resolve case numbers to internal document IDs
                for p in precedents:
                    case_number = p.get('caseNumber', '')
                    if case_number:
                        try:
                            resolved = Document.query.filter(
                                Document.doc_metadata['case_number'].astext == case_number,
                                # Shadow-gate clones share the gold's case_number; a
                                # precedent must never bind to a shadow document
                                # (deleted at shadow-cleanup -> dangling internalCaseId).
                                Document.doc_metadata['shadow_of'].astext.is_(None)
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
                        extraction_model=STEP4_DEFAULT_MODEL,
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
            prompt = build_precedent_prompt(case_text)

            # Call LLM
            response = llm_client.messages.create(
                **direct_call_params(STEP4_DEFAULT_MODEL, max_tokens=4096, temperature=0.1),
                messages=[{'role': 'user', 'content': prompt}]
            )
            raw_response = text_from_message(response)

            # Parse
            precedents = parse_json_response(raw_response, context="precedent_extraction")
            if precedents is None:
                precedents = []
            precedents = normalize_precedents(precedents)

            # Resolve + store
            session_id = str(uuid.uuid4())
            for p in precedents:
                case_number = p.get('caseNumber', '')
                if case_number:
                    try:
                        resolved = Document.query.filter(
                            Document.doc_metadata['case_number'].astext == case_number,
                            # Shadow-gate clones share the gold's case_number; a
                            # precedent must never bind to a shadow document
                            # (deleted at shadow-cleanup -> dangling internalCaseId).
                            Document.doc_metadata['shadow_of'].astext.is_(None)
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
                    extraction_model=STEP4_DEFAULT_MODEL,
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
