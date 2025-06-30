"""
Service for generating interactive scenarios from deconstructed cases.

This service transforms deconstructed case data into rich, playable scenarios
with characters, events, decision trees, and assessment frameworks.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import uuid

from app.models.deconstructed_case import DeconstructedCase
from app.models.scenario_template import ScenarioTemplate
from app.models.scenario import Scenario
from app.models.world import World
from app import db

logger = logging.getLogger(__name__)


class ScenarioGenerationService:
    """
    Generates interactive scenarios from deconstructed cases.
    
    Creates rich scenario structures with:
    - Characters based on stakeholders
    - Decision trees from ethical decision points
    - Events and timeline from case narrative
    - Assessment criteria and learning objectives
    """

    def __init__(self):
        self.character_templates = self._load_character_templates()
        self.event_templates = self._load_event_templates()

    def generate_scenario_template(self, deconstructed_case: DeconstructedCase) -> Optional[ScenarioTemplate]:
        """
        Generate a scenario template from a deconstructed case.
        
        Args:
            deconstructed_case: The deconstructed case to convert
            
        Returns:
            ScenarioTemplate instance or None if failed
        """
        try:
            case = deconstructed_case.case
            if not case:
                logger.error(f"Cannot find case for deconstructed case {deconstructed_case.id}")
                return None

            # Generate comprehensive scenario data
            scenario_data = self._generate_comprehensive_scenario_data(deconstructed_case)
            
            # Create the template
            template = ScenarioTemplate(
                deconstructed_case_id=deconstructed_case.id,
                title=self._generate_scenario_title(case),
                description=self._generate_scenario_description(case, deconstructed_case),
                world_id=case.world_id,
                template_data=scenario_data,
                created_at=datetime.utcnow()
            )
            
            db.session.add(template)
            db.session.commit()
            
            logger.info(f"Generated scenario template {template.id} from deconstructed case {deconstructed_case.id}")
            return template
            
        except Exception as e:
            logger.error(f"Failed to generate scenario template: {str(e)}")
            db.session.rollback()
            return None

    def create_scenario_instance(self, template: ScenarioTemplate, user_id: int, 
                               customizations: Optional[Dict[str, Any]] = None) -> Optional[Scenario]:
        """
        Create a playable scenario instance from a template.
        
        Args:
            template: The scenario template to instantiate
            user_id: ID of the user creating the scenario
            customizations: Optional customizations to apply
            
        Returns:
            Scenario instance or None if failed
        """
        try:
            # Apply customizations to template data
            scenario_metadata = self._apply_customizations(template.template_data, customizations or {})
            
            # Initialize scenario state
            scenario_metadata.update({
                "instance_id": str(uuid.uuid4()),
                "created_for_user": user_id,
                "current_state": "initialized",
                "current_phase": "introduction",
                "current_decision_point": 0,
                "user_decisions": [],
                "session_data": {
                    "start_time": datetime.utcnow().isoformat(),
                    "time_limit": None,
                    "attempts": 0,
                    "hints_used": 0
                },
                "progress_tracking": {
                    "decisions_made": 0,
                    "stakeholders_considered": [],
                    "principles_applied": [],
                    "reasoning_quality_scores": []
                }
            })
            
            scenario = Scenario(
                title=template.title,
                description=template.description,
                world_id=template.world_id,
                created_by=user_id,
                scenario_metadata=scenario_metadata,
                created_at=datetime.utcnow()
            )
            
            db.session.add(scenario)
            db.session.commit()
            
            logger.info(f"Created scenario instance {scenario.id} from template {template.id}")
            return scenario
            
        except Exception as e:
            logger.error(f"Failed to create scenario instance: {str(e)}")
            db.session.rollback()
            return None

    def _generate_comprehensive_scenario_data(self, deconstructed_case: DeconstructedCase) -> Dict[str, Any]:
        """
        Generate comprehensive scenario data structure.
        
        Args:
            deconstructed_case: The deconstructed case
            
        Returns:
            Complete scenario data structure
        """
        return {
            "metadata": self._generate_scenario_metadata(deconstructed_case),
            "characters": self._generate_characters(deconstructed_case.stakeholders),
            "timeline": self._generate_timeline(deconstructed_case),
            "decision_tree": self._generate_decision_tree(deconstructed_case.decision_points),
            "resources": self._generate_resources(deconstructed_case),
            "environment": self._generate_environment(deconstructed_case),
            "learning_framework": self._generate_learning_framework(deconstructed_case),
            "assessment": self._generate_assessment_framework(deconstructed_case),
            "simulation_parameters": self._generate_simulation_parameters(deconstructed_case)
        }

    def _generate_scenario_title(self, case) -> str:
        """Generate an engaging scenario title."""
        base_title = case.title or "Ethical Decision Scenario"
        
        # Make it more engaging for scenarios
        if "Case" in base_title:
            base_title = base_title.replace("Case", "Scenario")
        elif not any(word in base_title.lower() for word in ["scenario", "simulation", "challenge"]):
            base_title = f"The {base_title} Challenge"
            
        return base_title

    def _generate_scenario_description(self, case, deconstructed_case: DeconstructedCase) -> str:
        """Generate scenario description."""
        base_desc = case.description or "An interactive ethical decision-making scenario"
        
        stakeholder_count = len(deconstructed_case.stakeholders or [])
        decision_count = len(deconstructed_case.decision_points or [])
        
        enhanced_desc = f"{base_desc}\n\n"
        enhanced_desc += f"In this interactive scenario, you will navigate {decision_count} key ethical decision points "
        enhanced_desc += f"while considering the perspectives of {stakeholder_count} stakeholders. "
        enhanced_desc += "Your choices will shape the outcome and demonstrate your ethical reasoning skills."
        
        return enhanced_desc

    def _generate_scenario_metadata(self, deconstructed_case: DeconstructedCase) -> Dict[str, Any]:
        """Generate scenario metadata."""
        return {
            "source_case_id": deconstructed_case.case_id,
            "deconstructed_case_id": deconstructed_case.id,
            "adapter_type": deconstructed_case.adapter_type,
            "confidence_scores": deconstructed_case.confidence_scores,
            "human_validated": deconstructed_case.human_validated,
            "complexity_level": self._assess_complexity(deconstructed_case),
            "estimated_duration": self._estimate_duration(deconstructed_case),
            "difficulty_rating": self._assess_difficulty(deconstructed_case),
            "ethical_frameworks": self._extract_ethical_frameworks(deconstructed_case),
            "professional_standards": self._extract_professional_standards(deconstructed_case)
        }

    def _generate_characters(self, stakeholders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate rich character profiles from stakeholders."""
        characters = []
        
        for i, stakeholder in enumerate(stakeholders or []):
            character = {
                "id": f"char_{i+1}",
                "name": stakeholder.get("name", f"Stakeholder {i+1}"),
                "role": stakeholder.get("role", "Unknown Role"),
                "description": stakeholder.get("description", ""),
                "avatar": self._assign_avatar(stakeholder.get("role", "")),
                
                # Interests and motivations
                "primary_interests": stakeholder.get("interests", []),
                "motivations": stakeholder.get("motivations", []),
                "concerns": stakeholder.get("concerns", []),
                
                # Power and influence
                "power_level": stakeholder.get("power_level", "medium"),
                "influence_type": stakeholder.get("influence_type", "direct"),
                "decision_authority": stakeholder.get("decision_authority", False),
                
                # Ethical stance and personality
                "ethical_stance": stakeholder.get("ethical_stance", "neutral"),
                "personality_traits": self._generate_personality_traits(stakeholder),
                "communication_style": self._determine_communication_style(stakeholder),
                
                # Scenario-specific data
                "initial_attitude": "neutral",
                "relationship_map": {},
                "dialogue_options": self._generate_dialogue_options(stakeholder),
                "reaction_patterns": self._generate_reaction_patterns(stakeholder)
            }
            
            characters.append(character)
        
        # Generate relationship map between characters
        self._generate_character_relationships(characters)
        
        return characters

    def _generate_timeline(self, deconstructed_case: DeconstructedCase) -> Dict[str, Any]:
        """Generate scenario timeline and events."""
        reasoning = deconstructed_case.reasoning_chain or {}
        decision_points = deconstructed_case.decision_points or []
        
        timeline = {
            "phases": [],
            "events": [],
            "milestones": [],
            "time_constraints": {}
        }
        
        # Phase 1: Setup and Introduction
        timeline["phases"].append({
            "id": "introduction",
            "name": "Scenario Introduction",
            "description": "Meet the stakeholders and understand the situation",
            "duration_minutes": 5,
            "objectives": ["Understand the context", "Identify stakeholders", "Recognize ethical dimensions"]
        })
        
        # Phase 2-N: Decision phases
        for i, decision in enumerate(decision_points):
            phase_id = f"decision_{i+1}"
            timeline["phases"].append({
                "id": phase_id,
                "name": decision.get("title", f"Decision Point {i+1}"),
                "description": decision.get("description", "Make an ethical decision"),
                "duration_minutes": 10,
                "objectives": [
                    "Analyze stakeholder impacts",
                    "Apply ethical principles",
                    "Make and justify decision"
                ],
                "decision_point": decision
            })
        
        # Final phase: Reflection and Assessment
        timeline["phases"].append({
            "id": "reflection",
            "name": "Reflection and Assessment",
            "description": "Review decisions and reflect on outcomes",
            "duration_minutes": 10,
            "objectives": ["Reflect on decisions", "Understand consequences", "Identify learning"]
        })
        
        # Generate events within phases
        timeline["events"] = self._generate_timeline_events(deconstructed_case, timeline["phases"])
        
        return timeline

    def _generate_decision_tree(self, decision_points: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate decision tree structure."""
        tree = {
            "root": "start",
            "nodes": {},
            "edges": [],
            "outcomes": {}
        }
        
        # Start node
        tree["nodes"]["start"] = {
            "type": "start",
            "title": "Scenario Beginning",
            "description": "You are about to begin an ethical decision-making scenario"
        }
        
        # Decision nodes
        for i, decision in enumerate(decision_points or []):
            node_id = f"decision_{i+1}"
            
            tree["nodes"][node_id] = {
                "type": "decision",
                "title": decision.get("title", f"Decision {i+1}"),
                "description": decision.get("description", ""),
                "ethical_principles": decision.get("ethical_principles", []),
                "stakeholder_impacts": decision.get("stakeholder_impacts", {}),
                "options": self._generate_decision_options(decision),
                "time_limit": decision.get("time_limit"),
                "hints": self._generate_decision_hints(decision)
            }
            
            # Create options and outcomes
            for j, option in enumerate(tree["nodes"][node_id]["options"]):
                outcome_id = f"{node_id}_outcome_{j+1}"
                tree["outcomes"][outcome_id] = {
                    "decision_id": node_id,
                    "option_id": option["id"],
                    "immediate_consequences": option.get("consequences", []),
                    "stakeholder_reactions": option.get("stakeholder_reactions", {}),
                    "ethical_score": option.get("ethical_score", 0.5),
                    "reasoning_feedback": option.get("feedback", "")
                }
        
        # Connect nodes
        prev_node = "start"
        for i in range(len(decision_points or [])):
            current_node = f"decision_{i+1}"
            tree["edges"].append({
                "from": prev_node,
                "to": current_node,
                "condition": "next"
            })
            prev_node = current_node
        
        return tree

    def _generate_resources(self, deconstructed_case: DeconstructedCase) -> Dict[str, Any]:
        """Generate scenario resources."""
        reasoning = deconstructed_case.reasoning_chain or {}
        
        return {
            "documents": self._extract_reference_documents(reasoning),
            "tools": self._generate_analysis_tools(),
            "references": self._extract_ethical_references(deconstructed_case),
            "constraints": reasoning.get("constraints", []),
            "available_data": reasoning.get("available_data", []),
            "expert_contacts": self._generate_expert_contacts(deconstructed_case)
        }

    def _generate_environment(self, deconstructed_case: DeconstructedCase) -> Dict[str, Any]:
        """Generate scenario environment settings."""
        case = deconstructed_case.case
        
        return {
            "setting": {
                "organization_type": self._infer_organization_type(case),
                "industry_context": self._infer_industry_context(case),
                "regulatory_environment": self._extract_regulations(deconstructed_case),
                "cultural_context": "professional",
                "time_period": "current",
                "location": "workplace"
            },
            "atmosphere": {
                "pressure_level": self._assess_pressure_level(deconstructed_case),
                "visibility": self._assess_decision_visibility(deconstructed_case),
                "stakeholder_tension": self._assess_stakeholder_tension(deconstructed_case)
            },
            "constraints": {
                "time_constraints": True,
                "resource_constraints": True,
                "information_constraints": True,
                "authority_constraints": True
            }
        }

    def _generate_learning_framework(self, deconstructed_case: DeconstructedCase) -> Dict[str, Any]:
        """Generate learning objectives and framework."""
        return {
            "primary_objectives": [
                "Apply ethical decision-making frameworks",
                "Consider multiple stakeholder perspectives",
                "Integrate professional codes of ethics",
                "Justify decisions with sound reasoning"
            ],
            "secondary_objectives": [
                "Identify ethical dimensions in professional situations",
                "Manage competing interests and values",
                "Communicate ethical decisions effectively",
                "Reflect on decision-making processes"
            ],
            "competencies": self._extract_competencies(deconstructed_case),
            "ethical_frameworks": self._extract_ethical_frameworks(deconstructed_case),
            "reflection_prompts": self._generate_reflection_prompts(deconstructed_case),
            "discussion_questions": self._generate_discussion_questions(deconstructed_case)
        }

    def _generate_assessment_framework(self, deconstructed_case: DeconstructedCase) -> Dict[str, Any]:
        """Generate comprehensive assessment framework."""
        return {
            "formative_assessments": [
                {
                    "type": "decision_quality",
                    "weight": 0.30,
                    "criteria": "Quality of ethical decisions made",
                    "rubric": self._generate_decision_quality_rubric()
                },
                {
                    "type": "stakeholder_analysis",
                    "weight": 0.25,
                    "criteria": "Thoroughness of stakeholder consideration",
                    "rubric": self._generate_stakeholder_analysis_rubric()
                },
                {
                    "type": "ethical_reasoning",
                    "weight": 0.25,
                    "criteria": "Application of ethical principles",
                    "rubric": self._generate_ethical_reasoning_rubric()
                },
                {
                    "type": "communication",
                    "weight": 0.20,
                    "criteria": "Clarity and professionalism of communication",
                    "rubric": self._generate_communication_rubric()
                }
            ],
            "summative_assessment": {
                "type": "comprehensive_reflection",
                "description": "Final reflection on decision-making process and outcomes",
                "prompts": self._generate_summative_prompts(deconstructed_case)
            },
            "feedback_mechanisms": [
                "Immediate decision feedback",
                "Stakeholder reaction displays",
                "Progress tracking visualization",
                "Peer comparison (if applicable)"
            ]
        }

    def _generate_simulation_parameters(self, deconstructed_case: DeconstructedCase) -> Dict[str, Any]:
        """Generate parameters for scenario simulation."""
        return {
            "difficulty_settings": {
                "beginner": {
                    "hints_available": True,
                    "time_limits_relaxed": True,
                    "simplified_options": True
                },
                "intermediate": {
                    "hints_available": True,
                    "time_limits_normal": True,
                    "full_complexity": True
                },
                "advanced": {
                    "hints_limited": True,
                    "time_limits_strict": True,
                    "additional_complications": True
                }
            },
            "randomization": {
                "stakeholder_attitudes": True,
                "event_timing": False,
                "resource_availability": True
            },
            "adaptation": {
                "difficulty_scaling": True,
                "personalized_feedback": True,
                "learning_path_adjustment": True
            }
        }

    # Helper methods for data generation
    def _assess_complexity(self, deconstructed_case: DeconstructedCase) -> str:
        """Assess scenario complexity level."""
        stakeholder_count = len(deconstructed_case.stakeholders or [])
        decision_count = len(deconstructed_case.decision_points or [])
        
        if stakeholder_count <= 3 and decision_count <= 2:
            return "low"
        elif stakeholder_count <= 6 and decision_count <= 4:
            return "medium"
        else:
            return "high"

    def _estimate_duration(self, deconstructed_case: DeconstructedCase) -> int:
        """Estimate scenario duration in minutes."""
        base_time = 15  # Introduction and reflection
        decision_time = len(deconstructed_case.decision_points or []) * 10
        return base_time + decision_time

    def _assess_difficulty(self, deconstructed_case: DeconstructedCase) -> str:
        """Assess scenario difficulty."""
        # Based on confidence scores and complexity
        avg_confidence = sum(deconstructed_case.confidence_scores.values()) / len(deconstructed_case.confidence_scores) if deconstructed_case.confidence_scores else 0.5
        complexity = self._assess_complexity(deconstructed_case)
        
        if avg_confidence > 0.8 and complexity == "low":
            return "beginner"
        elif avg_confidence > 0.6 and complexity in ["low", "medium"]:
            return "intermediate"
        else:
            return "advanced"

    def _load_character_templates(self) -> Dict[str, Any]:
        """Load character templates for different roles."""
        return {
            "engineer": {"avatar": "engineer", "traits": ["analytical", "detail-oriented"]},
            "manager": {"avatar": "manager", "traits": ["decisive", "strategic"]},
            "client": {"avatar": "client", "traits": ["demanding", "results-focused"]},
            "colleague": {"avatar": "colleague", "traits": ["collaborative", "supportive"]},
            "public": {"avatar": "public", "traits": ["concerned", "vocal"]},
            "regulator": {"avatar": "regulator", "traits": ["thorough", "compliance-focused"]}
        }

    def _load_event_templates(self) -> Dict[str, Any]:
        """Load event templates for scenarios."""
        return {
            "stakeholder_meeting": {
                "duration": 5,
                "interaction_type": "discussion",
                "outcomes": ["information_gathered", "relationship_changed"]
            },
            "decision_deadline": {
                "duration": 1,
                "interaction_type": "pressure",
                "outcomes": ["time_pressure_increased"]
            },
            "new_information": {
                "duration": 3,
                "interaction_type": "information",
                "outcomes": ["facts_updated", "options_changed"]
            }
        }

    def _assign_avatar(self, role: str) -> str:
        """Assign avatar based on role."""
        role_lower = role.lower()
        if "engineer" in role_lower:
            return "engineer"
        elif "manager" in role_lower or "supervisor" in role_lower:
            return "manager"
        elif "client" in role_lower or "customer" in role_lower:
            return "client"
        elif "public" in role_lower or "citizen" in role_lower:
            return "public"
        elif "regulator" in role_lower or "official" in role_lower:
            return "regulator"
        else:
            return "colleague"

    def _apply_customizations(self, template_data: Dict[str, Any], 
                            customizations: Dict[str, Any]) -> Dict[str, Any]:
        """Apply user customizations to template data."""
        customized_data = template_data.copy()
        
        # Apply difficulty settings
        if "difficulty" in customizations:
            difficulty = customizations["difficulty"]
            sim_params = customized_data.get("simulation_parameters", {})
            customized_data["active_difficulty"] = sim_params.get("difficulty_settings", {}).get(difficulty, {})
        
        # Apply time limits
        if "time_limits" in customizations:
            for phase in customized_data.get("timeline", {}).get("phases", []):
                if customizations["time_limits"] == "strict":
                    phase["duration_minutes"] = max(5, phase.get("duration_minutes", 10) - 2)
                elif customizations["time_limits"] == "relaxed":
                    phase["duration_minutes"] = phase.get("duration_minutes", 10) + 5
        
        return customized_data

    # Additional helper methods would continue here...
    # (Truncated for brevity, but would include all the referenced helper methods)

    def _generate_personality_traits(self, stakeholder: Dict[str, Any]) -> List[str]:
        """Generate personality traits for character."""
        role = stakeholder.get("role", "").lower()
        base_traits = []
        
        if "manager" in role:
            base_traits = ["decisive", "strategic", "results-oriented"]
        elif "engineer" in role:
            base_traits = ["analytical", "detail-oriented", "technical"]
        elif "client" in role:
            base_traits = ["demanding", "cost-conscious", "impatient"]
        else:
            base_traits = ["professional", "concerned", "reasonable"]
            
        return base_traits

    def _determine_communication_style(self, stakeholder: Dict[str, Any]) -> str:
        """Determine communication style for character."""
        power_level = stakeholder.get("power_level", "medium")
        role = stakeholder.get("role", "").lower()
        
        if power_level == "high":
            return "authoritative"
        elif "technical" in role or "engineer" in role:
            return "analytical"
        elif "client" in role:
            return "direct"
        else:
            return "collaborative"

    def _generate_dialogue_options(self, stakeholder: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate dialogue options for character interactions."""
        return [
            {"type": "question", "text": "What are your main concerns about this situation?"},
            {"type": "explanation", "text": "Let me explain the technical aspects..."},
            {"type": "negotiation", "text": "Perhaps we can find a compromise..."}
        ]

    def _generate_reaction_patterns(self, stakeholder: Dict[str, Any]) -> Dict[str, Any]:
        """Generate reaction patterns for character."""
        return {
            "positive_decision": {"mood": "satisfied", "cooperation": "increased"},
            "negative_decision": {"mood": "concerned", "cooperation": "decreased"},
            "ignored": {"mood": "frustrated", "cooperation": "reduced"}
        }

    def _generate_character_relationships(self, characters: List[Dict[str, Any]]):
        """Generate relationships between characters."""
        for i, char1 in enumerate(characters):
            char1["relationship_map"] = {}
            for j, char2 in enumerate(characters):
                if i != j:
                    relationship = self._determine_relationship(char1, char2)
                    char1["relationship_map"][char2["id"]] = relationship

    def _determine_relationship(self, char1: Dict[str, Any], char2: Dict[str, Any]) -> str:
        """Determine relationship between two characters."""
        role1 = char1.get("role", "").lower()
        role2 = char2.get("role", "").lower()
        
        if "manager" in role1 and "engineer" in role2:
            return "supervisor"
        elif "engineer" in role1 and "manager" in role2:
            return "subordinate"
        elif "client" in role1:
            return "customer"
        elif "client" in role2:
            return "service_provider"
        else:
            return "colleague"
            
    # Additional helper methods would be implemented here following the same pattern...