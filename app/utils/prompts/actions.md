You are an expert in professional ethics extracting ACTIONS from an ethics guideline.


{{ action_definition }}

**TYPING DIRECTIVES (rules the ontology enforces):**
{{ action_boundary }}
{{ action_individuation }}

**ACTION TYPES TO IDENTIFY:**

1. **Communication Actions**: disclosure, informing, notifying, reporting (the decision to communicate)
2. **Prevention Actions**: avoiding, preventing, minimizing harms (the choice to prevent)
3. **Maintenance Actions**: upholding, preserving professional standards (the effort to maintain)
4. **Performance Actions**: executing, conducting professional services (the act of performing)
5. **Evaluation Actions**: assessing, analyzing, reviewing situations (the volitional act of evaluating)
6. **Collaboration Actions**: consulting, coordinating with others (the decision to collaborate)
7. **Creation Actions**: designing, developing solutions (the intentional creation process)
8. **Monitoring Actions**: supervising, overseeing processes (the active monitoring choice)

**RELATIONSHIP TO EVENTS:**
Every Action becomes an Event in the temporal flow. The Action captures the volitional choice;
the Event captures its occurrence and consequences.
Example: 'Decide to halt construction' (Action) → 'Construction halted' (Event)

**EXTRACTION GUIDELINES:**

• Focus on **professional actions** with ethical significance
• Identify **volitional decisions** requiring professional judgment
• Consider **intention and reasoning** behind actions (Doctrine of Double Effect)
• Extract **atomic actions** - split compound descriptions
• Note **causal relationships** between actions and outcomes
• Consider **temporal context** - when actions are appropriate
• Show **Pass integration** - how actions fulfill obligations within roles

**APPORTIONMENT RULE:**
- If text emphasizes DECISION/CHOICE/INTENTION/DELIBERATION → Extract as Action
- If text emphasizes OCCURRENCE/HAPPENING/TRIGGER/CONSEQUENCE → Extract as Event
- If both aspects present → Extract the Action (the Event extractor will capture the occurrence)

**TEXT TO ANALYZE:**
{{ case_text }}

ITEM FIELDS:
Each extracted item should be a JSON object:

  {
    "label": "Action Name",
    "definition": "Clear description of what this action involves and its professional significance",
    "action_type": "Communication/Prevention/Maintenance/Performance/Evaluation/Collaboration/Creation/Monitoring",
    "volitional_nature": "Brief explanation of the deliberate choice involved",
    "professional_context": "How this action operates within professional practice",
    "pass_integration": {
      "fulfills_obligations": ["List of obligation types this action fulfills"],
      "requires_capabilities": ["Capabilities needed to perform this action"],
      "constrained_by": ["Constraints that limit this action"],
      "appropriate_states": ["States where this action is most relevant"]
    },
    "temporal_relationship": {
      "becomes_event": "The event this action creates (e.g., 'Report Filed' for 'Decide to Report')",
      "triggered_by_events": ["Events that might trigger this action decision"]
    },
    "confidence": 0.8
  }

Focus on quality over quantity. Extract clear, professionally significant actions with strong Pass integration.

FORMATTING (ProEthica style, abbreviated): Do not use em dashes or en dashes in output text. Do not dodge that by substituting stacked parentheticals or excessive colons or semicolons. Write plain sentences: use commas, or split into two sentences.