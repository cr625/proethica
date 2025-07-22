"""
Wizard Controller service for managing interactive timeline scenarios.

Handles wizard step generation, progression, and user session management.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
from sqlalchemy import and_
from app.models import db
from app.models.scenario import Scenario
from app.models.event import Event, Action
from app.models.wizard import WizardStep, UserWizardSession


class WizardController:
    """Controls wizard-style progression through scenarios."""
    
    def __init__(self):
        self.step_templates = {
            'event': self._format_event_step,
            'decision': self._format_decision_step,
            'summary': self._format_summary_step
        }
    
    def generate_wizard_steps(self, scenario_id: int) -> List[WizardStep]:
        """Generate wizard steps from a scenario's timeline."""
        scenario = Scenario.query.get(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")
        
        # Get all timeline elements
        events = Event.query.filter_by(scenario_id=scenario_id).order_by(Event.event_time).all()
        decisions = Action.query.filter_by(scenario_id=scenario_id, is_decision=True).order_by(Action.action_time).all()
        
        # Combine and sort by time
        timeline_items = []
        for event in events:
            timeline_items.append(('event', event.event_time, event))
        for decision in decisions:
            timeline_items.append(('decision', decision.action_time, decision))
        
        timeline_items.sort(key=lambda x: x[1])
        
        # Generate wizard steps
        wizard_steps = []
        step_number = 1
        
        for item_type, _, item in timeline_items:
            step = self._create_wizard_step(scenario_id, step_number, item_type, item)
            wizard_steps.append(step)
            step_number += 1
        
        # Add summary step
        summary_step = self._create_summary_step(scenario_id, step_number)
        wizard_steps.append(summary_step)
        
        return wizard_steps
    
    def _create_wizard_step(self, scenario_id: int, step_number: int, item_type: str, item) -> WizardStep:
        """Create a wizard step from a timeline item."""
        step = WizardStep(
            scenario_id=scenario_id,
            step_number=step_number,
            step_type=item_type,
            timeline_reference_id=item.id,
            timeline_reference_type=item_type
        )
        
        if item_type == 'event':
            step.title = item.parameters.get('title', f'Event {step_number}')
            step.narrative_content = self._generate_event_narrative(item)
            step.step_metadata = {
                'event_type': item.parameters.get('event_type', 'generic'),
                'details': item.parameters.get('details', ''),
                'timeline_sequence': item.parameters.get('timeline_sequence', step_number)
            }
        
        elif item_type == 'decision':
            step.title = item.parameters.get('decision_title', f'Decision {step_number}')
            step.narrative_content = self._generate_decision_narrative(item)
            step.step_metadata = {
                'question': item.parameters.get('question_text', ''),
                'context': item.parameters.get('context', ''),
                'decision_sequence': item.parameters.get('decision_sequence', 1),
                'options_count': len(item.options or [])
            }
        
        return step
    
    def _create_summary_step(self, scenario_id: int, step_number: int) -> WizardStep:
        """Create the summary step."""
        return WizardStep(
            scenario_id=scenario_id,
            step_number=step_number,
            step_type='summary',
            title='Journey Complete',
            narrative_content='Your ethical journey through this scenario is complete. Review your choices and see how they compare with NSPE conclusions.',
            step_metadata={
                'show_choices': True,
                'show_analysis': True,
                'show_learning_points': True
            }
        )
    
    def _generate_event_narrative(self, event: Event) -> str:
        """Generate narrative content for an event step."""
        base_narrative = event.description
        
        # Add protagonist perspective
        if 'project_assignment' in event.parameters.get('event_type', ''):
            return f"You are Engineer A. {base_narrative}\n\nThis marks the beginning of your ethical journey."
        elif 'context_change' in event.parameters.get('event_type', ''):
            return f"A significant change occurs. {base_narrative}\n\nThis will impact your upcoming decisions."
        else:
            return f"{base_narrative}\n\nConsider how this affects your professional responsibilities."
    
    def _generate_decision_narrative(self, decision: Action) -> str:
        """Generate narrative content for a decision step."""
        context = decision.parameters.get('context', '')
        question = decision.parameters.get('question_text', '')
        
        return f"{context}\n\nNow you face a critical decision:\n\n{question}"
    
    def get_or_create_session(self, user_id: int, scenario_id: int) -> UserWizardSession:
        """Get existing session or create a new one."""
        # Look for active session
        session = UserWizardSession.query.filter(
            and_(
                UserWizardSession.user_id == user_id,
                UserWizardSession.scenario_id == scenario_id,
                UserWizardSession.session_status == 'active'
            )
        ).first()
        
        if not session:
            # Count total steps
            total_steps = WizardStep.query.filter_by(scenario_id=scenario_id).count()
            
            session = UserWizardSession(
                user_id=user_id,
                scenario_id=scenario_id,
                total_steps=total_steps
            )
            db.session.add(session)
            db.session.commit()
        else:
            # Update last accessed time
            session.last_accessed_at = datetime.utcnow()
            db.session.commit()
        
        return session
    
    def get_step_content(self, scenario_id: int, step_number: int) -> Dict:
        """Get formatted content for a specific step."""
        step = WizardStep.query.filter_by(
            scenario_id=scenario_id,
            step_number=step_number
        ).first()
        
        if not step:
            return None
        
        # Get the referenced timeline item if needed
        timeline_item = None
        if step.timeline_reference_id and step.timeline_reference_type:
            if step.timeline_reference_type == 'event':
                timeline_item = Event.query.get(step.timeline_reference_id)
            elif step.timeline_reference_type in ['action', 'decision']:
                timeline_item = Action.query.get(step.timeline_reference_id)
        
        # Format step content based on type
        formatter = self.step_templates.get(step.step_type)
        if formatter:
            return formatter(step, timeline_item)
        
        return step.to_dict()
    
    def _format_event_step(self, step: WizardStep, event: Event = None) -> Dict:
        """Format an event step for display."""
        content = {
            'step_number': step.step_number,
            'step_type': 'event',
            'title': step.title,
            'narrative': step.narrative_content,
            'metadata': step.step_metadata
        }
        
        if event:
            content['event_details'] = {
                'description': event.description,
                'parameters': event.parameters
            }
        
        return content
    
    def _format_decision_step(self, step: WizardStep, decision: Action = None) -> Dict:
        """Format a decision step with enhanced options."""
        content = {
            'step_number': step.step_number,
            'step_type': 'decision',
            'title': step.title,
            'narrative': step.narrative_content,
            'question': step.step_metadata.get('question', ''),
            'options': []
        }
        
        if decision and decision.options:
            for i, option in enumerate(decision.options):
                formatted_option = {
                    'id': option.get('id', f'option_{i+1}'),
                    'title': option.get('title', f'Option {i+1}'),
                    'description': option.get('description', ''),
                    'color': option.get('color', 'yellow'),
                    'nspe_status': option.get('nspe_status', 'alternative'),
                    'supporting_arguments': self._format_supporting_arguments(option),
                    'ethical_analysis': option.get('ethical_analysis', ''),
                    # Include original fields for template access
                    'code_references': option.get('code_references', []),
                    'precedent_cases': option.get('precedent_cases', []),
                    'reasoning_quote': option.get('reasoning_quote', '')
                }
                content['options'].append(formatted_option)
        
        return content
    
    def _format_supporting_arguments(self, option: Dict) -> List[Dict]:
        """Format supporting arguments for an option."""
        arguments = []
        
        # Code references
        for code_ref in option.get('code_references', []):
            arguments.append({
                'type': 'code_reference',
                'content': code_ref,
                'supporting': not option.get('nspe_status', '').endswith('negative')
            })
        
        # Precedent cases
        for case in option.get('precedent_cases', []):
            arguments.append({
                'type': 'precedent_case',
                'content': case,
                'supporting': True
            })
        
        # Reasoning quote
        if option.get('reasoning_quote'):
            arguments.append({
                'type': 'reasoning',
                'content': option['reasoning_quote'],
                'supporting': True
            })
        
        return arguments
    
    def _format_summary_step(self, step: WizardStep, _: any = None) -> Dict:
        """Format the summary step."""
        return {
            'step_number': step.step_number,
            'step_type': 'summary',
            'title': step.title,
            'narrative': step.narrative_content,
            'show_choices': step.step_metadata.get('show_choices', True),
            'show_analysis': step.step_metadata.get('show_analysis', True),
            'show_learning_points': step.step_metadata.get('show_learning_points', True)
        }
    
    def record_choice(self, session: UserWizardSession, step_number: int, option_id: str) -> bool:
        """Record a user's choice for a decision step."""
        # Verify this is a decision step
        step = WizardStep.query.filter_by(
            scenario_id=session.scenario_id,
            step_number=step_number,
            step_type='decision'
        ).first()
        
        if not step:
            return False
        
        session.record_choice(step_number, option_id)
        db.session.commit()
        return True
    
    def advance_session(self, session: UserWizardSession) -> bool:
        """Advance to the next step."""
        if session.current_step < session.total_steps:
            session.advance_step()
            db.session.commit()
            return True
        return False
    
    def go_back(self, session: UserWizardSession) -> bool:
        """Go back to the previous step."""
        if session.current_step > 1:
            session.go_back()
            db.session.commit()
            return True
        return False
    
    def generate_summary(self, session: UserWizardSession) -> Dict:
        """Generate a summary of the user's choices and analysis."""
        # Get all decision steps
        decision_steps = WizardStep.query.filter_by(
            scenario_id=session.scenario_id,
            step_type='decision'
        ).order_by(WizardStep.step_number).all()
        
        summary = {
            'total_decisions': len(decision_steps),
            'choices': [],
            'alignment_score': 0,
            'learning_points': []
        }
        
        nspe_matches = 0
        
        for step in decision_steps:
            step_number = str(step.step_number)
            if step_number in session.choices:
                choice_id = session.choices[step_number]
                
                # Get the actual decision to check NSPE alignment
                decision = Action.query.get(step.timeline_reference_id)
                if decision and decision.options:
                    chosen_option = next((opt for opt in decision.options if opt.get('id') == choice_id), None)
                    
                    if chosen_option:
                        is_nspe = chosen_option.get('nspe_status') in ['nspe_positive', 'nspe_negative', 'nspe_conclusion']
                        if is_nspe:
                            nspe_matches += 1
                        
                        summary['choices'].append({
                            'decision_title': step.title,
                            'question': step.step_metadata.get('question', ''),
                            'chosen_option': chosen_option.get('title', ''),
                            'is_nspe_aligned': is_nspe,
                            'nspe_status': chosen_option.get('nspe_status', '')
                        })
        
        # Calculate alignment score
        if summary['total_decisions'] > 0:
            summary['alignment_score'] = round(nspe_matches / summary['total_decisions'] * 100, 1)
        
        # Add learning points based on choices
        summary['learning_points'] = self._generate_learning_points(session, summary)
        
        return summary
    
    def _generate_learning_points(self, session: UserWizardSession, summary: Dict) -> List[str]:
        """Generate educational learning points based on user choices."""
        points = []
        
        # Based on alignment score
        if summary['alignment_score'] >= 80:
            points.append("Excellent alignment with NSPE professional standards")
        elif summary['alignment_score'] >= 60:
            points.append("Good understanding of ethical principles with room for refinement")
        else:
            points.append("Consider reviewing NSPE Code of Ethics for additional guidance")
        
        # Specific insights based on Case 7 (AI Ethics)
        points.extend([
            "AI tools require the same ethical considerations as other engineering tools",
            "Client data confidentiality extends to all external systems including AI",
            "Responsible Charge means maintaining detailed oversight, not just review",
            "Transparency builds trust even when disclosure isn't legally required"
        ])
        
        return points