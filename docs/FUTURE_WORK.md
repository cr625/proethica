## Weight Calibration for Precedent Retrieval

The current multi-factor similarity architecture uses fixed heuristic weights
(see `similarity_service.py`). The ICCBR 2026 paper validates retrieval with
these fixed weights against citation ground truth. Three directions for weight
calibration are planned:

1. **Citation-network calibration:** Use the 93 source cases with 228 citation
   edges as supervised signal to learn weights that maximize Recall@10 or MRR.
   Risk: overfitting to 228 edges.

2. **Expert similarity judgments:** Paired comparison study where domain experts
   rate case similarity. Use ratings to calibrate component weights. This also
   addresses the limitation noted in S5.2 of the ICCBR paper.

3. **LLM-based dynamic adjustment:** Per-query weight profiles where the LLM
   analyzes case characteristics and adjusts weights before retrieval. Skeleton
   methods exist in `similarity_service.py` (`_build_weight_prompt`,
   `_parse_weight_response`). Risk: introduces non-determinism and a black box
   into the retrieval path.

A head-to-head comparison of all three against the fixed baseline would
constitute a full research contribution.
