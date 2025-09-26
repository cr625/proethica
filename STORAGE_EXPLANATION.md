# Where Committed Entities Are Stored - Complete Explanation

## Short Answer
**The entities showing as "Committed" on http://localhost:5000/scenario_pipeline/case/18/entities/review are stored in BOTH places:**
1. **ProEthica Database** - Maintains records with `is_committed=True` flag
2. **OntServe Database & Files** - Actual ontological data in TTL files and PostgreSQL

## Detailed Storage Architecture

### 1. ProEthica Database (ai_ethical_dm)
**Table**: `temporary_rdf_storage`
**Purpose**: Tracking and metadata
**What's stored**:
- Entity metadata (label, URI, type, extraction info)
- Commit status (`is_committed` flag)
- Extraction session information
- RDF JSON-LD representation

**Current status for Case 18**:
```
4 Classes (is_committed=True):
- Technical Evaluation Report
- Water Quality Standards
- Conflict of Interest State
- Public Safety Risk State

5 Individuals (is_committed=True):
- XYZ_InsufficientInformation_Report
- DrinkingWater_LeadStandards
- StateEnv_WaterSourceApproval
- EngineerB_WaterSource_EvaluationReport
- EngineerB_PublicHealthRisk_Letter
```

### 2. OntServe Storage (ontserve database + TTL files)

#### A. OntServe PostgreSQL Database (ontserve)
**Tables**: `ontologies`, `ontology_entities`
**Purpose**: Ontology management and querying
**What's stored**:
- Complete ontology definitions
- Entity relationships
- SPARQL query support
- MCP server data source

**Current entities**:
```
proethica-intermediate-extracted (4 classes):
- Technical Evaluation Report
- Water Quality Standards
- Conflict of Interest State
- Public Safety Risk State

proethica-case-18 (5 individuals):
- XYZ_InsufficientInformation_Report
- DrinkingWater_LeadStandards
- StateEnv_WaterSourceApproval
- EngineerB_WaterSource_EvaluationReport
- EngineerB_PublicHealthRisk_Letter
```

#### B. OntServe TTL Files
**Location**: `/home/chris/onto/OntServe/ontologies/`
**Files**:
- `proethica-intermediate-extracted.ttl` - Contains class definitions
- `proethica-case-18.ttl` - Contains individual instances

## How the Dual Storage Works

### When Entity is Extracted (Not Yet Committed)
1. **ProEthica**: Stores in `temporary_rdf_storage` with `is_committed=False`
2. **OntServe**: Nothing stored yet
3. **UI Display**: Shows as uncommitted (no "Committed" badge)

### When User Clicks "Commit Selected to OntServe"
1. **ProEthica**:
   - Updates `is_committed=True` in database
   - Maintains record for tracking
2. **OntServe**:
   - Classes written to `proethica-intermediate-extracted.ttl`
   - Individuals written to `proethica-case-N.ttl`
   - Database synchronized via `refresh_entity_extraction.py`
3. **UI Display**: Shows "Committed" badge

### When User Clicks "Clear All Entities"
1. **ProEthica**:
   - Deletes only records where `is_committed=False`
   - Preserves records where `is_committed=True`
2. **OntServe**:
   - No changes - TTL files remain intact
   - Database entries preserved
3. **UI Display**: Committed entities still show with "Committed" badge

## Why This Dual Storage?

### ProEthica's Role
- **Workflow Management**: Tracks extraction sessions and commit status
- **User Interface**: Provides data for the review page
- **Audit Trail**: Maintains history of what was extracted and when committed
- **Temporary Storage**: Holds uncommitted work for review

### OntServe's Role
- **Permanent Storage**: Authoritative source for ontological knowledge
- **Ontology Serving**: Provides data via MCP protocol to other systems
- **SPARQL Queries**: Enables complex ontological queries
- **Inter-System Communication**: Shared knowledge base for all services

## Viewing the Data

### In ProEthica (http://localhost:5000/scenario_pipeline/case/18/entities/review)
- Shows ALL entities (committed and uncommitted)
- "Committed" badges indicate `is_committed=True` in ProEthica database
- Data comes from ProEthica's `temporary_rdf_storage` table

### In OntServe (http://localhost:5003/)
- Shows ONLY committed entities
- Data comes from OntServe's database and TTL files
- Two separate ontologies:
  - `proethica-intermediate-extracted` - View extracted classes
  - `proethica-case-18` - View individual instances

## Summary
The "Committed" status on the ProEthica review page means:
1. ✅ Entity is marked as committed in ProEthica database (`is_committed=True`)
2. ✅ Entity has been saved to OntServe TTL files
3. ✅ Entity exists in OntServe PostgreSQL database
4. ✅ Entity will be preserved when clearing uncommitted entities
5. ✅ Entity is visible in OntServe web interface at http://localhost:5003/