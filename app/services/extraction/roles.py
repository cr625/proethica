"""
Roles Extractor - Focused extraction of professional and stakeholder roles from guidelines.

This implements the first pass of the two-pass extraction approach outlined in 
ROLE_EXTRACTION_AND_MATCHING_INTEGRATED_PLAN.md.
"""

import json
import logging
import re
from typing import List, Optional

from .base import ConceptCandidate, Extractor, PostProcessor, Matcher, MatchedConcept
from .atomic_extraction_mixin import AtomicExtractionMixin

logger = logging.getLogger(__name__)


class RolesExtractor(Extractor, AtomicExtractionMixin):
    """Extract roles from guideline text using focused, roles-only prompting."""
    
    def __init__(self, provider: Optional[str] = None):
        """
        Initialize RolesExtractor.
        
        Args:
            provider: LLM provider ('anthropic', 'openai', or None for default)
        """
        self.provider = provider or 'anthropic'
    
    @property
    def concept_type(self) -> str:
        """The concept type this extractor handles."""
        return 'role'
        
    def extract(self, text: str, *, world_id: Optional[int] = None, guideline_id: Optional[int] = None, activity=None) -> List[ConceptCandidate]:
        """
        Extract roles from guideline text with optional external MCP context and provenance tracking.
        
        Args:
            text: Guideline content
            world_id: World context (defaults to Engineering)
            guideline_id: Guideline ID for tracking
            activity: Optional ProvenanceActivity for tracking LLM interactions
            
        Returns:
            List of ConceptCandidate objects for roles only
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for role extraction")
            return []
            
        logger.info(f"Starting roles extraction for guideline {guideline_id} (world {world_id})")
        
        try:
            # Check if external MCP integration is enabled
            import os
            # Ensure .env file is loaded
            try:
                from dotenv import load_dotenv
                load_dotenv()
            except ImportError:
                pass
            
            use_external_mcp = os.environ.get('ENABLE_EXTERNAL_MCP_ACCESS', 'true').lower() == 'true'
            logger.info(f"ENABLE_EXTERNAL_MCP_ACCESS = {os.environ.get('ENABLE_EXTERNAL_MCP_ACCESS')}")
            logger.info(f"Will use external MCP: {use_external_mcp}")
            
            if use_external_mcp:
                logger.info("Using external MCP server for ontology context")
                prompt = self._create_roles_prompt_with_external_mcp(text)
            else:
                logger.info("Using standard roles extraction (no external MCP)")
                prompt = self._create_roles_prompt(text)
            
            # Call LLM with focused prompt and provenance tracking
            response = self._call_llm(prompt, activity=activity)
            
            # Parse and validate response
            candidates = self._parse_response(response)
            
            # Post-process to ensure all are roles
            candidates = self._ensure_roles_only(candidates)
            
            logger.info(f"Extracted {len(candidates)} role candidates")
            
            # Enhanced splitting now handled at unified level in guideline_analysis_service.py
            # Individual extractor splitting disabled to avoid double-processing
            
            # Log first few for debugging
            for i, candidate in enumerate(candidates[:3]):
                logger.info(f"Role {i+1}: {candidate.label} ({candidate.primary_type})")
            
            # Apply unified atomic splitting
            return self._apply_atomic_splitting(candidates)
            
        except Exception as e:
            logger.error(f"Error in roles extraction: {e}", exc_info=True)
            return []
    
    def _get_prompt_for_preview(self, text: str) -> str:
        """Get the actual prompt that will be sent to the LLM, including MCP context."""
        # Always use external MCP (required for system to function)
        return self._create_roles_prompt_with_external_mcp(text)
    
    def _create_roles_prompt(self, text: str) -> str:
        """Create a focused prompt that extracts ONLY roles."""
        # Import enhanced prompt if available, otherwise use standard
        try:
            from .enhanced_prompts_roles_resources import get_enhanced_roles_prompt
            return get_enhanced_roles_prompt(text, include_mcp_context=False)
        except ImportError:
            # Fallback to standard prompt
            return f"""
