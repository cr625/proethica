# Ontology-Guided Extraction

An extraction prompt in ProEthica combines the text of a case with content read from the ontology. Before each extraction call, the prompt builder takes from `proethica-core.ttl` the definition of the component class and its boundary against the other eight component classes. The definition also names the relationships that a case individual of the class carries, and the field list of the prompt requests values for several of them, such as the States an Action initiates and terminates. The model returns one structured record per extracted item. The pipeline converts each record into a case individual linked to the other records of the case, and later processing, from precedent retrieval to Step 4 synthesis, reads those individuals.

## Ontology Content in the Prompt

The Action prompt of the example below carries four blocks read from the `proeth-core:Action` class. The prompts of the other eight component types carry the definitions of their own classes in the same way, with typing rules drawn from the same ontology.

| Prompt block | Ontology source | Content |
|--------------|-----------------|---------|
| Definition | `iao:0000115` of the class | What an Action is, as a BFO process, and how it differs from an Event |
| Extraction framing | `iao:0000116` of the class | How to tell an Action from an Event in a text, and the relationships recorded on each case individual |
| Negative boundary | The nine-way `owl:AllDisjointClasses` axiom | The component types an Action must not be confused with, each redirected to its own pass |
| Individuation | `skos:scopeNote` of the class | What defines the Action type, and which details attach to the case individual instead |

## Worked Example: An Action in Case 24-1

The example is taken from the stored Action extraction of NSPE Case 24-1, *Balancing Client Directives and Public Welfare* (stored as case 8), run on 7 July 2026. The prompt and the response belong to provenance activity 5835, with the model `claude-fable-5`. The Provenance page of a case shows the stored prompt and response of the latest run of each extraction stage.

### Source Passage

The opinion describes the notification in the Facts and returns to it in the Discussion.

Facts:

> Engineer L conducts additional studies and qualitatively estimates the risk that heavy rainfall could lead to stormwater runoff from the development reaching the nearby watershed and community drinking water source. Engineer L notifies Client X of this risk, advising that additional protective measures should be considered, especially as local environmental standards require steps to safeguard public water sources.

Discussion:

> Consistent with Code sections I.4, II.3.a, II.3.b, III.1.b, and III.3.a, Engineer L notified Client X of this risk.

### Prompt Instructions

The first excerpt is ontology content: the definition, part of the extraction framing and the negative boundary. The second is part of the field list of the Action extractor, which asks for the State transitions, the temporal extent and the supporting passages that the framing names. `[...]` marks omitted text.

<div class="wrap-excerpt" markdown>

```text
=== ACTION (ontology definition) ===
A process (BFO) that is a volitional, intentional intervention an agent performs through deliberate choice in a professional context, the temporal-dynamics counterpart of the Event. Whereas an Event is a non-volitional occurrence that happens to or around the agents in a case, an Action issues from an agent's deliberate choice and is therefore the occurrent to which professional responsibility, and the fulfilment or breach of obligations, attaches. As a happening in the Event-Calculus sense, an Action initiates and terminates the State fluents that carry the situation forward and stands as a cause in the case's causal chain, so responsibility for a downstream outcome can be attributed to it. [...]
Extraction framing:
[...] Step 3 emits actions as individuals typed directly to core:Action with no per-case subclass discovery. Each is anchored by time:hasTime (a time:Instant or time:ProperInterval) and reified Allen interval relations, records its State transitions through the initiates and terminates fluent edges, and carries its normative edges (fulfillsObligation, violatesObligation, guidedByPrinciple, raisesObligation) on the case individual. [...]

TYPING (rules the ontology enforces):
- NEGATIVE BOUNDARY: the nine D-tuple components are mutually disjoint (owl:AllDisjointClasses). Do NOT emit as an Action what is really a skill or competence (Capability); a hard boundary or prohibition (Constraint); an external occurrence (Event); a duty or 'shall' statement (Obligation); a value or ideal such as public safety (Principle); a document or standard such as the NSPE Code (Resource); a professional position or identity (Role); a condition such as a conflict of interest (State). Redirect each to the pass that owns it.
```

</div>

<div class="fit-excerpt" markdown>

```text
9. initiates: list of STATES (fluents) this action brings into holding. In the Event
   Calculus (Kowalski & Sergot 1986; Berreby et al. 2017) a happening initiates a fluent
   that then holds until terminated. Name the conditions/states that become true because
   of this action (for example "Conflict of Interest", "Public Safety Risk Disclosed"),
   using the same state names used elsewhere in the case. Empty list if it changes no state.
10. terminates: list of STATES (fluents) this action ends (conditions that stop holding).
    Empty list if none. An action must not terminate a state it initiates: never list the
    same state in both initiates and terminates; if a state would appear in both, keep it
    only in initiates.
11. temporal_extent: "instant" if the action is a point occurrence, "interval" if it
    extends over a period. This anchors the action in OWL-Time; temporal_marker stays the
    textual when.
12. text_references: verbatim quotes from the CASE FACTS / CASE DISCUSSION text grounding
    this action. Each must be an EXACT contiguous span copied from the case text (not the
    narrative summary); never paraphrase, summarize, or stitch fragments together.
```

