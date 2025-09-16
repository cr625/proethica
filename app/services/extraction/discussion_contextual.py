"""
Discussion Contextual Framework Extractor
Implements dual analysis (independent + contextual) for Pass 1 entities
Focuses on Roles, States, and Resources extraction from Discussion sections
"""

from typing import Dict, List, Optional, Any
import json
import logging

logger = logging.getLogger(__name__)


class DiscussionContextualExtractor:
    """
    Specialized extractor for Discussion section Pass 1 entities
    Implements dual analysis approach with Facts context integration
    """
    
    def __init__(self):
        self.entity_types = ['roles', 'states', 'resources']
        
    def create_independent_prompt(self, text: str, include_mcp_context: bool = False,
                                 existing_roles: Optional[List] = None,
                                 existing_states: Optional[List] = None,
                                 existing_resources: Optional[List] = None) -> str:
        """
        Create prompt for independent Discussion analysis (without Facts context)
        Focuses on Pass 1 entities emerging from professional reasoning
        """
        
        # Dynamic MCP fetching if requested
        if include_mcp_context:
            existing_roles = self._fetch_existing_roles(existing_roles)
            existing_states = self._fetch_existing_states(existing_states)
            existing_resources = self._fetch_existing_resources(existing_resources)
        
        prompt = f"""## INDEPENDENT DISCUSSION ANALYSIS - CONTEXTUAL FRAMEWORK PASS

Analyze the following professional ethics discussion to extract contextual framework entities.
Focus on entities that emerge from the discussion's reasoning alone, without reference to other sections.

**DISCUSSION TEXT:**
{text}

**EXTRACTION TASK:**
Extract THREE types of contextual framework entities from this discussion:

### 1. ROLES (WHO) - Professional Identities in Ethical Reasoning
Extract professional roles and stakeholder identities mentioned or implied in the discussion.
Focus on:
- Professional identities referenced in ethical analysis
- Stakeholder roles considered in the reasoning
- Relationships and responsibilities discussed
- Authority figures or decision-makers mentioned

### 2. STATES (WHEN/WHERE) - Environmental Contexts and Conditions
Extract environmental states, conditions, or situations described in the discussion.
Focus on:
- Ethical situations or dilemmas analyzed
- Professional contexts described
- Conflict states or tensions identified
- Environmental conditions affecting ethical judgment

### 3. RESOURCES (WHAT) - Knowledge Sources and References
Extract knowledge resources, standards, or authorities referenced in the discussion.
Focus on:
- Professional codes or standards cited
- Ethical frameworks or theories mentioned
- Precedents or case law referenced
- Expert opinions or authoritative sources
"""

        # Add existing entities context if available
        if existing_roles:
            prompt += self._format_existing_entities("ROLES", existing_roles)
        if existing_states:
            prompt += self._format_existing_entities("STATES", existing_states)
        if existing_resources:
            prompt += self._format_existing_entities("RESOURCES", existing_resources)
            
        prompt += """

**OUTPUT FORMAT:**
Provide a JSON object with three arrays: roles, states, and resources.
Each entity should include:
- label: Short identifier (2-4 words)
- description: Detailed explanation from the discussion context
- confidence: Score between 0.0 and 1.0
- discussion_context: Specific reference to how this appears in the discussion

Example structure:
{
  "roles": [
    {
      "label": "Senior Engineer",
      "description": "Professional with supervisory responsibilities discussed in ethical analysis",
      "confidence": 0.9,
      "discussion_context": "Referenced when analyzing responsibility hierarchy"
    }
  ],
  "states": [...],
  "resources": [...]
}

**IMPORTANT:** Extract ONLY entities explicitly present or strongly implied in the discussion text.
"""
        return prompt
    
    def create_contextual_prompt(self, text: str, facts_context: Dict[str, Any],
                                include_mcp_context: bool = False,
                                existing_roles: Optional[List] = None,
                                existing_states: Optional[List] = None,
                                existing_resources: Optional[List] = None) -> str:
        """
        Create prompt for contextual Discussion analysis (with Facts context)
        Focuses on how Discussion relates to and extends Facts-based entities
        """
        
        # Dynamic MCP fetching if requested
        if include_mcp_context:
            existing_roles = self._fetch_existing_roles(existing_roles)
            existing_states = self._fetch_existing_states(existing_states)
            existing_resources = self._fetch_existing_resources(existing_resources)
        
        # Extract Facts entities for context
        facts_roles = facts_context.get('roles', [])
        facts_states = facts_context.get('states', [])
        facts_resources = facts_context.get('resources', [])
        
        prompt = f"""## CONTEXTUAL DISCUSSION ANALYSIS - WITH FACTS AWARENESS

Analyze the professional ethics discussion in relation to established factual context.
Focus on how the discussion elaborates, extends, or provides new perspective on facts-based entities.

**ESTABLISHED FACTS CONTEXT:**
- Roles identified in Facts: {self._summarize_entities(facts_roles)}
- States identified in Facts: {self._summarize_entities(facts_states)}
- Resources identified in Facts: {self._summarize_entities(facts_resources)}

**DISCUSSION TEXT TO ANALYZE:**
{text}

**CONTEXTUAL EXTRACTION OBJECTIVES:**

### 1. ELABORATION - How Discussion Expands Facts Entities
Identify how the discussion:
- Provides deeper analysis of Facts-identified roles
- Reveals additional responsibilities or relationships
- Clarifies ambiguous factual states
- Adds professional judgment to factual situations

### 2. EXTENSION - New Entities Emerging from Analysis
Extract entities that:
- Emerge from professional reasoning about the facts
- Represent ethical considerations beyond factual description
- Include theoretical or normative roles/states not in facts
- Reference additional resources for ethical guidance

### 3. TENSION IDENTIFICATION - Conflicts and Complexities
Identify where discussion reveals:
- Conflicting role responsibilities
- Tensions between different states or conditions
- Disagreements about resource applicability
- Ethical complexities not apparent in facts alone

### 4. RELATIONSHIP MAPPING - Facts-Discussion Connections
Show how discussion entities relate to facts entities:
- Which facts entities are analyzed in discussion
- How discussion reframes factual entities
- What new relationships are revealed
"""

        # Add existing MCP entities if available
        if existing_roles:
            prompt += self._format_existing_entities("ROLES", existing_roles)
        if existing_states:
            prompt += self._format_existing_entities("STATES", existing_states)
        if existing_resources:
            prompt += self._format_existing_entities("RESOURCES", existing_resources)
            
        prompt += """

**OUTPUT FORMAT:**
Provide a JSON object with contextual analysis results:
{
  "elaborated_entities": {
    "roles": [
      {
        "label": "Engineer A",
        "facts_reference": "Originally identified as project engineer",
        "discussion_elaboration": "Discussion reveals whistleblower responsibilities",
        "confidence": 0.85
      }
    ],
    "states": [...],
    "resources": [...]
  },
  "new_entities": {
    "roles": [...],
    "states": [...],
    "resources": [...]
  },
  "identified_tensions": [
    {
      "type": "role_conflict",
      "description": "Tension between Engineer A's loyalty to employer vs public safety",
      "entities_involved": ["Engineer A", "Public Safety Obligation"]
    }
  ],
  "facts_discussion_relationships": [
    {
      "facts_entity": "Structural Deficiency State",
      "discussion_analysis": "Explored through lens of professional negligence",
      "relationship_type": "analytical_elaboration"
    }
  ]
}

**FOCUS:** Show how professional reasoning in discussion enriches understanding of factual circumstances.
"""
        return prompt
    
    def create_consolidated_prompt(self, independent_results: Dict, contextual_results: Dict) -> str:
        """
        Create prompt for consolidating independent and contextual analysis results
        """
        
        prompt = f"""## CONSOLIDATION OF DUAL ANALYSIS RESULTS

Merge and synthesize the results from independent and contextual analysis of the Discussion section.

**INDEPENDENT ANALYSIS RESULTS:**
{json.dumps(independent_results, indent=2)}

**CONTEXTUAL ANALYSIS RESULTS:**
{json.dumps(contextual_results, indent=2)}

**CONSOLIDATION OBJECTIVES:**

1. **MERGE ENTITIES** - Combine unique entities from both analyses
   - Eliminate duplicates while preserving unique insights
   - Prefer contextual elaborations over simple descriptions
   - Maintain highest confidence scores

2. **PRESERVE TENSIONS** - Keep identified conflicts and complexities
   - Document where independent and contextual analyses differ
   - Maintain multiple perspectives on controversial entities

3. **BUILD LAYERED UNDERSTANDING** - Create comprehensive view
   - Show both abstract reasoning and situational application
   - Highlight entities that appear in only one analysis
   - Note enrichments from contextual analysis

**OUTPUT FORMAT:**
{
  "consolidated_entities": {
    "roles": [
      {
        "label": "Entity Label",
        "description": "Comprehensive description combining insights",
        "confidence": 0.9,
        "source": "both|independent|contextual",
        "enrichment_notes": "How contextual analysis enriched understanding"
      }
    ],
    "states": [...],
    "resources": [...]
  },
  "preserved_tensions": [
    {
      "description": "Description of tension or conflict",
      "entities_involved": ["Entity1", "Entity2"],
      "resolution_notes": "How or if tension was resolved"
    }
  ],
  "analysis_insights": {
    "unique_to_independent": ["Entities only found in independent analysis"],
    "unique_to_contextual": ["Entities only found with facts context"],
    "enriched_by_context": ["Entities significantly enhanced by contextual analysis"]
  }
}
"""
        return prompt
    
    def consolidate_results(self, independent: Dict, contextual: Dict) -> Dict:
        """
        Consolidate independent and contextual analysis results
        """
        consolidated = {
            'roles': [],
            'states': [],
            'resources': [],
            'analysis_metadata': {
                'approach': 'dual_analysis',
                'independent_count': 0,
                'contextual_count': 0,
                'consolidated_count': 0,
                'tensions_identified': []
            }
        }
        
        # Process each entity type
        for entity_type in self.entity_types:
            independent_entities = independent.get(entity_type, [])
            
            # Handle different contextual result structures
            contextual_entities = []
            if contextual:
                if 'elaborated_entities' in contextual:
                    contextual_entities.extend(contextual['elaborated_entities'].get(entity_type, []))
                if 'new_entities' in contextual:
                    contextual_entities.extend(contextual['new_entities'].get(entity_type, []))
                else:
                    contextual_entities = contextual.get(entity_type, [])
            
            # Merge entities
            merged = self._merge_entity_lists(independent_entities, contextual_entities)
            consolidated[entity_type] = merged
            
            # Update metadata
            consolidated['analysis_metadata']['independent_count'] += len(independent_entities)
            consolidated['analysis_metadata']['contextual_count'] += len(contextual_entities)
            consolidated['analysis_metadata']['consolidated_count'] += len(merged)
        
        # Add identified tensions if available
        if contextual and 'identified_tensions' in contextual:
            consolidated['analysis_metadata']['tensions_identified'] = contextual['identified_tensions']
        
        return consolidated
    
    def _merge_entity_lists(self, list1: List[Dict], list2: List[Dict]) -> List[Dict]:
        """
        Merge two lists of entities, eliminating duplicates and preserving unique insights
        """
        merged = {}
        
        # Add all entities from list1
        for entity in list1:
            key = entity.get('label', '').lower()
            merged[key] = entity.copy()
            merged[key]['source'] = 'independent'
        
        # Merge or add entities from list2
        for entity in list2:
            key = entity.get('label', '').lower()
            if key in merged:
                # Merge with existing entity
                existing = merged[key]
                existing['source'] = 'both'
                # Take higher confidence
                existing['confidence'] = max(
                    existing.get('confidence', 0),
                    entity.get('confidence', 0)
                )
                # Combine descriptions if different
                if entity.get('description') != existing.get('description'):
                    existing['enrichment_notes'] = entity.get('description', '')
            else:
                # Add new entity
                merged[key] = entity.copy()
                merged[key]['source'] = 'contextual'
        
        return list(merged.values())
    
    def _fetch_existing_roles(self, existing_roles: Optional[List]) -> List:
        """
        Fetch existing role entities from MCP if not provided
        """
        if existing_roles is None:
            try:
                from app.services.external_mcp_client import get_external_mcp_client
                external_client = get_external_mcp_client()
                existing_roles = external_client.get_all_role_entities()
                logger.info(f"Fetched {len(existing_roles)} existing role entities from MCP")
            except Exception as e:
                logger.warning(f"Could not fetch existing roles from MCP: {e}")
                existing_roles = []
        return existing_roles
    
    def _fetch_existing_states(self, existing_states: Optional[List]) -> List:
        """
        Fetch existing state entities from MCP if not provided
        """
        if existing_states is None:
            try:
                from app.services.external_mcp_client import get_external_mcp_client
                external_client = get_external_mcp_client()
                existing_states = external_client.get_all_state_entities()
                logger.info(f"Fetched {len(existing_states)} existing state entities from MCP")
            except Exception as e:
                logger.warning(f"Could not fetch existing states from MCP: {e}")
                existing_states = []
        return existing_states
    
    def _fetch_existing_resources(self, existing_resources: Optional[List]) -> List:
        """
        Fetch existing resource entities from MCP if not provided
        """
        if existing_resources is None:
            try:
                from app.services.external_mcp_client import get_external_mcp_client
                external_client = get_external_mcp_client()
                existing_resources = external_client.get_all_resource_entities()
                logger.info(f"Fetched {len(existing_resources)} existing resource entities from MCP")
            except Exception as e:
                logger.warning(f"Could not fetch existing resources from MCP: {e}")
                existing_resources = []
        return existing_resources
    
    def _format_existing_entities(self, entity_type: str, entities: List) -> str:
        """
        Format existing entities for inclusion in prompt
        """
        if not entities:
            return ""
            
        output = f"\n\n**EXISTING {entity_type} IN ONTOLOGY:**\n"
        for entity in entities[:10]:  # Limit to first 10 for brevity
            label = entity.get('label', 'Unknown')
            description = entity.get('comment', entity.get('description', 'No description'))
            output += f"- **{label}**: {description}\n"
        
        if len(entities) > 10:
            output += f"... and {len(entities) - 10} more\n"
            
        output += f"\n*Note: Build upon these existing {entity_type.lower()} where appropriate.*\n"
        return output
    
    def _summarize_entities(self, entities: List[Dict]) -> str:
        """
        Create a brief summary of entities for context
        """
        if not entities:
            return "None identified"
        
        labels = [e.get('label', 'Unknown') for e in entities[:5]]
        summary = ", ".join(labels)
        
        if len(entities) > 5:
            summary += f" (and {len(entities) - 5} more)"
            
        return summary


# Convenience functions for direct use
def create_discussion_contextual_prompt(text: str, facts_context: Optional[Dict] = None,
                                       include_mcp_context: bool = False) -> Dict[str, str]:
    """
    Create both independent and contextual prompts for Discussion analysis
    Returns dict with 'independent' and 'contextual' prompts
    """
    extractor = DiscussionContextualExtractor()
    
    prompts = {
        'independent': extractor.create_independent_prompt(text, include_mcp_context),
        'contextual': None
    }
    
    if facts_context:
        prompts['contextual'] = extractor.create_contextual_prompt(
            text, facts_context, include_mcp_context
        )
    
    return prompts


def consolidate_discussion_results(independent: Dict, contextual: Dict) -> Dict:
    """
    Consolidate results from dual Discussion analysis
    """
    extractor = DiscussionContextualExtractor()
    return extractor.consolidate_results(independent, contextual)
