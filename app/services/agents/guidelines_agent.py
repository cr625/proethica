"""
Guidelines Agent for the AI Ethical Decision-Making Simulator.

This module provides the GuidelinesAgent class that specializes in
retrieving and analyzing guidelines for ethical decision-making.
"""

from typing import Dict, List, Any, Optional, Union
import logging
from app.services.agents.base_agent import BaseAgent
from app.services.langchain_claude import LangChainClaudeService
from app.services.embedding_service import EmbeddingService

# Set up logging
logger = logging.getLogger(__name__)

class GuidelinesAgent(BaseAgent):
    """
    Agent specialized in retrieving and analyzing guidelines for decisions.
    
    This agent uses vector similarity search to find relevant guidelines
    and LangChain with Claude to analyze them in the context of decisions.
    """
    
    def __init__(self, embedding_service: Optional[EmbeddingService] = None, 
                langchain_claude: Optional[LangChainClaudeService] = None,
                world_id: Optional[int] = None,
                status_callback: Optional[callable] = None):
        """
        Initialize the guidelines agent.
        
        Args:
            embedding_service: Service for generating embeddings and similarity search
            langchain_claude: Service for using Claude via LangChain
            world_id: ID of the world for context (optional)
            status_callback: Callback function for status updates (optional)
        """
        super().__init__("Guidelines", world_id)
        
        # Initialize embedding service
        if embedding_service:
            self.embedding_service = embedding_service
        else:
            self.embedding_service = EmbeddingService()
        
        # Initialize LangChain Claude service
        if langchain_claude:
            self.langchain_claude = langchain_claude
        else:
            self.langchain_claude = LangChainClaudeService.get_instance()
            
        # Status callback
        self.status_callback = status_callback
        
        # Create the guidelines analysis chain
        self.analysis_chain = self.langchain_claude.create_chain(
            template="""
            You are analyzing an ethical decision based on relevant guidelines.
            
            SCENARIO: {scenario}
            
            DECISION POINT: {decision}
            
            OPTIONS:
            {options}
            
            RELEVANT GUIDELINES:
            {guidelines}
            
            Analyze how each option aligns with the guidelines. Focus only on the guidelines perspective.
            For each option, provide:
            1. Alignment score (1-10)
            2. Reasoning based on specific guidelines
            3. Key guideline principles that apply
            
            YOUR ANALYSIS:
            """,
            input_variables=["scenario", "decision", "options", "guidelines"]
        )
        
        logger.info("Initialized Guidelines Agent with analysis chain")
    
    def _update_status(self, status: str, detail: Optional[str] = None):
        """
        Update the status of the agent.
        
        Args:
            status: Status message
            detail: Additional detail (optional)
        """
        if self.status_callback:
            self.status_callback(status, detail)
        logger.info(f"Guidelines Agent status: {status} {detail or ''}")
    
    def analyze(self, scenario_data: Dict[str, Any], decision_text: str, 
               options: List[Union[str, Dict[str, Any]]], 
               previous_results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze a decision in the context of relevant guidelines.
        
        Args:
            scenario_data: Dictionary containing scenario data
            decision_text: Text describing the decision to analyze
            options: List of decision options
            previous_results: Results from previous agents in the chain (optional)
            
        Returns:
            Dictionary containing analysis results
        """
        try:
            self._update_status("Starting analysis", f"Decision: {decision_text[:50]}...")
            
            # Extract and normalize scenario data
            normalized_scenario = self._extract_scenario_data(scenario_data)
            
            # Construct query for relevant guidelines
            self._update_status("Constructing query")
            query = self._construct_query(normalized_scenario, decision_text, options)
            
            # Retrieve relevant guidelines using vector similarity
            self._update_status("Searching for relevant guidelines")
            relevant_guidelines = self.embedding_service.search_similar_chunks(
                query=query,
                k=5,
                world_id=normalized_scenario.get('world_id'),
                document_type='guideline'
            )
            
            if relevant_guidelines:
                self._update_status("Found relevant guidelines", f"{len(relevant_guidelines)} guidelines found")
                for i, guideline in enumerate(relevant_guidelines[:3]):  # Show top 3 for status
                    title = guideline.get('title', 'Untitled')
                    self._update_status(f"Guideline {i+1}", f"{title[:50]}...")
            else:
                self._update_status("No relevant guidelines found via vector search")
            
            # Format guidelines for LLM input
            guidelines_text = self._format_guidelines(relevant_guidelines)
            
            # If no guidelines found, try to get them from the Claude service
            if not guidelines_text:
                self._update_status("Retrieving guidelines from Claude service")
                guidelines_text = self.langchain_claude.get_guidelines_for_world(
                    world_id=normalized_scenario.get('world_id')
                )
            
            # Run the analysis chain
            self._update_status("Analyzing guidelines")
            analysis = self.langchain_claude.run_chain(
                self.analysis_chain,
                scenario=normalized_scenario.get('description', ''),
                decision=decision_text,
                options=self._format_options(options),
                guidelines=guidelines_text
            )
            
            self._update_status("Analysis complete")
            
            return {
                "analysis": analysis,
                "relevant_guidelines": relevant_guidelines,
                "raw_guidelines_text": guidelines_text
            }
        
        except Exception as e:
            logger.error(f"Error in Guidelines Agent analysis: {str(e)}")
            return {
                "analysis": f"Error analyzing guidelines: {str(e)}",
                "relevant_guidelines": [],
                "raw_guidelines_text": "No guidelines available due to an error."
            }
    
    def _construct_query(self, scenario_data: Dict[str, Any], decision_text: str, 
                        options: List[Union[str, Dict[str, Any]]]) -> str:
        """
        Construct a query for similarity search based on scenario and decision.
        
        Args:
            scenario_data: Dictionary containing scenario data
            decision_text: Text describing the decision
            options: List of decision options
            
        Returns:
            Query string for similarity search
        """
        query = f"Decision: {decision_text}\n\n"
        query += f"Scenario: {scenario_data.get('name', '')}\n"
        query += f"Description: {scenario_data.get('description', '')}\n\n"
        query += "Options:\n"
        
        # Add options to query
        formatted_options = self._format_options(options)
        query += formatted_options
        
        return query
    
    def _format_guidelines(self, guidelines_chunks: List[Dict[str, Any]]) -> str:
        """
        Format guidelines chunks for LLM input.
        
        Args:
            guidelines_chunks: List of guideline chunks from vector search
            
        Returns:
            Formatted guidelines text
        """
        if not guidelines_chunks:
            return ""
            
        formatted = []
        for i, chunk in enumerate(guidelines_chunks):
            formatted.append(f"GUIDELINE {i+1}: {chunk['chunk_text']}")
        
        return "\n\n".join(formatted)
