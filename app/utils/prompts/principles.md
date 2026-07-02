{{ principle_definition }}

EXISTING PRINCIPLES IN ONTOLOGY:
{{ existing_principles_text }}

{{ pass_directive }}

CROSS-CONCEPT CONTEXT (roles already extracted in this case; ground invoked_by in a named role-bearer or actor; do NOT re-extract roles here):
{{ cross_concept_context }}

CASE TEXT:
{{ case_text }}

{{ principle_schema }}

PRINCIPLE EXTRACTION DIRECTIVES (rules the ontology enforces):
{{ principle_boundary }}
{{ principle_individuation }}
- GRANULARITY (per-value rule): a case yields at most one principle individual per distinct value, and distinct values remain separate individuals; each application of the value is recorded in that individual's applied_to and concrete_expression lists, and the balancing and tension narratives keep per-application entries.
- principle_class is the high-reliability canonical signal: the short, reusable leaf label of the value (e.g. "Public Safety Principle", "Honesty Principle"). REUSE an existing principle class from the list above and fold synonyms into it rather than minting a near-duplicate compound. The canonical leaf becomes the rdf:type at commit; case-specific detail belongs in the narrative fields, not the label.
- principle_category is the controlled kind and is used ONLY as the rdfs:subClassOf target when a genuinely new leaf class is minted. Set exactly one of fundamental_ethical, professional_virtue, relational, domain_specific. It is a routing input, not stored as a literal. Do not invent a kind outside this set.
- The five per-case narrative fields are the load-bearing per-individual signal and the provenance the defeasibility pass consumes: interpretation (what the principle requires here), concrete_expression (how it appears in this case), applied_to (the situation or party it bears on), balancing_with (the competing principle or value), tension_resolution (how the case resolves the tension). Populate each where the text supports it.
- invoked_by names the actor who invokes the principle (e.g. "Engineer A", or the NSPE Board of Ethical Review in the discussion). It resolves to the invokedBy edge at commit; name the actor, reusing a role-bearer identity from the cross-concept context where one fits.
- extensional_examples is an optional class-mint field carrying prior cases that instantiate the principle (McLaren extensional grounding); supply it only when minting a new class.
- Record the competing principle or value in balancing_with; do NOT assert defeat, precedence, or competition edges here. The defeasibility relations (competesWith, prevailsOver, defeasibleUnder) are produced by a separate pass from these literals.

MATCH DECISION RULES:
For each principle class, evaluate ONLY against the EXISTING PRINCIPLES IN ONTOLOGY list above. Cross-concept context from other extraction sections is provided so you can ground invoked_by and avoid re-extracting duplicates, but do NOT reference those entities in match_decision; that field is strictly for matching against the ontology list above.
- If the extracted principle IS the same concept as an existing class: match with HIGH confidence (0.85-1.0)
- If the extracted principle is a SPECIALIZATION of an existing class: match to parent with MEDIUM confidence (0.70-0.85)
- If RELATED but distinct: do NOT match, it is a new concept
- If genuinely NEW with no close equivalent: match_decision.matches_existing = false

OUTPUT FORMAT:
Return a JSON object with TWO arrays: new_principle_classes (reusable kinds of professional value) and principle_individuals (at most one individual per distinct value in this case). A Principle Class is a general reusable value (e.g. "Public Safety Principle"); a Principle Individual is the case's single record of that value: a case yields at most one principle individual per distinct value, with each application recorded in that individual's list fields, and distinct values remain separate individuals. Each individual MUST reference a class via the principle_class field.

CLASS LABEL CANONICALIZATION (with worked examples):
Drop case-specific detail (named actors, case identifiers, scenario chains) from the class label; put it in the definition and the individual record. Emit the short general right-hand form:
- "Engineer A's Duty to Hold Public Safety Paramount in the Bridge Review" -> "Public Safety Principle"
- "Obligation of Candor Owed to Client W" -> "Honesty Principle"
- "Loyalty to the Employing Firm" -> "Loyalty Principle"
Test: if a label could only ever apply to THIS case, generalize it until another case could reuse it.

CLASS SCHEMA (new_principle_classes array) -- each class is a JSON object:

  {
    "label": "Public Safety Principle",
    "definition": "The principle that a professional must hold the safety, health, and welfare of the public paramount in the exercise of professional duties.",
    "principle_category": "fundamental_ethical",
    "extensional_examples": ["BER Case 76-4 holding public safety paramount over client cost"],
    "text_references": ["the engineer must hold paramount the safety of the public"],
    "confidence": 0.9,
    "match_decision": {
      "matches_existing": false,
      "matched_uri": null,
      "matched_label": null,
      "confidence": 0,
      "reasoning": "No existing Public Safety Principle class; this is the paramount-welfare value the NSPE Code names first."
    }
  }

INDIVIDUAL SCHEMA (principle_individuals array) -- each individual is a JSON object:

  {
    "identifier": "Public Safety in Bridge Review",
    "principle_class": "Public Safety Principle",
    "interpretation": "In this case the principle requires the reviewing engineer to flag the structural deficiency despite schedule pressure.",
    "concrete_expression": "Engineer A's refusal to certify the design until the deficiency was corrected.",
    "applied_to": ["the decision whether to certify the bridge design"],
    "balancing_with": ["Loyalty Principle"],
    "tension_resolution": "Public safety prevailed over loyalty to the client's schedule.",
    "invoked_by": ["Engineer A"],
    "text_references": ["Engineer A declined to certify the design as submitted"],
    "confidence": 0.92
  }

Keep each individual's identifier short (the short concept plus the case anchor, at most about 6 words); scenario detail belongs in the narrative fields, not the identifier (it becomes the URI).

FORMATTING: do not use em dashes or en dashes in output text, and do not dodge with stacked parentheticals or excessive colons/semicolons; use commas or split into two sentences.
