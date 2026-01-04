"""
Enhanced Prompts for Roles and Resources Extraction
Based on Chapter 2 Literature Review and ProEthica Ontology Requirements

This module provides enhanced prompt templates that incorporate:
- Scholarly citations and theoretical grounding
- Ontology-aligned concept definitions
- Professional ethics framework from Chapter 2
"""

def get_enhanced_roles_prompt(text: str, include_mcp_context: bool = False, existing_roles: list = None) -> str:
    """
    Create enhanced roles extraction prompt with Chapter 2 literature grounding.
    
    Based on:
    - Oakley & Cocking (2001): Professional roles shape identity through distinctive obligations
    - Dennis et al. (2016): Roles function as ethical filters that transform general duties into specific obligations
    - Kong et al. (2020): Four-category framework for professional role relationships
    """
    
    mcp_context = ""
    if include_mcp_context and existing_roles:
        # Organize roles using actual hierarchy (like we did for Principles)
        base_role = None
        category_roles = []
        specific_roles = []
        
        # De-duplicate and organize by hierarchy
        seen_labels = set()
        for role in existing_roles:
            label = role.get('label', '')
            if label in seen_labels:
                continue
            seen_labels.add(label)
            
            description = role.get('description', role.get('definition', ''))
            
            # Skip non-role entities that might have been included
            if 'Agent' in label:
                continue
                
            # Organize by hierarchy
            if label == 'Role':
                if not base_role:  # Take first Role as base
                    base_role = {'label': label, 'definition': description}
            elif any(cat in label for cat in ['Professional Role', 'Participant Role', 'Stakeholder Role']):
                category_roles.append({'label': label, 'definition': description})
            else:
                specific_roles.append({'label': label, 'definition': description})
        
        # Build hierarchical context - NO TRUNCATION
        mcp_context = f"""
EXISTING ROLES IN ONTOLOGY (Hierarchical View):
Found {len(seen_labels)} role concepts organized by hierarchy:

**BASE CLASS:**
- **{base_role['label'] if base_role else 'Role'}**: {base_role['definition'] if base_role else 'The base concept for professional roles that can be realized by agents bearing professional duties and ethical obligations.'}
  (This is the parent class for all role concepts)

**ROLE CATEGORIES (Subclasses of Role):**
"""
        for cat in sorted(category_roles, key=lambda x: x['label']):
            mcp_context += f"- **{cat['label']}**: {cat['definition']}\n"
        
        mcp_context += "\n**SPECIFIC ROLES (Instances within categories):**\n"
        for spec in sorted(specific_roles, key=lambda x: x['label']):
            mcp_context += f"- **{spec['label']}**: {spec['definition']}\n"
        
        
        mcp_context += """
**EXTRACTION GUIDANCE:**
When identifying roles in the text, consider:
1. Check if the role already exists in the ontology
2. If new, identify which category it belongs to
3. Ensure it's a role that bears obligations, not just a descriptive label

Note: "Role" is the base ontology class. All specific roles should be
more descriptive (e.g., "Engineer Role" not just "Engineer").
"""
    
    return f"""
{mcp_context}

You are analyzing an ethics guideline to extract PROFESSIONAL ROLES based on the ProEthica formalism and professional ethics literature.

THEORETICAL FRAMEWORK - Key Insights from Professional Ethics Literature:

Roles are not merely job titles but obligation-generating entities that:
- **Ethical Filters**: Transform general moral duties into role-specific obligations (Dennis et al. 2016 empirical study of 127 professional codes)
- **Identity Formation**: Shape professional identity through distinctive goals and practices (Oakley & Cocking 2001 virtue ethics framework)
- **Relationship Structures**: Define professional relationships and their associated duties (Kong et al. 2020 analysis of engineering ethics cases)

**KONG ET AL. (2020) FOUR-CATEGORY FRAMEWORK:**
Based on analysis of 500+ engineering ethics cases, all professional roles fall into these categories:

1. **Provider-Client** → Service delivery relationships (Engineer-Client)
   - Duties: Competent service, confidentiality, client welfare
   
2. **Professional Peer** → Collegial relationships (Senior-Junior, Mentor-Mentee)
   - Duties: Peer review, mentoring, knowledge sharing
   
3. **Employer Relationship** → Organizational relationships (Employee-Employer)
   - Duties: Loyalty, competent performance, honest reporting
   
4. **Public Responsibility** → Societal obligations (Engineer-Public)
   - Duties: Public welfare paramount, can override other interests

**EXTRACTION PROCESS:**
1. Identify all roles mentioned (explicit or implied)
2. Match against existing ontology roles (use is_existing: true/false)
3. Categorize using Kong framework (required for all roles)
4. Identify obligations generated by each role
5. Note role conflicts if present

GUIDELINE TEXT:
{text if isinstance(text, str) else str(text)}

**MATCH DECISION RULES:**
For each role, evaluate against the existing ontology roles listed above:
- If the extracted role IS the same concept as an existing class: match with HIGH confidence (0.85-1.0)
- If the extracted role is a SPECIALIZATION of an existing class: match to parent with MEDIUM confidence (0.70-0.85)
- If the extracted role is RELATED but distinct: do NOT match, it's a new concept
- If genuinely NEW with no close equivalent: match_decision.matches_existing = false

OUTPUT: JSON array with ALL roles found:
[
  {{
    "label": "Environmental Engineer",
    "description": "Licensed engineer specializing in environmental impact assessment",
    "type": "role",
    "role_category": "provider_client",
    "obligations_generated": ["Environmental protection", "Accurate reporting", "Public safety"],
    "text_references": ["Engineer A, an environmental engineer"],
    "importance": "high",
    "match_decision": {{
      "matches_existing": true,
      "matched_uri": "http://proethica.org/ontology/intermediate#Engineer",
      "matched_label": "Engineer",
      "confidence": 0.85,
      "reasoning": "Environmental Engineer is a specialization of the existing Engineer class. Core professional obligations align."
    }}
  }}
]

If no match exists, use:
    "match_decision": {{
      "matches_existing": false,
      "matched_uri": null,
      "matched_label": null,
      "confidence": 0.0,
      "reasoning": "This is a novel role type not represented in the current ontology."
    }}

REMEMBER: Check ALL roles against the existing ontology roles listed above FIRST!
"""


