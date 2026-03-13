# CBR Similarity Synthesis Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify the two similarity approaches (section-based on `/cases/precedents/` and D-tuple on `/cases/<id>/structure`) into a single CBR-sound retrieval model on the precedents page.

**Architecture:** Switch the precedents page from section-based weights (`DEFAULT_WEIGHTS`) to component-aware weights (`COMPONENT_AWARE_WEIGHTS`), which use the 9-component D-tuple embeddings as the primary retrieval signal. Remove outcome from the retrieval score (display it post-retrieval only). Remove dead principle_tensions metric. The similarity service already supports component mode via `use_component_embedding=True` -- the main work is wiring it through the precedents route, updating the template, and repopulating the cache.

**Tech Stack:** Flask/Jinja2, PostgreSQL (pgvector), Python, existing `PrecedentSimilarityService`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `app/services/precedent/similarity_service.py` | Modify | Remove `outcome_alignment` and `principle_overlap` from `COMPONENT_AWARE_WEIGHTS`; redistribute weights |
| `app/routes/precedents.py` | Modify | Pass `use_component_embedding=True` through discovery service; update `MATCHING_METHODS` dict; pass source outcome from `case_precedent_features` |
| `app/services/precedent/precedent_discovery_service.py` | Modify | Accept and forward `use_component_embedding` parameter |
| `app/templates/precedents.html` | Modify | Update component display for D-tuple scores; show outcome post-retrieval only; remove principle tensions row; add per-component breakdown |
| `scripts/populate_similarity_cache.py` | Modify | Support component-aware mode; add `component_similarity` column or reuse existing columns |
| DB migration (inline SQL) | Execute | Add `component_similarity` column to `precedent_similarity_cache` if needed |

---

## Chunk 1: Service Layer Changes

### Task 1: Update Component-Aware Weights

**Files:**
- Modify: `app/services/precedent/similarity_service.py:68-76`

- [ ] **Step 1: Update `COMPONENT_AWARE_WEIGHTS` to remove outcome and principle_overlap**

Remove `outcome_alignment` and `principle_overlap` from `COMPONENT_AWARE_WEIGHTS`. Redistribute their weight to the remaining factors. New weights:

```python
COMPONENT_AWARE_WEIGHTS = {
    'component_similarity': 0.50,  # D-tuple 9-component weighted embedding
    'provision_overlap': 0.30,     # NSPE Code section overlap (Jaccard)
    'tag_overlap': 0.20,           # Subject tag overlap (Jaccard)
}
```

Rationale: `component_similarity` is the paper's contribution and should dominate. Provisions are the strongest structural signal in legal CBR. Tags provide domain indexing. Outcome is displayed post-retrieval, not used for ranking.

- [ ] **Step 2: Verify existing component-aware calculation path works**

The `calculate_similarity()` method at line 89 already handles `use_component_embedding=True` correctly -- it computes per-component cosine similarities weighted by `COMPONENT_WEIGHTS` from `case_feature_extractor.py`. No changes needed to the calculation logic, only the weight dict.

Run a quick sanity check:
```bash
cd /home/chris/onto/proethica && source venv-proethica/bin/activate
python -c "
from app import create_app
app = create_app()
with app.app_context():
    from app.services.precedent.similarity_service import PrecedentSimilarityService
    svc = PrecedentSimilarityService()
    result = svc.calculate_similarity(7, 120, use_component_embedding=True)
    print(f'Overall: {result.overall_similarity:.3f}')
    print(f'Components: {result.component_scores}')
    print(f'Per-component: {result.per_component_scores}')
    print(f'Method: {result.method}')
"
```
Expected: non-zero `component_similarity` score, per-component scores for R/P/O/S/Rs/A/E/Ca/Cs, method='component'.

- [ ] **Step 3: Commit**

