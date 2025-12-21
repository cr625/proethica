# Interface Overview

This guide covers the main interface elements and navigation patterns in ProEthica.

## Navigation Bar

The top navigation provides access to main features:

| Menu Item | Description |
|-----------|-------------|
| **Cases** | Case repository, upload, and individual case views |
| **Precedents** | Similarity-based precedent discovery and network visualization |
| **Tools** | Academic references, documentation, and utilities |
| **Admin** | System administration (if authorized) |

## Cases Section

### Case Repository

The Cases page (`/cases/`) displays all uploaded cases with:

- Year grouping for chronological organization
- Subject tags for filtering by topic
- Pipeline status indicators (pending, in progress, complete)
- Quick actions for each case

![Case Repository](../assets/images/screenshots/cases-list-content.png)

### Case Detail

Each case has a detail page showing:

- Case title, reference number, and metadata
- Full narrative with Facts and Discussion sections
- **Structure** button - View document sections and embeddings
- **Analyze** button - Launch the extraction pipeline

![Case Detail](../assets/images/screenshots/case-detail-content.png)

### Document Structure

The Structure view (`/cases/<id>/structure`) provides:

- Section breakdown with character counts
- Embedding status and regeneration controls
- Similar cases based on semantic matching

![Case Structure](../assets/images/screenshots/case-structure-content.png)

## Extraction Pipeline

The pipeline (`/scenario_pipeline/<case_id>`) provides step-by-step case analysis:

| Step | Phase | Description |
|------|-------|-------------|
| Step 1 | Phase 1 | Pass 1 extraction (Facts: Roles, States, Resources) |
| Step 1b | Phase 1 | Pass 1 extraction (Discussion section) |
| Step 2 | Phase 1 | Pass 2 extraction (Principles, Obligations) |
| Step 2b | Phase 1 | Pass 2 extraction (Discussion section) |
| Step 3 | Phase 1 | Pass 3 extraction (Actions, Events, Constraints, Capabilities) |
| Step 4 | Phase 2 | Case synthesis and transformation analysis |
| Step 5 | Phase 3 | Interactive scenario exploration |

### Pipeline Overview

The overview page shows step completion status:

- **Lock icon** - Prerequisites not met
- **Check mark** - Step completed
- **Arrow** - Current step available

![Pipeline Overview](../assets/images/screenshots/pipeline-overview-complete-content.png)

### Entity Review

After each extraction, the review page displays:

- Extracted entities organized by concept type
- Section toggle (Facts vs Discussion)
- Edit and delete controls for each entity
- Commit button to finalize to OntServe

![Entity Review](../assets/images/screenshots/entity-review-pass1-content.png)

## Precedent Discovery

### Similarity Search

The Precedents page (`/cases/precedents/`) provides:

- Similarity scores based on document embeddings
- Breakdown by section (Facts, Discussion)
- Filter by specific case or view all pairs

![Precedent Discovery](../assets/images/screenshots/precedent-discovery-content.png)

### Similarity Network

The network view (`/cases/precedents/network`) visualizes case relationships:

- Node color indicates case outcome (green: ethical, red: unethical, orange: mixed)
- Edge color indicates similarity strength
- Click nodes for case details
- Click edges for similarity breakdown

![Similarity Network](../assets/images/screenshots/similarity-network-content.png)

## Pipeline Automation

For batch processing, the Pipeline Dashboard (`/pipeline/dashboard`) shows:

- Service status (Redis, Celery, queue depth)
- Active pipeline runs with progress bars
- Queue management controls

![Pipeline Dashboard](../assets/images/screenshots/pipeline-dashboard-content.png)

## Status Indicators

### Service Status

The header shows service connectivity:

- **Green** - All services operational
- **Yellow** - Some services unavailable
- **Red** - Critical services offline

### Entity Status

Entities in review display their state:

- **New** - Extracted this session
- **Existing** - Matches ontology class
- **Modified** - User-edited entity

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Enter` | Submit current form |
| `Esc` | Close modal dialogs |

## Next Steps

- [Upload Cases](../how-to/upload-cases.md) - Add cases for analysis
- [Phase 1 Extraction](../how-to/phase1-extraction.md) - Start extracting concepts
- [Precedent Discovery](../how-to/precedent-discovery.md) - Find similar cases
