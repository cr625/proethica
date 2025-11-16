from typing import Dict, List, Any, Optional
from langchain_classic.chains import LLMChain
from langchain_classic.prompts import PromptTemplate
from langchain_classic.llms.base import BaseLLM
from langchain_community.llms.fake import FakeListLLM
import os
from app.services.mcp_client import MCPClient

class DecisionEngine:
    """Engine for evaluating decisions using LangChain."""
    
    def __init__(self, llm: Optional[BaseLLM] = None, mcp_client: Optional[MCPClient] = None):
        """
        Initialize the decision engine with LangChain components.
        
        Args:
            llm: Language model to use for reasoning (optional)
            mcp_client: MCP client for retrieving guidelines and cases (optional)
        """
        # Use provided LLM or create a fake one for development
        self.llm = llm or self._create_fake_llm()
        
        # Use provided MCP client or get the singleton instance
        self.mcp_client = mcp_client or MCPClient.get_instance()
        
        # Setup domain-specific chains
        self.domain_chains = {
            "military-medical-triage": {
                "rules": self._setup_military_triage_rules_chain(),
                "ethics": self._setup_military_triage_ethics_chain()
            },
            "engineering-ethics": {
                "rules": self._setup_engineering_ethics_rules_chain(),
                "ethics": self._setup_engineering_ethics_ethics_chain()
            },
            "us-law-practice": {
                "rules": self._setup_law_practice_rules_chain(),
                "ethics": self._setup_law_practice_ethics_chain()
            }
        }
    
    def _create_fake_llm(self) -> BaseLLM:
        """Create a fake LLM for development and testing."""
        # This would be replaced with a real LLM in production
        responses = [
            "The decision complies with engineering ethics standards. The engineer has appropriately prioritized public safety and professional integrity in accordance with the NSPE Code of Ethics. The decision demonstrates proper acknowledgment of design limitations and commitment to corrective action.",
            "The decision raises important engineering ethics considerations regarding professional responsibility. While the engineer has followed proper protocols for addressing design errors, there may be additional considerations regarding stakeholder communication and long-term safety implications that warrant further analysis."
        ]
        return FakeListLLM(responses=responses)
    
    def _setup_military_triage_rules_chain(self) -> LLMChain:
        """Set up the chain for evaluating military medical triage rules compliance."""
        prompt = PromptTemplate(
            input_variables=["scenario", "decision", "guidelines"],
            template="""
            Given the following military medical triage scenario:
            
            {scenario}
            
            And these military medical triage guidelines:
            {guidelines}
            
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
    
    def _setup_military_triage_ethics_chain(self) -> LLMChain:
        """Set up the chain for evaluating military medical triage ethical implications."""
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
    
    def _setup_engineering_ethics_rules_chain(self) -> LLMChain:
        """Set up the chain for evaluating engineering ethics rules compliance."""
        prompt = PromptTemplate(
            input_variables=["scenario", "decision", "guidelines"],
            template="""
            Given the following engineering ethics scenario:
            
            {scenario}
            
            And these engineering ethics guidelines:
            {guidelines}
            
            Evaluate if the decision: {decision}
            
            complies with established engineering ethics codes and standards.
            Focus on:
            1. Safety and welfare of the public
            2. Professional competence and integrity
            3. Truthfulness and objectivity
            4. Conflicts of interest
            5. Confidentiality and intellectual property
            
            Provide a detailed analysis of rules compliance.
            """
        )
        return LLMChain(llm=self.llm, prompt=prompt)
    
    def _setup_engineering_ethics_ethics_chain(self) -> LLMChain:
        """Set up the chain for evaluating engineering ethics ethical implications."""
        prompt = PromptTemplate(
            input_variables=["scenario", "decision", "similar_cases"],
            template="""
            Given the following engineering ethics scenario:
            
            {scenario}
            
            Evaluate the ethical implications of the decision: {decision}
            
            Consider these similar cases for reference:
            {similar_cases}
            
            Analyze the decision from multiple ethical frameworks:
            1. Utilitarian perspective (maximizing overall welfare)
            2. Deontological perspective (adherence to duties and rights)
            3. Virtue ethics perspective (character and intentions)
            4. Professional responsibility
            5. Sustainability and environmental ethics
            
            Provide a nuanced ethical evaluation that considers competing values and principles.
            """
        )
        return LLMChain(llm=self.llm, prompt=prompt)
    
    def _setup_law_practice_rules_chain(self) -> LLMChain:
        """Set up the chain for evaluating US law practice rules compliance."""
        prompt = PromptTemplate(
            input_variables=["scenario", "decision", "guidelines"],
            template="""
            Given the following US law practice scenario:
            
            {scenario}
            
            And these legal ethics guidelines:
            {guidelines}
            
            Evaluate if the decision: {decision}
            
            complies with established legal ethics rules and standards.
            Focus on:
            1. Client-lawyer relationship obligations
            2. Confidentiality and attorney-client privilege
            3. Conflicts of interest
            4. Duties to the court and legal system
            5. Professional conduct and integrity
            
            Provide a detailed analysis of rules compliance.
            """
        )
        return LLMChain(llm=self.llm, prompt=prompt)
    
    def _setup_law_practice_ethics_chain(self) -> LLMChain:
        """Set up the chain for evaluating US law practice ethical implications."""
        prompt = PromptTemplate(
            input_variables=["scenario", "decision", "similar_cases"],
            template="""
            Given the following US law practice scenario:
            
            {scenario}
            
            Evaluate the ethical implications of the decision: {decision}
            
            Consider these similar cases for reference:
            {similar_cases}
            
            Analyze the decision from multiple ethical frameworks:
            1. Duty to client vs. duty to legal system
            2. Confidentiality vs. prevention of harm
            3. Zealous advocacy vs. fairness and justice
            4. Professional independence
            5. Access to justice considerations
            
            Provide a nuanced ethical evaluation that considers competing values and principles.
            """
        )
        return LLMChain(llm=self.llm, prompt=prompt)
    
    def get_similar_cases(self, scenario: Dict[str, Any]) -> str:
        """
        Retrieve similar cases for analogical reasoning from the MCP server.
        
        Args:
            scenario: Dictionary containing scenario data
            
        Returns:
            String containing similar cases for reference
        """
        # Get domain from scenario
        domain = self._get_domain_from_scenario(scenario)
        
        # Use MCP client to get similar cases
        try:
            # Create a query from the scenario
            query = f"{scenario.get('name', '')} {scenario.get('description', '')}"
            
            # Add character information
            for char in scenario.get('characters', []):
                query += f" {char.get('name', '')} {char.get('role', '')}"
                for cond in char.get('conditions', []):
                    query += f" {cond.get('name', '')}"
            
            # Search for similar cases
            results = self.mcp_client.search_cases(query, domain=domain)
            
            # Format results as text
            text = ""
            for case in results.get('results', []):
                text += f"Case {case.get('id', '')}: {case.get('title', '')}\n"
                text += f"Description: {case.get('description', '')}\n"
                text += f"Decision: {case.get('decision', '')}\n"
                text += f"Outcome: {case.get('outcome', '')}\n"
                text += f"Ethical Analysis: {case.get('ethical_analysis', '')}\n\n"
            
            return text
        except Exception as e:
            # Return a placeholder if there's an error
            return f"Error retrieving similar cases: {str(e)}\n\nUsing placeholder cases instead."
    
    def _get_domain_from_scenario(self, scenario: Dict[str, Any]) -> str:
        """
        Get the domain identifier from a scenario's world.
        
        Args:
            scenario: Dictionary containing scenario data
            
        Returns:
            Domain identifier string
        """
        # Check if scenario is a database model
        if hasattr(scenario, 'world') and scenario.world:
            # Extract domain from world name or metadata
            world_name = scenario.world.name.lower()
            if 'military' in world_name or 'medical' in world_name or 'triage' in world_name:
                return 'military-medical-triage'
            elif 'engineering' in world_name or 'engineer' in world_name:
                return 'engineering-ethics'
            elif 'law' in world_name or 'legal' in world_name:
                return 'us-law-practice'
        
        # Check if scenario is a dictionary with world information
        if isinstance(scenario, dict):
            if 'world' in scenario and isinstance(scenario['world'], dict):
                world_name = scenario['world'].get('name', '').lower()
                if 'military' in world_name or 'medical' in world_name or 'triage' in world_name:
                    return 'military-medical-triage'
                elif 'engineering' in world_name or 'engineer' in world_name:
                    return 'engineering-ethics'
                elif 'law' in world_name or 'legal' in world_name:
                    return 'us-law-practice'
            elif 'world_id' in scenario:
                # Get world name from database
                from app.models import World
                world_obj = World.query.get(scenario['world_id'])
                if world_obj:
                    world_name = world_obj.name.lower()
                    if 'military' in world_name or 'medical' in world_name or 'triage' in world_name:
                        return 'military-medical-triage'
                    elif 'engineering' in world_name or 'engineer' in world_name:
                        return 'engineering-ethics'
                    elif 'law' in world_name or 'legal' in world_name:
                        return 'us-law-practice'
        
        # Default to engineering ethics
        return "engineering-ethics"
    
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
        
        # Get domain from scenario
        domain = self._get_domain_from_scenario(scenario)
        
        # Get domain-specific chains
        if domain in self.domain_chains:
            rules_chain = self.domain_chains[domain]["rules"]
            ethics_chain = self.domain_chains[domain]["ethics"]
        else:
            # Default to engineering ethics
            rules_chain = self.domain_chains["engineering-ethics"]["rules"]
            ethics_chain = self.domain_chains["engineering-ethics"]["ethics"]
        
        # Get guidelines from MCP server
        try:
            guidelines_data = self.mcp_client.get_guidelines(domain)
            guidelines_text = self._format_guidelines(guidelines_data)
        except Exception as e:
            guidelines_text = f"Error retrieving guidelines: {str(e)}"
        
        # Get similar cases from MCP server
        similar_cases = self.get_similar_cases(scenario)
        
        # Evaluate rules compliance
        rules_result = rules_chain.run(
            scenario=scenario_text,
            decision=decision,
            guidelines=guidelines_text
        )
        
        # Evaluate ethical implications
        ethics_result = ethics_chain.run(
            scenario=scenario_text,
            decision=decision,
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
            "guidelines": guidelines_text
        }
    
    def _format_guidelines(self, guidelines_data: Dict[str, Any]) -> str:
        """
        Format guidelines data as text for LLM input.
        
        Args:
            guidelines_data: Dictionary containing guidelines data
            
        Returns:
            Formatted guidelines text
        """
        text = ""
        
        # Format guidelines
        for guideline in guidelines_data.get('guidelines', []):
            text += f"Guideline: {guideline.get('name', 'Unnamed guideline')}\n"
            text += f"Description: {guideline.get('description', '')}\n\n"
            
            # Add categories if present
            if 'categories' in guideline:
                text += "Categories:\n"
                for category in guideline.get('categories', []):
                    text += f"- {category.get('name', 'Unnamed')}: {category.get('description', '')}\n"
                text += "\n"
            
            # Add factors if present
            if 'factors' in guideline:
                text += "Factors:\n"
                for factor in guideline.get('factors', []):
                    text += f"- {factor}\n"
                text += "\n"
            
            # Add principles if present
            if 'principles' in guideline:
                text += "Principles:\n"
                for principle in guideline.get('principles', []):
                    text += f"- {principle}\n"
                text += "\n"
            
            # Add steps if present
            if 'steps' in guideline:
                text += "Steps:\n"
                for step in guideline.get('steps', []):
                    text += f"- {step}\n"
                text += "\n"
            
            # Add considerations if present
            if 'considerations' in guideline:
                text += "Considerations:\n"
                for consideration in guideline.get('considerations', []):
                    text += f"- {consideration}\n"
                text += "\n"
        
        return text
    
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
