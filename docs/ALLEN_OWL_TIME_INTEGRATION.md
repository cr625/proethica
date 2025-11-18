# Allen Relations to OWL-Time Integration - Implementation Complete

## Overview

Successfully implemented comprehensive mapping of Allen's Interval Algebra temporal relations to W3C OWL-Time standard properties in ProEthica's Enhanced Temporal Dynamics extraction system.

**Status**: ✅ **COMPLETE** - Ready for production use

## What Was Implemented

### 1. Allen-to-OWL-Time Mapper Module
**File**: `/home/chris/onto/proethica/app/services/temporal_dynamics/utils/allen_owl_time_mapper.py`

Complete mapping system with:
- **13 Allen Relations** mapped to OWL-Time properties
- **Bidirectional mappings** (includes inverse relations)
- **Full URI resolution** for Semantic Web compatibility
- **Human-readable descriptions** for each relation
- **Validation functions** to ensure correct usage

#### Supported Allen Relations

| Allen Relation | OWL-Time Property | Full URI |
|----------------|-------------------|----------|
| `precedes` / `before` | `time:before` | `http://www.w3.org/2006/time#before` |
| `meets` | `time:intervalMeets` | `http://www.w3.org/2006/time#intervalMeets` |
| `overlaps` | `time:intervalOverlaps` | `http://www.w3.org/2006/time#intervalOverlaps` |
| `during` | `time:intervalDuring` | `http://www.w3.org/2006/time#intervalDuring` |
| `starts` | `time:intervalStarts` | `http://www.w3.org/2006/time#intervalStarts` |
| `finishes` | `time:intervalFinishes` | `http://www.w3.org/2006/time#intervalFinishes` |
| `equals` | `time:intervalEquals` | `http://www.w3.org/2006/time#intervalEquals` |
| `contains` | `time:intervalContains` | `http://www.w3.org/2006/time#intervalContains` |
| `after` / `preceded_by` | `time:after` | `http://www.w3.org/2006/time#after` |
| `met_by` | `time:intervalMetBy` | `http://www.w3.org/2006/time#intervalMetBy` |
| `overlapped_by` | `time:intervalOverlappedBy` | `http://www.w3.org/2006/time#intervalOverlappedBy` |
| `started_by` | `time:intervalStartedBy` | `http://www.w3.org/2006/time#intervalStartedBy` |
| `finished_by` | `time:intervalFinishedBy` | `http://www.w3.org/2006/time#intervalFinishedBy` |

### 2. Enhanced RDF Converter
**File**: `/home/chris/onto/proethica/app/services/temporal_dynamics/utils/rdf_converter.py`

Added `convert_allen_relation_to_rdf()` function that:
- Creates RDF entities for Allen relations
- Includes **both** ProEthica custom properties AND OWL-Time standard properties
- Generates proper URIs for entities
- Adds evidence and description metadata
- Makes relations queryable with standard SPARQL temporal queries

#### Example RDF Output

```json
{
  "@context": {
    "proeth": "http://proethica.org/ontology/intermediate#",
    "time": "http://www.w3.org/2006/time#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#"
  },
  "@id": "http://proethica.org/cases/13#AllenRelation_Task_Assignment_precedes_Task_Refusal",
  "@type": "proeth:TemporalRelation",
  "rdfs:label": "Task Assignment precedes Task Refusal",

  "proeth:fromEntity": "Task Assignment to Wasser",
  "proeth:toEntity": "Task Refusal and Memorandum",
  "proeth:allenRelation": "precedes",
  "proeth:owlTimeProperty": "time:before",
  "proeth:owlTimeURI": "http://www.w3.org/2006/time#before",

  "time:before": "http://proethica.org/cases/13#Action_Task_Refusal",

  "proeth:evidence": "Assignment occurred before refusal",
  "proeth:description": "Entity1 ends before Entity2 begins"
}
```

### 3. Storage Integration
**File**: `/home/chris/onto/proethica/app/services/temporal_dynamics/nodes/stage7_storage.py`

Updated to:
- Store Allen relations as separate entities with `entity_type='allen_relations'`
- Process temporal_markers data to extract Allen relations
- Track Allen relation count in progress messages
- Commit Allen relations alongside actions, events, and causal chains

### 4. Review Page Enhancement
**Files**:
- `/home/chris/onto/proethica/app/routes/scenario_pipeline/entity_review.py`
- `/home/chris/onto/proethica/app/templates/entity_review/enhanced_temporal_review.html`

Enhanced review page now displays:
- Allen relation type with human-readable description
- OWL-Time property mapping (e.g., `time:before`)
- Full OWL-Time URI as clickable link
- Evidence text from extraction
- Informational panel explaining Allen algebra and OWL-Time integration

## Architecture Benefits

### 1. Dual Property System
Each Allen relation includes **BOTH**:
- **Custom ProEthica properties** - For internal system use and flexibility
- **OWL-Time standard properties** - For Semantic Web interoperability

This dual approach provides:
- ✅ **Backward compatibility** - Existing ProEthica functionality unchanged
- ✅ **Standards compliance** - Works with OWL-Time reasoners and SPARQL endpoints
- ✅ **Flexibility** - Can add custom properties without breaking standards
- ✅ **Future-proofing** - Ready for Semantic Web integration

### 2. SPARQL Queryability

With OWL-Time properties, you can now query temporal relations using standard SPARQL:

