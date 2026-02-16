"""
Enhanced Obligations Extraction with Chapter 2 Literature Grounding
Based on Pass 2: Normative (SHOULD/MUST/CAN'T) - Professional Duties

This module implements obligation extraction grounded in professional ethics literature,
particularly focusing on transforming abstract principles into concrete professional duties
and responsibilities that can be monitored and enforced.
"""

from typing import List, Dict, Any, Optional
import logging
import json
from datetime import datetime

from .base import ConceptCandidate

# Optional provenance tracking
try:
    from app.models.provenance import ProvenanceActivity
    from app.services.provenance_service import get_provenance_service
except ImportError:
    ProvenanceActivity = None
    get_provenance_service = lambda: None

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Temporarily enable DEBUG for troubleshooting


def create_enhanced_obligations_prompt(text: str, include_mcp_context: bool = False, existing_obligations: list = None, include_principles: bool = False) -> str:
    """
    Create an enhanced prompt for obligation extraction based on professional ethics literature.

    Theoretical foundations:
    - NSPE Code of Ethics: Must/shall statements defining professional duties
    - Dennis et al. (2016): Obligations derived from role-principle combinations
    - Wooldridge & Jennings (1995): Obligations as behavioral constraints with deontic force
    - Kong et al. (2020): Context-dependent obligations requiring professional judgment
    - Hallamaa & Kalliokoski (2022): Obligations operationalize abstract principles

    Args:
        text: The text to analyze for obligations
        include_mcp_context: Whether to include MCP ontology context
        existing_obligations: Pre-fetched obligations (optional)
        include_principles: Whether to also fetch and include principles context (for full normative pass)
    """
    
    mcp_context = ""
    if include_mcp_context:
        try:
            # If existing_obligations not provided, fetch from MCP server
            if existing_obligations is None:
                from app.services.external_mcp_client import get_external_mcp_client
                import logging
                
                logger = logging.getLogger(__name__)
                logger.info("Fetching obligations context from external MCP server...")
                
                external_client = get_external_mcp_client()
                existing_obligations = external_client.get_all_obligation_entities()

                # Only get existing principles if explicitly requested (for full normative pass)
                existing_principles = []
                if include_principles:
                    existing_principles = external_client.get_all_principle_entities()
                    logger.info(f"Retrieved {len(existing_obligations)} obligations and {len(existing_principles)} principles from MCP")
                else:
                    logger.info(f"Retrieved {len(existing_obligations)} obligations from MCP (principles excluded for individual extraction)")
            else:
                existing_principles = []
                # If obligations provided and principles needed, fetch them
                if include_principles:
                    try:
                        from app.services.external_mcp_client import get_external_mcp_client
                        external_client = get_external_mcp_client()
                        existing_principles = external_client.get_all_principle_entities()
                    except:
                        existing_principles = []
        
            # Organize obligations hierarchically
            base_obligation = None
            specific_obligations = []
            
            # De-duplicate and organize
            seen_labels = set()
            for obligation in existing_obligations:
                label = obligation.get('label', '')
                if label in seen_labels:
                    continue
                seen_labels.add(label)
                
                description = obligation.get('description', obligation.get('definition', ''))
                
                # Organize by hierarchy
                if label == 'Obligation':
                    if not base_obligation:
                        base_obligation = {'label': label, 'definition': description}
                else:
                    specific_obligations.append({'label': label, 'definition': description})
            
            # Build hierarchical context - NO TRUNCATION
            mcp_context = f"""
EXISTING OBLIGATIONS IN ONTOLOGY (Hierarchical View):
Found {len(seen_labels)} obligation concepts organized by hierarchy:

**BASE CLASS:**
- **{base_obligation['label'] if base_obligation else 'Obligation'}**: {base_obligation['definition'] if base_obligation else 'Concrete professional duties that must be performed, derived from principles and activated by role-state combinations.'}
  (This is the parent class for all obligation concepts)

**SPECIFIC OBLIGATIONS (Direct instances):**
"""
            for spec in sorted(specific_obligations, key=lambda x: x['label']):
                mcp_context += f"- **{spec['label']}**: {spec['definition']}\n"
            
            # Only add Pass 2 integration context if principles are included
            if include_principles:
                mcp_context += """
**PASS 2 INTEGRATION (Principles → OBLIGATIONS → Constraints + Capabilities):**
Obligations operationalize abstract principles into concrete duties:
- Principles provide the WHY (ethical foundations)
- Obligations specify the WHAT (concrete duties)
- Constraints limit HOW obligations can be fulfilled
- Capabilities determine WHO can fulfill obligations

Example: "Public Welfare Principle" → "Must report safety hazards" (Obligation)

**RELATIONSHIP TO PRINCIPLES:**
Each obligation should trace back to one or more principles that justify it.
This transforms abstract values into actionable requirements.
"""

                # Add principle names if available
                if 'existing_principles' in locals() and existing_principles:
                    mcp_context += "\n**Available Principles for Reference:**\n"
                    principle_names = [p.get('label', '') for p in existing_principles if p.get('label')]
                    for principle in principle_names[:10]:  # Show first 10 principles
                        mcp_context += f"- {principle}\n"
            else:
                mcp_context += """
**FOCUS: OBLIGATIONS ONLY**
This is an individual extraction focusing solely on professional obligations.
Extract concrete duties and responsibilities without referencing principles.
Focus on MUST/SHALL/SHOULD statements that define professional requirements.
"""
                    
        except Exception as e:
            logger.error(f"Failed to fetch MCP context: {e}")
            mcp_context = """
ONTOLOGY CONTEXT:
Obligations in ProEthica represent concrete professional duties that:
- Transform abstract principles into specific requirements
- Use deontic operators (MUST, SHALL, SHOULD, MAY NOT)
- Can be monitored and enforced
- Arise from role-principle-state combinations
- May conflict, requiring professional judgment

Note: Could not fetch existing obligations from ontology server.
"""
    else:
        mcp_context = """
ONTOLOGY CONTEXT:
Obligations in ProEthica represent concrete professional duties that:
- Transform abstract principles into specific requirements
- Use deontic operators (MUST, SHALL, SHOULD, MAY NOT)
- Can be monitored and enforced
- Arise from role-principle-state combinations
- May conflict, requiring professional judgment

Note: No existing obligation instances found in ontology. All extracted obligations will be new.
"""
    
    prompt = f"""{mcp_context}

You are analyzing professional ethics text to extract OBLIGATIONS as part of Pass 2 (Normative Requirements) of the ProEthica extraction.

THEORETICAL FRAMEWORK - Key Insights from Normative Ethics Literature:

Obligations are not merely rules but concrete instantiations of ethical principles:
- **Principle Operationalization**: Abstract principles become actionable through obligations (Hallamaa & Kalliokoski 2022 analysis of professional codes)
- **Deontic Force**: Obligations carry normative force through modal operators (Wooldridge & Jennings 1995 formal semantics)
- **Role Activation**: Obligations activate based on professional roles and contexts (Dennis et al. 2016 empirical study)
- **Contextual Judgment**: Professional obligations require situational interpretation (Kong et al. 2020 case analysis)

**RELATIONSHIP TO PASS 2 (Normative Requirements):**
Obligations are the core of Pass 2, working with:
- **Principles** (upstream): Provide ethical justification for obligations
- **Constraints** (parallel): Limit how obligations can be fulfilled
- **Capabilities** (parallel): Determine who can fulfill obligations
1. Are derived from abstract principles and professional roles
2. Specify what professionals MUST, SHOULD, or MUST NOT do
3. Can be monitored, evaluated, and enforced
4. Apply to specific contexts and situations
5. May conflict with other obligations, requiring professional judgment

OBLIGATION CATEGORIES (from NSPE Code):
1. **Fundamental Duties**: Core obligations like public safety paramount
2. **Professional Practice**: Competence, honesty, objectivity requirements
3. **Disclosure Obligations**: Conflicts of interest, limitations, risks
4. **Collegial Duties**: Respect, fairness, credit for work
5. **Societal Responsibilities**: Sustainability, public welfare, truthfulness

EXTRACTION TASK:
Analyze the following discussion/analysis text and identify ALL professional obligations mentioned or implied.

For each obligation, provide:
1. **label**: A clear, action-oriented name (e.g., "Disclose Conflicts", "Maintain Competence")
2. **description**: What the obligation requires in this specific context
3. **obligation_type**: Category from above (fundamental_duty, professional_practice, etc.)
4. **enforcement_level**: mandatory, strongly_recommended, recommended, or conditional
5. **derived_from_principle**: Which principle(s) this obligation operationalizes
6. **stakeholders_affected**: Who is impacted by this obligation
7. **potential_conflicts**: Other obligations this might conflict with
8. **monitoring_criteria**: How compliance could be assessed
9. **nspe_reference**: Relevant NSPE Code section if applicable
10. **contextual_factors**: Situation-specific considerations

TEXT TO ANALYZE:
{text if isinstance(text, str) else str(text)}

**MATCH DECISION RULES:**
For each obligation, evaluate against existing ontology obligations listed above:
- If the obligation IS the same concept as an existing class: match with HIGH confidence (0.85-1.0)
- If the obligation is a VARIANT of an existing class: match to parent with MEDIUM confidence (0.70-0.85)
- If genuinely NEW: match_decision.matches_existing = false

IMPORTANT EXTRACTION GUIDELINES:
- Identify both explicit obligations ("must", "shall", "required") and implicit ones
- Look for professional duties implied by the situation
- Consider obligations from multiple stakeholder perspectives
- Distinguish between legal requirements and ethical obligations
- Note where professional judgment is required to resolve conflicts
- Include obligations that arise from the specific context, not just general duties

Return your analysis as a JSON array of obligation objects.
Each object should contain all fields specified above.
Focus on obligations that are:
1. Actionable and specific
2. Relevant to the case context
3. Grounded in professional ethics standards
4. Important for ethical decision-making

Example format:
[
    {{
        "label": "Disclose Design Limitations",
        "description": "Engineer must inform client about safety limitations of the proposed design",
        "obligation_type": "disclosure_obligation",
        "enforcement_level": "mandatory",
        "derived_from_principle": "Honesty and Transparency",
        "stakeholders_affected": ["client", "end users", "public"],
        "potential_conflicts": ["Client Confidentiality", "Project Timeline"],
        "monitoring_criteria": "Documentation of disclosure communications",
        "nspe_reference": "II.3.a - Engineers shall be objective and truthful",
        "contextual_factors": "Safety-critical infrastructure project",
        "match_decision": {{
            "matches_existing": true,
            "matched_uri": "http://proethica.org/ontology/intermediate#DisclosureObligation",
            "matched_label": "Disclosure Obligation",
            "confidence": 0.85,
            "reasoning": "This is a specific instance of the existing Disclosure Obligation class."
        }}
    }}
]

If no match exists, use:
    "match_decision": {{
        "matches_existing": false,
        "matched_uri": null,
        "matched_label": null,
        "confidence": 0.0,
        "reasoning": "This is a novel obligation not represented in the current ontology."
    }}
"""
    return prompt


# Literature grounding for obligation extraction prompts.
# These citations inform the theoretical framework section of the DB prompt template
# (extraction_prompt_templates id=5) and the chapter 2 discussion of obligations.
OBLIGATION_LITERATURE = {
    'Dennis2016': "Obligations derived from role-principle combinations; formal verification of compliance",
    'Wooldridge1995': "Obligations as behavioral constraints with deontic force (modal operators)",
    'Kong2020': "Context-dependent obligations requiring professional judgment",
    'Hallamaa2022': "Obligations operationalize abstract principles into concrete duties",
    'Donohue2017': "BFO placement: obligations as directive information entities (DIE), not socio-legal GDC",
}
