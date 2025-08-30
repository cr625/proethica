"""
Multi-Agent Coordinator for ProEthica

Implements specialized agents for different aspects of ethical reasoning,
coordinating their responses to provide comprehensive ethical analysis.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class ComponentType(Enum):
    """ProEthica formal model components"""
    ROLE = "Role"
    PRINCIPLE = "Principle"
    OBLIGATION = "Obligation"
    STATE = "State"
    RESOURCE = "Resource"
    ACTION = "Action"
    EVENT = "Event"
    CAPABILITY = "Capability"
    CONSTRAINT = "Constraint"


@dataclass
class EthicalConcept:
    """Represents an ethical concept from the ontology"""
    uri: str
    label: str
    component_type: ComponentType
    description: str = ""
    relationships: Dict[str, List[str]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentAnalysis:
    """Result from an individual agent's analysis"""
    agent_type: str
    concepts_identified: List[EthicalConcept]
    interpretation: str
    confidence: float = 0.0
    reasoning_trace: List[str] = field(default_factory=list)


@dataclass
class EthicalConflict:
    """Represents a conflict between ethical considerations"""
    conflicting_concepts: List[EthicalConcept]
    conflict_type: str  # e.g., "obligation-obligation", "principle-obligation"
    severity: str  # "low", "medium", "high"
    description: str


@dataclass
class ConflictResolution:
    """Proposed resolution for an ethical conflict"""
    conflict: EthicalConflict
    resolution_strategy: str
    prioritized_concept: Optional[EthicalConcept]
    compromise_solution: Optional[str]
    justification: str


class BaseEthicalAgent:
    """Base class for specialized ethical reasoning agents"""
    
    def __init__(self, mcp_manager=None):
        self.mcp_manager = mcp_manager
        self.agent_type = self.__class__.__name__
        
    async def analyze(self, 
                     query_components: List[str],
                     ontology_context: Dict[str, Any],
                     domain: str = "engineering-ethics") -> AgentAnalysis:
        """
        Analyze query components relevant to this agent
        
        Args:
            query_components: Components identified in the query
            ontology_context: Ontological concepts retrieved
            domain: Professional domain
            
        Returns:
            Agent's analysis of the ethical situation
        """
        raise NotImplementedError("Subclasses must implement analyze()")


class PrincipleAgent(BaseEthicalAgent):
    """Agent specializing in ethical principles"""
    
    async def analyze(self, query_components, ontology_context, domain):
        """Analyze ethical principles in the query"""
        reasoning_trace = []
        concepts = []
        
        # Look for principle-related concepts
        principles = ontology_context.get("Principle", [])
        
        for principle in principles:
            concept = EthicalConcept(
                uri=principle.get("uri", ""),
                label=principle.get("label", ""),
                component_type=ComponentType.PRINCIPLE,
                description=principle.get("description", "")
            )
            concepts.append(concept)
            reasoning_trace.append(f"Identified principle: {concept.label}")
        
        # Generate interpretation
        if concepts:
            interpretation = f"The query involves {len(concepts)} ethical principle(s): "
            interpretation += ", ".join([c.label for c in concepts])
            interpretation += ". These provide abstract ethical guidance for professional conduct."
        else:
            interpretation = "No explicit ethical principles identified in the query."
        
        return AgentAnalysis(
            agent_type="PrincipleAgent",
            concepts_identified=concepts,
            interpretation=interpretation,
            confidence=0.8 if concepts else 0.3,
            reasoning_trace=reasoning_trace
        )
    
    async def interpret_principle(self, principle: str, context: Dict) -> str:
        """Interpret a principle in a specific context"""
        # This would use the LLM to interpret abstract principles
        interpretation = f"The principle '{principle}' in this context means: "
        
        if "safety" in principle.lower():
            interpretation += "prioritizing the protection of human life and wellbeing above other considerations."
        elif "honesty" in principle.lower():
            interpretation += "providing truthful and complete information to all stakeholders."
        else:
            interpretation += "acting in accordance with professional ethical standards."
        
        return interpretation


