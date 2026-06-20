"""Case FIRAC + ethics-committee analysis routes."""
from flask import Blueprint, render_template, jsonify, request, current_app
from flask_login import login_required
from sqlalchemy import func, desc
from datetime import datetime, timedelta
import json
import logging

from app.models import db
from app.models.world import World
from app.models.guideline import Guideline
from app.models import Document
from app.models.document_section import DocumentSection
from app.models.entity_triple import EntityTriple
from app.models.ontology import Ontology
from app.models.deconstructed_case import DeconstructedCase
try:
    from app.models.case_guideline_associations import CaseGuidelineAssociation
except ImportError:
    # Create a placeholder for testing if the model doesn't exist yet
    CaseGuidelineAssociation = None
try:
    from app.models.temporary_concept import TemporaryConcept
except ImportError:
    # Create a placeholder for testing if the model doesn't exist yet
    TemporaryConcept = None
from app.services.step4_synthesis.firac_analysis_service import firac_analysis_service
from app.services.ethics_committee_agent import ethics_committee_agent
logger = logging.getLogger(__name__)


def register_analysis_routes(bp):
    @bp.route('/case/<int:case_id>/firac')
    @login_required
    def case_firac_analysis(case_id):
        """Generate and display FIRAC analysis for a specific case."""
    
        try:
            # Generate FIRAC analysis
            firac_analysis = firac_analysis_service.analyze_case(case_id)
        
            return render_template(
                'dashboard/firac_analysis.html',
                analysis=firac_analysis
            )
        except Exception as e:
            logger.error(f"Error generating FIRAC analysis for case {case_id}: {e}")
            return render_template(
                'dashboard/firac_error.html',
                case_id=case_id,
                error=str(e)
            )


    @bp.route('/api/case/<int:case_id>/firac')
    @login_required
    def api_case_firac_analysis(case_id):
        """API endpoint for FIRAC analysis."""
    
        try:
            firac_analysis = firac_analysis_service.analyze_case(case_id)
        
            # Convert to JSON-serializable format
            return jsonify({
                'status': 'success',
                'case_id': firac_analysis.case_id,
                'case_title': firac_analysis.case_title,
                'facts': {
                    'factual_statements': firac_analysis.facts.factual_statements,
                    'key_stakeholders': firac_analysis.facts.key_stakeholders,
                    'context_description': firac_analysis.facts.context_description,
                    'source_sections': firac_analysis.facts.source_sections
                },
                'issues': {
                    'primary_ethical_issues': firac_analysis.issues.primary_ethical_issues,
                    'secondary_issues': firac_analysis.issues.secondary_issues,
                    'ethical_dilemmas': firac_analysis.issues.ethical_dilemmas,
                    'stakeholder_conflicts': firac_analysis.issues.stakeholder_conflicts
                },
                'rules': {
                    'applicable_guidelines': firac_analysis.rules.applicable_guidelines,
                    'ontology_concepts': firac_analysis.rules.ontology_concepts,
                    'ethical_principles': firac_analysis.rules.ethical_principles,
                    'professional_standards': firac_analysis.rules.professional_standards,
                    'confidence_scores': firac_analysis.rules.confidence_scores
                },
                'analysis': {
                    'rule_application': firac_analysis.analysis.rule_application,
                    'conflict_resolution': firac_analysis.analysis.conflict_resolution,
                    'stakeholder_impact': firac_analysis.analysis.stakeholder_impact,
                    'precedent_cases': firac_analysis.analysis.precedent_cases,
                    'reasoning_chain': firac_analysis.analysis.reasoning_chain
                },
                'conclusion': {
                    'recommended_action': firac_analysis.conclusion.recommended_action,
                    'implementation_steps': firac_analysis.conclusion.implementation_steps,
                    'risk_assessment': firac_analysis.conclusion.risk_assessment,
                    'alternative_approaches': firac_analysis.conclusion.alternative_approaches,
                    'committee_consultation_needed': firac_analysis.conclusion.committee_consultation_needed
                },
                'confidence_overview': firac_analysis.confidence_overview,
                'processing_metadata': firac_analysis.processing_metadata
            })
        except Exception as e:
            logger.error(f"Error generating API FIRAC analysis for case {case_id}: {e}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500


    @bp.route('/case/<int:case_id>/ethics-committee')
    @login_required
    def case_ethics_committee(case_id):
        """Generate and display ethics committee consultation for a specific case."""
    
        try:
            # First generate FIRAC analysis
            firac_analysis = firac_analysis_service.analyze_case(case_id)
        
            # Then conduct ethics committee consultation
            committee_discussion = ethics_committee_agent.conduct_committee_consultation(firac_analysis)
        
            return render_template(
                'dashboard/ethics_committee.html',
                discussion=committee_discussion,
                firac_analysis=firac_analysis
            )
        except Exception as e:
            logger.error(f"Error generating ethics committee consultation for case {case_id}: {e}")
            return render_template(
                'dashboard/committee_error.html',
                case_id=case_id,
                error=str(e)
            )


    @bp.route('/api/case/<int:case_id>/ethics-committee')
    @login_required
    def api_case_ethics_committee(case_id):
        """API endpoint for ethics committee consultation."""
    
        try:
            # Generate FIRAC analysis first
            firac_analysis = firac_analysis_service.analyze_case(case_id)
        
            # Conduct committee consultation
            committee_discussion = ethics_committee_agent.conduct_committee_consultation(firac_analysis)
        
            # Convert to JSON-serializable format
            return jsonify({
                'status': 'success',
                'case_id': committee_discussion.case_id,
                'case_title': committee_discussion.case_title,
                'discussion_phases': committee_discussion.discussion_phases,
                'member_positions': [
                    {
                        'member_name': pos.member.name,
                        'member_role': pos.member.role,
                        'expertise': pos.member.expertise,
                        'position': pos.position,
                        'reasoning': pos.reasoning,
                        'supporting_evidence': pos.supporting_evidence,
                        'concerns_raised': pos.concerns_raised,
                        'confidence': pos.confidence
                    }
                    for pos in committee_discussion.member_positions
                ],
                'areas_of_agreement': committee_discussion.areas_of_agreement,
                'areas_of_disagreement': committee_discussion.areas_of_disagreement,
                'consensus_recommendation': committee_discussion.consensus_recommendation,
                'minority_opinions': committee_discussion.minority_opinions,
                'follow_up_actions': committee_discussion.follow_up_actions,
                'confidence_in_consensus': committee_discussion.confidence_in_consensus
            })
        except Exception as e:
            logger.error(f"Error generating API ethics committee consultation for case {case_id}: {e}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500


    @bp.route('/firac/test')
    @login_required
    def test_firac_analysis():
        """Test page for FIRAC analysis."""
    
        # Get sample cases for testing
        if CaseGuidelineAssociation is not None:
            try:
                cases_with_associations = db.session.query(Document.id, Document.title)\
                    .join(CaseGuidelineAssociation, Document.id == CaseGuidelineAssociation.case_id)\
                    .distinct()\
                    .limit(5)\
                    .all()
            except Exception as e:
                logger.warning(f"Could not query associations: {e}")
                cases_with_associations = []
        else:
            cases_with_associations = []
    
        # If no cases with associations, get any cases that look like NSPE cases
        if not cases_with_associations:
            try:
                cases_with_associations = db.session.query(Document.id, Document.title)\
                    .filter(Document.doc_metadata.op('->>')('case_number').isnot(None))\
                    .limit(5)\
                    .all()
            except Exception as e:
                logger.warning(f"Could not query cases: {e}")
                cases_with_associations = []
    
        return render_template(
            'dashboard/test_firac.html',
            cases=cases_with_associations
        )


