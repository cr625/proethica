"""
Enhanced prompts for Constraints extraction with MCP integration.
Part of Pass 2: Normative Requirements (Principles → Obligations → Constraints)
"""

import logging
from typing import List, Dict, Any, Optional
from app.services.extraction.base import ConceptCandidate

logger = logging.getLogger(__name__)

def create_enhanced_constraints_prompt(text: str, include_mcp_context: bool = False,
                                      existing_constraints: Optional[List[Dict[str, Any]]] = None,
                                      include_related_entities: bool = False) -> str:
    """
    Create an enhanced prompt for extracting constraints with MCP context.

    CRITICAL: Following the pattern from obligations fix - must fetch MCP data
    dynamically when include_mcp_context=True even if existing_constraints is None.

    Args:
        text: Input text to analyze
        include_mcp_context: Whether to include MCP ontology context
        existing_constraints: Pre-fetched constraints (optional)
        include_related_entities: Whether to fetch principles/obligations (for full pass only)

    Returns:
        Enhanced prompt with Pass 2 integration and MCP context
    """
    
    mcp_context = ""
    
    if include_mcp_context:
        try:
            # CRITICAL PATTERN: Fetch dynamically if not provided
            if existing_constraints is None:
                logger.info("Fetching constraint context from MCP server...")
                from app.services.external_mcp_client import get_external_mcp_client
                external_client = get_external_mcp_client()
                existing_constraints = external_client.get_all_constraint_entities()

                # Only get related Pass 2 entities if explicitly requested
                existing_principles = []
                existing_obligations = []
                if include_related_entities:
                    existing_principles = external_client.get_all_principle_entities()
                    existing_obligations = external_client.get_all_obligation_entities()
                    logger.info(f"Retrieved {len(existing_constraints)} constraints with {len(existing_principles)} principles and {len(existing_obligations)} obligations")
                else:
                    logger.info(f"Retrieved {len(existing_constraints)} constraints (related entities excluded for individual extraction)")
            else:
                # If constraints provided, only fetch related entities if requested
                existing_principles = []
                existing_obligations = []
                if include_related_entities:
                    from app.services.external_mcp_client import get_external_mcp_client
                    external_client = get_external_mcp_client()
                    existing_principles = external_client.get_all_principle_entities()
                    existing_obligations = external_client.get_all_obligation_entities()
            
            # Build hierarchical context for constraints
            constraint_context = organize_constraints_hierarchically(existing_constraints)
            
            # Build Pass 2 integration context only if related entities included
            if include_related_entities:
                pass2_context = f"""
==========================
PASS 2 INTEGRATION: NORMATIVE REQUIREMENTS
==========================

Pass 2 focuses on the normative requirements that guide professional behavior:

1. **PRINCIPLES** (Abstract Foundations - WHY):
   Found {len(existing_principles) if 'existing_principles' in locals() else 0} principles that provide ethical foundations
   - Examples: Public Welfare, Integrity, Competence
   - Function: Provide abstract guidance and justification

2. **OBLIGATIONS** (Concrete Requirements - WHAT MUST):
   Found {len(existing_obligations) if 'existing_obligations' in locals() else 0} obligations that specify duties
   - Examples: Must report violations, Must maintain competence
   - Function: Transform principles into specific requirements

3. **CONSTRAINTS** (Boundaries & Limits - WHAT CANNOT):
   Found {len(existing_constraints) if existing_constraints else 0} constraints that establish boundaries
   - Examples: Legal limits, Resource limitations, Jurisdictional bounds
   - Function: Define inviolable limits on acceptable actions

KEY RELATIONSHIPS:
- Principles generate Obligations (abstract → concrete)
- Obligations are bounded by Constraints (requirements ← limits)
- Constraints prevent violation of principles (boundaries protect values)

==========================
"""
            else:
                pass2_context = """
==========================
FOCUS: CONSTRAINTS ONLY
==========================

This is an individual extraction focusing solely on professional constraints.
Extract boundaries and limitations without referencing principles or obligations.
Focus on what CANNOT be done, what limits exist, and what boundaries constrain action.
==========================
"""
            
            mcp_context = f"""
{pass2_context}

EXISTING CONSTRAINTS IN ONTOLOGY:
---------------------------------
{constraint_context}

CRITICAL INSTRUCTIONS:
---------------------
1. CHECK EXISTING FIRST: Always check if a constraint matches an existing one
2. COMPLEMENT OBLIGATIONS: Constraints set boundaries that obligations must respect
3. CHAPTER 2 GROUNDING: Based on Section 2.2.9 literature:
   - Ganascia (2007): Defeasible constraints with justified exceptions
   - Dennis et al. (2016): Inviolable boundaries and dilemma resolution
   - Taddeo et al. (2024): Context-dependent tolerance thresholds
   - Kroll (2020): Legal vs ethical constraint interpretation
   - Arkin (2008): Ethical governor concept for boundary enforcement

CONSTRAINT TYPES TO IDENTIFY:
- Legal Constraints: Statutory requirements and legal boundaries
- Regulatory Constraints: Professional standards and regulations
- Resource Constraints: Time, budget, personnel limitations
- Competence Constraints: Capability and skill boundaries
- Jurisdictional Constraints: Authority and scope limits
- Procedural Constraints: Required processes and protocols
- Safety Constraints: Safety-critical boundaries
- Confidentiality Constraints: Information disclosure limits
"""
            
        except Exception as e:
            logger.error(f"Failed to fetch MCP context: {e}")
            mcp_context = """
NOTE: Could not fetch existing constraints from ontology.
Identify constraints based on Chapter 2 literature (Section 2.2.9):
- Boundaries that restrict or govern professional behavior
- Inviolable limits on acceptable actions
- Defeasible constraints that admit justified exceptions
"""
    
    prompt = f"""You are analyzing professional text to extract CONSTRAINTS - boundaries and limitations that restrict professional behavior.

TASK: Extract 8-10 constraints from the provided text.

{mcp_context}

TEXT TO ANALYZE:
--------------
{text}
--------------

EXTRACTION FRAMEWORK (Based on Chapter 2, Section 2.2.9):

1. **CONSTRAINT DEFINITION**: 
   - Boundaries that establish inviolable limits on acceptable actions
   - Complement obligations by defining what CANNOT be done
   - May be defeasible (admit exceptions) or inviolable (absolute)

2. **IDENTIFICATION CRITERIA**:
   - Look for: limitations, restrictions, boundaries, prohibitions
   - Legal/regulatory requirements that limit actions
   - Resource limitations (time, budget, personnel)
   - Competence boundaries (skill/capability limits)
   - Jurisdictional limits (authority boundaries)
   - Procedural requirements that constrain flexibility

3. **RELATIONSHIP TO OBLIGATIONS**:
   - Obligations specify what MUST be done
   - Constraints specify what CANNOT be done
   - Together they define the normative space for action

4. **VALIDATION QUESTIONS**:
   - Does this establish a boundary or limit?
   - Does it restrict what can be done?
   - Is it about capability, authority, or resource limits?
   - Does it prevent certain actions or approaches?

IMPORTANT: Distinguish constraints from obligations:
- Obligation: "Must report safety violations" (required action)
- Constraint: "Cannot disclose without authorization" (prohibited action)
- Constraint: "Limited to areas of competence" (capability boundary)

OUTPUT FORMAT (JSON):
{{
  "constraints": [
    {{
      "label": "string",  // Clear, descriptive name
      "description": "string",  // How this constrains behavior
      "type": "string",  // legal|regulatory|resource|competence|jurisdictional|procedural|safety|confidentiality
      "defeasible": boolean,  // Can this constraint have exceptions?
      "source_quote": "string",  // Direct quote from text
      "is_existing": boolean,  // Found in ontology?
      "ontology_match": "string or null"  // Label of matching constraint if exists
    }}
  ],
  "extraction_metadata": {{
    "constraint_count": number,
    "types_found": ["list of types"],
    "pass2_integration": "How constraints complement principles and obligations"
  }}
}}

Remember: 
- Constraints establish BOUNDARIES, not requirements
- They work with obligations to define professional action space
- Check existing ontology constraints first
- Ground in Chapter 2 literature on professional boundaries
"""
    
    return prompt


