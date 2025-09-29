# ProEthica-OntServe Synchronization Improvement Plan

## Problem Statement
ProEthica currently maintains duplicate storage of committed entities instead of showing live OntServe data. This creates synchronization issues when entities are edited in OntServe.

## Proposed Solution: Live Data + Provenance Pattern

### Architecture Changes

#### 1. Storage Model Refactoring
```python
# Current (BAD): Full duplication
TemporaryRDFStorage:
  - Full entity data for both committed and uncommitted
  - is_committed flag

# Proposed (GOOD): Provenance + Reference
TemporaryRDFStorage:
  - Full data only for uncommitted entities
  - For committed: only store commit_metadata

CommitProvenance (new table):
  - case_id
  - entity_uri (reference to OntServe)
  - original_data (JSON snapshot at commit time)
  - commit_timestamp
  - commit_by
  - ontserve_ontology (which ontology it's in)
  - ontserve_version (version at commit time)
```

#### 2. Display Logic Changes

##### Current Flow (Problematic):
```
Review Page Load:
1. Query TemporaryRDFStorage for case entities
2. Display all with is_committed badges
3. Never check OntServe for updates
```

##### Proposed Flow (Synchronized):
```
Review Page Load:
1. Query uncommitted from TemporaryRDFStorage
2. Query committed entity URIs from CommitProvenance
3. Fetch live data from OntServe for committed URIs
4. Merge and display with change indicators
```

### Implementation Steps

#### Phase 1: Add OntServe Fetch Capability
```python
class OntServeDataFetcher:
    def fetch_entity(self, uri: str) -> Dict:
        """Fetch live entity data from OntServe"""
        # Query OntServe via MCP or direct DB

    def fetch_entities_by_case(self, case_id: int) -> List[Dict]:
        """Fetch all entities for a case from OntServe"""
        # Get from proethica-case-N ontology

    def compare_with_original(self, live_data: Dict, original: Dict) -> Dict:
        """Compare live vs original for change detection"""
        return {
            'has_changes': True/False,
            'changed_fields': [...],
            'live_data': live_data,
            'original_data': original
        }
```

#### Phase 2: Refactor Entity Review Display
```python
@bp.route('/case/<int:case_id>/entities/review')
def review_case_entities(case_id):
    # Get uncommitted (as before)
    uncommitted = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, is_committed=False
    ).all()

    # Get committed from OntServe (NEW)
    provenance = CommitProvenance.query.filter_by(case_id=case_id).all()
    ontserve_fetcher = OntServeDataFetcher()

    committed = []
    for prov in provenance:
        live_data = ontserve_fetcher.fetch_entity(prov.entity_uri)
        comparison = ontserve_fetcher.compare_with_original(
            live_data, prov.original_data
        )
        committed.append({
            'entity': live_data,
            'provenance': prov,
            'changes': comparison
        })

    return render_template('entity_review.html',
        uncommitted=uncommitted,
        committed=committed  # Now contains live data!
    )
```

#### Phase 3: Update UI to Show Synchronization Status
```html
<!-- Show sync status for committed entities -->
{% for entity in committed %}
<div class="entity-card">
    <span class="badge bg-success">Committed to OntServe</span>
    {% if entity.changes.has_changes %}
        <span class="badge bg-warning">Modified in OntServe</span>
        <button onclick="showChanges('{{ entity.entity.uri }}')">
            View Changes
        </button>
    {% endif %}

    <!-- Display LIVE data from OntServe -->
    <h5>{{ entity.entity.label }}</h5>
    <p>{{ entity.entity.description }}</p>

    <!-- Provenance info -->
    <small class="text-muted">
        Committed: {{ entity.provenance.commit_timestamp }}
    </small>
</div>
{% endfor %}
```

### Benefits of This Approach

1. **Single Source of Truth**: OntServe is authoritative for committed entities
2. **Change Visibility**: Users see when OntServe data has been edited
3. **Provenance Tracking**: Keep history of what was originally extracted
4. **Storage Efficiency**: No duplicate storage of committed entities
5. **Real-time Accuracy**: Always show current ontology state

