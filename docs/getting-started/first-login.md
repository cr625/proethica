# First Login

This guide introduces the ProEthica interface and helps you navigate the system.

## Interface Overview

ProEthica provides a web interface for ethical case analysis with several key areas:

### Navigation Bar

The top navigation provides access to main features:

| Menu Item | Description |
|-----------|-------------|
| **Cases** | Manage and analyze ethics cases |
| **Precedents** | Discover similar precedent cases |
| **Tools** | Academic references and utilities |
| **Admin** | System administration (if authorized) |

### Cases Page

The Cases page (`/cases/`) is the primary entry point for analysis:

- View all uploaded cases
- Filter by status (analyzed, pending)
- Access individual case details
- Generate document embeddings
- Launch extraction pipeline

### Case Detail View

Each case has a detail page (`/cases/<id>`) showing:

- Case title and metadata
- Full case narrative (Facts and Discussion sections)
- **Structure** button - View sections and embeddings
- **Analyze** button - Start extraction pipeline
- Extraction status if previously processed

### Scenario Pipeline

The extraction pipeline (`/scenario_pipeline/<case_id>`) provides step-by-step analysis:

| Step | Phase | Description |
|------|-------|-------------|
| Step 1 | Phase 1 | Pass 1 extraction (Facts: Roles, States, Resources) |
| Step 1b | Phase 1 | Pass 1 extraction (Discussion section) |
| Step 2 | Phase 1 | Pass 2 extraction (Principles, Obligations) |
| Step 2b | Phase 1 | Pass 2 extraction (Discussion section) |
| Step 3 | Phase 1 | Pass 3 extraction (Temporal dynamics) |
| Step 4 | Phase 2 | Case synthesis and analysis |
| Step 5 | Phase 3 | Interactive scenario visualization |

### Entity Review

After each extraction pass, the Entity Review page displays:

- Extracted entities with class labels
- Available classes from OntServe ontology
- Edit/delete controls for each entity
- Commit button to finalize extraction

### Pipeline Dashboard

For batch processing (`/pipeline/dashboard`):

- Service status (Redis, Celery, queue depth)
- Active pipeline runs with progress
- Queue management for bulk operations
- Cancel/reprocess controls

### Precedent Discovery

The Precedents page (`/cases/precedents/`) shows:

- Similarity scores between cases
- Embedding-based matching on Facts and Discussion
- Filter by case selection
- Navigate to similar cases

## Workflow Overview

A typical analysis workflow:

1. **Upload Case** - Add case text via Cases page
2. **Generate Embeddings** - Create section embeddings for similarity
3. **Start Pipeline** - Begin extraction from case detail
4. **Review Entities** - Validate extracted concepts
5. **Commit Entities** - Finalize to OntServe
6. **Run Analysis** - Execute Phase 2 analysis
7. **View Scenario** - Explore interactive visualization
8. **Find Precedents** - Compare with similar cases

## Status Indicators

### Service Status

The header shows service connectivity:

- **Green**: All services operational
- **Yellow**: Some services unavailable
- **Red**: Critical services offline

### Extraction Status

Pipeline steps show completion status:

- **Lock icon**: Prerequisites not met
- **Check mark**: Step completed
- **Arrow**: Current step available

### Entity Status

Entities in review show:

- **New**: Extracted this session
- **Existing**: Matches ontology class
- **Modified**: User-edited entity

## Quick Actions

### Generate Embeddings

From case detail, click **Structure** then **Generate Embeddings** to create vector representations for similarity matching.

### Clear and Re-run

Each extraction step includes a **Clear and Re-run** option to restart extraction with fresh results.

### Cancel Pipeline

From Pipeline Dashboard, use **Cancel** button to stop running extractions.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Enter` | Submit current form |
| `Esc` | Close modal dialogs |

## Next Steps

- [Upload Cases](../how-to/upload-cases.md) - Add cases for analysis
- [Nine-Concept Framework](../concepts/nine-concepts.md) - Understand the methodology
- [Phase 1 Extraction](../how-to/phase1-extraction.md) - Start extracting concepts
