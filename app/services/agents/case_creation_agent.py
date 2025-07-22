"""
Agent-Assisted Case Creation Service

This service extends the BaseAgent framework to provide intelligent, ontology-guided
case creation capabilities. It integrates with the existing 8-category ontology system
to help users develop comprehensive engineering ethics cases.
"""

from typing import Dict, List, Any, Optional
import logging
from .base_agent import BaseAgent
from app.services.ontology_entity_service import OntologyEntityService
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

class CaseCreationAgent(BaseAgent):
    """
    Specialized agent for ontology-guided case creation.
    
    This agent helps users create engineering ethics cases by:
    - Integrating selected ontological categories into prompts
    - Providing contextual guidance based on ethical concepts
    - Suggesting relevant principles, obligations, and other concepts
    - Structuring case development around ontological frameworks
    """
    
    def __init__(self, world_id: Optional[int] = None):
        """Initialize the Case Creation Agent."""
        super().__init__("CaseCreationAgent", world_id)
        self.ontology_service = OntologyEntityService.get_instance()
        self.llm_service = LLMService()
        self.selected_categories = []
        self.selected_concepts = {}
        
    def set_selected_categories(self, categories: List[str]):
        """
        Set the ontological categories selected by the user.
        This is now derived from selected concepts.
        
        Args:
            categories: List of category names (e.g., ['Principle', 'Obligation'])
        """
        self.selected_categories = categories
        logger.info(f"Case Creation Agent: Categories with selected concepts: {categories}")
        
    def set_selected_concepts(self, concepts: Dict[str, List[str]]):
        """
        Set specific concepts selected from each category.
        
        Args:
            concepts: Dict mapping category names to lists of concept names
                     e.g., {'Principle': ['PublicSafetyPrinciple'], 'Obligation': ['PublicWelfareObligation']}
        """
        self.selected_concepts = concepts
        logger.info(f"Case Creation Agent: Selected concepts {concepts}")
    
    def analyze(self, scenario_data: Dict[str, Any], decision_text: str, 
               options: List[str], previous_results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze case creation request with ontological context.
        
        Args:
            scenario_data: Contains world info and any existing case data
            decision_text: User's case creation prompt or request
            options: Available case creation options or next steps
            previous_results: Results from other agents (if any)
            
        Returns:
            Dict containing case creation guidance and suggestions
        """
        try:
            # Get world context if available
            world = None
            if self.world_id:
                from app.models.world import World
                world = World.query.get(self.world_id)
            
            # Build ontological context
            ontology_context = self._build_ontology_context(world)
            
            # Create contextual prompt
            prompt = self._create_contextual_prompt(decision_text, ontology_context)
            
            # Get LLM guidance
            guidance = self._get_llm_guidance(prompt)
            
            # Structure the response
            result = {
                "agent_name": self.name,
                "guidance": guidance,
                "selected_categories": self.selected_categories,
                "ontology_context": ontology_context,
                "suggestions": self._generate_suggestions(ontology_context),
                "next_steps": self._suggest_next_steps(decision_text, ontology_context)
            }
            
            logger.info(f"Case Creation Agent analysis completed for prompt: {decision_text[:100]}...")
            return result
            
        except Exception as e:
            logger.error(f"Error in Case Creation Agent analysis: {e}")
            return {
                "agent_name": self.name,
                "error": str(e),
                "guidance": "I encountered an issue while analyzing your case creation request. Please try again.",
                "selected_categories": self.selected_categories
            }
    
    def _build_ontology_context(self, world) -> Dict[str, Any]:
        """Build context from selected ontological categories and concepts."""
        context = {
            "categories": self.selected_categories,
            "concepts": self.selected_concepts,
            "available_entities": {}
        }
        
        if world:
            # Get entities for the selected categories
            entities = self.ontology_service.get_entities_for_world(world)
            
            for category in self.selected_categories:
                if category in entities.get("entities", {}):
                    context["available_entities"][category] = entities["entities"][category]
        
        return context
    
    def _create_contextual_prompt(self, user_prompt: str, ontology_context: Dict[str, Any]) -> str:
        """Create an enhanced prompt with ontological context."""
        
        base_prompt = f"""You are an expert in engineering ethics case development. 
The user wants to create an engineering ethics case with the following request:

USER REQUEST: {user_prompt}

ONTOLOGICAL FRAMEWORK:
The user has selected these ontological categories: {', '.join(self.selected_categories) if self.selected_categories else 'None selected'}
"""
        
        # Add specific concepts if selected
        if self.selected_concepts:
            base_prompt += "\n🎯 SELECTED SPECIFIC CONCEPTS:\n"
            total_concepts = 0
            for category, concepts in self.selected_concepts.items():
                if concepts:  # Only show categories with selected concepts
                    base_prompt += f"• {category}: {', '.join(concepts)}\n"
                    total_concepts += len(concepts)
            
            if total_concepts > 0:
                base_prompt += f"\nYou should focus particularly on incorporating these {total_concepts} selected concepts into the case development.\n"
        
        # Add context about how to use the concepts
        if self.selected_concepts:
            base_prompt += "\nINTEGRATION GUIDANCE:\n"
            for category, concepts in self.selected_concepts.items():
                if concepts:
                    if category == "Principle":
                        base_prompt += f"- Principles ({', '.join(concepts)}): Create ethical tensions or conflicts where these principles must be balanced\n"
                    elif category == "Obligation":
                        base_prompt += f"- Obligations ({', '.join(concepts)}): Design scenarios where these professional duties conflict or are challenged\n"
                    elif category == "Role":
                        base_prompt += f"- Roles ({', '.join(concepts)}): Include characters or stakeholders representing these professional positions\n"
                    elif category == "Action":
                        base_prompt += f"- Actions ({', '.join(concepts)}): Structure the case around decisions involving these specific actions\n"
                    elif category == "Event":
                        base_prompt += f"- Events ({', '.join(concepts)}): Include these types of incidents or occurrences in the timeline\n"
                    elif category == "State":
                        base_prompt += f"- States ({', '.join(concepts)}): Create situations that exemplify these conditions or circumstances\n"
                    elif category == "Resource":
                        base_prompt += f"- Resources ({', '.join(concepts)}): Reference these documents, tools, or materials in the case\n"
                    elif category == "Capability":
                        base_prompt += f"- Capabilities ({', '.join(concepts)}): Address questions of competence and expertise in these areas\n"
        
        base_prompt += """

TASK: Develop a comprehensive engineering ethics case that meaningfully incorporates the selected concepts. Focus on:

1. **Case Structure**: Create a realistic engineering scenario with clear timeline and stakeholders
2. **Concept Integration**: Weave the selected ontological concepts naturally into the narrative  
3. **Ethical Complexity**: Design genuine dilemmas where the selected concepts create tension
4. **Professional Context**: Ensure realistic engineering practices and industry standards
5. **Decision Points**: Create meaningful choices that require ethical reasoning

Provide specific, actionable guidance for developing this case. Be concrete about how to incorporate the selected concepts."""
        
        return base_prompt
    
    def _get_llm_guidance(self, prompt: str) -> str:
        """Get guidance from the LLM service."""
        try:
            response = self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.7,
                max_tokens=800
            )
            return response.get("response", "I'm having trouble generating guidance right now.")
        except Exception as e:
            logger.error(f"LLM guidance error: {e}")
            return "I'm currently unable to provide detailed guidance. Please try selecting your ontological categories and describe what kind of case you'd like to create."
    
    def _generate_suggestions(self, ontology_context: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate specific suggestions based on selected ontological context."""
        suggestions = []
        
        # Category-specific suggestions
        if "Principle" in self.selected_categories:
            suggestions.append({
                "type": "principle_focus",
                "title": "Focus on Ethical Principles",
                "description": "Develop scenarios where fundamental ethical principles conflict or need to be prioritized"
            })
        
        if "Obligation" in self.selected_categories:
            suggestions.append({
                "type": "obligation_conflict", 
                "title": "Professional Obligation Conflicts",
                "description": "Create situations where different professional obligations compete (e.g., client loyalty vs. public safety)"
            })
            
        if "Role" in self.selected_categories:
            suggestions.append({
                "type": "role_complexity",
                "title": "Multi-Role Scenarios", 
                "description": "Develop cases involving multiple professional roles with different responsibilities"
            })
            
        if "Action" in self.selected_categories:
            suggestions.append({
                "type": "decision_points",
                "title": "Critical Decision Points",
                "description": "Structure the case around specific actions the protagonist must take"
            })
            
        if "Event" in self.selected_categories:
            suggestions.append({
                "type": "sequence_development",
                "title": "Event Sequence Development", 
                "description": "Create a timeline of events that escalate the ethical complexity"
            })
        
        return suggestions
    
    def _suggest_next_steps(self, user_prompt: str, ontology_context: Dict[str, Any]) -> List[str]:
        """Suggest concrete next steps for case development."""
        steps = []
        
        # Basic structure steps
        steps.append("Define the main protagonist (engineer role and expertise)")
        steps.append("Establish the professional context (project, client, organization)")
        
        # Category-specific steps
        if "Principle" in self.selected_categories:
            steps.append("Identify 2-3 ethical principles that will be in tension")
            
        if "Obligation" in self.selected_categories:
            steps.append("Define conflicting professional obligations")
            
        if "State" in self.selected_categories:
            steps.append("Describe the problematic situation or ethical dilemma state")
            
        if "Resource" in self.selected_categories:
            steps.append("Specify relevant documents, standards, or resources")
            
        if "Action" in self.selected_categories:
            steps.append("Outline key decision points and possible actions")
            
        if "Event" in self.selected_categories:
            steps.append("Create a timeline of escalating events")
            
        if "Capability" in self.selected_categories:
            steps.append("Address competency and expertise boundaries")
        
        # Final steps
        steps.append("Develop realistic stakeholder perspectives")
        steps.append("Create multiple plausible resolution options")
        
        return steps
    
    def get_category_concepts(self, category: str, world_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get available concepts for a specific ontological category.
        
        Args:
            category: Name of the ontological category (e.g., 'Principle')
            world_id: World ID for context (optional)
            
        Returns:
            List of available concepts in that category
        """
        try:
            if world_id:
                from app.models.world import World
                world = World.query.get(world_id)
                if world:
                    entities = self.ontology_service.get_entities_for_world(world)
                    return entities.get("entities", {}).get(category, [])
            
            return []
        except Exception as e:
            logger.error(f"Error getting concepts for category {category}: {e}")
            return []
    
    def format_response_for_ui(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Format the analysis result for UI display."""
        return {
            "message": analysis_result.get("guidance", ""),
            "suggestions": analysis_result.get("suggestions", []),
            "next_steps": analysis_result.get("next_steps", []),
            "selected_categories": analysis_result.get("selected_categories", []),
            "agent_type": "case_creation",
            "status": "success" if "error" not in analysis_result else "error"
        }