class ObligationAgent(BaseEthicalAgent):
    """Agent specializing in professional obligations"""
    
    async def analyze(self, query_components, ontology_context, domain):
        """Analyze obligations in the query"""
        reasoning_trace = []
        concepts = []
        
        # Look for obligation-related concepts
        obligations = ontology_context.get("Obligation", [])
        
        for obligation in obligations:
            concept = EthicalConcept(
                uri=obligation.get("uri", ""),
                label=obligation.get("label", ""),
                component_type=ComponentType.OBLIGATION,
                description=obligation.get("description", "")
            )
            concepts.append(concept)
            reasoning_trace.append(f"Identified obligation: {concept.label}")
        
        # Check for role-based obligations
        roles = ontology_context.get("Role", [])
        if roles:
            reasoning_trace.append(f"Checking obligations for {len(roles)} role(s)")
        
        # Generate interpretation
        if concepts:
            interpretation = f"The query involves {len(concepts)} professional obligation(s): "
            interpretation += ", ".join([c.label for c in concepts])
            interpretation += ". These are concrete requirements that must be fulfilled."
        else:
            interpretation = "No explicit obligations identified, but role-based obligations may apply."
        
        return AgentAnalysis(
            agent_type="ObligationAgent",
            concepts_identified=concepts,
            interpretation=interpretation,
            confidence=0.9 if concepts else 0.4,
            reasoning_trace=reasoning_trace
        )
    
    async def check_fulfillment(self, action: str, obligations: List[EthicalConcept]) -> Dict:
        """Check if an action fulfills obligations"""
        results = {}
        for obligation in obligations:
            # Simplified logic - in reality would use more sophisticated reasoning
            if "safety" in obligation.label.lower() and "ensure" in action.lower():
                results[obligation.label] = "fulfilled"
            elif "report" in obligation.label.lower() and "inform" in action.lower():
                results[obligation.label] = "fulfilled"
            else:
                results[obligation.label] = "unclear"
        
        return results


class PrecedentAgent(BaseEthicalAgent):
    """Agent specializing in case-based reasoning"""
    
    async def analyze(self, query_components, ontology_context, domain):
        """Analyze precedents relevant to the query"""
        reasoning_trace = []
        concepts = []
        
        # Look for precedent/resource concepts
        resources = ontology_context.get("Resource", [])
        
        for resource in resources:
            if "precedent" in resource.get("label", "").lower() or \
               "case" in resource.get("label", "").lower():
                concept = EthicalConcept(
                    uri=resource.get("uri", ""),
                    label=resource.get("label", ""),
                    component_type=ComponentType.RESOURCE,
                    description=resource.get("description", "")
                )
                concepts.append(concept)
                reasoning_trace.append(f"Found relevant precedent: {concept.label}")
        
        # Generate interpretation
        if concepts:
            interpretation = f"Found {len(concepts)} relevant precedent(s) that may guide decision-making."
        else:
            interpretation = "No specific precedents identified, but case-based reasoning may still apply."
        
        return AgentAnalysis(
            agent_type="PrecedentAgent",
            concepts_identified=concepts,
            interpretation=interpretation,
            confidence=0.7 if concepts else 0.3,
            reasoning_trace=reasoning_trace
        )
    
    async def find_similar_cases(self, scenario: Dict) -> List[Dict]:
        """Find cases similar to the current scenario"""
        # In a real implementation, this would use semantic similarity
        # For now, return mock data
        return [
            {
                "case_id": "NSPE-BER-96-1",
                "similarity": 0.85,
                "decision": "Engineer must report safety concerns",
                "key_factors": ["public safety", "professional duty"]
            }
        ]


