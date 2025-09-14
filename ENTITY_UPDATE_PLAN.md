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

### ✅ PASS 2 COMPLETE (Normative Requirements)
All four Pass 2 components implemented with MCP integration:

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
- **Status**: ✅ Complete (17 entities)
- **Files**: `enhanced_prompts_constraints.py`
- **Categories**: Boundary, Defeasibility, Ethical, Temporal types
- **Key Fix**: All 13 subclasses added to TTL files following ontology-first architecture

#### Capabilities (Ca) - WHO CAN fulfill obligations
- **Status**: ✅ Complete (17 entities - base + 15 new + Technical)
- **Files**: `enhanced_prompts_states_capabilities.py`, `capabilities.py`
- **Categories**: Norm Management, Awareness, Learning, Reasoning, Communication, Domain-Specific
- **Key Fix**: Added all 15 subclasses to proethica-intermediate.ttl (January 13, 2025)

---

### ❌ PASS 3 NOT STARTED (Temporal Dynamics)

#### Actions (A) - Behavioral manifestations
- **Status**: ❌ Not implemented with MCP
- **Files**: `actions.py` exists but needs enhancement

#### Events (E) - Temporal occurrences  
- **Status**: ❌ Not implemented with MCP
- **Files**: `events.py` exists but needs enhancement

---

## Completed Tasks (January 13, 2025)

### ✅ Constraints Implementation Fixed
- Added all 13 constraint subclasses to `proethica-intermediate.ttl`
- Verified MCP retrieves all 17 constraints (base + subclasses)
- Tested UI shows constraints with full definitions

### ✅ Capabilities Implementation Complete
- Added 15 capability subclasses to `proethica-intermediate.ttl`
- Based on Chapter 2.2.8 literature (Tolmeijer et al. 2021, Anderson 2018, etc.)
- Created MCP method `get_all_capability_entities()`
- Integrated with `capabilities.py` extractor
- Verified all 17 capabilities in database (base + 15 new + Technical)

### Capability Categories Implemented:
**Norm Management (2)**:
- NormCompetence - Tolmeijer et al. 2021
- ConflictResolution - Dennis et al. 2016

**Awareness & Perception (2)**:
- SituationalAwareness - Almpani et al. 2023
- EthicalPerception - Anderson et al. 2006

**Learning & Adaptation (2)**:
- EthicalLearning - Anderson & Anderson 2018
- PrincipleRefinement - GenEth system

**Reasoning & Deliberation (3)**:
- EthicalReasoning - Wallach & Allen 2009
- CausalReasoning - Sarmiento et al. 2023
- TemporalReasoning - Govindarajulu & Bringsjord 2017

**Communication & Explanation (3)**:
- ExplanationGeneration - Langley 2019
- JustificationCapability - McLaren 2003
- ResponsibilityDocumentation - Arkin 2008

**Domain-Specific (3)**:
- DomainExpertise - Hallamaa & Kalliokoski 2022
- ProfessionalCompetence - Kong et al. 2020
- PrecedentRetrieval - McLaren 2003

---

## Next: Pass 3 Implementation (Actions & Events)

With Pass 2 complete, implement temporal dynamics:

1. Review Chapter 2 for Actions and Events definitions
2. Create action/event subclasses in TTL
3. Update extractors with MCP integration
4. Add temporal reasoning context
5. Test with NSPE scenarios

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
