EXISTING ROLES IN ONTOLOGY:
{{ existing_roles_text }}

THEORETICAL FRAMEWORK - Key Insights from Professional Ethics Literature:

Roles are not merely job titles but obligation-generating entities that:
- **Ethical Filters**: Transform general moral duties into role-specific obligations; Dennis et al. 2016 treat an ethical agent as a member of a profession whose decision-making is governed by that profession's code of ethics
- **Identity Formation**: Shape professional character and conduct through the distinctive ends and practices of the profession (Oakley & Cocking 2001 virtue ethics account of professional roles)
- **Relationship Structures**: Define professional relationships and their associated duties (informed by Kong et al. 2020 analysis of professional codes)

**RELATIONSHIP CATEGORIES (system scheme, informed by Kong et al. 2020):**
The system groups role attribution into four relationship-based categories, informed by the audience-oriented identity roles Kong et al. observe in professional codes:

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
2. Match against existing ontology roles (use match_decision)
3. Categorize using the four relationship categories above (required for all roles)
4. Note role conflicts if present

CASE TEXT:
{{ case_text }}

**MATCH DECISION RULES:**
For each role, evaluate ONLY against the EXISTING ROLES IN ONTOLOGY list above.
Cross-concept context from other extraction sections is provided so you can avoid re-extracting duplicates, but do NOT reference those entities in match_decision. The match_decision field is strictly for matching against the ontology list above.
- If the extracted role IS the same concept as an existing class: match with HIGH confidence (0.85-1.0)
- If the extracted role is a SPECIALIZATION of an existing class: match to parent with MEDIUM confidence (0.70-0.85)
- If the extracted role is RELATED but distinct: do NOT match, it's a new concept
- If genuinely NEW with no close equivalent: match_decision.matches_existing = false

OUTPUT FORMAT:
Return a JSON object with TWO arrays: new_role_classes (types/categories of roles) and role_individuals (specific persons/entities filling those roles).

**Role Classes** are general types or categories (e.g., "Design Engineer", "Peer Review Engineer", "Project Owner").
**Role Individuals** are specific named persons or entities from the case (e.g., "Engineer A Design Engineer", "Engineer B Peer Reviewer").

Each individual MUST reference a class via the role_class field.

**NAMING CONVENTION**: Do NOT append type suffixes like "Role" or "Instance" to labels or identifiers. The concept type is already captured by the array membership (class vs individual). Use descriptive names only (e.g., "Design Engineer" not "Design Engineer Role"; "Engineer A Design Engineer" not "Engineer A Design Engineer Instance"). The class may be one of the new_role_classes you extracted OR an existing class from the ontology list above.

**Typing accuracy**: Ensure each individual's role_class correctly reflects the type of role. A design engineer must reference an engineering role class, not a client role class. Do not use the generic base class "Role" when a more specific class is available.

**VALID role_class values**: The role_class field on each individual MUST be set to one of:
(a) A label from the EXISTING ROLES IN ONTOLOGY list at the top of this prompt, OR
(b) A label from your new_role_classes array (must exactly match), OR
(c) One of these base categories: Provider-Client Role, Professional Peer Role, Employer Relationship Role, Public Responsibility Role, Participant Role, Stakeholder Role

Do NOT invent class names that are not in (a), (b), or (c). If unsure, use the closest base category from (c).

CLASS LABEL GENERALITY (canonicalization requirement):
- Structure every class label as [core concept] + at most ONE distinguishing qualifier + the component-type head noun (Role / Principle / Obligation / State / Resource / Action / Event / Capability / Constraint), in Title Case, typically 3-5 words, with the head noun LAST. Drop named actors (Engineer A, Client C, Doe), case/precedent identifiers (BER 84-5, Case 04-11), multi-clause scenario chains, and redundant prefixes/suffixes (e.g. "Post-Client-Override", "Competing-Duties"). Keep "X versus Y" wording ONLY for a State that encodes a genuine tension or dilemma.
A class label names a REUSABLE role type that other cases with a similar concept can share. It is NOT a place to encode this case's facts.
- Keep the label short and general (about 2 to 5 words), naming the abstract role: e.g. "Affected Property Owner", NOT a scenario-specific phrase like "Adversely Affected Highway Route Citizens Client".
- Put ALL case-specific detail (named actors, organizations, the fact pattern, conditions, jurisdictions, and the resolution) in the DEFINITION and in the matching INDIVIDUAL record (its identifier and case_context), never in the class label.
- Test: if a label could only ever apply to THIS case, it is too specific; generalize it until another case could reuse it.
- This is distinct from typing accuracy: still pick the correct specific TYPE rather than the bare base class, but express that type generally instead of by restating the case.
A reusable class plus a case-bound individual is what lets the matcher reuse an existing class instead of minting a near-duplicate.

CLASS LABEL EXAMPLES (verbose compound -> short general):
Examples of the transform to apply to every role class label. Drop the case-specific scenario; keep the reusable concept plus its component suffix.
- "Adversely Affected Highway Route Citizens Client" -> "Affected Citizen"
- "Part-Time Municipal Engineer Advisory Dual-Role Official" -> "Municipal Engineer"
- "Standards Committee Chair Opposing Expert Witness" -> "Expert Witness"
- "Whistleblowing Subordinate Design Engineer" -> "Subordinate Engineer"
Follow these examples: emit the short general form on the left's right-hand side. The dropped detail belongs in the definition and the individual record, never in the class label.

