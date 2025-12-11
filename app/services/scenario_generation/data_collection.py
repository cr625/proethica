"""
Stage 1: Eligibility Check & Data Collection

Verifies that a case has completed all required analysis passes and collects
all extracted data from multiple sources for scenario generation.

Data Sources:
1. temporary_rdf_storage (ProEthica ai_ethical_dm database) - Case-specific extractions
2. ontology_entities (OntServe ontserve database) - Committed ontology entities
3. Temporal dynamics data (Step 3 outputs)
4. Synthesis data (Step 4 outputs)

Documentation: docs/SCENARIO_GENERATION_CROSS_REFERENCE.md (Stage 1)
"""

from typing import Dict, List, Optional, Any
import json
from datetime import datetime
from sqlalchemy import text

from app import db
from .models import (
    ScenarioSourceData,
    RDFEntity,
    TemporalDynamicsData,
    SynthesisData,
    CaseMetadata,
    ProvenanceData,
    EligibilityReport,
    PassCompletionStatus,
    TimelineEntry,
    Action,
    Event,
    TemporalMarker,
    AllenRelation,
    CausalChain,
    CodeProvision,
    EthicalQuestion,
    EthicalConclusion,
    QuestionConclusionLink,
    ProvisionEntityLink
)


class ScenarioDataCollector:
    """
    Collects all data required for scenario generation.

    Stage 1 of the 9-stage scenario generation pipeline.
    """

    def check_eligibility(self, case_id: int) -> EligibilityReport:
        """
        Check if case is eligible for scenario generation.

        Requirements:
        - Pass 1 complete (Roles, States, Resources in facts+discussion)
        - Pass 2 complete (Principles, Obligations, Constraints, Capabilities)
        - Pass 3 complete (Actions, Events with temporal dynamics)
        - Step 4 complete (Provisions, Q&A synthesis)

        Args:
            case_id: Case ID to check

        Returns:
            EligibilityReport with detailed status
        """
        # Check pass completion
        pass1_status = self._check_pass_completion(case_id, pass_num=1)
        pass2_status = self._check_pass_completion(case_id, pass_num=2)
        pass3_status = self._check_pass_completion(case_id, pass_num=3)

        # Check Step 4 completion
        step4_complete, step4_summary = self._check_step4_completion(case_id)

        # Count entities
        entity_counts = self._count_entities_by_type(case_id)

        # Check temporal dynamics
        has_temporal, temporal_summary = self._check_temporal_dynamics(case_id)

        # Determine overall eligibility
        eligible = all([
            pass1_status.complete,
            pass2_status.complete,
            pass3_status.complete,
            step4_complete
        ])

        # Generate summary
        if eligible:
            summary = f"Case {case_id} is ELIGIBLE for scenario generation. " \
                      f"All passes complete with {sum(entity_counts.values())} total entities."
        else:
            missing = []
            if not pass1_status.complete:
                missing.append("Pass 1")
            if not pass2_status.complete:
                missing.append("Pass 2")
            if not pass3_status.complete:
                missing.append("Pass 3")
            if not step4_complete:
                missing.append("Step 4")
            summary = f"Case {case_id} is NOT ELIGIBLE. Missing: {', '.join(missing)}"

        return EligibilityReport(
            case_id=case_id,
            eligible=eligible,
            pass_completion={
                'pass1': pass1_status,
                'pass2': pass2_status,
                'pass3': pass3_status
            },
            entity_counts=entity_counts,
            has_temporal_dynamics=has_temporal,
            temporal_summary=temporal_summary,
            step4_complete=step4_complete,
            step4_summary=step4_summary,
            summary=summary
        )

    def collect_all_data(self, case_id: int) -> ScenarioSourceData:
        """
        Collect all extracted data for scenario generation.

        Loads entities from two sources:
        1. Temporary entities from ProEthica temporary_rdf_storage
        2. Committed entities from OntServe ontology_entities (via is_published flag)

        Args:
            case_id: Case ID to collect data for

        Returns:
            ScenarioSourceData with complete data package
        """
        # Load temporary (case-specific) entities
        temporary_entities = self._load_temporary_entities(case_id)

        # Load committed entities
        committed_entities = self._load_committed_entities(case_id)

        # Merge entity sets
        merged_entities = self._merge_entity_sets(temporary_entities, committed_entities)

        # Load temporal dynamics
        temporal_dynamics = self._load_temporal_dynamics(case_id)

        # Load synthesis data
        synthesis_data = self._load_synthesis_data(case_id)

        # Load case metadata
        case_metadata = self._load_case_metadata(case_id)

        # Load provenance data
        provenance = self._load_provenance_data(case_id)

        return ScenarioSourceData(
            temporary_entities=temporary_entities,
            committed_entities=committed_entities,
            merged_entities=merged_entities,
            temporal_dynamics=temporal_dynamics,
            synthesis_data=synthesis_data,
            case_metadata=case_metadata,
            provenance=provenance
        )

    # Private methods for pass completion checking

    def _check_pass_completion(self, case_id: int, pass_num: int) -> PassCompletionStatus:
        """
        Check if a specific pass is complete.

        Pass completion criteria:
        - Pass 1: Roles, States, Resources extracted from facts + discussion
        - Pass 2: Principles, Obligations, Constraints, Capabilities extracted
        - Pass 3: Actions, Events extracted with temporal dynamics

        Args:
            case_id: Case ID
            pass_num: Pass number (1, 2, or 3)

        Returns:
            PassCompletionStatus
        """
        # Expected entity types per pass (case-insensitive)
        pass_entity_types = {
            1: ['Role', 'State', 'Resource', 'Roles', 'States', 'Resources'],
            2: ['Principle', 'Obligation', 'Constraint', 'Capability', 'Principles', 'Obligations', 'Constraints', 'Capabilities'],
            3: ['Action', 'Event', 'actions', 'events']
        }

        entity_types = pass_entity_types.get(pass_num, [])

        # Count entities for this pass
        query = text("""
            SELECT entity_type, COUNT(*) as count
            FROM temporary_rdf_storage
            WHERE case_id = :case_id AND entity_type = ANY(:entity_types)
            GROUP BY entity_type
        """)
        results = db.session.execute(query, {"case_id": case_id, "entity_types": entity_types}).fetchall()

        # Get sections from extraction_prompts for this pass
        sections_query = text("""
            SELECT DISTINCT section_type
            FROM extraction_prompts
            WHERE case_id = :case_id AND step_number = :pass_num
        """)
        section_results = db.session.execute(sections_query, {"case_id": case_id, "pass_num": pass_num}).fetchall()
        sections_complete = {row.section_type for row in section_results}

        # Sum entity counts
        entity_count = 0
        for row in results:
            entity_count += row.count

        # Pass is complete if we have entities
        complete = entity_count > 0

        return PassCompletionStatus(
            pass_number=pass_num,
            complete=complete,
            entity_count=entity_count,
            sections_complete=list(sections_complete)
        )

    def _check_step4_completion(self, case_id: int) -> tuple[bool, Dict[str, Any]]:
        """
        Check if Step 4 (whole-case synthesis) is complete.

        Step 4 includes:
        - Code provisions
        - Questions and Conclusions
        - Q→C links

        Args:
            case_id: Case ID

        Returns:
            Tuple of (complete, summary_dict)
        """
        # Check if whole_case_synthesis exists in extraction_prompts (most reliable)
        synthesis_query = text("""
            SELECT COUNT(*) as count
            FROM extraction_prompts
            WHERE case_id = :case_id
              AND concept_type = 'whole_case_synthesis'
              AND step_number = 4
        """)
        synthesis_result = db.session.execute(synthesis_query, {"case_id": case_id}).fetchone()
        has_synthesis = synthesis_result.count > 0 if synthesis_result else False

        # Also check for questions/conclusions entities (case-insensitive)
        entity_query = text("""
            SELECT entity_type, COUNT(*) as count
            FROM temporary_rdf_storage
            WHERE case_id = :case_id
              AND (LOWER(entity_type) = 'question'
                   OR LOWER(entity_type) = 'questions'
                   OR LOWER(entity_type) = 'conclusion'
                   OR LOWER(entity_type) = 'conclusions')
            GROUP BY entity_type
        """)
        entity_results = db.session.execute(entity_query, {"case_id": case_id}).fetchall()

        counts = {row.entity_type.lower(): row.count for row in entity_results}
        question_count = counts.get('questions', 0) + counts.get('question', 0)
        conclusion_count = counts.get('conclusions', 0) + counts.get('conclusion', 0)

        # Complete if synthesis record exists OR if we have questions/conclusions
        complete = has_synthesis or question_count > 0 or conclusion_count > 0

        summary = {
            'questions': question_count,
            'conclusions': conclusion_count,
            'synthesis_record': has_synthesis,
            'complete': complete
        }

        return complete, summary

    def _count_entities_by_type(self, case_id: int) -> Dict[str, int]:
        """
        Count extracted entities by type.

        Args:
            case_id: Case ID

        Returns:
            Dictionary mapping entity type to count
        """
        query = text("""
            SELECT entity_type, COUNT(*) as count
            FROM temporary_rdf_storage
            WHERE case_id = :case_id
            GROUP BY entity_type
        """)
        results = db.session.execute(query, {"case_id": case_id}).fetchall()
        return {row.entity_type: row.count for row in results}

    def _check_temporal_dynamics(self, case_id: int) -> tuple[bool, Dict[str, Any]]:
        """
        Check if temporal dynamics data is available.

        Temporal dynamics from Step 3 includes:
        - Actions with volition/intention metadata
        - Events with emergency classification
        - Timeline sequence

        Args:
            case_id: Case ID

        Returns:
            Tuple of (available, summary_dict)
        """
        action_count = self._count_entities_by_type(case_id).get('Action', 0)
        event_count = self._count_entities_by_type(case_id).get('Event', 0)

        available = action_count > 0 or event_count > 0

        summary = {
            'actions': action_count,
            'events': event_count,
            'available': available
        }

        return available, summary

    # Private methods for data loading

    def _load_temporary_entities(self, case_id: int) -> Dict[str, List[RDFEntity]]:
        """
        Load entities from temporary_rdf_storage in ProEthica.

        Returns all entities (committed and uncommitted) for this case.

        Args:
            case_id: Case ID

        Returns:
            Dictionary mapping entity type to list of RDFEntity objects
        """
        query = text("""
            SELECT entity_type, entity_uri, entity_label, entity_definition,
                   rdf_turtle, rdf_json_ld, is_published, is_selected, is_reviewed,
                   extraction_session_id
            FROM temporary_rdf_storage
            WHERE case_id = :case_id
            ORDER BY entity_type, entity_label
        """)
        results = db.session.execute(query, {"case_id": case_id}).fetchall()

        entities_by_type = {}
        for row in results:
            entity_type = row.entity_type
            if entity_type not in entities_by_type:
                entities_by_type[entity_type] = []

            # Parse JSON-LD if present
            rdf_json_ld = None
            if row.rdf_json_ld:
                try:
                    rdf_json_ld = json.loads(row.rdf_json_ld) if isinstance(row.rdf_json_ld, str) else row.rdf_json_ld
                except (json.JSONDecodeError, TypeError):
                    rdf_json_ld = None

            entities_by_type[entity_type].append(RDFEntity(
                uri=row.entity_uri,
                label=row.entity_label,
                entity_type=entity_type,
                definition=row.entity_definition,
                rdf_turtle=row.rdf_turtle,
                rdf_json_ld=rdf_json_ld,
                is_published=row.is_published or False,
                is_selected=row.is_selected or False,
                is_reviewed=row.is_reviewed or False,
                source='temporary',
                case_id=case_id,
                section_type=None,  # Not tracked in temporary_rdf_storage
                extraction_session_id=row.extraction_session_id
            ))

        return entities_by_type

    def _load_committed_entities(self, case_id: int) -> Dict[str, List[RDFEntity]]:
        """
        Load committed entities from OntServe ontology_entities.

        Current approach: Query entities marked is_published=true in temporary_rdf_storage.
        Future enhancement: Also load general engineering ethics entities via MCP.

        Args:
            case_id: Case ID

        Returns:
            Dictionary mapping entity type to list of RDFEntity objects
        """
        # Find URIs of committed entities from this case
        # Note: DISTINCT ON (entity_uri) to handle duplicates, ordering by entity_uri
        query = text("""
            SELECT DISTINCT ON (entity_uri) entity_uri, entity_type, entity_label, entity_definition,
                   rdf_turtle, rdf_json_ld
            FROM temporary_rdf_storage
            WHERE case_id = :case_id AND is_published = true
            ORDER BY entity_uri
        """)
        results = db.session.execute(query, {"case_id": case_id}).fetchall()

        entities_by_type = {}
        for row in results:
            entity_type = row.entity_type
            if entity_type not in entities_by_type:
                entities_by_type[entity_type] = []

            # Parse JSON-LD if present
            rdf_json_ld = None
            if row.rdf_json_ld:
                try:
                    rdf_json_ld = json.loads(row.rdf_json_ld) if isinstance(row.rdf_json_ld, str) else row.rdf_json_ld
                except (json.JSONDecodeError, TypeError):
                    rdf_json_ld = None

            entities_by_type[entity_type].append(RDFEntity(
                uri=row.entity_uri,
                label=row.entity_label,
                entity_type=entity_type,
                definition=row.entity_definition,
                rdf_turtle=row.rdf_turtle,
                rdf_json_ld=rdf_json_ld,
                source='committed',
                is_published=True
            ))

        return entities_by_type

    def _merge_entity_sets(
        self,
        temporary: Dict[str, List[RDFEntity]],
        committed: Dict[str, List[RDFEntity]]
    ) -> Dict[str, List[RDFEntity]]:
        """
        Merge temporary and committed entities.

        Strategy:
        - Include all temporary entities (case-specific)
        - Add committed entities that provide ontological grounding
        - For duplicates (same URI), prefer temporary version for case-specific details
        - Tag each entity with source for traceability

        Args:
            temporary: Temporary entities from ProEthica
            committed: Committed entities from OntServe

        Returns:
            Merged dictionary of entities
        """
        merged = {}

        # Start with temporary entities
        for entity_type, entities in temporary.items():
            merged[entity_type] = entities.copy()

        # Add committed entities not already present
        for entity_type, entities in committed.items():
            if entity_type not in merged:
                merged[entity_type] = []

            existing_uris = {e.uri for e in merged[entity_type]}
            for entity in entities:
                if entity.uri not in existing_uris:
                    entity.enrichment_source = 'committed_ontology'
                    merged[entity_type].append(entity)

        return merged

    def _load_temporal_dynamics(self, case_id: int) -> TemporalDynamicsData:
        """
        Load temporal dynamics data from Step 3.

        Note: Full implementation requires querying Step 3 output storage.
        For now, creates empty structure as placeholder.

        Args:
            case_id: Case ID

        Returns:
            TemporalDynamicsData
        """
        # TODO: Implement full temporal dynamics loading
        # This requires querying Step 3 Stage outputs (timeline, actions, events, etc.)
        # For now, return empty structure
        return TemporalDynamicsData()

    def _load_synthesis_data(self, case_id: int) -> SynthesisData:
        """
        Load synthesis data from Step 4.

        Note: Full implementation requires querying Step 4 output storage.
        For now, creates empty structure as placeholder.

        Args:
            case_id: Case ID

        Returns:
            SynthesisData
        """
        # TODO: Implement full synthesis data loading
        # This requires querying Step 4 outputs (provisions, Q&A, links)
        # For now, return empty structure
        return SynthesisData()

    def _load_case_metadata(self, case_id: int) -> CaseMetadata:
        """
        Load case metadata.

        Args:
            case_id: Case ID

        Returns:
            CaseMetadata
        """
        # Query documents table (ProEthica uses 'documents', not 'cases')
        query = text("""
            SELECT id, title
            FROM documents
            WHERE id = :case_id
        """)
        result = db.session.execute(query, {"case_id": case_id}).fetchone()

        if result:
            return CaseMetadata(
                case_id=result.id,
                title=result.title or f"Case {result.id}",
                case_number=str(result.id),  # Use ID as case number
                domain="engineering_ethics"
            )
        else:
            return CaseMetadata(
                case_id=case_id,
                title=f"Case {case_id}",
                domain="engineering_ethics"
            )

    def _load_provenance_data(self, case_id: int) -> ProvenanceData:
        """
        Load provenance data from extraction_prompts.

        Args:
            case_id: Case ID

        Returns:
            ProvenanceData
        """
        query = text("""
            SELECT DISTINCT extraction_session_id, step_number
            FROM extraction_prompts
            WHERE case_id = :case_id
        """)
        results = db.session.execute(query, {"case_id": case_id}).fetchall()

        extraction_sessions = [row.extraction_session_id for row in results]
        step_numbers = {row.step_number for row in results}

        pass_completion = {
            'pass1': 1 in step_numbers,
            'pass2': 2 in step_numbers,
            'pass3': 3 in step_numbers
        }

        # Check Step 4 completion
        step4_complete, _ = self._check_step4_completion(case_id)

        return ProvenanceData(
            extraction_sessions=extraction_sessions,
            pass_completion=pass_completion,
            step4_complete=step4_complete
        )
