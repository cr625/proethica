"""
Agent Orchestrator for the AI Ethical Decision-Making Simulator.

This module provides the AgentOrchestrator class that coordinates
between specialized agents in the multi-agent architecture.
"""

from typing import Dict, List, Any, Optional, Union
import logging
from app.services.embedding_service import EmbeddingService
from app.services.langchain_claude import LangChainClaudeService
from app.services.agents.guidelines_agent import GuidelinesAgent

# Set up logging
logger = logging.getLogger(__name__)

class AgentOrchestrator:
    """
    Orchestrator for coordinating between specialized agents.
    
    This class manages the flow of information between agents and
    combines their analyses into a final response.
    """
    
    def __init__(self, embedding_service: Optional[EmbeddingService] = None,
                langchain_claude: Optional[LangChainClaudeService] = None,
                world_id: Optional[int] = None,
                status_callback: Optional[callable] = None):
        """
        Initialize the agent orchestrator.
        
        Args:
            embedding_service: Service for generating embeddings and similarity search
            langchain_claude: Service for using Claude via LangChain
            world_id: ID of the world for context (optional)
            status_callback: Callback function for status updates (optional)
        """
        # Initialize services
        self.embedding_service = embedding_service or EmbeddingService.get_instance()
        self.langchain_claude = langchain_claude or LangChainClaudeService.get_instance()
        self.world_id = world_id
        self.status_callback = status_callback
        
        # Initialize agents
        self.guidelines_agent = GuidelinesAgent(
            embedding_service=self.embedding_service,
            langchain_claude=self.langchain_claude,
            world_id=self.world_id,
            status_callback=self._create_agent_status_callback("Guidelines")
        )
        
        # Create synthesis chain
        self.synthesis_chain = self.langchain_claude.create_chain(
            template="""
            You are synthesizing analyses from multiple specialized agents to provide
            a comprehensive ethical evaluation of a decision.
            
            SCENARIO: {scenario}
            
            DECISION POINT: {decision}
            
            OPTIONS:
            {options}
            
            GUIDELINES ANALYSIS:
            {guidelines_analysis}
            
            Based on the guidelines analysis, provide a comprehensive evaluation of the decision options.
            For each option, provide:
            1. Overall ethical score (1-10)
            2. Key strengths and weaknesses
            3. Recommendation (strongly recommend, recommend, neutral, caution against, strongly caution against)
            
            Finally, provide a brief summary of which option appears most ethically sound based on the guidelines.
            
            YOUR SYNTHESIS:
            """,
            input_variables=["scenario", "decision", "options", "guidelines_analysis"]
        )
        
        logger.info("Initialized Agent Orchestrator with Guidelines Agent")
    
    def _create_agent_status_callback(self, agent_name: str) -> callable:
        """
        Create a status callback function for an agent.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Status callback function
        """
        def callback(status: str, detail: Optional[str] = None):
            if self.status_callback:
                message = f"{agent_name} Agent: {status}"
                if detail:
                    message += f" - {detail}"
                self.status_callback(message)
            logger.info(f"{agent_name} Agent status: {status} {detail or ''}")
        
        return callback
    
    def _update_status(self, status: str, detail: Optional[str] = None):
        """
        Update the status of the orchestrator.
        
        Args:
            status: Status message
            detail: Additional detail (optional)
        """
        if self.status_callback:
            message = f"Agent Orchestrator: {status}"
            if detail:
                message += f" - {detail}"
            self.status_callback(message)
        logger.info(f"Agent Orchestrator status: {status} {detail or ''}")
    
    def process_decision(self, scenario_data: Dict[str, Any], decision_text: str,
                        options: List[Union[str, Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Process a decision using the multi-agent architecture.
        
        Args:
            scenario_data: Dictionary containing scenario data
            decision_text: Text describing the decision
            options: List of decision options
            
        Returns:
            Dictionary containing processing results
        """
        try:
            self._update_status("Starting decision analysis", f"Decision: {decision_text[:50]}...")
            
            # Initialize results dictionary
            results = {}
            
            # Process with Guidelines Agent
            self._update_status("Consulting Guidelines Agent")
            guidelines_result = self.guidelines_agent.analyze(
                scenario_data=scenario_data,
                decision_text=decision_text,
                options=options
            )
            results["guidelines"] = guidelines_result
            self._update_status("Guidelines analysis complete")
            
            # In the future, process with other agents here
            # For example:
            # self._update_status("Consulting Ontology Agent")
            # results["ontology"] = self.ontology_agent.analyze(...)
            # self._update_status("Ontology analysis complete")
            
            # self._update_status("Consulting Cases Agent")
            # results["cases"] = self.cases_agent.analyze(...)
            # self._update_status("Cases analysis complete")
            # etc.
            
            # Synthesize results
            self._update_status("Synthesizing agent results")
            synthesis = self.langchain_claude.run_chain(
                self.synthesis_chain,
                scenario=scenario_data.get('description', ''),
                decision=decision_text,
                options=self._format_options(options),
                guidelines_analysis=guidelines_result.get('analysis', '')
            )
            self._update_status("Synthesis complete")
            
            # Return combined results
            return {
                "agent_results": results,
                "synthesis": synthesis,
                "final_response": synthesis  # For now, just use synthesis as final response
            }
        
        except Exception as e:
            logger.error(f"Error in Agent Orchestrator: {str(e)}")
            return {
                "agent_results": {},
                "synthesis": f"Error processing decision: {str(e)}",
                "final_response": f"I encountered an error while analyzing this decision: {str(e)}"
            }
    
    def _format_options(self, options: List[Union[str, Dict[str, Any]]]) -> str:
        """
        Format options for LLM input.
        
        Args:
            options: List of options (strings or dictionaries)
            
        Returns:
            Formatted options string
        """
        formatted = []
        for i, option in enumerate(options):
            option_text = option
            if isinstance(option, dict) and 'text' in option:
                option_text = option['text']
            formatted.append(f"{i+1}. {option_text}")
        return "\n".join(formatted)
