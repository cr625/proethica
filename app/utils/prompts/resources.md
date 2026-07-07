{{ resource_definition }}

EXISTING RESOURCES IN ONTOLOGY:
{{ existing_resources_text }}

{{ pass_directive }}

CASE TEXT:
{{ case_text }}

{{ resource_schema }}

RESOURCE EXTRACTION DIRECTIVES (rules the ontology enforces):
{{ resource_boundary }}
{{ resource_individuation }}
- Do not invent a document_title the case does not state.
- resource_category is the controlled SOURCE KIND and the canonical typing signal. Set exactly one of ethical_code, technical_standard, case_precedent, legal_resource, reference_material. It becomes the rdfs:subClassOf typing at commit (ethical_code is typed EthicalCode subClassOf Guideline subClassOf Resource; the other four subClassOf Resource), so a wrong kind collides with the disjointness axioms. It is a routing input, not stored as a literal. Do not invent a kind outside this set. A profession's code of ethics is ethical_code.
- The source kind is the class identity. Do NOT fold topic, who used it, or the document title into the class label; those are context carried on their own fields.
- document_title names the specific source document (e.g. "NSPE Code of Ethics", "ASCE Standard 7").
- topic names the subject the resource addresses, carried on the declared proeth:topic property, not on the overflow string.
- used_by and cited_by are two distinct signals and resolve to two distinct edges. used_by is the Facts-section signal: the case actor who RELIED on the resource (resolves to availableTo). cited_by is the Discussion-section signal: who invoked it as AUTHORITY (resolves to citedByAgent, commonly the NSPE Board of Ethical Review or NSPE the institution). Name the actor, not a role label.
- provision_codes: when the resource is a code, standard, or regulation, this list is its PRIMARY content and MUST be populated. Scan the whole case (facts and discussion) for every provision the case attributes to that source and list them all, capturing each Canon and Code section number (e.g. "I.1", "I.2", "I.5", "II.1.c", "II.2.a", "II.2.b", "III.8.a", "III.9"). An empty provision_codes on a cited code is an extraction error. Leave empty only for a non-code resource (a precedent opinion, a tool, a generic reference).
- Emit one resource individual per distinct source used or cited, not one per canon citation. The individual canon and section citations belong inside that source's provision_codes list, not as separate resources.
- A prior board opinion or precedent the case relies on (e.g. "BER Case 90-6", "BER Case 98-3") is a legitimate case_precedent resource of THIS case, not contamination. Extract each cited precedent as its own resource individual.

MATCH DECISION RULES:
For each resource class, evaluate ONLY against the EXISTING RESOURCES IN ONTOLOGY list above. Evaluate match_decision strictly against the ontology list above; used_by and cited_by are free-text party names resolved to case agents at commit.
- If the extracted resource IS the same concept as an existing class: match with HIGH confidence (0.85-1.0)
- If the extracted resource is a SPECIALIZATION of an existing class: match to parent with MEDIUM confidence (0.70-0.85)
- If RELATED but distinct: do NOT match, it is a new concept
- If genuinely NEW with no close equivalent: match_decision.matches_existing = false

OUTPUT FORMAT:
Return a JSON object with TWO arrays: new_resource_classes (reusable kinds of professional knowledge source) and resource_individuals (specific documents used or cited in this case). A Resource Class is a general reusable source type (e.g. "Ethical Code"); a Resource Individual is a specific document in the case (e.g. "NSPE Code of Ethics"). Each individual MUST reference a class via the resource_class field.

CLASS LABEL CANONICALIZATION (with worked examples):
Drop case-specific detail (named actors, case identifiers, topic) from the class label; put it in the definition and the individual record. Emit the short general right-hand form:
- "The NSPE Code Provision on Public Safety Cited Against Engineer A" -> "Ethical Code"
- "ASCE Standard the Reviewer Applied to the Soil Report" -> "Technical Standard"
- "BER Case 76-4 Relied On as Precedent" -> "Case Precedent"
Test: if a label could only ever apply to THIS case, generalize it until another case could reuse it.

CLASS SCHEMA (new_resource_classes array) -- each class is a JSON object:

  {
    "label": "Ethical Code",
    "definition": "A formal document that codifies ethical principles and professional conduct requirements for a profession.",
    "resource_category": "ethical_code",
    "text_references": ["the NSPE Code of Ethics requires engineers to hold paramount public safety"],
    "confidence": 0.9,
    "match_decision": {
      "matches_existing": true,
      "matched_uri": null,
      "matched_label": "Ethical Code",
      "confidence": 0.95,
      "reasoning": "Ethical Code is the canonical source kind for a society's ethics code and already exists in the ontology; no narrower class is required."
    }
  }

INDIVIDUAL SCHEMA (resource_individuals array) -- each individual is a JSON object:

  {
    "identifier": "NSPE Code of Ethics",
    "resource_class": "Ethical Code",
    "document_title": "NSPE Code of Ethics",
    "topic": "professional duties of engineers",
    "used_by": "Engineer A",
    "cited_by": "NSPE Board of Ethical Review",
    "provision_codes": ["I.1", "II.2.b"],
    "text_references": ["the Board cited Section I.1 of the Code"],
    "confidence": 0.92
  }

Keep each individual's identifier short (the document name, at most about 6 words); it becomes the URI.

FORMATTING: do not use em dashes or en dashes in output text, and do not dodge with stacked parentheticals or excessive colons/semicolons; use commas or split into two sentences.
