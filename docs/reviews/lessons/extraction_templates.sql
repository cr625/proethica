-- Case 24-1 (ProEthica case 8) review: prompt-template lessons.
--
-- The live extraction prompts are the extraction_prompt_templates rows (template_text, one row
-- per pass_type, 'facts' and 'discussion', sharing one body per concept). They cannot be changed
-- from code, so each lesson that needs template wording is applied here as an UPDATE carrying the
-- FULL new text. The new text is the seed body app/utils/prompts/<concept>.md as committed on the
-- branch review/case8-lessons/prompts-and-filters, so a re-seed from those files produces the same
-- rows. Code-side changes (per-pass directives, validators, filters, the segmenter) are in the
-- Python modules of the same branch and are not repeated here.
--
-- Before applying, diff each live row against the seed body of the base commit to confirm the row
-- has not been edited in the prompt editor since seeding. Each block first records the current
-- text in extraction_prompt_template_versions (the same bookkeeping as
-- ExtractionPromptTemplate.save_new_version) and then replaces template_text and bumps version.
-- The variables the bodies reference are unchanged, so variables_schema needs no update.
--
-- Apply with: psql -h localhost -U postgres -d ai_ethical_dm -v ON_ERROR_STOP=1 -f extraction_templates.sql

BEGIN;

-- ===================================================================================
-- principles (step 2, pass rows facts and discussion)
-- L2: BALANCING CHECK: a populated tension_resolution with an empty balancing_with is named as rejected at validation (the schema validator added in schemas.py).
-- L2: New PASS SPLIT bullet: the facts pass records balancing_with and leaves tension_resolution empty whenever the facts resolve nothing, never a placeholder such as 'unresolved in the facts', and the discussion pass re-emits that individual with the same identifier and the Board's resolution.
-- L1: OUTPUT FORMAT: the per-value rule holds across passes, so an individual listed in the PRINCIPLES INDIVIDUALS ALREADY EXTRACTED block is refined under its identifier, never extracted a second time (two PublicWelfarePrinciple and two TransparencyPrinciple individuals were committed for case 8).
INSERT INTO extraction_prompt_template_versions
    (template_id, version_number, template_text, variables_schema, change_description, changed_by, changed_at)
SELECT id, version, template_text, variables_schema,
       'case-8 review lessons (L1, L2): see docs/reviews/lessons/extraction_templates.sql',
       'review/case8-lessons', now()
FROM extraction_prompt_templates
WHERE extraction_type = 'case' AND step_number = 2 AND concept_type = 'principles' AND is_active = true;

UPDATE extraction_prompt_templates
SET template_text = $proethica_tpl${{ principle_definition }}

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
- BALANCING CHECK (do this for EACH principle individual): before finalizing the individual, check whether the case weighs this value against another extracted value, in the discussion's tension, balancing, competing-duty, "outweighs", "paramount over", or "conflicted with" language. When it does, record that competing value's principle label in balancing_with and record how the case resolves the tension in tension_resolution; the two fields travel together, and a populated tension_resolution whose balancing_with is empty is incomplete because the resolution names a tension whose other side went unrecorded (such a tension_resolution is rejected at validation). Leave balancing_with empty only when the case presents no tension for this value. Record only tensions the case actually presents; do not invent a competing value.
- PASS SPLIT of the balancing fields: the Facts narrate a tension, the Board resolves it. In the facts pass, record balancing_with when the facts show competing values and leave tension_resolution EMPTY whenever the facts resolve nothing; never write a placeholder such as "unresolved in the facts" into it. In the discussion pass, a facts-pass individual listed with balancing_with set and tension_resolution empty is re-emitted with the SAME identifier and class and the Board's resolution; a second individual for the same value is an error.
- invoked_by names the actor who invokes the principle (e.g. "Engineer A", or the NSPE Board of Ethical Review in the discussion). It resolves to the invokedBy edge at commit; name the actor, reusing a role-bearer identity from the cross-concept context where one fits.
- extensional_cases is an optional class-mint field carrying prior cases that instantiate the principle (McLaren extensional grounding); supply it only when minting a new class.
- Record the competing principle or value in balancing_with; do NOT assert defeat, precedence, or competition edges here. The defeasibility relations (competesWith, prevailsOver, defeasibleUnder) are produced by a separate pass from these literals.

