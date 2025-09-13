# ProEthica Entity Extraction Implementation Guide

## CRITICAL REQUIREMENTS (READ FIRST)

### 1. Ontology-First Architecture
**Entities MUST be defined as classes in TTL files, NOT just in the database**

1. **Base classes**: Define in `proethica-core.ttl` (e.g., `proeth-core:Constraint`)
2. **Subclasses**: Define in `proethica-intermediate.ttl` or `engineering-ethics.ttl`
3. **Database**: Load FROM TTL files using scripts
4. **MCP Server**: Retrieves from database via recursive CTE queries
5. **Extractors**: Fetch from MCP server dynamically

**NEVER**: Add entities only to database - they MUST be in TTL files first!

### 2. Academic Definitions Source
All entity definitions MUST come from:
- **Primary**: `/home/chris/onto/proethica/docs/chapter2_main_document.md`
- **Secondary**: Literature references with DOI links
- **Format**: Include both theoretical definition AND practical extraction guidance

### 3. Implementation Pattern (Uniform for All Entities)

Each entity extractor MUST follow this pattern:

```python
# In enhanced_prompts_X.py
def create_enhanced_X_prompt(text: str, include_mcp_context: bool = False, 
                            existing_X: Optional[List] = None) -> str:
    if include_mcp_context:
        if existing_X is None:  # CRITICAL: Dynamic fetching
            from app.services.external_mcp_client import get_external_mcp_client
            external_client = get_external_mcp_client()
            existing_X = external_client.get_all_X_entities()
            # Also get related Pass entities for context
```

### 4. Pass Integration Requirements

**Pass 1 (Contextual Framework)**: Roles + States + Resources
- Show WHO has obligations, WHEN they activate, WHAT guides decisions

**Pass 2 (Normative Requirements)**: Principles + Obligations + Constraints + Capabilities  
- Show WHY (principles), WHAT MUST (obligations), WHAT CANNOT (constraints), WHO CAN (capabilities)

**Pass 3 (Temporal Dynamics)**: Actions + Events
- Show behavioral manifestations and temporal occurrences

### 5. UI Integration Points
- **Step 2**: `/home/chris/onto/proethica/app/routes/scenario_pipeline/step2.py`
- **Template**: `/home/chris/onto/proethica/app/templates/scenarios/step2.html`
- **Import Pattern**: Must import both function AND class from enhanced_prompts files

### 6. Server Management
```bash
# Start servers (in order)
cd /home/chris/onto/OntServe && python servers/mcp_server.py  # Port 8082
cd /home/chris/onto/OntServe && python web/app.py             # Port 5003  
cd /home/chris/onto/proethica && python run.py                # Port 5000

# Kill services
pkill -f "mcp_server.py"
pkill -f "app.py" 
pkill -f "run.py"

# Restart after TTL changes
1. Edit TTL files
2. Kill all services
3. Restart in order above
4. Database auto-reloads from TTL on startup
```

### 7. No Fallbacks in Dev Mode
- Remove all fallback text when MCP fails
- If MCP fails, FIX IT, don't provide static text
- All prompts MUST show actual ontology entities

---

## Implementation Status

### ✅ PASS 1 COMPLETE (Contextual Framework)
All three Pass 1 components implemented with MCP integration:

#### Roles (R) - WHO has obligations
- **Status**: ✅ Complete (9 entities)
- **Files**: `enhanced_prompts_roles_resources.py`
- **Hierarchy**: Role → ProfessionalRole/ParticipantRole → Specific roles

#### States (S) - WHEN obligations activate  
- **Status**: ✅ Complete (7 entities)
- **Files**: `enhanced_prompts_states_capabilities.py`
- **Categories**: Conflict, Risk, Competence, Emergency states

#### Resources (Rs) - WHAT guides decisions
- **Status**: ✅ Complete (4 entities)
- **Files**: `enhanced_prompts_roles_resources.py`
- **Types**: Professional codes, Case precedents, Standards

---

### ⚠️ PASS 2 IN PROGRESS (Normative Requirements)

#### Principles (P) - WHY (ethical foundations)
- **Status**: ✅ Complete (12 entities)
- **Files**: `enhanced_prompts_principles.py`
- **Hierarchy**: Principle → 4 categories → 6 specific principles
- **Key Fix**: Using recursive CTE with parent_uri, not label matching

#### Obligations (O) - WHAT MUST be done
- **Status**: ✅ Complete (15 entities)
- **Files**: `enhanced_prompts_obligations.py`
- **Categories**: Disclosure, Safety, Competence, Confidentiality, etc.
- **Key Fix**: Dynamic MCP fetching when include_mcp_context=True

