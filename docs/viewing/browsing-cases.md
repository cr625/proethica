# Browsing Cases

ProEthica organizes ethics cases in a searchable repository with filtering by year, subject, and domain.

## Cases List

Navigate to **Cases** in the navigation bar, or access directly at `/cases/`.

![Cases List](../assets/images/screenshots/cases-list-content.png)
*Case repository showing cases grouped by year with clickable subject tags*

### List Layout

Cases are organized by year with expandable cards displaying:

| Element | Description |
|---------|-------------|
| **Title** | Clickable case name linking to the detail page |
| **Case Number** | Badge showing identifier (e.g., "Case #24-02") |
| **Subject Tags** | Clickable tags for filtering (yellow badges) |
| **Find Similar** | Link to precedent discovery |
| **Questions** | Ethical questions posed to the board (expanded view) |
| **Conclusions** | Board determinations (expanded view) |

A view toggle in the page header switches between **compact** (titles and tags only) and **expanded** (questions and conclusions visible) modes. The selected mode persists across browser sessions.

### Filtering

The filter bar provides filtering options:

| Filter | Description |
|--------|-------------|
| **World Filter** | Dropdown to filter by domain (e.g., Engineering Ethics) |
| **Tag Filter** | Clickable tags to filter by subject category |

#### Tag Filtering

Subject tags are clickable throughout the interface:

- **Filter bar tags** - Click any tag in the "Filter by tag:" row
- **Case card tags** - Click a tag on any case card
- **Expand for more** - Click "+X more" to reveal all available tags
- **Clear filter** - Click the active (highlighted) tag again to remove the filter

When a tag filter is active, a "Filtering by:" indicator appears at the top. The active tag is highlighted in yellow with an "x" indicator.

#### Find Similar

Each case card includes a **Find Similar** link that navigates to the precedent network with that case pre-selected. See [Precedent Network](precedent-network.md) for details.

### Subject Tags

Subject tags provide topical classification. For NSPE cases, these come from the NSPE Board of Ethical Review's subject categorization system.

| Tag Category | Examples |
|--------------|----------|
| Professional Conduct | Conflict of Interest, Competence, Integrity |
| Public Safety | Health and Safety, Public Welfare |
| Practice Areas | Design, Construction, Consulting |
| Relationships | Client Relations, Employer Relations |

## Case Detail Page

Click the case title on any case card to access the full case page at `/cases/<id>`.

![Case Detail](../assets/images/screenshots/case-detail-content.png)

### Context Bar

Below the case title, a context bar displays key metadata and navigation:

| Element | Description |
|---------|-------------|
| **OntServe Link** | Links to the case ontology on OntServe (when entities are committed) |
| **Entity Count** | Badge showing total extracted entities |
| **Transformation** | Case transformation type (Transfer, Stalemate, Oscillation, Phase Lag) |
| **Structure** | View document sections and embeddings |
| **Provenance** | View extraction history and session data |

### Pipeline Status (Authenticated Users)

Authenticated users see a pipeline status bar with numbered step buttons below the context bar:

| Button | Name | Content |
|--------|------|---------|
| **1** | Contextual | Roles, States, Resources |
| **2** | Normative | Principles, Obligations, Constraints, Capabilities |
| **3** | Temporal | Actions, Events, Causal Relationships |
| **4** | Synthesis | Provisions, Precedents, Questions, Conclusions, Decision Points, Resolution Patterns |

Step button states indicate completion:

- **Filled (green)** -- Step complete, click to view results
- **Outline** -- Step available but not run
- **Lock icon** -- Step locked pending prerequisites

The pipeline status bar and associated step buttons are hidden for unauthenticated users in production.

### Header Actions

| Button | Function |
|--------|----------|
| **Back to Cases** | Return to case list |
| **Pipeline** | Open the case pipeline dashboard (authenticated users only) |
| **Source** | Link to original source (if available) |

### Case Sections

Engineering ethics cases (NSPE format) contain these sections:

| Section | Content |
|---------|---------|
| **Facts** | Background circumstances and situation description |
| **Question(s)** | Specific ethical questions posed to the board |
| **NSPE Code References** | Relevant code of ethics provisions |
| **Discussion** | Board's ethical analysis and reasoning |
| **Conclusion(s)** | Board's formal determinations |
| **Dissenting Opinion** | Minority view (if present) |

Section structure varies by professional domain. ProEthica currently uses NSPE engineering ethics as the canonical format.

### Case Metadata

The card header displays:

- **Case Number** - Official case identifier
- **Year** - Year of board decision
- **World** - Domain classification (e.g., "Engineering Ethics")

## Structure Page

The Structure page displays document analysis and embedding information. Access via the **Structure** button on any case detail page.

![Case Structure](../assets/images/screenshots/case-structure-content.png)
*Structure page showing document sections and embedding status*

### Summary Cards

| Metric | Description |
|--------|-------------|
| **Sections** | Total number of document sections |
| **With Embeddings** | Sections that have vector embeddings |
| **Coverage** | Percentage of sections with embeddings |
| **Dimensions** | Embedding vector size (384D for local model) |

### Document Sections

The accordion shows each section with content length, embedding status, and preview text.

### Similar Cases Sidebar

When embeddings exist, the sidebar shows cases with similar discussion sections based on embedding cosine similarity.

## Related Pages

- [Viewing Extractions](viewing-extractions.md) - View extracted entities from completed cases
- [Precedent Network](precedent-network.md) - Explore case similarity relationships
- [Guidelines](guidelines.md) - Browse professional codes of ethics