MATCH DECISION RULES:
For each principle class, evaluate ONLY against the EXISTING PRINCIPLES IN ONTOLOGY list above. Cross-concept context from other extraction sections is provided so you can ground invoked_by and avoid re-extracting duplicates, but do NOT reference those entities in match_decision; that field is strictly for matching against the ontology list above.
- If the extracted principle IS the same concept as an existing class: match with HIGH confidence (0.85-1.0)
- If the extracted principle is a SPECIALIZATION of an existing class: match to parent with MEDIUM confidence (0.70-0.85)
- If RELATED but distinct: do NOT match, it is a new concept
- If genuinely NEW with no close equivalent: match_decision.matches_existing = false

OUTPUT FORMAT:
Return a JSON object with TWO arrays: new_principle_classes (reusable kinds of professional value) and principle_individuals (at most one individual per distinct value in this case). A Principle Class is a general reusable value (e.g. "Public Safety Principle"); a Principle Individual is the case's single record of that value: a case yields at most one principle individual per distinct value, with each application recorded in that individual's list fields, and distinct values remain separate individuals. The per-value rule holds ACROSS passes: when a "PRINCIPLES INDIVIDUALS ALREADY EXTRACTED FROM PRIOR SECTIONS" block appears above, an individual listed there is refined under its own identifier (REUSE or REFINE), never extracted a second time. Each individual MUST reference a class via the principle_class field.

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
    "extensional_cases": ["BER Case 76-4 holding public safety paramount over client cost"],
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
$proethica_tpl$,
    version = version + 1,
    updated_at = now()
WHERE extraction_type = 'case' AND step_number = 2 AND concept_type = 'principles' AND is_active = true;

-- ===================================================================================
-- obligations (step 2, pass rows facts and discussion)
-- L2: obligation_statement keeps to the Code's own wording plus the Board's application to the actor, without widening or hardening the duty.
-- L2: New compliance_status bullet: the facts pass emits 'unclear' on every individual, the discussion pass sets met, unmet or partial from the holding and confirms or revises every facts-pass status by re-emitting the individual under the same identifier (case 8 set 'partial' in the facts pass and never revised it).
-- L2: Note after the worked example: its compliance_status is a discussion-pass value, the facts pass emits 'unclear'.
INSERT INTO extraction_prompt_template_versions
    (template_id, version_number, template_text, variables_schema, change_description, changed_by, changed_at)
SELECT id, version, template_text, variables_schema,
       'case-8 review lessons (L2): see docs/reviews/lessons/extraction_templates.sql',
       'review/case8-lessons', now()
FROM extraction_prompt_templates
WHERE extraction_type = 'case' AND step_number = 2 AND concept_type = 'obligations' AND is_active = true;

UPDATE extraction_prompt_templates
SET template_text = $proethica_tpl${{ obligation_definition }}

EXISTING OBLIGATIONS IN ONTOLOGY:
{{ existing_obligations_text }}

{{ pass_directive }}

CROSS-CONCEPT CONTEXT (roles and principles already extracted in this case; ground obligated_party in a named role-bearer and derived_from_principle in a named principle; do NOT re-extract roles or principles here):
{{ cross_concept_context }}

CASE TEXT:
{{ case_text }}

{{ obligation_schema }}

