"""
Enhanced Engineering Ethics adapter with MCP-Ontology integration.

This enhanced adapter uses the MCP server to access 122 ontological entities across
9 ProEthica categories, replacing pattern-matching with intelligent extraction
guided by formal ontology and validated through semantic similarity.
"""

import re
import asyncio
from typing import Dict, List, Any, Optional, Tuple
import logging
from dataclasses import asdict

from .engineering_ethics_adapter import EngineeringEthicsAdapter
from .data_models import (
    Stakeholder, StakeholderRole, EthicalDecisionPoint, DecisionType, 
    DecisionOption, ReasoningChain, ReasoningStep
)

# Import MCP integration
from shared.llm_orchestration.core.orchestrator import get_llm_orchestrator
from shared.llm_orchestration.providers import GenerationRequest, GenerationResponse, Conversation, Message

logger = logging.getLogger(__name__)


class EnhancedEngineeringEthicsAdapter(EngineeringEthicsAdapter):
    """
    Enhanced NSPE Engineering Ethics adapter with MCP-Ontology integration.
    
    Extends the base engineering ethics adapter with:
    - Ontology-guided entity extraction using 122 formal entities
    - LLM-powered analysis with ontological context  
    - Semantic validation against known entities
    - Multi-pass extraction with cross-validation
    - Enhanced confidence scoring based on ontological alignment
    """
    
    def __init__(self):
        super().__init__()
        self.adapter_name = "enhanced_engineering_ethics"
        self.version = "2.0"
        
        # Initialize MCP integration
        self.mcp_manager = None
        self.llm_orchestrator = None
        self._initialize_mcp_integration()
        
        # ProEthica 9-category mapping to ontology categories
        self.proethica_categories = [
            "Role", "Principle", "Obligation", "State",
            "Resource", "Action", "Event", "Capability", "Constraint"
        ]
        
        # Enhanced confidence thresholds
        self.confidence_thresholds = {
            'ontology_alignment': 0.8,
            'semantic_similarity': 0.75,
            'cross_validation': 0.7,
            'llm_confidence': 0.8
        }
        
        logger.info("Enhanced Engineering Ethics Adapter initialized with MCP integration")
    
    def _initialize_mcp_integration(self):
        """Initialize MCP context manager and LLM orchestrator."""
        try:
            from shared.llm_orchestration.integrations.mcp_context import get_mcp_context_manager
            self.mcp_manager = get_mcp_context_manager()
            self.llm_orchestrator = get_llm_orchestrator()
            logger.info("MCP integration initialized successfully")
        except Exception as e:
            logger.warning(f"MCP integration initialization failed: {e}")
            logger.warning("Falling back to base adapter functionality")
    
    def extract_stakeholders(self, case_content: Dict[str, Any]) -> List[Stakeholder]:
        """Enhanced stakeholder extraction using ontology-guided analysis."""
        try:
            if self.mcp_manager:
                # Check if event loop is already running
                try:
                    loop = asyncio.get_running_loop()
                    # If we're in an event loop, create a task instead
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(self._run_async_stakeholder_extraction, case_content)
                        return future.result()
                except RuntimeError:
                    # No event loop running, safe to use asyncio.run
                    return asyncio.run(self._extract_stakeholders_with_ontology(case_content))
            else:
                logger.info("Using fallback stakeholder extraction")
                return super().extract_stakeholders(case_content)
        except Exception as e:
            logger.error(f"Enhanced stakeholder extraction failed: {e}")
            logger.info("Falling back to base extraction")
            return super().extract_stakeholders(case_content)

    def _run_async_stakeholder_extraction(self, case_content: Dict[str, Any]) -> List[Stakeholder]:
        """Helper method to run async stakeholder extraction in a new event loop."""
        return asyncio.run(self._extract_stakeholders_with_ontology(case_content))
    
    async def _extract_stakeholders_with_ontology(self, case_content: Dict[str, Any]) -> List[Stakeholder]:
        """Extract stakeholders using ontological guidance and LLM analysis."""
        
        # Step 1: Get Role entities from ontology for context
        role_entities = await self.mcp_manager.get_entities_by_category(
            category="Role",
            domain_id="engineering-ethics",
            status="approved"
        )
        
        case_text = self._get_case_text(case_content)
        
        # Step 2: Use LLM with ontological context for stakeholder extraction
        stakeholder_prompt = self._build_stakeholder_extraction_prompt(case_text, role_entities)
        
        try:
            llm_response = await self._get_llm_response(stakeholder_prompt)
            extracted_stakeholders = self._parse_stakeholder_response(llm_response)
            
            # Step 3: Validate and enrich with ontological alignment
            validated_stakeholders = await self._validate_stakeholders_with_ontology(
                extracted_stakeholders, role_entities
            )
            
            # Step 4: Convert to Stakeholder objects with enhanced confidence
            stakeholders = []
            for stakeholder_data in validated_stakeholders:
                stakeholder = self._create_enhanced_stakeholder(stakeholder_data)
                stakeholders.append(stakeholder)
            
            logger.info(f"Enhanced extraction found {len(stakeholders)} stakeholders")
            return stakeholders[:8]  # Limit to top 8 stakeholders
            
        except Exception as e:
            logger.error(f"LLM stakeholder extraction failed: {e}")
            # Fall back to base pattern matching
            return super().extract_stakeholders(case_content)
    
    def identify_ethical_decision_points(self, case_content: Dict[str, Any]) -> List[EthicalDecisionPoint]:
        """Enhanced ethical decision point identification using ontological context."""
        try:
            if self.mcp_manager:
                # Check if event loop is already running
                try:
                    loop = asyncio.get_running_loop()
                    # If we're in an event loop, create a task instead
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(self._run_async_decision_extraction, case_content)
                        return future.result()
                except RuntimeError:
                    # No event loop running, safe to use asyncio.run
                    return asyncio.run(self._identify_decision_points_with_ontology(case_content))
            else:
                logger.info("Using fallback decision point identification")
                return super().identify_ethical_decision_points(case_content)
        except Exception as e:
            logger.error(f"Enhanced decision point identification failed: {e}")
            return super().identify_ethical_decision_points(case_content)

    def _run_async_decision_extraction(self, case_content: Dict[str, Any]) -> List[EthicalDecisionPoint]:
        """Helper method to run async decision extraction in a new event loop."""
        return asyncio.run(self._identify_decision_points_with_ontology(case_content))
    
    async def _identify_decision_points_with_ontology(self, case_content: Dict[str, Any]) -> List[EthicalDecisionPoint]:
        """Identify decision points using ontological guidance and multi-category analysis."""
        
        # Step 1: Get relevant ontological entities for context
        ontology_context = await self._gather_ontology_context()
        
        case_text = self._get_case_text(case_content)
        questions_text = self._get_section_text(case_content, 'question')
        
        # Step 2: Use LLM with full ontological context for decision extraction
        if questions_text:
            decision_points = await self._extract_interactive_decisions_with_ontology(
                questions_text, case_text, ontology_context, case_content
            )
        else:
            decision_points = await self._extract_general_decisions_with_ontology(
                case_text, ontology_context
            )
        
        logger.info(f"Enhanced extraction found {len(decision_points)} decision points")
        return decision_points
    
    def extract_reasoning_chain(self, case_content: Dict[str, Any]) -> ReasoningChain:
        """Enhanced reasoning chain extraction with ontological validation."""
        try:
            if self.mcp_manager:
                # Check if event loop is already running
                try:
                    loop = asyncio.get_running_loop()
                    # If we're in an event loop, create a task instead
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(self._run_async_reasoning_extraction, case_content)
                        return future.result()
                except RuntimeError:
                    # No event loop running, safe to use asyncio.run
                    return asyncio.run(self._extract_reasoning_with_ontology(case_content))
            else:
                return super().extract_reasoning_chain(case_content)
        except Exception as e:
            logger.error(f"Enhanced reasoning extraction failed: {e}")
            return super().extract_reasoning_chain(case_content)

    def _run_async_reasoning_extraction(self, case_content: Dict[str, Any]) -> ReasoningChain:
        """Helper method to run async reasoning extraction in a new event loop."""
        return asyncio.run(self._extract_reasoning_with_ontology(case_content))
    
    async def _extract_reasoning_with_ontology(self, case_content: Dict[str, Any]) -> ReasoningChain:
        """Extract reasoning chain using ontological principles and structured analysis."""
        
        # Get Principle and Obligation entities for reasoning context
        principles = await self.mcp_manager.get_entities_by_category("Principle", "engineering-ethics")
        obligations = await self.mcp_manager.get_entities_by_category("Obligation", "engineering-ethics")
        
        case_text = self._get_case_text(case_content)
        discussion_text = self._get_section_text(case_content, 'discussion')
        conclusion_text = self._get_section_text(case_content, 'conclusion')
        
        # Build reasoning extraction prompt with ontological context
        reasoning_prompt = self._build_reasoning_extraction_prompt(
            case_text, discussion_text, conclusion_text, principles, obligations
        )
        
        try:
            llm_response = await self._get_llm_response(reasoning_prompt)
            reasoning_data = self._parse_reasoning_response(llm_response)
            
            # Validate reasoning steps against ontological principles
            validated_reasoning = await self._validate_reasoning_with_ontology(
                reasoning_data, principles, obligations
            )
            
            return self._create_enhanced_reasoning_chain(validated_reasoning)
            
        except Exception as e:
            logger.error(f"LLM reasoning extraction failed: {e}")
            return super().extract_reasoning_chain(case_content)
    
    async def _gather_ontology_context(self) -> Dict[str, Any]:
        """Gather comprehensive ontological context for case analysis."""
        context = {}
        
        for category in self.proethica_categories:
            try:
                entities = await self.mcp_manager.get_entities_by_category(
                    category=category,
                    domain_id="engineering-ethics",
                    status="approved"
                )
                context[category.lower()] = entities.get("entities", [])
            except Exception as e:
                logger.warning(f"Failed to get {category} entities: {e}")
                context[category.lower()] = []
        
        return context
    
    def _build_stakeholder_extraction_prompt(self, case_text: str, role_entities: Dict[str, Any]) -> str:
        """Build prompt for LLM stakeholder extraction with ontological context."""
        
        # Extract sample roles from ontology for context
        sample_roles = []
        entities_list = role_entities.get("entities", [])
        for entity in entities_list[:10]:  # Use top 10 role entities
            if isinstance(entity, dict):
                role_label = entity.get("label", "Unknown")
                role_desc = entity.get("description", "")[:100]  # Limit description
                sample_roles.append(f"- {role_label}: {role_desc}")
        
        roles_context = "\n".join(sample_roles) if sample_roles else "- Professional Engineer\n- Client\n- Public"
        
        return f"""You are an expert in engineering ethics case analysis. Extract stakeholders from the following case using the provided ontological role context.

ONTOLOGICAL ROLE CONTEXT:
{roles_context}

CASE TEXT:
{case_text}

Please identify all stakeholders in this case and format your response as JSON:

{{
    "stakeholders": [
        {{
            "name": "Descriptive name for stakeholder",
            "role_category": "Role category (e.g., Professional Engineer, Client, Public)",
            "description": "Brief description of their involvement",
            "interests": ["list", "of", "primary", "interests"],
            "power_level": "high/medium/low",
            "ontology_alignment": "Which ontological role best matches (if any)",
            "confidence": 0.85
        }}
    ],
    "extraction_confidence": 0.90,
    "reasoning": "Explanation of extraction approach and ontological alignment"
}}

Focus on stakeholders who have clear ethical interests in the case outcome. Use the ontological role context to ensure accurate categorization."""

    async def _get_llm_response(self, prompt: str) -> str:
        """Get response from LLM orchestrator."""
        if not self.llm_orchestrator:
            raise Exception("LLM orchestrator not initialized")
        
        response = await self.llm_orchestrator.send_message(
            message=prompt,
            max_tokens=2000,
            temperature=0.1  # Low temperature for consistent extraction
        )
        
        return response.content if response else ""
    
    def _parse_stakeholder_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response to extract stakeholder data."""
        import json
        
        try:
            # Clean response and extract JSON
            cleaned_response = self._clean_json_response(response)
            data = json.loads(cleaned_response)
            
            stakeholders = data.get("stakeholders", [])
            logger.info(f"Parsed {len(stakeholders)} stakeholders from LLM response")
            return stakeholders
            
        except Exception as e:
            logger.error(f"Failed to parse stakeholder response: {e}")
            return []
    
    def _clean_json_response(self, response: str) -> str:
        """Clean LLM response to extract valid JSON."""
        # Find JSON block in response
        start_idx = response.find('{')
        end_idx = response.rfind('}') + 1
        
        if start_idx != -1 and end_idx > start_idx:
            return response[start_idx:end_idx]
        
        return response
    
    async def _validate_stakeholders_with_ontology(self, stakeholders: List[Dict[str, Any]], 
                                                 role_entities: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Validate extracted stakeholders against ontological entities."""
        entities_list = role_entities.get("entities", [])
        
        validated_stakeholders = []
        
        for stakeholder in stakeholders:
            # Calculate ontological alignment score
            alignment_score = self._calculate_role_alignment(stakeholder, entities_list)
            stakeholder["ontology_alignment_score"] = alignment_score
            
            # Adjust confidence based on ontological alignment
            original_confidence = stakeholder.get("confidence", 0.5)
            adjusted_confidence = (original_confidence + alignment_score) / 2
            stakeholder["adjusted_confidence"] = adjusted_confidence
            
            # Only include stakeholders with reasonable confidence
            if adjusted_confidence >= 0.6:
                validated_stakeholders.append(stakeholder)
        
        # Sort by adjusted confidence
        validated_stakeholders.sort(key=lambda x: x.get("adjusted_confidence", 0), reverse=True)
        
        return validated_stakeholders
    
    def _calculate_role_alignment(self, stakeholder: Dict[str, Any], role_entities: List[Dict[str, Any]]) -> float:
        """Calculate semantic alignment between extracted stakeholder and ontological roles."""
        stakeholder_role = stakeholder.get("role_category", "").lower()
        stakeholder_desc = stakeholder.get("description", "").lower()
        
        max_alignment = 0.0
        
        for entity in role_entities:
            if isinstance(entity, dict):
                entity_label = entity.get("label", "").lower()
                entity_desc = entity.get("description", "").lower()
                
                # Calculate simple similarity scores
                label_similarity = self._calculate_text_similarity(stakeholder_role, entity_label)
                desc_similarity = self._calculate_text_similarity(stakeholder_desc, entity_desc)
                
                # Combine similarities
                alignment = (label_similarity * 0.7 + desc_similarity * 0.3)
                max_alignment = max(max_alignment, alignment)
        
        return max_alignment
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity based on word overlap."""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _create_enhanced_stakeholder(self, stakeholder_data: Dict[str, Any]) -> Stakeholder:
        """Create Stakeholder object with enhanced confidence and ontological alignment."""
        
        # Map role category to StakeholderRole enum
        role_category = stakeholder_data.get("role_category", "").lower()
        stakeholder_role = StakeholderRole.PUBLIC  # Default
        
        if "engineer" in role_category or "professional" in role_category:
            stakeholder_role = StakeholderRole.PROFESSIONAL
        elif "client" in role_category or "customer" in role_category:
            stakeholder_role = StakeholderRole.CLIENT  
        elif "employer" in role_category or "company" in role_category:
            stakeholder_role = StakeholderRole.EMPLOYER
        elif "regulator" in role_category or "authority" in role_category:
            stakeholder_role = StakeholderRole.REGULATOR
        
        return Stakeholder(
            name=stakeholder_data.get("name", "Unknown Stakeholder"),
            role=stakeholder_role,
            description=stakeholder_data.get("description", ""),
            interests=stakeholder_data.get("interests", []),
            power_level=stakeholder_data.get("power_level", "medium"),
            ontology_alignment=stakeholder_data.get("ontology_alignment", ""),
            confidence_score=stakeholder_data.get("adjusted_confidence", 0.5)
        )
    
    async def _extract_interactive_decisions_with_ontology(self, questions_text: str, case_text: str,
                                                         ontology_context: Dict[str, Any],
                                                         case_content: Dict[str, Any]) -> List[EthicalDecisionPoint]:
        """Extract interactive decision points with full ontological context."""
        
        # Build comprehensive decision extraction prompt
        decision_prompt = self._build_decision_extraction_prompt(
            questions_text, case_text, ontology_context, interactive=True
        )
        
        try:
            llm_response = await self._get_llm_response(decision_prompt)
            decisions_data = self._parse_decisions_response(llm_response)
            
            # Create enhanced decision points with ontological validation
            decision_points = []
            for i, decision_data in enumerate(decisions_data.get("decisions", [])):
                enhanced_decision = await self._create_enhanced_decision_point(
                    decision_data, i + 1, ontology_context, case_content
                )
                decision_points.append(enhanced_decision)
            
            return decision_points
            
        except Exception as e:
            logger.error(f"Interactive decision extraction with ontology failed: {e}")
            return super().identify_ethical_decision_points(case_content)
    
    def _build_decision_extraction_prompt(self, questions_text: str, case_text: str,
                                        ontology_context: Dict[str, Any], interactive: bool = True) -> str:
        """Build comprehensive prompt for decision point extraction with ontological guidance."""
        
        # Build ontology context summary
        ontology_summary = []
        for category, entities in ontology_context.items():
            if entities:
                sample_entities = []
                for entity in entities[:5]:  # Top 5 per category
                    if isinstance(entity, dict):
                        label = entity.get("label", "Unknown")
                        sample_entities.append(label)
                ontology_summary.append(f"{category.title()}: {', '.join(sample_entities)}")
        
        context_text = "\n".join(ontology_summary)
        
        prompt_type = "interactive questions" if interactive else "case analysis"
        
        return f"""You are an expert in engineering ethics with access to formal ontological knowledge. Extract ethical decision points from the following {prompt_type} using the provided ontological context.

