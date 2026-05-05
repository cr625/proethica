# Embedding-Only Ablation Results

**Date:** 2026-03-18 07:43
**Script:** `experiments/iccbr-2026/analysis/embedding_ablation.py`
**Spec:** `EMBEDDING_ABLATION_SPEC.md`

## Design

Four conditions isolating embedding and set-feature contributions, plus the full multi-factor reference from Table 3. All conditions use the same 93 source cases, 228 citation edges, 118 candidates per query.

| Condition | Formula |
|-----------|---------|
| Emb-Section | 0.375 x facts_cosine + 0.625 x discussion_cosine |
| Emb-Combined | cosine(combined_embedding_i, combined_embedding_j) |
| Emb-PerComp | weighted avg of 9 component cosines (Table 2 weights, renormalized to 1.0) |
| Set-Only | 0.417 x provisions + 0.250 x outcome + 0.167 x tags + 0.167 x principles |
| Full (ref) | 0.40 x embedding + 0.60 x set-based (from Table 3) |

## Results

| Metric | Emb-Section | Emb-Combined | Emb-PerComp | Set-Only | Full (S/C/P) | Random |
|--------|:-----------:|:------------:|:-----------:|:--------:|:------------:|:------:|
| MRR | 0.393 | 0.429 | 0.437 | 0.316 | 0.380/0.407/0.403 | 0.086 |
| Recall@5 | 0.263 | 0.429 | 0.413 | 0.264 | 0.286/0.324/0.331 | 0.042 |
| Recall@10 | 0.387 | 0.523 | 0.568 | 0.387 | 0.420/0.463/0.442 | 0.085 |
| Recall@20 | 0.539 | 0.712 | 0.730 | 0.505 | 0.536/0.577/0.554 | 0.169 |

## Analysis

### 1. Embedding Isolation

D-tuple advantage with embeddings only (no set-feature floor):

| Comparison | Delta MRR | Delta Recall@10 |
|------------|:---------:|:---------------:|
| Combined vs Section | +0.036 | +0.136 |
| Per-comp vs Section | +0.044 | +0.181 |

Full-formula Combined-vs-Section Recall@10 delta: +0.043
Embedding-only Combined-vs-Section Recall@10 delta: +0.136

The D-tuple advantage is **larger** in isolation than in the full formula, confirming that the 60% shared set-feature floor compresses the observable effect.

### 2. Set-Feature Contribution

| Signal | Recall@10 |
|--------|:---------:|
| Set-Only | 0.387 |
| Emb-PerComp (best embedding-only) | 0.568 |
| Full-formula best | 0.463 |

Embedding-only (0.568) **exceeds** the full formula (0.463). The 0.60 set-feature weight does not improve retrieval over D-tuple embeddings alone. Set-Only (0.387) is the weakest signal.

### 3. Complementarity

Marginal embedding contribution (Full best - Set-Only): +0.076 Recall@10
Marginal set-feature contribution (Full best - Emb-best): -0.105 Recall@10

Set features have **negative** marginal contribution: adding set features to the best embedding reduces Recall@10 by 0.105. The current 0.40/0.60 weighting dilutes the embedding signal. The D-tuple extraction framework produces embeddings strong enough to outperform the combined formula.

### 4. Per-Edge Comparison (Embedding-Only)

**Emb-Combined vs Emb-Section:** Combined wins 143, Section wins 68, tied 17

**Emb-PerComp vs Emb-Section:** Component wins 136, Section wins 83, tied 9

**Emb-Combined vs Emb-PerComp:** Combined wins 91, Component wins 93, tied 44
