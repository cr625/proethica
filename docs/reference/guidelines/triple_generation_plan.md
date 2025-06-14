# Enhanced Triple Generation Plan for Guidelines

## Objective
Transform the current basic triple generation into a comprehensive system that:
1. Extracts engineering-ethics ontology terms from guidelines
2. Identifies new terms not yet in the ontology
3. Creates rich semantic relationships
4. Enables ontology expansion

## Current State Analysis

### What Works
- Basic triple generation (type, label, description)
- Category-based relationship inference
- URI generation using namespace + slugified labels
- JSON and Turtle format support

### What's Missing
- Deep ontology alignment
- Discovery of implicit relationships
- New term identification for ontology expansion
- Instance vs. class distinction
- Confidence scoring

## Enhanced Triple Generation Architecture

### Phase 1: Ontology-Aware Extraction

#### 1.1 Pre-Processing
```python
# Load engineering-ethics ontology terms
ontology_terms = {
    'Roles': ['Engineer', 'Client', 'PublicOfficial', ...],
    'Principles': ['Honesty', 'Integrity', 'PublicSafety', ...],
    'Obligations': ['ProtectPublic', 'MaintainConfidentiality', ...],
    'Actions': ['Design', 'Review', 'Approve', ...],
    # etc.
}

# Create embedding index for semantic search
ontology_embeddings = create_embeddings(ontology_terms)
```

#### 1.2 Enhanced Concept Extraction
```python
def extract_concepts_with_ontology(guideline_text):
    # Step 1: Initial extraction with LLM
    raw_concepts = llm_extract_concepts(guideline_text)
    
    # Step 2: Match to existing ontology
    for concept in raw_concepts:
        # Find similar ontology terms
        matches = semantic_search(concept, ontology_embeddings)
        
        # Classify as existing or new
        if max(matches.scores) > 0.85:
            concept['ontology_match'] = matches[0]
            concept['is_new'] = False
        else:
            concept['is_new'] = True
            concept['suggested_parent'] = find_best_parent(concept)
    
    return concepts
```

### Phase 2: Rich Triple Generation

#### 2.1 Triple Categories

**1. Class-Level Triples (General)**
```turtle
# Existing ontology term
proethica:ProfessionalIntegrity a owl:Class ;
    rdfs:subClassOf proethica:Principle ;
    rdfs:label "Professional Integrity" ;
    rdfs:comment "The principle of maintaining..." .

# New term candidate
proethica:EnvironmentalStewardship a owl:Class ;
    rdfs:subClassOf proethica:Obligation ;
    rdfs:label "Environmental Stewardship" ;
    proethica:isNewTerm true ;
    proethica:sourceGuideline :guideline_190 .
```

**2. Relationship Triples**
```turtle
# Domain-specific relationships
proethica:Engineer proethica:hasObligation proethica:ProtectPublicSafety .
proethica:DesignAction proethica:requires proethica:TechnicalCompetence .
proethica:ConflictOfInterest proethica:threatens proethica:ProfessionalIntegrity .
```

**3. Guideline Association Triples**
```turtle
:guideline_190 proethica:defines proethica:ProfessionalIntegrity ;
    proethica:emphasizes proethica:PublicSafety ;
    proethica:introduces proethica:EnvironmentalStewardship .
```

#### 2.2 Relationship Discovery Algorithm
```python
def discover_relationships(concepts, ontology):
    relationships = []
    
    # Pattern-based discovery
    patterns = {
        'requires': ['necessary for', 'required to', 'must have'],
        'enables': ['allows', 'permits', 'makes possible'],
        'conflicts_with': ['incompatible with', 'opposes', 'contradicts'],
        'guides': ['directs', 'governs', 'regulates']
    }
    
    # LLM-enhanced discovery
    for c1, c2 in concept_pairs(concepts):
        # Check text references for patterns
        rel = find_pattern_relationship(c1, c2, patterns)
        
        # Use LLM for semantic relationship inference
        if not rel:
            rel = llm_infer_relationship(c1, c2, context=guideline_text)
        
        if rel:
            relationships.append({
                'subject': c1,
                'predicate': rel,
                'object': c2,
                'confidence': calculate_confidence(rel)
            })
    
    return relationships
```

### Phase 3: Ontology Integration

#### 3.1 New Term Processing
```python
def process_new_terms(new_concepts):
    candidates = []
    
    for concept in new_concepts:
        # Generate proposed ontology entry
        entry = {
            'uri': generate_uri(concept),
            'type': map_to_owl_class(concept.category),
            'parent': concept.suggested_parent,
            'label': concept.label,
            'definition': concept.description,
            'source': concept.guideline_id,
            'confidence': concept.extraction_confidence
        }
        
        # Check for conflicts
        conflicts = check_ontology_conflicts(entry)
        if conflicts:
            entry['conflicts'] = conflicts
            entry['requires_review'] = True
        
        candidates.append(entry)
    
    return candidates
```

#### 3.2 Review Interface Requirements
- Display existing vs. new terms differently
- Show confidence scores
- Highlight potential conflicts
- Allow editing before saving
- Batch approval/rejection
- Export to ontology format

### Phase 4: Implementation Plan

#### 4.1 Database Schema Updates
```sql
-- Track new term candidates
CREATE TABLE ontology_candidates (
    id SERIAL PRIMARY KEY,
    uri VARCHAR(255) UNIQUE,
    label VARCHAR(255),
    parent_uri VARCHAR(255),
    definition TEXT,
    category VARCHAR(50),
    source_guideline_id INTEGER,
    confidence FLOAT,
    status VARCHAR(20), -- 'pending', 'approved', 'rejected'
    created_at TIMESTAMP
);

-- Enhanced triple storage
CREATE TABLE guideline_triples (
    id SERIAL PRIMARY KEY,
    guideline_id INTEGER,
    subject_uri VARCHAR(255),
    predicate_uri VARCHAR(255),
    object_uri VARCHAR(255),
    confidence FLOAT,
    is_inferred BOOLEAN,
    explanation TEXT
);
```

#### 4.2 Service Layer Enhancements
```python
class EnhancedGuidelineAnalysisService:
    def extract_ontology_aligned_concepts(self, guideline_text):
        # Implementation of Phase 1
        
    def generate_rich_triples(self, concepts):
        # Implementation of Phase 2
        
    def identify_new_terms(self, concepts):
        # Implementation of Phase 3.1
        
    def save_to_ontology(self, approved_terms):
        # Sync to both database and TTL file
```

## Success Metrics
1. **Coverage**: 90%+ of guideline concepts mapped to ontology
2. **New Terms**: 10-20 new engineering ethics terms per guideline
3. **Relationships**: 5+ semantic relationships per concept
4. **Accuracy**: 85%+ validation accuracy on manual review

## Timeline
- **Week 1-2**: Implement ontology-aware extraction
- **Week 3-4**: Build rich triple generation
- **Week 5-6**: Create review interface
- **Week 7-8**: Testing and refinement

## Next Steps
1. Set up ontology embedding index
2. Implement enhanced extraction service
3. Create new term candidate table
4. Build review interface
5. Test with Guideline 190 (NSPE Code)