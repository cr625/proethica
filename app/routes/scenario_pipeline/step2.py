"""
Step 2: Normative Requirements Pass for Facts Section
Shows the facts section and provides extraction for Pass 2: Principles, Obligations, Constraints, and Capabilities.
Based on Chapter 2 literature: Capabilities are essential for norm competence (Tolmeijer et al. 2021) - 
agents need capabilities to store, recognize, apply, and resolve normative requirements.
"""

import logging
import json
import uuid
from datetime import datetime
from contextlib import nullcontext
from flask import render_template, request, jsonify, redirect, url_for, flash
from app.models import Document, db
from app.routes.scenario_pipeline.overview import _format_section_for_llm
from app.services.extraction.enhanced_prompts_principles import EnhancedPrinciplesExtractor, create_enhanced_principles_prompt
from app.services.extraction.enhanced_prompts_obligations import EnhancedObligationsExtractor, create_enhanced_obligations_prompt
from app.services.extraction.enhanced_prompts_constraints import EnhancedConstraintsExtractor, create_enhanced_constraints_prompt
from app.services.extraction.enhanced_prompts_states_capabilities import EnhancedCapabilitiesExtractor, create_enhanced_capabilities_prompt
from app.utils.llm_utils import get_llm_client

# Import provenance services
try:
    from app.services.provenance_versioning_service import get_versioned_provenance_service
    USE_VERSIONED_PROVENANCE = True
except ImportError:
    from app.services.provenance_service import get_provenance_service
    USE_VERSIONED_PROVENANCE = False

logger = logging.getLogger(__name__)

# Function to exempt specific routes from CSRF after app initialization
def init_step2_csrf_exemption(app):
    """Exempt Step 2 normative pass routes from CSRF protection"""
    if hasattr(app, 'csrf') and app.csrf:
        # Import the route functions that actually get called
        from app.routes.scenario_pipeline.interactive_builder import normative_pass_prompt, normative_pass_execute, step2_extract, step2_extract_individual
        # Exempt the normative pass routes from CSRF protection
        app.csrf.exempt(normative_pass_prompt)
        app.csrf.exempt(normative_pass_execute)
        app.csrf.exempt(step2_extract)
        app.csrf.exempt(step2_extract_individual)