```sparql
PREFIX time: <http://www.w3.org/2006/time#>
PREFIX proeth: <http://proethica.org/ontology/intermediate#>

# Find all actions that precede other actions
SELECT ?action1 ?action2
WHERE {
  ?action1 a proeth:Action .
  ?action2 a proeth:Action .
  ?action1 time:before ?action2 .
}
```

### 3. Reasoner Integration

OWL-Time properties enable:
- **Temporal reasoning** - Infer transitive relations (if A before B, B before C, then A before C)
- **Consistency checking** - Detect impossible temporal orderings
- **Allen algebra operations** - Automatic inverse relation generation

## File Locations

### Implementation Files
```
proethica/app/services/temporal_dynamics/
├── utils/
│   ├── allen_owl_time_mapper.py      # NEW: Allen→OWL-Time mapping system
│   └── rdf_converter.py               # UPDATED: Added convert_allen_relation_to_rdf()
└── nodes/
    └── stage7_storage.py              # UPDATED: Store Allen relations

proethica/app/routes/scenario_pipeline/
└── entity_review.py                   # UPDATED: Fetch Allen relations with OWL-Time data

proethica/app/templates/entity_review/
└── enhanced_temporal_review.html      # UPDATED: Display OWL-Time properties
```

### Documentation
```
proethica/docs/
├── BFO_TEMPORAL_MAPPINGS.md           # Complete BFO + OWL-Time documentation
└── ALLEN_OWL_TIME_INTEGRATION.md      # This document
```

## Usage Example

### Step 1: Extract Temporal Dynamics
Run the Enhanced Temporal Dynamics extraction from Step 3 for any case.

### Step 2: Review Allen Relations
Navigate to: `http://localhost:5000/scenario_pipeline/case/{case_id}/enhanced_temporal/review`

The Allen Relations card will show:
- Allen relation name (e.g., "precedes")
- Human-readable description
- Mapped OWL-Time property (`time:before`)
- Full OWL-Time URI (clickable link)
- Evidence from case text

### Step 3: Query with SPARQL (Future)
When integrated with a SPARQL endpoint, you can query using standard OWL-Time properties.

## Testing

### Manual Testing
1. ✅ Run extraction on Case 13 (Lawn Irrigation Design)
2. ✅ Verify Allen relations are extracted and stored
3. ✅ Check review page displays OWL-Time properties
4. ✅ Verify RDF JSON-LD includes both custom and OWL-Time properties

### Automated Testing (Future)
Consider adding:
- Unit tests for `allen_owl_time_mapper.py` functions
- Integration tests for RDF conversion
- SPARQL query tests for temporal reasoning

## Performance Impact

**Negligible** - The mapping is a simple dictionary lookup with no external API calls or heavy computation.

## Maintenance

### Adding New Allen Relations
If you need to add custom temporal relations:

1. Add to `ALLEN_TO_OWL_TIME` dict in `allen_owl_time_mapper.py`
2. Add human-readable description to `ALLEN_DESCRIPTIONS`
3. If it's a new OWL-Time property, add to `OWL_TIME_URIS`

### Validation
Use `validate_allen_relation()` function to check if a relation name is recognized.

## Known Limitations

1. **Allen relations are extracted but not automatically inferred** - The system extracts explicit Allen relations from case text but doesn't use a reasoner to infer additional relations (e.g., if A before B and B before C, it doesn't automatically infer A before C).

2. **Temporal consistency checking is basic** - The system checks for simple contradictions but doesn't use full Allen algebra constraint propagation.

3. **Action/Event URI assumption** - The RDF converter assumes entities in Allen relations are Actions or Events. If other entity types are used, the URI generation may need adjustment.

## Future Enhancements

### 1. Temporal Reasoner Integration
Integrate with Pellet, HermiT, or another OWL reasoner to:
- Infer transitive temporal relations
- Detect temporal contradictions
- Generate composition tables for Allen relations

### 2. SPARQL Endpoint
Set up a SPARQL endpoint with OWL-Time support to enable:
- Standard temporal queries
- Integration with external Semantic Web systems
- Federated queries across multiple cases

### 3. Temporal Visualization
Create interactive timeline visualization that:
- Shows Allen relations as graph edges
- Highlights temporal conflicts
- Allows manual adjustment of temporal orderings

### 4. OWL-Time Instant Support
Currently uses intervals. Could add support for:
- `time:Instant` for point-in-time events
- `time:hasBeginning` and `time:hasEnd` for intervals
- `time:inXSDDateTime` for absolute timestamps

## References

### Standards
- **OWL-Time**: https://www.w3.org/TR/owl-time/
- **Allen's Interval Algebra**: Allen, J.F. (1983). "Maintaining knowledge about temporal intervals". Communications of the ACM. 26 (11): 832–843.

### ProEthica Documentation
- [BFO Temporal Mappings](./BFO_TEMPORAL_MAPPINGS.md) - Complete BFO integration documentation
- [Multi-Section Extraction Plan](./MULTI_SECTION_EXTRACTION_PLAN.md) - Overall extraction system architecture

### W3C Specifications
- OWL-Time Ontology: http://www.w3.org/2006/time#
- SPARQL 1.1: https://www.w3.org/TR/sparql11-query/

## Conclusion

**ProEthica's temporal dynamics extraction now fully supports W3C OWL-Time standard properties** for Allen temporal relations. This enables:
- Interoperability with Semantic Web temporal reasoning systems
- Standard SPARQL temporal queries
- Future integration with temporal reasoners
- Proper BFO + OWL-Time compliance

The implementation maintains backward compatibility while adding powerful new capabilities for temporal reasoning and Semantic Web integration.

**Status**: Production-ready ✅