OBLIGATION EXTRACTION DIRECTIVES (rules the ontology enforces):
{{ obligation_boundary }}
{{ obligation_individuation }}
- obligation_type is the controlled typing signal. Set exactly one of the NSPE categories disclosure, safety, competence, confidentiality, reporting, collegial, attribution, legal, ethical. The category becomes the rdfs:subClassOf core:Obligation typing at commit, so a wrong category collides with the disjointness axioms rather than passing silently. Do not invent a category outside this set. attribution is the NSPE III.9 credit duty (give credit for engineering work to those to whom credit is due, including tool-assisted content); a duty to CREDIT is attribution, while a duty to INFORM a stakeholder of a fact is disclosure.
- obligated_party names the duty-bearer: the stable actor identity who bears the obligation (e.g. "Engineer A"), reused from the roles pass, not a role label. It resolves to the obligatedParty edge at commit; name the actor, do not describe the duty here.
- derived_from_principle names the principle the duty operationalizes (the P side of R->P->O). It is stored and fed to the dedicated R->P->O pass, which derives the derivedFromPrinciple edge at commit. Use a principle label from the cross-concept context above where one fits.
- obligation_statement is the concrete duty (the operative "shall" or "must" clause), stated for this case in the Code's own wording plus the Board's application of it to the actor; do not widen or harden the duty beyond what the Code and the holding state.
- compliance_status is holding-dependent and follows the PASS SPLIT: the Facts establish duties, not their discharge, so the facts pass emits "unclear" on every obligation individual. The discussion pass sets met, unmet, or partial from the Board's holding, and it must confirm or revise EVERY facts-pass status by re-emitting that individual with the SAME identifier and class (the "OBLIGATIONS INDIVIDUALS ALREADY EXTRACTED FROM PRIOR SECTIONS" block lists them); a second individual for the same duty is an error.
- Distinguish an obligation from a constraint: a "was required to do X" or "shall do X" statement is an obligation; a "must not", "may not", or "is prohibited from" statement is a constraint and is left to the constraint pass. Do not emit a prohibition as an obligation.
- A must-not or shall-not statement is a Constraint, not an Obligation.
- Required-ness is the differentia: guidance the source treats as recommended best practice is not an Obligation and routes to the Principle pass.
- A duty to comply with named requirements is a positive duty and is an Obligation even when the requirements themselves are Constraints.
- Single-home rule: a provision the code states negatively (shall not X) is extracted once, as a Constraint; the Obligation pass records only a separately stated positive duty and cross-references the constraint rather than restating the prohibition.
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

Keep each individual's identifier short (the case actor plus the short concept, at most about 6 words); scenario detail belongs in case_context, not the identifier (it becomes the URI). Set obligated_party to the actor's stable identity (the same value the roles pass uses for that actor), not a role label, so the obligatedParty edge resolves to one Agent. The compliance_status in the worked example is a discussion-pass value; in the facts pass it is "unclear".

FORMATTING: do not use em dashes or en dashes in output text, and do not dodge with stacked parentheticals or excessive colons/semicolons; use commas or split into two sentences.
$proethica_tpl$,
    version = version + 1,
    updated_at = now()
WHERE extraction_type = 'case' AND step_number = 2 AND concept_type = 'obligations' AND is_active = true;

-- ===================================================================================
-- constraints (step 2, pass rows facts and discussion)
-- L2: New PASS SPLIT bullet: a prohibition on the engineer that the Facts do not state in words is a holding and belongs to the discussion pass, the facts pass returns empty arrays when the Facts state no prohibition (case 8's facts pass emitted the Board's 'must not acquiesce' holding).
-- L1: Same bullet: a holding that restates a facts-pass constraint refines that individual under the same identifier, two near-identical constraint_statements are an error (two FaithfulAgentLimitConstraint individuals were committed for case 8).
INSERT INTO extraction_prompt_template_versions
    (template_id, version_number, template_text, variables_schema, change_description, changed_by, changed_at)
SELECT id, version, template_text, variables_schema,
       'case-8 review lessons (L1, L2): see docs/reviews/lessons/extraction_templates.sql',
       'review/case8-lessons', now()
FROM extraction_prompt_templates
WHERE extraction_type = 'case' AND step_number = 2 AND concept_type = 'constraints' AND is_active = true;

UPDATE extraction_prompt_templates
SET template_text = $proethica_tpl${{ constraint_definition }}

EXISTING CONSTRAINTS IN ONTOLOGY:
{{ existing_constraints_text }}

{{ pass_directive }}

CROSS-CONCEPT CONTEXT (obligations, states, and resources already extracted in this case; ground constrained_entity in a named actor and the source in a named provision; do NOT re-extract them here):
{{ cross_concept_context }}

CASE TEXT:
{{ case_text }}

{{ constraint_schema }}

