# Precedent Network

The precedent network provides case-based reasoning through semantic similarity matching. Cases with similar ethical situations connect through embedding-based similarity scores.

## Overview

Precedent discovery identifies cases with similar:

- Fact patterns
- Ethical reasoning
- Code provisions
- Professional contexts

## Accessing Precedent Discovery

### From Navigation

Navigate to **Precedents** > **Find Precedents** in the navigation bar.

Direct URL: `/cases/precedents/`

### From Cases List

Each case card includes a **Find Similar** link (blue badge) that opens precedent discovery with that case pre-selected.

### From Case Structure

On any case Structure page, click **Find More Precedents** in the Similar Cases sidebar.

![Precedent Discovery](../assets/images/screenshots/precedent-discovery-content.png)
*Precedent discovery page showing similar cases ranked by combined similarity score*

## Using Precedent Discovery

### Select Source Case

1. Open Precedents page
2. Select a case from the dropdown
3. View similar cases ranked by similarity

### View Matches

The results table displays:

| Column | Description |
|--------|-------------|
| **Case** | Case title with link |
| **Facts Score** | Facts embedding similarity |
| **Discussion Score** | Discussion embedding similarity |
| **Combined** | Average similarity score |

### Explore Matches

Click any match to view case details and compare analysis.

## Similarity Filters

### Minimum Threshold

| Threshold | Typical Results |
|-----------|-----------------|
| **0.9** | Nearly identical cases |
| **0.7** | Similar situations |
| **0.5** | Related topics |
| **0.3** | Broadly relevant |

### Section Focus

- **Both** - Requires similarity in both sections
- **Facts Only** - Match situational similarity
- **Discussion Only** - Match reasoning similarity

## Interpreting Results

### High Similarity (0.8+)

Cases with very similar fact patterns, ethical issues, and professional contexts. Suitable for direct precedent comparison.

### Moderate Similarity (0.5-0.8)

Cases sharing related ethical concepts, similar role structures, or comparable dilemmas. Provides broader context.

### Low Similarity (< 0.5)

Cases with limited connection but potential insights.

## Similarity Network Visualization

The Similarity Network provides a visual overview of all cases and their relationships.

Navigate to **Precedents** > **Similarity Network** or direct URL: `/cases/precedents/network`

![Similarity Network](../assets/images/screenshots/similarity-network-content.png)
*Force-directed graph showing case relationships with color-coded outcomes*

### Node Colors (by Outcome)

| Color | Outcome |
|-------|---------|
| Green | Ethical |
| Red | Unethical |
| Orange | Mixed |
| Gray | Unknown/Unclear |

### Edge Colors (by Similarity Score)

| Color | Score Range | Meaning |
|-------|-------------|---------|
| Green | > 0.5 | High similarity |
| Yellow | 0.3 - 0.5 | Moderate similarity |
| Red | < 0.3 | Low similarity |

### Interacting with the Network

**Click a Node** - Displays case details panel showing title, outcome type, NSPE Code provisions, entity count, and connection count.

**Click an Edge** - Displays similarity breakdown with component scores for facts, discussion, provisions, outcome, tags, and principles.

**Navigation** - Drag nodes to reposition, scroll to zoom, click background to pan.

### Filtering Options

#### Minimum Score Threshold

Use the **Min** dropdown to filter edges:

| Threshold | Result |
|-----------|--------|
| 0.2 | Most relationships |
| 0.3 | Default balanced view |
| 0.4 | Higher similarity only |
| 0.5 | Strong relationships only |

#### Similarity Component Filters

| Filter | Description |
|--------|-------------|
| **All** | Default weighted combination |
| **Provisions** | Cases sharing NSPE Code sections |
| **Discussion** | Semantic similarity in ethical analysis |
| **Facts** | Semantic similarity in case situations |
| **Outcome** | Same ethical/unethical verdict |
| **Tag Similarity** | Shared subject tags |
| **Principle Tensions** | Similar ethical principle conflicts |

#### Entity Overlap Filters

Filter by shared entities using the concept buttons (R, P, O, S, Rs, A, E, Ca, Cs).

### Layout Options

| Layout | Description | Best For |
|--------|-------------|----------|
| **Force** | Physics-based simulation | Discovering clusters |
| **Circular** | All cases in a circle | Seeing all connections |
| **Grid** | Regular grid pattern | Dense networks |
| **Radial** | Grouped by outcome | Comparing outcomes |

### Focus Mode

![Focused Network](../assets/images/screenshots/similarity-network-focused-content.png)
*Network with a specific case focused and highlighted*

Use URL parameter to focus: `/cases/precedents/network?case_id=7`

## Similarity Components

The network uses six similarity factors:

| Component | Method | Description |
|-----------|--------|-------------|
| Facts Similarity | Cosine | Semantic similarity of case facts |
| Discussion Similarity | Cosine | Semantic similarity of ethical analysis |
| Provision Overlap | Jaccard | NSPE Code section overlap |
| Outcome Alignment | Categorical | Ethical/unethical match |
| Tag Overlap | Jaccard | Subject tag overlap |
| Principle Overlap | Jaccard | Ethical principle conflicts |

## Technical Details

### Embedding Model

Default: `all-MiniLM-L6-v2` (sentence-transformers)

- 384 dimensions
- Optimized for semantic similarity

### Similarity Calculation

Cosine distance between embeddings:

- **1.0** = Identical
- **0.8+** = Very similar
- **0.5-0.8** = Moderately similar
- **< 0.5** = Dissimilar

Combined score: `(Facts Score + Discussion Score) / 2`

## Related Pages

- [Browsing Cases](browsing-cases.md) - Navigate the case repository
- [Viewing Extractions](viewing-extractions.md) - View extracted entities
- [Guidelines](guidelines.md) - Browse professional codes