```bash
git add app/services/precedent/similarity_service.py
git commit -m "refactor: update component-aware weights for CBR-sound retrieval

Remove outcome_alignment and principle_overlap from retrieval scoring.
Outcome is displayed post-retrieval but not used for ranking, consistent
with legal CBR practice (HYPO/CATO). Principle tensions always returned
zero across all cases."
```

### Task 2: Wire Component Mode Through Discovery Service

**Files:**
- Modify: `app/services/precedent/precedent_discovery_service.py:83-123`

- [ ] **Step 1: Add `use_component_embedding` parameter to `find_precedents()`**

```python
def find_precedents(
    self,
    source_case_id: int,
    limit: int = 10,
    min_score: float = 0.3,
    focus: Optional[str] = None,
    use_dynamic_weights: bool = False,
    include_llm_analysis: bool = True,
    use_component_embedding: bool = False  # ADD THIS
) -> List[PrecedentMatch]:
```

Forward it to `find_similar_cases()`:

```python
similarity_results = self.similarity_service.find_similar_cases(
    source_case_id=source_case_id,
    limit=limit,
    min_score=min_score,
    weights=weights,
    use_component_embedding=use_component_embedding  # ADD THIS
)
```

- [ ] **Step 2: Commit**

```bash
git add app/services/precedent/precedent_discovery_service.py
git commit -m "feat: forward use_component_embedding through discovery service"
```

### Task 3: Update Precedents Route

**Files:**
- Modify: `app/routes/precedents.py:28-65` (MATCHING_METHODS), `app/routes/precedents.py:138-242` (_find_precedents_for_case)

- [ ] **Step 1: Update `MATCHING_METHODS` dict**

Replace current 6-method dict with component-aware methods:

```python
MATCHING_METHODS = {
    'component_similarity': {
        'name': 'D-tuple Similarity',
        'method': 'Cosine',
        'description': '9-component weighted embedding similarity (R, P, O, S, Rs, A, E, Ca, Cs)',
    },
    'provision_overlap': {
        'name': 'Provision Overlap',
        'method': 'Jaccard',
        'description': 'NSPE Code section overlap',
        'citation': 'NS-LCR (Sun et al., 2024)'
    },
    'tag_overlap': {
        'name': 'Subject Tags',
        'method': 'Jaccard',
        'description': 'Topic category overlap',
    }
}
```

- [ ] **Step 2: Update `_find_precedents_for_case()` to use component mode**

Change the `find_precedents()` call to pass `use_component_embedding=True`:

```python
matches = discovery_service.find_precedents(
    source_case_id=case_id,
    limit=limit,
    min_score=min_score,
    include_llm_analysis=False,
    use_component_embedding=True  # ADD THIS
)
```

Also pass `per_component_scores` from the similarity result through to the template. The `PrecedentMatch` dataclass already has `component_scores` but not per-component D-tuple breakdown. Add it to the result dict:

In the results append block, add per-component scores from the match's component_scores. The `SimilarityResult.per_component_scores` contains per-component cosine similarities (R, P, O, etc.), but this is not exposed through `PrecedentMatch`.

Two options: (a) add `per_component_scores` to `PrecedentMatch` dataclass, or (b) compute it in the route. Option (a) is cleaner.

Add to `PrecedentMatch` dataclass in `precedent_discovery_service.py`:
```python
per_component_scores: Optional[Dict[str, float]] = None
```

And in `_create_precedent_match()`:
```python
return PrecedentMatch(
    ...
    per_component_scores=similarity.per_component_scores,
)
```

Then in the route, pass it to the template results:
```python
results.append({
    ...
    'per_component_scores': match.per_component_scores or {},
})
```

- [ ] **Step 3: Commit**

```bash
git add app/routes/precedents.py app/services/precedent/precedent_discovery_service.py
git commit -m "feat: switch precedents page to component-aware retrieval

Use D-tuple 9-component embedding as primary retrieval signal.
Remove outcome and principle_tensions from retrieval scoring.
Pass per-component scores to template for breakdown display."
```

