{{ capability_definition }}

EXISTING CAPABILITIES IN ONTOLOGY:
{{ existing_capabilities_text }}

{{ pass_directive }}

CROSS-CONCEPT CONTEXT (roles and obligations already extracted in this case; ground possessed_by in a named actor and required_for_obligations in a named obligation; do NOT re-extract roles or obligations here):
{{ cross_concept_context }}

CASE TEXT:
{{ case_text }}

{{ capability_schema }}

CAPABILITY EXTRACTION DIRECTIVES (rules the ontology enforces):
{{ capability_boundary }}
{{ capability_individuation }}
- capability_class is the canonical competence KIND and the controlled typing signal. Use a tool/actor-neutral head-noun label (e.g. "Structural Analysis Capability", "Ethical Reasoning Capability"), REUSE an existing capability class from the list above, and fold synonyms into it rather than minting a near-duplicate. The kind becomes the rdfs:subClassOf typing at commit. Do not put the tool, the actor, or the case scenario in the label.
- GOVERNING directive: extract ONLY a competence the agent POSSESSES or exercises. A lacked, insufficient, or unexercised competence is NOT a capability and must not be emitted here. The competence gap is captured separately downstream as a state; do not mint a capability for it.
- possessed_by names the agent who holds or exercises the capability (e.g. "Engineer A"), reused from the roles pass. It resolves to the possessedBy edge at commit; name the actor, not a role label.
- required_for_obligations names the obligations that presuppose this capacity (the Ca->O capacity linkage; obligations are extracted earlier and appear in the cross-concept context). It resolves to the requiresCapability edge (Obligation->Capability). Name an obligation label where one fits.
- Do not assert a skill level, proficiency, or the actions the capability enables; those are not stored.

MATCH DECISION RULES:
For each capability class, evaluate ONLY against the EXISTING CAPABILITIES IN ONTOLOGY list above. Cross-concept context is provided so you can ground possessed_by and required_for_obligations and avoid re-extracting duplicates, but do NOT reference those entities in match_decision; that field is strictly for matching against the ontology list above.
- If the extracted capability IS the same concept as an existing class: match with HIGH confidence (0.85-1.0)
- If the extracted capability is a SPECIALIZATION of an existing class: match to parent with MEDIUM confidence (0.70-0.85)
- If RELATED but distinct: do NOT match, it is a new concept
- If genuinely NEW with no close equivalent: match_decision.matches_existing = false

OUTPUT FORMAT:
Return a JSON object with TWO arrays: new_capability_classes (reusable competence kinds) and capability_individuals (specific competences a party holds in this case). A Capability Class is a general reusable competence kind (e.g. "Structural Analysis Capability"); a Capability Individual is a specific competence a named actor holds in the case. Each individual MUST reference a class via the capability_class field.

CLASS LABEL CANONICALIZATION (with worked examples):
Drop case-specific detail (named actors, tools, case identifiers) from the class label; put it in the definition and the individual record. Emit the short general head-noun form:
- "Engineer A's Ability to Run the AI Structural Tool" -> "Structural Analysis Capability"
- "The Reviewer's Skill at Spotting the Soil Report Flaw" -> "Design Review Capability"
- "Knowing How to Weigh Public Safety Against Cost" -> "Ethical Reasoning Capability"
Test: if a label could only ever apply to THIS case or THIS tool, generalize it until another case could reuse it.

CLASS SCHEMA (new_capability_classes array) -- each class is a JSON object:

  {
    "label": "Structural Analysis Capability",
    "definition": "The competence to analyze a structure's loads, stresses, and failure modes and judge its adequacy.",
    "required_for_obligations": ["Competence Obligation"],
    "text_references": ["Engineer A performed the structural analysis of the proposed design"],
    "confidence": 0.9,
    "match_decision": {
      "matches_existing": false,
      "matched_uri": null,
      "matched_label": null,
      "confidence": 0,
      "reasoning": "Structural Analysis Capability is the canonical competence kind; no narrower existing class is required."
    }
  }

INDIVIDUAL SCHEMA (capability_individuals array) -- each individual is a JSON object:

  {
    "identifier": "Engineer A Structural Analysis",
    "capability_class": "Structural Analysis Capability",
    "possessed_by": "Engineer A",
    "case_context": "Engineer A performed the structural analysis that detected the deficiency.",
    "text_references": ["Engineer A performed the structural analysis of the proposed design"],
    "confidence": 0.92
  }

Keep each individual's identifier short (the actor plus the short competence, at most about 6 words); scenario detail belongs in case_context, not the identifier (it becomes the URI). Set possessed_by to the actor's stable identity, the same value the roles pass uses for that actor.

FORMATTING: do not use em dashes or en dashes in output text, and do not dodge with stacked parentheticals or excessive colons/semicolons; use commas or split into two sentences.