You are analyzing an ethics guideline to extract ROLES only. Do NOT extract principles, obligations, or other concepts.

FOCUS: Identify only the ROLES mentioned in this guideline text.

ROLE TYPES:
1. **Professional Roles**: People who have professional obligations (e.g., Engineer, Project Manager, Supervisor)
2. **Stakeholder Roles**: People affected by or interacting with professionals (e.g., Client, Employer, Public, Community)

EXAMPLES OF ROLES:
- Engineer, Senior Engineer, Structural Engineer
- Client, Customer, Employer, Supervisor
- Public, Community, Society, Citizens
- Contractor, Consultant, Manager, Administrator

GUIDELINES:
- Extract specific role mentions, not general concepts
- Include both individual roles (Engineer) and role categories (Public)
- Roles should be people/entities, not processes or principles
- Each role should have clear definition of who fills this role

GUIDELINE TEXT:
{text}

OUTPUT FORMAT:
Return a JSON array with this structure:
[
  {{
    "label": "Engineer Role",
    "description": "Professional engineer responsible for technical work", 
    "type": "role",
    "role_classification": "professional",
    "text_references": ["specific quote from text"],
    "importance": "high"
  }}
]

Focus on accuracy over quantity. Extract only clear, unambiguous roles.
"""

    def _create_roles_prompt_with_external_mcp(self, text: str) -> str:
        """Create enhanced roles prompt with external MCP ontology context."""
        try:
            # Import external MCP client
            from app.services.external_mcp_client import get_external_mcp_client
            
            logger.info("Fetching ontology context from external MCP server...")
            external_client = get_external_mcp_client()
            
            # Get existing roles from ontology
            existing_roles = external_client.get_all_role_entities()
            
            logger.info(f"Retrieved {len(existing_roles)} existing roles from external MCP for context")
            
            # Try to use enhanced prompt with MCP context
            try:
                from .enhanced_prompts_roles_resources import get_enhanced_roles_prompt
                return get_enhanced_roles_prompt(text, include_mcp_context=True, existing_roles=existing_roles)
            except ImportError:
                # Fallback to building context manually
                # Build ontology context
                ontology_context = "EXISTING ROLES IN ONTOLOGY:\n"
                if existing_roles:
                    ontology_context += f"Found {len(existing_roles)} existing role concepts:\n"
                    for role in existing_roles:  # Show all roles
                        label = role.get('label', 'Unknown')
                        description = role.get('description', 'No description')
                        ontology_context += f"- {label}: {description}\n"
                else:
                    ontology_context += "No existing roles found in ontology (fresh setup)\n"
                
                logger.info(f"Retrieved {len(existing_roles)} existing roles from external MCP for context")
            
            # Create enhanced prompt with ontology context
            enhanced_prompt = f"""
{ontology_context}

You are analyzing an ethics guideline to extract ROLES only. Do NOT extract principles, obligations, or other concepts.

IMPORTANT: Consider the existing roles above when extracting. For each role you extract:
1. Check if it matches an existing role (mark as existing)
2. If it's genuinely new, mark as new
3. Provide clear reasoning for why it's new vs existing

FOCUS: Identify only the ROLES mentioned in this guideline text.

ROLE TYPES:
1. **Professional Roles**: People who have professional obligations (e.g., Engineer, Project Manager, Supervisor)
2. **Stakeholder Roles**: People affected by or interacting with professionals (e.g., Client, Employer, Public, Community)

GUIDELINES:
- Extract specific role mentions, not general concepts
- Include both individual roles (Engineer) and role categories (Public)
- Roles should be people/entities, not processes or principles
- Each role should have clear definition of who fills this role
- Consider existing ontology roles when determining if extracted role is new

GUIDELINE TEXT:
{text}

