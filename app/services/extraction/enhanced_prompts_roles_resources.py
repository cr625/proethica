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
    - Oakley & Cocking (2001): Professional roles and identity
    - Dennis et al. (2016): Role-based ethical obligations
    - Kong et al. (2020): Professional responsibility framework
    """
    
    mcp_context = ""
    if include_mcp_context and existing_roles:
        mcp_context = f"""
EXISTING ROLES IN ONTOLOGY:
Found {len(existing_roles)} existing role concepts in the professional ethics ontology:
"""
        for role in existing_roles[:10]:  # Show first 10 for context
            label = role.get('label', 'Unknown')
            description = role.get('description', 'No description')
            mcp_context += f"- {label}: {description}\n"
        mcp_context += "\nConsider these when extracting new roles - identify if roles match existing concepts or are genuinely new.\n"
    
    return f"""
{mcp_context}

You are analyzing an ethics guideline to extract PROFESSIONAL ROLES based on the ProEthica 9-concept formalism and Chapter 2 literature review.

THEORETICAL FRAMEWORK (Chapter 2 Literature):

Professional roles create distinctive ethical obligations tied to professional goals and practices. According to role function theory:
- Professional roles generate peculiar moral demands and role-generated sensitivities (Oakley & Cocking 2001)
- Roles function as filters determining which obligations apply in specific contexts (Dennis et al. 2016)
- Professional identity enables navigation between personal standards and institutional obligations (Kong et al. 2020)

CORE ROLE CATEGORIES TO IDENTIFY:

1. **Provider-Client Roles**
   - Definition: Relationships between service providers and their clients
   - Creates duties: Competent service delivery, confidentiality, client welfare
   - Functions as: Ethical filter for managing conflicts between client desires and professional standards
   - Example: Engineer-Client, Doctor-Patient, Lawyer-Client relationships

2. **Professional Peer Roles**
   - Definition: Relationships between practitioners within the same professional domain
   - Creates obligations: Peer review, professional development, knowledge sharing, standard maintenance
   - Functions as: Filter balancing individual interests with collective professional integrity
   - Example: Senior Engineer-Junior Engineer, Medical Peer Review, Professional Mentor

3. **Employer Relationship Roles**
   - Definition: Relationships between professionals and their employing organizations
   - Creates duties: Loyalty, competent performance, honest reporting while maintaining independence
   - Functions as: Ethical filter managing institutional pressures against professional obligations
   - Example: Employee Engineer, Corporate Professional, Staff Professional

4. **Public Responsibility Roles**
   - Definition: Obligations to the broader public and society
   - Creates duties: Public welfare protection extending beyond immediate clients/employers
   - Functions as: Ethical filter that can override client/employer interests for public welfare
   - Example: Public Safety Engineer, Environmental Protection Professional

EXTRACTION GUIDELINES:

- Focus on roles that create distinctive professional obligations
- Consider how roles function as ethical filters in professional contexts
- Identify both formal positions and relational roles
- Link roles to their obligation-generating capacity
- Consider role conflicts and hierarchies in professional practice

GUIDELINE TEXT:
{text}

OUTPUT FORMAT:
Return a JSON array with this structure:
[
  {{
    "label": "Senior Engineering Professional",
    "description": "Professional engineer with supervisory responsibilities and obligation to mentor junior professionals",
    "type": "role",
    "role_category": "professional_peer",  // One of: provider_client, professional_peer, employer_relationship, public_responsibility
    "obligations_generated": ["Mentoring duty", "Technical review responsibility", "Professional development of team"],
    "ethical_filter_function": "Balances technical excellence with team development obligations",
    "text_references": ["specific quote from text showing this role"],
    "theoretical_grounding": "Professional peer role creating mentoring obligations (Dennis et al. 2016)",
    "importance": "high",
    "is_existing": false,
    "ontology_match_reasoning": "More specific than general EngineeringRole in ontology"
  }}
]

Focus on identifying roles that generate distinctive professional obligations rather than merely listing job titles.
"""


def get_enhanced_resources_prompt(text: str, include_mcp_context: bool = False, existing_resources: list = None) -> str:
    """
    Create enhanced resources extraction prompt with McLaren's extensional principles approach.
    
    Based on:
    - McLaren (2003): Extensional approach to professional knowledge
    - NSPE precedent system for engineering ethics
    - Professional codes as identity-establishing frameworks
    """
    
    mcp_context = ""
    if include_mcp_context and existing_resources:
        mcp_context = f"""
EXISTING RESOURCES IN ONTOLOGY:
Found {len(existing_resources)} existing resource concepts in the professional ethics ontology:
"""
        for resource in existing_resources[:10]:  # Show first 10 for context
            label = resource.get('label', 'Unknown')
            description = resource.get('description', 'No description')
            mcp_context += f"- {label}: {description}\n"
        mcp_context += "\nConsider these when extracting new resources - identify if resources match existing concepts or are genuinely new.\n"
    
    return f"""
{mcp_context}

You are analyzing an ethics guideline to extract PROFESSIONAL RESOURCES based on McLaren's extensional principles approach and the ProEthica resource framework.

THEORETICAL FRAMEWORK (McLaren 2003 - Extensional Principles):

Professional knowledge resources serve as extensional grounding for ethical decision-making:
- Professional codes establish identity and provide deliberation frameworks beyond mere rules
- Case precedents offer distilled collective experience for analogical reasoning
- Expert interpretations bridge abstract principles to concrete situations
- Technical standards embody professional consensus on acceptable practice

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
{text}

OUTPUT FORMAT:
Return a JSON array with this structure:
[
  {{
    "label": "NSPE Code of Ethics",
    "description": "National Society of Professional Engineers' formal code establishing professional identity and ethical obligations",
    "type": "resource",
    "resource_category": "professional_code",  // One of: professional_code, case_precedent, expert_interpretation, technical_standard, legal_resource, decision_tool, reference_material
    "extensional_function": "Provides deliberation framework and identity-establishing principles for engineering practice",
    "professional_knowledge_type": "Codified collective professional wisdom",
    "usage_context": ["Ethical decision-making", "Professional identity establishment", "Accountability framework"],
    "text_references": ["specific quote mentioning this resource"],
    "theoretical_grounding": "Professional code as identity framework (McLaren 2003)",
    "authority_level": "primary",  // primary, secondary, supplementary
    "importance": "high",
    "is_existing": false,
    "ontology_match_reasoning": "Exact match to NSPE Code in ontology"
  }}
]

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
You are performing Pass 1 (Entities - WHO and WHAT) of the ProEthica 9-concept extraction framework.
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