### Migration Strategy

#### Step 1: Add new tables/fields
```sql
-- Add provenance table
CREATE TABLE commit_provenance (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL,
    entity_uri VARCHAR(500) NOT NULL,
    ontology_name VARCHAR(200) NOT NULL,
    original_data JSONB NOT NULL,
    commit_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    commit_by VARCHAR(100),
    UNIQUE(entity_uri)
);

-- Add reference fields to temporary_rdf_storage
ALTER TABLE temporary_rdf_storage
ADD COLUMN ontserve_uri VARCHAR(500),
ADD COLUMN sync_status VARCHAR(50) DEFAULT 'local';
```

#### Step 2: Implement fetcher service
- Create OntServeDataFetcher class
- Add MCP client methods for entity retrieval
- Implement comparison logic

#### Step 3: Update commit workflow
- On commit: Move data to provenance table
- Clear full data from temporary_rdf_storage
- Keep only reference to OntServe URI

#### Step 4: Update review interface
- Fetch live data for committed entities
- Show change indicators
- Allow viewing diffs

### Potential Challenges & Solutions

#### Challenge 1: Performance
**Issue**: Fetching from OntServe for each page load might be slow
**Solution**:
- Implement caching with TTL
- Batch fetch operations
- Use async loading for committed entities

#### Challenge 2: OntServe Availability
**Issue**: What if OntServe is down?
**Solution**:
- Fall back to cached provenance data
- Show "OntServe Unavailable" indicator
- Queue sync for when service returns

#### Challenge 3: Complex Edits
**Issue**: Major structural changes in OntServe
**Solution**:
- Handle missing entities gracefully
- Show "Entity Deleted in OntServe" status
- Allow re-extraction if needed

## Decision Point: Should We Implement This?

### Arguments FOR Implementation:
1. ✅ **Data Integrity**: Eliminates sync issues completely
2. ✅ **Transparency**: Users see exactly what's in OntServe
3. ✅ **Flexibility**: OntServe edits immediately visible
4. ✅ **Proper Architecture**: Follows single-source-of-truth principle
5. ✅ **Audit Trail**: Provenance tracking shows evolution

### Arguments AGAINST (Devil's Advocate):
1. ❌ **Complexity**: Adds architectural complexity
2. ❌ **Performance**: Potential latency from OntServe queries
3. ❌ **Dependencies**: ProEthica becomes dependent on OntServe availability
4. ❌ **Development Time**: Significant refactoring needed

## Recommendation

**STRONGLY RECOMMEND IMPLEMENTATION** for these reasons:

1. **Critical for Multi-User Environments**: If multiple users/systems edit ontologies, synchronization is essential
2. **Prevents Data Corruption**: Eliminates possibility of conflicting versions
3. **Professional Standard**: This is how enterprise systems handle distributed data
4. **Future-Proof**: Sets foundation for more advanced ontology management features

## Quick Win Alternative

If full implementation is too complex initially, consider this interim solution:

### "Refresh from OntServe" Button
```python
@bp.route('/case/<int:case_id>/entities/refresh_committed', methods=['POST'])
def refresh_committed_entities(case_id):
    """Pull latest data from OntServe for committed entities"""
    # Fetch all committed entity URIs
    # Query OntServe for current data
    # Update temporary_rdf_storage with latest
    # Mark as 'synced' with timestamp
    return jsonify({'refreshed': count, 'timestamp': now})
```

This provides:
- Manual sync capability
- User control over when to update
- Visibility into sync status
- Lower implementation complexity

## Next Steps

1. **Evaluate** current usage patterns - is multi-user editing a concern?
2. **Prototype** the OntServeDataFetcher service
3. **Test** performance impact of live fetching
4. **Implement** incrementally - start with manual refresh button
5. **Migrate** to full automatic sync once proven