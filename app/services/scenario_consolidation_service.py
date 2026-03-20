"""
Scenario Consolidation Service

Reduces a full set of scenario branches (e.g., 18) to a curated subset
(e.g., 5-7) suitable for interactive traversal by study participants.

Algorithm (hybrid actor-grouping + scoring):
1. Group branches by decision maker (normalized base name)
2. Score each branch on dilemma richness
3. Pick top representatives per actor group
4. Trim to target count, preserving original narrative order

The full branch set remains untouched for computational analysis.
The curated subset is stored as `interactive_selection` within scenario_seeds.
"""

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_TARGET_COUNT = 7


def consolidate_branches(branches: List[Dict], target_count: int = DEFAULT_TARGET_COUNT) -> Dict:
    """
    Select a representative subset of branches for interactive traversal.

    Args:
        branches: Full list of scenario branches from Phase 4
        target_count: Desired number of branches for the traversal

    Returns:
        interactive_selection dict with branch_indices, method, target_count
    """
    if len(branches) <= target_count:
        return {
            'branch_indices': list(range(len(branches))),
            'method': 'all_included',
            'target_count': target_count,
            'overridden': False,
        }

    # Step 1: Score every branch
    scored = []
    for i, branch in enumerate(branches):
        scored.append({
            'index': i,
            'branch': branch,
            'actor': _extract_base_name(branch.get('decision_maker_label', '')),
            'score': _score_branch(branch),
        })

    # Step 2: Group by actor
    groups: Dict[str, List[dict]] = {}
    for item in scored:
        groups.setdefault(item['actor'], []).append(item)

    # Sort within each group by score descending
    for actor in groups:
        groups[actor].sort(key=lambda x: x['score'], reverse=True)

    # Step 3: Pick representatives
    selected_indices = _select_representatives(groups, target_count)

    # Step 4: Preserve original narrative order
    selected_indices.sort()

    logger.info(
        f"Consolidated {len(branches)} branches to {len(selected_indices)} "
        f"(target {target_count}, {len(groups)} actor groups)"
    )

    return {
        'branch_indices': selected_indices,
        'method': 'auto_consolidate_v1',
        'target_count': target_count,
        'overridden': False,
    }


def _score_branch(branch: Dict) -> float:
    """
    Score a branch on dilemma richness. Higher = more suitable for
    interactive presentation.

    Criteria:
    - Competing obligations (more = richer tension)
    - Board choice is non-obvious (not the first option)
    - Option count and label diversity
    - Has consequence data (populated by Stage 4.3b)
    """
    score = 0.0

    # Competing obligations: 2 points each
    obligations = branch.get('competing_obligation_labels', [])
    score += len(obligations) * 2.0

    # Board choice position: +3 if not the first option (non-obvious)
    options = branch.get('options', [])
    for i, opt in enumerate(options):
        if opt.get('is_board_choice') and i > 0:
            score += 3.0
            break

    # Option count: slight bonus for having exactly 2 clear options
    if len(options) == 2:
        score += 1.0
    elif len(options) > 2:
        score += 1.5

    # Option label diversity: penalize if labels are very similar
    if len(options) >= 2:
        labels = [opt.get('label', '') for opt in options]
        if labels[0] and labels[1]:
            overlap = _word_overlap(labels[0], labels[1])
            if overlap < 0.5:
                score += 2.0  # distinct options
            elif overlap > 0.8:
                score -= 1.0  # near-duplicate options

    # Consequence data populated: +2 (richer analysis reveal)
    for opt in options:
        if opt.get('consequence_narrative'):
            score += 2.0
            break

    # Board rationale populated: +1
    if branch.get('board_rationale'):
        score += 1.0

    # Question length: slight bonus for substantive questions
    question = branch.get('question', '')
    if 30 < len(question) < 200:
        score += 1.0

    return score


def _select_representatives(groups: Dict[str, List[dict]], target_count: int) -> List[int]:
    """
    Select branch indices from actor groups to reach target_count.

    Strategy:
    - Round 1: one branch per group (highest scored)
    - Round 2+: fill remaining slots from next-best across all groups
    """
    selected = []
    remaining_per_group: Dict[str, List[dict]] = {}

    # Round 1: top pick from each group
    for actor, items in groups.items():
        selected.append(items[0]['index'])
        if len(items) > 1:
            remaining_per_group[actor] = items[1:]

    if len(selected) >= target_count:
        # Too many groups; rank by score and trim
        scored_selected = [(idx, next(
            item['score'] for g in groups.values() for item in g if item['index'] == idx
        )) for idx in selected]
        scored_selected.sort(key=lambda x: x[1], reverse=True)
        return [idx for idx, _ in scored_selected[:target_count]]

    # Round 2+: fill remaining slots from remaining candidates
    all_remaining = []
    for actor, items in remaining_per_group.items():
        all_remaining.extend(items)
    all_remaining.sort(key=lambda x: x['score'], reverse=True)

    slots_left = target_count - len(selected)
    for item in all_remaining[:slots_left]:
        selected.append(item['index'])

    return selected


def _extract_base_name(label: str) -> str:
    """Extract base actor name from a decision maker label."""
    match = re.match(r'^((?:Engineer|Client|Dr\.|Mr\.|Ms\.|Professor)\s+\w+)', label)
    if match:
        return match.group(1)
    return label


def _word_overlap(a: str, b: str) -> float:
    """Jaccard similarity of word sets between two strings."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)