def organize_constraints_hierarchically(constraints: List[Dict[str, Any]]) -> str:
    """
    Organize constraints into a hierarchical structure for display.
    
    Args:
        constraints: List of constraint entities from MCP
        
    Returns:
        Formatted string showing constraint hierarchy
    """
    if not constraints:
        return "No existing constraints found in ontology.\n"
    
    # Separate base and specific constraints
    base_constraint = None
    boundary_types = []
    defeasibility_types = []
    ethical_types = []
    temporal_types = []
    other_constraints = []
    
    for c in constraints:
        label = c.get('label', '')
        desc = c.get('description', '')
        
        if label == 'Constraint':
            base_constraint = c
        elif any(term in label for term in ['Legal', 'Regulatory', 'Resource', 'Competence', 
                                            'Jurisdictional', 'Procedural']):
            boundary_types.append(c)
        elif any(term in label for term in ['Defeasible', 'Inviolable']):
            defeasibility_types.append(c)
        elif any(term in label for term in ['Ethical', 'Safety', 'Confidentiality']):
            ethical_types.append(c)
        elif any(term in label for term in ['Temporal', 'Priority']):
            temporal_types.append(c)
        else:
            other_constraints.append(c)
    
    # Build formatted output - NO TRUNCATION, show full definitions
    output_lines = []
    
    if base_constraint:
        output_lines.append("BASE CLASS:")
        output_lines.append(f"- **{base_constraint['label']}**: {base_constraint.get('description', '')}")
        output_lines.append("")
    
    if boundary_types:
        output_lines.append("BOUNDARY TYPES (What limits exist):")
        for c in sorted(boundary_types, key=lambda x: x['label']):
            output_lines.append(f"- **{c['label']}**: {c.get('description', '')}")
        output_lines.append("")
    
    if defeasibility_types:
        output_lines.append("DEFEASIBILITY TYPES (Exception handling):")
        for c in sorted(defeasibility_types, key=lambda x: x['label']):
            output_lines.append(f"- **{c['label']}**: {c.get('description', '')}")
        output_lines.append("")
    
    if ethical_types:
        output_lines.append("ETHICAL BOUNDARY TYPES:")
        for c in sorted(ethical_types, key=lambda x: x['label']):
            output_lines.append(f"- **{c['label']}**: {c.get('description', '')}")
        output_lines.append("")
    
    if temporal_types:
        output_lines.append("TEMPORAL & PRIORITY TYPES:")
        for c in sorted(temporal_types, key=lambda x: x['label']):
            output_lines.append(f"- **{c['label']}**: {c.get('description', '')}")
        output_lines.append("")
    
    if other_constraints:
        output_lines.append("OTHER CONSTRAINTS:")
        for c in sorted(other_constraints, key=lambda x: x['label']):
            output_lines.append(f"- **{c['label']}**: {c.get('description', '')}")
        output_lines.append("")
    
    return "\n".join(output_lines)


# Literature grounding for constraint extraction prompts.
# These citations inform the theoretical framework section of the DB prompt template
# (extraction_prompt_templates id=6) and the chapter 2 discussion of constraints.
CONSTRAINT_LITERATURE = {
    'Ganascia2007': "Ethical rules as default rules with justified exceptions",
    'Dennis2016': "Formal verification ensuring compliance even in dilemmas",
    'Taddeo2024': "Context-dependent tolerance thresholds for constraint balancing",
    'Kroll2020': "Legal obligations require interpretation beyond rule enforcement",
    'Arkin2008': "Ethical governor concept - preventive control filtering unacceptable actions",
    'Furbach2014': "Deontic logic formalizing professional constraints",
    'Benzmüller2020': "Distinction between normative ideals and concrete deontic operators",
}
