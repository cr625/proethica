# Testing Participant Mapping (Step 5 Stage 3)

**Created:** November 16, 2025
**Feature:** LLM-enhanced participant profile extraction
**Status:** Ready for testing

---

## Quick Start

### 1. Check Database Schema (NO MIGRATION NEEDED!)

**⚠️ IMPORTANT:** Migration 013 is OBSOLETE - the database already has a better schema!

```bash
# From proethica directory
cd /home/user/proethica

# Check if table exists (it should!)
export PGPASSWORD=PASS
psql -h localhost -U postgres -d ai_ethical_dm -c "\d scenario_participants"
```

The table already exists with **22 columns** (not the 12 in migration 013):
- `source_role_uri` (not `role_entity_uri`)
- `relationships` (not `key_relationships`)
- `llm_enrichment` (not `metadata`)
- Plus: `participant_id`, `llm_enhanced`, `llm_model`, `updated_at`, etc.

**The model and service have been updated to match this existing schema.**

See `db_migration/013_OBSOLETE_README.md` for full details.

### 2. Start the Application

```bash
# Make sure ANTHROPIC_API_KEY is set
export ANTHROPIC_API_KEY="your-key-here"

# Start ProEthica
python run.py
```

### 3. Test via Web UI

**Step-by-step:**

1. **Navigate to scenario generation**:
   ```
   http://localhost:5000/scenario_pipeline/case/8/generate
   ```
   (Case 8 is a good test case - has complete extraction)

2. **Watch the SSE stream**:
   - Stage 1: Data Collection (~10 seconds)
   - Stage 2: Timeline Construction (~5 seconds)
   - **Stage 3: Participant Mapping** (~30-60 seconds with LLM)

3. **Check progress messages**:
   ```
   Stage 3: Creating character profiles...
   Stage 3: Analyzing 12 roles with LLM...
   Stage 3: Created 8 participant profiles
   ```

4. **Check browser console** for full JSON response

---

## Testing Methods

### Method 1: Web UI (Easiest)

**Full Scenario Generation:**
```
http://localhost:5000/scenario_pipeline/case/8/generate
```

**View Results:**
```
http://localhost:5000/scenario_pipeline/case/8/step3
```

### Method 2: Python Script (Most Control)

Create `test_participant_mapping.py`:

```python
"""
Test participant mapping directly.
"""

import os
os.environ['ANTHROPIC_API_KEY'] = 'your-key-here'  # Set your key

from app import create_app
from app.services.scenario_generation import ParticipantMapper
from app.models import Document, db

# Initialize app
app = create_app()

with app.app_context():
    # Test case
    case_id = 8  # Use Case 8 or any completed case

    # Get roles for this case
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    roles = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        entity_type='Role'
    ).all()

    print(f"Found {len(roles)} roles for case {case_id}")
    for role in roles[:5]:
        print(f"  - {role.entity_label}")

    # Create mapper
    mapper = ParticipantMapper()

    # Generate participants
    print("\nGenerating participants with LLM...")
    participants = mapper.create_participants(
        case_id=case_id,
        roles=roles
    )

    # Print results
    print(f"\nCreated {len(participants)} participants:")
    for p in participants:
        print(f"\n{p['name']} - {p.get('title', 'No title')}")
        print(f"  Motivations: {len(p.get('motivations', []))}")
        print(f"  Tensions: {len(p.get('ethical_tensions', []))}")
        print(f"  Character arc: {p.get('character_arc', 'None')[:80]}...")

    # Save to database (optional)
    save = input("\nSave to database? (y/n): ")
    if save.lower() == 'y':
        saved = mapper.save_participants_to_db(participants, db.session)
        print(f"Saved {len(saved)} participants to database")
```

Run:
```bash
python test_participant_mapping.py
```

### Method 3: Direct Database Query

After running scenario generation, check the database:

```bash
export PGPASSWORD=PASS

# View all participants for a case
psql -h localhost -U postgres -d ai_ethical_dm -c "
SELECT
    name,
    title,
    array_length(motivations, 1) as motivation_count,
    array_length(ethical_tensions, 1) as tension_count,
    length(character_arc) as arc_length
FROM scenario_participants
WHERE case_id = 8
ORDER BY name;
"

# View full participant details
psql -h localhost -U postgres -d ai_ethical_dm -c "
SELECT
    name,
    title,
    motivations,
    ethical_tensions,
    character_arc
FROM scenario_participants
WHERE case_id = 8 AND name = 'Engineer A';
"

# Check LLM usage metadata
psql -h localhost -U postgres -d ai_ethical_dm -c "
SELECT
    name,
    metadata->'requested_at' as timestamp,
    metadata->'model' as model
FROM scenario_participants
WHERE case_id = 8;
"
```

---

## What to Look For

### ✅ Success Indicators

1. **Stage 3 completes** without errors (check browser console/terminal)
2. **Participants created**: 5-12 profiles (varies by case)
3. **Each participant has**:
   - Name (e.g., "Engineer A", "Client X")
   - Title (e.g., "Senior Structural Engineer")
   - 2-4 motivations
   - 2-4 ethical tensions
   - Character arc (50-200 chars)
   - 1-5 key relationships

4. **Database records** match participant count
5. **LLM token usage** logged (~2000-4000 tokens)

### ❌ Common Issues

**Issue: "No roles found"**
- **Cause**: Case doesn't have extraction data
- **Fix**: Run Passes 1-3 first:
  ```
  http://localhost:5000/scenario_pipeline/case/8/step1
  ```

