# Ontology Alignment Strategy for Guidelines

## Overview
This document outlines the strategy for aligning extracted guideline concepts with the engineering-ethics ontology, identifying gaps, and proposing new terms.

## Ontology Structure Review

### ProEthica Intermediate Ontology Hierarchy
```
Thing (BFO:Entity)
├── Continuant
│   ├── IndependentContinuant
│   │   ├── MaterialEntity
│   │   │   ├── Agent (Person/Organization)
│   │   │   └── Resource
│   │   └── Role
│   └── DependentContinuant
│       ├── Quality
│       │   ├── Capability
│       │   └── Condition
│       └── Disposition
│           └── Principle
└── Occurrent
    ├── Process
    │   ├── Action
    │   └── Event
    └── TemporalRegion
```

### Engineering Ethics Extensions
- **Roles**: Engineer, Client, Employer, PublicOfficial
- **Principles**: Honesty, Integrity, PublicSafety, Sustainability
- **Obligations**: ProtectPublic, MaintainConfidentiality, AvoidConflicts
- **Actions**: Design, Review, Report, Disclose
- **Conditions**: ConflictOfInterest, SafetyRisk, EthicalDilemma

## Alignment Process

### Step 1: Concept Categorization
```python
def categorize_concept(concept, ontology):
    """Map extracted concept to ontology category"""
    
    # Direct mapping rules
    category_keywords = {
        'Role': ['engineer', 'client', 'employer', 'official'],
        'Principle': ['integrity', 'honesty', 'ethics', 'value'],
        'Obligation': ['must', 'shall', 'required', 'duty'],
        'Action': ['perform', 'execute', 'conduct', 'do'],
        'Condition': ['situation', 'circumstance', 'state'],
        'Resource': ['tool', 'document', 'information'],
        'Capability': ['ability', 'skill', 'competence']
    }
    
    # Semantic similarity matching
    best_category = None
    best_score = 0
    
    for category, examples in ontology.categories.items():
        score = semantic_similarity(concept, examples)
        if score > best_score:
            best_category = category
            best_score = score
    
    return best_category, best_score
```

### Step 2: Hierarchical Placement
```python
def find_ontology_parent(concept, category, ontology):
    """Determine appropriate parent class in ontology"""
    
    # Get all classes in category
    category_classes = ontology.get_classes_by_type(category)
    
    # Find most specific parent
    candidates = []
    for cls in category_classes:
        if is_semantically_broader(cls, concept):
            candidates.append({
                'class': cls,
                'specificity': calculate_specificity(cls),
                'similarity': semantic_similarity(cls, concept)
            })
    
    # Return most specific matching parent
    return max(candidates, key=lambda x: x['specificity'])
```

### Step 3: Gap Identification
```python
def identify_ontology_gaps(concepts, ontology):
    """Find concepts not adequately covered by ontology"""
    
    gaps = {
        'missing_classes': [],
        'missing_relationships': [],
        'insufficient_coverage': []
    }
    
    for concept in concepts:
        # Check class coverage
        matches = ontology.find_similar_classes(concept)
        if not matches or max(matches.scores) < 0.7:
            gaps['missing_classes'].append({
                'concept': concept,
                'suggested_parent': find_nearest_parent(concept),
                'justification': generate_justification(concept)
            })
        
        # Check relationship coverage
        for rel in concept.relationships:
            if not ontology.has_property(rel.type):
                gaps['missing_relationships'].append(rel)
    
    return gaps
```

## New Term Identification Criteria

### 1. Novelty Assessment
- **Semantic Distance**: > 0.3 from nearest ontology term
- **Conceptual Uniqueness**: Introduces new aspect not covered
- **Frequency**: Appears multiple times in guideline
- **Context**: Used in distinct contexts

### 2. Relevance Scoring
```python
def score_term_relevance(term, guideline, ontology):
    scores = {
        'frequency': count_occurrences(term, guideline) / len(guideline),
        'centrality': measure_context_importance(term, guideline),
        'novelty': 1.0 - max_similarity_to_ontology(term, ontology),
        'clarity': assess_definition_quality(term.description)
    }
    
    # Weighted average
    weights = {'frequency': 0.2, 'centrality': 0.3, 'novelty': 0.3, 'clarity': 0.2}
    return sum(scores[k] * weights[k] for k in scores)
```

### 3. Integration Readiness
- Has clear definition
- Non-ambiguous scope
- Consistent with ontology principles
- No conflicts with existing terms

## Synchronization Strategy

### Dual Storage Architecture
```
┌─────────────────┐     ┌─────────────────┐
│   TTL Files     │ ←→  │    Database     │
│  (Canonical)    │     │   (Queryable)   │
└─────────────────┘     └─────────────────┘
         ↓                       ↓
    Git Version            API Access
     Control              & UI Display
```

### Synchronization Rules
1. **TTL → Database**: On startup and manual trigger
2. **Database → TTL**: After approved changes
3. **Conflict Resolution**: TTL files are canonical
4. **Version Tracking**: Every sync creates version record

### Implementation
```python
class OntologySynchronizer:
    def sync_ttl_to_db(self):
        """Load TTL files into database"""
        for ttl_file in ontology_files:
            # Parse TTL
            graph = rdflib.Graph()
            graph.parse(ttl_file, format='turtle')
            
            # Extract entities
            entities = extract_entities(graph)
            
            # Update database
            for entity in entities:
                OntologyEntity.upsert(entity)
            
            # Create version record
            OntologyVersion.create(
                file=ttl_file,
                hash=calculate_hash(ttl_file),
                entities_count=len(entities)
            )
    
    def sync_db_to_ttl(self, approved_changes):
        """Export database changes to TTL"""
        # Load current TTL
        graph = load_ontology_graph()
        
        # Apply changes
        for change in approved_changes:
            if change.type == 'new_class':
                add_class_to_graph(graph, change)
            elif change.type == 'new_property':
                add_property_to_graph(graph, change)
        
        # Serialize to TTL
        graph.serialize(destination='engineering-ethics-updated.ttl', 
                       format='turtle')
        
        # Validate
        validate_ontology(graph)
```

## Quality Assurance

### Validation Pipeline
1. **Syntax Validation**: Valid RDF/OWL syntax
2. **Consistency Check**: No logical contradictions
3. **Coverage Analysis**: Ensure key concepts represented
4. **Relationship Integrity**: Valid domain/range constraints

### Review Process
1. **Automated Checks**: Run validation pipeline
2. **Expert Review**: Domain expert approval
3. **Community Feedback**: Stakeholder input
4. **Integration Testing**: Verify case analysis compatibility

## Next Steps
1. Implement categorization algorithm
2. Build hierarchical placement system
3. Create gap analysis reports
4. Design synchronization service
5. Establish review workflow