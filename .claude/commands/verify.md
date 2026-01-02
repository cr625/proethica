# ProEthica Case Verification Command

## Usage

```
/verify [case_id]     - Verify a specific synthesized case
/verify all           - Verify all synthesized cases
/verify summary       - Show synthesis status for all cases
```

## What This Verifies

This command checks synthesized cases (those with completed Steps 1-4) for data quality issues that could cause problems during demos.

### Verification Criteria

| Check | Severity | Description |
|-------|----------|-------------|
| Duplicate Entries | CRITICAL | Same extraction_type has multiple sessions of data |
| Arg/Val Mismatch | CRITICAL | argument_generated count != argument_validation count |
| Misattributed Language | WARNING | "The board concluded..." for non-explicit conclusions |
| Empty Class Definitions | WARNING | Class entities missing definitions |
| Role Classification | WARNING | Named roles missing role classification prefix |
| Completeness | INFO | Missing extraction types for synthesized case |
| Count Sanity | INFO | Entity counts outside expected ranges |

## Quick Commands

```bash
# Check which cases are synthesized (have argument_generated)
PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c "
SELECT case_id, COUNT(*) as total_entities,
       COUNT(CASE WHEN extraction_type = 'argument_generated' THEN 1 END) as args
FROM temporary_rdf_storage GROUP BY case_id ORDER BY case_id;"

# Verify specific case for duplicates
PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c "
SELECT extraction_type, COUNT(DISTINCT extraction_session_id) as sessions, COUNT(*) as total
FROM temporary_rdf_storage WHERE case_id = 7
GROUP BY extraction_type HAVING COUNT(DISTINCT extraction_session_id) > 1;"

# Check argument/validation counts for all cases
PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c "
SELECT case_id,
       COUNT(CASE WHEN extraction_type = 'argument_generated' THEN 1 END) as args,
       COUNT(CASE WHEN extraction_type = 'argument_validation' THEN 1 END) as vals
FROM temporary_rdf_storage GROUP BY case_id
HAVING COUNT(CASE WHEN extraction_type = 'argument_generated' THEN 1 END) > 0
ORDER BY case_id;"
```

## Synthesized Cases

Cases with `argument_generated` entries have completed Step 4 synthesis:
- Case 4, 7, 9, 11, 12, 15, 16 (as of January 2026)

**Primary Demo Case**: Case 7 (NSPE 24-2)

## Reference Documentation

- [docs-internal/CASE7_VERIFICATION_FIXES.md](docs-internal/CASE7_VERIFICATION_FIXES.md) - Issues found and fixed in Case 7
- [.claude/agents/verify-case.md](.claude/agents/verify-case.md) - Detailed verification agent

---

*Last Updated: January 2, 2026*