def extract_individual_concept(case_id):
    """
    API endpoint to extract an individual concept type from the normative pass.
    This allows debugging of individual extractors (principles, obligations, constraints, capabilities).
    """
    from app import db  # Import db at the start of the function

    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        concept_type = data.get('concept_type')
        if not concept_type:
            return jsonify({'error': 'concept_type is required'}), 400

        if concept_type not in ['principles', 'obligations', 'constraints', 'capabilities']:
            return jsonify({'error': f'Invalid concept_type: {concept_type}'}), 400

        # Get the case
        case = Document.query.get_or_404(case_id)

        # Get the facts section text (same logic as normative_pass_execute)
        section_text = None
        raw_sections = {}

        if case.doc_metadata:
            # Get sections from metadata
            if 'sections_dual' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections_dual']
            elif 'sections' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections']
            elif 'document_structure' in case.doc_metadata and 'sections' in case.doc_metadata['document_structure']:
                raw_sections = case.doc_metadata['document_structure']['sections']

        # Look for facts section
        for section_key, section_content in raw_sections.items():
            if 'fact' in section_key.lower():
                section_text = _format_section_for_llm(section_key, section_content, case)
                break

        # If no facts section found, use first available section
        if not section_text and raw_sections:
            first_key = list(raw_sections.keys())[0]
            section_text = _format_section_for_llm(first_key, raw_sections[first_key], case)

        if not section_text:
            # Fallback to using available content
            section_text = case.content or case.description or ""
            if not section_text:
                return jsonify({'error': 'No facts section found'}), 400

        logger.info(f"Executing individual {concept_type} extraction for case {case_id}")

        # Initialize LLM client
        try:
            llm_client = get_llm_client()
        except Exception as e:
            logger.warning(f"Could not initialize LLM client: {str(e)}")
            llm_client = None

        # Initialize provenance service
        if USE_VERSIONED_PROVENANCE:
            prov = get_versioned_provenance_service()
        else:
            from app.services.provenance_service import get_provenance_service
            prov = get_provenance_service()

        # Create session ID for this extraction
        session_id = str(uuid.uuid4())

        # Create context from the case
        context = {
            'case_id': case_id,
            'case_title': case.title if case else None,
            'document_type': 'ethics_case'
        }

        # Perform the extraction based on concept type
        candidates = []
        extraction_prompt = ""
        activity = None

        if concept_type == 'principles':
            # Use dual principles extractor for both classes and individuals
            from app.services.extraction.dual_principles_extractor import DualPrinciplesExtractor
            from models import ModelConfig

            extractor = DualPrinciplesExtractor()

            # Generate the prompt for display
            extraction_prompt = extractor._create_dual_principle_extraction_prompt(section_text, 'discussion')

            # Extract both classes and individuals
            candidate_classes, principle_individuals = extractor.extract_dual_principles(
                case_text=section_text,
                case_id=case_id,
                section_type='discussion'
            )

            # Get raw LLM response for RDF conversion
            raw_llm_response = extractor.get_last_raw_response()

            # Save prompt and response
            from app.models import ExtractionPrompt
            try:
                ExtractionPrompt.save_prompt(
                    case_id=case_id,
                    concept_type='principles',
                    prompt_text=extraction_prompt,
                    raw_response=raw_llm_response,
                    step_number=2,
                    llm_model=ModelConfig.get_claude_model("powerful"),
                    extraction_session_id=session_id
                )
            except Exception as e:
                logger.warning(f"Could not save extraction prompt: {e}")

            # Convert to RDF if we have the raw response
            if raw_llm_response:
                try:
                    import re
                    # Try to extract JSON from potentially mixed response
                    try:
                        raw_data = json.loads(raw_llm_response)
                    except json.JSONDecodeError:
                        json_match = re.search(r'\{[\s\S]*\}', raw_llm_response)
                        if json_match:
                            raw_data = json.loads(json_match.group())
                        else:
                            raw_data = {"new_principle_classes": [], "principle_individuals": []}

                    # Convert to RDF
                    from app.services.rdf_extraction_converter import RDFExtractionConverter
                    rdf_converter = RDFExtractionConverter()
                    class_graph, individual_graph = rdf_converter.convert_principles_extraction_to_rdf(
                        raw_data, case_id
                    )

                    # Store in temporary RDF storage
                    from app.models import TemporaryRDFStorage
                    rdf_data = rdf_converter.get_temporary_triples()
                    logger.info(f"DEBUG: Storing principles - classes: {len(rdf_data.get('new_classes', []))}, individuals: {len(rdf_data.get('new_individuals', []))}")

                    stored_entities = TemporaryRDFStorage.store_extraction_results(
                        case_id=case_id,
                        extraction_session_id=session_id,
                        extraction_type='principles',
                        rdf_data=rdf_data,
                        extraction_model=ModelConfig.get_claude_model("powerful")
                    )

                    logger.info(f"DEBUG: Stored {len(stored_entities)} principle entities in RDF storage")

                    # Commit the database changes
                    try:
                        db.session.commit()
                        logger.info(f"DEBUG: Committed principle entities to database")
                    except Exception as commit_error:
                        logger.error(f"DEBUG: Error committing principles: {commit_error}")
                        db.session.rollback()
                        raise
                except Exception as e:
                    logger.error(f"Error converting principles to RDF: {e}", exc_info=True)
                    import traceback
                    traceback.print_exc()

            # Convert to candidates format for compatibility
            candidates = []
            for cls in candidate_classes:
                from app.services.extraction.base import ConceptCandidate
                candidates.append(ConceptCandidate(
                    label=cls.label,
                    description=cls.definition,
                    primary_type='principle',
                    category='principle',
                    confidence=cls.confidence,
                    debug={
                        'abstract_nature': cls.abstract_nature,
                        'value_basis': cls.value_basis,
                        'extensional_examples': cls.extensional_examples,
                        'application_context': cls.application_context,
                        'operationalization': cls.operationalization,
                        'is_class': True
                    }
                ))

            for ind in principle_individuals:
                from app.services.extraction.base import ConceptCandidate
                candidates.append(ConceptCandidate(
                    label=ind.identifier,
                    description=ind.concrete_expression,
                    primary_type='principle_instance',
                    category='principle',
                    confidence=ind.confidence,
                    debug={
                        'principle_class': ind.principle_class,
                        'invoked_by': ind.invoked_by,
                        'applied_to': ind.applied_to,
                        'interpretation': ind.interpretation,
                        'balancing_with': ind.balancing_with,
                        'is_individual': True
                    }
                ))

        elif concept_type == 'obligations':
            # Use dual obligations extractor for both classes and individuals
            from app.services.extraction.dual_obligations_extractor import DualObligationsExtractor
            from models import ModelConfig

            extractor = DualObligationsExtractor()

            # Generate the prompt for display
            extraction_prompt = extractor._create_dual_obligations_extraction_prompt(section_text, 'discussion')

            # Extract both classes and individuals
            candidate_classes, obligation_individuals = extractor.extract_dual_obligations(
                case_text=section_text,
                case_id=case_id,
                section_type='discussion'
            )

            # Get raw LLM response for RDF conversion
            raw_llm_response = extractor.get_last_raw_response()

            # Save prompt and response
            from app.models import ExtractionPrompt
            try:
                ExtractionPrompt.save_prompt(
                    case_id=case_id,
                    concept_type='obligations',
                    prompt_text=extraction_prompt,
                    raw_response=raw_llm_response,
                    step_number=2,
                    llm_model=ModelConfig.get_claude_model("powerful"),
                    extraction_session_id=session_id
                )
            except Exception as e:
                logger.warning(f"Could not save extraction prompt: {e}")

            # Convert to RDF if we have the raw response
            if raw_llm_response:
                try:
                    import re
                    # Try to extract JSON from potentially mixed response
                    try:
                        raw_data = json.loads(raw_llm_response)
                    except json.JSONDecodeError:
                        json_match = re.search(r'\{[\s\S]*\}', raw_llm_response)
                        if json_match:
                            raw_data = json.loads(json_match.group())
                        else:
                            raw_data = {"new_obligation_classes": [], "obligation_individuals": []}

                    # Convert to RDF
                    from app.services.rdf_extraction_converter import RDFExtractionConverter
                    rdf_converter = RDFExtractionConverter()
                    class_graph, individual_graph = rdf_converter.convert_obligations_extraction_to_rdf(
                        raw_data, case_id
                    )

                    # Store in temporary RDF storage
                    from app.models import TemporaryRDFStorage
                    from app import db
                    rdf_data = rdf_converter.get_temporary_triples()
                    logger.info(f"DEBUG: Storing obligations - classes: {len(rdf_data.get('new_classes', []))}, individuals: {len(rdf_data.get('new_individuals', []))}")

                    stored_entities = TemporaryRDFStorage.store_extraction_results(
                        case_id=case_id,
                        extraction_session_id=session_id,
                        extraction_type='obligations',
                        rdf_data=rdf_data,
                        extraction_model=ModelConfig.get_claude_model("powerful")
                    )

                    logger.info(f"DEBUG: Stored {len(stored_entities)} obligation entities in RDF storage")

                    # Commit the database changes
                    try:
                        db.session.commit()
                        logger.info(f"DEBUG: Committed obligation entities to database")
                    except Exception as commit_error:
                        logger.error(f"DEBUG: Error committing obligations: {commit_error}")
                        db.session.rollback()
                        raise

                except Exception as e:
                    logger.error(f"Error converting obligations to RDF: {e}")
                    import traceback
                    traceback.print_exc()

            # Convert to format for display (combining classes and individuals)
            candidates = []
            from app.services.extraction.base import ConceptCandidate
            for obl_class in candidate_classes:
                candidates.append(ConceptCandidate(
                    label=obl_class.label,
                    description=obl_class.definition,
                    primary_type='obligations',
                    category='obligations_class',
                    confidence=obl_class.confidence,
                    debug={
                        'is_class': True,
                        'derived_from_principle': obl_class.derived_from_principle,
                        'duty_type': obl_class.duty_type,
                        'enforcement_mechanism': obl_class.enforcement_mechanism,
                        'extraction_method': 'dual_extraction'
                    }
                ))

            for individual in obligation_individuals:
                candidates.append(ConceptCandidate(
                    label=individual.identifier,
                    description=individual.obligation_statement,
                    primary_type='obligations',
                    category='obligations_individual',
                    confidence=individual.confidence,
                    debug={
                        'is_individual': True,
                        'obligation_class': individual.obligation_class,
                        'obligated_party': individual.obligated_party,
                        'compliance_status': individual.compliance_status,
                        'extraction_method': 'dual_extraction'
                    }
                ))

        elif concept_type == 'constraints':
            # Use dual constraints extractor for both classes and individuals
            from app.services.extraction.dual_constraints_extractor import DualConstraintsExtractor
            from models import ModelConfig

            extractor = DualConstraintsExtractor()

            # Generate the prompt for display
            extraction_prompt = extractor._create_dual_constraints_extraction_prompt(section_text, 'discussion')

            # Extract both classes and individuals
            candidate_classes, constraint_individuals = extractor.extract_dual_constraints(
                case_text=section_text,
                case_id=case_id,
                section_type='discussion'
            )

            # Get raw LLM response for RDF conversion
            raw_llm_response = extractor.get_last_raw_response()

            # Save prompt and response
            from app.models import ExtractionPrompt
            try:
                ExtractionPrompt.save_prompt(
                    case_id=case_id,
                    concept_type='constraints',
                    prompt_text=extraction_prompt,
                    raw_response=raw_llm_response,
                    step_number=2,
                    llm_model=ModelConfig.get_claude_model("powerful"),
                    extraction_session_id=session_id
                )
            except Exception as e:
                logger.warning(f"Could not save extraction prompt: {e}")

            # Convert to RDF if we have the raw response
            if raw_llm_response:
                try:
                    import re
                    # Try to extract JSON from potentially mixed response
                    try:
                        raw_data = json.loads(raw_llm_response)
                    except json.JSONDecodeError:
                        json_match = re.search(r'\{[\s\S]*\}', raw_llm_response)
                        if json_match:
                            raw_data = json.loads(json_match.group())
                        else:
                            raw_data = {"new_constraint_classes": [], "constraint_individuals": []}

                    # Convert to RDF
                    from app.services.rdf_extraction_converter import RDFExtractionConverter
                    rdf_converter = RDFExtractionConverter()
                    class_graph, individual_graph = rdf_converter.convert_constraints_extraction_to_rdf(
                        raw_data, case_id
                    )

                    # Store in temporary RDF storage
                    from app.models import TemporaryRDFStorage
                    from app import db
                    rdf_data = rdf_converter.get_temporary_triples()
                    logger.info(f"DEBUG: Storing constraints - classes: {len(rdf_data.get('new_classes', []))}, individuals: {len(rdf_data.get('new_individuals', []))}")

                    stored_entities = TemporaryRDFStorage.store_extraction_results(
                        case_id=case_id,
                        extraction_session_id=session_id,
                        extraction_type='constraints',
                        rdf_data=rdf_data,
                        extraction_model=ModelConfig.get_claude_model("powerful")
                    )

                    logger.info(f"DEBUG: Stored {len(stored_entities)} constraint entities in RDF storage")

                    # Commit the database changes
                    try:
                        db.session.commit()
                        logger.info(f"DEBUG: Committed constraint entities to database")
                    except Exception as commit_error:
                        logger.error(f"DEBUG: Error committing constraints: {commit_error}")
                        db.session.rollback()
                        raise

                except Exception as e:
                    logger.error(f"Error converting constraints to RDF: {e}")
                    import traceback
                    traceback.print_exc()

            # Convert to format for display (combining classes and individuals)
            candidates = []
            from app.services.extraction.base import ConceptCandidate
            for cons_class in candidate_classes:
                candidates.append(ConceptCandidate(
                    label=cons_class.label,
                    description=cons_class.definition,
                    primary_type='constraints',
                    category='constraints_class',
                    confidence=cons_class.confidence,
                    debug={
                        'is_class': True,
                        'constraint_type': cons_class.constraint_type,
                        'flexibility': cons_class.flexibility,
                        'violation_impact': cons_class.violation_impact,
                        'extraction_method': 'dual_extraction'
                    }
                ))

            for individual in constraint_individuals:
                candidates.append(ConceptCandidate(
                    label=individual.identifier,
                    description=individual.constraint_statement,
                    primary_type='constraints',
                    category='constraints_individual',
                    confidence=individual.confidence,
                    debug={
                        'is_individual': True,
                        'constraint_class': individual.constraint_class,
                        'constrained_entity': individual.constrained_entity,
                        'severity': individual.severity,
                        'extraction_method': 'dual_extraction'
                    }
                ))

        elif concept_type == 'capabilities':
            # Use dual capabilities extractor for both classes and individuals
            from app.services.extraction.dual_capabilities_extractor import DualCapabilitiesExtractor
            from models import ModelConfig

            extractor = DualCapabilitiesExtractor()

            # Generate the prompt for display
            extraction_prompt = extractor._create_dual_capabilities_extraction_prompt(section_text, 'discussion')

            # Extract both classes and individuals
            candidate_classes, capability_individuals = extractor.extract_dual_capabilities(
                case_text=section_text,
                case_id=case_id,
                section_type='discussion'
            )

            # Get raw LLM response for RDF conversion
            raw_llm_response = extractor.get_last_raw_response()
            logger.info(f"DEBUG CAPABILITIES: Got raw response, length: {len(raw_llm_response) if raw_llm_response else 0}")

            # Save prompt and response
            from app.models import ExtractionPrompt
            try:
                ExtractionPrompt.save_prompt(
                    case_id=case_id,
                    concept_type='capabilities',
                    prompt_text=extraction_prompt,
                    raw_response=raw_llm_response,
                    step_number=2,
                    llm_model=ModelConfig.get_claude_model("powerful"),
                    extraction_session_id=session_id
                )
            except Exception as e:
                logger.warning(f"Could not save extraction prompt: {e}")

            # Convert to RDF if we have the raw response
            if raw_llm_response:
                logger.info(f"DEBUG CAPABILITIES: Starting RDF conversion")
                try:
                    import re
                    # Try to extract JSON from potentially mixed response
                    try:
                        raw_data = json.loads(raw_llm_response)
                        logger.info(f"DEBUG CAPABILITIES: Parsed JSON directly")
                    except json.JSONDecodeError:
                        logger.info(f"DEBUG CAPABILITIES: JSON decode failed, trying regex")
                        json_match = re.search(r'\{[\s\S]*\}', raw_llm_response)
                        if json_match:
                            raw_data = json.loads(json_match.group())
                            logger.info(f"DEBUG CAPABILITIES: Extracted JSON via regex")
                        else:
                            raw_data = {"new_capability_classes": [], "capability_individuals": []}
                            logger.warning(f"DEBUG CAPABILITIES: No JSON found, using empty data")

                    logger.info(f"DEBUG CAPABILITIES: Raw data keys: {raw_data.keys()}")
                    logger.info(f"DEBUG CAPABILITIES: Classes count: {len(raw_data.get('new_capability_classes', []))}")
                    logger.info(f"DEBUG CAPABILITIES: Individuals count: {len(raw_data.get('capability_individuals', []))}")

                    # Convert to RDF
                    from app.services.rdf_extraction_converter import RDFExtractionConverter
                    rdf_converter = RDFExtractionConverter()
                    class_graph, individual_graph = rdf_converter.convert_capabilities_extraction_to_rdf(
                        raw_data, case_id
                    )
                    logger.info(f"DEBUG CAPABILITIES: RDF conversion complete")

                    # Store in temporary RDF storage
                    rdf_data = rdf_converter.get_temporary_triples()
                    logger.info(f"DEBUG CAPABILITIES: Got RDF data - classes: {len(rdf_data.get('classes', []))}, individuals: {len(rdf_data.get('individuals', []))}")

                    from app.models import TemporaryRDFStorage
                    TemporaryRDFStorage.store_extraction_results(
                        case_id=case_id,
                        extraction_session_id=session_id,
                        extraction_type='capabilities',
                        rdf_data=rdf_data,
                        extraction_model=ModelConfig.get_claude_model("powerful")
                    )
                    logger.info(f"DEBUG CAPABILITIES: Called store_extraction_results")

                    # Commit the session after successful storage
                    try:
                        db.session.commit()
                        logger.info(f"DEBUG CAPABILITIES: Successfully committed {len(rdf_data.get('classes', []))} capability classes and {len(rdf_data.get('individuals', []))} individuals")
                    except Exception as commit_error:
                        logger.error(f"DEBUG CAPABILITIES: Error committing: {commit_error}")
                        db.session.rollback()
                        raise

                except Exception as e:
                    logger.error(f"DEBUG CAPABILITIES: Error converting to RDF: {e}")
                    import traceback
                    traceback.print_exc()
                    logger.error(f"DEBUG CAPABILITIES: Full error details: {traceback.format_exc()}")

            # Convert to format for display (combining classes and individuals)
            candidates = []
            from app.services.extraction.base import ConceptCandidate
            for cap_class in candidate_classes:
                candidates.append(ConceptCandidate(
                    label=cap_class.label,
                    description=cap_class.definition,
                    primary_type='capabilities',
                    category='capabilities_class',
                    confidence=cap_class.confidence,
                    debug={
                        'is_class': True,
                        'capability_type': cap_class.capability_type,
                        'norm_competence_related': cap_class.norm_competence_related,
                        'skill_level': cap_class.skill_level,
                        'extraction_method': 'dual_extraction'
                    }
                ))

            for individual in capability_individuals:
                candidates.append(ConceptCandidate(
                    label=individual.identifier,
                    description=individual.capability_statement,
                    primary_type='capabilities',
                    category='capabilities_individual',
                    confidence=individual.confidence,
                    debug={
                        'is_individual': True,
                        'capability_class': individual.capability_class,
                        'possessed_by': individual.possessed_by,
                        'proficiency_level': individual.proficiency_level,
                        'extraction_method': 'dual_extraction'
                    }
                ))

        # Record extraction results in provenance
        if candidates and activity:
            prov.record_extraction_results(
                results=[{
                    'label': c.label,
                    'description': c.description,
                    'confidence': c.confidence,
                    'debug': c.debug
                } for c in candidates],
                activity=activity,
                entity_type=f'extracted_{concept_type}',
                metadata={'count': len(candidates)}
            )

        # Commit provenance records
        db.session.commit()

        # Convert candidates to response format
        results = []
        for candidate in candidates:
            result_data = {
                "label": candidate.label,
                "description": candidate.description or "",
                "type": concept_type.rstrip('s'),  # Remove plural 's'
                "confidence": candidate.confidence
            }

            # Add concept-specific metadata
            if concept_type == 'principles':
                result_data.update({
                    "principle_category": candidate.debug.get('principle_category', 'professional'),
                    "abstraction_level": candidate.debug.get('abstraction_level', 'high'),
                    "requires_interpretation": candidate.debug.get('requires_interpretation', True),
                    "potential_conflicts": candidate.debug.get('potential_conflicts', []),
                    "extensional_examples": candidate.debug.get('extensional_examples', []),
                    "derived_obligations": candidate.debug.get('derived_obligations', []),
                    "scholarly_grounding": candidate.debug.get('scholarly_grounding', '')
                })
            elif concept_type == 'obligations':
                result_data.update({
                    "obligation_type": candidate.debug.get('obligation_type', 'professional_practice'),
                    "enforcement_level": candidate.debug.get('enforcement_level', 'mandatory'),
                    "derived_from_principle": candidate.debug.get('derived_from_principle', ''),
                    "stakeholders_affected": candidate.debug.get('stakeholders_affected', []),
                    "potential_conflicts": candidate.debug.get('potential_conflicts', []),
                    "monitoring_criteria": candidate.debug.get('monitoring_criteria', ''),
                    "nspe_reference": candidate.debug.get('nspe_reference', ''),
                    "contextual_factors": candidate.debug.get('contextual_factors', '')
                })
            elif concept_type == 'constraints':
                result_data.update({
                    "constraint_category": candidate.debug.get('constraint_category', 'resource'),
                    "flexibility": candidate.debug.get('flexibility', 'non-negotiable'),
                    "impact_on_decisions": candidate.debug.get('impact_on_decisions', ''),
                    "affected_stakeholders": candidate.debug.get('affected_stakeholders', []),
                    "potential_violations": candidate.debug.get('potential_violations', ''),
                    "mitigation_strategies": candidate.debug.get('mitigation_strategies', []),
                    "temporal_aspect": candidate.debug.get('temporal_aspect', 'permanent'),
                    "quantifiable_metrics": candidate.debug.get('quantifiable_metrics', '')
                })
            elif concept_type == 'capabilities':
                result_data.update({
                    "capability_category": candidate.debug.get('capability_category', 'TechnicalCapability'),
                    "ethical_relevance": candidate.debug.get('ethical_relevance', ''),
                    "required_for_roles": candidate.debug.get('required_for_roles', []),
                    "enables_obligations": candidate.debug.get('enables_obligations', []),
                    "theoretical_grounding": candidate.debug.get('theoretical_grounding', ''),
                    "development_path": candidate.debug.get('development_path', '')
                })

            results.append(result_data)

        # Get the actual model being used
        from models import ModelConfig
        model_used = 'heuristic'
        if llm_client:
            if hasattr(llm_client, 'api_version'):
                # Anthropic client - we're using the powerful model for extraction
                model_used = ModelConfig.get_claude_model("powerful")
            elif hasattr(llm_client, 'models'):
                # OpenAI client
                model_used = 'gpt-4'
            else:
                model_used = 'unknown_llm'

        # Get raw LLM response (from dual extractor)
        raw_llm_response = None
        # The raw response was saved in the dual extractor
        from app.models import ExtractionPrompt
        # Don't filter by session_id since each extraction creates a new one
        saved_prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type=concept_type,
            step_number=2,
            is_active=True
        ).first()
        if saved_prompt:
            raw_llm_response = saved_prompt.raw_response

        return jsonify({
            'success': True,
            'concept_type': concept_type,
            'results': results,
            'count': len(results),
            'prompt': extraction_prompt,
            'raw_llm_response': raw_llm_response,  # Add this for the UI
            'session_id': session_id,
            'extraction_metadata': {
                'timestamp': datetime.now().isoformat(),
                'extraction_method': 'enhanced_individual',
                'llm_available': llm_client is not None,
                'provenance_tracked': True,
                'model_used': model_used
            }
        })

    except Exception as e:
        logger.error(f"Error extracting individual {concept_type} for case {case_id}: {str(e)}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500

def step2_data(case_id):
    """
    Helper function to get Step 2 data without rendering template.
    Used by both regular step2 and step2_streaming views.
    """
    # Get the case
    case = Document.query.get_or_404(case_id)

    # Extract sections using the same logic as step1
    raw_sections = {}
    if case.doc_metadata:
        # Priority 1: sections_dual (contains formatted HTML with enumerated lists)
        if 'sections_dual' in case.doc_metadata:
            raw_sections = case.doc_metadata['sections_dual']
        # Priority 2: sections (basic sections)
        elif 'sections' in case.doc_metadata:
            raw_sections = case.doc_metadata['sections']
        # Priority 3: document_structure sections
        elif 'document_structure' in case.doc_metadata and 'sections' in case.doc_metadata['document_structure']:
            raw_sections = case.doc_metadata['document_structure']['sections']

    # If no sections found, create basic structure
    if not raw_sections:
        raw_sections = {
            'full_content': case.content or 'No content available'
        }

    # Find the facts section (same as step1)
    facts_section = None
    facts_section_key = None

    # Look for facts section (case insensitive)
    for section_key, section_content in raw_sections.items():
        if 'fact' in section_key.lower():
            facts_section_key = section_key
            facts_section = _format_section_for_llm(section_key, section_content, case_doc=case)
            break

    # If no facts section found, use first available section
    if not facts_section and raw_sections:
        first_key = list(raw_sections.keys())[0]
        facts_section_key = first_key
        facts_section = _format_section_for_llm(first_key, raw_sections[first_key], case_doc=case)

    # Load saved prompts for all concept types
    from app.models import ExtractionPrompt
    saved_prompts = {}
    for concept_type in ['principles', 'obligations', 'constraints', 'capabilities']:
        # Get active prompt and check if it's for step 2
        prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type=concept_type,
            step_number=2,
            is_active=True
        ).first()
        saved_prompts[concept_type] = prompt

    return case, facts_section, saved_prompts

