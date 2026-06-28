{{ role_definition }}

EXISTING ROLES IN ONTOLOGY:
{{ existing_roles_text }}

{{ pass_directive }}

{{ role_directives }}

CASE TEXT:
{{ case_text }}

{{ role_schema }}

{{ role_category_vocab }}

MATCH DECISION RULES:
For each role, evaluate ONLY against the EXISTING ROLES IN ONTOLOGY list above. Cross-concept context from other extraction sections is provided so you can avoid re-extracting duplicates, but do NOT reference those entities in match_decision; that field is strictly for matching against the ontology list above.
- If the extracted role IS the same concept as an existing class: match with HIGH confidence (0.85-1.0)
- If the extracted role is a SPECIALIZATION of an existing class: match to parent with MEDIUM confidence (0.70-0.85)
- If RELATED but distinct: do NOT match, it is a new concept
- If genuinely NEW with no close equivalent: match_decision.matches_existing = false

OUTPUT FORMAT:
Return a JSON object with TWO arrays: new_role_classes (reusable types/categories of roles) and role_individuals (specific persons/entities filling those roles). A Role Class is a general reusable type (e.g. "Design Engineer"); a Role Individual is a specific named actor in the case (e.g. "Engineer A Design Engineer"). Each individual MUST reference a class via the role_class field.

VALID role_class values: (a) a label from EXISTING ROLES above, (b) a label from your new_role_classes array (exact match), or (c) a base category: Provider-Client Role, Professional Peer Role, Employer Relationship Role, Public Responsibility Role, Participant Role, Stakeholder Role. Do not invent class names outside (a)-(c). Prefer the most specific correct type over the bare base class "Role".

CLASS LABEL CANONICALIZATION (the D-LABEL directive, with worked examples):
Drop case-specific detail (named actors, case identifiers, scenario chains) from the class label; put it in the definition and the individual record. Emit the short general right-hand form:
- "Adversely Affected Highway Route Citizens Client" -> "Affected Citizen"
- "Part-Time Municipal Engineer Advisory Dual-Role Official" -> "Municipal Engineer"
- "Standards Committee Chair Opposing Expert Witness" -> "Expert Witness"
- "Whistleblowing Subordinate Design Engineer" -> "Subordinate Engineer"
Test: if a label could only ever apply to THIS case, generalize it until another case could reuse it.

CLASS SCHEMA (new_role_classes array) -- each class is a JSON object:

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

INDIVIDUAL SCHEMA (role_individuals array) -- each individual is a JSON object:

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
    "relationships": [{"type": "hasClient", "target": "Owner", "quote": "Engineer A was retained by the Owner to design the tower"}, {"type": "workReviewedBy", "target": "Engineer B", "quote": "Engineer B was engaged to review Engineer A's work"}],
    "text_references": ["plans and design of Engineer A", "Engineer A objects and refused to consent"],
    "confidence": 0.90
  }

Keep each individual's identifier short (the case actor plus the short concept, at most about 6 words); scenario detail belongs in case_involvement, not the identifier (it becomes the URI). For role_individuals, also populate active_obligations (the obligations that apply given the role) and ethical_tensions (conflicts among this individual's role obligations).

{{ role_relationships }}

ACTOR IDENTITY (cross-section): each role individual names a role FACET that some underlying actor plays. Set `actor` to that actor's stable identity (e.g. "Engineer A", "Owner", "City of X"), kept separate from the role facet in `identifier`. The SAME actor seen in a different section under a different role facet MUST reuse the SAME `actor` value. When an "ACTORS ALREADY IDENTIFIED IN PRIOR SECTIONS" block appears above the case text, reuse those actor identities exactly. One Agent is minted per distinct actor and bears each facet, so consistent actor naming is what keeps a person from being fragmented across sections.

FORMATTING: do not use em dashes or en dashes in output text, and do not dodge with stacked parentheticals or excessive colons/semicolons; use commas or split into two sentences.