#### Constraints (Cs) - WHAT CANNOT be done
- **Status**: ⚠️ PARTIAL - Database only, NOT in TTL files!
- **Files**: `enhanced_prompts_constraints.py`
- **CRITICAL ISSUE**: 13 constraint subclasses exist only in database, not in TTL files
- **TODO**: 
  1. Add constraint subclasses to `proethica-intermediate.ttl`
  2. Reload database from TTL
  3. Verify MCP retrieval

#### Capabilities (Ca) - WHO CAN fulfill obligations
- **Status**: ❌ Not started
- **Files**: Need to create separate from States
- **Note**: Part of Pass 2 per Chapter 2 (norm competence)

---

### ❌ PASS 3 NOT STARTED (Temporal Dynamics)

#### Actions (A) - Behavioral manifestations
- **Status**: ❌ Not implemented with MCP
- **Files**: `actions.py` exists but needs enhancement

#### Events (E) - Temporal occurrences  
- **Status**: ❌ Not implemented with MCP
- **Files**: `events.py` exists but needs enhancement

---

## Current Task: Fix Constraints Implementation

### Problem
Constraint subclasses were added directly to database via script, violating ontology-first architecture.

### Solution Steps
1. ✅ Created `constraint_subclasses_to_add.ttl` with proper definitions
2. ⏳ Add these to `proethica-intermediate.ttl`
3. ⏳ Restart services to reload from TTL
4. ⏳ Verify MCP retrieves all 17 constraints
5. ⏳ Test in UI that constraints show with full definitions

### Constraint Subclasses to Add (13 total)
**Boundary Types (6)**:
- LegalConstraint - Kroll 2020
- RegulatoryConstraint - Taddeo et al. 2024
- ResourceConstraint - Ganascia 2007
- CompetenceConstraint - Hallamaa & Kalliokoski 2022
- JurisdictionalConstraint - Dennis et al. 2016
- ProceduralConstraint - Furbach et al. 2014

**Defeasibility Types (2)**:
- DefeasibleConstraint - Ganascia 2007
- InviolableConstraint - Dennis et al. 2016

**Ethical Boundary Types (3)**:
- EthicalConstraint - Benzmüller et al. 2020
- SafetyConstraint - Arkin 2008
- ConfidentialityConstraint - Dennis et al. 2016

**Temporal Types (2)**:
- TemporalConstraint - Govindarajulu & Bringsjord 2017
- PriorityConstraint - Scheutz & Malle 2014

---

## Next: Capabilities Implementation

After fixing Constraints, implement Capabilities to complete Pass 2:

1. Check Chapter 2.2.8 for Capabilities definition
2. Create capability subclasses in TTL
3. Create `enhanced_prompts_capabilities.py` (separate from states)
4. Add MCP method `get_all_capability_entities()`
5. Integrate with Pass 2 context
6. Test extraction with NSPE text

---

## Success Metrics

Each entity type MUST have:
- [ ] Base class in `proethica-core.ttl`
- [ ] Subclasses in `proethica-intermediate.ttl` or `engineering-ethics.ttl`
- [ ] Enhanced prompt file with MCP integration
- [ ] Dynamic fetching (no static fallbacks)
- [ ] Pass integration context
- [ ] Full definitions without truncation
- [ ] Literature grounding with context
- [ ] Test showing correct entity count

---

## Files Reference

### Core Documents
- `/home/chris/onto/proethica/docs/chapter2_main_document.md` - Entity definitions
- `/home/chris/onto/proethica/docs/ONTOLOGY_MODIFICATION_GUIDE.md` - How to edit TTLs
- `/home/chris/onto/proethica/CLAUDE.md` - AI assistant instructions

### Ontology Files  
- `/home/chris/onto/OntServe/ontologies/proethica-core.ttl` - Base classes
- `/home/chris/onto/OntServe/ontologies/proethica-intermediate.ttl` - Subclasses
- `/home/chris/onto/OntServe/ontologies/engineering-ethics.ttl` - Domain-specific

### Implementation Files
- `/home/chris/onto/proethica/app/services/extraction/enhanced_prompts_*.py` - Extractors
- `/home/chris/onto/proethica/app/services/external_mcp_client.py` - MCP client
- `/home/chris/onto/OntServe/storage/concept_manager_database.py` - Database queries

### UI Integration
- `/home/chris/onto/proethica/app/routes/scenario_pipeline/step2.py` - Route handler
- `/home/chris/onto/proethica/app/templates/scenarios/step2.html` - Template

---

## Archive/Obsolete Files

The following files are obsolete and should be archived:
- Reasoning inspector documents (if any found)
- Old extraction implementations without MCP
- Static prompt generators

---

## Notes

- **CTE** = Common Table Expression (SQL feature for hierarchical queries)
- **Recursive CTE** = Traverses parent-child relationships via parent_uri
- **MCP** = Model Context Protocol (server providing ontology context)
- Always test with actual NSPE text for validation