def step2(case_id):
    """
    Step 2: Normative Pass for Facts Section
    Shows the facts section with a normative pass button for extracting principles, obligations, and constraints.
    """
    try:
        # Get data
        case, facts_section, saved_prompts = step2_data(case_id)

        # Find the facts section key for template
        facts_section_key = None
        raw_sections = {}
        if case.doc_metadata:
            if 'sections_dual' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections_dual']
            elif 'sections' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections']
            elif 'document_structure' in case.doc_metadata and 'sections' in case.doc_metadata['document_structure']:
                raw_sections = case.doc_metadata['document_structure']['sections']

        for section_key, section_content in raw_sections.items():
            if 'fact' in section_key.lower():
                facts_section_key = section_key
                break

        if not facts_section_key and raw_sections:
            facts_section_key = list(raw_sections.keys())[0]

        # Template context
        # Load saved prompts for all concept types
        from app.models import ExtractionPrompt
        saved_prompts = {}
        for concept_type in ['principles', 'obligations', 'constraints', 'capabilities']:
            # Get active prompt and check if it's for step 2
            saved_prompt = ExtractionPrompt.query.filter_by(
                case_id=case_id,
                concept_type=concept_type,
                step_number=2,
                is_active=True
            ).first()
            if saved_prompt:
                saved_prompts[concept_type] = saved_prompt

        context = {
            'case': case,
            'discussion_section': facts_section,  # Keep variable name for template compatibility
            'discussion_section_key': facts_section_key,
            'current_step': 2,
            'step_title': 'Normative Pass - Facts Section',
            'next_step_url': url_for('scenario_pipeline.step3', case_id=case_id),
            'prev_step_url': url_for('scenario_pipeline.overview', case_id=case_id),
            'saved_prompts': saved_prompts
        }

        return render_template('scenarios/step2_multi_section.html', **context)
        
    except Exception as e:
        logger.error(f"Error loading step 2 for case {case_id}: {str(e)}")
        flash(f'Error loading step 2: {str(e)}', 'danger')
        return redirect(url_for('cases.view_case', id=case_id))