---

## Chunk 2: Template Changes

### Task 4: Update Precedents Template

**Files:**
- Modify: `app/templates/precedents.html`

- [ ] **Step 1: Update method legend**

Replace the three-badge legend (Cosine/Jaccard/Categorical) with component-aware legend:

```html
<div class="card mb-3">
    <div class="card-body py-2">
        <div class="row align-items-center">
            <div class="col-auto">
                <strong class="small">Retrieval Components:</strong>
            </div>
            <div class="col">
                <span class="badge bg-primary method-badge me-2">D-tuple</span>
                <span class="small text-muted me-3">9-component weighted embedding</span>
                <span class="badge bg-success method-badge me-2">Jaccard</span>
                <span class="small text-muted">Set intersection / union</span>
            </div>
        </div>
    </div>
</div>
```

- [ ] **Step 2: Update the left column (Similarity Components)**

Show the three retrieval components (D-tuple, Provision Overlap, Subject Tags) instead of six. The component_scores dict now has `component_similarity`, `provision_overlap`, `tag_overlap`.

Keep the same bar chart pattern but reduce to three rows.

- [ ] **Step 3: Add D-tuple per-component breakdown (expandable)**

Below the three main scores, add a collapsible detail showing per-component cosine similarities for the D-tuple:

```html
{% if precedent.per_component_scores %}
<details class="mt-2">
    <summary class="small text-muted" style="cursor: pointer;">
        D-tuple breakdown
    </summary>
    <div class="mt-1">
        {% for comp_code, comp_score in precedent.per_component_scores.items() %}
        <div class="component-row">
            <div class="component-label" style="width: 80px;">
                <span class="badge" style="background-color: {{ component_colors.get(comp_code, '#6c757d') }}; font-size: 0.65rem;">{{ comp_code }}</span>
            </div>
            <div class="component-bar">
                <div class="score-bar">
                    <div class="score-fill bg-primary" style="width: {{ (comp_score * 100)|round }}%;"></div>
                </div>
            </div>
            <div class="component-value">{{ (comp_score * 100)|round|int }}%</div>
        </div>
        {% endfor %}
    </div>
</details>
{% endif %}
```

Pass `component_colors` from the route (or define inline in template) using the entity type hex colors from ui-conventions.md:
```python
COMPONENT_COLORS = {
    'R': '#0d6efd', 'S': '#6f42c1', 'Rs': '#20c997',
    'P': '#fd7e14', 'O': '#dc3545', 'Cs': '#6c757d',
    'Ca': '#0dcaf0', 'A': '#198754', 'E': '#ffc107',
}
```

- [ ] **Step 4: Move outcome to "What They Share" section only**

Outcome is already displayed in the right-side "What They Share" panel. Remove it from the scored components. No template changes needed for the right panel -- it already shows outcome match/mismatch correctly.

- [ ] **Step 5: Remove principle tensions from "What They Share"**

Remove the "Pattern:" (transformation match) row since it's not part of retrieval scoring. Keep "Outcome:" and "Provisions:" and "Topics:" in "What They Share."

Actually, "Pattern" is transformation match (stalemate/transfer/etc.), not principle tensions. The principle_tensions Jaccard was a separate component that always returned 0. Transformation pattern is useful context to keep in "What They Share."

- [ ] **Step 6: Commit**

```bash
git add app/templates/precedents.html app/routes/precedents.py
git commit -m "feat: update precedents template for component-aware display

Show D-tuple, Provision Overlap, Subject Tags as retrieval components.
Add expandable per-component breakdown for D-tuple scores.
Outcome shown in 'What They Share' panel (post-retrieval, not scored)."
```

---

## Chunk 3: Cache and Cleanup

### Task 5: Add Component Similarity to Cache

**Files:**
- Modify: DB schema (add column)
- Modify: `app/services/precedent/similarity_service.py:311-370` (cache_similarity)
- Modify: `app/routes/precedents.py:383-419` (network API cache query)
- Modify: `scripts/populate_similarity_cache.py`