OUTPUT FORMAT:
Return a JSON array with this structure:
[
  {{
    "label": "Engineer Role",
    "description": "Professional engineer responsible for technical work", 
    "type": "role",
    "role_classification": "professional",
    "text_references": ["specific quote from text"],
    "importance": "high",
    "is_existing": false,
    "ontology_match_reasoning": "Similar to existing Engineer concepts but more specific"
  }}
]

Focus on accuracy over quantity. Extract only clear, unambiguous roles.
"""
            
            return enhanced_prompt
            
        except Exception as e:
            logger.error(f"Failed to get external MCP context: {e}")
            logger.info("Falling back to standard roles prompt")
            return self._create_roles_prompt(text)

    def _call_llm(self, prompt: str, activity=None) -> str:
        """Call LLM with the roles extraction prompt, tracking with provenance if activity provided."""
        try:
            from app.utils.llm_utils import get_llm_client
            from app.services.provenance_service import get_provenance_service
            
            llm_client = get_llm_client()
            prov = get_provenance_service() if activity else None
            
            # Record the prompt if provenance tracking is active
            prompt_entity = None
            if prov and activity:
                prompt_entity = prov.record_prompt(
                    prompt_text=prompt,
                    activity=activity,
                    entity_name="roles_extraction_prompt",
                    metadata={
                        'extraction_type': 'roles',
                        'prompt_length': len(prompt)
                    }
                )
            
            # Track LLM model and parameters
            model_name = None
            model_params = {}
            response_metadata = {}
            
            # Handle different LLM client types  
            if hasattr(llm_client, 'messages') and hasattr(llm_client.messages, 'create'):
                # Anthropic client
                model_name = "claude-sonnet-4-20250514"
                model_params = {'max_tokens': 2000, 'provider': 'anthropic'}
                
                response = llm_client.messages.create(
                    model=model_name,
                    max_tokens=2000,  # Reduced since we're only extracting roles
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                response_text = response.content[0].text if response.content else ""
                
                # Capture response metadata
                if hasattr(response, 'usage'):
                    response_metadata['usage'] = {
                        'input_tokens': getattr(response.usage, 'input_tokens', None),
                        'output_tokens': getattr(response.usage, 'output_tokens', None),
                        'total_tokens': getattr(response.usage, 'total_tokens', None)
                    }
                
            elif hasattr(llm_client, 'chat') and hasattr(llm_client.chat, 'completions'):
                # OpenAI client
                model_name = "gpt-4"
                model_params = {'max_tokens': 2000, 'provider': 'openai'}
                
                response = llm_client.chat.completions.create(
                    model=model_name,
                    messages=[{
                        "role": "user", 
                        "content": prompt
                    }],
                    max_tokens=2000
                )
                response_text = response.choices[0].message.content
                
                # Capture response metadata
                if hasattr(response, 'usage'):
                    response_metadata['usage'] = {
                        'prompt_tokens': response.usage.prompt_tokens,
                        'completion_tokens': response.usage.completion_tokens,
                        'total_tokens': response.usage.total_tokens
                    }
                
            else:
                raise RuntimeError(f"Unsupported LLM client type: {type(llm_client)}")
            
            # Record the response if provenance tracking is active
            if prov and activity and prompt_entity:
                response_metadata.update({
                    'model': model_name,
                    'model_params': model_params,
                    'extraction_type': 'roles'
                })
                
                prov.record_response(
                    response_text=response_text,
                    activity=activity,
                    derived_from=prompt_entity,
                    entity_name="roles_extraction_response",
                    metadata=response_metadata
                )
            
            logger.debug(f"LLM response for roles extraction: {response_text[:200]}...")
            return response_text
            
        except Exception as e:
            logger.error(f"Error calling LLM for roles extraction: {e}")
            return ""
    
    def _parse_response(self, response_text: str) -> List[ConceptCandidate]:
        """Parse LLM response into ConceptCandidate objects."""
        if not response_text:
            return []
            
        try:
            # Extract JSON from markdown code blocks if present
            code_block_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response_text)
            if code_block_match:
                response_text = code_block_match.group(1).strip()
            
            # Try to parse JSON directly
            if response_text.strip().startswith('['):
                roles_data = json.loads(response_text)
            elif response_text.strip().startswith('{'):
                # Handle case where LLM returns object instead of array
                parsed = json.loads(response_text)
                roles_data = parsed.get('roles', parsed.get('concepts', []))
            else:
                # Look for JSON array in the text
                json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                if json_match:
                    roles_data = json.loads(json_match.group())
                else:
                    logger.warning(f"No JSON array found in response: {response_text[:200]}...")
                    return []
            
            # Convert to ConceptCandidate objects
            candidates = []
            for role_data in roles_data:
                if not isinstance(role_data, dict):
                    continue
                    
                # Extract match_decision if present (new structured format)
                match_decision = role_data.get('match_decision', {})

                candidate = ConceptCandidate(
                    label=role_data.get('label', ''),
                    description=role_data.get('description', ''),
                    primary_type='role',  # Force all to be roles
                    category='role',
                    confidence=self._parse_confidence(role_data.get('importance', 'medium')),
                    debug={
                        # Preserve old fields for compatibility
                        'role_classification': role_data.get('role_classification', ''),
                        'text_references': role_data.get('text_references', []),
                        'importance': role_data.get('importance', 'medium'),
                        # Add ALL enhanced prompt fields
                        'role_category': role_data.get('role_category'),  # New: provider_client, professional_peer, etc.
                        'obligations_generated': role_data.get('obligations_generated', []),
                        'ethical_filter_function': role_data.get('ethical_filter_function'),
                        'theoretical_grounding': role_data.get('theoretical_grounding'),
                        # Legacy fields (backward compat)
                        'is_existing': role_data.get('is_existing') or match_decision.get('matches_existing'),
                        'ontology_match_reasoning': role_data.get('ontology_match_reasoning'),
                        # NEW: Structured match decision for entity-ontology linking
                        'match_decision': match_decision,
                        'matched_ontology_uri': match_decision.get('matched_uri'),
                        'matched_ontology_label': match_decision.get('matched_label'),
                        'match_confidence': match_decision.get('confidence'),
                        'match_reasoning': match_decision.get('reasoning'),
                        # Store complete raw data for full preservation
                        'raw_llm_data': role_data
                    }
                )
                
                if candidate.label:  # Only add if we have a label
                    candidates.append(candidate)
                    
            logger.info(f"Parsed {len(candidates)} role candidates from LLM response")
            return candidates
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response was: {response_text}")
            return []
        except Exception as e:
            logger.error(f"Error parsing roles response: {e}")
            return []
    
    def _parse_confidence(self, importance: str) -> float:
        """Convert importance level to confidence score."""
        mapping = {
            'high': 0.9,
            'medium': 0.7,
            'low': 0.5
        }
        return mapping.get(importance.lower(), 0.7)
    
    def _ensure_roles_only(self, candidates: List[ConceptCandidate]) -> List[ConceptCandidate]:
        """Post-process to ensure all candidates are actually roles."""
        role_candidates = []
        
        for candidate in candidates:
            # Force type to be role
            candidate.primary_type = 'role'
            candidate.category = 'role'
            
            # Basic validation that this looks like a role
            if self._is_valid_role(candidate):
                role_candidates.append(candidate)
            else:
                logger.warning(f"Filtering out non-role concept: {candidate.label}")
                
        return role_candidates
    
    def _is_valid_role(self, candidate: ConceptCandidate) -> bool:
        """Check if candidate is a valid role concept."""
        label = candidate.label.lower() if candidate.label else ""
        
        # Must have a label
        if not label:
            return False
            
        # Common role indicators
        role_keywords = [
            'engineer', 'client', 'contractor', 'supervisor', 'manager', 
            'public', 'employer', 'employee', 'professional', 'stakeholder',
            'administrator', 'analyst', 'architect', 'consultant', 'director',
            'specialist', 'technician', 'worker', 'officer', 'official',
            'citizen', 'community', 'society', 'user', 'customer'
        ]
        
        # Check if any role keyword is present
        for keyword in role_keywords:
            if keyword in label:
                return True
                
        # Check if it explicitly contains "role" 
        if 'role' in label:
            return True
            
        # If none of the above, it's probably not a role
        return False


class RoleClassificationPostProcessor(PostProcessor):
    """Post-processor that classifies roles as professional vs stakeholder."""
    
    def process(self, candidates: List[ConceptCandidate]) -> List[ConceptCandidate]:
        """Classify roles into professional vs stakeholder categories."""
        processed = []
        
        for candidate in candidates:
            # Classify role type
            classification = self._classify_role(candidate)
            
            # Update debug info with classification
            if not candidate.debug:
                candidate.debug = {}
            candidate.debug['role_classification'] = classification
            
            processed.append(candidate)
            
        return processed
    
    def _classify_role(self, candidate: ConceptCandidate) -> str:
        """Classify role as 'professional' or 'stakeholder'."""
        label = candidate.label.lower() if candidate.label else ""
        description = candidate.description.lower() if candidate.description else ""
        
        # Professional role indicators
        professional_keywords = [
            'engineer', 'manager', 'supervisor', 'administrator', 'director',
            'analyst', 'architect', 'consultant', 'specialist', 'technician',
            'professional', 'officer', 'official', 'contractor'
        ]
        
        # Stakeholder role indicators  
        stakeholder_keywords = [
            'client', 'customer', 'employer', 'public', 'community', 'society',
            'citizen', 'user', 'stakeholder', 'beneficiary', 'affected party'
        ]
        
        # Check professional indicators
        for keyword in professional_keywords:
            if keyword in label or keyword in description:
                return 'professional'
                
        # Check stakeholder indicators
        for keyword in stakeholder_keywords:
            if keyword in label or keyword in description:
                return 'stakeholder'
                
        # Default to professional if unclear
        return 'professional'


class SimpleRoleMatcher(Matcher):
    """Simple matcher for roles using label similarity and embeddings."""
    
    def match(self, candidates: List[ConceptCandidate], *, world_id: Optional[int] = None) -> List[MatchedConcept]:
        """Match role candidates to existing ontology roles."""
        from app.utils.label_normalization import normalize_role_label
        
        matched = []
        
        for candidate in candidates:
            try:
                # Try to find existing role match
                ontology_match = self._find_ontology_match(candidate, world_id)
                
                matched_concept = MatchedConcept(
                    candidate=candidate,
                    ontology_match=ontology_match,
                    similarity=ontology_match.get('score', 0.0) if ontology_match else None,
                    normalized_label=normalize_role_label(candidate.label) if candidate.label else None
                )
                
                matched.append(matched_concept)
                
            except Exception as e:
                logger.error(f"Error matching role '{candidate.label}': {e}")
                # Add as unmatched concept
                matched.append(MatchedConcept(candidate=candidate))
                
        return matched
    
    def _find_ontology_match(self, candidate: ConceptCandidate, world_id: Optional[int]) -> Optional[dict]:
        """Find matching role in ontology."""
        try:
            # Try to get ontology service
            from app.services.ontology_service_factory import get_ontology_service
            from app.models.world import World
            
            if not world_id:
                world_id = 1  # Default to Engineering World
                
            world = World.query.get(world_id)
            if not world:
                return None
                
            ontology_service = get_ontology_service()
            result = ontology_service.get_entities_for_world(world)
            
            if not result.get('entities'):
                return None
                
            # Look for roles in the ontology
            role_entities = result['entities'].get('Role', [])
            
            if not role_entities:
                logger.warning("No roles found in ontology")
                return None
                
            # Simple label matching for now
            candidate_label = candidate.label.lower() if candidate.label else ""
            
            for role_entity in role_entities:
                entity_label = role_entity.get('label', '').lower()
                
                # Exact match
                if candidate_label == entity_label:
                    return {
                        'uri': role_entity.get('uri', ''),
                        'label': role_entity.get('label', ''),
                        'description': role_entity.get('description', ''),
                        'score': 1.0,
                        'match_type': 'exact'
                    }
                    
                # Partial match (contains)
                if candidate_label in entity_label or entity_label in candidate_label:
                    return {
                        'uri': role_entity.get('uri', ''),
                        'label': role_entity.get('label', ''),
                        'description': role_entity.get('description', ''),
                        'score': 0.8,
                        'match_type': 'partial'
                    }
            
            # No match found
            return None
            
        except Exception as e:
            logger.error(f"Error finding ontology match for role '{candidate.label}': {e}")
            return None


class RolesLinker:
    """Link roles to obligations, principles, ends, and codes based on textual proximity."""
    
    def __init__(self):
        self.predicates = {
            'hasObligation': 'http://proethica.org/ontology/intermediate#hasObligation',
            'adheresToPrinciple': 'http://proethica.org/ontology/intermediate#adheresToPrinciple',
            'pursuesEnd': 'http://proethica.org/ontology/intermediate#pursuesEnd',
            'governedByCode': 'http://proethica.org/ontology/intermediate#governedByCode'
        }
    
    def link_roles_to_obligations(self, roles: List[MatchedConcept], 
                                 guideline_text: str) -> List[dict]:
        """Create hasObligation links for professional roles based on textual cues."""
        links = []
        
        # Simple pattern-based obligation detection
        obligation_patterns = [
            r'shall\s+([^.]*)',
            r'must\s+([^.]*)',
            r'should\s+([^.]*)',
            r'required\s+to\s+([^.]*)',
            r'responsible\s+for\s+([^.]*)',
            r'duty\s+to\s+([^.]*)'
        ]
        
        for role in roles:
            # Only link professional roles to obligations
            role_classification = role.candidate.debug.get('role_classification', 'professional')
            if role_classification != 'professional':
                continue
                
            role_uri = self._get_role_uri(role)
            role_label = role.candidate.label.lower() if role.candidate.label else ""
            
            # Find obligation mentions near this role
            for pattern in obligation_patterns:
                matches = re.finditer(pattern, guideline_text, re.IGNORECASE)
                for match in matches:
                    obligation_text = match.group(1).strip()
                    
                    # Check if role is mentioned nearby (within 100 chars)
                    start = max(0, match.start() - 100)
                    end = min(len(guideline_text), match.end() + 100)
                    context = guideline_text[start:end].lower()
                    
                    if role_label in context:
                        # Create obligation link
                        obligation_uri = self._generate_obligation_uri(obligation_text)
                        links.append({
                            'subject_uri': role_uri,
                            'predicate_uri': self.predicates['hasObligation'],
                            'object_uri': obligation_uri,
                            'confidence': 0.7,
                            'context': {
                                'obligation_text': obligation_text,
                                'pattern': pattern,
                                'role_label': role.candidate.label
                            }
                        })
        
        return links
    
    def _get_role_uri(self, role: MatchedConcept) -> str:
        """Get URI for role, using ontology match if available."""
        if role.ontology_match:
            return role.ontology_match.get('uri', '')
        
        # Generate new URI
        from slugify import slugify
        slug = slugify(role.candidate.label, separator='_')
        return f"http://proethica.ai/ontology#{slug}"
    
    def _generate_obligation_uri(self, obligation_text: str) -> str:
        """Generate URI for obligation based on text."""
        from slugify import slugify
        slug = slugify(obligation_text[:50], separator='_')  # Use first 50 chars
        return f"http://proethica.ai/ontology#{slug}_obligation"
