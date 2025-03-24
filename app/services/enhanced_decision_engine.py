"""
Enhanced Decision Engine that uses vector similarity search for retrieving relevant guidelines.
"""

from typing import Dict, List, Any, Optional, Union
import logging
from app.services.decision_engine import DecisionEngine
# Import EmbeddingService in methods to avoid circular imports
from app.models.document import Document, DocumentChunk

# Set up logging
logger = logging.getLogger(__name__)

class EnhancedDecisionEngine(DecisionEngine):
    """
    Enhanced Decision Engine that uses vector similarity search for retrieving relevant guidelines.
    This extends the base DecisionEngine with vector similarity search capabilities.
    """
    
    def __init__(self, llm_service=None, mcp_client=None, embedding_service=None):
        """
        Initialize the enhanced decision engine with LangChain components and embedding service.
        
        Args:
            llm_service: Language model service to use for reasoning
            mcp_client: MCP client for retrieving guidelines and cases
            embedding_service: Service for generating embeddings and performing similarity search
        """
        # Initialize the base decision engine
        super().__init__(llm_service, mcp_client)
        
        # Initialize the embedding service
        if embedding_service:
            self.embedding_service = embedding_service
        else:
            # Import here to avoid circular imports
            from app.services.embedding_service import EmbeddingService
            self.embedding_service = EmbeddingService()
    
    def evaluate_decision(self, decision, scenario, character=None, guidelines=None):
        """
        Evaluate a decision against rules and ethics, using vector similarity search for relevant guidelines.
        
        Args:
            decision: Decision object or string describing the decision to evaluate
            scenario: Scenario object or dictionary containing scenario data
            character: Character object making the decision (optional)
            guidelines: List of guideline strings (optional)
            
        Returns:
            Dictionary containing evaluation results
        """
        try:
            # Extract decision text
            if hasattr(decision, 'description'):
                decision_text = decision.description
            else:
                decision_text = str(decision)
            
            # Extract scenario data
            scenario_data = self._extract_scenario_data(scenario)
            
            # Extract character data if provided
            character_data = self._extract_character_data(character) if character else {}
            
            # Construct query for similarity search
            query = self._construct_similarity_query(decision_text, scenario_data, character_data)
            
            # Get world_id for filtering
            world_id = None
            if hasattr(scenario, 'world_id'):
                world_id = scenario.world_id
            elif hasattr(scenario, 'world') and hasattr(scenario.world, 'id'):
                world_id = scenario.world.id
            
            # Retrieve relevant guidelines using vector similarity search
            retrieved_guidelines = self._retrieve_relevant_guidelines(query, world_id)
            
            # Combine with any explicitly provided guidelines
            all_guidelines = retrieved_guidelines
            if guidelines:
                if isinstance(guidelines, list):
                    all_guidelines.extend(guidelines)
                else:
                    all_guidelines.append(str(guidelines))
            
            # Format guidelines for LLM input
            guidelines_text = "\n\n".join(all_guidelines)
            
            # Get domain from scenario
            domain = self._get_domain_from_scenario(scenario_data)
            
            # Get domain-specific chains
            if domain in self.domain_chains:
                rules_chain = self.domain_chains[domain]["rules"]
                ethics_chain = self.domain_chains[domain]["ethics"]
            else:
                # Default to military medical triage
                rules_chain = self.domain_chains["military-medical-triage"]["rules"]
                ethics_chain = self.domain_chains["military-medical-triage"]["ethics"]
            
            # Format scenario for LLM
            scenario_text = self._format_scenario(scenario_data)
            
            # Get similar cases
            similar_cases = self.get_similar_cases(scenario_data)
            
            # Evaluate rules compliance
            rules_result = rules_chain.run(
                scenario=scenario_text,
                decision=decision_text,
                guidelines=guidelines_text
            )
            
            # Evaluate ethical implications
            ethics_result = ethics_chain.run(
                scenario=scenario_text,
                decision=decision_text,
                similar_cases=similar_cases
            )
            
            # Parse results to extract scores
            rules_score = self._parse_rules_score(rules_result)
            ethics_score = self._parse_ethics_score(ethics_result)
            
            return {
                "domain": domain,
                "rules_compliance": rules_score,
                "ethical_evaluation": ethics_score,
                "rules_reasoning": rules_result,
                "ethics_reasoning": ethics_result,
                "combined_score": (rules_score + ethics_score) / 2,
                "similar_cases": similar_cases,
                "guidelines": guidelines_text,
                "retrieved_guidelines_count": len(retrieved_guidelines)
            }
        
        except Exception as e:
            logger.error(f"Error evaluating decision: {str(e)}")
            # Fall back to the base decision engine
            return super().evaluate_decision(decision, scenario)
    
    def _extract_scenario_data(self, scenario) -> Dict[str, Any]:
        """
        Extract scenario data from a scenario object or dictionary.
        
        Args:
            scenario: Scenario object or dictionary
            
        Returns:
            Dictionary containing scenario data
        """
        if isinstance(scenario, dict):
            return scenario
        
        # Extract data from scenario object
        scenario_data = {
            'id': getattr(scenario, 'id', None),
            'name': getattr(scenario, 'name', 'Unnamed scenario'),
            'description': getattr(scenario, 'description', ''),
            'world_id': getattr(scenario, 'world_id', None)
        }
        
        # Extract world data if available
        if hasattr(scenario, 'world') and scenario.world:
            scenario_data['world'] = {
                'id': scenario.world.id,
                'name': scenario.world.name,
                'description': scenario.world.description
            }
        
        # Extract characters if available
        if hasattr(scenario, 'characters') and scenario.characters:
            scenario_data['characters'] = []
            for char in scenario.characters:
                char_data = {
                    'id': char.id,
                    'name': char.name,
                    'role': getattr(char, 'role', None)
                }
                
                # Extract conditions if available
                if hasattr(char, 'conditions') and char.conditions:
                    char_data['conditions'] = []
                    for cond in char.conditions:
                        char_data['conditions'].append({
                            'id': cond.id,
                            'name': cond.name,
                            'description': cond.description,
                            'severity': getattr(cond, 'severity', None)
                        })
                
                scenario_data['characters'].append(char_data)
        
        # Extract resources if available
        if hasattr(scenario, 'resources') and scenario.resources:
            scenario_data['resources'] = []
            for res in scenario.resources:
                scenario_data['resources'].append({
                    'id': res.id,
                    'name': res.name,
                    'description': res.description,
                    'quantity': getattr(res, 'quantity', 0)
                })
        
        # Extract events if available
        if hasattr(scenario, 'events') and scenario.events:
            scenario_data['events'] = []
            for event in scenario.events:
                scenario_data['events'].append({
                    'id': event.id,
                    'description': event.description,
                    'event_time': str(event.event_time)
                })
        
        return scenario_data
    
    def _extract_character_data(self, character) -> Dict[str, Any]:
        """
        Extract character data from a character object or dictionary.
        
        Args:
            character: Character object or dictionary
            
        Returns:
            Dictionary containing character data
        """
        if isinstance(character, dict):
            return character
        
        # Extract data from character object
        character_data = {
            'id': getattr(character, 'id', None),
            'name': getattr(character, 'name', 'Unnamed character'),
            'role': getattr(character, 'role', None)
        }
        
        # Extract conditions if available
        if hasattr(character, 'conditions') and character.conditions:
            character_data['conditions'] = []
            for cond in character.conditions:
                character_data['conditions'].append({
                    'id': cond.id,
                    'name': cond.name,
                    'description': cond.description,
                    'severity': getattr(cond, 'severity', None)
                })
        
        return character_data
    
    def _construct_similarity_query(self, decision_text: str, scenario_data: Dict[str, Any], 
                                   character_data: Dict[str, Any]) -> str:
        """
        Construct a query for similarity search based on decision, scenario, and character data.
        
        Args:
            decision_text: Text describing the decision
            scenario_data: Dictionary containing scenario data
            character_data: Dictionary containing character data
            
        Returns:
            Query string for similarity search
        """
        query = f"Decision: {decision_text}\n\n"
        
        # Add scenario information
        query += f"Scenario: {scenario_data.get('name', '')}\n"
        query += f"Description: {scenario_data.get('description', '')}\n\n"
        
        # Add character information if available
        if character_data:
            query += f"Character: {character_data.get('name', '')}\n"
            query += f"Role: {character_data.get('role', '')}\n\n"
            
            # Add conditions if available
            if 'conditions' in character_data and character_data['conditions']:
                query += "Conditions:\n"
                for cond in character_data['conditions']:
                    query += f"- {cond.get('name', '')}: {cond.get('description', '')}\n"
        
        return query
    
    def _retrieve_relevant_guidelines(self, query: str, world_id: Optional[int] = None) -> List[str]:
        """
        Retrieve relevant guidelines using vector similarity search.
        
        Args:
            query: Query string for similarity search
            world_id: ID of the world to filter guidelines by
            
        Returns:
            List of relevant guideline texts
        """
        try:
            # Search for similar chunks
            results = self.embedding_service.search_similar_chunks(
                query=query,
                k=5,
                world_id=world_id,
                document_type='guideline'
            )
            
            # Extract guideline texts
            guidelines = []
            for result in results:
                guidelines.append(result['chunk_text'])
            
            return guidelines
        
        except Exception as e:
            logger.error(f"Error retrieving relevant guidelines: {str(e)}")
            return []
    
    def find_similar_scenarios(self, scenario_text: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Find scenarios similar to the given scenario text.
        
        Args:
            scenario_text: Text describing the scenario
            k: Number of similar scenarios to retrieve
            
        Returns:
            List of similar scenarios
        """
        try:
            return self.embedding_service.search_similar_chunks(
                query=scenario_text,
                k=k,
                document_type='scenario'
            )
        except Exception as e:
            logger.error(f"Error finding similar scenarios: {str(e)}")
            return []