CLASS SCHEMA (new_role_classes array):
Each new role class should be a JSON object:

  {
    "label": "Design Engineer",
    "definition": "A professional engineering role responsible for creating original plans, specifications, and designs",
    "role_category": "provider_client",
    "distinguishing_features": ["Creates original designs rather than reviewing them"],
    "professional_scope": "Original engineering design within the licensed discipline",
    "typical_qualifications": ["Professional Engineer license", "Discipline-specific design experience"],
    "generated_obligations": ["Hold paramount public safety in the design", "Disclose identified design risks to the client"],
    "adheres_to_principles": ["Public Safety and Welfare", "Professional Competence"],
    "associated_virtues": ["Competence", "Integrity"],
    "text_references": ["Engineer A designed the tower structures"],
    "confidence": 0.85,
    "match_decision": {
      "matches_existing": false,
      "matched_uri": null,
      "matched_label": null,
      "confidence": 0,
      "reasoning": "While Engineer exists in the ontology, Design Engineer captures the specific responsibility for original design work distinct from review or consulting roles."
    }
  }

{{ role_schema }}

For role_individuals, also populate active_obligations (the obligations that apply to this individual given the role) and ethical_tensions (tensions when this individual's role obligations conflict).

INDIVIDUAL IDENTIFIER (conciseness):
Keep each individual's `identifier` short and readable: the case actor plus the short concept, at most about 6 words (e.g. "Engineer K Safety Disclosure", NOT "Safety Disclosure Engineer K Bridge Design Phase After Discovery Of Deficiency"). Do NOT restate the whole scenario in the identifier; scenario detail belongs in case_context and the statement/description fields. The identifier becomes the individual's URI, so keep it terse.

INDIVIDUAL SCHEMA (role_individuals array):
Each role instance should be a JSON object:

  {
    "identifier": "Engineer A Design Engineer",
    "actor": "Engineer A",
    "role_class": "Design Engineer",
    "role_category": "provider_client",
    "case_involvement": "Created original tower designs containing significant errors",
    "active_obligations": ["Disclose the design errors to the Owner", "Cooperate with the reviewing engineer"],
    "ethical_tensions": ["Loyalty to the Owner versus candor about the engineer's own errors"],
    "license": "Professional Engineer",
    "specialty": "Structural design",
    "attributes": {"professional_membership": "ASCE member"},
    "relationships": [{"type": "has_client", "target": "Owner", "quote": "Engineer A was retained by the Owner to design the tower"}, {"type": "peer", "target": "Engineer B", "quote": "Engineer B was engaged to review Engineer A's work"}],
    "text_references": ["plans and design of Engineer A", "Engineer A objects and refused to consent"],
    "confidence": 0.90
  }

RELATIONSHIP EVIDENCE:
Each entry in `relationships` MUST include a `quote`: a short verbatim snippet from the
case text that evidences the relationship (the same kind of grounding used for the role
itself). The quote is attached as PROV-O provenance on the relationship edge. If no text
supports a relationship, do not assert it.

RELATIONSHIP TYPES (directional; the subject is THIS role's actor):
State each relationship from this role-bearer's own perspective and pick the controlled `type` value that records the direction, so the actor edge is oriented correctly:
- "has_client": this actor provides professional service to the target (the target is the client). Use "has_provider" when THIS actor is the client and the target provides the service.
- "employed_by": this actor is employed by the target. Use "employs" when this actor is the employer.
- "reviews": this actor reviews the target's work. Use "reviewed_by" when this actor's own work is reviewed by the target.
- "peer": collegial professional peer (symmetric; direction does not matter).
Do not emit a bare "client" when "has_client" or "has_provider" states the direction. A client role (for example an owner who retains an engineer) uses "has_provider", not "has_client".

ACTOR IDENTITY (cross-section):
Each role individual names a role FACET that some underlying actor plays. Set the
`actor` field to that actor's stable identity (e.g. "Engineer A", "Owner", "City
of X"), kept separate from the role facet in `identifier`. The SAME actor seen in a
different section under a different role facet MUST reuse the SAME `actor` value.
When a block titled "ACTORS ALREADY IDENTIFIED IN PRIOR SECTIONS" appears above the
case text, reuse those actor identities exactly; do NOT invent a parallel actor for
someone already listed. One Agent is minted per distinct actor and bears each facet,
so consistent actor naming is what keeps a person from being fragmented across sections.

REMEMBER: Check ALL role classes against the existing ontology roles listed above FIRST!
FORMATTING (ProEthica style, abbreviated): Do not use em dashes or en dashes in output text. Do not dodge that by substituting stacked parentheticals or excessive colons or semicolons. Write plain sentences: use commas, or split into two sentences.

=== PROFESSIONAL vs PARTICIPANT ROLES ===
Classify each role against the ROLE SCHEMA above. A PROFESSIONAL role (engineer, architect, project manager, consultant, regulator, ...) is obligation-bearing: populate the universal AND professional-role class fields, plus the bearer fields on the individual where the case states them. A PARTICIPANT or STAKEHOLDER role (an affected party, the public, a client as a layperson) is NOT obligation-bearing: populate ONLY the universal class fields. Do not invent professional attributes for a non-professional role.