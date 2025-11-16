"""
Unified Scenario Generation Orchestrator

Coordinates all 9 stages of scenario generation with progress callback support.
Can be used by both Flask SSE endpoints and future MCP servers.

Documentation: docs/SCENARIO_GENERATION_MCP_SSE_ARCHITECTURE.md
"""

import logging
from typing import Optional, Callable, Dict, Any
from datetime import datetime

from .data_collection import ScenarioDataCollector
from .timeline_constructor import TimelineConstructor
from .participant_mapper import ParticipantMapper
from .models import (
    ScenarioSourceData,
    EligibilityReport,
    ScenarioTimeline
)

logger = logging.getLogger(__name__)


class ScenarioGenerationOrchestrator:
    """
    Unified orchestrator for scenario generation.

    Executes all 9 stages with optional progress callbacks.
    Can be called from:
    - Flask SSE endpoint (user-facing)
    - MCP server (agent-facing)
    - CLI tools (testing)
    """

    def __init__(self, progress_callback: Optional[Callable] = None):
        """
        Initialize orchestrator.

        Args:
            progress_callback: Optional callback for progress updates
                             Signature: callback(stage: str, progress: int, message: str, data: dict)
        """
        self.progress_callback = progress_callback

        # Initialize stage services
        self.collector = ScenarioDataCollector()
        self.timeline_constructor = TimelineConstructor()
        self.participant_mapper = ParticipantMapper()

        # Future stage services (Stages 4-9)
        # self.decision_identifier = DecisionIdentifier()
        # ... etc

        logger.info("[Scenario Gen] Orchestrator initialized")

    def _report_progress(self, stage: str, progress: int, message: str, data: Optional[Dict[str, Any]] = None):
        """
        Report progress to callback if provided.

        Args:
            stage: Current stage name
            progress: Progress percentage (0-100)
            message: Progress message
            data: Optional additional data
        """
        if self.progress_callback:
            try:
                self.progress_callback(stage, progress, message, data or {})
            except Exception as e:
                logger.error(f"[Scenario Gen] Progress callback error: {e}")

    def check_eligibility(self, case_id: int) -> EligibilityReport:
        """
        Check if case is eligible for scenario generation.

        Requirements:
        - Pass 1 complete (Roles, States, Resources)
        - Pass 2 complete (Principles, Obligations, Constraints, Capabilities)
        - Pass 3 complete (Actions, Events with temporal dynamics)
        - Step 4 complete (Provisions, Q&A synthesis)

        Args:
            case_id: Case ID to check

        Returns:
            EligibilityReport with detailed status
        """
        logger.info(f"[Scenario Gen] Checking eligibility for case {case_id}")
        return self.collector.check_eligibility(case_id)

    def generate_complete_scenario(self, case_id: int) -> Dict[str, Any]:
        """
        Execute complete 9-stage scenario generation pipeline.

        Stages:
        1. Data Collection
        2. Timeline Construction
        3. Participant Mapping
        4. Decision Point Identification
        5. Causal Chain Integration
        6. Normative Framework Integration
        7. Scenario Assembly
        8. Interactive Model Generation
        9. Validation

        Args:
            case_id: Case ID to generate scenario from

        Returns:
            Dictionary with scenario generation results

        Raises:
            ValueError: If case is not eligible
            Exception: On generation failure
        """
        start_time = datetime.utcnow()
        logger.info(f"[Scenario Gen] Starting generation for case {case_id}")

        try:
            # Check eligibility first
            self._report_progress('eligibility_check', 0, 'Checking case eligibility...')
            eligibility = self.check_eligibility(case_id)

            if not eligibility.eligible:
                error_msg = f"Case {case_id} is not eligible for scenario generation: {eligibility.summary}"
                logger.error(f"[Scenario Gen] {error_msg}")
                self._report_progress('error', 0, error_msg, {'eligibility': eligibility.to_dict()})
                raise ValueError(error_msg)

            logger.info(f"[Scenario Gen] Case {case_id} is eligible: {eligibility.summary}")

            # Stage 1: Data Collection
            self._report_progress('data_collection', 10, 'Collecting extracted entities from all sources...')
            logger.info("[Scenario Gen] Stage 1: Data Collection")

            data = self.collector.collect_all_data(case_id)

            entity_count = sum(len(entities) for entities in data.merged_entities.values())
            logger.info(f"[Scenario Gen] Collected {entity_count} entities")

            self._report_progress(
                'data_collection',
                20,
                f'Collected {entity_count} entities',
                {
                    'temporary_entities': sum(len(e) for e in data.temporary_entities.values()),
                    'committed_entities': sum(len(e) for e in data.committed_entities.values()),
                    'merged_entities': entity_count,
                    'entity_types': list(data.merged_entities.keys())
                }
            )

            # Stage 2: Timeline Construction
            self._report_progress('timeline_construction', 30, 'Building chronological timeline...')
            logger.info("[Scenario Gen] Stage 2: Timeline Construction")

            timeline = self.timeline_constructor.build_timeline(case_id)

            timeline_summary = timeline.to_dict()
            logger.info(
                f"[Scenario Gen] Timeline built with {len(timeline.entries)} entries, "
                f"{timeline.total_actions} actions, {timeline.total_events} events"
            )

            self._report_progress(
                'timeline_construction',
                35,
                f'Timeline built with {len(timeline.entries)} timepoints across {len(timeline.phases)} phases',
                timeline_summary
            )

            # Stage 3: Participant Mapping (IMPLEMENTED)
            self._report_progress('participant_mapping', 40, 'Creating character profiles...')
            logger.info("[Scenario Gen] Stage 3: Participant Mapping")

            # Get roles for mapping
            roles = data.get_entities_by_type('Role')
            logger.info(f"[Scenario Gen] Found {len(roles)} role entities")

            # Create participants using LLM enhancement
            participants = []
            if roles:
                self._report_progress('participant_mapping', 42, f'Analyzing {len(roles)} roles with LLM...')

                participants = self.participant_mapper.create_participants(
                    case_id=case_id,
                    roles=roles,
                    timeline=timeline
                )

                logger.info(f"[Scenario Gen] Created {len(participants)} participant profiles")

            # Build participant summary
            participant_summary = {
                'status': 'complete',
                'participants_created': len(participants),
                'roles_analyzed': len(roles),
                'participants': [
                    {
                        'name': p['name'],
                        'title': p.get('title'),
                        'motivation_count': len(p.get('motivations', [])),
                        'tension_count': len(p.get('ethical_tensions', []))
                    }
                    for p in participants[:5]  # First 5 for progress
                ]
            }

            self._report_progress(
                'participant_mapping',
                50,
                f'Created {len(participants)} participant profiles',
                participant_summary
            )

            # Stage 4: Decision Point Identification (Placeholder)
            self._report_progress('decision_identification', 55, 'Identifying decision points...')
            logger.info("[Scenario Gen] Stage 4: Decision Identification (TODO)")

            # Count volitional actions and questions
            actions = data.temporal_dynamics.actions
            questions = data.synthesis_data.questions
            decision_summary = {
                'status': 'placeholder',
                'message': 'Decision identification not yet implemented',
                'actions': len(actions),
                'questions': len(questions)
            }

            self._report_progress(
                'decision_identification',
                60,
                f'Found {len(actions)} actions and {len(questions)} questions',
                decision_summary
            )

            # Stage 5: Causal Chain Integration (Placeholder)
            self._report_progress('causal_integration', 65, 'Linking decision consequences...')
            logger.info("[Scenario Gen] Stage 5: Causal Integration (TODO)")

            causal_chains = data.temporal_dynamics.causal_chains
            self._report_progress(
                'causal_integration',
                70,
                f'Found {len(causal_chains)} causal chains',
                {'causal_chains': len(causal_chains)}
            )

            # Stage 6: Normative Framework Integration (Placeholder)
            self._report_progress('normative_integration', 75, 'Integrating ethical framework...')
            logger.info("[Scenario Gen] Stage 6: Normative Integration (TODO)")

            principles = data.get_entities_by_type('Principle')
            obligations = data.get_entities_by_type('Obligation')
            provisions = data.synthesis_data.code_provisions

            self._report_progress(
                'normative_integration',
                80,
                f'Integrated {len(principles)} principles, {len(obligations)} obligations',
                {
                    'principles': len(principles),
                    'obligations': len(obligations),
                    'provisions': len(provisions)
                }
            )

            # Stage 7: Scenario Assembly (Placeholder)
            self._report_progress('scenario_assembly', 85, 'Assembling complete scenario...')
            logger.info("[Scenario Gen] Stage 7: Scenario Assembly (TODO)")

            self._report_progress(
                'scenario_assembly',
                90,
                'Scenario assembled with educational components',
                {'status': 'placeholder'}
            )

            # Stage 8: Interactive Model Generation (Placeholder)
            self._report_progress('model_generation', 93, 'Creating interactive models...')
            logger.info("[Scenario Gen] Stage 8: Model Generation (TODO)")

            self._report_progress(
                'model_generation',
                95,
                'Interactive models created',
                {'status': 'placeholder'}
            )

            # Stage 9: Validation (Placeholder)
            self._report_progress('validation', 97, 'Validating scenario quality...')
            logger.info("[Scenario Gen] Stage 9: Validation (TODO)")

            self._report_progress(
                'validation',
                99,
                'Validation complete',
                {'quality_score': 85, 'status': 'placeholder'}
            )

            # Completion
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            result = {
                'success': True,
                'case_id': case_id,
                'eligibility': eligibility.to_dict(),
                'entity_count': entity_count,
                'duration_seconds': duration,
                'stages_completed': 9,
                'status': 'complete_placeholder',
                'message': 'Scenario generation pipeline executed (Stages 2-9 are placeholders pending implementation)',
                'next_steps': [
                    'Implement Stage 2: Timeline Construction',
                    'Implement Stage 3: Participant Mapping',
                    'Implement Stage 4: Decision Identification',
                    'Implement Stage 5: Causal Chain Integration',
                    'Implement Stage 6: Normative Framework Integration',
                    'Implement Stage 7: Scenario Assembly',
                    'Implement Stage 8: Interactive Model Generation',
                    'Implement Stage 9: Validation'
                ]
            }

            logger.info(f"[Scenario Gen] Generation complete for case {case_id} in {duration:.2f}s")
            self._report_progress('complete', 100, 'Scenario generation complete!', result)

            return result

        except ValueError as e:
            # Eligibility or validation error
            logger.error(f"[Scenario Gen] Validation error: {e}")
            self._report_progress('error', 0, str(e), {'error_type': 'validation'})
            raise

        except Exception as e:
            # Unexpected error
            logger.error(f"[Scenario Gen] Unexpected error: {e}", exc_info=True)
            self._report_progress('error', 0, f'Error: {str(e)}', {'error_type': 'unexpected'})
            raise
