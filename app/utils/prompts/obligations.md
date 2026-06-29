=== WHAT AN OBLIGATION IS (ontology grounding) ===
An obligation is a specific professional duty: a requirement for action or restraint that binds a role-bearer (a directive information entity, BFO iao:0000033). It operationalizes a principle into a concrete "shall" or "must" clause owed by a particular party in the case. An obligation is distinct from a principle (the value it serves), from a constraint (a prohibition or hard boundary, "must not"), and from an action (the act that fulfills or violates it). A positive duty to do X is an obligation; a prohibition on doing X is a constraint and belongs to the constraint pass.

EXISTING OBLIGATIONS IN ONTOLOGY:
{{ existing_obligations_text }}

{{ pass_directive }}

CROSS-CONCEPT CONTEXT (roles and principles already extracted in this case; ground obligated_party in a named role-bearer and derived_from_principle in a named principle; do NOT re-extract roles or principles here):
{{ cross_concept_context }}

CASE TEXT:
{{ case_text }}

{{ obligation_schema }}

OBLIGATION EXTRACTION DIRECTIVES (rules the ontology enforces):
- NEGATIVE BOUNDARY: an obligation is NOT a principle and NOT a constraint. It is a concrete positive duty owed by a party, distinct from the abstract value behind it (a principle) and from a hard prohibition (a constraint). If the candidate is an abstract value, redirect it to the principle pass; if it is a "must not", redirect it to the constraint pass.
- obligation_type is the controlled typing signal. Set exactly one of the NSPE categories disclosure, safety, competence, confidentiality, reporting, collegial, legal, ethical. The category becomes the rdfs:subClassOf core:Obligation typing at commit, so a wrong category collides with the disjointness axioms rather than passing silently. Do not invent a category outside this set.
- obligated_party names the duty-bearer: the stable actor identity who bears the obligation (e.g. "Engineer A"), reused from the roles pass, not a role label. It resolves to the obligatedParty edge at commit; name the actor, do not describe the duty here.
- derived_from_principle names the principle the duty operationalizes (the P side of R->P->O). It resolves to the derivedFromPrinciple edge. Use a principle label from the cross-concept context above where one fits.
- obligation_statement is the concrete duty (the operative "shall" or "must" clause), stated for this case.
- Distinguish an obligation from a constraint: a "was required to do X" or "shall do X" statement is an obligation; a "must not", "may not", or "is prohibited from" statement is a constraint and is left to the constraint pass. Do not emit a prohibition as an obligation.
- Use a canonical, short, reusable obligation label (the D-LABEL rule below) and REUSE an existing obligation class from the list above rather than minting a near-duplicate compound.
- Do not assert obligation competition, defeat, or precedence here. The defeasibility relations (competesWith, prevailsOver, defeasibleUnder) are produced by a separate pass.

MATCH DECISION RULES:
For each obligation class, evaluate ONLY against the EXISTING OBLIGATIONS IN ONTOLOGY list above. Cross-concept context from other extraction sections is provided so you can ground the edges and avoid re-extracting duplicates, but do NOT reference those entities in match_decision; that field is strictly for matching against the ontology list above.
- If the extracted obligation IS the same concept as an existing class: match with HIGH confidence (0.85-1.0)
- If the extracted obligation is a SPECIALIZATION of an existing class: match to parent with MEDIUM confidence (0.70-0.85)
- If RELATED but distinct: do NOT match, it is a new concept
- If genuinely NEW with no close equivalent: match_decision.matches_existing = false

OUTPUT FORMAT:
Return a JSON object with TWO arrays: new_obligation_classes (reusable types of professional duty) and obligation_individuals (specific duties borne by a party in this case). An Obligation Class is a general reusable type (e.g. "Disclosure Obligation"); an Obligation Individual is a specific duty owed by a named actor in the case. Each individual MUST reference a class via the obligation_class field.

CLASS LABEL CANONICALIZATION (the D-LABEL directive, with worked examples):
Drop case-specific detail (named actors, case identifiers, scenario chains) from the class label; put it in the definition and the individual record. Emit the short general right-hand form:
- "Engineer A's Duty to Disclose the AI Tool to Client W" -> "AI Tool Disclosure Obligation"
- "Obligation to Report the Suppressed Soil Report to the City" -> "Reporting Obligation"
- "Duty to Keep the Acme Merger Terms Confidential" -> "Confidentiality Obligation"
Test: if a label could only ever apply to THIS case, generalize it until another case could reuse it.

CLASS SCHEMA (new_obligation_classes array) -- each class is a JSON object:

  {
    "label": "AI Tool Disclosure Obligation",
    "definition": "A professional duty to disclose to the client that AI-assisted tools were used to prepare the deliverable.",
    "obligation_type": "disclosure",
    "derived_from_principle": "Honesty and Transparency",
    "text_references": ["Engineer A used an AI-assisted drafting tool to prepare the design documents"],
    "confidence": 0.9,
    "match_decision": {
      "matches_existing": false,
      "matched_uri": null,
      "matched_label": null,
      "confidence": 0,
      "reasoning": "Disclosure Obligation exists in the ontology, but AI Tool Disclosure captures the specific duty to disclose tool authorship distinct from general conflict or interest disclosure."
    }
  }

INDIVIDUAL SCHEMA (obligation_individuals array) -- each individual is a JSON object:

  {
    "identifier": "Engineer A AI Disclosure Duty",
    "obligation_class": "AI Tool Disclosure Obligation",
    "obligated_party": "Engineer A",
    "obligation_statement": "Engineer A must disclose to Client W that AI-assisted drafting tools were used to prepare the design documents.",
    "derived_from_principle": "Honesty and Transparency",
    "temporal_scope": "At the time of delivering the design documents to the client",
    "compliance_status": "unmet",
    "case_context": "Engineer A delivered AI-assisted design documents without disclosing the tool's use.",
    "text_references": ["Engineer A did not inform Client W that the documents were AI-assisted"],
    "confidence": 0.92
  }

Keep each individual's identifier short (the case actor plus the short concept, at most about 6 words); scenario detail belongs in case_context, not the identifier (it becomes the URI). Set obligated_party to the actor's stable identity (the same value the roles pass uses for that actor), not a role label, so the obligatedParty edge resolves to one Agent.

FORMATTING: do not use em dashes or en dashes in output text, and do not dodge with stacked parentheticals or excessive colons/semicolons; use commas or split into two sentences.
