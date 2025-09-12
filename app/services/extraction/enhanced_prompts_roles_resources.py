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
        # De-duplicate roles by label, keeping the one with the best description
        unique_roles = {}
        for role in existing_roles:
            label = role.get('label', 'Unknown')
            description = role.get('description', 'No description')
            
            # Keep the role with the longer/better description
            if label not in unique_roles or len(description) > len(unique_roles[label].get('description', '')):
                unique_roles[label] = role
        
        # Define proper descriptions for roles missing them from Chapter 2 literature
        role_definitions = {
            'Role': 'The base concept for professional roles that can be realized by agents bearing professional duties and ethical obligations.',
            'Agent': 'A material entity capable of bearing roles and performing intentional actions in professional contexts.',
            'Professional Role': 'Roles that create distinctive professional obligations tied to professional goals and practices (Kong et al. 2020).',
            'Participant Role': 'Roles of those who participate in professional contexts but may not be professionals themselves.',
            'Stakeholder Role': 'Roles of those who have legitimate interests in professional activities and their outcomes.',
            'Provider-Client Role': 'Professional role defining relationships between service providers and their clients, creating duties of competent service delivery, confidentiality, and client welfare (Kong et al. 2020).',
            'Professional Peer Role': 'Professional role defining relationships between practitioners within the same professional domain, creating obligations for peer review, professional development, knowledge sharing, and standard maintenance (Kong et al. 2020).',
            'Employer Relationship Role': 'Professional role defining relationships between professionals and their employing organizations, creating duties of loyalty, competent performance, and honest reporting while maintaining professional independence (Wendel 2024).',
            'Public Responsibility Role': 'Professional role defining obligations to the broader public and society, creating duties of public welfare protection that can override client or employer interests (Thornton et al. 2017).',
            'Quality Engineer': 'Engineering role focused on quality assurance, continuous improvement, and ensuring products/services meet specified requirements.',
            'Safety Engineer': 'Critical engineering role for safety-critical systems and applications, responsible for hazard analysis and risk mitigation.',
            'Standards Engineer': 'Specialized engineering role focusing on standards compliance, implementation, and ensuring technical conformance.'
        }
        
        mcp_context = f"""
EXISTING ROLES IN ONTOLOGY ({len(unique_roles)} total):
The following {len(unique_roles)} roles are already defined in the professional ethics ontology. Check against these FIRST before creating new roles:

"""
        # Group roles by hierarchy for better organization
        base_roles = []
        professional_categories = []
        specific_professional_roles = []
        participant_roles = []
        engineering_roles = []
        
        for label, role in unique_roles.items():
            description = role.get('description', 'No description')
            
            # Use our defined descriptions if the MCP didn't provide a good one
            if description == 'No description' or description.startswith('A subclass of'):
                description = role_definitions.get(label, description)
            
            # Categorize roles
            if label in ['Role', 'Agent']:
                base_roles.append((label, description))
            elif label in ['Professional Role']:
                professional_categories.append((label, description))
            elif label in ['Provider-Client Role', 'Professional Peer Role', 'Employer Relationship Role', 'Public Responsibility Role']:
                specific_professional_roles.append((label, description))
            elif label in ['Participant Role', 'Stakeholder Role']:
                participant_roles.append((label, description))
            elif 'Engineer' in label:
                engineering_roles.append((label, description))
        
        # Display in organized hierarchy - ALL roles
        role_count = 0
        if base_roles:
            mcp_context += f"BASE CONCEPTS ({len(base_roles)} roles):\n"
            for label, desc in base_roles:
                # Show full descriptions for important concepts
                mcp_context += f"- **{label}**: {desc}\n"
                role_count += 1
            mcp_context += "\n"
        
        if professional_categories:
            mcp_context += f"PROFESSIONAL ROLE CATEGORIES ({len(professional_categories)} roles):\n"
            for label, desc in professional_categories:
                mcp_context += f"- **{label}**: {desc}\n"
                role_count += 1
            mcp_context += "\n"
        
        if specific_professional_roles:
            mcp_context += f"SPECIFIC PROFESSIONAL ROLE TYPES from Kong et al. 2020 ({len(specific_professional_roles)} roles):\n"
            for label, desc in specific_professional_roles:
                mcp_context += f"- **{label}**: {desc}\n"
                role_count += 1
            mcp_context += "\n"
        
        if participant_roles:
            mcp_context += f"PARTICIPANT/STAKEHOLDER ROLES ({len(participant_roles)} roles):\n"
            for label, desc in participant_roles:
                mcp_context += f"- **{label}**: {desc}\n"
                role_count += 1
            mcp_context += "\n"
        
        if engineering_roles:
            mcp_context += f"DOMAIN-SPECIFIC ENGINEERING ROLES ({len(engineering_roles)} roles):\n"
            for label, desc in engineering_roles:
                mcp_context += f"- **{label}**: {desc}\n"
                role_count += 1
            mcp_context += "\n"
        
        mcp_context += f"""
IMPORTANT EXTRACTION RULES:
1. **ALWAYS CHECK EXISTING ROLES FIRST** - Compare each role you find against ALL {len(unique_roles)} roles listed above
2. **USE is_existing: true** - If the role matches or is a specific instance of any role above
3. **USE is_existing: false** - ONLY if the role is genuinely novel and not covered by existing concepts
4. **Match liberally** - "Environmental Engineer" matches existing "Engineer Role", "Client W" matches "Provider-Client Role"
5. **Use Kong et al. (2020) categories** - Every role should fit one of these four:
   - Provider-Client (service delivery relationships)
   - Professional Peer (collegial relationships)  
   - Employer Relationship (organizational relationships)
   - Public Responsibility (societal obligations)

Example matching:
- "Engineer A" → matches "Engineer Role" (is_existing: true)
- "Client W" → matches "Provider-Client Role" (is_existing: true)
- "Mentor Engineer B" → matches "Professional Peer Role" (is_existing: true)
- "Environmental Engineer" → matches "Engineer Role" (is_existing: true)
"""
    
    return f"""
{mcp_context}

TASK: Extract all PROFESSIONAL ROLES from the guideline text using the ProEthica formalism.

KEY PRINCIPLE: Roles are obligation-generating entities that function as ethical filters (Dennis et al. 2016).

KONG ET AL. (2020) FRAMEWORK - All roles must fit ONE of these:

1. **Provider-Client** → Service delivery relationships (Engineer-Client)
   - Duties: Competent service, confidentiality, client welfare
   
2. **Professional Peer** → Collegial relationships (Senior-Junior, Mentor-Mentee)
   - Duties: Peer review, mentoring, knowledge sharing
   
3. **Employer Relationship** → Organizational relationships (Employee-Employer)
   - Duties: Loyalty, competent performance, honest reporting
   
4. **Public Responsibility** → Societal obligations (Engineer-Public)
   - Duties: Public welfare paramount, can override other interests

EXTRACTION PROCESS:
1. Identify all roles mentioned (explicit or implied)
2. Match against existing ontology roles (use is_existing: true/false)
3. Categorize using Kong framework (required for all roles)
4. Identify obligations generated by each role
5. Note role conflicts if present

GUIDELINE TEXT:
{text}

OUTPUT: JSON array with ALL roles found:
[
  {{
    "label": "Environmental Engineer",  // Role name from text
    "description": "Licensed engineer specializing in environmental impact assessment",
    "type": "role",
    "role_category": "provider_client",  // REQUIRED: provider_client|professional_peer|employer_relationship|public_responsibility
    "obligations_generated": ["Environmental protection", "Accurate reporting", "Public safety"],
    "text_references": ["Engineer A, an environmental engineer"],  // Quote from text
    "importance": "high",  // high|medium|low based on centrality to case
    "is_existing": true,  // true if matches ontology role, false if novel
    "ontology_match": "Engineer Role"  // Which ontology role it matches (if is_existing: true)
  }}
]

REMEMBER: Check ALL roles against the existing ontology roles listed above FIRST!
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
        # De-duplicate resources by label, keeping the one with the best description
        unique_resources = {}
        for resource in existing_resources:
            label = resource.get('label', 'Unknown')
            description = resource.get('description', 'No description')
            
            # Keep the resource with the longer/better description
            if label not in unique_resources or len(description) > len(unique_resources[label].get('description', '')):
                unique_resources[label] = resource
        
        # Define proper descriptions based on McLaren (2003) Chapter 2 literature
        resource_definitions = {
            'Resource': 'The base concept for professional knowledge resources used in ethical decision-making.',
            'Professional Code': 'Formal codified professional ethics standards (e.g., NSPE Code, IEEE Code) that establish professional identity and provide deliberation frameworks (McLaren 2003).',
            'Case Precedent': 'Documented cases from ethics review boards providing precedential knowledge and analogical reasoning patterns (McLaren 2003).',
            'Expert Interpretation': 'Authoritative explanations bridging principles to specific contexts, providing nuanced understanding of principle application.',
            'Technical Standard': 'Industry standards and specifications (e.g., ISO, IEEE, ASME) embodying collective professional agreement on technical acceptability.',
            'Legal Resource': 'Laws, regulations, and statutes governing professional practice and establishing legal boundaries.',
            'Decision Tool': 'Frameworks, methodologies, and assessment tools providing structured approaches to ethical decision-making.',
            'Reference Material': 'Handbooks, manuals, guides, and documentation supporting professional practice with technical knowledge.',
            'Standard': 'A documented agreement containing technical specifications or criteria for professional practice.',
            'Measurement': 'A quantitative or qualitative assessment or evaluation tool.',
            'Justification': 'A rationale, argument, or evidence artifact supporting a decision or interpretation.'
        }
        
        mcp_context = f"""
