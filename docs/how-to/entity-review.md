# Entity Review

This guide covers the entity review workflow for validating extracted concepts before commitment to the ontology.

## Overview

After each extraction pass, entities enter a review queue where users:

1. Validate accuracy of extracted entities
2. Edit labels and definitions
3. Match to existing ontology classes
4. Approve new classes when needed
5. Commit validated entities

## Entity Review Interface

### Accessing Review

After extraction completes, the Entity Review page displays automatically. You can also access it via:

- Pipeline step completion
- Entity Review link in sidebar
- Direct URL: `/scenario_pipeline/<case_id>/entity_review/<pass>`

### Interface Layout

| Section | Description |
|---------|-------------|
| **Available Classes** | Existing classes from OntServe ontology |
| **Extracted Entities** | New entities from extraction |
| **Entity Details** | Edit form for selected entity |
| **Actions** | Commit, clear, re-run controls |

## Available Classes

The collapsible "Available Classes" section shows existing ontology classes from OntServe:

### Class Categories

| Category | Examples |
|----------|----------|
| **Roles** | Engineer, Client, Employer |
| **States** | Competent, Conflicted, Authorized |
| **Resources** | NSPE Code, State Regulations |
| **Principles** | Public Safety, Competence |
| **Obligations** | Disclose, Verify, Report |
| **Constraints** | Cannot Certify, Must Not |
| **Capabilities** | Can Consult, May Decline |
| **Events** | Request, Discovery, Violation |
| **Actions** | Certify, Disclose, Decline |

### Using Available Classes

When reviewing entities:

1. Expand "Available Classes" section
2. Find matching class if exists
3. Reassign entity to existing class
4. Or approve as new class

## Entity Table

### Table Columns

| Column | Description |
|--------|-------------|
| **Select** | Checkbox for bulk actions |
| **Label** | Short entity identifier |
| **Type** | Concept type (Role, State, etc.) |
| **Definition** | Full description |
| **Status** | New, Existing, Modified |
| **Actions** | Edit, Delete buttons |

### Status Indicators

| Status | Icon | Meaning |
|--------|------|---------|
| **New** | Star | Extracted this session, no ontology match |
| **Existing** | Check | Matches existing ontology class |
| **Modified** | Pencil | User-edited entity |
| **Pending** | Clock | Awaiting review |

## Editing Entities

### Edit Dialog

Click **Edit** on any entity to open edit dialog:

| Field | Description |
|-------|-------------|
| **Label** | Short identifier (edit freely) |
| **Definition** | Full description (edit freely) |
| **Class** | Ontology class assignment |
| **Source** | Original extraction source |

### Best Practices

When editing entities:

- **Labels**: Keep concise (2-5 words)
- **Definitions**: Be specific and complete
- **Class**: Match to existing when appropriate
- **Source**: Preserve for provenance

### Merging Entities

If duplicate entities extracted:

1. Identify duplicates
2. Keep most accurate version
3. Delete duplicates
4. Or use Clear and Re-run

## Class Assignment

### Matching Existing Classes

To assign entity to existing class:

1. Click **Edit** on entity
2. Open Class dropdown
3. Select matching class from list
4. Save changes

### Approving New Classes

When LLM identifies genuinely novel concept:

1. Entity marked "New Class"
2. Review definition carefully
3. Click **Approve New Class**
4. Entity will create new ontology class on commit

### When to Approve New

Approve new class when:

- Concept not in existing ontology
- Definition is clear and specific
- Concept is genuinely distinct
- Will be useful for future cases

### When to Reassign

Reassign to existing class when:

- Similar class exists in ontology
- Difference is merely wording
- Can be subsumed by existing concept

## Bulk Operations

### Select All

Use header checkbox to select all entities.

### Bulk Delete

Select multiple entities and click **Delete Selected**.

### Bulk Approve

Select multiple new classes and click **Approve Selected**.

## Committing Entities

### Commit Process

After review complete:

1. Ensure all entities reviewed
2. Click **Commit Entities**
3. Entities saved to temporary storage
4. Linked to extraction session
5. Ready for Phase 2 analysis

### What Commit Does

| Action | Result |
|--------|--------|
| **Saves** | Entities to `temporary_rdf_storage` |
| **Links** | Entities to `extraction_session_id` |
| **Records** | Prompt and response in `extraction_prompts` |
| **Enables** | Next pipeline step |

### Temporary vs Permanent

Committed entities remain in temporary storage until explicitly pushed to OntServe ontology. This allows:

- Further review and editing
- Rollback if needed
- Batch ontology updates

## Clear and Re-run

### When to Use

Use Clear and Re-run when:

- Extraction quality poor
- Major changes needed
- Starting fresh preferred

### Clear Process

1. Click **Clear and Re-run**
2. Existing entities removed
3. Extraction runs again
4. New entities replace old

### Preserving Work

If partial work should be preserved:

1. Export entities first
2. Or commit before clearing
3. Then clear and re-run

## Extraction Session Linkage

### Session ID

Each extraction creates a unique `extraction_session_id` linking:

- `ExtractionPrompt` records (prompt/response)
- `TemporaryRDFStorage` records (entities)

### Viewing Session

Session information shows:

- Session ID
- Timestamp
- Entity count
- Prompt/response data

### Session Persistence

Sessions persist in database until:

- Explicitly cleared
- Case deleted
- Manual cleanup

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

## Related Guides

- [Phase 1 Extraction](phase1-extraction.md) - Extraction process
- [Ontology Integration](../reference/ontology-integration.md) - OntServe details
- [Pipeline Automation](pipeline-automation.md) - Batch processing
