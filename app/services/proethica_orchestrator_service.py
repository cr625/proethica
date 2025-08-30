"""
ProEthica Orchestrator Service

Coordinates between the semantic router, MCP server, and LLM orchestrator
to provide ontology-aware ethical reasoning.
"""

import os
import sys
import logging
import asyncio
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import time

# Add shared path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
onto_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
shared_path = os.path.join(onto_root, 'shared')
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

from app.services.semantic_router_service import (
    SemanticRouterService, 
    QueryAnalysis, 
    QueryPlan,
    ComponentType
)

try:
    from llm_orchestration.core.orchestrator import get_llm_orchestrator, OrchestratorConfig
    from llm_orchestration.integrations.mcp_context import MCPContextManager
    SHARED_ORCHESTRATOR_AVAILABLE = True
except ImportError:
    SHARED_ORCHESTRATOR_AVAILABLE = False
    logging.warning("Shared orchestrator not available - will use fallback mode")

logger = logging.getLogger(__name__)


@dataclass
class OntologyContext:
    """Context retrieved from ontology for a query."""
    query_analysis: QueryAnalysis
    retrieved_entities: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    sparql_results: List[Dict[str, Any]] = field(default_factory=list)
    relevant_resources: List[Dict[str, Any]] = field(default_factory=list)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    retrieval_time_ms: int = 0
    cache_hits: int = 0


@dataclass
class EnrichedPrompt:
    """LLM prompt enriched with ontological context."""
    original_query: str
    system_prompt: str
    context_section: str
    user_prompt: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestratedResponse:
    """Response from orchestrated reasoning."""
    response_text: str
    ontology_context: OntologyContext
    reasoning_steps: List[str] = field(default_factory=list)
    citations: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    processing_time_ms: int = 0