CONSTRAINT EXTRACTION DIRECTIVES (rules the ontology enforces):
{{ constraint_boundary }}
{{ constraint_individuation }}
- POLARITY first: emit only a PROHIBITION or hard boundary. If the text states a positive duty ("was required to", "shall", "must do"), that is an obligation, redirect it to the obligation pass and do NOT emit it here. A constraint says what must not be done.
- PASS SPLIT: a prohibition on the engineer that the Facts do not state in words is a HOLDING, not a fact. It belongs to the discussion pass; when the Facts state no prohibition, the facts pass returns empty arrays. In the discussion pass, a holding that restates a facts-pass constraint refines that individual (re-emit it with the SAME identifier and class and the holding's wording); it does not mint a second individual, and near-identical constraint_statements under two identifiers are an error.
- Single-home rule: a provision the code states negatively (shall not X) is extracted once, as a Constraint; the Obligation pass records only a separately stated positive duty and cross-references the constraint rather than restating the prohibition.
- INDIVIDUAL EMISSION (dual output; read the single-home rule correctly): "extracted once, as a Constraint" decides WHICH PASS owns a norm (Constraint, not Obligation); it does NOT mean one record. Within this pass a case-grounded prohibition is emitted BOTH as its class (new, or matched to an existing ontology class) AND as a constraint_individuals entry referencing that class. The individual is what carries the per-case fields (constrained_entity, applicability_condition, severity, source); the class cannot carry them. Matching an existing class does NOT record the case's boundary and is never a reason to omit the individual: a matched class still requires its case individual. Emit one individual for every prohibition the case holds a named actor to; an empty constraint_individuals array is correct only when the pass yields no case-grounded prohibition at all.
- constraint_type is the controlled boundary type and the typing signal. Set exactly one of legal, regulatory, resource, competence, jurisdictional, procedural, safety, confidentiality, ethical, temporal. It becomes the rdfs:subClassOf typing at commit; set the single best-fitting type (the ten kinds carry no disjointness axioms, so precision rests on this choice). A compound becomes a boundary-type subclass with the specificity carried in the label and definition. Do not invent a type outside this set.
- constraint_statement is the prohibition (the operative "must not" clause), stated for this case. It becomes the skos:definition / rdfs:comment.
- applicability_condition names the situational circumstances under which the prohibition applies (the Dennis specification-by-context condition): in what situation the boundary holds.
- temporal_scope states WHEN the boundary is in force: a durational window (e.g. for the duration of the engagement), distinct from the applicability trigger.
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
Return a JSON object with TWO arrays: new_constraint_classes (reusable kinds of prohibition) and constraint_individuals (specific boundaries holding in this case). A Constraint Class is a general reusable prohibition kind (e.g. "Confidentiality Constraint"); a Constraint Individual is a specific boundary on a named actor in the case. Each individual MUST reference a class via the constraint_class field. The two arrays answer different questions: the class names the reusable kind, the individual records the boundary actually holding on a named actor in THIS case. A class alone, including a class matched to the existing ontology, leaves the case unrecorded; whenever the case text holds an actor to a prohibition, emit the matching constraint_individuals entry (see the INDIVIDUAL SCHEMA worked example below for the expected per-case detail).

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
$proethica_tpl$,
    version = version + 1,
    updated_at = now()
WHERE extraction_type = 'case' AND step_number = 2 AND concept_type = 'constraints' AND is_active = true;

-- ===================================================================================
-- roles (step 1, pass rows facts and discussion)
-- L9: MATCH DECISION RULES: when a canonical class and a previously extracted class both fit, match the canonical class (the Board of Ethical Review is a Regulatory Authority Role, whose definition names an ethics review board).
-- L9: INDIVIDUAL SCHEMA: the generates_obligations routing input is shown in the worked example.
-- L9: ROLE TYPING FIELDS: role_kind professional requires at least one obligation named in generates_obligations, otherwise the individual is participant or leaves role_kind unset, and a reviewing or oversight body is participant (the parse-time check in role_checks.py rejects an unsupported professional typing).
-- L9: New ONE FACET PER COUNTERPARTY paragraph: a relational standing toward a counterparty already linked by an actor edge is a relationships[] entry or a role_category on the existing facet, never a new facet (the faithful-agent facet minted beside the design-engineer facet in case 8).
INSERT INTO extraction_prompt_template_versions
    (template_id, version_number, template_text, variables_schema, change_description, changed_by, changed_at)
SELECT id, version, template_text, variables_schema,
       'case-8 review lessons (L9): see docs/reviews/lessons/extraction_templates.sql',
       'review/case8-lessons', now()
FROM extraction_prompt_templates
WHERE extraction_type = 'case' AND step_number = 1 AND concept_type = 'roles' AND is_active = true;

UPDATE extraction_prompt_templates
SET template_text = $proethica_tpl${{ role_definition }}

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
- When a CANONICAL class and a PREVIOUSLY EXTRACTED class both fit a role, match the canonical class: read the canonical definitions first (the NSPE Board of Ethical Review is a Regulatory Authority Role, whose definition names an ethics review board), and choose a previously extracted class only when no canonical class covers the role.

OUTPUT FORMAT:
Return a JSON object with TWO arrays: new_role_classes (reusable types/categories of roles) and role_individuals (specific persons/entities filling those roles). A Role Class is a general reusable type (e.g. "Design Engineer"); a Role Individual is a specific named actor in the case (e.g. "Engineer A Design Engineer"). Each individual MUST reference a class via the role_class field.

VALID role_class values: (a) a label from EXISTING ROLES above, (b) a label from your new_role_classes array (exact match), or (c) a base category: Provider-Client Role, Professional Peer Role, Employer Relationship Role, Public Responsibility Role, Participant Role. Do not invent class names outside (a)-(c). Prefer the most specific correct type over the bare base class "Role".

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
    "role_kind": "professional",
    "distinguishing_features": ["Creates original designs rather than reviewing them"],
    "professional_scope": "Original engineering design within the licensed discipline",
    "typical_qualifications": ["Professional Engineer license", "Discipline-specific design experience"],
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
    "role_kind": "professional",
    "generates_obligations": ["Duty to hold paramount the safety, health, and welfare of the public in the tower design"],
    "case_involvement": "Created original tower designs containing significant errors",
    "license": "Professional Engineer",
    "specialty": "Structural design",
    "attributes": [{"key": "professional_membership", "value": "ASCE member"}],
    "relationships": [{"type": "hasClient", "target": "Owner", "quote": "Engineer A was retained by the Owner to design the tower"}, {"type": "workReviewedBy", "target": "Engineer B", "quote": "Engineer B was engaged to review Engineer A's work"}],
    "text_references": ["plans and design of Engineer A", "Engineer A objects and refused to consent"],
    "confidence": 0.90
  }

