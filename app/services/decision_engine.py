from typing import Dict, List, Any, Optional
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.llms.base import BaseLLM
from langchain_community.llms.fake import FakeListLLM
import os

class DecisionEngine:
    """Engine for evaluating decisions using LangChain."""
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        """
        Initialize the decision engine with LangChain components.
        
        Args:
            llm: Language model to use for reasoning (optional)
        """
        # Use provided LLM or create a fake one for development
        self.llm = llm or self._create_fake_llm()
        
        # Setup chains
        self.rules_chain = self._setup_rules_chain()
        self.ethics_chain = self._setup_ethics_chain()
    
    def _create_fake_llm(self) -> BaseLLM:
        """Create a fake LLM for development and testing."""
        # This would be replaced with a real LLM in production
        responses = [
            "The decision complies with medical triage protocols. Priority is given to patients with life-threatening conditions that can be treated with available resources.",
            "The decision raises ethical concerns regarding resource allocation. While it follows utilitarian principles of maximizing lives saved, it may neglect individual rights and dignity."
        ]
        return FakeListLLM(responses=responses)
    
    def _setup_rules_chain(self) -> LLMChain:
        """Set up the chain for evaluating rules compliance."""
        prompt = PromptTemplate(
            input_variables=["scenario", "decision"],
            template="""
            Given the following military medical triage scenario:
            
            {scenario}
            
            Evaluate if the decision: {decision}
            
            complies with established protocols and constraints for military medical triage.
            Focus on:
            1. Proper categorization of patients
            2. Appropriate resource allocation
            3. Adherence to standard triage protocols
            4. Compliance with military medical guidelines
            
            Provide a detailed analysis of rules compliance.
            """
        )
        return LLMChain(llm=self.llm, prompt=prompt)
    
    def _setup_ethics_chain(self) -> LLMChain:
        """Set up the chain for evaluating ethical implications."""
        prompt = PromptTemplate(
            input_variables=["scenario", "decision", "similar_cases"],
            template="""
            Given the following military medical triage scenario:
            
            {scenario}
            
            Evaluate the ethical implications of the decision: {decision}
            
            Consider these similar cases for reference:
            {similar_cases}
            
            Analyze the decision from multiple ethical frameworks:
            1. Utilitarian perspective (maximizing overall welfare)
            2. Deontological perspective (adherence to duties and rights)
            3. Virtue ethics perspective (character and intentions)
            4. Justice and fairness considerations
            5. Military medical ethics principles
            
            Provide a nuanced ethical evaluation that considers competing values and principles.
            """
        )
        return LLMChain(llm=self.llm, prompt=prompt)
    
    def get_similar_cases(self, scenario: Dict[str, Any]) -> str:
        """
        Retrieve similar cases for analogical reasoning.
        
        Args:
            scenario: Dictionary containing scenario data
            
        Returns:
            String containing similar cases for reference
        """
        # This would typically involve vector database retrieval
        # For now, we'll return a placeholder
        return """
        Case 1: Field hospital with limited supplies treating soldiers with varying injuries.
        Decision: Prioritized those with highest chance of survival and return to duty.
        Outcome: Maximized military effectiveness but resulted in some potentially salvageable patients being classified as expectant.
        
        Case 2: Mass casualty event with civilians and military personnel.
        Decision: Treated all patients equally based on medical need regardless of status.
        Outcome: Aligned with humanitarian principles but reduced military operational effectiveness.
        """
    
    def evaluate_decision(self, scenario: Dict[str, Any], decision: str) -> Dict[str, Any]:
        """
        Evaluate a decision against rules and ethics.
        
        Args:
            scenario: Dictionary containing scenario data
            decision: String describing the decision to evaluate
            
        Returns:
            Dictionary containing evaluation results
        """
        # Format scenario for LLM
        scenario_text = self._format_scenario(scenario)
        
        # Get similar cases
        similar_cases = self.get_similar_cases(scenario)
        
        # Evaluate rules compliance
        rules_result = self.rules_chain.run(
            scenario=scenario_text,
            decision=decision
        )
        
        # Evaluate ethical implications
        ethics_result = self.ethics_chain.run(
            scenario=scenario_text,
            decision=decision,
            similar_cases=similar_cases
        )
        
        # Parse results to extract scores
        rules_score = self._parse_rules_score(rules_result)
        ethics_score = self._parse_ethics_score(ethics_result)
        
        return {
            "rules_compliance": rules_score,
            "ethical_evaluation": ethics_score,
            "rules_reasoning": rules_result,
            "ethics_reasoning": ethics_result,
            "combined_score": (rules_score + ethics_score) / 2,
            "similar_cases": similar_cases
        }
    
    def _format_scenario(self, scenario: Dict[str, Any]) -> str:
        """
        Format scenario data as text for LLM input.
        
        Args:
            scenario: Dictionary containing scenario data
            
        Returns:
            Formatted scenario text
        """
        # Build scenario description
        text = f"Scenario: {scenario.get('name', 'Unnamed scenario')}\n\n"
        text += f"Description: {scenario.get('description', '')}\n\n"
        
        # Add characters
        text += "Characters:\n"
        for char in scenario.get('characters', []):
            text += f"- {char.get('name', 'Unnamed')} ({char.get('role', 'Unknown role')})\n"
            
            # Add conditions
            for cond in char.get('conditions', []):
                text += f"  * Condition: {cond.get('name', 'Unknown')} "
                text += f"(Severity: {cond.get('severity', 'Unknown')})\n"
                text += f"    {cond.get('description', '')}\n"
        
        # Add resources
        text += "\nResources:\n"
        for res in scenario.get('resources', []):
            text += f"- {res.get('name', 'Unknown')}: {res.get('quantity', 0)} units\n"
            text += f"  {res.get('description', '')}\n"
        
        # Add timeline
        text += "\nTimeline:\n"
        for event in scenario.get('events', []):
            text += f"- {event.get('event_time', 'Unknown time')}: {event.get('description', '')}\n"
        
        return text
    
    def _parse_rules_score(self, rules_result: str) -> float:
        """
        Parse rules compliance score from LLM output.
        
        Args:
            rules_result: String containing LLM evaluation of rules compliance
            
        Returns:
            Float score between 0 and 1
        """
        # This would typically involve more sophisticated parsing
        # For now, we'll return a placeholder value
        return 0.8
    
    def _parse_ethics_score(self, ethics_result: str) -> float:
        """
        Parse ethical evaluation score from LLM output.
        
        Args:
            ethics_result: String containing LLM ethical evaluation
            
        Returns:
            Float score between 0 and 1
        """
        # This would typically involve more sophisticated parsing
        # For now, we'll return a placeholder value
        return 0.7