EXISTING RESOURCES IN ONTOLOGY:
The professional ethics ontology contains {len(unique_resources)} established resource concepts based on McLaren's (2003) extensional principles approach:

"""
        # Group resources by category
        base_resources = []
        professional_codes = []
        case_precedents = []
        technical_standards = []
        decision_support = []
        other_resources = []
        
        for label, resource in unique_resources.items():
            description = resource.get('description', 'No description')
            
            # Use our defined descriptions if the MCP didn't provide a good one
            if description == 'No description' or len(description) < 50:
                description = resource_definitions.get(label, description)
            
            # Categorize resources
            if label == 'Resource':
                base_resources.append((label, description))
            elif 'Professional Code' in label or 'NSPE' in label:
                professional_codes.append((label, description))
            elif 'Case Precedent' in label:
                case_precedents.append((label, description))
            elif 'Technical Standard' in label or 'Standard' in label:
                technical_standards.append((label, description))
            elif label in ['Expert Interpretation', 'Decision Tool', 'Legal Resource']:
                decision_support.append((label, description))
            else:
                other_resources.append((label, description))
        
        # Display all resources in organized categories
        if base_resources:
            mcp_context += "BASE CONCEPT:\n"
            for label, desc in base_resources:
                mcp_context += f"- **{label}**: {desc}\n"
            mcp_context += "\n"
        
        if professional_codes:
            mcp_context += "PROFESSIONAL CODES (Identity-Establishing Frameworks):\n"
            for label, desc in professional_codes:
                mcp_context += f"- **{label}**: {desc}\n"
            mcp_context += "\n"
        
        if case_precedents:
            mcp_context += "CASE PRECEDENTS (Analogical Reasoning Resources):\n"
            for label, desc in case_precedents:
                mcp_context += f"- **{label}**: {desc}\n"
            mcp_context += "\n"
        
        if technical_standards:
            mcp_context += "TECHNICAL STANDARDS (Collective Professional Agreements):\n"
            for label, desc in technical_standards:
                mcp_context += f"- **{label}**: {desc}\n"
            mcp_context += "\n"
        
        if decision_support:
            mcp_context += "DECISION SUPPORT RESOURCES:\n"
            for label, desc in decision_support:
                mcp_context += f"- **{label}**: {desc}\n"
            mcp_context += "\n"
        
        if other_resources:
            mcp_context += "OTHER PROFESSIONAL RESOURCES:\n"
            for label, desc in other_resources:
                mcp_context += f"- **{label}**: {desc}\n"
            mcp_context += "\n"
        
        mcp_context += """EXTRACTION GUIDANCE:
When identifying resources in the text:
1. First check if they match any existing resource concepts above
2. Consider McLaren's (2003) four core types:
   - Professional Codes (identity frameworks)
   - Case Precedents (analogical reasoning)
   - Expert Interpretations (principle bridging)
   - Technical Standards (collective agreements)
3. Mark resources as 'existing' if they match, or 'new' if they represent genuinely novel resource concepts
"""
    
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