- [ ] **Step 1: Add `component_similarity` column to cache table**

```sql
ALTER TABLE precedent_similarity_cache
ADD COLUMN IF NOT EXISTS component_similarity double precision;
```

- [ ] **Step 2: Update `cache_similarity()` in similarity_service.py**

Add `component_similarity` to the INSERT/UPDATE:

```python
'component_similarity': result.component_scores.get('component_similarity', 0),
```

- [ ] **Step 3: Update `populate_similarity_cache.py` to support component mode**

Add `--component` flag that uses `use_component_embedding=True`:

```python
parser.add_argument('--component', action='store_true',
                    help='Use component-aware (D-tuple) similarity')
```

And pass it through:
```python
result = service.calculate_similarity(src_id, tgt_id,
    use_component_embedding=args.component)
```

- [ ] **Step 4: Repopulate cache with component-aware scores**

```bash
cd /home/chris/onto/proethica && source venv-proethica/bin/activate
python scripts/populate_similarity_cache.py --all --force --component
```

This recomputes all 3,968 cached pairs (~7,021 possible pairs for 119 cases). The existing cache uses section-based scores. Running with `--force --component` overwrites them with component-aware scores.

- [ ] **Step 5: Update the similarity network API to use component_similarity**

The network API at `app/routes/precedents.py:262` reads from cache. Update the query to include `component_similarity` column and use it when available.

- [ ] **Step 6: Commit**

```bash
git add app/services/precedent/similarity_service.py scripts/populate_similarity_cache.py app/routes/precedents.py
git commit -m "feat: add component_similarity to cache, repopulate

Cache now stores D-tuple similarity alongside section-based scores.
Populate script supports --component flag for component-aware mode."
```

### Task 6: Remove Structure Page Sidebar Toggle

**Files:**
- Modify: `app/templates/case_structure.html:248-340`
- Modify: `app/routes/cases/structure_embeddings.py:107-150`

- [ ] **Step 1: Simplify the Similar Cases sidebar**

Remove the Discussion/D-tuple toggle. Show only D-tuple results (the component-based similarity). Keep the "Full Similarity Analysis" link.

The structure page sidebar becomes a preview of the main precedents page, both using the same D-tuple metric. No toggle needed.

- [ ] **Step 2: Remove `similar_by_discussion` computation from route**

Remove the discussion-based similarity lookup from the structure route (lines 110-128). Keep only the component-based query.

- [ ] **Step 3: Remove toggle JavaScript**

Remove the `toggleSimilarMethod()` function from the template scripts block.

- [ ] **Step 4: Commit**

```bash
git add app/templates/case_structure.html app/routes/cases/structure_embeddings.py
git commit -m "refactor: remove discussion/D-tuple toggle from structure page

Structure page sidebar now shows only D-tuple similarity, consistent
with the precedents page. Removes redundant discussion-based lookup."
```

### Task 7: Update UI Conventions Doc

**Files:**
- Modify: `docs-internal/ui-conventions.md`

- [ ] **Step 1: Record changes in the Change Log**

Add entries for all changes made in this plan.

- [ ] **Step 2: Commit**

```bash
git add docs-internal/ui-conventions.md
git commit -m "docs: record CBR similarity synthesis changes in UI conventions"
```

---

## Verification

After all tasks complete:

1. Navigate to `/cases/precedents/?case_id=7` -- verify D-tuple scores display, outcome in "What They Share" only, no principle tensions
2. Click D-tuple breakdown -- verify per-component bars show R/P/O/S/Rs/A/E/Ca/Cs scores
3. Navigate to `/cases/7/structure` -- verify sidebar shows D-tuple results only, no toggle
4. Compare top results between old section-based and new component-based rankings -- expect different ordering since D-tuple weighs entity-level similarity
5. Check similarity network still loads from cache
