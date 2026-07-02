{{ state_definition }}

EXISTING STATES IN ONTOLOGY:
{{ existing_states_text }}

{{ pass_directive }}

CROSS-CONCEPT CONTEXT (entities already extracted in this case, for grounding the linkage fields; do NOT re-extract them here):
{{ cross_concept_context }}

CASE TEXT:
{{ case_text }}

{{ state_schema }}

STATE EXTRACTION DIRECTIVES (rules the ontology enforces):
{{ state_boundary }}
{{ state_individuation }}
- state_category is the controlled content archetype and the load-bearing typing signal. Set exactly one of epistemic, risk, competence, emergency, conflict_of_interest, regulatory, temporal, resource, disclosure. It classifies the condition in the world (a RiskState is hazard exposure, an EpistemicState is an agent's knowledge condition), explicitly NOT the activatesObligation relation. The archetype becomes the rdfs:subClassOf typing at commit, so a wrong archetype collides with the disjointness axioms; it is a routing input, not stored as a literal. Do not invent an archetype outside this set.
- Use a canonical, short, reusable state label and REUSE an existing state class from the list above. A discovered compound class must chain through its archetype (e.g. "Tool Reliance State" is a CompetenceState; "Confidential Information State" is a DisclosureState), so a specific label still lands on one of the nine.
- Stative-label rule: a state is named for the condition that holds (for example Sealed Draft Report), never for the happening that produced it.
- A case yields one state individual per distinct condition even when the condition is narrated in several passages; a happening-shaped candidate routes to the Event pass.
- persistence_type records whether the state is an inertial or non-inertial fluent (Berreby): inertial states persist until terminated, non-inertial states hold only momentarily.
- urgency_level records the salience or acuteness of the state (Jones moral intensity): low, medium, high, or critical. It is an attribute of the state, not its kind.
- The linkage fields are edge-driving inputs, converted to edges at commit and not stored as literals: obligation_activation names the obligations the state makes applicable (the activatesObligation edge); action_constraints names the constraints it activates; activation_conditions and termination_conditions, triggering_event and terminated_by name the events that bring the state into or out of holding; affected_parties names the agents the state affects (the affects edge); subject names what is in the state. Provide them where the text supports them.
- Do not assert obligation competition, defeat, or precedence here. The defeasibility relations are produced by a separate pass.

MATCH DECISION RULES:
For each state class, evaluate ONLY against the EXISTING STATES IN ONTOLOGY list above. Cross-concept context is provided so you can ground the linkage fields and avoid re-extracting duplicates, but do NOT reference those entities in match_decision; that field is strictly for matching against the ontology list above.
- If the extracted state IS the same concept as an existing class: match with HIGH confidence (0.85-1.0)
- If the extracted state is a SPECIALIZATION of an existing class: match to parent with MEDIUM confidence (0.70-0.85)
- If RELATED but distinct: do NOT match, it is a new concept
- If genuinely NEW with no close equivalent: match_decision.matches_existing = false

OUTPUT FORMAT:
Return a JSON object with TWO arrays: new_state_classes (reusable kinds of condition) and state_individuals (specific conditions holding in this case). A State Class is a general reusable condition (e.g. "Conflict Of Interest State"); a State Individual is a specific condition holding in the case. Each individual MUST reference a class via the state_class field.

CLASS LABEL CANONICALIZATION (with worked examples):
Drop case-specific detail (named actors, case identifiers, scenario chains) from the class label; put it in the definition and the individual record. Emit the short general right-hand form:
- "Engineer A's Conflict Between Client W and the Merger Party" -> "Conflict Of Interest State"
- "Public Endangered by the Suppressed Soil Report" -> "Public Safety Risk State"
- "Intern Assigned Work Beyond Their Training" -> "Out Of Competence State"
Test: if a label could only ever apply to THIS case, generalize it until another case could reuse it, while still chaining to one of the nine archetypes.

CLASS SCHEMA (new_state_classes array) -- each class is a JSON object:

  {
    "label": "Conflict Of Interest State",
    "definition": "A condition in which a professional's duty to one party is set against a competing interest, so that judgment owed to the first party may be compromised.",
    "state_category": "conflict_of_interest",
    "persistence_type": "inertial",
    "activation_conditions": ["Engineer A retained by two parties with opposing interests"],
    "termination_conditions": ["Engineer A withdraws from one engagement"],
    "obligation_activation": ["Disclosure Obligation"],
    "action_constraints": ["Confidentiality Constraint"],
    "principle_transformation": "The loyalty principle now requires disclosure of the dual engagement.",
    "text_references": ["Engineer A was engaged by both the owner and the contractor"],
    "confidence": 0.9,
    "match_decision": {
      "matches_existing": false,
      "matched_uri": null,
      "matched_label": null,
      "confidence": 0,
      "reasoning": "Conflict Of Interest State is the canonical ConflictOfInterestState archetype; no narrower existing class fits this dual-engagement condition."
    }
  }

INDIVIDUAL SCHEMA (state_individuals array) -- each individual is a JSON object:

  {
    "identifier": "Dual Engagement Conflict",
    "state_class": "Conflict Of Interest State",
    "subject": "Engineer A",
    "active_period": "From the second retention until withdrawal",
    "triggering_event": "Engineer A accepts the contractor's retention",
    "terminated_by": "Engineer A withdraws from the contractor engagement",
    "affected_parties": ["Owner", "Contractor"],
    "urgency_level": "high",
    "text_references": ["Engineer A was engaged by both the owner and the contractor"],
    "confidence": 0.92
  }

Keep each individual's identifier short (the short condition plus the case anchor, at most about 6 words); scenario detail belongs in the definition and the linkage fields, not the identifier (it becomes the URI).

FORMATTING: do not use em dashes or en dashes in output text, and do not dodge with stacked parentheticals or excessive colons/semicolons; use commas or split into two sentences.
