# Viewing Committed Entities in OntServe - Complete Guide

## Current Status (As of September 26, 2025)

### ✅ **Classes in proethica-intermediate-extracted**
**URL**: http://localhost:5003/ontology/proethica-intermediate-extracted

**4 Classes Successfully Visible**:
1. **TechnicalEvaluationReport** (Resource)
2. **WaterQualityStandards** (Resource)
3. **ConflictOfInterestState** (State)
4. **PublicSafetyRiskState** (State)

### ✅ **Individuals in proethica-case-18**
**URL**: http://localhost:5003/ontology/proethica-case-18

**5 Individuals Successfully Stored**:
1. **DrinkingWater_LeadStandards** - instance of WaterQualityStandards
2. **EngineerB_PublicHealthRisk_Letter** - instance of TechnicalEvaluationReport
3. **EngineerB_WaterSource_EvaluationReport** - instance of TechnicalEvaluationReport
4. **StateEnv_WaterSourceApproval** - instance of LegalResource
5. **XYZ_InsufficientInformation_Report** - instance of TechnicalEvaluationReport

## How to View Entities

### 1. **Main Ontologies List** (http://localhost:5003/)
- Shows both `proethica-intermediate-extracted` and `proethica-case-18` in the list
- Click on either to see details

### 2. **Extracted Classes View** (http://localhost:5003/ontology/proethica-intermediate-extracted)
Shows:
- **Entity Statistics**: 4 Classes, 0 Properties, 0 Individuals
- **Classes Section**: Lists all 4 classes with their definitions
- **Visualization**: Click "Visualize" button to see graph

### 3. **Case Individuals View** (http://localhost:5003/ontology/proethica-case-18)
Shows:
- **Entity Statistics**: 0 Classes, 0 Properties, 5 Individuals
- **Individuals Section**: Lists all 5 individuals
- **Content View**: Click "View Content" to see raw TTL

### 4. **Visualization Options**
- **Graph View**: http://localhost:5003/editor/ontology/proethica-intermediate-extracted/visualize
- **Content View**: http://localhost:5003/ontology/proethica-case-18/content

## Technical Details

### Database Verification
```sql
-- Check classes
SELECT label, entity_type FROM ontology_entities
WHERE ontology_id = (SELECT id FROM ontologies WHERE name = 'proethica-intermediate-extracted');

-- Check individuals
SELECT label, entity_type, parent_uri FROM ontology_entities
WHERE ontology_id = (SELECT id FROM ontologies WHERE name = 'proethica-case-18');
```

### API Endpoints
- **Classes API**: http://localhost:5003/api/ontology/proethica-intermediate-extracted
  - Returns: `{"entity_counts": {"classes": 4, "properties": 0, "individuals": 0}}`

- **Individuals API**: http://localhost:5003/api/ontology/proethica-case-18
  - Returns: `{"entity_counts": {"classes": 0, "properties": 0, "individuals": 5}}`

## Cumulative Addition Confirmed

### How It Works
1. **New extractions ADD to existing entities** - they don't replace them
2. **Classes accumulate** in proethica-intermediate-extracted.ttl
3. **Individuals accumulate** in proethica-case-N.ttl files
4. **Database synchronization** happens automatically after each commit

### Test Results
- Started with 2 Resource classes
- Added 2 State classes
- Result: 4 total classes in proethica-intermediate-extracted
- All properly visible in web interface

## Troubleshooting

If entities don't appear in the web interface:

1. **Refresh entity extraction**:
```bash
cd /home/chris/onto/OntServe
python scripts/refresh_entity_extraction.py proethica-intermediate-extracted
python scripts/refresh_entity_extraction.py proethica-case-18
```

2. **Check database directly**:
```bash
export PGPASSWORD=PASS
psql -h localhost -U postgres -d ontserve -c "SELECT name, entity_type, COUNT(*) FROM ontology_entities GROUP BY name, entity_type;"
```

3. **Verify TTL files exist**:
```bash
ls -la /home/chris/onto/OntServe/ontologies/proethica-*.ttl
```

## Summary
✅ Both classes and individuals are successfully stored and visible in OntServe
✅ Cumulative addition works - new entities are added without removing existing ones
✅ ProEthica commit workflow properly separates classes and individuals
✅ OntServe web interface displays all entities correctly at http://localhost:5003/