Keep each individual's identifier short (the case actor plus the short concept, at most about 6 words); scenario detail belongs in case_involvement, not the identifier (it becomes the URI).

ROLE TYPING FIELDS (role_category and role_kind are routing inputs, never stored as literals):
- role_category is the RELATIONAL category, one of the four Kong values (provider_client, professional_peer, employer_relationship, public_responsibility) or omitted when the role bears none. It is a FALLBACK: when the role bears an actor relationship (the relationships[] field), that edge determines the relational archetype and wins on conflict, so set role_category to agree with the directed edge you emit.
- role_kind is the OCCUPATIONAL backstop, professional or participant. Set it when the case states the judgment; omit it when unstated (do not guess). It types a role that matches no known occupational class onto the professional/participant axis. The do-not-establish-professional-obligations test: a party with no professional obligations is participant.
- role_kind professional REQUIRES at least one obligation the role generates, named in generates_obligations as the case states it (a routing input, not stored). An individual that names none is participant, or leaves role_kind unset; a professional typing with no obligation named is rejected at parse time. A reviewing or oversight body (an ethics review board, a licensure board) bears statutory oversight, not profession-generated obligations, and is participant.

{{ role_relationships }}

ACTOR IDENTITY (cross-section): each role individual names a role FACET that some underlying actor plays. Set `actor` to that actor's stable identity (e.g. "Engineer A", "Owner", "City of X"), kept separate from the role facet in `identifier`. The SAME actor seen in a different section under a different role facet MUST reuse the SAME `actor` value. When an "ACTORS ALREADY IDENTIFIED IN PRIOR SECTIONS" block appears above the case text, reuse those actor identities exactly. One Agent is minted per distinct actor and bears each facet, so consistent actor naming is what keeps a person from being fragmented across sections.

ONE FACET PER COUNTERPARTY: a relational standing toward a counterparty the actor is ALREADY linked to by an actor edge (a faithful-agent, fiduciary, or trustee standing toward an existing client, employer, or peer) is a relationships[] entry or a role_category on the EXISTING facet, never a new role facet. Mint a second facet for the same actor only for a genuinely different occupational role; a duplicate relational facet is folded into the existing facet at parse time.

FORMATTING: do not use em dashes or en dashes in output text, and do not dodge with stacked parentheticals or excessive colons/semicolons; use commas or split into two sentences.
$proethica_tpl$,
    version = version + 1,
    updated_at = now()
WHERE extraction_type = 'case' AND step_number = 1 AND concept_type = 'roles' AND is_active = true;

