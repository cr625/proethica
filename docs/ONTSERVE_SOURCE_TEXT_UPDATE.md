# OntServe Update Required: Source Text Provenance Support

**Date:** November 17, 2025
**Status:** ProEthica implementation COMPLETE - OntServe updates PENDING
**Priority:** Medium - Required before re-extracting entities with source text

---

## Summary

ProEthica now extracts and stores **source text provenance** for all 9 concept types across Pass 1-3 entity extraction. Each extracted entity (both classes and individuals) now includes the exact text snippet from the source case where that entity was identified.

OntServe needs to be updated to:
1. Accept and store the new `source_text` field in entity commit requests
2. Preserve `source_text` in RDF graphs when storing entities
3. Return `source_text` when querying entities
4. Display `source_text` in the web visualization interface (optional enhancement)

---

## What Changed in ProEthica

### New RDF Property

**Namespace:** `http://proethica.org/ontology/provenance/`
**Property:** `sourceText`
**Full URI:** `http://proethica.org/ontology/provenance/sourceText`

**Definition:**
```turtle
proeth-prov:sourceText a owl:DatatypeProperty ;
    rdfs:label "Source Text" ;
    rdfs:comment "Exact text snippet from source document where this entity was identified (max 200 characters)" ;
    rdfs:domain owl:Thing ;
    rdfs:range xsd:string .
```

### Affected Entity Types (All 9 Concepts)

**Pass 1: Contextual Framework**
- Roles (classes + individuals)
- States (classes + individuals)
- Resources (classes + individuals)

**Pass 2: Normative Requirements**
- Principles (classes + individuals)
- Obligations (classes + individuals)
- Constraints (classes + individuals)
- Capabilities (classes + individuals)

**Pass 3: Temporal Dynamics**
- Actions (classes + individuals)
- Events (classes + individuals)

---

## Data Structure Changes

### Before (without source_text)
```json
{
  "entity_label": "Engineer",
  "entity_type": "role",
  "storage_type": "class",
  "rdf_json_ld": {
    "@type": ["http://www.w3.org/2002/07/owl#Class"],
    "rdfs:label": "Engineer",
    "rdfs:comment": "Licensed professional engineer",
    "rdfs:subClassOf": "http://proethica.org/ontology/core/Role"
  }
}
```

### After (with source_text)
```json
{
  "entity_label": "Engineer",
  "entity_type": "role",
  "storage_type": "class",
  "rdf_json_ld": {
    "@type": ["http://www.w3.org/2002/07/owl#Class"],
    "rdfs:label": "Engineer",
    "rdfs:comment": "Licensed professional engineer",
    "rdfs:subClassOf": "http://proethica.org/ontology/core/Role",
    "source_text": "Engineer L, a licensed professional engineer, has many years of experience in stormwater control design."
  }
}
```

### RDF Triple Representation
```turtle
# Entity definition
proeth-int:Engineer a owl:Class ;
    rdfs:label "Engineer" ;
    rdfs:comment "Licensed professional engineer" ;
    rdfs:subClassOf proeth-core:Role ;
    proeth-prov:sourceText "Engineer L, a licensed professional engineer, has many years of experience in stormwater control design." .
```

---

## Example Data from ProEthica

### Role Class Example
```json
{
  "entity_label": "Stormwater Control Design Specialist",
  "entity_type": "role",
  "storage_type": "class",
  "rdf_json_ld": {
    "@type": ["http://www.w3.org/2002/07/owl#Class"],
    "rdfs:label": "Stormwater Control Design Specialist",
    "rdfs:comment": "Professional who designs stormwater management systems",
    "rdfs:subClassOf": "http://proethica.org/ontology/core/Role",
    "source_text": "Engineer L is contracted by Client X to design a stormwater management system"
  }
}
```

### Obligation Individual Example
```json
{
  "entity_label": "Hold paramount public safety",
  "entity_type": "obligation",
  "storage_type": "individual",
  "rdf_json_ld": {
    "@type": ["http://www.w3.org/2002/07/owl#NamedIndividual"],
    "rdf:type": ["http://proethica.org/ontology/core/ProfessionalObligation"],
    "rdfs:label": "Hold paramount public safety",
    "proeth:obligationType": "paramount_duty",
    "proeth:bindingForce": "mandatory",
    "source_text": "Engineers shall hold paramount the safety, health, and welfare of the public"
  }
}
```

### Action Individual Example
```json
{
  "entity_label": "Design stormwater system",
  "entity_type": "action",
  "storage_type": "individual",
  "rdf_json_ld": {
    "@type": ["http://www.w3.org/2002/07/owl#NamedIndividual"],
    "rdf:type": ["http://proethica.org/ontology/core/Action"],
    "rdfs:label": "Design stormwater system",
    "proeth:performedBy": "Engineer L",
    "proeth:temporalInterval": "Before flood event",
    "source_text": "Engineer L designed a stormwater management system for the commercial development site"
  }
}
```

---

## Required OntServe Changes

### 1. MCP Server (`servers/mcp_server.py`)

**Commit Entities Endpoint** - Must accept `source_text` in entity data:

```python
# Current behavior (needs update)
async def commit_entities(self, entities: List[Dict]) -> Dict:
    """Commit entities to permanent storage"""
    # Extract entity data
    for entity in entities:
        rdf_json = entity.get('rdf_json_ld', {})
        # Need to preserve source_text if present
        source_text = rdf_json.get('source_text')
```

**Expected Input Format:**
```json
{
  "entities": [
    {
      "entity_label": "Engineer",
      "entity_type": "role",
      "storage_type": "class",
      "rdf_json_ld": {
        "source_text": "Engineer L, a licensed professional engineer..."
      }
    }
  ],
  "case_id": 8,
  "ontology": "proethica-case-8"
}
```

### 2. Storage Layer (`storage/rdf_storage.py`)

**Add Source Text Triple** - When storing entities:

```python
def add_entity(self, entity_uri, entity_data):
    """Add entity to RDF graph"""
    # ... existing code ...

    # NEW: Add source text if present
    if 'source_text' in entity_data and entity_data['source_text']:
        self.graph.add((
            entity_uri,
            URIRef('http://proethica.org/ontology/provenance/sourceText'),
            Literal(entity_data['source_text'], datatype=XSD.string)
        ))
```

### 3. Query/Retrieval Layer

**Return Source Text** - When querying entities:

```python
def get_entity_details(self, entity_uri):
    """Get complete entity details including source text"""
    details = {}

    # ... existing code to get label, comment, etc. ...

    # NEW: Query source text
    source_text_query = """
        SELECT ?sourceText WHERE {
            <%s> <http://proethica.org/ontology/provenance/sourceText> ?sourceText .
        }
    """ % entity_uri

    results = self.graph.query(source_text_query)
    if results:
        details['source_text'] = str(list(results)[0][0])

    return details
```

### 4. Web Visualization (Optional Enhancement)

**Display Source Text** in entity detail views:

```html
<!-- Entity detail view -->
<div class="entity-details">
    <h3>{{ entity.label }}</h3>
    <p class="definition">{{ entity.comment }}</p>

    <!-- NEW: Source text display -->
    {% if entity.source_text %}
    <div class="source-provenance">
        <h4>Source Context</h4>
        <blockquote class="source-quote">
            <i class="fa fa-quote-left"></i>
            {{ entity.source_text }}
        </blockquote>
    </div>
    {% endif %}
</div>
```

---

## Implementation Priority

**Phase 1: Core Functionality (REQUIRED)**
1. ✅ Accept `source_text` in commit entity requests (don't reject it)
2. ✅ Store `source_text` as RDF triple using `proeth-prov:sourceText`
3. ✅ Return `source_text` in entity query responses

**Phase 2: Enhancement (OPTIONAL)**
1. Display `source_text` in web visualization
2. Add SPARQL query support for searching by source text
3. Add provenance validation (ensure source_text length ≤ 200 chars)

---

## Testing Data

**Test Case:** Extract Pass 1 entities from Case 8 with source text

**Expected Commits:**
- 3 Role classes with source_text
- 12 Role individuals with source_text
- 2 State classes with source_text
- 8 State individuals with source_text
- 2 Resource classes with source_text
- 6 Resource individuals with source_text

**Verification Query:**
```sparql
# Count entities with source text
SELECT (COUNT(?entity) as ?count) WHERE {
    ?entity <http://proethica.org/ontology/provenance/sourceText> ?sourceText .
}
```

---

## Backward Compatibility

**CRITICAL:** OntServe must maintain backward compatibility:

1. **Accept entities without source_text** - Older entities won't have this field
2. **Don't require source_text** - It's an optional provenance enhancement
3. **Return null/empty** - If source_text not present, return `null` or omit field

**Example Query Response (backward compatible):**
```json
{
  "entities": [
    {
      "uri": "http://proethica.org/ontology/intermediate/Engineer",
      "label": "Engineer",
      "comment": "Licensed professional engineer",
      "source_text": "Engineer L, a licensed professional..."  // NEW - may be null
    },
    {
      "uri": "http://proethica.org/ontology/intermediate/Client",
      "label": "Client",
      "comment": "Entity that contracts engineering services",
      "source_text": null  // OLD entity - no source text
    }
  ]
}
```

---

## Questions for OntServe Team

1. **Storage Location:** Should `source_text` be stored in the main ontology graph or in a separate provenance graph?
2. **Versioning:** Do we need to version source_text (track changes if entity is re-extracted)?
3. **Search:** Should source_text be indexed for full-text search?
4. **Validation:** Should we validate max length (200 chars) or accept any length?
5. **Display:** Priority for web UI enhancement to display source_text?

---

## Related Documentation

- **ProEthica Implementation:** See `PROGRESS.md` Section 9
- **RDF Converter:** `app/services/rdf_extraction_converter.py`
- **Extractor Examples:** `app/services/extraction/dual_role_extractor.py` (lines 267-270)
- **Template Display:** `app/templates/scenarios/entity_review.html` (lines 429-432)
- **Integration Guide:** `docs/PROETHICA_ONTSERVE_INTEGRATION.md`

---

## Contact

**ProEthica Status:** Source text extraction COMPLETE - ready to commit entities
**Next Step:** Update OntServe to accept and store source_text field
**Timeline:** Required before re-running entity extraction on all cases

**Questions?** See integration documentation or check ProEthica commit history (commits 31-36)