class ConflictResolutionAgent(BaseEthicalAgent):
    """Agent specializing in resolving ethical conflicts"""
    
    async def identify_conflicts(self, 
                               agent_analyses: List[AgentAnalysis]) -> List[EthicalConflict]:
        """Identify conflicts between different ethical considerations"""
        conflicts = []
        
        # Collect all concepts by type
        concepts_by_type = {}
        for analysis in agent_analyses:
            for concept in analysis.concepts_identified:
                type_key = concept.component_type.value
                if type_key not in concepts_by_type:
                    concepts_by_type[type_key] = []
                concepts_by_type[type_key].append(concept)
        
        # Check for obligation conflicts
        obligations = concepts_by_type.get("Obligation", [])
        if len(obligations) > 1:
            # Simple conflict detection - in reality would be more sophisticated
            for i, ob1 in enumerate(obligations):
                for ob2 in obligations[i+1:]:
                    if self._are_conflicting(ob1, ob2):
                        conflict = EthicalConflict(
                            conflicting_concepts=[ob1, ob2],
                            conflict_type="obligation-obligation",
                            severity="medium",
                            description=f"Conflict between '{ob1.label}' and '{ob2.label}'"
                        )
                        conflicts.append(conflict)
        
        # Check principle-obligation conflicts
        principles = concepts_by_type.get("Principle", [])
        for principle in principles:
            for obligation in obligations:
                if self._principle_obligation_conflict(principle, obligation):
                    conflict = EthicalConflict(
                        conflicting_concepts=[principle, obligation],
                        conflict_type="principle-obligation",
                        severity="high",
                        description=f"Principle '{principle.label}' may conflict with obligation '{obligation.label}'"
                    )
                    conflicts.append(conflict)
        
        return conflicts
    
    def _are_conflicting(self, ob1: EthicalConcept, ob2: EthicalConcept) -> bool:
        """Check if two obligations conflict"""
        # Simplified logic - check for opposing keywords
        opposing_pairs = [
            ("disclose", "confidential"),
            ("report", "protect"),
            ("public", "client")
        ]
        
        label1_lower = ob1.label.lower()
        label2_lower = ob2.label.lower()
        
        for word1, word2 in opposing_pairs:
            if (word1 in label1_lower and word2 in label2_lower) or \
               (word2 in label1_lower and word1 in label2_lower):
                return True
        
        return False
    
    def _principle_obligation_conflict(self, 
                                     principle: EthicalConcept,
                                     obligation: EthicalConcept) -> bool:
        """Check if a principle conflicts with an obligation"""
        # Simplified logic
        if "autonomy" in principle.label.lower() and "must" in obligation.label.lower():
            return True
        if "transparency" in principle.label.lower() and "confidential" in obligation.label.lower():
            return True
        return False
    
    async def propose_resolution(self, conflict: EthicalConflict) -> ConflictResolution:
        """Propose a resolution for an ethical conflict"""
        # Simplified resolution strategies
        if conflict.conflict_type == "obligation-obligation":
            # Prioritize public safety
            prioritized = None
            for concept in conflict.conflicting_concepts:
                if "public" in concept.label.lower() or "safety" in concept.label.lower():
                    prioritized = concept
                    break
            
            if prioritized:
                resolution = ConflictResolution(
                    conflict=conflict,
                    resolution_strategy="prioritization",
                    prioritized_concept=prioritized,
                    compromise_solution=None,
                    justification="Public safety takes precedence in professional ethics"
                )
            else:
                resolution = ConflictResolution(
                    conflict=conflict,
                    resolution_strategy="contextual",
                    prioritized_concept=None,
                    compromise_solution="Consider specific context and stakeholder impacts",
                    justification="Resolution depends on specific situational factors"
                )
        else:
            # Principle-obligation conflict
            resolution = ConflictResolution(
                conflict=conflict,
                resolution_strategy="balance",
                prioritized_concept=None,
                compromise_solution="Seek solution that honors principle while meeting obligation",
                justification="Professional ethics requires balancing ideals with duties"
            )
        
        return resolution


