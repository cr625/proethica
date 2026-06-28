=== WHAT A CONSTRAINT IS (ontology grounding) ===
A constraint is a prohibition or hard boundary: a directive information entity (BFO iao:0000033) that states what must NOT be done ("X must not be done", "may not", "is prohibited from"). It is the negative space of the normative layer. A constraint is distinct from an obligation: an obligation is a POSITIVE duty (a "shall" or "must do" clause), a constraint is a PROHIBITION. A "was required to do X" statement is an obligation and belongs to the obligation pass; only a "must not" or boundary statement is a constraint. This polarity is the defining signal.

EXISTING CONSTRAINTS IN ONTOLOGY:
{{ existing_constraints_text }}

{{ pass_directive }}

CROSS-CONCEPT CONTEXT (obligations, states, and resources already extracted in this case; ground constrained_entity in a named actor and the source in a named provision; do NOT re-extract them here):
{{ cross_concept_context }}

CASE TEXT:
{{ case_text }}

{{ constraint_schema }}

CONSTRAINT EXTRACTION DIRECTIVES (rules the ontology enforces):
- POLARITY first: emit only a PROHIBITION or hard boundary. If the text states a positive duty ("was required to", "shall", "must do"), that is an obligation, redirect it to the obligation pass and do NOT emit it here. A constraint says what must not be done.
- constraint_type is the controlled boundary type and the typing signal. Set exactly one of legal, regulatory, resource, competence, jurisdictional, procedural, safety, confidentiality, ethical, temporal, priority. It becomes the rdfs:subClassOf typing at commit, so a wrong boundary type collides with the disjointness axioms; a compound becomes a boundary-type subclass with the specificity carried in the label and definition. Do not invent a type outside this set.
- constraint_statement is the prohibition (the operative "must not" clause), stated for this case. It becomes the skos:definition / rdfs:comment.
- applicability_condition names the temporal and contextual circumstances under which the prohibition applies (the Dennis complete-specification condition): when and in what situation the boundary holds.
- constrained_entity names the agent whose conduct the constraint limits (e.g. "Engineer A"), reused from the roles pass. It resolves to the constrainedEntity edge; name the actor, not a role label.
- source names the provision or authority that establishes the prohibition (e.g. an NSPE Code section, a statute). It resolves to the establishedBy edge when the source resolves.
- severity records how serious the boundary is: critical, high, medium, or low (the Dennis severity ordering). It is a genuine attribute, not a defeasibility flag; do not assert flexibility or defeat here.

MATCH DECISION RULES:
For each constraint class, evaluate ONLY against the EXISTING CONSTRAINTS IN ONTOLOGY list above. Cross-concept context is provided so you can ground constrained_entity and source and avoid re-extracting duplicates, but do NOT reference those entities in match_decision; that field is strictly for matching against the ontology list above.
- If the extracted constraint IS the same concept as an existing class: match with HIGH confidence (0.85-1.0)
- If the extracted constraint is a SPECIALIZATION of an existing class: match to parent with MEDIUM confidence (0.70-0.85)
- If RELATED but distinct: do NOT match, it is a new concept
- If genuinely NEW with no close equivalent: match_decision.matches_existing = false

OUTPUT FORMAT:
Return a JSON object with TWO arrays: new_constraint_classes (reusable kinds of prohibition) and constraint_individuals (specific boundaries holding in this case). A Constraint Class is a general reusable prohibition kind (e.g. "Confidentiality Constraint"); a Constraint Individual is a specific boundary on a named actor in the case. Each individual MUST reference a class via the constraint_class field.

CLASS LABEL CANONICALIZATION (with worked examples):
Drop case-specific detail (named actors, case identifiers, scenario chains) from the class label; put it in the definition and the individual record. Emit the short general right-hand form:
- "Engineer A May Not Disclose the Acme Merger Terms" -> "Confidentiality Constraint"
- "The Firm May Not Practice Outside Its Licensed Discipline" -> "Jurisdictional Constraint"
- "No Certification Without an Adequate Structural Review" -> "Procedural Constraint"
Test: if a label could only ever apply to THIS case, generalize it until another case could reuse it.

CLASS SCHEMA (new_constraint_classes array) -- each class is a JSON object:

  {
    "label": "Confidentiality Constraint",
    "definition": "A prohibition on disclosing information a professional holds in confidence for a client or employer.",
    "constraint_type": "confidentiality",
    "text_references": ["Engineer A may not reveal the merger terms learned in confidence"],
    "confidence": 0.9,
    "match_decision": {
      "matches_existing": false,
      "matched_uri": null,
      "matched_label": null,
      "confidence": 0,
      "reasoning": "Confidentiality Constraint is the canonical confidentiality boundary type; no narrower existing class fits this prohibition."
    }
  }

INDIVIDUAL SCHEMA (constraint_individuals array) -- each individual is a JSON object:

  {
    "identifier": "Engineer A Merger Confidentiality",
    "constraint_class": "Confidentiality Constraint",
    "constraint_statement": "Engineer A must not disclose the Acme merger terms learned in confidence from Client W.",
    "applicability_condition": "While the merger remains non-public and Engineer A holds the client engagement.",
    "constrained_entity": "Engineer A",
    "source": "NSPE Code III.4",
    "temporal_scope": "For the duration of the engagement and after its termination",
    "severity": "high",
    "case_context": "Engineer A learned the merger terms while preparing the client's facility design.",
    "text_references": ["Engineer A may not reveal the merger terms learned in confidence"],
    "confidence": 0.92
  }

Keep each individual's identifier short (the actor plus the short boundary, at most about 6 words); scenario detail belongs in case_context, not the identifier (it becomes the URI). Set constrained_entity to the actor's stable identity, the same value the roles pass uses for that actor.

FORMATTING: do not use em dashes or en dashes in output text, and do not dodge with stacked parentheticals or excessive colons/semicolons; use commas or split into two sentences.