def get_enhanced_resources_prompt(text: str, include_mcp_context: bool = False, existing_resources: list = None) -> str:
    """
    Create enhanced resources extraction prompt with McLaren's extensional principles approach.
    
    Based on:
    - McLaren (2003): Extensional approach grounding ethics in professional knowledge
    - NSPE precedent system showing how cases create practical wisdom
    - Professional codes as identity-establishing frameworks beyond mere rules
    """
    
    mcp_context = ""
    if include_mcp_context and existing_resources:
        # Organize resources hierarchically (like we did for Roles and States)
        base_resource = None
        specific_resources = []
        
        # De-duplicate and organize
        seen_labels = set()
        for resource in existing_resources:
            label = resource.get('label', '')
            if label in seen_labels:
                continue
            seen_labels.add(label)
            
            description = resource.get('description', resource.get('definition', ''))
            
            # Skip non-resource entities that might have been included
            if 'Constrained' in label or 'Available' in label:
                continue  # These are States, not Resources
                
            # Organize by hierarchy
            if label == 'Resource':
                if not base_resource:  # Take first Resource as base
                    base_resource = {'label': label, 'definition': description}
            else:
                specific_resources.append({'label': label, 'definition': description})
        
        # Build hierarchical context - NO TRUNCATION
        mcp_context = f"""
EXISTING RESOURCES IN ONTOLOGY (Hierarchical View):
Found {len(seen_labels)} resource concepts organized by hierarchy:

**BASE CLASS:**
- **{base_resource['label'] if base_resource else 'Resource'}**: {base_resource['definition'] if base_resource else 'Professional knowledge sources that provide extensional grounding for ethical decision-making.'}
  (This is the parent class for all resource concepts)

**SPECIFIC RESOURCES (Direct instances):**
"""
        for spec in sorted(specific_resources, key=lambda x: x['label']):
            mcp_context += f"- **{spec['label']}**: {spec['definition']}\n"
        
        mcp_context += """
**PASS 1 INTEGRATION (Roles + States + RESOURCES):**
Resources complete Pass 1 by defining WHAT knowledge guides decisions:
- Roles define WHO has obligations
- States define WHEN those obligations become active  
- Resources define WHAT knowledge guides decisions in those states

Example: "Engineer Role" + "Conflict of Interest State" → Uses "NSPE Code" (Resource) for guidance

**McLAREN'S (2003) EXTENSIONAL PRINCIPLE:**
Resources provide concrete grounding for abstract principles through:
- Professional codes that establish identity beyond rules
- Case precedents that offer analogical reasoning patterns
- Technical standards that embody collective professional wisdom
"""
    else:
        mcp_context = """
ONTOLOGY CONTEXT:
Resources in ProEthica represent professional knowledge sources that:
- Provide extensional grounding for ethical principles
- Establish professional identity and accountability
- Bridge abstract principles to concrete practice
- Embody collective professional wisdom
- Guide decision-making in specific contexts

Note: No existing resource instances found in ontology. All extracted resources will be new.
"""
    
    return f"""
{mcp_context}

You are analyzing an ethics guideline to extract PROFESSIONAL RESOURCES as part of Pass 1 (Contextual Framework) of the ProEthica extraction.

THEORETICAL FRAMEWORK - Key Insights from Extensional Principles Literature:

Resources are not merely documents but professional knowledge sources that ground ethical reasoning:
- **Extensional Grounding**: Abstract principles require concrete cases and precedents for meaning (McLaren 2003 analysis of NSPE case system)
- **Identity Establishment**: Professional codes create identity frameworks beyond rule lists (analysis of 50+ professional codes)
- **Analogical Reasoning**: Case precedents enable pattern-based ethical reasoning (empirical study of 200+ NSPE BER cases)
- **Collective Wisdom**: Technical standards embody professional consensus (review of engineering standard development)

**RELATIONSHIP TO PASS 1 (WHO-WHEN-WHAT):**
Resources complete the contextual triad:
- Roles (WHO) identify obligation bearers
- States (WHEN) activate those obligations
- Resources (WHAT) provide knowledge to fulfill obligations

FOUR CORE RESOURCE TYPES TO IDENTIFY:

1. **Professional Codes (ProfessionalCode)**
   - Definition: Formal codified professional ethics standards (e.g., NSPE Code, IEEE Code)
   - Function: Establish professional identity, create accountability, provide deliberation frameworks
   - Extensional Role: Distillations of collective experience that guide and justify actions
   - Examples: "NSPE Code of Ethics", "ACM Code of Professional Conduct", "IEEE Code of Ethics"

2. **Case Precedents (CasePrecedent)**
   - Definition: Documented cases from ethics review boards providing precedential knowledge
   - Function: Offer analogical reasoning patterns for similar situations
   - Extensional Role: Concrete instances that ground abstract principles in professional reality
   - Examples: "NSPE Board of Ethical Review Case 92-6", "Previous similar incident rulings"

3. **Expert Interpretations (ExpertInterpretation)**
   - Definition: Authoritative explanations bridging principles to specific contexts
   - Function: Provide nuanced understanding of how principles apply in complex situations
   - Extensional Role: Professional consensus on principle application in edge cases
   - Examples: "Ethics committee guidance", "Senior professional consultation", "Expert panel recommendations"

4. **Technical Standards (TechnicalStandard)**
   - Definition: Industry standards and specifications defining acceptable practice
   - Function: Establish minimum professional competence and quality benchmarks
   - Extensional Role: Collective professional agreement on technical acceptability
   - Examples: "ASME Boiler Code", "IEEE Standards", "ISO 9001 Quality Standards", "Building Codes"

ADDITIONAL RESOURCE CATEGORIES:

5. **Legal Resources**: Laws, regulations, statutes governing professional practice
6. **Decision Tools**: Frameworks, methodologies, assessment tools for ethical analysis
7. **Reference Materials**: Handbooks, manuals, guides supporting professional practice

EXTRACTION GUIDELINES:

- Focus on resources that provide extensional grounding for ethical decisions
- Identify how resources function as professional knowledge sources
- Consider resources that establish professional identity and accountability
- Look for resources that bridge abstract principles to concrete practice
- Prioritize resources that embody collective professional wisdom

GUIDELINE TEXT:
{text if isinstance(text, str) else str(text)}

**MATCH DECISION RULES:**
For each resource, evaluate against existing ontology resources:
- If the resource IS the same as an existing class: match with HIGH confidence (0.85-1.0)
- If the resource is a VARIANT of an existing class: match to parent with MEDIUM confidence (0.70-0.85)
- If genuinely NEW: match_decision.matches_existing = false

OUTPUT FORMAT:
Return a JSON array with this structure:
[
  {{
    "label": "NSPE Code of Ethics",
    "description": "National Society of Professional Engineers' formal code establishing professional identity and ethical obligations",
    "type": "resource",
    "resource_category": "professional_code",
    "extensional_function": "Provides deliberation framework and identity-establishing principles for engineering practice",
    "professional_knowledge_type": "Codified collective professional wisdom",
    "usage_context": ["Ethical decision-making", "Professional identity establishment", "Accountability framework"],
    "text_references": ["specific quote mentioning this resource"],
    "theoretical_grounding": "Professional code as identity framework (McLaren 2003)",
    "authority_level": "primary",
    "importance": "high",
    "match_decision": {{
      "matches_existing": true,
      "matched_uri": "http://proethica.org/ontology/intermediate#ProfessionalCode",
      "matched_label": "Professional Code",
      "confidence": 0.90,
      "reasoning": "NSPE Code is a specific instance of the Professional Code class in the ontology."
    }}
  }}
]

If no match exists, use:
    "match_decision": {{
      "matches_existing": false,
      "matched_uri": null,
      "matched_label": null,
      "confidence": 0.0,
      "reasoning": "This resource type is not represented in the current ontology."
    }}

Focus on identifying resources that provide extensional grounding for professional ethical decision-making rather than merely listing documents.
"""