class MultiAgentCoordinator:
    """
    Coordinates multiple specialized agents for comprehensive ethical analysis
    """
    
    def __init__(self, mcp_manager=None):
        """
        Initialize the multi-agent coordinator
        
        Args:
            mcp_manager: MCP manager for ontology access
        """
        self.mcp_manager = mcp_manager
        
        # Initialize specialized agents
        self.agents = {
            'principle': PrincipleAgent(mcp_manager),
            'obligation': ObligationAgent(mcp_manager),
            'precedent': PrecedentAgent(mcp_manager),
        }
        
        # Conflict resolution agent is separate
        self.conflict_agent = ConflictResolutionAgent(mcp_manager)
        
        logger.info("Multi-agent coordinator initialized with %d agents", len(self.agents))
    
    async def process(self,
                     query: str,
                     components: Dict[str, List[str]],
                     ontology_context: Dict[str, Any],
                     domain: str = "engineering-ethics") -> Dict[str, Any]:
        """
        Coordinate agent processing with consensus building
        
        Args:
            query: Original user query
            components: Components identified in the query
            ontology_context: Ontological concepts retrieved
            domain: Professional domain
            
        Returns:
            Coordinated analysis from all agents
        """
        start_time = datetime.now()
        
        # Run agent analyses in parallel
        agent_tasks = []
        active_agents = []
        
        for agent_type, agent in self.agents.items():
            # Determine if agent should be activated based on components
            if self._should_activate_agent(agent_type, components):
                task = agent.analyze(
                    query_components=components.get(agent_type, []),
                    ontology_context=ontology_context,
                    domain=domain
                )
                agent_tasks.append(task)
                active_agents.append(agent_type)
                logger.debug(f"Activated {agent_type} agent")
        
        # Wait for all agent analyses
        if agent_tasks:
            agent_results = await asyncio.gather(*agent_tasks)
        else:
            agent_results = []
        
        # Check for conflicts
        conflicts = await self.conflict_agent.identify_conflicts(agent_results)
        
        # Resolve conflicts if any
        resolutions = []
        if conflicts:
            for conflict in conflicts:
                resolution = await self.conflict_agent.propose_resolution(conflict)
                resolutions.append(resolution)
                logger.info(f"Resolved conflict: {conflict.conflict_type}")
        
        # Build consensus
        consensus = self._build_consensus(agent_results, resolutions)
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return {
            'agent_analyses': [self._serialize_analysis(a) for a in agent_results],
            'conflicts_identified': [self._serialize_conflict(c) for c in conflicts],
            'resolutions': [self._serialize_resolution(r) for r in resolutions],
            'consensus': consensus,
            'active_agents': active_agents,
            'processing_time': processing_time
        }
    
    def _should_activate_agent(self, agent_type: str, components: Dict) -> bool:
        """Determine if an agent should be activated"""
        # Activate based on component presence or query patterns
        activation_map = {
            'principle': ['principle', 'value', 'ethical', 'moral'],
            'obligation': ['obligation', 'duty', 'must', 'required', 'shall'],
            'precedent': ['case', 'precedent', 'similar', 'example']
        }
        
        # Check if relevant components are present
        for key in activation_map.get(agent_type, []):
            if key in str(components).lower():
                return True
        
        # Default activation for core agents
        if agent_type in ['principle', 'obligation']:
            return True
        
        return False
    
    def _build_consensus(self, 
                        agent_results: List[AgentAnalysis],
                        resolutions: List[ConflictResolution]) -> Dict[str, Any]:
        """Build consensus from agent analyses and conflict resolutions"""
        
        # Collect all identified concepts
        all_concepts = []
        for analysis in agent_results:
            all_concepts.extend(analysis.concepts_identified)
        
        # Group concepts by type
        concepts_by_type = {}
        for concept in all_concepts:
            type_key = concept.component_type.value
            if type_key not in concepts_by_type:
                concepts_by_type[type_key] = []
            concepts_by_type[type_key].append(concept)
        
        # Build consensus interpretation
        interpretation_parts = []
        
        # Add agent interpretations
        for analysis in agent_results:
            if analysis.confidence > 0.5:  # Only include confident interpretations
                interpretation_parts.append(analysis.interpretation)
        
        # Add conflict resolutions
        if resolutions:
            interpretation_parts.append("\n**Ethical Conflicts Resolved:**")
            for resolution in resolutions:
                if resolution.prioritized_concept:
                    interpretation_parts.append(
                        f"- Prioritized: {resolution.prioritized_concept.label} "
                        f"({resolution.justification})"
                    )
                elif resolution.compromise_solution:
                    interpretation_parts.append(
                        f"- Compromise: {resolution.compromise_solution}"
                    )
        
        # Calculate overall confidence
        if agent_results:
            avg_confidence = sum(a.confidence for a in agent_results) / len(agent_results)
        else:
            avg_confidence = 0.0
        
        return {
            'interpretation': "\n\n".join(interpretation_parts),
            'concepts_by_type': {
                k: [{'label': c.label, 'uri': c.uri} for c in v]
                for k, v in concepts_by_type.items()
            },
            'confidence': avg_confidence,
            'num_conflicts_resolved': len(resolutions)
        }
    
    def _serialize_analysis(self, analysis: AgentAnalysis) -> Dict:
        """Serialize agent analysis for JSON response"""
        return {
            'agent_type': analysis.agent_type,
            'concepts_identified': [
                {
                    'label': c.label,
                    'uri': c.uri,
                    'type': c.component_type.value,
                    'description': c.description
                }
                for c in analysis.concepts_identified
            ],
            'interpretation': analysis.interpretation,
            'confidence': analysis.confidence,
            'reasoning_trace': analysis.reasoning_trace
        }
    
    def _serialize_conflict(self, conflict: EthicalConflict) -> Dict:
        """Serialize ethical conflict for JSON response"""
        return {
            'conflicting_concepts': [
                {'label': c.label, 'type': c.component_type.value}
                for c in conflict.conflicting_concepts
            ],
            'conflict_type': conflict.conflict_type,
            'severity': conflict.severity,
            'description': conflict.description
        }
    
    def _serialize_resolution(self, resolution: ConflictResolution) -> Dict:
        """Serialize conflict resolution for JSON response"""
        result = {
            'resolution_strategy': resolution.resolution_strategy,
            'justification': resolution.justification
        }
        
        if resolution.prioritized_concept:
            result['prioritized_concept'] = {
                'label': resolution.prioritized_concept.label,
                'type': resolution.prioritized_concept.component_type.value
            }
        
        if resolution.compromise_solution:
            result['compromise_solution'] = resolution.compromise_solution
        
        return result
    
    async def get_agent_capabilities(self) -> Dict[str, List[str]]:
        """Get capabilities of all agents"""
        capabilities = {}
        
        for agent_type, agent in self.agents.items():
            agent_caps = []
            
            if agent_type == 'principle':
                agent_caps = [
                    "Identify ethical principles",
                    "Interpret abstract principles in context",
                    "Map principles to professional codes"
                ]
            elif agent_type == 'obligation':
                agent_caps = [
                    "Identify professional obligations",
                    "Check obligation fulfillment",
                    "Prioritize competing obligations"
                ]
            elif agent_type == 'precedent':
                agent_caps = [
                    "Find similar cases",
                    "Extract decision patterns",
                    "Apply precedent-based reasoning"
                ]
            
            capabilities[agent_type] = agent_caps
        
        # Add conflict resolution capabilities
        capabilities['conflict_resolution'] = [
            "Identify ethical conflicts",
            "Propose resolution strategies",
            "Prioritize based on context",
            "Find creative compromises"
        ]
        
        return capabilities
