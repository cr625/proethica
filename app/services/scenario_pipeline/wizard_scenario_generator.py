"""
Wizard Scenario Generator Service.

Converts enhanced timeline data into interactive wizard scenarios
that can be played step-by-step like existing scenarios.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime
from app import db
from app.models.scenario import Scenario
from app.models.wizard import WizardStep
from app.models import Document

logger = logging.getLogger(__name__)

class WizardScenarioGenerator:
    """Generates interactive wizard scenarios from enhanced timeline data."""
    
    def __init__(self):
        self.logger = logger
    
    def create_wizard_scenario_from_enhanced_timeline(
        self, 
        case: Document, 
        enhanced_timeline: Dict[str, Any]
    ) -> int:
        """
        Create a complete wizard scenario from enhanced timeline data.
        
        Args:
            case: The source case document
            enhanced_timeline: Enhanced timeline data from EnhancedLLMScenarioService
            
        Returns:
            scenario_id: ID of the created scenario
        """
        try:
            # Create the main scenario record
            scenario = self._create_scenario_record(case, enhanced_timeline)
            db.session.add(scenario)
            db.session.flush()  # Get the ID
            
            # Generate wizard steps from timeline
            wizard_steps = self._generate_wizard_steps(scenario.id, enhanced_timeline)
            
            # Add all steps to database
            for step in wizard_steps:
                db.session.add(step)
            
            db.session.commit()
            
            logger.info(f"Created wizard scenario {scenario.id} with {len(wizard_steps)} steps")
            return scenario.id
            
        except Exception as e:
            logger.error(f"Failed to create wizard scenario: {e}")
            db.session.rollback()
            raise
    
    def _create_scenario_record(self, case: Document, enhanced_timeline: Dict[str, Any]) -> Scenario:
        """Create the main scenario database record."""
        
        # Extract key info from enhanced timeline
        stats = enhanced_timeline.get('stats', {})
        participants = enhanced_timeline.get('participants', [])
        
        # Generate scenario name from case title
        scenario_name = f"Enhanced: {case.title}"
        if len(scenario_name) > 255:
            scenario_name = scenario_name[:252] + "..."
            
        # Create description from case content
        description = f"Interactive ethical decision scenario generated from case {case.id}. "
        description += f"Contains {stats.get('event_count', 0)} events and {stats.get('decision_count', 0)} decisions."
        
        if participants:
            description += f" Key participants: {', '.join([p['name'] for p in participants[:3]])}."
        
        scenario = Scenario(
            name=scenario_name,
            description=description,
            world_id=case.world_id or 1,  # Default to world 1 if not set
            scenario_metadata={
                'source_case_id': case.id,
                'generation_method': 'enhanced_llm',
                'pipeline_version': enhanced_timeline.get('extraction_metadata', {}).get('llm_model', 'enhanced_llm_v1'),
                'generated_at': datetime.utcnow().isoformat(),
                'stats': stats,
                'participants': participants,
                'ontology_enrichment_status': enhanced_timeline.get('ontology_enrichment_status'),
                'temporal_evidence_count': len(enhanced_timeline.get('temporal_evidence', []))
            }
        )
        
        return scenario
    
    def _generate_wizard_steps(self, scenario_id: int, enhanced_timeline: Dict[str, Any]) -> List[WizardStep]:
        """Generate wizard steps from enhanced timeline data."""
        
        steps = []
        step_number = 1
        
        # Get events and decisions from timeline
        timeline_events = enhanced_timeline.get('timeline_events', [])
        enhanced_decisions = enhanced_timeline.get('enhanced_decisions', [])
        
        # Sort timeline events by sequence number
        sorted_events = sorted(timeline_events, key=lambda x: x.get('sequence_number', 0))
        
        # Create event steps
        for event in sorted_events:
            step = self._create_event_step(scenario_id, step_number, event)
            steps.append(step)
            step_number += 1
        
        # Create decision steps
        for decision in enhanced_decisions:
            # Convert EnhancedDecision dataclass to dictionary
            if hasattr(decision, 'id'):  # It's an EnhancedDecision object
                decision_dict = {
                    'id': decision.id,
                    'title': decision.title,
                    'question': decision.question,
                    'context': decision.context,
                    'section_source': decision.section_source,
                    'temporal_triggers': decision.temporal_triggers,
                    'ontology_categories': decision.ontology_categories,
                    'evidence_text': decision.evidence_text
                }
            else:  # Already a dictionary
                decision_dict = decision
                
            step = self._create_decision_step(scenario_id, step_number, decision_dict)
            steps.append(step)
            step_number += 1
            
        return steps
    
    def _create_event_step(self, scenario_id: int, step_number: int, event_data: Dict[str, Any]) -> WizardStep:
        """Create a wizard step for a timeline event."""
        
        title = event_data.get('title', f"Event {step_number}")
        description = event_data.get('description', event_data.get('text', ''))
        
        # Create narrative content
        narrative = self._create_event_narrative(event_data)
        
        # Handle timeline_reference_id safely
        reference_id = event_data.get('sequence_number') or event_data.get('id')
        if reference_id:
            try:
                reference_id = int(reference_id)
            except (ValueError, TypeError):
                reference_id = None
        
        step = WizardStep(
            scenario_id=scenario_id,
            step_number=step_number,
            step_type='event',
            title=title,
            narrative_content=narrative,
            timeline_reference_id=reference_id,
            timeline_reference_type='timeline_event',
            step_metadata={
                'event_type': event_data.get('event_type', 'action'),
                'participants': event_data.get('participants', []),
                'section_source': event_data.get('section_source', ''),
                'extraction_method': event_data.get('extraction_method', 'llm_semantic'),
                'original_event_data': event_data
            }
        )
        
        return step
    
    def _create_decision_step(self, scenario_id: int, step_number: int, decision_data: Dict[str, Any]) -> WizardStep:
        """Create a wizard step for an enhanced decision."""
        
        title = decision_data.get('title', f"Decision {step_number}")
        question = decision_data.get('question', '')
        context = decision_data.get('context', '')
        
        # Create narrative content
        narrative = self._create_decision_narrative(decision_data)
        
        # Generate decision options in wizard format
        options = self._generate_decision_options(decision_data)
        
        # Handle timeline_reference_id safely - convert to int if possible, otherwise use None
        reference_id = decision_data.get('id')
        if reference_id and isinstance(reference_id, str) and not reference_id.isdigit():
            reference_id = None  # Use NULL for non-numeric IDs
        elif reference_id:
            try:
                reference_id = int(reference_id)
            except (ValueError, TypeError):
                reference_id = None
        
        step = WizardStep(
            scenario_id=scenario_id,
            step_number=step_number,
            step_type='decision',
            title=title,
            narrative_content=narrative,
            timeline_reference_id=reference_id,
            timeline_reference_type='enhanced_decision',
            step_metadata={
                'question': question,
                'context': context,
                'options': options,
                'ontology_categories': decision_data.get('ontology_categories', []),
                'temporal_triggers': decision_data.get('temporal_triggers', []),
                'section_source': decision_data.get('section_source', 'question'),
                'original_decision_data': decision_data
            }
        )
        
        return step
    
    def _create_event_narrative(self, event_data: Dict[str, Any]) -> str:
        """Create narrative content for an event step."""
        
        title = event_data.get('title', 'An important event occurs')
        description = event_data.get('description', event_data.get('text', ''))
        participants = event_data.get('participants', [])
        
        narrative = f"{description}\n\n"
        
        if participants:
            narrative += f"Key participants involved: {', '.join(participants)}.\n\n"
        
        narrative += "This event sets the stage for the ethical considerations that follow."
        
        return narrative
    
    def _create_decision_narrative(self, decision_data: Dict[str, Any]) -> str:
        """Create narrative content for a decision step."""
        
        context = decision_data.get('context', '')
        question = decision_data.get('question', '')
        triggers = decision_data.get('temporal_triggers', [])
        
        narrative = ""
        
        if context:
            narrative += f"{context}\n\n"
        
        if triggers:
            narrative += f"This decision point arises from: {', '.join(triggers)}.\n\n"
        
        narrative += "As Engineer A, you must now make an important ethical decision that will impact the project and stakeholders."
        
        return narrative
    
    def _generate_decision_options(self, decision_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate decision options in wizard format."""
        
        # Start with basic options - Phase 2 will enhance these with NSPE references
        base_options = [
            {
                'id': 'option_1',
                'title': 'Prioritize Public Safety',
                'description': 'Focus on public welfare and safety considerations above other concerns.',
                'color': 'green',
                'nspe_status': 'nspe_positive',
                'ethical_analysis': 'This choice aligns with the fundamental engineering principle of protecting public safety and welfare.',
                'code_references': ['I.1 - Public Safety'],
                'precedent_cases': []
            },
            {
                'id': 'option_2', 
                'title': 'Seek Additional Guidance',
                'description': 'Consult with supervisor, ethics committee, or professional colleagues before proceeding.',
                'color': 'yellow',
                'nspe_status': 'neutral',
                'ethical_analysis': 'Seeking guidance demonstrates professional responsibility and ensures well-informed decision-making.',
                'code_references': ['II.1 - Professional Development'],
                'precedent_cases': []
            },
            {
                'id': 'option_3',
                'title': 'Follow Client Directives',
                'description': 'Proceed according to client instructions and contractual obligations.',
                'color': 'yellow',
                'nspe_status': 'neutral',
                'ethical_analysis': 'This option honors contractual commitments but must be weighed against other ethical obligations.',
                'code_references': ['III.1 - Client Relations'],
                'precedent_cases': []
            },
            {
                'id': 'option_4',
                'title': 'Document Concerns and Proceed Cautiously',
                'description': 'Document ethical concerns while finding a balanced approach to move forward.',
                'color': 'yellow',
                'nspe_status': 'neutral',
                'ethical_analysis': 'Documentation creates accountability while allowing for measured progress.',
                'code_references': ['II.5 - Documentation'],
                'precedent_cases': []
            }
        ]
        
        # Customize based on decision context
        question_text = decision_data.get('question', '').lower()
        
        if 'disclose' in question_text or 'ai' in question_text:
            # AI disclosure specific options
            base_options[0] = {
                'id': 'option_1',
                'title': 'Full Disclosure of AI Use',
                'description': 'Explicitly inform all stakeholders about AI assistance used in the analysis.',
                'color': 'green',
                'nspe_status': 'nspe_positive',
                'ethical_analysis': 'Full transparency maintains professional integrity and client trust.',
                'code_references': ['I.4 - Honesty'],
                'precedent_cases': []
            }
        
        elif 'report' in question_text and 'accuracy' in question_text:
            # Reporting accuracy specific options
            base_options[0] = {
                'id': 'option_1', 
                'title': 'Independent Verification',
                'description': 'Conduct independent verification of all critical findings before reporting.',
                'color': 'green',
                'nspe_status': 'nspe_positive',
                'ethical_analysis': 'Independent verification ensures accuracy and maintains professional standards.',
                'code_references': ['I.2 - Competent Practice'],
                'precedent_cases': []
            }
        
        return base_options[:3]  # Return 3 options for now
    
    def get_scenario_url(self, scenario_id: int) -> str:
        """Get the URL for accessing the created wizard scenario."""
        return f"/scenarios/{scenario_id}"