# Comprehensive Plan for Updating ProEthica Core Entity Extractors

## Overview
Update all 9 ProEthica core entity extractors (R, P, O, S, Rs, A, E, Ca, Cs) to match the quality of the Roles extractor, with proper MCP integration, ontology entries, and optimized LLM prompts.

## Important Operational Notes

### Service Management
- **Start ProEthica**: `cd /home/chris/onto/proethica && python run.py` (runs on port 5000 for development)
- **Start OntServe Web**: `cd /home/chris/onto/OntServe && python web/app.py` (port 5003)
- **Start MCP Server**: `cd /home/chris/onto/OntServe && python servers/mcp_server.py` (port 8082)
- **Kill services**: Use `pkill -f "run.py"` or `pkill -f "mcp_server.py"`
- **Database access**: `PGPASSWORD=PASS psql -h localhost -U postgres -d ontserve`
- **ProEthica Dev URL**: http://localhost:5000 (development mode)
- **ProEthica Prod URL**: http://localhost:3333 (Gunicorn production only)

### Script Development Guidelines
- **Create scripts in**: `/home/chris/onto/proethica/scripts/` directory
- **Use timeout**: Add 3-5 second sleeps when testing scripts to allow services to respond
- **Fallback strategy**: If Python script hangs, create equivalent shell script in same directory
- **Test scripts**: Always test with small samples before full execution
- **Avoid complex CLI Python**: Create proper scripts instead of complex command-line Python

### Ontology Editing Process
1. **Check definitions in main document**: `/home/chris/onto/proethica/docs/chapter2_main_document.md` contains all entity definitions
2. **Additional concept details**: 
   - `/home/chris/onto/proethica/docs/proethica_master_plan.md` - Overall system design
   - `/home/chris/onto/proethica/docs/domain_prompts.md` - Extraction strategies
   - `/home/chris/onto/proethica/docs/ONTOLOGY_MODIFICATION_GUIDE.md` - How to edit ontologies
3. **Edit ontology files**: Located in `/home/chris/onto/OntServe/storage/ontologies/`
   - `proethica-core.ttl` - Core formal definitions (19 entities)
   - `proethica-intermediate.ttl` - Populated concepts (76 entities)
   - `engineering-ethics.ttl` - Domain-specific NSPE-based concepts (33 entities)
4. **Ontology hierarchy**:
   - `proethica-core` → Base formal tuple D=(R,P,O,S,Rs,A,E,Ca,Cs)
   - `proethica-intermediate` → Imports from core, adds professional role subclasses
   - `engineering-ethics` → Imports from intermediate, adds specific engineering roles (Quality Engineer, Safety Engineer, etc.)
5. **Refresh database**: After editing TTL files, follow ONTOLOGY_MODIFICATION_GUIDE.md
6. **Verify in database**: Check with SQL queries to confirm updates

## Detailed Plan for Each Entity Type

### Phase 1: Review and Documentation Check

1. **Primary source**: Review `/home/chris/onto/proethica/docs/chapter2_main_document.md` for:
   - Formal definitions of each entity type
   - Theoretical grounding with specific claims about each concept
   - Examples from professional ethics literature

2. **Review existing extractors** in `/home/chris/onto/proethica/app/services/extraction/`

3. **Document theoretical grounding** - When referencing literature:
   - Don't just cite names, explain the specific concept being used
   - Example: "Professional roles as obligation-generating filters that transform general duties into specific requirements based on role context"
   - Include the practical implication for extraction

### Phase 2: Update Each Extractor (Following Roles Pattern)

For each entity type:

#### 1. Update enhanced prompt file (e.g., `enhanced_prompts_principles.py`):
```python
# Add MCP integration
from app.services.external_mcp_client import get_external_mcp_client

# Fetch existing entities
external_client = get_external_mcp_client()
existing_principles = external_client.get_all_principle_entities()

# Create detailed definitions with practical explanations
principle_definitions = {
    'Principle': 'Fundamental ethical guidelines that provide reasons for obligations and shape professional judgment',
    'Public Safety Paramount': 'The overriding principle that public welfare takes precedence over all other considerations',
    # ... more with explanations of WHY each matters for extraction
}
```

#### 2. Update extractor class:
- Ensure `_get_prompt_for_preview()` always uses MCP (no conditionals)
- Add proper deduplication by URI
- Include detailed logging

#### 3. Update ontology entries:
- Add entities identified from NSPE Code of Ethics
- Include rdfs:comment with practical descriptions
- Maintain proper subClassOf hierarchy

#### 4. Optimize prompt structure:
- Clear task statement with entity count
- Practical framework (not just citations)
- Existing ontology entities organized by category
- Extraction rules emphasizing "check existing first"
- JSON format with `is_existing` and `ontology_match` fields

### Phase 3: Testing Protocol