ONTOLOGICAL CONTEXT (ProEthica Categories):
{context_text}

CASE TEXT:
{case_text}

{"QUESTIONS TO ANALYZE:" if interactive else ""}
{questions_text if interactive else ""}

Analyze the case and identify distinct ethical decision points. Format your response as JSON:

{{
    "decisions": [
        {{
            "title": "Clear decision point title",
            "description": "Detailed description of the ethical situation",
            "decision_type": "safety/disclosure/confidentiality/professional_duty/conflict_of_interest",
            "protagonist": "Who needs to make this decision",
            "ethical_principles": ["Relevant NSPE/ethical principles"],
            "ontology_categories": {{
                "roles": ["Relevant role entities"],
                "principles": ["Relevant principle entities"],
                "obligations": ["Relevant obligation entities"],
                "actions": ["Relevant action entities"]
            }},
            "options": [
                {{
                    "title": "Option name",
                    "description": "What this option involves",
                    "ethical_justification": "Why this might be ethical",
                    "consequences": ["Potential outcomes"]
                }}
            ],
            "context_factors": ["Environmental factors affecting decision"],
            "confidence": 0.85
        }}
    ],
    "extraction_confidence": 0.90,
    "reasoning": "Explanation of extraction approach and ontological alignment"
}}

Use the ontological categories to ensure comprehensive analysis across all ProEthica dimensions."""
    
    def _parse_decisions_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response to extract decision data."""
        import json
        
        try:
            cleaned_response = self._clean_json_response(response)
            data = json.loads(cleaned_response)
            
            decisions = data.get("decisions", [])
            logger.info(f"Parsed {len(decisions)} decisions from LLM response")
            return data
            
        except Exception as e:
            logger.error(f"Failed to parse decisions response: {e}")
            return {"decisions": [], "extraction_confidence": 0.0}
    
    async def _create_enhanced_decision_point(self, decision_data: Dict[str, Any], sequence: int,
                                            ontology_context: Dict[str, Any], 
                                            case_content: Dict[str, Any]) -> EthicalDecisionPoint:
        """Create enhanced decision point with ontological validation and enrichment."""
        
        # Extract basic decision information
        title = decision_data.get("title", f"Decision Point {sequence}")
        description = decision_data.get("description", "")
        decision_type_str = decision_data.get("decision_type", "professional_duty")
        
        # Map to DecisionType enum
        decision_type = self._map_decision_type(decision_type_str)
        
        # Create enhanced decision options with ontological validation
        options_data = decision_data.get("options", [])
        enhanced_options = []
        
        for option_data in options_data:
            option = DecisionOption(
                option_id=self._generate_option_id(option_data.get("title", "")),
                title=option_data.get("title", ""),
                ethical_justification=option_data.get("ethical_justification", ""),
                consequences=option_data.get("consequences", []),
                ontology_alignment=self._calculate_option_ontology_alignment(option_data, ontology_context)
            )
            enhanced_options.append(option)
        
        # Validate against ontological principles
        principles = decision_data.get("ethical_principles", [])
        validated_principles = await self._validate_principles_with_ontology(principles, ontology_context)
        
        # Extract context factors and validate
        context_factors = decision_data.get("context_factors", [])
        
        return EthicalDecisionPoint(
            decision_id=f"enhanced_decision_{sequence}",
            title=title,
            description=description,
            decision_type=decision_type,
            ethical_principles=validated_principles,
            primary_options=enhanced_options,
            context_factors=context_factors,
            sequence_number=sequence,
            protagonist=decision_data.get("protagonist", "Professional Engineer"),
            ontology_categories=decision_data.get("ontology_categories", {}),
            extraction_confidence=decision_data.get("confidence", 0.7),
            ontology_validation_score=await self._calculate_decision_ontology_score(decision_data, ontology_context)
        )
    
    def _map_decision_type(self, decision_type_str: str) -> DecisionType:
        """Map string decision type to enum."""
        mapping = {
            "safety": DecisionType.SAFETY,
            "disclosure": DecisionType.DISCLOSURE, 
            "confidentiality": DecisionType.CONFIDENTIALITY,
            "professional_duty": DecisionType.PROFESSIONAL_DUTY,
            "conflict_of_interest": DecisionType.CONFLICT_OF_INTEREST
        }
        return mapping.get(decision_type_str.lower(), DecisionType.PROFESSIONAL_DUTY)
    
    def _generate_option_id(self, title: str) -> str:
        """Generate option ID from title."""
        return re.sub(r'[^a-zA-Z0-9]+', '_', title.lower()).strip('_')
    
    def _calculate_option_ontology_alignment(self, option_data: Dict[str, Any], 
                                           ontology_context: Dict[str, Any]) -> float:
        """Calculate how well an option aligns with ontological concepts."""
        justification = option_data.get("ethical_justification", "").lower()
        
        # Check alignment with principle entities
        principle_entities = ontology_context.get("principle", [])
        max_alignment = 0.0
        
        for entity in principle_entities[:10]:  # Check top 10 principles
            if isinstance(entity, dict):
                entity_desc = entity.get("description", "").lower()
                alignment = self._calculate_text_similarity(justification, entity_desc)
                max_alignment = max(max_alignment, alignment)
        
        return max_alignment
    
    async def _validate_principles_with_ontology(self, principles: List[str], 
                                               ontology_context: Dict[str, Any]) -> List[str]:
        """Validate and enrich ethical principles using ontological knowledge."""
        principle_entities = ontology_context.get("principle", [])
        
        validated_principles = []
        
        for principle in principles:
            # Find best matching principle entity
            best_match = self._find_best_principle_match(principle, principle_entities)
            if best_match:
                # Use the formal ontological description
                validated_principles.append(best_match.get("description", principle))
            else:
                # Keep original if no good match
                validated_principles.append(principle)
        
        return validated_principles
    
    def _find_best_principle_match(self, principle: str, principle_entities: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Find the best matching principle entity from ontology."""
        best_match = None
        best_score = 0.3  # Minimum threshold
        
        for entity in principle_entities:
            if isinstance(entity, dict):
                entity_label = entity.get("label", "")
                entity_desc = entity.get("description", "")
                
                # Calculate similarity scores
                label_score = self._calculate_text_similarity(principle.lower(), entity_label.lower())
                desc_score = self._calculate_text_similarity(principle.lower(), entity_desc.lower())
                
                combined_score = max(label_score, desc_score * 0.8)  # Prefer label matches
                
                if combined_score > best_score:
                    best_score = combined_score
                    best_match = entity
        
        return best_match
    
    async def _calculate_decision_ontology_score(self, decision_data: Dict[str, Any], 
                                               ontology_context: Dict[str, Any]) -> float:
        """Calculate overall ontological alignment score for a decision point."""
        
        # Get ontology categories mentioned in decision
        ontology_categories = decision_data.get("ontology_categories", {})
        
        total_score = 0.0
        category_count = 0
        
        for category_name, mentioned_entities in ontology_categories.items():
            if mentioned_entities and category_name in ontology_context:
                available_entities = ontology_context[category_name]
                
                # Calculate match score for this category
                category_score = self._calculate_category_match_score(mentioned_entities, available_entities)
                total_score += category_score
                category_count += 1
        
        return total_score / category_count if category_count > 0 else 0.0
    
    def _calculate_category_match_score(self, mentioned_entities: List[str], 
                                      available_entities: List[Dict[str, Any]]) -> float:
        """Calculate match score between mentioned entities and available ontology entities."""
        if not mentioned_entities or not available_entities:
            return 0.0
        
        match_scores = []
        
        for mentioned in mentioned_entities:
            best_match_score = 0.0
            
            for available in available_entities:
                if isinstance(available, dict):
                    available_label = available.get("label", "")
                    score = self._calculate_text_similarity(mentioned.lower(), available_label.lower())
                    best_match_score = max(best_match_score, score)
            
            match_scores.append(best_match_score)
        
        return sum(match_scores) / len(match_scores)
    
    def _build_reasoning_extraction_prompt(self, case_text: str, discussion_text: str, 
                                         conclusion_text: str, principles: Dict[str, Any], 
                                         obligations: Dict[str, Any]) -> str:
        """Build prompt for reasoning chain extraction with ontological context."""
        
        # Build principle and obligation context
        principle_context = self._build_entity_context(principles.get("entities", [])[:10])
        obligation_context = self._build_entity_context(obligations.get("entities", [])[:10])
        
        return f"""You are an expert in engineering ethics reasoning. Extract the reasoning chain from this case using the provided ontological context.

ONTOLOGICAL PRINCIPLES:
{principle_context}

ONTOLOGICAL OBLIGATIONS:
{obligation_context}

CASE FACTS:
{case_text}

DISCUSSION:
{discussion_text}

CONCLUSION:
{conclusion_text}

Extract the reasoning chain and format as JSON:

{{
    "facts": ["Key factual statements from the case"],
    "applicable_principles": ["Relevant ontological principles applied"],
    "reasoning_steps": [
        {{
            "step_number": 1,
            "reasoning_type": "factual_analysis/principle_application/consequence_evaluation",
            "input_elements": ["What information is being processed"],
            "reasoning_logic": "The logical reasoning applied",
            "output_conclusion": "What this step concludes",
            "ontology_support": "Which ontological entities support this reasoning",
            "confidence": 0.85
        }}
    ],
    "predicted_outcome": "What the reasoning predicts will happen",
    "actual_outcome": "What actually happened (if available)",
    "extraction_confidence": 0.90,
    "reasoning": "Explanation of reasoning extraction and ontological alignment"
}}

Use the ontological context to ensure comprehensive reasoning analysis."""
    
    def _build_entity_context(self, entities: List[Dict[str, Any]]) -> str:
        """Build formatted context string from entity list."""
        context_lines = []
        
        for entity in entities:
            if isinstance(entity, dict):
                label = entity.get("label", "Unknown")
                description = entity.get("description", "")[:150]  # Limit description length
                context_lines.append(f"- {label}: {description}")
        
        return "\n".join(context_lines) if context_lines else "No entities available"
    
    def _parse_reasoning_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response to extract reasoning data."""
        import json
        
        try:
            cleaned_response = self._clean_json_response(response)
            data = json.loads(cleaned_response)
            
            reasoning_steps = data.get("reasoning_steps", [])
            logger.info(f"Parsed {len(reasoning_steps)} reasoning steps from LLM response")
            return data
            
        except Exception as e:
            logger.error(f"Failed to parse reasoning response: {e}")
            return {
                "facts": [],
                "applicable_principles": [],
                "reasoning_steps": [],
                "predicted_outcome": "",
                "actual_outcome": "",
                "extraction_confidence": 0.0
            }
    
    async def _validate_reasoning_with_ontology(self, reasoning_data: Dict[str, Any],
                                              principles: Dict[str, Any],
                                              obligations: Dict[str, Any]) -> Dict[str, Any]:
        """Validate reasoning steps against ontological principles and obligations."""
        
        principle_entities = principles.get("entities", [])
        obligation_entities = obligations.get("entities", [])
        
        # Validate applicable principles
        stated_principles = reasoning_data.get("applicable_principles", [])
        validated_principles = []
        
        for principle in stated_principles:
            best_match = self._find_best_principle_match(principle, principle_entities)
            if best_match:
                validated_principles.append(best_match.get("description", principle))
            else:
                validated_principles.append(principle)
        
        reasoning_data["validated_principles"] = validated_principles
        
        # Validate reasoning steps
        reasoning_steps = reasoning_data.get("reasoning_steps", [])
        validated_steps = []
        
        for step in reasoning_steps:
            validation_score = await self._validate_reasoning_step(step, principle_entities, obligation_entities)
            step["ontology_validation_score"] = validation_score
            validated_steps.append(step)
        
        reasoning_data["validated_steps"] = validated_steps
        
        return reasoning_data
    
    async def _validate_reasoning_step(self, step: Dict[str, Any], 
                                     principle_entities: List[Dict[str, Any]],
                                     obligation_entities: List[Dict[str, Any]]) -> float:
        """Validate a single reasoning step against ontological entities."""
        
        reasoning_logic = step.get("reasoning_logic", "").lower()
        ontology_support = step.get("ontology_support", "").lower()
        
        # Check alignment with principle entities
        principle_score = 0.0
        for entity in principle_entities[:10]:
            if isinstance(entity, dict):
                entity_desc = entity.get("description", "").lower()
                score = self._calculate_text_similarity(reasoning_logic, entity_desc)
                principle_score = max(principle_score, score)
        
        # Check alignment with obligation entities  
        obligation_score = 0.0
        for entity in obligation_entities[:10]:
            if isinstance(entity, dict):
                entity_desc = entity.get("description", "").lower()
                score = self._calculate_text_similarity(reasoning_logic, entity_desc)
                obligation_score = max(obligation_score, score)
        
        # Combine scores
        return (principle_score + obligation_score) / 2
    
    def _create_enhanced_reasoning_chain(self, validated_reasoning: Dict[str, Any]) -> ReasoningChain:
        """Create ReasoningChain object with enhanced ontological validation."""
        
        # Convert validated steps to ReasoningStep objects
        validated_steps = validated_reasoning.get("validated_steps", [])
        reasoning_steps = []
        
        for step_data in validated_steps:
            step = ReasoningStep(
                step_order=step_data.get("step_number", 1),
                reasoning_type=step_data.get("reasoning_type", "ethical_analysis"),
                input_elements=step_data.get("input_elements", []),
                reasoning_logic=step_data.get("reasoning_logic", ""),
                output_conclusion=step_data.get("output_conclusion", ""),
                confidence=step_data.get("confidence", 0.5),
                ontology_validation_score=step_data.get("ontology_validation_score", 0.0),
                ontology_support=step_data.get("ontology_support", "")
            )
            reasoning_steps.append(step)
        
        return ReasoningChain(
            case_facts=validated_reasoning.get("facts", []),
            applicable_principles=validated_reasoning.get("validated_principles", []),
            reasoning_steps=reasoning_steps,
            predicted_outcome=validated_reasoning.get("predicted_outcome", ""),
            actual_outcome=validated_reasoning.get("actual_outcome", ""),
            extraction_confidence=validated_reasoning.get("extraction_confidence", 0.0),
            ontology_alignment_score=self._calculate_overall_reasoning_score(validated_reasoning)
        )
    
    def _calculate_overall_reasoning_score(self, validated_reasoning: Dict[str, Any]) -> float:
        """Calculate overall ontological alignment score for the reasoning chain."""
        
        validated_steps = validated_reasoning.get("validated_steps", [])
        
        if not validated_steps:
            return 0.0
        
        total_score = sum(step.get("ontology_validation_score", 0.0) for step in validated_steps)
        return total_score / len(validated_steps)
    
    async def _extract_general_decisions_with_ontology(self, case_text: str, 
                                                     ontology_context: Dict[str, Any]) -> List[EthicalDecisionPoint]:
        """Extract general decision points (non-interactive cases) with ontological context."""
        
        # Build decision extraction prompt for general case analysis
        decision_prompt = self._build_decision_extraction_prompt(
            "", case_text, ontology_context, interactive=False
        )
        
        try:
            llm_response = await self._get_llm_response(decision_prompt)
            decisions_data = self._parse_decisions_response(llm_response)
            
            # Create enhanced decision points
            decision_points = []
            for i, decision_data in enumerate(decisions_data.get("decisions", [])):
                enhanced_decision = await self._create_enhanced_decision_point(
                    decision_data, i + 1, ontology_context, {"content": case_text}
                )
                decision_points.append(enhanced_decision)
            
            return decision_points
            
        except Exception as e:
            logger.error(f"General decision extraction with ontology failed: {e}")
            # Fall back to base adapter
            return super().identify_ethical_decision_points({"content": case_text})
