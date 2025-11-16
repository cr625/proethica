# Migration 013: OBSOLETE - Do Not Apply

**Status:** Obsolete - superseded by existing database schema
**Created:** November 16, 2025
**Reason:** Database already has more comprehensive schema

---

## Summary

Migration `013_create_scenario_participants.sql` was created as part of Week 1 participant mapping work, but the database already contained a more advanced `scenario_participants` table.

**Do NOT apply this migration** - the table already exists with a better schema.

---

## Schema Comparison

### Migration 013 Schema (12 columns)
```sql
CREATE TABLE scenario_participants (
    id, case_id, role_entity_uri, name, title, background,
    motivations TEXT[], ethical_tensions TEXT[], character_arc,
    key_relationships JSONB, metadata JSONB, created_at
);
```

### Actual Database Schema (22 columns)
```sql
CREATE TABLE scenario_participants (
    id, case_id, participant_id, source_role_uri, name, title, role_type,
    background, expertise JSONB, qualifications JSONB, goals JSONB,
    obligations JSONB, constraints JSONB, narrative_role,
    relationships JSONB, llm_enhanced, llm_enrichment JSONB, llm_model,
    created_at, updated_at
);
```

**Key differences:**
- Column names: `role_entity_uri` → `source_role_uri`
- Column names: `key_relationships` → `relationships`
- Column names: `metadata` → `llm_enrichment`
- Arrays → JSONB: `motivations TEXT[]` → part of `llm_enrichment JSONB`
- Additional tracking: `llm_enhanced`, `llm_model`, `updated_at`
- More structured data: `expertise`, `qualifications`, `goals`, `obligations`, `constraints`

---

## Resolution

**Model updated:** `app/models/scenario_participant.py` now matches actual database (22 columns)

**Service updated:** `app/services/scenario_generation/participant_mapper.py` uses correct column names:
- `source_role_uri` instead of `role_entity_uri`
- `relationships` instead of `key_relationships`
- `llm_enrichment` instead of `metadata`
- Stores motivations/tensions in `llm_enrichment` JSONB
- Sets `llm_enhanced=True` and `llm_model` for tracking

**Migration status:** Skip - table already exists with superior schema

---

## Existing Data

As of November 16, 2025:
- **14 participant records** in database
- Created: November 11, 2025
- All records have `llm_enhanced=true`
- Model used: `claude-sonnet-4-5-20250929`

---

## Future Migrations

Next migration should be numbered **014** and should not attempt to recreate or alter `scenario_participants`.

---

## Testing

The updated model and service work with the existing database schema:

```bash
# Test that model matches database
python -c "
from app import create_app
from app.models.scenario_participant import ScenarioParticipant
app = create_app()
with app.app_context():
    # Query should work without errors
    count = ScenarioParticipant.query.count()
    print(f'Found {count} participants in database')
"
```

Expected output: `Found 14 participants in database`

---

## Related Documentation

- Model: `app/models/scenario_participant.py`
- Service: `app/services/scenario_generation/participant_mapper.py`
- Testing guide: `docs/TESTING_PARTICIPANT_MAPPING.md`

---

**Resolution Date:** November 16, 2025
**Resolved By:** Claude Code - schema mismatch detection and fix