Create `/home/chris/onto/proethica/scripts/test_all_extractors.py`:
```python
#!/usr/bin/env python3
"""Test all entity extractors for MCP integration."""

import time
import sys
sys.path.append('/home/chris/onto/proethica')

from app.services.extraction.principles import PrinciplesExtractor
from app.services.extraction.obligations import ObligationsExtractor
from app.services.extraction.states import StatesExtractor
from app.services.extraction.resources import ResourcesExtractor
# Import others as needed

test_text = """
The engineer must hold paramount the safety, health, and welfare of the public.
Engineers shall perform services only in areas of their competence.
"""

extractors = [
    ('Principles', PrinciplesExtractor),
    ('Obligations', ObligationsExtractor),
    ('States', StatesExtractor),
    ('Resources', ResourcesExtractor),
    # Add others
]

for name, ExtractorClass in extractors:
    print(f"\nTesting {name} extractor...")
    try:
        extractor = ExtractorClass()
        prompt = extractor._get_prompt_for_preview(test_text)
        
        if 'EXISTING' in prompt.upper() and 'ONTOLOGY' in prompt.upper():
            # Count entities mentioned
            entity_count = prompt.count('- ')
            print(f"  ✅ MCP integrated with {entity_count} existing entities")
        else:
            print(f"  ❌ Missing MCP context")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    time.sleep(3)  # Allow services to recover
```

### Phase 4: Database Verification

Create `/home/chris/onto/proethica/scripts/verify_ontology_entities.sh`:
```bash
#!/bin/bash
# Verify entity counts in database

echo "ProEthica Ontology Entity Counts:"
echo "================================="

PGPASSWORD=PASS psql -h localhost -U postgres -d ontserve -t << EOF
SELECT 
    CASE 
        WHEN label ILIKE '%Role%' THEN 'Roles'
        WHEN label ILIKE '%Principle%' THEN 'Principles'
        WHEN label ILIKE '%Obligation%' THEN 'Obligations'
        WHEN label ILIKE '%State%' THEN 'States'
        WHEN label ILIKE '%Resource%' THEN 'Resources'
        WHEN label ILIKE '%Action%' THEN 'Actions'
        WHEN label ILIKE '%Event%' THEN 'Events'
        WHEN label ILIKE '%Capabilit%' THEN 'Capabilities'
        WHEN label ILIKE '%Constraint%' THEN 'Constraints'
        ELSE 'Other'
    END as entity_type,
    COUNT(*) as count
FROM ontology_entities
WHERE ontology_id IN (
    SELECT id FROM ontologies 
    WHERE name IN ('proethica-core', 'proethica-intermediate')
)
AND entity_type = 'class'
GROUP BY entity_type
ORDER BY entity_type;
EOF
```

## Execution Order & Priority

1. **Principles** (P) - Foundation of ethical reasoning
   - Key concepts: Public welfare, integrity, competence, honesty
   - Source: NSPE Fundamental Canons

2. **Obligations** (O) - Core normative requirements  
   - Key concepts: Must/shall statements, professional duties
   - Source: NSPE Rules of Practice

3. **States** (S) - Context conditions
   - Already has `create_enhanced_states_prompt`
   - Needs MCP integration completion
   - Key concepts: Conflict of interest, competence boundaries

4. **Resources** (Rs) - Knowledge sources
   - Already has MCP in `_create_resources_prompt_with_mcp`
   - Needs ontology population
   - Key concepts: Codes, standards, precedents

5. **Actions** (A) - Behavioral manifestations
   - Key concepts: Approve, reject, report, disclose
   - Source: NSPE verbs and action requirements

6. **Events** (E) - Temporal occurrences
   - Key concepts: Incidents, discoveries, changes
   - Source: Triggering conditions in NSPE

7. **Capabilities** (Ca) - Agent competencies
   - Key concepts: Technical skills, judgment abilities
   - Source: Competence requirements

8. **Constraints** (Cs) - Limiting factors
   - Key concepts: Legal limits, resource constraints
   - Source: Boundary conditions in NSPE

## Success Criteria

For each entity type:
- [ ] Enhanced prompt includes MCP context with exact entity count
- [ ] Ontology has 10+ meaningful entities from NSPE/literature
- [ ] No duplicate entities returned from MCP (check with deduplication)
- [ ] Prompt emphasizes "check existing ontology first"
- [ ] Test script confirms MCP integration works
- [ ] Database query shows correct entity count
- [ ] Practical descriptions explain WHY each concept matters

## Final System Test

After all updates:
1. Kill all existing services: `pkill -f "run.py"; pkill -f "app.py"; pkill -f "mcp_server.py"`
2. Restart in order:
   - MCP Server first (port 8082)
   - OntServe Web (port 5003)
   - ProEthica (port 5000)
3. Run `/home/chris/onto/proethica/scripts/test_all_extractors.py`
4. Test extraction on NSPE sample text
5. Verify at http://localhost:5000 - Guidelines - Analyze
6. Check that all 9 entity types extract with ontology awareness

## Notes on Literature References

When updating prompts with theoretical grounding:
- Don't just cite "Smith (2020)" - explain the specific concept
- Example: "Roles function as ethical filters that transform general obligations into specific duties based on the agent's professional position and relationships"
- Include practical implications: "This means when extracting roles, look for positions that create specific duties not applicable to everyone"
- Focus on operational definitions that help the LLM understand what to extract

This plan ensures systematic updates matching the Roles extractor quality while maintaining practical, actionable guidance for LLM extraction.