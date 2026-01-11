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
| **Title** | Case name with robot icon if agent-generated |
| **Case Number** | Badge showing identifier (e.g., "Case #24-02") |
| **Analyzed Badge** | Green "Analyzed" or gray "Not Analyzed" |
| **Subject Tags** | Clickable tags for filtering (yellow badges) |
| **Find Similar** | Link to precedent discovery |
| **Questions** | Ethical questions posed to the board |
| **Conclusions** | Board determinations |

### Filtering

The filter bar provides several options:

| Filter | Description |
|--------|-------------|
| **World Filter** | Dropdown to filter by domain (e.g., Engineering Ethics) |
| **Analyzed Only** | Checkbox to show only cases with Step 4 synthesis complete |
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

Click **View Details** on any case card to access the full case page at `/cases/<id>`.

![Case Detail](../assets/images/screenshots/case-detail-content.png)
*Individual case page showing the analysis pipeline status and case sections*

### Pipeline Status

Below the case title, numbered step buttons show extraction pipeline progress:

| Button | Name | Content |
|--------|------|---------|
| **1** | Contextual | Roles, States, Resources |
| **2** | Normative | Principles, Obligations, Constraints, Capabilities |
| **3** | Temporal | Actions, Events, Causal Relationships |
| **4** | Synthesis | Provisions, questions, decisions, narrative |

Step button states indicate completion:

- **Filled (green)** - Step complete, click to view results
- **Outline** - Step available but not run
- **Lock icon** - Step locked pending prerequisites

### Header Actions

| Button | Function |
|--------|----------|
| **Back to Cases** | Return to case list |
| **Structure** | View document sections and embeddings |
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
