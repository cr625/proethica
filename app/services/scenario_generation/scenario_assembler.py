"""
Scenario Assembly Service - Stage 7

Combines all Stage 1-6 outputs into unified scenario structure.
No new LLM calls - purely assembly and structuring.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

from .models import (
    ScenarioTimeline,
    AssembledScenario,
    ScenarioMetadata
)
from .participant_mapper import ParticipantMappingResult
from .decision_identifier import DecisionIdentificationResult

logger = logging.getLogger(__name__)


class ScenarioAssembler:
    """
    Stage 7: Assembles complete scenario from Stages 1-6 outputs.

    Purpose: Combine timeline, participants, decisions, and analytical frameworks
    into unified structure ready for visualization (Stage 8) and validation (Stage 9).
    """

    def assemble_scenario(
        self,
        case_id: int,
        case_title: str,
        timeline_result: ScenarioTimeline,
        participant_result: ParticipantMappingResult,
        decision_result: DecisionIdentificationResult,
        action_mapping: Optional[Dict] = None,
        transformation: Optional[Dict] = None,
        entity_summary: Optional[Dict] = None
    ) -> AssembledScenario:
        """
        Assemble complete scenario from all Stage 1-6 components.

        Args:
            case_id: Case document ID
            case_title: Case title
            timeline_result: Stage 2 output (timeline with phases)
            participant_result: Stage 3 output (character profiles)
            decision_result: Stage 4 output (decision points)
            action_mapping: Stage 5 data (from Step 4 Part E)
            transformation: Stage 6 data (from Step 4 Part F)
            entity_summary: Stage 1 summary (entity counts)

        Returns:
            AssembledScenario with all components integrated
        """
        logger.info(f"[Scenario Assembler] Assembling scenario for case {case_id}")

        # Extract components
        timeline = timeline_result.to_dict()
        participants = participant_result.to_dict()
        decisions = decision_result.to_dict()

        # Build metadata
        metadata = self._build_metadata(
            case_id=case_id,
            case_title=case_title,
            timeline_result=timeline_result,
            participant_result=participant_result,
            decision_result=decision_result,
            entity_summary=entity_summary
        )

        # Build scenario structure
        scenario_data = {
            'case_id': case_id,
            'title': case_title,
            'metadata': metadata,

            # Stage 2: Timeline
            'timeline': {
                'entries': timeline.get('entries', []),
                'phases': timeline.get('phases', {}),
                'total_timepoints': timeline.get('total_entries', 0),
                'llm_enhanced': False  # Timeline built from temporal dynamics data, not LLM-enhanced
            },

            # Stage 3: Participants
            'participants': {
                'profiles': participants.get('participants', []),
                'total_count': len(participants.get('participants', [])),
                'protagonist': participants.get('protagonist_id'),
                'relationship_map': participants.get('relationship_map', []),
                'llm_enhanced': participants.get('llm_enrichment') is not None,
                'analysis_notes': participants.get('analysis_notes')
            },

            # Stage 4: Decisions
            'decisions': {
                'decision_points': decisions.get('decision_points', []),
                'total_count': decisions.get('total_decisions', 0),
                'has_institutional_analysis': any(
                    d.get('institutional_rule_analysis') for d in decisions.get('decision_points', [])
                ),
                'has_transformation_analysis': any(
                    d.get('transformation_analysis') for d in decisions.get('decision_points', [])
                )
            },

            # Stage 5: Causal Chains (from Part E)
            'causal_chains': {
                'actions_taken': action_mapping.get('actions_taken', []) if action_mapping else [],
                'actions_not_taken': action_mapping.get('actions_not_taken', []) if action_mapping else [],
                'transformation_points': action_mapping.get('transformation_points', []) if action_mapping else [],
                'rule_shifts': action_mapping.get('rule_shifts', []) if action_mapping else []
            } if action_mapping else None,

            # Stage 6: Normative Framework (from Part F)
            'normative_framework': {
                'transformation_type': transformation.get('transformation_type'),
                'confidence': transformation.get('confidence'),
                'symbolic_significance': transformation.get('symbolic_significance'),
                'pattern_name': transformation.get('pattern_name')
            } if transformation else None,

            # Assembly metadata
            'assembly_info': {
                'assembled_at': datetime.utcnow().isoformat(),
                'stages_included': self._count_stages_included(
                    timeline, participants, decisions, action_mapping, transformation
                ),
                'completeness_score': self._calculate_completeness(
                    timeline, participants, decisions, action_mapping, transformation
                )
            },

            # LLM Provenance Tracking
            'llm_provenance': {
                'stage_2b_timeline_enrichment': {
                    'used': hasattr(timeline_result, 'llm_enhanced') and timeline_result.llm_enhanced,
                    'prompt': timeline_result.llm_prompt if hasattr(timeline_result, 'llm_prompt') else None,
                    'response': timeline_result.llm_response if hasattr(timeline_result, 'llm_response') else None,
                    'model': 'claude-sonnet-4-20250514',
                    'source_data': 'Step 3 (Temporal Dynamics)',
                    'source_url': f'/scenario_pipeline/case/{case_id}/step3'
                },
                'stage_3_participant_enhancement': {
                    'used': participant_result.llm_enrichment is not None,
                    'prompt': participant_result.llm_prompt,
                    'response': participant_result.llm_response,
                    'model': 'claude-sonnet-4-20250514',
                    'source_data': 'Pass 1 (Role Extraction)',
                    'source_url': f'/scenario_pipeline/case/{case_id}/step1'
                },
                'stage_4_decision_identification': {
                    'used': False,  # Currently references Step 4 Part D (no new LLM calls)
                    'source_data': 'Step 4 Part D (Institutional Rule Analysis)',
                    'source_url': f'/scenario_pipeline/case/{case_id}/step4#part-d'
                },
                'stage_5_causal_chains': {
                    'used': False,  # References Step 4 Part E
                    'source_data': 'Step 4 Part E (Action-Rule Mapping)',
                    'source_url': f'/scenario_pipeline/case/{case_id}/step4#part-e'
                },
                'stage_6_normative_framework': {
                    'used': False,  # References Step 4 Part F
                    'source_data': 'Step 4 Part F (Transformation Classification)',
                    'source_url': f'/scenario_pipeline/case/{case_id}/step4#part-f'
                }
            }
        }

        assembled = AssembledScenario(
            case_id=case_id,
            title=case_title,
            scenario_data=scenario_data,
            metadata=metadata
        )

        logger.info(f"[Scenario Assembler] Assembly complete: {assembled.metadata.total_components} components")
        return assembled

    def _build_metadata(
        self,
        case_id: int,
        case_title: str,
        timeline_result: ScenarioTimeline,
        participant_result: ParticipantMappingResult,
        decision_result: DecisionIdentificationResult,
        entity_summary: Optional[Dict] = None
    ) -> ScenarioMetadata:
        """Build scenario metadata for quick reference."""
        return ScenarioMetadata(
            case_id=case_id,
            title=case_title,
            created_at=datetime.utcnow(),
            total_timepoints=len(timeline_result.entries) if timeline_result else 0,
            total_participants=len(participant_result.participants) if participant_result else 0,
            total_decisions=decision_result.total_decisions if decision_result else 0,
            total_entities=entity_summary.get('total', 0) if entity_summary else 0,
            total_components=sum([
                len(timeline_result.entries) if timeline_result else 0,
                len(participant_result.participants) if participant_result else 0,
                decision_result.total_decisions if decision_result else 0
            ]),
            phases=timeline_result.phases if timeline_result else {},
            has_llm_enhancement=(
                participant_result.llm_enrichment is not None if participant_result else False
            )
        )

    def _count_stages_included(
        self,
        timeline: Dict,
        participants: Dict,
        decisions: Dict,
        action_mapping: Optional[Dict],
        transformation: Optional[Dict]
    ) -> int:
        """Count how many stages contributed data."""
        count = 0
        if timeline.get('entries'): count += 1  # Stage 2
        if participants.get('participants'): count += 1  # Stage 3
        if decisions.get('decision_points'): count += 1  # Stage 4
        if action_mapping: count += 1  # Stage 5
        if transformation: count += 1  # Stage 6
        return count

    def _calculate_completeness(
        self,
        timeline: Dict,
        participants: Dict,
        decisions: Dict,
        action_mapping: Optional[Dict],
        transformation: Optional[Dict]
    ) -> float:
        """
        Calculate scenario completeness score (0.0 - 1.0).

        Weights:
        - Timeline: 0.2
        - Participants: 0.2
        - Decisions: 0.2
        - Causal chains: 0.2
        - Normative framework: 0.2
        """
        score = 0.0

        # Timeline (0.2)
        if timeline.get('entries'):
            score += 0.2

        # Participants (0.2)
        if participants.get('participants'):
            score += 0.2

        # Decisions (0.2)
        if decisions.get('decision_points'):
            score += 0.2

        # Causal chains (0.2)
        if action_mapping:
            score += 0.2

        # Normative framework (0.2)
        if transformation:
            score += 0.2

        return round(score, 2)

    def to_json(self, assembled: AssembledScenario, indent: int = 2) -> str:
        """Export assembled scenario as JSON."""
        return json.dumps(assembled.scenario_data, indent=indent, default=str)

    def save_to_database(self, assembled: AssembledScenario) -> bool:
        """
        Save assembled scenario to database.

        Uses PostgreSQL UPSERT to replace existing scenario for the case.
        """
        try:
            from app.models import db
            from sqlalchemy import text

            # UPSERT query (replace if exists)
            # Note: Cast scenario_data parameter to JSONB in Python first
            query = text("""
                INSERT INTO scenario_assemblies (
                    case_id,
                    scenario_data,
                    completeness_score,
                    stages_included,
                    total_components,
                    created_at,
                    updated_at
                )
                VALUES (
                    :case_id,
                    :scenario_data,
                    :completeness_score,
                    :stages_included,
                    :total_components,
                    NOW(),
                    NOW()
                )
                ON CONFLICT (case_id)
                DO UPDATE SET
                    scenario_data = EXCLUDED.scenario_data,
                    completeness_score = EXCLUDED.completeness_score,
                    stages_included = EXCLUDED.stages_included,
                    total_components = EXCLUDED.total_components,
                    updated_at = NOW()
                RETURNING id
            """)

            result = db.session.execute(query, {
                'case_id': assembled.case_id,
                'scenario_data': json.dumps(assembled.scenario_data, default=str),
                'completeness_score': assembled.scenario_data['assembly_info']['completeness_score'],
                'stages_included': assembled.scenario_data['assembly_info']['stages_included'],
                'total_components': assembled.metadata.total_components
            })

            db.session.commit()
            scenario_id = result.fetchone()[0]
            logger.info(f"[Scenario Assembler] Saved to database (id: {scenario_id})")
            return True

        except Exception as e:
            logger.error(f"[Scenario Assembler] Database save failed: {e}")
            db.session.rollback()
            return False

    def save_to_file(self, assembled: AssembledScenario, file_path: str) -> bool:
        """Save assembled scenario to JSON file (for debugging/export)."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.to_json(assembled))
            logger.info(f"[Scenario Assembler] Saved to {file_path}")
            return True
        except Exception as e:
            logger.error(f"[Scenario Assembler] Failed to save: {e}")
            return False
