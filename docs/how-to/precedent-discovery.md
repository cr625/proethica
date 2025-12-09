# Precedent Discovery

This guide covers finding similar precedent cases using semantic similarity matching.

## Overview

Precedent discovery identifies cases with similar ethical situations through embedding-based similarity matching. This enables:

- Finding relevant prior board decisions
- Comparing outcomes across similar cases
- Building case-based reasoning for new scenarios

## Accessing Precedent Discovery

Navigate to: **Precedents** in the navigation bar

Or direct URL: `/cases/precedents/`

## How It Works

### Embedding Generation

Each case generates two 384-dimensional embeddings:

| Embedding | Source | Purpose |
|-----------|--------|---------|
| **Facts Embedding** | Facts section text | Match situational similarity |
| **Discussion Embedding** | Discussion section text | Match reasoning similarity |

### Similarity Calculation

Similarity uses cosine distance between embeddings:

- **1.0** = Identical
- **0.8+** = Very similar
- **0.5-0.8** = Moderately similar
- **< 0.5** = Dissimilar

### Ranking

Cases ranked by combined similarity:

```
Combined Score = (Facts Score + Discussion Score) / 2
```

## Using Precedent Discovery

### Step 1: Select Source Case

1. Open Precedents page
2. Select a case from dropdown
3. Or use "Find More Precedents" from case Structure page

### Step 2: View Matches

The system displays similar cases:

| Column | Description |
|--------|-------------|
| **Case** | Case title with link |
| **Facts Score** | Facts embedding similarity |
| **Discussion Score** | Discussion embedding similarity |
| **Combined** | Average similarity score |

### Step 3: Explore Matches

Click any match to:

- View case details
- Compare side-by-side
- Access case analysis

## Similarity Filters

### Minimum Threshold

Filter results by minimum similarity:

| Threshold | Typical Results |
|-----------|-----------------|
| **0.9** | Nearly identical cases |
| **0.7** | Similar situations |
| **0.5** | Related topics |
| **0.3** | Broadly relevant |

### Section Focus

Filter by which section to match:

- **Both** - Requires similarity in both sections
- **Facts Only** - Match situational similarity
- **Discussion Only** - Match reasoning similarity

## Structure Page Integration

### Find More Precedents

From case detail page:

1. Click **Structure** button
2. View document sections
3. Click **Find More Precedents**
4. Redirects to Precedents page with case pre-selected

### Similar Cases Preview

The Structure page shows top 3 matches:

- Quick preview without full search
- Discussion similarity prioritized
- Click to expand search

## Generating Embeddings

### Manual Generation

If embeddings missing:

1. Go to case Structure page
2. Click **Generate Embeddings**
3. Wait for generation (10-30 seconds)
4. Embeddings now available for matching

### Automatic Generation

Embeddings auto-generate when:

- Case uploaded (if configured)
- Pipeline automation runs
- Explicit generation requested

### Sync to Precedent Features

After generating in Structure page:

- Embeddings sync to `case_precedent_features` table
- Required for Precedent Discovery matching
- Happens automatically

## Embedding Details

### Model

Default embedding model: `all-MiniLM-L6-v2` (sentence-transformers)

- 384 dimensions
- Optimized for semantic similarity
- Fast generation

### Storage

Embeddings stored in:

| Table | Column | Type |
|-------|--------|------|
| `document_sections` | `embedding` | vector(384) |
| `case_precedent_features` | `facts_embedding` | vector(384) |
| `case_precedent_features` | `discussion_embedding` | vector(384) |

### Vector Operations

Similarity via pgvector:

```sql
SELECT 1 - (facts_embedding <=> target_embedding) as similarity
FROM case_precedent_features
ORDER BY similarity DESC;
```

## Interpreting Results

### High Similarity (0.8+)

Cases with very similar:

- Fact patterns
- Ethical issues
- Professional contexts

Use for direct precedent comparison.

### Moderate Similarity (0.5-0.8)

Cases sharing:

- Related ethical concepts
- Similar role structures
- Comparable dilemmas

Use for broader context.

### Low Similarity (< 0.5)

Cases with limited connection:

- Different domains
- Unrelated issues
- Minimal overlap

May still offer insights.

## Example: Case 24-2 Precedents

For NSPE Case 24-2 (AI in Engineering):

| Match | Facts | Discussion | Combined |
|-------|-------|------------|----------|
| Case 17-4 (Technology Use) | 0.82 | 0.79 | 0.81 |
| Case 19-1 (Competence) | 0.75 | 0.84 | 0.80 |
| Case 21-3 (Certification) | 0.71 | 0.76 | 0.74 |

## Bulk Precedent Analysis

### Pipeline Dashboard

For batch precedent analysis:

1. Go to Pipeline Dashboard
2. Select cases with embeddings
3. Run precedent matching
4. Export results

### API Access

Programmatic access via:

```python
from app.services.embedding_service import EmbeddingService

service = EmbeddingService()
matches = service.find_similar_cases(case_id, top_k=10)
```

## Troubleshooting

### Zero Similarity Scores

If all scores show 0%:

1. Check embeddings generated in Structure page
2. Verify sync to `case_precedent_features`
3. Re-generate embeddings if needed

### Missing Cases in Results

If expected cases missing:

1. Verify target case has embeddings
2. Check minimum threshold setting
3. Ensure case is in database

### Slow Results

If search slow:

1. Check database indexes
2. Verify pgvector extension
3. Consider result limit

## Database Verification

Check embedding status:

```sql
SELECT
    case_id,
    facts_embedding IS NOT NULL as has_facts,
    discussion_embedding IS NOT NULL as has_disc
FROM case_precedent_features;
```

Sync embeddings if needed:

```sql
UPDATE case_precedent_features cpf
SET facts_embedding = (
    SELECT embedding
    FROM document_sections ds
    WHERE ds.document_id = cpf.case_id
    AND ds.section_type = 'facts'
)
WHERE facts_embedding IS NULL;
```

## Related Guides

- [Upload Cases](upload-cases.md) - Adding cases
- [Phase 1 Extraction](phase1-extraction.md) - Extraction process
- [Settings](settings.md) - Configuration options
