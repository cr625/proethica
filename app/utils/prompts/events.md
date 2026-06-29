=== WHAT AN EVENT IS (ontology grounding) ===
An event is an occurrence, not a volitional decision: a process (BFO bfo:0000015) that happens in the case and that an agent may or may not have caused. Its load-bearing signal is its ORIGIN. An event is distinct from an action (an act an agent deliberately performs) and from a state (the condition the event brings into or out of holding). An event does not create an obligation or activate a constraint directly; it initiates a STATE (a fluent) that then makes obligations or constraints apply.

EXISTING EVENTS IN ONTOLOGY:
{{ existing_events_text }}

{{ pass_directive }}

CROSS-CONCEPT CONTEXT (states and actions already extracted in this case, for grounding initiates/terminates and caused_by_action; do NOT re-extract them here):
{{ cross_concept_context }}

CASE TEXT:
{{ case_text }}

{{ event_schema }}

EVENT EXTRACTION DIRECTIVES (rules the ontology enforces):
- NEGATIVE BOUNDARY: an event is NOT an action. It is a non-deliberate occurrence or outcome, never an agent's deliberate act. If a named agent deliberately did the thing (e.g. a client "instructed to revise the design"), it is an action and belongs to the action pass, not an event.
- event_type is the controlled ORIGIN and the load-bearing typing signal (Berreby/Sarmiento). Set exactly one of outcome (the result of a case agent's action), exogenous (external, not caused by any case agent), automatic (fires automatically when preconditions hold). It becomes the three-way subClassOf typing at commit (outcome to AgentCausedEvent, exogenous to ExogenousEvent, automatic to AutomaticEvent), so it carries weight for responsibility attribution: an exogenous event is no agent's doing, an outcome traces to an action. It is a routing input, not stored as a literal. Do not invent an origin outside this set.
- label is a SHORT, GENERAL name of at most 4 words naming the KIND of event, not the case scenario: write "Structural Failure", not "Single-Client Conflict Mitigation Recognized". The label becomes the event's URI; put case-specific detail in the description.
- description is 1-2 sentences carrying the case-specific detail.
- temporal_marker is when the event occurred (the textual when); temporal_extent is "instant" for a point occurrence or "interval" for one that extends over a period.
- initiates and terminates name the STATES (fluents) the event brings into or out of holding (Event Calculus). Name the conditions that become or stop being true (for example "Public Safety Risk State", "Project Halted State"), using the same state names used elsewhere in the case. An event initiates a state, not an obligation; the obligation and constraint links are recovered downstream from the state.
- caused_by_action references the action label that caused this event, when one applies.
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
