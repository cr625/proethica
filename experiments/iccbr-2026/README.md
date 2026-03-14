# ICCBR 2026 Experiment Data

Experiment results for "Component-Aware Case Retrieval for Professional Ethics" (ICCBR 2026). All data produced from a pool of 119 NSPE Board of Ethical Review cases with 228 citation edges across 93 source cases.

## Multi-Factor Similarity Architecture

All three embedding methods share the same scoring formula:

```
score = 0.40 * embedding + 0.25 * provision_overlap + 0.15 * outcome_alignment
        + 0.10 * tag_overlap + 0.10 * principle_overlap
```

Only the 0.40 embedding component differs across methods. The 0.60 set-based component is identical, so retrieval differences are attributable solely to the embedding strategy.

The three embedding strategies form a progression of structural awareness:

1. **Section-based** (baseline): Facts (0.375) + Discussion (0.625) cosine similarity, normalized within the 0.40 allocation
2. **Combined D-tuple**: Single cosine between combined embedding vectors (weighted average of 9 component embeddings, L2-normalized)
3. **Per-component D-tuple**: Nine independent component cosines combined by weighted sum using domain-informed weights

## Experiments

### 1. Three-Way Retrieval Comparison

Citation ground truth validation across 93 source cases with 228 citation edges (118 candidates per query).

| Metric | Section | Combined | Per-comp. | Random |
|--------|:-------:|:--------:|:---------:|:------:|
| MRR | 0.380 | **0.407** | 0.403 | 0.086 |
| Recall@5 | 0.286 | 0.324 | **0.331** | 0.042 |
| Recall@10 | 0.420 | **0.463** | 0.442 | 0.085 |
| Recall@20 | 0.536 | **0.577** | 0.554 | 0.169 |

**Files:** `retrieval_aggregate.csv`, `retrieval_results.md`, `retrieval_per_edge.csv`

### 2. Citation Text Ablation

Tests whether citation references in Discussion text inflate section-based retrieval. Strips sentences containing case references (326 of 3,932 sentences across 80 cases) and re-embeds. Uses embedding-only scoring to isolate the contamination effect.

Result: citation text does not inflate scores. Removing it marginally improves Recall (R@10: 0.397 vs 0.387 original), indicating citation language acts as noise.

**Files:** `ablation_citation_text.csv`

### 3. Embedding-Only Ablation

Isolates the embedding contribution by scoring with embeddings only (set features zeroed) and set features only (embeddings zeroed).

| Metric | Emb-Section | Emb-Combined | Emb-PerComp | Set-Only |
|--------|:-----------:|:------------:|:-----------:|:--------:|
| MRR | 0.393 | 0.429 | 0.437 | 0.316 |
| Recall@5 | 0.263 | 0.429 | 0.413 | 0.264 |
| Recall@10 | 0.387 | 0.523 | 0.568 | 0.387 |
| Recall@20 | 0.539 | 0.712 | 0.730 | 0.505 |

Per-component embedding alone (0.568 R@10) exceeds the full-formula best (0.463 Combined). The 0.60 set-feature weight dilutes the D-tuple embedding signal.

**Files:** `embedding_ablation_results.md`, `embedding_ablation_per_edge.csv`

### 4. Rank Correlation

Pairwise Spearman rho and Overlap@10 across all 119 cases.

| Metric | Sec. vs Comb. | Sec. vs Comp. | Comb. vs Comp. |
|--------|:-------------:|:-------------:|:--------------:|
| Mean Spearman rho | 0.929 | 0.935 | 0.991 |
| Mean Overlap@10 | 76.9% | 78.3% | 91.5% |

The two D-tuple methods produce near-identical rankings (rho = 0.991). The D-tuple extraction framework is the primary contributor to retrieval quality, not the aggregation strategy.

**Files:** `rank_correlation_summary.md`, `rank_correlation_per_case.csv`

### 5. Divergent Case Analysis

Per-component similarity breakdown for the three cases with lowest section-vs-per-component rho (Cases 19, 105, 141). Top-10 neighbors selected by the paper-weight full formula.

Actions consistently shows the highest variance across top-10 neighbors (std 0.073--0.105). Capabilities is consistently lowest (std 0.025--0.060). Principles shows case-dependent behavior: low variance in competence-focused cases (Case 105, std 0.046) and high variance in cases involving multiple competing ethical obligations (Cases 19 and 141, std 0.081--0.086).

**Files:** `divergent_components.csv`

### 6. Weight Sensitivity Analysis

Varies the embedding/set-feature ratio (alpha) from 0.0 to 1.0 in steps of 0.05 for all three methods.

| Method | Optimal Alpha | R@10 at Optimum | R@10 at 0.40 |
|--------|:------------:|:---------------:|:------------:|
| Section | 0.90 | 0.468 | 0.420 |
| Combined | 0.80 | 0.598 | 0.463 |
| Per-component | 0.90 | 0.615 | 0.442 |

Set features interact differently with each embedding strategy. Section-based embedding gains from set features at alpha=0.40 (+0.033 R@10 over embedding-only), while Combined loses (-0.060) and Per-component loses most (-0.126). Per-component overtakes Combined above alpha=0.45. The paper's fixed alpha=0.40 understates the D-tuple advantage.

**Files:** `weight_sweep_results.md`, `weight_sweep_data.csv`

## Reproduction

All experiments run against the `case_precedent_features` table in the ProEthica database. The analysis scripts are in `scripts/analysis/`.

| Experiment | Script | Arguments |
|:----------:|--------|-----------|
| 1 | `evaluate_ground_truth_v3.py` | `--paper-weights` |
| 2 | `ablation_citation_text.py` | |
| 3 | `embedding_ablation.py` | |
| 4 | `rank_correlation_three_way.py` | |
| 5 | `recompute_divergent_components.py` | |
| 6 | `weight_sweep.py` | |

```bash
cd proethica
source venv-proethica/bin/activate
PYTHONPATH=/home/chris/onto/proethica python scripts/analysis/<script>.py
```

All scripts load case features into memory and compute pairwise scores without modifying the database. Runtime is under two minutes per script.

## Component Weights

Weights for the per-component embedding method (Table 2 in the paper):

| Component | Code | Weight |
|-----------|:----:|:------:|
| Principles | P | 0.20 |
| Obligations | O | 0.15 |
| Roles | R | 0.12 |
| States | S | 0.10 |
| Resources | Rs | 0.10 |
| Actions | A | 0.10 |
| Constraints | Cs | 0.08 |
| Events | E | 0.08 |
| Capabilities | Ca | 0.07 |
