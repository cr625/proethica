"""
Semantic Router Service for ProEthica

Analyzes user queries to identify relevant ProEthica components (R, P, O, S, Rs, A, E, Ca, Cs)
and generates query execution plans for the orchestrator.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class ComponentType(Enum):
    """ProEthica formal model components."""
    ROLE = "R"  # Professional positions and responsibilities
    PRINCIPLE = "P"  # Abstract ethical foundations
    OBLIGATION = "O"  # Concrete moral requirements
    STATE = "S"  # Environmental conditions
    RESOURCE = "Rs"  # Precedents, codes, guidelines
    ACTION = "A"  # Professional actions and decisions
    EVENT = "E"  # Temporal occurrences triggering ethics
    CAPABILITY = "Ca"  # Agent abilities for ethical reasoning
    CONSTRAINT = "Cs"  # Limitations and boundaries


class ConflictType(Enum):
    """Types of ethical conflicts."""
    ROLE_CONFLICT = "role_conflict"  # Conflicts between different roles
    PRINCIPLE_CONFLICT = "principle_conflict"  # Competing principles
    OBLIGATION_CONFLICT = "obligation_conflict"  # Conflicting duties
    RESOURCE_CONFLICT = "resource_conflict"  # Incompatible precedents
    CONSTRAINT_VIOLATION = "constraint_violation"  # Constraint vs action


@dataclass
class IdentifiedComponent:
    """A component identified in a query."""
    type: ComponentType
    text: str  # The text that triggered this identification
    confidence: float  # Confidence score (0-1)
    entities: List[str] = field(default_factory=list)  # Specific entities mentioned
    relationships: List[str] = field(default_factory=list)  # Related components


@dataclass
class QueryAnalysis:
    """Complete analysis of a user query."""
    original_query: str
    normalized_query: str
    identified_components: List[IdentifiedComponent]
    conflicts: List[ConflictType]
    domain: str = "engineering-ethics"  # Default domain
    query_type: str = "analysis"  # analysis, explanation, comparison, resolution
    confidence: float = 0.0


@dataclass
class QueryStep:
    """A single step in a query execution plan."""
    tool: str
    params: Dict[str, Any]
    depends_on: List[int] = field(default_factory=list)  # Indices of prerequisite steps
    optional: bool = False


@dataclass
class QueryPlan:
    """Execution plan for a query."""
    analysis: QueryAnalysis
    steps: List[QueryStep]
    estimated_time_ms: int = 0
    cache_hits_expected: int = 0


class SemanticRouterService:
    """
    Analyzes queries and routes them to appropriate ProEthica components.
    """
    
    def __init__(self):
        """Initialize the semantic router."""
        self.patterns = self._initialize_patterns()
        self.conflict_patterns = self._initialize_conflict_patterns()
        self.query_type_patterns = self._initialize_query_type_patterns()
        
        # Domain-specific keyword mappings
        self.domain_keywords = {
            "engineering-ethics": ["engineer", "engineering", "technical", "design", "safety", "construction"],
            "medical-ethics": ["medical", "physician", "patient", "healthcare", "clinical", "treatment"],
            "legal-ethics": ["lawyer", "attorney", "legal", "client", "court", "justice"],
            "business-ethics": ["business", "corporate", "company", "profit", "stakeholder", "market"]
        }
        
        logger.info("Semantic Router Service initialized")
    
    def _initialize_patterns(self) -> Dict[ComponentType, List[re.Pattern]]:
        """Initialize regex patterns for each component type."""
        return {
            ComponentType.ROLE: [
                re.compile(r'\b(?:what|which) (?:types? of )?roles?\b', re.IGNORECASE),  # "what roles are available"
                re.compile(r'\b(?:available|defined|existing) roles?\b', re.IGNORECASE),  # "available roles"
                re.compile(r'\broles? (?:are|that are) (?:available|defined|in the)\b', re.IGNORECASE),  # "roles that are available"
                re.compile(r'\b(?:list|show|get|find) (?:the |all )?roles?\b', re.IGNORECASE),  # "list roles"
                re.compile(r'\b(?:role|responsibility|duty|position) of (?:an? )?(\w+)', re.IGNORECASE),
                re.compile(r'\bwhat (?:does|should) (?:an? )?(\w+) do\b', re.IGNORECASE),
                re.compile(r"\b(\w+)'s (?:professional )?(?:obligations?|duties|responsibilities)\b", re.IGNORECASE),
                re.compile(r'\b(?:as an? )(\w+)\b', re.IGNORECASE),
                re.compile(r'\b(\w+) (?:must|should|needs to)\b', re.IGNORECASE)
            ],
            ComponentType.PRINCIPLE: [
                re.compile(r'\b(?:principle|value|ideal|foundation) of (\w+)', re.IGNORECASE),
                re.compile(r'\b(?:ethical|moral) (?:principles?|foundations?|basis|values?)\b', re.IGNORECASE),
                re.compile(r'\b(?:guided by|based on|according to) (?:the )?principle\b', re.IGNORECASE),
                re.compile(r'\b(?:integrity|honesty|justice|fairness|autonomy|beneficence)\b', re.IGNORECASE),
                re.compile(r'\bhold paramount\b', re.IGNORECASE)
            ],
            ComponentType.OBLIGATION: [
                re.compile(r'\b(?:must|should|required to|obligated to|need to) (\w+)', re.IGNORECASE),
                re.compile(r'\b(?:obligations?|duties|requirements?|responsibilities) (?:to|for|regarding) (\w+)', re.IGNORECASE),
                re.compile(r'\bwhat is (?:required|mandatory|obligatory|necessary)\b', re.IGNORECASE),
                re.compile(r'\b(?:duty|obligation) to (\w+)', re.IGNORECASE),
                re.compile(r'\b(?:accountable|responsible) for\b', re.IGNORECASE)
            ],
            ComponentType.STATE: [
                re.compile(r'\b(?:when|if|during|while|under) (?:[\w\s]+) (?:conditions?|circumstances?|situations?)\b', re.IGNORECASE),
                re.compile(r'\bin (?:the )?(?:context|situation|case) (?:of|where)\b', re.IGNORECASE),
                re.compile(r'\b(?:emergency|crisis|normal|routine|exceptional) (?:situation|condition|state)\b', re.IGNORECASE),
                re.compile(r'\b(?:time pressure|resource constraints?|limited information)\b', re.IGNORECASE),
                re.compile(r'\b(?:organizational|institutional|professional) (?:culture|climate|environment)\b', re.IGNORECASE)
            ],
            ComponentType.RESOURCE: [
                re.compile(r'\b(?:according to|based on|per|following) (?:the )?(?:code|standard|guideline|precedent)\b', re.IGNORECASE),
                re.compile(r'\b(?:professional|ethics?) (?:code|standards?|guidelines?|rules?)\b', re.IGNORECASE),
                re.compile(r'\b(?:precedent|case|example|instance) (?:of|from|in)\b', re.IGNORECASE),
                re.compile(r'\b(?:NSPE|AMA|ABA|IEEE) (?:code|standards?|guidelines?)\b', re.IGNORECASE),
                re.compile(r'\b(?:best practices?|standard procedures?|protocols?)\b', re.IGNORECASE)
            ],
            ComponentType.ACTION: [
                re.compile(r'\b(?:action|decision|choice|behavior|conduct) (?:to|of|by)\b', re.IGNORECASE),
                re.compile(r'\b(?:what to do|how to act|course of action)\b', re.IGNORECASE),
                re.compile(r'\b(?:perform|execute|carry out|implement|undertake) (\w+)', re.IGNORECASE),
                re.compile(r'\b(?:refrain from|avoid|prevent|stop) (\w+)', re.IGNORECASE),
                re.compile(r'\b(?:disclose|report|document|communicate|inform)\b', re.IGNORECASE)
            ],
            ComponentType.EVENT: [
                re.compile(r'\b(?:when|after|before|during|upon) (?:[\w\s]+) (?:occurs?|happens?|arises?)\b', re.IGNORECASE),
                re.compile(r'\b(?:incident|event|occurrence|situation) (?:that|which|where)\b', re.IGNORECASE),
                re.compile(r'\b(?:trigger|cause|lead to|result in) (?:ethical|moral)\b', re.IGNORECASE),
                re.compile(r'\b(?:discovery|disclosure|failure|breach|violation)\b', re.IGNORECASE),
                re.compile(r'\b(?:emergency|crisis|accident|mistake|error)\b', re.IGNORECASE)
            ],
            ComponentType.CAPABILITY: [
                re.compile(r'\b(?:ability|capability|competence|skill) (?:to|for|in)\b', re.IGNORECASE),
                re.compile(r'\b(?:qualified|competent|capable|able) to\b', re.IGNORECASE),
                re.compile(r'\b(?:expertise|knowledge|understanding|proficiency) (?:in|of)\b', re.IGNORECASE),
                re.compile(r'\b(?:judgment|reasoning|analysis|evaluation) (?:skills?|abilities?)\b', re.IGNORECASE),
                re.compile(r'\b(?:professional|technical|ethical) (?:competence|expertise)\b', re.IGNORECASE)
            ],
            ComponentType.CONSTRAINT: [
                re.compile(r'\b(?:limitation|constraint|restriction|boundary) (?:on|to|of)\b', re.IGNORECASE),
                re.compile(r'\b(?:cannot|must not|forbidden|prohibited|not allowed)\b', re.IGNORECASE),
                re.compile(r'\b(?:legal|regulatory|policy) (?:requirements?|constraints?|limitations?)\b', re.IGNORECASE),
                re.compile(r'\b(?:budget|time|resource) (?:constraints?|limitations?)\b', re.IGNORECASE),
                re.compile(r'\b(?:confidentiality|privacy|proprietary) (?:requirements?|restrictions?)\b', re.IGNORECASE)
            ]
        }
    
    def _initialize_conflict_patterns(self) -> Dict[ConflictType, List[re.Pattern]]:
        """Initialize patterns for detecting conflicts."""
        return {
            ConflictType.ROLE_CONFLICT: [
                re.compile(r'\b(?:conflict|tension|dilemma) between (?:roles?|positions?)\b', re.IGNORECASE),
                re.compile(r'\b(?:dual|multiple|conflicting) roles?\b', re.IGNORECASE),
                re.compile(r'\bas both (\w+) and (\w+)\b', re.IGNORECASE)
            ],
            ConflictType.PRINCIPLE_CONFLICT: [
                re.compile(r'\b(?:conflict|tension|dilemma|choice) between (?:[\w\s]+) and (?:[\w\s]+)\b', re.IGNORECASE),
                re.compile(r'\b(?:competing|conflicting|incompatible) (?:principles?|values?)\b', re.IGNORECASE),
                re.compile(r'\b(?:balancing|weighing|trading off) (\w+) (?:against|versus|vs\.?) (\w+)\b', re.IGNORECASE)
            ],
            ConflictType.OBLIGATION_CONFLICT: [
                re.compile(r'\b(?:conflicting|competing|incompatible) (?:obligations?|duties|requirements?)\b', re.IGNORECASE),
                re.compile(r'\b(?:duty|obligation) to (\w+) (?:conflicts?|competes?) with (?:duty|obligation) to (\w+)\b', re.IGNORECASE),
                re.compile(r'\bcannot (?:both|simultaneously) (\w+) and (\w+)\b', re.IGNORECASE)
            ],
            ConflictType.RESOURCE_CONFLICT: [
                re.compile(r'\b(?:conflicting|inconsistent|contradictory) (?:guidance|precedents?|standards?)\b', re.IGNORECASE),
                re.compile(r'\b(?:different|varying|contradictory) (?:codes?|standards?|guidelines?)\b', re.IGNORECASE)
            ],
            ConflictType.CONSTRAINT_VIOLATION: [
                re.compile(r'\b(?:violate|breach|exceed|go beyond) (?:constraints?|limitations?|boundaries?)\b', re.IGNORECASE),
                re.compile(r'\b(?:within|outside|beyond) (?:the )?(?:limits?|boundaries?|constraints?)\b', re.IGNORECASE)
            ]
        }
    
    def _initialize_query_type_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Initialize patterns for detecting query types."""
        return {
            "explanation": [
                re.compile(r'\b(?:explain|what is|define|describe|tell me about)\b', re.IGNORECASE),
                re.compile(r'\b(?:meaning|definition|explanation) of\b', re.IGNORECASE)
            ],
            "comparison": [
                re.compile(r'\b(?:compare|contrast|difference|similarity) (?:between|among)\b', re.IGNORECASE),
                re.compile(r'\b(?:versus|vs\.?|compared to|relative to)\b', re.IGNORECASE)
            ],
            "resolution": [
                re.compile(r'\b(?:resolve|solve|address|handle|deal with) (?:the )?(?:conflict|dilemma|problem)\b', re.IGNORECASE),
                re.compile(r'\b(?:what should|how to|best way to|appropriate response)\b', re.IGNORECASE)
            ],
            "analysis": [
                re.compile(r'\b(?:analyze|evaluate|assess|examine|consider)\b', re.IGNORECASE),
                re.compile(r'\b(?:is it|would it be|should) (?:ethical|appropriate|acceptable)\b', re.IGNORECASE)
            ]
        }
    
    def analyze_query(self, query: str) -> QueryAnalysis:
        """
        Analyze a user query to identify ProEthica components and conflicts.
        
        Args:
            query: The user's natural language query
            
        Returns:
            QueryAnalysis with identified components and metadata
        """
        logger.info(f"Analyzing query: {query[:100]}...")
        
        # Normalize the query
        normalized = self._normalize_query(query)
        
        # Identify components
        components = self._identify_components(query)
        
        # Detect conflicts
        conflicts = self._detect_conflicts(query)
        
        # Determine domain
        domain = self._identify_domain(query)
        
        # Determine query type
        query_type = self._identify_query_type(query)
        
        # Calculate overall confidence
        confidence = self._calculate_confidence(components, conflicts)
        
        analysis = QueryAnalysis(
            original_query=query,
            normalized_query=normalized,
            identified_components=components,
            conflicts=conflicts,
            domain=domain,
            query_type=query_type,
            confidence=confidence
        )
        
        logger.info(f"Query analysis complete: {len(components)} components, {len(conflicts)} conflicts identified")
        return analysis
    
    def _normalize_query(self, query: str) -> str:
        """Normalize a query for processing."""
        # Remove extra whitespace
        normalized = ' '.join(query.split())
        # Lowercase for comparison
        normalized = normalized.lower()
        return normalized
    
    def _identify_components(self, query: str) -> List[IdentifiedComponent]:
        """Identify ProEthica components in the query."""
        components = []
        
        for comp_type, patterns in self.patterns.items():
            for pattern in patterns:
                matches = pattern.finditer(query)
                for match in matches:
                    text = match.group(0)
                    entities = [g for g in match.groups() if g]
                    
                    # Calculate confidence based on match quality
                    confidence = self._calculate_match_confidence(match, query)
                    
                    component = IdentifiedComponent(
                        type=comp_type,
                        text=text,
                        confidence=confidence,
                        entities=entities
                    )
                    
                    # Avoid duplicates
                    if not self._is_duplicate_component(component, components):
                        components.append(component)
        
        # Sort by confidence
        components.sort(key=lambda x: x.confidence, reverse=True)
        
        return components
    
    def _detect_conflicts(self, query: str) -> List[ConflictType]:
        """Detect ethical conflicts in the query."""
        conflicts = []
        
        for conflict_type, patterns in self.conflict_patterns.items():
            for pattern in patterns:
                if pattern.search(query):
                    if conflict_type not in conflicts:
                        conflicts.append(conflict_type)
        
        return conflicts
    
    def _identify_domain(self, query: str) -> str:
        """Identify the professional domain from the query."""
        query_lower = query.lower()
        
        for domain, keywords in self.domain_keywords.items():
            for keyword in keywords:
                if keyword in query_lower:
                    return domain
        
        # Default to engineering ethics
        return "engineering-ethics"
    
    def _identify_query_type(self, query: str) -> str:
        """Identify the type of query."""
        for query_type, patterns in self.query_type_patterns.items():
            for pattern in patterns:
                if pattern.search(query):
                    return query_type
        
        # Default to analysis
        return "analysis"
    
    def _calculate_match_confidence(self, match: re.Match, query: str) -> float:
        """Calculate confidence score for a pattern match."""
        # Base confidence
        confidence = 0.5
        
        # Boost for exact word boundaries
        if match.group(0) == match.group(0).strip():
            confidence += 0.1
        
        # Boost for match at beginning of query
        if match.start() < 10:
            confidence += 0.1
        
        # Boost for longer matches
        match_length = len(match.group(0))
        if match_length > 10:
            confidence += min(0.2, match_length / 50)
        
        # Boost for matches with captured groups
        if match.groups():
            confidence += 0.1
        
        return min(1.0, confidence)
    
    def _calculate_confidence(self, components: List[IdentifiedComponent], conflicts: List[ConflictType]) -> float:
        """Calculate overall confidence for the analysis."""
        if not components:
            return 0.0
        
        # Average component confidence
        avg_confidence = sum(c.confidence for c in components) / len(components)
        
        # Boost for identified conflicts (they add clarity)
        if conflicts:
            avg_confidence = min(1.0, avg_confidence + 0.1)
        
        # Boost for multiple component types
        unique_types = len(set(c.type for c in components))
        if unique_types > 2:
            avg_confidence = min(1.0, avg_confidence + 0.1)
        
        return avg_confidence
    
    def _is_duplicate_component(self, component: IdentifiedComponent, existing: List[IdentifiedComponent]) -> bool:
        """Check if a component is a duplicate of an existing one."""
        for existing_comp in existing:
            if (existing_comp.type == component.type and 
                existing_comp.text == component.text):
                return True
            # Check for overlapping text
            if (existing_comp.type == component.type and
                (component.text in existing_comp.text or existing_comp.text in component.text)):
                # Keep the longer match
                if len(component.text) <= len(existing_comp.text):
                    return True
        return False
    
    def generate_query_plan(self, analysis: QueryAnalysis) -> QueryPlan:
        """
        Generate an execution plan based on query analysis.
        
        Args:
            analysis: The analyzed query
            
        Returns:
            QueryPlan with ordered execution steps
        """
        logger.info(f"Generating query plan for {analysis.query_type} query")
        
        steps = []
        
        # Generate steps based on identified components
        for i, component in enumerate(analysis.identified_components):
            step = self._create_step_for_component(component, analysis.domain)
            if step:
                steps.append(step)
        
        # Add conflict resolution steps if needed
        if analysis.conflicts:
            conflict_steps = self._create_conflict_resolution_steps(analysis.conflicts, analysis.domain)
            steps.extend(conflict_steps)
        
        # Add query-type specific steps
        type_steps = self._create_query_type_steps(analysis.query_type, analysis)
        steps.extend(type_steps)
        
        # Optimize and order steps
        steps = self._optimize_steps(steps)
        
        # Estimate execution time
        estimated_time = self._estimate_execution_time(steps)
        
        plan = QueryPlan(
            analysis=analysis,
            steps=steps,
            estimated_time_ms=estimated_time
        )
        
        logger.info(f"Query plan generated with {len(steps)} steps")
        return plan
    
    def _create_step_for_component(self, component: IdentifiedComponent, domain: str) -> Optional[QueryStep]:
        """Create an execution step for a component."""
        if component.confidence < 0.3:
            return None
        
        params = {
            "category": component.type.name.capitalize(),
            "domain_id": domain
        }
        
        # Add entity filter if specific entities were identified
        if component.entities:
            params["filter"] = component.entities[0]
        
        return QueryStep(
            tool="get_entities_by_category",
            params=params
        )
    
    def _create_conflict_resolution_steps(self, conflicts: List[ConflictType], domain: str) -> List[QueryStep]:
        """Create steps to resolve identified conflicts."""
        steps = []
        
        for conflict in conflicts:
            if conflict == ConflictType.PRINCIPLE_CONFLICT:
                # Get principles and their priorities
                steps.append(QueryStep(
                    tool="get_entities_by_category",
                    params={"category": "Principle", "domain_id": domain}
                ))
            elif conflict == ConflictType.OBLIGATION_CONFLICT:
                # Get obligations and precedence rules
                steps.append(QueryStep(
                    tool="get_entities_by_category",
                    params={"category": "Obligation", "domain_id": domain}
                ))
            # Add SPARQL query for relationships
            steps.append(QueryStep(
                tool="sparql_query",
                params={
                    "query": f"SELECT ?s ?p ?o WHERE {{ ?s ?p ?o . FILTER(regex(str(?p), 'conflict|precedence|priority')) }}",
                    "domain_id": domain
                }
            ))
        
        return steps
    
    def _create_query_type_steps(self, query_type: str, analysis: QueryAnalysis) -> List[QueryStep]:
        """Create steps specific to the query type."""
        steps = []
        
        if query_type == "comparison":
            # Need to get entities from multiple categories or domains
            for component in analysis.identified_components:
                steps.append(QueryStep(
                    tool="get_entities_by_category",
                    params={
                        "category": component.type.name.capitalize(),
                        "domain_id": analysis.domain,
                        "include_relationships": True
                    }
                ))
        elif query_type == "explanation":
            # Get detailed information about specific concepts
            if analysis.identified_components:
                main_component = analysis.identified_components[0]
                steps.append(QueryStep(
                    tool="sparql_query",
                    params={
                        "query": f"SELECT ?s ?p ?o WHERE {{ ?s rdfs:label ?label . FILTER(regex(?label, '{main_component.text}', 'i')) . ?s ?p ?o }}",
                        "domain_id": analysis.domain
                    }
                ))
        
        return steps
    
    def _optimize_steps(self, steps: List[QueryStep]) -> List[QueryStep]:
        """Optimize and deduplicate query steps."""
        # Remove exact duplicates
        unique_steps = []
        seen = set()
        
        for step in steps:
            step_key = (step.tool, json.dumps(step.params, sort_keys=True))
            if step_key not in seen:
                seen.add(step_key)
                unique_steps.append(step)
        
        # Order steps by dependency
        # (Simple ordering for now - can be enhanced with topological sort)
        return unique_steps
    
    def _estimate_execution_time(self, steps: List[QueryStep]) -> int:
        """Estimate execution time in milliseconds."""
        base_time = 100  # Base overhead
        
        time_per_tool = {
            "get_entities_by_category": 50,
            "sparql_query": 200,
            "get_domain_info": 30
        }
        
        total_time = base_time
        for step in steps:
            total_time += time_per_tool.get(step.tool, 100)
        
        return total_time
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get router statistics."""
        return {
            "component_patterns": {k.name: len(v) for k, v in self.patterns.items()},
            "conflict_patterns": {k.name: len(v) for k, v in self.conflict_patterns.items()},
            "supported_domains": list(self.domain_keywords.keys()),
            "query_types": list(self.query_type_patterns.keys())
        }


# Example usage and testing
if __name__ == "__main__":
    # Set up logging for testing
    logging.basicConfig(level=logging.INFO)
    
    # Initialize router
    router = SemanticRouterService()
    
    # Test queries
    test_queries = [
        "What are the obligations of an engineer when safety conflicts with client demands?",
        "Explain the principle of informed consent in medical ethics",
        "Compare engineering ethics with legal ethics regarding confidentiality",
        "As a manager, what should I do when I discover a safety violation?",
        "What constraints apply to sharing proprietary information?"
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print('='*60)
        
        # Analyze query
        analysis = router.analyze_query(query)
        
        print(f"Domain: {analysis.domain}")
        print(f"Query Type: {analysis.query_type}")
        print(f"Confidence: {analysis.confidence:.2f}")
        
        print("\nIdentified Components:")
        for comp in analysis.identified_components:
            print(f"  - {comp.type.name}: '{comp.text}' (confidence: {comp.confidence:.2f})")
            if comp.entities:
                print(f"    Entities: {comp.entities}")
        
        if analysis.conflicts:
            print("\nConflicts Detected:")
            for conflict in analysis.conflicts:
                print(f"  - {conflict.name}")
        
        # Generate plan
        plan = router.generate_query_plan(analysis)
        
        print(f"\nExecution Plan ({len(plan.steps)} steps, ~{plan.estimated_time_ms}ms):")
        for i, step in enumerate(plan.steps, 1):
            print(f"  {i}. {step.tool}: {step.params}")
