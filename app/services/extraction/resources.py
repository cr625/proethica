"""
Resources Extractor - Extraction of decision-making resources from guidelines.

This implements Checkpoint 3 of the 9-component extraction plan:
Resources (Rs) - Documents, tools, or knowledge sources used to guide ethical decision-making.
"""

from __future__ import annotations

from typing import List, Optional, Set, Any, Dict
import os
import re
from slugify import slugify

from .base import ConceptCandidate, MatchedConcept, SemanticTriple, Extractor, Linker
from .atomic_extraction_mixin import AtomicExtractionMixin
from .policy_gatekeeper import RelationshipPolicyGatekeeper
from models import ModelConfig

# LLM utils are optional at runtime; import guarded
try:
    from app.utils.llm_utils import get_llm_client
except Exception:  # pragma: no cover - environment without Flask/LLM
    get_llm_client = None  # type: ignore


class ResourcesExtractor(Extractor, AtomicExtractionMixin):
    """Extract resources used for ethical decision-making from guidelines.
    
    Resources include codes of ethics, standards, guidelines, tools, documents,
    and other knowledge sources that professionals use to make ethical decisions.
    """

    def __init__(self, provider: Optional[str] = None) -> None:
        # provider hint: 'anthropic'|'openai'|'gemini'|'auto'|None
        self.provider = (provider or 'auto').lower()
    
    @property
    def concept_type(self) -> str:
        """The concept type this extractor handles."""
        return 'resource'

    def extract(self, text: str, *, world_id: Optional[int] = None, guideline_id: Optional[int] = None, activity=None) -> List[ConceptCandidate]:
        """Extract resources from guideline text with provenance tracking.
        
        Args:
            text: Guideline content to extract from
            world_id: World context for ontology matching
            guideline_id: Guideline ID for tracking
            activity: Optional ProvenanceActivity for tracking LLM interactions
            
        Returns:
            List of ConceptCandidate objects for resources
        """
        if not text:
            return []

        # Try provider-backed extraction first when configured and client available
        if self.provider != 'heuristic' and get_llm_client is not None:
            try:
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"ResourcesExtractor: Attempting LLM extraction with provider {self.provider}")
                items = self._extract_with_llm(text, activity=activity)
                logger.info(f"ResourcesExtractor: LLM returned {len(items) if items else 0} items")
                if items:
                    logger.info(f"ResourcesExtractor: First item: {items[0] if items else 'None'}")
                    candidates = [
                        ConceptCandidate(
                            label=i.get('label') or i.get('resource') or i.get('name') or '',
                            description=i.get('description') or i.get('explanation') or None,
                            primary_type='resource',
                            category='resource',
                            confidence=float(i.get('confidence', 0.65)) if isinstance(i.get('confidence', 0.65), (int, float, str)) else 0.65,
                            debug={
                                'source': 'provider', 
                                'provider': self.provider,
                                # Add ALL enhanced prompt fields
                                'resource_category': i.get('resource_category'),  # professional_code, case_precedent, etc.
                                'extensional_function': i.get('extensional_function'),
                                'professional_knowledge_type': i.get('professional_knowledge_type'),
                                'usage_context': i.get('usage_context', []),
                                'text_references': i.get('text_references', []),
                                'theoretical_grounding': i.get('theoretical_grounding'),
                                'authority_level': i.get('authority_level'),
                                'importance': i.get('importance'),
                                'is_existing': i.get('is_existing'),
                                'ontology_match_reasoning': i.get('ontology_match_reasoning'),
                                # Store complete raw data for full preservation
                                'raw_llm_data': i
                            }
                        )
                        for i in items
                        if (i.get('label') or i.get('resource') or i.get('name'))
                    ]
                    # Apply unified atomic splitting to LLM results
                    return self._apply_atomic_splitting(candidates)
            except Exception:
                # Fall through to heuristic if provider path fails
                pass
                
        # Heuristic extraction as fallback
        candidates = self._extract_heuristic(text, guideline_id)
        
        # Apply unified atomic splitting
        return self._apply_atomic_splitting(candidates)

    def _get_prompt_for_preview(self, text: str) -> str:
        """Get the actual prompt that will be sent to the LLM, including MCP context."""
        # Always use external MCP (required for system to function)
        return self._create_resources_prompt_with_mcp(text)

    def _extract_heuristic(self, text: str, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """Heuristic extraction based on resource keywords and patterns."""
        sentences = re.split(r"(?<=[\.!?])\s+", text.strip())
        
        # Resource keywords and patterns
        resource_patterns = [
            # Codes and standards
            r"\b([A-Z]{2,6}\s+(?:Code|Standard|Guideline|Ethics|Policy))\b",
            r"\b(Code of Ethics|Professional Code|Ethical Guidelines|Standards of Practice)\b",
            r"\b(NSPE Code|IEEE Code|ASCE Code|Professional Standards)\b",
            # Documents and publications
            r"\b(handbook|manual|guide|reference|documentation|specification|regulation)\b",
            # Legal and regulatory resources
            r"\b(law|regulation|statute|ordinance|policy|procedure|rule)\b",
            # Professional resources
            r"\b(best practices|industry standards|technical standards|professional guidelines)\b",
            # Tools and systems
            r"\b(decision framework|assessment tool|evaluation criteria|checklist|methodology)\b",
            # Knowledge sources
            r"\b(precedent|case study|expert opinion|consultation|advisory|counsel)\b"
        ]
        
        seen: Set[str] = set()
        results: List[ConceptCandidate] = []
        
        for sentence in sentences:
            if not sentence:
                continue
                
            for pattern in resource_patterns:
                matches = re.finditer(pattern, sentence, re.IGNORECASE)
                for match in matches:
                    matched_text = match.group(0)
                    
                    # Expand context to capture full resource names
                    start = max(0, match.start() - 20)
                    end = min(len(sentence), match.end() + 30)
                    context = sentence[start:end].strip()
                    
                    # Try to extract a more complete resource name
                    label = self._extract_resource_name(matched_text, context, sentence)
                    
                    # Normalize for deduplication
                    key = label.lower().strip()
                    if key in seen or len(key) < 3:
                        continue
                    seen.add(key)
                    
                    # Truncate overly long labels
                    display_label = label if len(label) <= 100 else label[:97] + '…'
                    
                    # Classify the type of resource
                    resource_type = self._classify_resource_type(matched_text, context)
                    
                    results.append(ConceptCandidate(
                        label=display_label,
                        description=f"Resource: {label}" if display_label != label else None,
                        primary_type='resource',
                        category='resource',
                        confidence=0.65,
                        debug={
                            'source': 'heuristic_patterns',
                            'resource_type': resource_type,
                            'pattern_matched': pattern,
                            'guideline_id': guideline_id
                        }
                    ))
        
        return results

    def _extract_resource_name(self, matched_text: str, context: str, full_sentence: str) -> str:
        """Extract a complete resource name from the matched text and context."""
        # For codes and standards, try to get the full name
        if re.search(r'\b(code|standard|guideline|policy)\b', matched_text, re.IGNORECASE):
            # Look for organization acronyms before the matched text
            org_pattern = r'\b([A-Z]{2,6})\s+' + re.escape(matched_text)
            org_match = re.search(org_pattern, full_sentence, re.IGNORECASE)
            if org_match:
                return org_match.group(0)
                
        # For other resources, prefer the context if it's more descriptive
        if len(context) > len(matched_text) + 5 and len(context) <= 80:
            return context
            
        return matched_text

    def _classify_resource_type(self, matched_text: str, context: str) -> str:
        """Classify the type of resource based on the matched text and context."""
        text_lower = (matched_text + " " + context).lower()
        
        if any(word in text_lower for word in ['code', 'ethics', 'professional code']):
            return 'ethics_code'
        elif any(word in text_lower for word in ['standard', 'specification', 'technical']):
            return 'technical_standard'
        elif any(word in text_lower for word in ['law', 'regulation', 'statute', 'legal']):
            return 'legal_resource'
        elif any(word in text_lower for word in ['guideline', 'best practices', 'procedure']):
            return 'guidance_document'
        elif any(word in text_lower for word in ['tool', 'framework', 'methodology', 'assessment']):
            return 'decision_tool'
        elif any(word in text_lower for word in ['handbook', 'manual', 'reference', 'guide']):
            return 'reference_document'
        elif any(word in text_lower for word in ['precedent', 'case study', 'consultation']):
            return 'knowledge_source'
        else:
            return 'general_resource'

    # ---- Provider-backed helpers ----

    def _extract_with_llm(self, text: str, activity=None) -> List[Dict[str, Any]]:
        """Call configured LLM provider to extract resources with provenance tracking.

        Returns a list of dicts with keys like label, description, confidence.
        """
        from app.services.provenance_service import get_provenance_service
        import logging
        logger = logging.getLogger(__name__)

        client = get_llm_client() if get_llm_client else None
        if client is None:
            logger.warning("ResourcesExtractor: No LLM client available")
            return []

        logger.info("ResourcesExtractor: LLM client available, generating prompt")
        prov = get_provenance_service() if activity else None

        # Always use external MCP (required for system to function)
        prompt = self._create_resources_prompt_with_mcp(text)
        logger.info(f"ResourcesExtractor: Generated prompt length: {len(prompt)} chars")
        
        # Record the prompt if provenance tracking is active
        prompt_entity = None
        if prov and activity:
            prompt_entity = prov.record_prompt(
                prompt_text=prompt,
                activity=activity,
                entity_name="resources_extraction_prompt",
                metadata={
                    'extraction_type': 'resources',
                    'prompt_length': len(prompt),
                    'uses_mcp': use_external_mcp
                }
            )

        # Try Google Gemini style first
        try:
            if hasattr(client, 'GenerativeModel'):
                model_name = os.getenv('GEMINI_MODEL', 'gemini-1.5-pro')
                model = client.GenerativeModel(model_name)
                resp = model.generate_content(prompt)
                output = getattr(resp, 'text', None) or (resp.candidates[0].content.parts[0].text if getattr(resp, 'candidates', None) else '')
                
                # Record response if provenance tracking is active
                if prov and activity and prompt_entity:
                    prov.record_response(
                        response_text=output,
                        activity=activity,
                        derived_from=prompt_entity,
                        entity_name="resources_extraction_response",
                        metadata={
                            'model': model_name,
                            'model_params': {'provider': 'gemini'},
                            'extraction_type': 'resources'
                        }
                    )
                
                return self._parse_json_items(output, root_key='resources')
        except Exception:
            pass

        # Try Anthropic messages API
        try:
            if hasattr(client, 'messages') and hasattr(client.messages, 'create'):
                model = ModelConfig.get_claude_model("powerful")  # Use Opus 4.1 for better extraction
                resp = client.messages.create(
                    model=model,
                    max_tokens=800,
                    temperature=0,
                    system=(
                        "Extract resources and decision-making tools from text and output ONLY JSON with key 'resources'."
                    ),
                    messages=[{"role": "user", "content": prompt}],
                )
                # Newer SDK returns content list with .text
                content = getattr(resp, 'content', None)
                if content and isinstance(content, list) and len(content) > 0:
                    text_out = getattr(content[0], 'text', None) or str(content[0])
                else:
                    text_out = getattr(resp, 'text', None) or str(resp)
                
                # Record response if provenance tracking is active
                if prov and activity and prompt_entity:
                    response_metadata = {
                        'model': model,
                        'model_params': {'max_tokens': 800, 'temperature': 0, 'provider': 'anthropic'},
                        'extraction_type': 'resources'
                    }
                    
                    # Add usage metadata if available
                    if hasattr(resp, 'usage'):
                        response_metadata['usage'] = {
                            'input_tokens': getattr(resp.usage, 'input_tokens', None),
                            'output_tokens': getattr(resp.usage, 'output_tokens', None),
                            'total_tokens': getattr(resp.usage, 'total_tokens', None)
                        }
                    
                    prov.record_response(
                        response_text=text_out,
                        activity=activity,
                        derived_from=prompt_entity,
                        entity_name="resources_extraction_response",
                        metadata=response_metadata
                    )
                
                return self._parse_json_items(text_out, root_key='resources')
        except Exception:
            pass

        # Try OpenAI Chat Completions
        try:
            if hasattr(client, 'chat') and hasattr(client.chat, 'completions'):
                model = os.getenv('OPENAI_CHAT_MODEL', 'gpt-4o-mini')
                resp = client.chat.completions.create(
                    model=model,
                    temperature=0,
                    messages=[{"role": "user", "content": prompt}],
                )
                text_out = resp.choices[0].message.content if getattr(resp, 'choices', None) else ''
                
                # Record response if provenance tracking is active
                if prov and activity and prompt_entity:
                    response_metadata = {
                        'model': model,
                        'model_params': {'temperature': 0, 'provider': 'openai'},
                        'extraction_type': 'resources'
                    }
                    
                    # Add usage metadata if available
                    if hasattr(resp, 'usage'):
                        response_metadata['usage'] = {
                            'prompt_tokens': resp.usage.prompt_tokens,
                            'completion_tokens': resp.usage.completion_tokens,
                            'total_tokens': resp.usage.total_tokens
                        }
                    
                    prov.record_response(
                        response_text=text_out,
                        activity=activity,
                        derived_from=prompt_entity,
                        entity_name="resources_extraction_response",
                        metadata=response_metadata
                    )
                
                return self._parse_json_items(text_out, root_key='resources')
        except Exception:
            pass

        return []

    def _create_resources_prompt(self, text: str) -> str:
        """Create standard resources extraction prompt."""
        # Import enhanced prompt if available, otherwise use standard
        try:
            from .enhanced_prompts_roles_resources import get_enhanced_resources_prompt
            return get_enhanced_resources_prompt(text, include_mcp_context=False)
        except ImportError:
            # Fallback to standard prompt
            return f"""
You are an ontology-aware extractor. From the guideline excerpt, list distinct resources and decision-making tools.

FOCUS: Extract resources that guide ethical decision-making and professional practice.

RESOURCE TYPES TO EXTRACT:
1. **Ethics Codes**: Professional codes of ethics (e.g., NSPE Code, IEEE Code)
2. **Technical Standards**: Industry standards, specifications, technical guidelines
3. **Legal Resources**: Laws, regulations, statutes, legal requirements
4. **Guidance Documents**: Best practices, procedures, professional guidelines
5. **Decision Tools**: Frameworks, methodologies, assessment tools, checklists
6. **Reference Materials**: Handbooks, manuals, guides, documentation
7. **Knowledge Sources**: Precedents, case studies, expert consultations

EXAMPLES:
- "NSPE Code of Ethics"
- "IEEE Standards"
- "Professional Engineering License Requirements"
- "Safety Assessment Framework"
- "Technical Design Standards"
- "Best Practices Guidelines"
- "Legal Precedents"

Return STRICT JSON with an array under key 'resources'. Each item: {{label, description, confidence}}.

Guideline excerpt:
{text}
"""

    def _create_resources_prompt_with_mcp(self, text: str) -> str:
        """Create enhanced resources prompt with external MCP ontology context."""
        try:
            # Import external MCP client
            from app.services.external_mcp_client import get_external_mcp_client
            import logging
            
            logger = logging.getLogger(__name__)
            logger.info("Fetching resources context from external MCP server...")
            
            external_client = get_external_mcp_client()
            
            # Get existing resources from ontology (if available)
            try:
                existing_resources = external_client.get_all_resource_entities()
            except AttributeError:
                # Method might not exist yet, fall back to empty
                existing_resources = []
            
            # Build ontology context
            ontology_context = "EXISTING RESOURCES IN ONTOLOGY:\n"
            if existing_resources:
                ontology_context += f"Found {len(existing_resources)} existing resource concepts:\n"
                for resource in existing_resources:  # Show all resources
                    label = resource.get('label', 'Unknown')
                    description = resource.get('description', 'No description')
                    ontology_context += f"- {label}: {description}\n"
            else:
                ontology_context += "No existing resources found in ontology (or method not available)\n"
            
            logger.info(f"Retrieved {len(existing_resources)} existing resources from external MCP for context")
            
            # Try to use enhanced prompt with MCP context
            try:
                from .enhanced_prompts_roles_resources import get_enhanced_resources_prompt
                return get_enhanced_resources_prompt(text, include_mcp_context=True, existing_resources=existing_resources)
            except ImportError:
                # Fallback to building context manually
                # Create enhanced prompt with ontology context
                enhanced_prompt = f"""
{ontology_context}

You are an ontology-aware extractor analyzing an ethics guideline to extract RESOURCES.

IMPORTANT: Consider the existing resources above when extracting. For each resource you extract:
1. Check if it matches an existing resource (mark as existing)
2. If it's genuinely new, mark as new
3. Provide clear reasoning for why it's new vs existing

FOCUS: Extract resources that guide ethical decision-making and professional practice.

RESOURCE TYPES TO EXTRACT:
1. **Ethics Codes**: Professional codes of ethics (e.g., NSPE Code, IEEE Code)
2. **Technical Standards**: Industry standards, specifications, technical guidelines
3. **Legal Resources**: Laws, regulations, statutes, legal requirements
4. **Guidance Documents**: Best practices, procedures, professional guidelines
5. **Decision Tools**: Frameworks, methodologies, assessment tools, checklists
6. **Reference Materials**: Handbooks, manuals, guides, documentation
7. **Knowledge Sources**: Precedents, case studies, expert consultations

EXAMPLES:
- "NSPE Code of Ethics" - Professional engineering ethics code
- "IEEE Standards" - Technical standards for electrical engineering
- "Safety Assessment Framework" - Tool for evaluating project safety
- "Professional Engineering License" - Legal requirement for practice
- "Technical Design Standards" - Guidelines for engineering design
- "Best Practices Manual" - Reference document for procedures

GUIDELINES:
- Extract tangible resources, documents, and tools
- Include both specific named resources and general categories
- Focus on resources that support decision-making
- Resources should be actionable sources of guidance or information

GUIDELINE TEXT:
{text}

OUTPUT FORMAT:
Return STRICT JSON with an array under key 'resources':
[
  {{
    "label": "NSPE Code of Ethics",
    "description": "National Society of Professional Engineers' code of ethical conduct", 
    "confidence": 0.9,
    "is_existing": false,
    "ontology_match_reasoning": "Similar to existing engineering codes but more specific"
  }}
]

Focus on accuracy over quantity. Extract only clear, unambiguous resources.
"""
            
            return enhanced_prompt
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to get external MCP context for resources: {e}")
            logger.info("Falling back to standard resources prompt")
            return self._create_resources_prompt(text)

    @staticmethod
    def _parse_json_items(raw: Optional[str], root_key: str) -> List[Dict[str, Any]]:
        """Best-effort parse of JSON content possibly wrapped in code fences."""
        if not raw:
            return []
        import json, re as _re
        s = raw.strip()
        # Strip markdown fences
        if s.startswith('```'):
            s = _re.sub(r"^```[a-zA-Z0-9]*\n|\n```$", "", s)
        # If it's a bare array, wrap into object
        try:
            if s.strip().startswith('['):
                arr = json.loads(s)
                return arr if isinstance(arr, list) else []
        except Exception:
            pass
        # Try as object with root_key
        try:
            obj = json.loads(s)
            val = obj.get(root_key)
            if isinstance(val, list):
                return val
        except Exception:
            # last resort: find first [...] block
            try:
                m = _re.search(r"\[(?:.|\n)*\]", s)
                if m:
                    return json.loads(m.group(0))
            except Exception:
                return []
        return []


class ResourcesLinker(Linker):
    """Link resources to roles and other concepts based on governance and usage relationships."""

    def __init__(self, gatekeeper: Optional[RelationshipPolicyGatekeeper] = None) -> None:
        self.gate = gatekeeper or RelationshipPolicyGatekeeper()

    def link(self, matches: List[MatchedConcept], *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[SemanticTriple]:
        """Generate governance and usage links between resources and other concepts."""
        triples: List[SemanticTriple] = []

        # Partition matched concepts by type
        resources = [m for m in matches if (m.candidate.primary_type or '').lower() == 'resource']
        roles = [m for m in matches if (m.candidate.primary_type or '').lower() in {'role', 'professionalrole', 'participantrole'}]

        # Link roles to resources they are governed by or use
        for role in roles:
            role_uri = (role.ontology_match or {}).get('uri')
            if not role_uri:
                continue

            for resource in resources:
                resource_uri = (resource.ontology_match or {}).get('uri')
                if not resource_uri:
                    continue
                    
                # Determine relationship type based on resource type
                resource_type = resource.candidate.debug.get('resource_type', 'general_resource')
                predicate_uri = self._get_resource_role_predicate(resource_type)
                
                if predicate_uri:
                    triples.append(
                        SemanticTriple(
                            subject_uri=role_uri,
                            predicate_uri=predicate_uri,
                            object_uri=resource_uri,
                            context={
                                'guideline_id': guideline_id, 
                                'resource_type': resource_type
                            } if guideline_id else {'resource_type': resource_type},
                            is_approved=False,
                        )
                    )

        return triples

    def _get_resource_role_predicate(self, resource_type: str) -> Optional[str]:
        """Get appropriate predicate for linking roles to resources."""
        resource_predicates = {
            'ethics_code': 'governedByCode',  # Professional roles are governed by codes
            'technical_standard': 'adheresToStandard',  # Roles follow technical standards
            'legal_resource': 'boundByLaw',  # Roles are bound by legal requirements
            'guidance_document': 'guidedBy',  # Roles are guided by best practices
            'decision_tool': 'usesTool',  # Roles use decision frameworks
            'reference_document': 'consultsWith',  # Roles consult reference materials
            'knowledge_source': 'drawsUpon',  # Roles draw upon knowledge sources
            'general_resource': 'utilizesResource'  # General usage relationship
        }
        return resource_predicates.get(resource_type, 'utilizesResource')


class SimpleResourceMatcher:
    """Assigns stable derived URIs for resources when no ontology match exists.

    URI scheme: urn:proethica:resource:<slug>
    """

    def match(self, candidates: List[ConceptCandidate], *, world_id: Optional[int] = None) -> List[MatchedConcept]:
        results: List[MatchedConcept] = []
        for c in candidates:
            slug = slugify(c.label or 'resource')
            uri = f"urn:proethica:resource:{slug}"
            results.append(MatchedConcept(
                candidate=c,
                ontology_match={'uri': uri, 'label': c.label, 'score': 0.65},
                chosen_parent=None,
                similarity=0.65,
                normalized_label=c.label,
                notes='derived: simple resource matcher'
            ))
        return results
