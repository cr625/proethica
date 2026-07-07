You are an expert in professional ethics extracting ACTIONS (volitional professional decisions) from an engineering ethics case.

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
- initiates / terminates name the STATES (fluents) the action brings into or out of holding (Event Calculus; Kowalski & Sergot 1986, Berreby et al. 2017), using the same state names used elsewhere in the case. An action must not terminate a state it initiates: never list the same state in both; if a state would appear in both, keep it only in initiates.
- text_references are verbatim quotes from the case text grounding this action: each an EXACT contiguous span copied from the case text, never a paraphrase, summary, or stitched fragment.

**APPORTIONMENT RULE:**
- If text emphasizes DECISION/CHOICE/INTENTION/DELIBERATION: extract as Action
- If text emphasizes OCCURRENCE/HAPPENING/TRIGGER/CONSEQUENCE: extract as Event
- If both aspects are present, extract the Action; the Event extractor captures the occurrence separately when the case treats it as its own happening

**TEXT TO ANALYZE:**
{{ case_text }}

ITEM FIELDS (the live Step-3 field contract; single source with action_extractor.py):
Each extracted item is a JSON object:

  {
    "label": "A SHORT, GENERAL action name of AT MOST 4 words naming the KIND of action, not the case scenario (the label becomes the URI; case-specific detail goes in description)",
    "description": "1-2 sentences with the case-specific detail",
    "agent": "Person and role",
    "temporal_marker": "When it occurred",
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