class ProEthicaOrchestratorService:
    """
    Orchestrates ontology-aware ethical reasoning by coordinating
    between the semantic router, MCP server, and LLM.
    """
    
    def __init__(self, mcp_server_url: Optional[str] = None):
        """
        Initialize the ProEthica orchestrator.
        
        Args:
            mcp_server_url: URL of the OntServe MCP server
        """
        # Initialize semantic router
        self.semantic_router = SemanticRouterService()
        
        # MCP server configuration
        self.mcp_server_url = mcp_server_url or os.environ.get(
            "ONTSERVE_MCP_URL", 
            "http://localhost:8082"
        )
        
        # Initialize MCP context manager if available
        self.mcp_manager = None
        if SHARED_ORCHESTRATOR_AVAILABLE:
            try:
                self.mcp_manager = MCPContextManager(self.mcp_server_url)
                logger.info(f"MCP context manager initialized: {self.mcp_server_url}")
            except Exception as e:
                logger.error(f"Failed to initialize MCP manager: {e}")
        
        # Cache for ontology entities
        self._entity_cache: Dict[str, Tuple[Any, float]] = {}
        self._cache_ttl = 300  # 5 minutes
        
        # ProEthica formal model component mapping
        self.component_category_map = {
            ComponentType.ROLE: "Role",
            ComponentType.PRINCIPLE: "Principle",
            ComponentType.OBLIGATION: "Obligation",
            ComponentType.STATE: "State",
            ComponentType.RESOURCE: "Resource",
            ComponentType.ACTION: "Action",
            ComponentType.EVENT: "Event",
            ComponentType.CAPABILITY: "Capability",
            ComponentType.CONSTRAINT: "Constraint"
        }
        
        logger.info("ProEthica Orchestrator Service initialized")
    
    async def process_query(self, 
                           query: str,
                           domain: str = "engineering-ethics",
                           use_cache: bool = True) -> OrchestratedResponse:
        """
        Process a query with full ontology-aware orchestration.
        
        Args:
            query: User's natural language query
            domain: Professional domain
            use_cache: Whether to use cached entities
            
        Returns:
            Orchestrated response with ontological grounding
        """
        start_time = time.time()
        
        logger.info(f"Processing query: {query[:100]}...")
        
        # Step 1: Analyze query with semantic router
        analysis = self.semantic_router.analyze_query(query)
        if domain:
            analysis.domain = domain
        
        # Step 2: Generate query plan
        plan = self.semantic_router.generate_query_plan(analysis)
        
        # Step 3: Execute query plan to get ontology context
        context = await self.execute_query_plan(plan, use_cache)
        
        # Step 4: Enrich prompt with ontology context
        enriched_prompt = self.enrich_prompt(query, context)
        
        # Step 5: Send to LLM with enriched context
        llm_response = await self.coordinate_reasoning(query, context, enriched_prompt)
        
        # Step 6: Extract citations and structure response
        response = self._structure_response(llm_response, context)
        
        # Calculate processing time
        processing_time = int((time.time() - start_time) * 1000)
        response.processing_time_ms = processing_time
        
        logger.info(f"Query processed in {processing_time}ms")
        return response
    
    async def execute_query_plan(self, 
                                plan: QueryPlan,
                                use_cache: bool = True) -> OntologyContext:
        """
        Execute a query plan by calling MCP tools.
        
        Args:
            plan: Query execution plan
            use_cache: Whether to use cached entities
            
        Returns:
            Ontology context with retrieved entities
        """
        start_time = time.time()
        context = OntologyContext(query_analysis=plan.analysis)
        cache_hits = 0
        
        # Execute each step in the plan
        for step in plan.steps:
            try:
                # Check cache first
                cache_key = self._get_cache_key(step.tool, step.params)
                
                if use_cache and cache_key in self._entity_cache:
                    cached_data, cached_time = self._entity_cache[cache_key]
                    if time.time() - cached_time < self._cache_ttl:
                        result = cached_data
                        cache_hits += 1
                        logger.debug(f"Cache hit for {step.tool}")
                    else:
                        # Cache expired
                        del self._entity_cache[cache_key]
                        result = await self._execute_mcp_tool(step.tool, step.params)
                else:
                    result = await self._execute_mcp_tool(step.tool, step.params)
                
                # Cache the result
                if use_cache and result:
                    self._entity_cache[cache_key] = (result, time.time())
                
                # Store results by type
                if step.tool == "get_entities_by_category":
                    category = step.params.get("category", "Unknown")
                    if category not in context.retrieved_entities:
                        context.retrieved_entities[category] = []
                    if isinstance(result, dict) and "entities" in result:
                        context.retrieved_entities[category].extend(result["entities"])
                
                elif step.tool == "sparql_query":
                    if isinstance(result, dict):
                        context.sparql_results.append(result)
                
            except Exception as e:
                logger.error(f"Error executing step {step.tool}: {e}")
                continue
        
        # Calculate retrieval time
        context.retrieval_time_ms = int((time.time() - start_time) * 1000)
        context.cache_hits = cache_hits
        
        logger.info(f"Executed {len(plan.steps)} steps in {context.retrieval_time_ms}ms ({cache_hits} cache hits)")
        return context
    
    async def _execute_mcp_tool(self, tool: str, params: Dict[str, Any]) -> Any:
        """
        Execute an MCP tool call.
        
        Args:
            tool: Tool name
            params: Tool parameters
            
        Returns:
            Tool execution result
        """
        if not self.mcp_manager:
            logger.warning("MCP manager not available, returning mock data")
            return self._get_mock_data(tool, params)
        
        try:
            # Map tool to MCP method
            if tool == "get_entities_by_category":
                result = await self.mcp_manager.get_entities_by_category(
                    category=params.get("category"),
                    domain_id=params.get("domain_id", "engineering-ethics"),
                    status=params.get("status", "approved")
                )
            elif tool == "sparql_query":
                result = await self.mcp_manager.execute_sparql_query(
                    query=params.get("query"),
                    domain_id=params.get("domain_id", "engineering-ethics")
                )
            elif tool == "get_domain_info":
                result = await self.mcp_manager.get_domain_info(
                    domain_id=params.get("domain_id", "engineering-ethics")
                )
            else:
                logger.warning(f"Unknown tool: {tool}")
                result = None
            
            return result
            
        except Exception as e:
            logger.error(f"MCP tool execution failed: {e}")
            return self._get_mock_data(tool, params)
    
    def _get_mock_data(self, tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get mock data for testing when MCP is unavailable.
        
        Args:
            tool: Tool name
            params: Tool parameters
            
        Returns:
            Mock data response
        """
        if tool == "get_entities_by_category":
            category = params.get("category", "Role")
            
            mock_entities = {
                "Role": [
                    {
                        "uri": "http://proethica.org/ontology/engineering-ethics#EngineerRole",
                        "label": "Engineer Role",
                        "description": "A professional engineer with responsibilities to public safety and client service"
                    }
                ],
                "Principle": [
                    {
                        "uri": "http://proethica.org/ontology/engineering-ethics#PublicWelfare",
                        "label": "Hold Paramount Public Welfare",
                        "description": "Engineers must hold paramount the safety, health, and welfare of the public"
                    }
                ],
                "Obligation": [
                    {
                        "uri": "http://proethica.org/ontology/engineering-ethics#SafetyObligation",
                        "label": "Safety Obligation",
                        "description": "Obligation to ensure safety in all engineering work"
                    }
                ]
            }
            
            return {
                "entities": mock_entities.get(category, []),
                "category": category,
                "domain_id": params.get("domain_id"),
                "total_count": len(mock_entities.get(category, []))
            }
        
        return {"mock": True, "tool": tool, "params": params}
    
    def enrich_prompt(self, query: str, context: OntologyContext) -> EnrichedPrompt:
        """
        Enrich an LLM prompt with ontological context.
        
        Args:
            query: Original user query
            context: Ontology context
            
        Returns:
            Enriched prompt with context
        """
        # Build context section
        context_parts = []
        
        # Add identified components
        if context.query_analysis.identified_components:
            context_parts.append("## Identified Components:")
            for comp in context.query_analysis.identified_components:
                context_parts.append(f"- {comp.type.name}: {comp.text}")
        
        # Add retrieved entities
        if context.retrieved_entities:
            context_parts.append("\n## Relevant Ontological Concepts:")
            for category, entities in context.retrieved_entities.items():
                if entities:
                    context_parts.append(f"\n### {category}:")
                    for entity in entities[:3]:  # Limit to top 3 per category
                        label = entity.get("label", "Unknown")
                        desc = entity.get("description", "")
                        context_parts.append(f"- **{label}**: {desc}")
        
        # Add conflicts if detected
        if context.query_analysis.conflicts:
            context_parts.append("\n## Ethical Conflicts Detected:")
            for conflict in context.query_analysis.conflicts:
                context_parts.append(f"- {conflict.value}")
        
        context_section = "\n".join(context_parts)
        
        # Build system prompt
        system_prompt = self._get_system_prompt(context.query_analysis.domain)
        
        # Build user prompt
        user_prompt = f"""Based on the ontological context provided, please answer the following query:

{query}

Consider the formal ProEthica model components identified and provide a response that:
1. References specific ontological concepts where relevant
2. Addresses any ethical conflicts identified
3. Provides grounded, traceable ethical reasoning
4. Cites specific principles, obligations, or precedents as appropriate
"""
        
        return EnrichedPrompt(
            original_query=query,
            system_prompt=system_prompt,
            context_section=context_section,
            user_prompt=user_prompt,
            metadata={
                "domain": context.query_analysis.domain,
                "query_type": context.query_analysis.query_type,
                "confidence": context.query_analysis.confidence
            }
        )
    
    def _get_system_prompt(self, domain: str) -> str:
        """Get domain-specific system prompt."""
        base_prompt = """You are an AI assistant with expertise in professional ethics, specifically trained on ProEthica's formal ontology model D = (R, P, O, S, Rs, A, E, Ca, Cs).

Components:
- R (Roles): Professional positions and responsibilities
- P (Principles): Abstract ethical foundations
- O (Obligations): Concrete moral requirements
- S (States): Environmental conditions
- Rs (Resources): Precedents, codes, guidelines
- A (Actions): Professional decisions
- E (Events): Temporal triggers
- Ca (Capabilities): Agent abilities
- Cs (Constraints): Limitations

When answering questions:
1. Ground your reasoning in the provided ontological context
2. Reference specific concepts by name
3. Apply extensional definition through precedents
4. Address ethical conflicts systematically
5. Provide traceable, professional reasoning
"""
        
        domain_specific = {
            "engineering-ethics": "\n\nDomain: Engineering Ethics\nKey Reference: NSPE Code of Ethics\nCore Principle: Hold paramount the safety, health, and welfare of the public",
            "medical-ethics": "\n\nDomain: Medical Ethics\nKey Principles: Autonomy, Beneficence, Non-maleficence, Justice\nCore Framework: Beauchamp & Childress",
            "legal-ethics": "\n\nDomain: Legal Ethics\nKey Reference: ABA Model Rules\nCore Duties: Confidentiality, Competence, Zealous Advocacy within bounds of law",
            "business-ethics": "\n\nDomain: Business Ethics\nKey Concepts: Stakeholder theory, Corporate responsibility\nCore Balance: Profit and social responsibility"
        }
        
        return base_prompt + domain_specific.get(domain, "")
    
    async def coordinate_reasoning(self, 
                                 query: str,
                                 context: OntologyContext,
                                 enriched_prompt: EnrichedPrompt) -> str:
        """
        Coordinate LLM reasoning with enriched context.
        
        Args:
            query: Original query
            context: Ontology context
            enriched_prompt: Enriched prompt
            
        Returns:
            LLM response text
        """
        if not SHARED_ORCHESTRATOR_AVAILABLE:
            logger.warning("Shared orchestrator not available, using mock response")
            return self._get_mock_llm_response(query, context)
        
        try:
            # Get the shared orchestrator
            orchestrator = get_llm_orchestrator()
            
            # Build full prompt
            full_prompt = f"{enriched_prompt.context_section}\n\n{enriched_prompt.user_prompt}"
            
            # Send to LLM with system prompt
            response = await orchestrator.send_message(
                message=full_prompt,
                system_prompt=enriched_prompt.system_prompt,
                preferred_provider="anthropic",
                temperature=0.7,
                max_tokens=2048
            )
            
            return response.content
            
        except Exception as e:
            logger.error(f"LLM orchestration failed: {e}")
            return self._get_mock_llm_response(query, context)
    
    def _get_mock_llm_response(self, query: str, context: OntologyContext) -> str:
        """Generate mock LLM response for testing."""
        components = [c.type.name for c in context.query_analysis.identified_components]
        
        response = f"""Based on the ProEthica ontological analysis of your query, I can identify the following ethical considerations:

**Identified Components:** {', '.join(components)}

**Domain:** {context.query_analysis.domain}

**Analysis:**
Your query involves important ethical considerations within professional practice. The formal ProEthica model helps us understand this through its structured components.

"""
        
        if "Role" in components:
            response += "The professional role identified carries specific obligations and responsibilities as defined in the relevant professional code.\n\n"
        
        if "Obligation" in components:
            response += "The obligations mentioned are concrete moral requirements that professionals must fulfill in their practice.\n\n"
        
        if context.query_analysis.conflicts:
            response += f"**Ethical Conflicts:** This scenario involves competing ethical considerations that require careful balancing.\n\n"
        
        response += "This analysis is based on the ProEthica formal model and would be enhanced with actual ontological data in a production environment."
        
        return response
    
    def _structure_response(self, 
                          llm_response: str,
                          context: OntologyContext) -> OrchestratedResponse:
        """
        Structure the final response with citations and metadata.
        
        Args:
            llm_response: Raw LLM response
            context: Ontology context
            
        Returns:
            Structured orchestrated response
        """
        # Extract citations from context
        citations = []
        for category, entities in context.retrieved_entities.items():
            for entity in entities:
                citations.append({
                    "type": category,
                    "label": entity.get("label"),
                    "uri": entity.get("uri"),
                    "description": entity.get("description")
                })
        
        # Build reasoning steps
        reasoning_steps = [
            f"1. Analyzed query to identify {len(context.query_analysis.identified_components)} ProEthica components",
            f"2. Retrieved {sum(len(e) for e in context.retrieved_entities.values())} relevant ontological entities",
            f"3. Enriched prompt with domain-specific context for {context.query_analysis.domain}",
            "4. Coordinated LLM reasoning with ontological grounding",
            "5. Structured response with citations and traceability"
        ]
        
        response = OrchestratedResponse(
            response_text=llm_response,
            ontology_context=context,
            reasoning_steps=reasoning_steps,
            citations=citations,
            confidence=context.query_analysis.confidence
        )
        
        return response
    
    def _get_cache_key(self, tool: str, params: Dict[str, Any]) -> str:
        """Generate cache key for tool call."""
        return f"{tool}:{json.dumps(params, sort_keys=True)}"
    
    def clear_cache(self):
        """Clear the entity cache."""
        self._entity_cache.clear()
        logger.info("Entity cache cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        return {
            "cache_size": len(self._entity_cache),
            "cache_ttl": self._cache_ttl,
            "mcp_available": self.mcp_manager is not None,
            "mcp_server_url": self.mcp_server_url,
            "shared_orchestrator_available": SHARED_ORCHESTRATOR_AVAILABLE,
            "router_stats": self.semantic_router.get_statistics()
        }
