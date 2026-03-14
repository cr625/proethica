# Weight Sweep Results

**Date:** 2026-03-14 09:11
**Script:** `scripts/analysis/weight_sweep.py`

Retrieval metrics as a function of embedding weight (alpha). At each alpha: score = alpha * embedding + (1 - alpha) * set_features.

## Recall@10 by Alpha

| Alpha | Section | Combined | Per-comp |
|------:|:-------:|:--------:|:--------:|
| 0.00 | 0.387 | 0.387 | 0.387 |
| 0.05 | 0.397 | 0.400 | 0.398 |
| 0.10 | 0.404 | 0.399 | 0.403 |
| 0.15 | 0.400 | 0.408 | 0.403 |
| 0.20 | 0.389 | 0.427 | 0.419 |
| 0.25 | 0.396 | 0.436 | 0.421 |
| 0.30 | 0.417 | 0.448 | 0.421 |
| 0.35 | 0.433 | 0.460 | 0.430 |
| 0.40 | 0.420 | 0.463 | 0.442 |
| 0.45 | 0.413 | 0.448 | 0.458 |
| 0.50 | 0.412 | 0.454 | 0.465 |
| 0.55 | 0.412 | 0.494 | 0.473 |
| 0.60 | 0.416 | 0.516 | 0.506 |
| 0.65 | 0.418 | 0.556 | 0.528 |
| 0.70 | 0.444 | 0.566 | 0.564 |
| 0.75 | 0.463 | 0.592 | 0.583 |
| 0.80 | 0.453 | 0.598 | 0.585 |
| 0.85 | 0.454 | 0.592 | 0.606 |
| 0.90 | 0.468 | 0.573 | 0.615 |
| 0.95 | 0.426 | 0.555 | 0.578 |
| 1.00 | 0.387 | 0.523 | 0.568 |

## Optimal Alpha per Method (Recall@10)

| Method | Optimal Alpha | R@10 at Optimum | R@10 at 0.40 |
|--------|:------------:|:---------------:|:------------:|
| Section | 0.90 | 0.468 | 0.420 |
| Combined | 0.80 | 0.598 | 0.463 |
| Per-comp | 0.90 | 0.615 | 0.442 |

## Crossover Analysis

Combined leads in the mid-range (alpha 0.05--0.80), with brief Per-component leads at alpha 0.10 and 0.45--0.50. Per-component leads durably above alpha = 0.85 (Per-comp 0.606 vs Combined 0.592) and achieves the overall highest R@10 (0.615 at alpha = 0.90).

## Set-Feature Interaction

| Method | Emb-only R@10 | R@10 at alpha=0.40 | Delta |
|--------|:------------:|:------------------:|:-----:|
| Section | 0.387 | 0.420 | +0.033 |
| Combined | 0.523 | 0.463 | -0.060 |
| Per-comp | 0.568 | 0.442 | -0.126 |

## Validation

At alpha=0.00 (set-only), all methods should be identical: Section=0.387, Combined=0.387, Per-comp=0.387.
At alpha=0.40 (paper config), Table 3 check: Section=0.420 (expect 0.420), Combined=0.463 (expect 0.463), Per-comp=0.442 (expect 0.442).
At alpha=1.00 (emb-only), ablation check: Section=0.387 (expect 0.387), Combined=0.523 (expect 0.523), Per-comp=0.568 (expect 0.568).
