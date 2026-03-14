# Three-Way Embedding Comparison Results

**Date:** 2026-03-13 10:57
**Script:** `scripts/analysis/evaluate_ground_truth_v3.py`

## Experimental Design

All three methods share the same multi-factor scoring formula (0.40 embedding + 0.60 set-based features). Only the 0.40 embedding component differs:

1. **Section-based**: Facts (0.15) + Discussion (0.25) cosine similarity
2. **Combined D-tuple**: Single cosine between combined_embedding vectors (0.40)
3. **Per-component D-tuple**: 9 independent component cosines, weighted average (0.40)

## Data

| Metric | Value |
|--------|------:|
| Cases with all embedding types | 119 |
| Source cases with resolvable citations | 93 |
| Total citation edges | 228 |
| Candidates per query | 118 |
| Average citations per source | 2.5 |

## Aggregate Results

| Metric | Section | Combined | Per-comp. | Random |
|--------|:-------:|:--------:|:---------:|:------:|
| MRR | 0.380 | 0.407 | 0.403 | 0.086 |
| Recall@5 | 0.286 | 0.324 | 0.331 | 0.042 |
| Recall@10 | 0.420 | 0.463 | 0.442 | 0.085 |
| Recall@20 | 0.536 | 0.577 | 0.554 | 0.169 |

## Improvement Decomposition

| Step | Recall@10 | Delta |
|------|:---------:|:-----:|
| Section baseline | 0.420 | -- |
| + D-tuple extraction (combined) | 0.463 | +0.043 |
| + Component independence (per-comp.) | 0.442 | -0.021 |
| Total improvement | | +0.022 |

D-tuple extraction accounts for 10.2% improvement in Recall@10 over section-based embedding.

## Per-Edge Rank Comparison

**Per-comp. vs Section:** component wins 111, section wins 89, tied 28

**Combined vs Section:** combined wins 119, section wins 76, tied 33

**Combined vs Per-comp.:** combined wins 109, component wins 50, tied 69
