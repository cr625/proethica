# Phase 3: Interactive Scenario

Phase 3 generates interactive scenarios with participant mapping, decision points, and provenance tracking.

## Overview

Phase 3 (Step 5) executes six stages to create an interactive visualization:

| Stage | Name | Output |
|-------|------|--------|
| 1 | Timeline Construction | Decision points with timestamps |
| 2 | Participant Mapping | Character profiles |
| 3 | Relationship Networks | Professional and ethical relationships |
| 4 | Decision Points | Transformation opportunities |
| 5 | Causal Chain Visualization | Cause-effect diagrams |
| 6 | Normative Framework Display | Code provision links |

## Starting Scenario Generation

### Prerequisites

Before Step 5:

- Complete Phase 1 extraction (Steps 1-3)
- Complete Phase 2 analysis (Step 4)
- All entities committed

### Access Step 5

1. Navigate to Scenario Pipeline (`/scenario_pipeline/<case_id>`)
2. Click **Step 5** in the sidebar
3. Review scenario generation interface

## Stage 1: Timeline Construction

Builds chronological sequence of events and decisions:

### Timeline Elements

| Element | Description |
|---------|-------------|
| **Decision Point** | Moment requiring ethical choice |
| **Timestamp** | Relative or absolute time marker |
| **Description** | LLM-generated summary |
| **Participants** | Roles involved |

### Example Timeline

For Case 24-2:
1. Client requests AI-assisted design
2. Engineer assesses AI tool capabilities
3. Engineer decides to proceed without verification expertise
4. Engineer completes AI-generated design
5. Engineer certifies work
6. Board reviews conduct

### Timeline Visualization

The interactive timeline displays:

- Horizontal timeline with markers
- Clickable decision points
- Participant involvement indicators
- Causal connections between events

## Stage 2: Participant Mapping

Creates detailed character profiles with LLM enhancement:

### Participant Fields

| Field | Description |
|-------|-------------|
| **Name** | Role identifier (e.g., "Engineer A") |
| **Role** | Professional position |
| **Profile** | 2-3 sentence analytical narrative |
| **Background** | Ethically-relevant professional details |
| **Motivations** | Factors driving decisions |
| **Analytical Notes** | Key principles, conflicts, tensions |

### LLM Enhancement

The system uses LLM to generate:

- Enriched character backgrounds
- Additional motivations illuminating tensions
- Analytical notes identifying ethical significance

### Example Participant

**Engineer A**:
- Role: Consulting Engineer
- Profile: Licensed PE with 15 years experience, recently adopted AI tools for design efficiency
- Motivations: Client satisfaction, competitive pressure, technology adoption
- Tensions: Competence boundaries vs. efficiency gains

## Stage 3: Relationship Networks

Maps relationships between participants:

### Relationship Types

| Type | Description |
|------|-------------|
| **Professional** | Work relationships (employer, client, colleague) |
| **Ethical** | Obligation relationships (duty to, responsible for) |
| **Tension** | Conflict relationships |

### Network Visualization

Interactive graph showing:

- Nodes for each participant
- Edges with relationship labels
- Color coding by relationship type
- Click to view relationship details

## Stage 4: Decision Points

Identifies transformation opportunities:

### Decision Point Structure

| Field | Description |
|---------|-------------|
| **Timestamp** | When decision occurred |
| **Actor** | Who made decision |
| **Choice Made** | Actual decision |
| **Alternatives** | Other options available |
| **Consequences** | Resulting outcomes |
| **Transformation Impact** | How it affected ethical state |

### Example Decision Point

**Decision Point 3: Proceed Without Verification**
- Actor: Engineer A
- Choice: Used AI without verification capability
- Alternatives: Hire specialist, decline project, request training
- Consequences: Violated competence requirement
- Impact: Triggered transfer transformation

## Stage 5: Causal Chain Visualization

Displays cause-effect relationships:

### Chain Structure

```
Condition → Action → Outcome
    ↓
Obligation Status
```

### Example Chain

```
Lacks AI verification competence
    ↓
Uses AI without verification
    ↓
Certifies AI-generated design
    ↓
Violates NSPE Code II.1.a
```

### Visualization

Interactive diagram showing:

- Conditions as input nodes
- Actions as process nodes
- Outcomes as output nodes
- Obligation status as annotations

## Stage 6: Normative Framework Display

Links to code of ethics provisions:

### Framework Elements

| Element | Description |
|---------|-------------|
| **Principles** | Abstract standards (18 linked) |
| **Obligations** | Concrete duties (18 linked) |
| **Code Provisions** | Referenced standards |
| **Precedent Cases** | Similar prior decisions (23 matches) |

### Navigation

Click any framework element to:

- View full definition
- See related entities
- Access precedent comparisons

## Running Scenario Generation

### Generate Scenario

Click **Generate Scenario** to execute all six stages:

1. Progress indicator shows stage completion
2. Each stage streams results via SSE
3. Interactive visualization builds incrementally

### Generation Time

Typical generation: 30-60 seconds depending on:

- Case complexity
- Number of participants
- LLM response time

## Interactive Features

### Timeline Navigation

- Scroll horizontally through timeline
- Click decision points for details
- Zoom in/out for detail level

### Participant Cards

- Hover for quick profile
- Click for full details
- Drag to rearrange layout

### Relationship Explorer

- Filter by relationship type
- Highlight specific participants
- Trace connection paths

### Provenance View

For any element:

- Click provenance icon
- View extraction source
- See LLM trace
- Access original text

## Scenario Output

### Export Options

| Format | Contents |
|--------|----------|
| **Web View** | Interactive HTML |
| **JSON** | Structured data |
| **RDF** | Semantic triples |

### Sharing

Share scenario via:

- Direct URL link
- Export to file
- Embed in reports

## Database Storage

Scenario data stored in:

| Table | Contents |
|-------|----------|
| `scenario_participants` | Character profiles |
| `scenario_relationship_map` | Relationship data |
| `scenario_timeline` | Decision points |
| `scenario_decisions` | Choice details |

## Troubleshooting

### Generation Timeout

If generation stalls:

1. Check LLM API status
2. Verify Phase 2 completion
3. Retry generation

### Missing Participants

If participants incomplete:

1. Check Pass 1 Role extraction
2. Verify entity commits
3. Re-run Stage 2

### Relationship Display Issues

If network doesn't render:

1. Refresh page
2. Check browser console
3. Verify data completeness

## Related Guides

- [Phase 2 Analysis](phase2-analysis.md) - Prerequisite analysis
- [Precedent Discovery](precedent-discovery.md) - Finding similar cases
- [Entity Review](entity-review.md) - Validating entities