-- ===================================================================================
-- states (step 1, pass rows facts and discussion)
-- L8: New bullet: active_period is written in narrative order, from the triggering happening to the terminating one (a case-8 state carried the period end first).
INSERT INTO extraction_prompt_template_versions
    (template_id, version_number, template_text, variables_schema, change_description, changed_by, changed_at)
SELECT id, version, template_text, variables_schema,
       'case-8 review lessons (L8): see docs/reviews/lessons/extraction_templates.sql',
       'review/case8-lessons', now()
FROM extraction_prompt_templates
WHERE extraction_type = 'case' AND step_number = 1 AND concept_type = 'states' AND is_active = true;

UPDATE extraction_prompt_templates
SET template_text = $proethica_tpl${{ state_definition }}

EXISTING STATES IN ONTOLOGY:
{{ existing_states_text }}

{{ pass_directive }}

CROSS-CONCEPT CONTEXT (entities already extracted in this case, when any exist at this stage; states extract first in the current pipeline, so this section is normally empty and the linkage fields are grounded at commit; do NOT re-extract them here):
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
- Edge-only linkage fields, converted to edges at commit and not stored as literals: obligation_activation names the obligations the state makes applicable (the activatesObligation edge); action_constraints names the constraints it activates; activation_conditions and termination_conditions are the class-level Event-Calculus fields; affected_parties names the agents the state affects (the affects edge).
- Kept-literal fields: triggering_event and terminated_by are stored verbatim on the individual AND resolved to the activatedByEvent/terminatedByEvent edges, and subject (what is in the state) is stored as a literal; all three later feed the defeasibility prompt as state context, so write full, readable phrases, not terse edge fodder. Provide every field where the text supports it.
- active_period is written in NARRATIVE ORDER, from the triggering happening to the terminating one (start first, end last), as in "From the second retention until withdrawal"; never the end first.
- Do not assert obligation competition, defeat, or precedence here. The defeasibility relations are produced by a separate pass.

MATCH DECISION RULES:
For each state class, evaluate ONLY against the EXISTING STATES IN ONTOLOGY list above. The cross-concept section above is normally empty at the states stage; when populated it helps avoid duplicates, but do NOT reference those entities in match_decision; that field is strictly for matching against the ontology list above.
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
$proethica_tpl$,
    version = version + 1,
    updated_at = now()
WHERE extraction_type = 'case' AND step_number = 1 AND concept_type = 'states' AND is_active = true;

-- ===================================================================================
-- actions (step 3, pass rows facts and discussion)
-- L8: initiates / terminates name State labels of this case only (the CASE STATE LABELS closed list when supplied), a label equal to an Action or Event label is dropped.
-- L8: New modality bullet and ITEM FIELDS entry: performed versus prescribed, a Board holding ('cannot ethically acquiesce') is a prescribed act and never a performed Action with a present-tense temporal_marker.
INSERT INTO extraction_prompt_template_versions
    (template_id, version_number, template_text, variables_schema, change_description, changed_by, changed_at)
SELECT id, version, template_text, variables_schema,
       'case-8 review lessons (L8): see docs/reviews/lessons/extraction_templates.sql',
       'review/case8-lessons', now()
FROM extraction_prompt_templates
WHERE extraction_type = 'case' AND step_number = 3 AND concept_type = 'actions' AND is_active = true;

UPDATE extraction_prompt_templates
SET template_text = $proethica_tpl$You are an expert in professional ethics extracting ACTIONS (volitional professional decisions) from an engineering ethics case.

{{ action_definition }}

**TYPING DIRECTIVES (rules the ontology enforces):**
{{ action_boundary }}
{{ action_individuation }}

{{ pass_directive }}

**INDIVIDUALS ONLY (mints no classes):**
Actions are extracted as case individuals only. This pass mints NO action classes and applies no topical action taxonomy; every extracted action is typed directly as an Action occurrence of this case.

**EXTRACTION GUIDELINES:**

