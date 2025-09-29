"""
Candidate Role Validation Service

Manages the workflow for validating, reviewing, and integrating discovered role classes
into the proethica-intermediate ontology.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from app.models import db
from app.models.candidate_role_class import CandidateRoleClass, CandidateRoleIndividual
from app.services.external_mcp_client import get_external_mcp_client
from sqlalchemy import desc, asc

logger = logging.getLogger(__name__)

class CandidateRoleValidationService:
    """Service for managing candidate role class validation workflow"""

    def __init__(self):
        self.mcp_client = get_external_mcp_client()

    def store_candidate_role_class(self,
                                 candidate_data: Dict[str, Any],
                                 case_id: int,
                                 section_type: str = None) -> CandidateRoleClass:
        """
        Store a newly discovered candidate role class for validation

        Args:
            candidate_data: Dictionary with candidate role class information
            case_id: Case ID where this role was discovered
            section_type: Case section where discovered (facts, questions, etc.)

        Returns:
            CandidateRoleClass: The stored candidate
        """
        try:
            candidate = CandidateRoleClass(
                label=candidate_data.get('label', ''),
                definition=candidate_data.get('definition', ''),
                discovered_in_case_id=case_id,
                discovered_from_section=section_type,
                discovery_confidence=candidate_data.get('confidence', 0.8),
                distinguishing_features=candidate_data.get('distinguishing_features', []),
                professional_scope=candidate_data.get('professional_scope', ''),
                typical_qualifications=candidate_data.get('typical_qualifications', []),
                examples_from_case=candidate_data.get('examples_from_case', []),
                similarity_to_existing=candidate_data.get('similarity_to_existing', 0.0),
                existing_similar_classes=candidate_data.get('existing_similar_classes', []),
                extraction_metadata=candidate_data.get('extraction_metadata', {}),
                validation_priority=self._calculate_validation_priority(candidate_data)
            )

            db.session.add(candidate)
            db.session.commit()

            logger.info(f"Stored candidate role class '{candidate.label}' from case {case_id}")
            return candidate

        except Exception as e:
            logger.error(f"Error storing candidate role class: {e}")
            db.session.rollback()
            raise

    def store_candidate_role_individual(self,
                                      individual_data: Dict[str, Any],
                                      candidate_role_class: CandidateRoleClass,
                                      case_id: int) -> CandidateRoleIndividual:
        """
        Store an individual who fulfills a candidate role class

        Args:
            individual_data: Dictionary with individual information
            candidate_role_class: The candidate role class they fulfill
            case_id: Case ID where this individual appears

        Returns:
            CandidateRoleIndividual: The stored individual
        """
        try:
            individual = CandidateRoleIndividual(
                candidate_role_class_id=candidate_role_class.id,
                individual_name=individual_data.get('name', ''),
                individual_attributes=individual_data.get('attributes', {}),
                case_id=case_id
            )

            db.session.add(individual)
            db.session.commit()

            logger.info(f"Stored individual '{individual.individual_name}' for candidate role '{candidate_role_class.label}'")
            return individual

        except Exception as e:
            logger.error(f"Error storing candidate role individual: {e}")
            db.session.rollback()
            raise

    def get_candidates_for_review(self,
                                status: str = 'pending_review',
                                priority: str = None,
                                limit: int = 20) -> List[CandidateRoleClass]:
        """
        Get candidate role classes that need review

        Args:
            status: Filter by status (pending_review, under_review, etc.)
            priority: Filter by priority (high, medium, low)
            limit: Maximum number of candidates to return

        Returns:
            List of candidate role classes
        """
        try:
            query = CandidateRoleClass.query.filter_by(status=status)

            if priority:
                query = query.filter_by(validation_priority=priority)

            # Order by priority (high first) then by creation date
            query = query.order_by(
                db.case(
                    (CandidateRoleClass.validation_priority == 'high', 1),
                    (CandidateRoleClass.validation_priority == 'medium', 2),
                    else_=3
                ),
                CandidateRoleClass.created_at.desc()
            )

            candidates = query.limit(limit).all()

            logger.info(f"Retrieved {len(candidates)} candidates for review (status: {status}, priority: {priority})")
            return candidates

        except Exception as e:
            logger.error(f"Error retrieving candidates for review: {e}")
            return []

    def get_candidate_details(self, candidate_id: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a candidate role class including individuals

        Args:
            candidate_id: ID of the candidate role class

        Returns:
            Dictionary with candidate details and related individuals
        """
        try:
            candidate = CandidateRoleClass.query.get(candidate_id)
            if not candidate:
                return None

            # Get individuals who fulfill this role
            individuals = CandidateRoleIndividual.query.filter_by(
                candidate_role_class_id=candidate_id
            ).all()

            return {
                'candidate': candidate.to_dict(),
                'individuals': [
                    {
                        'name': ind.individual_name,
                        'attributes': ind.individual_attributes,
                        'case_id': ind.case_id
                    }
                    for ind in individuals
                ],
                'individual_count': len(individuals),
                'cases_involved': list(set(ind.case_id for ind in individuals))
            }

        except Exception as e:
            logger.error(f"Error retrieving candidate details: {e}")
            return None

    def approve_candidate(self,
                         candidate_id: int,
                         reviewed_by: str,
                         approved_label: str = None,
                         approved_definition: str = None,
                         review_notes: str = None) -> bool:
        """
        Approve a candidate role class for integration

        Args:
            candidate_id: ID of the candidate to approve
            reviewed_by: Name/ID of the reviewer
            approved_label: Final approved label (optional)
            approved_definition: Final approved definition (optional)
            review_notes: Review comments

        Returns:
            True if successful, False otherwise
        """
        try:
            candidate = CandidateRoleClass.query.get(candidate_id)
            if not candidate:
                logger.error(f"Candidate {candidate_id} not found")
                return False

            candidate.approve(reviewed_by, approved_label, approved_definition, review_notes)
            db.session.commit()

            logger.info(f"Approved candidate role class '{candidate.label}' (ID: {candidate_id})")
            return True

        except Exception as e:
            logger.error(f"Error approving candidate: {e}")
            db.session.rollback()
            return False

    def reject_candidate(self, candidate_id: int, reviewed_by: str, review_notes: str) -> bool:
        """
        Reject a candidate role class

        Args:
            candidate_id: ID of the candidate to reject
            reviewed_by: Name/ID of the reviewer
            review_notes: Reason for rejection

        Returns:
            True if successful, False otherwise
        """
        try:
            candidate = CandidateRoleClass.query.get(candidate_id)
            if not candidate:
                logger.error(f"Candidate {candidate_id} not found")
                return False

            candidate.reject(reviewed_by, review_notes)
            db.session.commit()

            logger.info(f"Rejected candidate role class '{candidate.label}' (ID: {candidate_id})")
            return True

        except Exception as e:
            logger.error(f"Error rejecting candidate: {e}")
            db.session.rollback()
            return False

    def request_revision(self,
                        candidate_id: int,
                        reviewed_by: str,
                        revision_notes: str,
                        review_notes: str = None) -> bool:
        """
        Request revisions to a candidate role class

        Args:
            candidate_id: ID of the candidate
            reviewed_by: Name/ID of the reviewer
            revision_notes: Specific changes requested
            review_notes: Additional review comments

        Returns:
            True if successful, False otherwise
        """
        try:
            candidate = CandidateRoleClass.query.get(candidate_id)
            if not candidate:
                logger.error(f"Candidate {candidate_id} not found")
                return False

            candidate.request_revision(reviewed_by, revision_notes, review_notes)
            db.session.commit()

            logger.info(f"Requested revision for candidate role class '{candidate.label}' (ID: {candidate_id})")
            return True

        except Exception as e:
            logger.error(f"Error requesting revision: {e}")
            db.session.rollback()
            return False

    def integrate_approved_candidate(self, candidate_id: int) -> bool:
        """
        Integrate an approved candidate into the proethica-intermediate ontology

        Args:
            candidate_id: ID of the approved candidate

        Returns:
            True if successful, False otherwise
        """
        try:
            candidate = CandidateRoleClass.query.get(candidate_id)
            if not candidate or candidate.status != 'approved':
                logger.error(f"Candidate {candidate_id} not found or not approved")
                return False

            # Create the role class in proethica-intermediate via MCP
            role_data = {
                'label': candidate.approved_label,
                'definition': candidate.approved_definition,
                'distinguishing_features': candidate.distinguishing_features,
                'professional_scope': candidate.professional_scope,
                'typical_qualifications': candidate.typical_qualifications,
                'discovered_in_case': candidate.discovered_in_case_id,
                'uri': candidate.proposed_uri
            }

            # Call MCP to add the role class to proethica-intermediate
            result = self.mcp_client.call_tool('add_role_class_to_intermediate', {
                'role_data': role_data,
                'ontology': 'proethica-intermediate'
            })

            if result and result.get('success'):
                # Mark as integrated
                final_uri = result.get('uri', candidate.proposed_uri)
                candidate.mark_integrated('proethica-intermediate', final_uri)
                db.session.commit()

                logger.info(f"Successfully integrated candidate '{candidate.label}' into proethica-intermediate")
                return True
            else:
                logger.error(f"MCP integration failed for candidate {candidate_id}: {result}")
                return False

        except Exception as e:
            logger.error(f"Error integrating candidate: {e}")
            db.session.rollback()
            return False

    def get_validation_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about candidate validation workflow

        Returns:
            Dictionary with validation statistics
        """
        try:
            stats = {
                'total_candidates': CandidateRoleClass.query.count(),
                'by_status': {},
                'by_priority': {},
                'by_discovery_month': {},
                'novel_candidates': CandidateRoleClass.query.filter(
                    CandidateRoleClass.similarity_to_existing < 0.3
                ).count(),
                'needs_attention': CandidateRoleClass.query.filter(
                    db.or_(
                        CandidateRoleClass.similarity_to_existing > 0.6,
                        CandidateRoleClass.discovery_confidence < 0.7,
                        CandidateRoleClass.status == 'needs_revision'
                    )
                ).count()
            }

            # Status breakdown
            status_counts = db.session.query(
                CandidateRoleClass.status,
                db.func.count(CandidateRoleClass.id)
            ).group_by(CandidateRoleClass.status).all()

            stats['by_status'] = {status: count for status, count in status_counts}

            # Priority breakdown
            priority_counts = db.session.query(
                CandidateRoleClass.validation_priority,
                db.func.count(CandidateRoleClass.id)
            ).group_by(CandidateRoleClass.validation_priority).all()

            stats['by_priority'] = {priority: count for priority, count in priority_counts}

            return stats

        except Exception as e:
            logger.error(f"Error getting validation statistics: {e}")
            return {}

    def _calculate_validation_priority(self, candidate_data: Dict[str, Any]) -> str:
        """
        Calculate validation priority based on candidate characteristics

        Args:
            candidate_data: Candidate role class data

        Returns:
            Priority level: 'high', 'medium', or 'low'
        """
        confidence = candidate_data.get('confidence', 0.8)
        similarity = candidate_data.get('similarity_to_existing', 0.0)

        # High priority if:
        # - Very novel (low similarity) and high confidence
        # - Moderate similarity but needs disambiguation
        if (similarity < 0.2 and confidence > 0.8) or (0.4 < similarity < 0.8):
            return 'high'

        # Low priority if:
        # - Very similar to existing (likely duplicate)
        # - Low confidence extraction
        elif similarity > 0.8 or confidence < 0.6:
            return 'low'

        # Medium priority for everything else
        else:
            return 'medium'