def get_enhanced_pass1_entities_prompt(text: str, include_mcp_context: bool = False, 
                                       existing_roles: list = None, 
                                       existing_resources: list = None) -> str:
    """
    Combined Pass 1 prompt for Entities (WHO and WHAT) extraction with full theoretical grounding.
    
    This prompt combines both Roles and Resources extraction in a single pass,
    emphasizing their interconnected nature in professional ethics.
    """
    
    roles_context = ""
    resources_context = ""
    
    if include_mcp_context:
        if existing_roles:
            roles_context = f"\nExisting Roles: {len(existing_roles)} role concepts already in ontology"
        if existing_resources:
            resources_context = f"\nExisting Resources: {len(existing_resources)} resource concepts already in ontology"
    
    return f"""
You are performing Pass 1 (Entities - WHO and WHAT) of the ProEthica 9-component extraction framework.
{roles_context}{resources_context}

THEORETICAL FOUNDATION:

Pass 1 identifies the key entities involved in professional ethics situations:
- WHO: Professional and stakeholder roles that bear obligations and make decisions
- WHAT: Resources and tools that guide ethical decision-making

These entities form the foundation for understanding:
1. Who has professional obligations (Roles as obligation bearers)
2. What resources ground ethical decisions (Resources as extensional knowledge)
3. How roles and resources interact in professional practice

EXTRACTION FOCUS:

**ROLES (WHO)** - Based on Oakley & Cocking (2001), Dennis et al. (2016), Kong et al. (2020):
- Provider-Client Roles: Service delivery relationships with duties of competence and care
- Professional Peer Roles: Collegial relationships with mentoring and review obligations
- Employer Relationship Roles: Organizational relationships balancing loyalty and independence
- Public Responsibility Roles: Societal obligations that can override client/employer interests

**RESOURCES (WHAT)** - Based on McLaren (2003) extensional principles:
- Professional Codes: Identity-establishing frameworks for professional conduct
- Case Precedents: Documented cases providing analogical reasoning patterns
- Expert Interpretations: Authoritative guidance bridging principles to practice
- Technical Standards: Consensus on acceptable professional practice

GUIDELINE TEXT:
{text}

INTEGRATED ANALYSIS:
Extract both roles and resources, considering:
1. How roles utilize specific resources for decision-making
2. Which resources govern particular role obligations
3. The relationship between role identity and resource authority

OUTPUT FORMAT:
Return a JSON object with two arrays:
{{
  "roles": [
    {{
      "label": "Engineering Project Manager",
      "role_category": "employer_relationship",
      "obligations_focus": "Team coordination and project delivery while maintaining ethical standards",
      "resources_used": ["NSPE Code", "Company Ethics Policy"],
      "importance": "high"
    }}
  ],
  "resources": [
    {{
      "label": "NSPE Code of Ethics",
      "resource_category": "professional_code",
      "extensional_function": "Establishes engineering professional identity and obligations",
      "roles_governed": ["Engineering Project Manager", "Design Engineer"],
      "importance": "high"
    }}
  ]
}}

Focus on the interconnected nature of roles and resources in professional ethics rather than treating them as independent entities.
"""
