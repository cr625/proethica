# Entity Review

The entity review workflow validates extracted concepts before commitment to the ontology.

!!! note "Login Required"
    Editing and committing entities requires authentication.

## Overview

After each extraction pass, entities enter a review queue:

1. Validate accuracy of extracted entities
2. Edit labels and definitions
3. Match to existing ontology classes
4. Approve new classes when needed
5. Commit validated entities

## Accessing Review

After extraction completes, the entity review page displays automatically. Access it via:

- Pipeline step completion redirect
- Entity review link in the pipeline sidebar
- Direct URL: `/scenario_pipeline/case/<case_id>/entities/review` (Pass 2: append `/pass2`)

![Entity Review Interface](../assets/images/screenshots/entity-review-content.png)

## Interface Layout

Entities display as cards organized by concept type (e.g., Roles, States, Resources). Each concept type section shows a count of classes and individuals.

| Section | Description |
|---------|-------------|
| **Concept Type Sections** | Cards grouped by type with color-coded headers |
| **Available Classes** | Existing ontology classes (collapsed by default) |
| **Section Toggle** | Switch between Facts and Discussion results (Steps 1-2) |
| **Actions** | Re-run Extraction, Provenance, Commit controls |

## Entity Cards

Each entity displays as a card with a 5px color-coded left border matching its concept type.

**Card contents:**

| Element | Description |
|---------|-------------|
| **Label** | Entity name (e.g., "Engineer") |
| **Type** | `rdfs:subClassOf` classification |
| **Definition** | Full description from extraction |
| **Properties** | RDF properties grid (domain, range, etc.) |
| **Source Text** | Original case text quotes |
| **Match Badge** | Ontology match status |
| **Delete Button** | Remove unpublished entities |

### Match Status Badges

| Badge | Color | Meaning |
|-------|-------|---------|
| **Linked** | Green | High-confidence match to ontology class (>= 0.90) |
| **Review** | Clickable | Lower-confidence match requiring manual review |
| **New** | Gray | No matching ontology class found |

Clicking a **Review** badge opens the match details modal showing the proposed ontology class and confidence score.

## Entity Management

### Deleting Entities

Unpublished entities show a delete button (X icon). Published entities display a green check badge and cannot be deleted from the review interface.

### Duplicate Entities

The Reconcile step (between Steps 3 and 4) handles deduplication automatically. For manual cleanup, delete duplicates individually from the review cards.

## Class Assignment

Entities are automatically matched to existing ontology classes during extraction. The match confidence determines the badge displayed:

- **Linked** (>= 0.90) - Automatically assigned to the matching ontology class
- **Review** (< 0.90) - Requires manual confirmation via the match details modal
- **New** - No match found; entity creates a new ontology class on commit

## Committing Entities

### OntServe Commit

The OntServe commit publishes entities from `temporary_rdf_storage` to the ontology. The pipeline performs two commits:

1. **First commit** (after Reconcile) - Steps 1-3 base entities (9 component types)
2. **Second commit** (after Step 4) - Step 4 synthesis entities (8 additional types)

Each commit generates a TTL file and registers entities in the OntServe database.

### What Commit Does

| Action | Result |
|--------|--------|
| **Generates** | TTL (Turtle) file with RDF triples |
| **Registers** | Entities in OntServe database |
| **Marks** | Entities as published in `temporary_rdf_storage` |
| **Links** | Case to ontology graph |

### Uncommit

Previously committed entities can be removed via the uncommit operation, which deletes the TTL file and OntServe database registrations.

## Re-run Extraction

Each step page includes a **Re-run Extraction** button that clears existing entities for that step and runs extraction again.

## OntServe Integration

### Available Classes Source

Available classes fetched from OntServe MCP via:

- `get_entities_by_category()` method
- Real-time ontology query
- Cached for performance

### Connection Status

Header shows OntServe status:

| Status | Meaning |
|--------|---------|
| **Green** | Connected, classes available |
| **Yellow** | Degraded, limited function |
| **Red** | Disconnected, no classes |

### Fallback Mode

If OntServe unavailable:

- Available classes section empty
- Extraction still works
- Commit stores locally
- Push to ontology deferred

## Troubleshooting

### Empty Available Classes

If Available Classes empty:

1. Check OntServe MCP running
2. Verify connection status
3. Restart OntServe if needed

### Commit Failed

If commit fails:

1. Check database connection
2. Verify entity data valid
3. Check for constraint violations
4. Review error message

### Lost Entities

If entities disappear:

1. Check if Clear was clicked
2. Review extraction session
3. Check database directly
4. Re-run extraction if needed

## Related Pages

- [Running Extractions](running-extractions.md) - Extraction process
- [Pipeline Automation](pipeline-automation.md) - Batch processing
- [Ontology Integration](../admin-guide/ontology-integration.md) - OntServe details