</div>

The full prompt also contains the case text, the individuation rule, the extraction directives shared across components, fields 1 to 8 and the response format.

### Recorded Response

The response lists eight Actions. The excerpt shows selected fields of the sixth, Risk Notification, in the formatting of the response. Omitted from this Action: `description`, `intention`, `ethical_context` and `professional_context`. Omitted from the response: the other seven Actions (Contract Acceptance, Work Suspension Request, Nondisclosure at Suspension, Work Resumption, Risk Study Conduct, Safeguard Refusal and Refusal to Acquiesce).

<div class="wrap-excerpt" markdown>

```json
{"actions": [
  {
    "label": "Risk Notification",
    "agent": "Engineer L (Licensed Professional Engineer)",
    "temporal_marker": "After completing the additional studies",
    "source_section": "facts",
    "initiates": ["Risk Disclosed to Client"],
    "terminates": ["Undisclosed Unquantified Risk Concern"],
    "temporal_extent": "instant",
    "text_references": [
      "Engineer L notifies Client X of this risk, advising that additional protective measures should be considered, especially as local environmental standards require steps to safeguard public water sources.",
      "Consistent with Code sections I.4, II.3.a, II.3.b, III.1.b, and III.3.a, Engineer L notified Client X of this risk."
    ]
  }
]}
```

</div>

??? note "Complete Risk Notification object from the response"

    <div class="wrap-excerpt" markdown>

    ```json
    {
      "label": "Risk Notification",
      "description": "Engineer L notifies Client X of the identified runoff risk and advises that additional protective measures should be considered, noting that local environmental standards require steps to safeguard public water sources.",
      "agent": "Engineer L (Licensed Professional Engineer)",
      "temporal_marker": "After completing the additional studies",
      "source_section": "facts",
      "intention": {
        "mental_state": "deliberate",
        "intended_outcome": "Inform the client of the established risk and prompt investment in protective measures",
        "foreseen_unintended_effects": ["Client resistance due to budget limitations"],
        "agent_knowledge": "Knew the runoff risk was now established and that local environmental standards require safeguarding public water sources"
      },
      "ethical_context": {
        "obligations_fulfilled": ["Public Safety Paramountcy Obligation", "Faithful Agent Obligation", "Project Success Advisement Obligation", "Opinions Founded on Facts Obligation"],
        "obligations_violated": [],
        "guiding_principles": ["Public Safety Health and Welfare Principle", "Faithful Agent Principle"]
      },
      "professional_context": {
        "within_competence": true,
        "required_capabilities": ["Risk communication", "Knowledge of local environmental standards"]
      },
      "initiates": ["Risk Disclosed to Client"],
      "terminates": ["Undisclosed Unquantified Risk Concern"],
      "temporal_extent": "instant",
      "text_references": [
        "Engineer L notifies Client X of this risk, advising that additional protective measures should be considered, especially as local environmental standards require steps to safeguard public water sources.",
        "Consistent with Code sections I.4, II.3.a, II.3.b, III.1.b, and III.3.a, Engineer L notified Client X of this risk."
      ]
    }
    ```

    </div>

The record places the notification in the timeline of the case: it ends the State of an undisclosed risk concern and begins the State of a risk disclosed to the client. Its two quotations are the passages shown under Source Passage.

### Case Records Built from the Response

The pipeline converts each returned Action into a case individual and links its fields to other records of the case.

| Response field | Case record |
|----------------|-------------|
| `label` | A case individual typed directly to `proeth-core:Action`; the label forms its IRI |
| `agent` | A `proeth-core:isPerformedBy` link to the agent individual of the case |
| `initiates`, `terminates` | State names kept with the record; at commit an edge step matches them to the State individuals of the case and writes `proeth-core:initiates` and `proeth-core:terminates` edges |
| `temporal_extent`, `temporal_marker` | A `time:Instant` or `time:ProperInterval` individual linked by `time:hasTime` and labelled with the temporal marker; the pipeline adds interval relations to the other happenings of the case and a sequence position |
| `ethical_context` | Obligation and Principle names resolved to the individuals of the case as `proeth-core:fulfillsObligation`, `proeth-core:violatesObligation` and `proeth-core:guidedByPrinciple` edges |
| `text_references` | `proeth:textReferences` quotations on the individual |

The Actions of a case form the Action component of the nine-component similarity used in [precedent retrieval](../viewing/precedent-network.md). The Timeline of [Viewing Extractions](../viewing/viewing-extractions.md) and the Entity Timeline of the [Interactive Scenario](../viewing/interactive-scenario.md) present the Actions and Events of a case in sequence. Step 4 synthesis takes the Action records as input when it relates each action to the obligations of the case and when it builds decision points.

## Related Documentation

- [Nine-Component Framework](nine-components.md) - Definitions of the nine component types
- [Ontology Properties](ontology-properties.md) - The object properties that link case individuals
- [System Architecture](../admin-guide/architecture.md#llm-request-flow) - Model tiers, prompt storage and the commit-time checks
- [Prompt Editor](../admin-guide/prompt-editor.md) - The stored prompt templates
