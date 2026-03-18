# Experiment Data

Pre-computed features for reproducing the ICCBR 2026 experiments. Contains embeddings, set-based features, and citation edges for 119 NSPE BER cases. No original case text is included.

## Files

| File | Description |
|------|-------------|
| `case_precedent_features.sql.gz` | PostgreSQL dump of the `case_precedent_features` table (119 rows, gzipped). Contains all embeddings (384-dim vectors), provisions cited, outcome types, subject tags, principle tensions, citation edges, and per-component embeddings (R, P, O, S, Rs, A, E, Ca, Cs). |
| `documents_stub.csv` | Minimal case metadata: id, title, document_type, world_id. Used for CSV labeling in experiment output. Does not contain case text. |

## Loading

Requires PostgreSQL 16+ with the [pgvector](https://github.com/pgvector/pgvector) extension.

```bash
# 1. Create database and enable pgvector
createdb ai_ethical_dm
psql -d ai_ethical_dm -c "CREATE EXTENSION IF NOT EXISTS vector"

# 2. Load features table
gunzip -k case_precedent_features.sql.gz
psql -d ai_ethical_dm -f case_precedent_features.sql

# 3. Load documents stub
psql -d ai_ethical_dm -c "
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    source TEXT,
    document_type TEXT NOT NULL,
    world_id INTEGER NOT NULL DEFAULT 1,
    file_path TEXT,
    file_type TEXT,
    content TEXT,
    doc_metadata JSONB,
    processing_status VARCHAR(20),
    processing_phase VARCHAR(50),
    processing_progress INTEGER,
    processing_error TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    created_by INTEGER,
    data_type VARCHAR(20) DEFAULT 'user'
)"

psql -d ai_ethical_dm -c "\COPY documents(id, title, document_type, world_id) FROM 'documents_stub.csv' CSV HEADER"
```

Then run any experiment script from the repository root:

```bash
export DATABASE_URL=postgresql://user:pass@localhost:5432/ai_ethical_dm
export ANTHROPIC_API_KEY=dummy
PYTHONPATH=$(pwd) python scripts/analysis/weight_sweep.py
```

## Contents

The `case_precedent_features` table contains derived features only:

- **Embeddings**: 384-dimensional vectors from all-MiniLM-L6-v2 for facts, discussion, combined, and 9 per-component (R, P, O, S, Rs, A, E, Ca, Cs) representations
- **Set features**: provisions_cited (NSPE Code section arrays), outcome_type, subject_tags, principle_tensions, obligation_conflicts
- **Citation graph**: cited_case_ids (directed edges from BER opinion cross-references)

No original NSPE Board of Ethical Review case text is included. The embeddings are numerical vectors derived from extracted entity labels and definitions. The full extracted case data, component breakdowns, and precedent analysis views can be browsed at [https://proethica.org](https://proethica.org).