def get_saved_prompt(case_id):
    """Get saved extraction prompt for a concept type in Step 2"""
    from app.models import ExtractionPrompt

    concept_type = request.args.get('concept_type')
    if not concept_type:
        return jsonify({'error': 'concept_type is required'}), 400

    saved_prompt = ExtractionPrompt.query.filter_by(
        case_id=case_id,
        concept_type=concept_type,
        step_number=2,
        is_active=True
    ).first()

    if saved_prompt:
        return jsonify({
            'success': True,
            'prompt_text': saved_prompt.prompt_text,
            'raw_response': saved_prompt.raw_response,
            'created_at': saved_prompt.created_at.isoformat() if saved_prompt.created_at else None
        })
    else:
        return jsonify({'success': False, 'message': 'No saved prompt found'})

def clear_saved_prompt(case_id):
    """Clear saved extraction prompt for a concept type in Step 2"""
    from app.models import ExtractionPrompt, db

    data = request.get_json()
    concept_type = data.get('concept_type')

    if not concept_type:
        return jsonify({'error': 'concept_type is required'}), 400

    try:
        # Deactivate existing prompts for this case/concept/step
        ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type=concept_type,
            step_number=2,
            is_active=True
        ).update({'is_active': False})

        db.session.commit()
        return jsonify({'success': True, 'message': f'Cleared prompt for {concept_type}'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to clear prompt: {str(e)}'}), 500

def normative_pass_prompt(case_id):
    """
    API endpoint to generate and return the LLM prompt for normative pass before execution.
    This will extract principles, obligations, and constraints.
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        section_text = data.get('section_text')
        if not section_text:
            return jsonify({'error': 'section_text is required'}), 400
        
        logger.info(f"Generating normative pass prompt for case {case_id}")
        
        # Use enhanced principles prompt from Chapter 2 literature with MCP context
        # MCP will be fetched dynamically from the external server
        principles_prompt = create_enhanced_principles_prompt(section_text, include_mcp_context=True)

        # Use enhanced obligations prompt with MCP context - include principles for full normative pass
        obligations_prompt = create_enhanced_obligations_prompt(section_text, include_mcp_context=True, include_principles=True)

        # Use enhanced constraints prompt with MCP context - include related entities for full normative pass
        constraints_prompt = create_enhanced_constraints_prompt(section_text, include_mcp_context=True, include_related_entities=True)
        
        # Use enhanced capabilities prompt with MCP context - retrieves capability types via recursive CTE
        capabilities_prompt = create_enhanced_capabilities_prompt(section_text, include_mcp_context=True)
        
        return jsonify({
            'success': True,
            'principles_prompt': principles_prompt,
            'obligations_prompt': obligations_prompt,
            'constraints_prompt': constraints_prompt,
            'capabilities_prompt': capabilities_prompt,
            'section_length': len(section_text)
        })
        
    except Exception as e:
        logger.error(f"Error generating normative pass prompt for case {case_id}: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500

def normative_pass_execute(case_id):
    """
    API endpoint to execute the normative pass extraction.
    This will run the actual LLM extraction for principles, obligations, and constraints.
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405
        
        # Get the case
        case = Document.query.get_or_404(case_id)
        
        # Get the facts section text (same logic as step2 view)
        section_text = None
        raw_sections = {}
        
        if case.doc_metadata:
            # Get sections from metadata
            if 'sections_dual' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections_dual']
            elif 'sections' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections']
            elif 'document_structure' in case.doc_metadata and 'sections' in case.doc_metadata['document_structure']:
                raw_sections = case.doc_metadata['document_structure']['sections']
        
        # Look for facts section
        for section_key, section_content in raw_sections.items():
            if 'fact' in section_key.lower():
                section_text = _format_section_for_llm(section_key, section_content, case)
                break
        
        # If no facts section found, use first available section
        if not section_text and raw_sections:
            first_key = list(raw_sections.keys())[0]
            section_text = _format_section_for_llm(first_key, raw_sections[first_key], case)
        
        if not section_text:
            # Fallback to using available content
            section_text = case.content or case.description or ""
            if not section_text:
                return jsonify({'error': 'No facts section found'}), 400
        
        logger.info(f"Executing normative pass for case {case_id}")
        
        # Initialize enhanced extractors with LLM client
        try:
            llm_client = get_llm_client()
        except Exception as e:
            logger.warning(f"Could not initialize LLM client: {str(e)}")
            llm_client = None
        
        # Initialize provenance service with versioning if available
        if USE_VERSIONED_PROVENANCE:
            prov = get_versioned_provenance_service()
            logger.info("Using versioned provenance service for Step 2")
        else:
            from app.services.provenance_service import get_provenance_service
            prov = get_provenance_service()
            logger.info("Using standard provenance service")
        
        # Create session ID for this normative pass
        session_id = str(uuid.uuid4())
        
        # Create context from the case we already have
        context = {
            'case_id': case_id,
            'case_title': case.title if case else None,
            'document_type': 'ethics_case'
        }
        
        # Track versioned workflow if available
        version_context = nullcontext()
        if USE_VERSIONED_PROVENANCE:
            version_context = prov.track_versioned_workflow(
                workflow_name='step2_normative_pass',
                description='Pass 2: Normative extraction of Principles, Obligations, and Constraints',
                version_tag='enhanced_normative',
                auto_version=True
            )
        
        # Use context manager for versioned workflow
        with version_context:
            # Track the main normative pass activity
            with prov.track_activity(
                activity_type='extraction',
                activity_name='normative_pass_step2',
                case_id=case_id,
                session_id=session_id,
                agent_type='extraction_service',
                agent_name='proethica_normative_pass',
                execution_plan={
                    'pass_number': 2,
                    'concepts': ['principles', 'obligations', 'constraints'],
                    'strategy': 'llm_enhanced',
                    'version': 'enhanced_normative' if USE_VERSIONED_PROVENANCE else 'standard'
                }
            ) as main_activity:
                
                # Extract principles
                with prov.track_activity(
                    activity_type='llm_query',
                    activity_name='principles_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='EnhancedPrinciplesExtractor'
                ) as principles_activity:
                    logger.info("Extracting principles with provenance tracking...")
                    principles_extractor = EnhancedPrinciplesExtractor(
                        llm_client=llm_client,
                        provenance_service=prov
                    )
                    principle_candidates = principles_extractor.extract(
                        section_text, 
                        context=context,
                        activity=principles_activity
                    )
                    
                    # Record extraction results
                    prov.record_extraction_results(
                        results=[{
                            'label': c.label,
                            'description': c.description,
                            'confidence': c.confidence,
                            'debug': c.debug
                        } for c in principle_candidates],
                        activity=principles_activity,
                        entity_type='extracted_principles',
                        metadata={'count': len(principle_candidates)}
                    )
                
                # Extract obligations
                with prov.track_activity(
                    activity_type='llm_query',
                    activity_name='obligations_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='EnhancedObligationsExtractor'
                ) as obligations_activity:
                    logger.info("Extracting obligations with provenance tracking...")
                    obligations_extractor = EnhancedObligationsExtractor(
                        llm_client=llm_client,
                        provenance_service=prov
                    )
                    obligation_candidates = obligations_extractor.extract(
                        section_text,
                        context=context,
                        activity=obligations_activity
                    )
                    
                    # Record extraction results
                    prov.record_extraction_results(
                        results=[{
                            'label': c.label,
                            'description': c.description,
                            'confidence': c.confidence,
                            'debug': c.debug
                        } for c in obligation_candidates],
                        activity=obligations_activity,
                        entity_type='extracted_obligations',
                        metadata={'count': len(obligation_candidates)}
                    )
                
                # Extract constraints
                with prov.track_activity(
                    activity_type='llm_query',
                    activity_name='constraints_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='EnhancedConstraintsExtractor'
                ) as constraints_activity:
                    logger.info("Extracting constraints with provenance tracking...")
                    constraints_extractor = EnhancedConstraintsExtractor(
                        llm_client=llm_client,
                        provenance_service=prov
                    )
                    constraint_candidates = constraints_extractor.extract(
                        section_text,
                        context=context,
                        activity=constraints_activity
                    )
                    
                    # Record extraction results
                    prov.record_extraction_results(
                        results=[{
                            'label': c.label,
                            'description': c.description,
                            'confidence': c.confidence,
                            'debug': c.debug
                        } for c in constraint_candidates],
                        activity=constraints_activity,
                        entity_type='extracted_constraints',
                        metadata={'count': len(constraint_candidates)}
                    )
                
                # Track capabilities extraction as a sub-activity (Part of Pass 2: Normative Requirements)
                with prov.track_activity(
                    activity_type='llm_query',
                    activity_name='capabilities_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='EnhancedCapabilitiesExtractor'
                ) as capabilities_activity:
                    logger.info("Extracting capabilities with enhanced extractor...")
                    capabilities_extractor = EnhancedCapabilitiesExtractor(
                        llm_client=llm_client,
                        provenance_service=prov
                    )
                    capability_candidates = capabilities_extractor.extract(
                        section_text,
                        context=context,
                        activity=capabilities_activity
                    )
                    
                    # Record extraction results
                    prov.record_extraction_results(
                        results=[{
                            'label': c.label,
                            'description': c.description,
                            'confidence': c.confidence,
                            'debug': c.debug
                        } for c in capability_candidates],
                        activity=capabilities_activity,
                        entity_type='extracted_capabilities',
                        metadata={'count': len(capability_candidates)}
                    )
                
                # Link sub-activities to main activity
                prov.link_activities(principles_activity, main_activity, 'sequence')
                prov.link_activities(obligations_activity, principles_activity, 'sequence')
                prov.link_activities(constraints_activity, obligations_activity, 'sequence')
                prov.link_activities(capabilities_activity, constraints_activity, 'sequence')
        
        # Commit provenance records
        db.session.commit()
        
        # Convert candidates to response format
        principles = []
        for candidate in principle_candidates:
            principle_data = {
                "label": candidate.label,
                "description": candidate.description or "",
                "type": "principle",
                "principle_category": candidate.debug.get('principle_category', 'professional'),
                "abstraction_level": candidate.debug.get('abstraction_level', 'high'),
                "requires_interpretation": candidate.debug.get('requires_interpretation', True),
                "potential_conflicts": candidate.debug.get('potential_conflicts', []),
                "extensional_examples": candidate.debug.get('extensional_examples', []),
                "derived_obligations": candidate.debug.get('derived_obligations', []),
                "scholarly_grounding": candidate.debug.get('scholarly_grounding', ''),
                "confidence": candidate.confidence
            }
            principles.append(principle_data)
        
        obligations = []
        for candidate in obligation_candidates:
            obligation_data = {
                "label": candidate.label,
                "description": candidate.description or "",
                "type": "obligation",
                "obligation_type": candidate.debug.get('obligation_type', 'professional_practice'),
                "enforcement_level": candidate.debug.get('enforcement_level', 'mandatory'),
                "derived_from_principle": candidate.debug.get('derived_from_principle', ''),
                "stakeholders_affected": candidate.debug.get('stakeholders_affected', []),
                "potential_conflicts": candidate.debug.get('potential_conflicts', []),
                "monitoring_criteria": candidate.debug.get('monitoring_criteria', ''),
                "nspe_reference": candidate.debug.get('nspe_reference', ''),
                "contextual_factors": candidate.debug.get('contextual_factors', ''),
                "confidence": candidate.confidence
            }
            obligations.append(obligation_data)
        
        constraints = []
        for candidate in constraint_candidates:
            constraint_data = {
                "label": candidate.label,
                "description": candidate.description or "",
                "type": "constraint",
                "constraint_category": candidate.debug.get('constraint_category', 'resource'),
                "flexibility": candidate.debug.get('flexibility', 'non-negotiable'),
                "impact_on_decisions": candidate.debug.get('impact_on_decisions', ''),
                "affected_stakeholders": candidate.debug.get('affected_stakeholders', []),
                "potential_violations": candidate.debug.get('potential_violations', ''),
                "mitigation_strategies": candidate.debug.get('mitigation_strategies', []),
                "temporal_aspect": candidate.debug.get('temporal_aspect', 'permanent'),
                "quantifiable_metrics": candidate.debug.get('quantifiable_metrics', ''),
                "confidence": candidate.confidence
            }
            constraints.append(constraint_data)
        
        capabilities = []
        for candidate in capability_candidates:
            capability_data = {
                "label": candidate.label,
                "description": candidate.description or "",
                "type": "capability",
                "capability_category": candidate.debug.get('capability_category', 'TechnicalCapability'),
                "ethical_relevance": candidate.debug.get('ethical_relevance', ''),
                "required_for_roles": candidate.debug.get('required_for_roles', []),
                "enables_obligations": candidate.debug.get('enables_obligations', []),
                "theoretical_grounding": candidate.debug.get('theoretical_grounding', ''),
                "development_path": candidate.debug.get('development_path', ''),
                "confidence": candidate.confidence
            }
            capabilities.append(capability_data)
        
        # Summary statistics
        summary = {
            'principles_count': len(principles),
            'obligations_count': len(obligations),
            'constraints_count': len(constraints),
            'capabilities_count': len(capabilities),
            'total_entities': len(principles) + len(obligations) + len(constraints) + len(capabilities),
            'session_id': session_id,
            'version': 'enhanced_normative' if USE_VERSIONED_PROVENANCE else 'standard'
        }
        
        # Add provenance URL if available
        if USE_VERSIONED_PROVENANCE:
            summary['provenance_url'] = url_for('provenance.provenance_viewer')
        
        # Get the actual model being used
        from models import ModelConfig
        model_used = 'heuristic'
        if llm_client:
            if hasattr(llm_client, 'api_version'):
                # Anthropic client - we're using the powerful model for extraction
                model_used = ModelConfig.get_claude_model("powerful")
            elif hasattr(llm_client, 'models'):
                # OpenAI client
                model_used = 'gpt-4'
            else:
                model_used = 'unknown_llm'

        # Add extraction metadata
        extraction_metadata = {
            'timestamp': datetime.now().isoformat(),
            'extraction_method': 'enhanced_chapter2' if llm_client else 'fallback_heuristic',
            'principles_extractor': 'EnhancedPrinciplesExtractor',
            'obligations_extractor': 'EnhancedObligationsExtractor',
            'constraints_extractor': 'EnhancedConstraintsExtractor',
            'capabilities_extractor': 'EnhancedCapabilitiesExtractor',
            'llm_available': llm_client is not None,
            'provenance_tracked': True,
            'model_used': model_used
        }
        
        return jsonify({
            'success': True,
            'principles': principles,
            'obligations': obligations,
            'constraints': constraints,
            'capabilities': capabilities,
            'summary': summary,
            'extraction_metadata': extraction_metadata
        })
        
    except Exception as e:
        logger.error(f"Error executing normative pass for case {case_id}: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500
