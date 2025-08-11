"""
Scenario Population Service

This service takes a deconstructed case and populates a scenario with comprehensive
database objects representing all 8 main ontology categories:
1. Roles (Characters)
2. Principles (stored in metadata)
3. Obligations (stored in metadata) 
4. States (Conditions)
5. Resources (Resources)
6. Actions (Actions)
7. Events (Events)
8. Capabilities (stored in character attributes)

Also generates a timeline with decision points for interactive play.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.models import db
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.resource import Resource
from app.models.event import Event, Action
from app.models.condition import Condition
from app.models.condition_type import ConditionType
from app.models.deconstructed_case import DeconstructedCase

logger = logging.getLogger(__name__)


class ScenarioPopulationService:
    """Service for populating scenarios with comprehensive data from deconstructed cases."""
    
    @classmethod
    def populate_scenario_from_deconstruction(cls, scenario: Scenario, deconstructed_case: DeconstructedCase) -> bool:
        """
        Populate a scenario with comprehensive data from a deconstructed case.
        
        Args:
            scenario: The scenario to populate
            deconstructed_case: The deconstructed case data source
            
        Returns:
            True if population succeeded, False otherwise
        """
        try:
            logger.info(f"Starting comprehensive population of scenario {scenario.id} from deconstructed case {deconstructed_case.id}")
            
            # Clear existing scenario components
            cls._clear_existing_components(scenario)
            
            # 1. ROLES - Create Characters from stakeholders
            characters = cls._create_characters(scenario, deconstructed_case.stakeholders)
            
            # 2. RESOURCES - Extract and create resources
            resources = cls._create_resources(scenario, deconstructed_case)
            
            # 3. STATES - Create conditions representing states
            conditions = cls._create_conditions(scenario, characters, deconstructed_case)
            
            # A single base_time ensures interleaved ordering between events and decisions
            base_time = datetime.utcnow()

            # 4. ACTIONS - Create actions from decision options and reasoning
            actions = cls._create_actions(scenario, deconstructed_case, base_time)
            
            # 5. EVENTS - Create events from timeline and outcomes
            events = cls._create_events(scenario, deconstructed_case, base_time)
            
            # 6. Update scenario metadata with principles, obligations, and capabilities
            cls._update_scenario_metadata(scenario, deconstructed_case, characters)
            
            # 7. Generate interactive timeline with decision points
            cls._create_decision_timeline(scenario, deconstructed_case)
            
            db.session.commit()
            
            logger.info(f"Successfully populated scenario {scenario.id} with: {len(characters)} characters, {len(resources)} resources, {len(conditions)} conditions, {len(actions)} actions, {len(events)} events")
            return True
            
        except Exception as e:
            logger.error(f"Failed to populate scenario {scenario.id}: {str(e)}", exc_info=True)
            db.session.rollback()
            return False
    
    @classmethod
    def _clear_existing_components(cls, scenario: Scenario):
        """Clear existing scenario components to avoid duplicates."""
        # Delete in reverse order of dependencies
        Event.query.filter_by(scenario_id=scenario.id).delete()
        Action.query.filter_by(scenario_id=scenario.id).delete()
        Condition.query.filter(Condition.character.has(scenario_id=scenario.id)).delete()
        Character.query.filter_by(scenario_id=scenario.id).delete()
        Resource.query.filter_by(scenario_id=scenario.id).delete()
        
    @classmethod
    def _create_characters(cls, scenario: Scenario, stakeholders: List[Dict[str, Any]]) -> List[Character]:
        """Create Character objects from stakeholder data."""
        characters = []
        
        for i, stakeholder in enumerate(stakeholders):
            character = Character(
                scenario_id=scenario.id,
                name=stakeholder.get('name', f'Stakeholder {i+1}'),
                role=stakeholder.get('role', 'stakeholder'),
                attributes={
                    'description': stakeholder.get('description', ''),
                    'interests': stakeholder.get('interests', []),
                    'power_level': stakeholder.get('power_level', 0.5),
                    'influence_level': stakeholder.get('influence_level', 0.5),
                    'ethical_stance': stakeholder.get('ethical_stance', 'neutral'),
                    'capabilities': cls._extract_capabilities_for_stakeholder(stakeholder),
                    'background': cls._clean_description(stakeholder.get('description', ''))
                }
            )
            
            db.session.add(character)
            characters.append(character)
            
        logger.info(f"Created {len(characters)} characters")
        return characters
    
    @classmethod
    def _create_resources(cls, scenario: Scenario, deconstructed_case: DeconstructedCase) -> List[Resource]:
        """Create Resource objects from reasoning chain and decision context."""
        resources = []
        reasoning = deconstructed_case.reasoning_chain or {}
        
        # Extract resources from initial conditions
        available_resources = reasoning.get('available_resources', [])
        for resource_name in available_resources:
            resource = Resource(
                scenario_id=scenario.id,
                name=resource_name,
                type='material',
                description='Resource identified from case analysis',
                quantity=1
            )
            db.session.add(resource)
            resources.append(resource)
        
        # Add standard engineering resources
        standard_resources = [
            {'name': 'NSPE Code of Ethics', 'type': 'regulatory', 'importance': 'critical'},
            {'name': 'Technical Specifications', 'type': 'technical', 'importance': 'high'},
            {'name': 'Environmental Standards', 'type': 'regulatory', 'importance': 'high'},
            {'name': 'Budget Constraints', 'type': 'financial', 'importance': 'medium'},
            {'name': 'Project Timeline', 'type': 'temporal', 'importance': 'medium'}
        ]
        
        for res_data in standard_resources:
            resource = Resource(
                scenario_id=scenario.id,
                name=res_data['name'],
                type=res_data['type'],
                description=f"Standard {res_data['type']} resource - {res_data['importance']} importance",
                quantity=1
            )
            db.session.add(resource)
            resources.append(resource)
        
        logger.info(f"Created {len(resources)} resources")
        return resources
    
    @classmethod
    def _create_conditions(cls, scenario: Scenario, characters: List[Character], deconstructed_case: DeconstructedCase) -> List[Condition]:
        """Create Condition objects representing states."""
        conditions = []
        
        # Create general condition types if they don't exist
        condition_types = cls._ensure_condition_types(scenario)
        
        # Extract states from reasoning chain
        reasoning = deconstructed_case.reasoning_chain or {}
        case_facts = reasoning.get('case_facts', [])
        
        # Analyze case facts to identify states
        state_conditions = [
            {'name': 'Public Safety Risk', 'severity': 8, 'type': 'safety_state'},
            {'name': 'Client Pressure', 'severity': 6, 'type': 'professional_state'},
            {'name': 'Ethical Dilemma', 'severity': 7, 'type': 'ethical_state'},
            {'name': 'Environmental Concern', 'severity': 8, 'type': 'environmental_state'},
            {'name': 'Professional Competence', 'severity': 5, 'type': 'capability_state'}
        ]
        
        # Create conditions and assign to characters
        for char_idx, character in enumerate(characters):
            # Assign relevant conditions based on character role
            relevant_conditions = cls._get_relevant_conditions_for_role(character.role, state_conditions)
            
            for cond_data in relevant_conditions:
                condition = Condition(
                    character_id=character.id,
                    name=cond_data['name'],
                    severity=cond_data['severity'],
                    description=f"State affecting {character.name} in the scenario - {cond_data['type']}"
                )
                db.session.add(condition)
                conditions.append(condition)
        
        logger.info(f"Created {len(conditions)} conditions (states)")
        return conditions
    
    @classmethod
    def _create_actions(cls, scenario: Scenario, deconstructed_case: DeconstructedCase, base_time: datetime) -> List[Action]:
        """Create Action objects from decision options and reasoning steps with interleaved timestamps."""
        actions: List[Action] = []

    # Base time provided by caller for consistent interleaving

        # Extract actions from decision points and assign interleaved timestamps
        decision_points = deconstructed_case.decision_points or []
        for i, decision in enumerate(decision_points):
            # Each decision group gets an odd timeline position (events occupy even positions)
            decision_time = base_time.replace()  # copy naive dt
            # Offset: 2 minutes per step, decisions at + (2*i + 1) minutes
            from datetime import timedelta
            decision_time = decision_time + timedelta(minutes=(2 * i + 1))

            for option in decision.get('primary_options', []):
                params = {
                    'decision_id': decision.get('decision_id'),
                    'decision_sequence': i + 1,
                    'option_id': option.get('option_id'),
                    'ethical_principles': option.get('alignment_with_principles', {}),
                    'predicted_outcomes': option.get('predicted_outcomes', []),
                    'risk_factors': option.get('risk_factors', []),
                    'complexity': decision.get('complexity_level', 0.5),
                    'urgency': decision.get('urgency_level', 0.5),
                    'timeline_sequence': 2 * i + 1,
                    'origin': 'llm',
                    'llm_generated': True
                }

                action = Action(
                    scenario_id=scenario.id,
                    name=option.get('title', 'Unknown Action'),
                    description=option.get('ethical_justification', ''),
                    action_type=decision.get('decision_type', 'general'),
                    is_decision=True,
                    action_time=decision_time,
                    parameters=params
                )
                db.session.add(action)
                actions.append(action)
        
        # Add standard professional actions
        standard_actions = [
            {'name': 'Consult NSPE Code', 'type': 'consultation', 'description': 'Review ethical guidelines'},
            {'name': 'Discuss with Supervisor', 'type': 'communication', 'description': 'Seek internal guidance'},
            {'name': 'Document Decision', 'type': 'documentation', 'description': 'Record reasoning and decision'},
            {'name': 'Monitor Outcomes', 'type': 'monitoring', 'description': 'Track results of decisions'}
        ]
        
        # Place standard actions after the main timeline so they don't interleave confusingly
        if decision_points:
            from datetime import timedelta
            tail_time = base_time + timedelta(minutes=(2 * len(decision_points) + 10))
        else:
            tail_time = base_time

        for idx, action_data in enumerate(standard_actions):
            # Stagger by 1 minute each after tail_time
            from datetime import timedelta
            at = tail_time + timedelta(minutes=idx)
            action = Action(
                scenario_id=scenario.id,
                name=action_data['name'],
                description=action_data['description'],
                action_type=action_data['type'],
                action_time=at,
                parameters={
                    'source': 'standard_professional',
                    'origin': 'system',
                    'availability': 'always'
                }
            )
            db.session.add(action)
            actions.append(action)
        
        logger.info(f"Created {len(actions)} actions")
        return actions
    
    @classmethod
    def _create_events(cls, scenario: Scenario, deconstructed_case: DeconstructedCase, base_time: datetime) -> List[Event]:
        """Create Event objects from timeline and reasoning chain with interleaved timestamps."""
        events: List[Event] = []
        reasoning = deconstructed_case.reasoning_chain or {}

    # Base time provided by caller for consistent interleaving

        # Create events from reasoning steps at even positions
        reasoning_steps = reasoning.get('reasoning_steps', [])
        from datetime import timedelta
        for i, step in enumerate(reasoning_steps):
            event_time = base_time + timedelta(minutes=(2 * i))
            event = Event(
                scenario_id=scenario.id,
                event_time=event_time,
                description=f"Reasoning Step {i+1}: {cls._clean_description(step.get('reasoning_logic', ''))}",
                parameters={
                    'name': f"Reasoning Step {i+1}",
                    'event_type': 'reasoning',
                    'step_order': step.get('step_order', i+1),
                    'reasoning_type': step.get('reasoning_type', 'analysis'),
                    'input_elements': step.get('input_elements', []),
                    'timeline_position': i / len(reasoning_steps) if reasoning_steps else 0,
                    'timeline_sequence': 2 * i,
                    'origin': 'llm',
                    'llm_generated': True
                }
            )
            db.session.add(event)
            events.append(event)

        # Add milestone events after the main interleaved sequence
        milestone_events = [
            {'name': 'Case Initiation', 'type': 'milestone', 'description': 'Engineering project begins'},
            {'name': 'Problem Identification', 'type': 'milestone', 'description': 'Ethical dilemma becomes apparent'},
            {'name': 'Outcome Evaluation', 'type': 'milestone', 'description': 'Results of decisions are assessed'}
        ]

        tail_offset = max(2 * len(reasoning_steps), 0)
        for j, event_data in enumerate(milestone_events):
            event_time = base_time + timedelta(minutes=(tail_offset + j))
            event = Event(
                scenario_id=scenario.id,
                event_time=event_time,
                description=event_data['description'],
                parameters={
                    'name': event_data['name'],
                    'event_type': event_data['type'],
                    'source': 'timeline_generation',
                    'importance': 'high',
                    'origin': 'system'
                }
            )
            db.session.add(event)
            events.append(event)
        
        logger.info(f"Created {len(events)} events")
        return events
    
    @classmethod
    def _update_scenario_metadata(cls, scenario: Scenario, deconstructed_case: DeconstructedCase, characters: List[Character]):
        """Update scenario metadata with principles, obligations, and capabilities."""
        reasoning = deconstructed_case.reasoning_chain or {}
        
        # Extract principles
        principles = reasoning.get('applicable_principles', [])
        
        # Extract obligations (implicit in ethical principles)
        obligations = [
            'Hold paramount the safety, health, and welfare of the public',
            'Act for each employer or client as faithful agents or trustees',
            'Issue public statements only in an objective and truthful manner',
            'Conduct themselves honorably, responsibly, ethically, and lawfully'
        ]
        
        # Aggregate capabilities from all characters
        all_capabilities = []
        for character in characters:
            if character.attributes and 'capabilities' in character.attributes:
                all_capabilities.extend(character.attributes['capabilities'])
        
        # Update scenario metadata
        if not scenario.scenario_metadata:
            scenario.scenario_metadata = {}
            
        scenario.scenario_metadata.update({
            'principles': principles,
            'obligations': obligations,
            'capabilities': list(set(all_capabilities)),  # Remove duplicates
            'decision_tree': cls._create_decision_tree(deconstructed_case),
            'learning_objectives': cls._generate_learning_objectives(deconstructed_case),
            'timeline': cls._create_interactive_timeline(deconstructed_case),
            'assessment_rubric': cls._create_assessment_rubric(deconstructed_case)
        })
    
    @classmethod
    def _create_decision_timeline(cls, scenario: Scenario, deconstructed_case: DeconstructedCase):
        """Create an interactive timeline with decision points."""
        timeline = []
        
        # Create timeline from decision points
        for i, decision in enumerate(deconstructed_case.decision_points or []):
            timeline_item = {
                'sequence': i + 1,
                'title': decision.get('title', f'Decision {i+1}'),
                'description': cls._clean_description(decision.get('description', '')),
                'decision_type': decision.get('decision_type', 'general'),
                'ethical_principles': decision.get('ethical_principles', []),
                'options': [
                    {
                        'id': opt.get('option_id', f'opt_{j}'),
                        'title': opt.get('title', f'Option {j+1}'),
                        'description': opt.get('ethical_justification', ''),
                        'consequences': opt.get('predicted_outcomes', []),
                        'ethical_score': cls._calculate_ethical_score(opt)
                    }
                    for j, opt in enumerate(decision.get('primary_options', []))
                ],
                'context_factors': decision.get('context_factors', []),
                'urgency': decision.get('urgency_level', 0.5),
                'complexity': decision.get('complexity_level', 0.5)
            }
            timeline.append(timeline_item)
        
        # Add to scenario metadata
        if not scenario.scenario_metadata:
            scenario.scenario_metadata = {}
        scenario.scenario_metadata['interactive_timeline'] = timeline
    
    # Helper methods
    @classmethod
    def _clean_description(cls, description: str) -> str:
        """Clean HTML and extract meaningful text from descriptions."""
        if not description:
            return ""
        
        # Simple HTML removal (for now)
        import re
        text = re.sub(r'<[^>]+>', '', description)
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Limit length
        if len(text) > 500:
            text = text[:497] + "..."
            
        return text
    
    @classmethod
    def _extract_capabilities_for_stakeholder(cls, stakeholder: Dict[str, Any]) -> List[str]:
        """Extract capabilities based on stakeholder role and context."""
        role = stakeholder.get('role', 'unknown')
        
        capabilities_map = {
            'professional': ['technical_expertise', 'ethical_reasoning', 'project_management'],
            'client': ['decision_making', 'resource_control', 'project_oversight'],
            'employer': ['organizational_authority', 'financial_control', 'strategic_planning'],
            'public': ['collective_action', 'regulatory_influence', 'public_pressure'],
            'regulator': ['enforcement_authority', 'regulatory_expertise', 'compliance_monitoring']
        }
        
        return capabilities_map.get(role, ['general_capabilities'])
    
    @classmethod
    def _get_relevant_conditions_for_role(cls, role: str, all_conditions: List[Dict]) -> List[Dict]:
        """Get conditions relevant to a specific character role."""
        role_condition_map = {
            'professional': ['Public Safety Risk', 'Ethical Dilemma', 'Professional Competence'],
            'client': ['Client Pressure', 'Public Safety Risk'],
            'employer': ['Professional Competence', 'Client Pressure'],
            'public': ['Public Safety Risk', 'Environmental Concern'],
            'regulator': ['Environmental Concern', 'Public Safety Risk']
        }
        
        relevant_names = role_condition_map.get(role, ['Ethical Dilemma'])
        return [cond for cond in all_conditions if cond['name'] in relevant_names]
    
    @classmethod
    def _ensure_condition_types(cls, scenario: Scenario) -> Dict[str, ConditionType]:
        """Ensure necessary condition types exist for the scenario's world."""
        types_needed = ['safety_state', 'professional_state', 'ethical_state', 'environmental_state', 'capability_state']
        condition_types = {}
        world_id = scenario.world_id
        
        for type_name in types_needed:
            cond_type = ConditionType.query.filter_by(name=type_name, world_id=world_id).first()
            if not cond_type:
                cond_type = ConditionType(
                    name=type_name, 
                    description=f"{type_name.replace('_', ' ').title()} condition",
                    world_id=world_id,
                    category='state'
                )
                db.session.add(cond_type)
            condition_types[type_name] = cond_type
            
        return condition_types
    
    @classmethod
    def _create_decision_tree(cls, deconstructed_case: DeconstructedCase) -> Dict[str, Any]:
        """Create a decision tree structure for interactive gameplay."""
        return {
            'root': 'start',
            'nodes': {
                'start': {
                    'type': 'situation',
                    'title': 'Case Introduction',
                    'description': 'Review the ethical dilemma',
                    'next': 'decision_1'
                }
            }
        }
    
    @classmethod
    def _generate_learning_objectives(cls, deconstructed_case: DeconstructedCase) -> List[str]:
        """Generate learning objectives based on the case content."""
        return [
            'Apply NSPE Code of Ethics to real-world scenarios',
            'Identify and analyze competing ethical principles',
            'Evaluate stakeholder interests and impacts',
            'Make reasoned ethical decisions under pressure',
            'Communicate ethical decisions professionally'
        ]
    
    @classmethod
    def _create_interactive_timeline(cls, deconstructed_case: DeconstructedCase) -> List[Dict[str, Any]]:
        """Create an interactive timeline for scenario progression."""
        return [
            {'phase': 'setup', 'title': 'Case Setup', 'duration': 5},
            {'phase': 'analysis', 'title': 'Stakeholder Analysis', 'duration': 10},
            {'phase': 'decisions', 'title': 'Decision Making', 'duration': 15},
            {'phase': 'outcomes', 'title': 'Outcome Evaluation', 'duration': 10}
        ]
    
    @classmethod
    def _create_assessment_rubric(cls, deconstructed_case: DeconstructedCase) -> Dict[str, Any]:
        """Create assessment rubric for the scenario."""
        return {
            'criteria': [
                {'name': 'Ethical Reasoning', 'weight': 0.3},
                {'name': 'Stakeholder Consideration', 'weight': 0.25},
                {'name': 'Code Application', 'weight': 0.25},
                {'name': 'Decision Quality', 'weight': 0.2}
            ]
        }
    
    @classmethod
    def _calculate_ethical_score(cls, option: Dict[str, Any]) -> float:
        """Calculate an ethical score for a decision option."""
        # Simple scoring based on available data
        base_score = 0.5
        
        if 'public' in option.get('ethical_justification', '').lower():
            base_score += 0.2
        if 'safety' in option.get('ethical_justification', '').lower():
            base_score += 0.2
        if 'professional' in option.get('ethical_justification', '').lower():
            base_score += 0.1
            
        return min(1.0, base_score)