- Extract only volitional professional decisions, not occurrences/events.
- An omission, a required or expected act not performed, is extractable as an Action when the case treats the non-performance as the agent's conduct.
- Extract atomic actions: split compound descriptions.
- Capture the intention behind each action (Doctrine of Double Effect): mental state, intended outcome, foreseen unintended effects, agent knowledge.
- Name obligations and principles using the SAME names they carry elsewhere in the case (the obligation/principle individuals already extracted), not fresh paraphrases; they are resolved downstream to the actual individuals (Action fulfillsObligation / violatesObligation / guidedByPrinciple edges). Do NOT list constraints or competing obligation pairs; constraint activation is carried by the State an action initiates, and obligation competition by the case's defeasibility edges.
- Each guiding_principles entry must name a Principle extracted for this case (a label match to one of the case's principle individuals). When an extracted principle plausibly guided the action, name it here; most deliberate professional actions are guided by at least one of the case's principles. A motive, goal, or adverb such as "Speed", "Efficiency", or "Meeting the deadline" is NOT a principle and is invalid; use an empty list only when no extracted principle applies.
- initiates / terminates name the STATES (fluents) the action brings into or out of holding (Event Calculus; Kowalski & Sergot 1986, Berreby et al. 2017), using the same state names used elsewhere in the case. They name State labels of this case ONLY (the CASE STATE LABELS list when one is supplied is a closed list); a label equal to an Action or Event label is invalid and is dropped. An action must not terminate a state it initiates: never list the same state in both; if a state would appear in both, keep it only in initiates.
- modality distinguishes a PERFORMED act from a PRESCRIBED one. "performed" when the case narrates the agent doing (or omitting) the act; "prescribed" when the act is one the Board says the agent must, must not, or cannot ethically do (a holding stated in the discussion, e.g. "cannot ethically acquiesce"). A prescribed act is never recorded as a performed Action with a present-tense temporal_marker such as "present" or "ongoing"; give it the holding's temporal frame or leave temporal_marker empty.
- text_references are verbatim quotes from the case text grounding this action: each an EXACT contiguous span copied from the case text, never a paraphrase, summary, or stitched fragment.

**APPORTIONMENT RULE:**
- If text emphasizes DECISION/CHOICE/INTENTION/DELIBERATION: extract as Action
- If text emphasizes OCCURRENCE/HAPPENING/TRIGGER/CONSEQUENCE: extract as Event
- If both aspects are present, extract the Action; the Event extractor captures the occurrence separately when the case treats it as its own happening

**TEXT TO ANALYZE:**
{{ case_text }}

{{ action_schema }}

ITEM FIELDS (the live Step-3 field contract; single source with action_extractor.py):
Each extracted item is a JSON object:

  {
    "label": "A SHORT, GENERAL action name of AT MOST 4 words naming the KIND of action, not the case scenario (the label becomes the URI; case-specific detail goes in description)",
    "description": "1-2 sentences with the case-specific detail",
    "agent": "Person and role",
    "temporal_marker": "When it occurred",
    "modality": "performed or prescribed (performed: the case narrates the act; prescribed: the Board says the agent must, must not, or cannot ethically do it)",
    "source_section": "facts or discussion",
    "intention": {
      "mental_state": "deliberate/negligent/etc.",
      "intended_outcome": "What the agent intended",
      "foreseen_unintended_effects": ["Effects foreseen but not intended"]
    },
    "ethical_context": {
      "obligations_fulfilled": ["Obligation names as extracted for this case"],
      "obligations_violated": ["Obligation names as extracted for this case"],
      "guiding_principles": ["Principle labels extracted for this case"]
    },
    "professional_context": {
      "within_competence": true,
      "required_capabilities": ["Capabilities needed to perform this action"]
    },
    "initiates": ["States this action brings into holding"],
    "terminates": ["States this action ends (never a state it initiates)"],
    "temporal_extent": "instant or interval (OWL-Time anchor; temporal_marker stays the textual when)",
    "text_references": ["EXACT contiguous verbatim spans copied from the case text grounding this action"]
  }

Focus on quality over quantity. Extract clear, professionally significant volitional decisions.

FORMATTING (ProEthica style, abbreviated): Do not use em dashes or en dashes in output text. Do not dodge that by substituting stacked parentheticals or excessive colons or semicolons. Write plain sentences: use commas, or split into two sentences.
$proethica_tpl$,
    version = version + 1,
    updated_at = now()
WHERE extraction_type = 'case' AND step_number = 3 AND concept_type = 'actions' AND is_active = true;

-- ===================================================================================
-- events (step 3, pass rows facts and discussion)
-- L8: initiates / terminates name State labels of this case only (the CASE STATE LABELS closed list when supplied), a label equal to an Action or Event label is dropped (an Event label was given where a State label was required in case 8).
INSERT INTO extraction_prompt_template_versions
    (template_id, version_number, template_text, variables_schema, change_description, changed_by, changed_at)
SELECT id, version, template_text, variables_schema,
       'case-8 review lessons (L8): see docs/reviews/lessons/extraction_templates.sql',
       'review/case8-lessons', now()
FROM extraction_prompt_templates
WHERE extraction_type = 'case' AND step_number = 3 AND concept_type = 'events' AND is_active = true;

UPDATE extraction_prompt_templates
SET template_text = $proethica_tpl${{ event_definition }}

EXISTING EVENTS IN ONTOLOGY:
{{ existing_events_text }}

{{ pass_directive }}

CROSS-CONCEPT CONTEXT (states and actions already extracted in this case, for grounding initiates/terminates and caused_by_action; do NOT re-extract them here):
{{ cross_concept_context }}

CASE TEXT:
{{ case_text }}

{{ event_schema }}

EVENT EXTRACTION DIRECTIVES (rules the ontology enforces):
{{ event_boundary }}
{{ event_individuation }}
- event_type is the controlled ORIGIN and the load-bearing typing signal (Berreby/Sarmiento). Set exactly one of outcome (the result of a case agent's action), exogenous (external, not caused by any case agent), automatic (fires automatically when preconditions hold). It becomes the three-way subClassOf typing at commit (outcome to AgentCausedEvent, exogenous to ExogenousEvent, automatic to AutomaticEvent), so it carries weight for responsibility attribution: an exogenous event is no agent's doing, an outcome traces to an action. It is a routing input, not stored as a literal. Do not invent an origin outside this set.
- Origin tie-break: when the proximate producer of a happening is a system executing set rules, type it AutomaticEvent even if an agent action supplied the preconditions, and record that enabling action via the caused_by_action link; AgentCausedEvent is reserved for consequences not mediated by automated rule-following.
- label is a SHORT, GENERAL name of at most 4 words naming the KIND of event, not the case scenario: write "Structural Failure", not "Single-Client Conflict Mitigation Recognized". The label becomes the event's URI; put case-specific detail in the description.
- description is 1-2 sentences carrying the case-specific detail.
- temporal_marker is when the event occurred (the textual when); temporal_extent is "instant" for a point occurrence or "interval" for one that extends over a period.
- initiates and terminates name the STATES (fluents) the event brings into or out of holding (Event Calculus). Name the conditions that become or stop being true (for example "Public Safety Risk State", "Project Halted State"), using the same state names used elsewhere in the case. They name State labels of this case ONLY (the CASE STATE LABELS list when one is supplied is a closed list); a label equal to an Action or Event label is invalid and is dropped. An event initiates a state, not an obligation; the obligation and constraint links are recovered downstream from the state. An event must not terminate a state it initiates: never list the same state in both initiates and terminates; if a state would appear in both, keep it only in initiates.
- caused_by_action references the action label that caused this event, when one applies.
- text_references are verbatim quotes from the case text grounding this event: each an EXACT contiguous span copied from the case text, never a paraphrase, summary, or stitched fragment. confidence is the extraction confidence 0.0-1.0.
- Do NOT emit severity, an automatic-trigger boolean, preconditions, NESS test factors, or a causal chain here. Severity is dropped for events, and the NESS causal analysis is owned by the separate Stage-5 causal pass.

OUTPUT FORMAT:
Return a JSON object with a single array "events", each entry a specific event occurrence in the case. Events are origin-typed individuals; this pass mints no event classes.

EVENT SCHEMA (events array) -- each event is a JSON object:

  {
    "label": "Structural Failure",
    "description": "A critical structural deficiency was discovered during the independent review of the proposed design.",
    "event_type": "outcome",
    "temporal_marker": "Month 5",
    "temporal_extent": "instant",
    "initiates": ["Public Safety Risk State", "Project Halted State"],
    "terminates": [],
    "caused_by_action": "Task Assignment Decision",
    "text_references": ["a critical structural flaw was found in the detailed review"],
    "confidence": 0.92
  }

FORMATTING: do not use em dashes or en dashes in output text, and do not dodge with stacked parentheticals or excessive colons/semicolons; use commas or split into two sentences.
$proethica_tpl$,
    version = version + 1,
    updated_at = now()
WHERE extraction_type = 'case' AND step_number = 3 AND concept_type = 'events' AND is_active = true;


COMMIT;