**Issue: "ANTHROPIC_API_KEY not set"**
- **Cause**: API key missing
- **Fix**:
  ```bash
  export ANTHROPIC_API_KEY="sk-ant-..."
  ```

**Issue: "JSON parsing failed"**
- **Cause**: LLM returned unexpected format
- **Fix**: Check logs for raw response, may need prompt adjustment

**Issue: Timeout after 3 minutes**
- **Cause**: Too many roles or case text too long
- **Fix**: Mapper limits to 15 roles and 3000 chars, should not timeout

---

## Interpreting Results

### Example Good Output

```json
{
  "name": "Engineer A",
  "title": "Senior Structural Engineer",
  "background": "20 years experience in commercial construction...",
  "motivations": [
    "Professional integrity and maintaining reputation",
    "Concern for public safety",
    "Career advancement and job security"
  ],
  "ethical_tensions": [
    "Loyalty to employer vs duty to public",
    "Professional engineering standards vs cost constraints",
    "Reporting violations vs fear of retaliation"
  ],
  "character_arc": "Initially hesitant to challenge employer's decisions, gradually becomes more assertive about safety concerns, ultimately reports violations to licensing board despite personal risk",
  "key_relationships": [
    {
      "participant_id": "r1",
      "relationship": "reports to",
      "description": "Client pressures Engineer A for faster approval"
    },
    {
      "participant_id": "r2",
      "relationship": "collaborates with",
      "description": "Works alongside other consulting engineers"
    }
  ]
}
```

### Quality Checks

**Good participants:**
- ✅ Specific, concrete motivations (not generic)
- ✅ Tensions reflect actual case dilemmas
- ✅ Character arc shows development
- ✅ Relationships are case-specific

**Poor participants:**
- ❌ Generic motivations ("be ethical")
- ❌ Tensions not from case text
- ❌ No character development
- ❌ Missing relationships

---

## Test Cases

### Recommended Cases for Testing

**Case 8**: Good baseline
- Has complete extraction (Passes 1-3)
- ~12 roles identified
- Complex ethical dilemma
- Multiple participants with tensions

**Case 10**: Another good test
- Different scenario type
- Different role mix
- Tests generalization

**Case with No Extraction**: Should fail gracefully
- Error: "No roles found"
- No participants created
- Stage 3 skipped

---

## Monitoring LLM Usage

### Check Token Costs

```python
from app.services.llm import get_llm_manager

llm = get_llm_manager()
stats = llm.get_usage_stats()

print(f"Total calls: {stats['total_calls']}")
print(f"Total tokens: {stats['total_input_tokens'] + stats['total_output_tokens']}")
print(f"Total cost: ${stats['total_cost_usd']:.4f}")
print(f"\nBy model:")
for model, data in stats['calls_by_model'].items():
    print(f"  {model}: {data['calls']} calls, ${data['cost_usd']:.4f}")
```

**Expected costs** (per case):
- Input: ~2000-3000 tokens (~$0.006-0.009)
- Output: ~1000-2000 tokens (~$0.015-0.030)
- **Total per case: ~$0.02-0.04**

---

## Debugging

### Enable Detailed Logging

```python
import logging

# Set LLM manager to debug mode
logging.getLogger('app.services.llm.manager').setLevel(logging.DEBUG)
logging.getLogger('app.services.scenario_generation.participant_mapper').setLevel(logging.DEBUG)

# Now run tests - will see full prompts and responses
```

### Check Raw LLM Response

```python
# Add to participant_mapper.py temporarily:
logger.info(f"[DEBUG] Raw LLM response: {response.text}")
```

### Validate JSON Manually

```python
import json

# Copy response text from logs
response_text = '...'  # From logs

# Try to parse
try:
    data = json.loads(response_text)
    print("Valid JSON!")
except json.JSONDecodeError as e:
    print(f"Invalid JSON: {e}")
    # Check for markdown wrapping
    if '```' in response_text:
        print("Has markdown code blocks - parser should handle this")
```

---

## Integration Testing

### Full Pipeline Test

```bash
# Test complete scenario generation with all stages
curl -N http://localhost:5000/scenario_pipeline/case/8/generate
```

Watch for:
1. Stage 1: Data collection (~10s)
2. Stage 2: Timeline (~5s)
3. **Stage 3: Participants (~30-60s)**
4. Stages 4-9: Placeholders (~10s)

### Check Database Integrity

```sql
-- Verify foreign key relationships
SELECT
    sp.name,
    d.title as case_title
FROM scenario_participants sp
JOIN documents d ON sp.case_id = d.id
WHERE sp.case_id = 8;

-- Check for orphaned participants (shouldn't exist)
SELECT * FROM scenario_participants
WHERE case_id NOT IN (SELECT id FROM documents);
```

---

## Next Steps

Once participant mapping works:

1. **Week 2**: Implement Stage 4 (Decision Points)
2. **Connect participants to decisions**: Link who makes which decisions
3. **Visualize relationships**: Network graph of participants
4. **Export for teaching**: Generate participant handouts

---

## Questions?

**Common questions:**

Q: How many participants should be created?
A: 5-12 is typical. Depends on case complexity.

Q: Can I re-run for same case?
A: Yes, but will create duplicates. Clear old data first:
```sql
DELETE FROM scenario_participants WHERE case_id = 8;
```

Q: What if LLM creates bad participants?
A: Adjust prompt in `participant_mapper.py` or switch models.

Q: Token usage too high?
A: Reduce `max_tokens` from 4000 to 2000 in `create_participants()`.

---

**Ready to test!** Start with Method 1 (Web UI) for easiest testing.
