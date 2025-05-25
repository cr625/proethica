# Guidelines Enhancement Action Plan

## Executive Summary
Transform the guidelines component from basic concept extraction to a comprehensive ontology-aware system that identifies new engineering ethics terms and creates rich semantic relationships for case analysis.

## Goals
1. **Extract all ontology-relevant terms** from guidelines (Roles, Principles, Obligations, etc.)
2. **Identify new engineering ethics terms** not yet in the ontology
3. **Generate rich RDF triples** with semantic relationships
4. **Enable ontology expansion** through approved new terms
5. **Maintain synchronization** between TTL files and database

## Implementation Phases

### Phase 1: Foundation Enhancement (Week 1-2)

#### 1.1 Ontology Service Improvements
```python
# Create comprehensive ontology index
class OntologyIndexService:
    def __init__(self):
        self.load_engineering_ethics_ontology()
        self.create_embeddings_index()
        self.build_hierarchy_map()
    
    def find_similar_terms(self, concept, threshold=0.7):
        # Semantic similarity search
        
    def suggest_parent_class(self, concept):
        # Hierarchical placement
```

#### 1.2 Database Schema Updates
```sql
-- New term candidates table
CREATE TABLE guideline_term_candidates (
    id SERIAL PRIMARY KEY,
    guideline_id INTEGER REFERENCES guidelines(id),
    term_label VARCHAR(255),
    term_uri VARCHAR(255),
    category VARCHAR(50),
    parent_class_uri VARCHAR(255),
    definition TEXT,
    confidence FLOAT,
    is_existing BOOLEAN,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Enhanced guideline triples
CREATE TABLE guideline_semantic_triples (
    id SERIAL PRIMARY KEY,
    guideline_id INTEGER REFERENCES guidelines(id),
    subject_uri VARCHAR(255),
    predicate VARCHAR(255),
    object_uri VARCHAR(255),
    confidence FLOAT,
    inference_type VARCHAR(50), -- 'explicit', 'pattern', 'llm'
    explanation TEXT
);
```

### Phase 2: Enhanced Extraction (Week 3-4)

#### 2.1 Ontology-Aware Concept Extraction
```python
class EnhancedGuidelineAnalysisService:
    def extract_concepts_with_ontology(self, guideline_text):
        # Step 1: Extract with category focus
        prompt = f"""
        Extract concepts focusing on these ontology categories:
        - Roles (professional positions)
        - Principles (ethical values)  
        - Obligations (duties, requirements)
        - Conditions (circumstances, constraints)
        - Resources (tools, documents)
        - Actions (activities, processes)
        - Events (occurrences)
        - Capabilities (skills, competencies)
        
        For each concept, identify if it matches existing terms:
        {self.get_ontology_examples()}
        """
        
        # Step 2: Classify as existing or new
        concepts = llm_extract(prompt)
        enriched = self.classify_concepts(concepts)
        
        return enriched
```

#### 2.2 New Term Detection
```python
def identify_new_terms(concepts, ontology):
    new_terms = []
    
    for concept in concepts:
        # Check similarity to existing terms
        matches = ontology.find_similar(concept)
        
        if max(matches.scores) < 0.75:
            new_term = {
                'label': concept.label,
                'uri': generate_uri(concept),
                'category': concept.category,
                'definition': concept.description,
                'parent_suggestion': ontology.suggest_parent(concept),
                'confidence': concept.confidence,
                'justification': f"No close match in ontology (best: {max(matches.scores)})"
            }
            new_terms.append(new_term)
    
    return new_terms
```

### Phase 3: Rich Triple Generation (Week 5-6)

#### 3.1 Semantic Relationship Discovery
```python
def generate_semantic_triples(concepts, guideline_context):
    triples = []
    
    # Relationship patterns
    patterns = {
        'requires': ['necessary for', 'prerequisite', 'required'],
        'enables': ['allows', 'facilitates', 'permits'],
        'guides': ['directs', 'governs', 'informs'],
        'conflictsWith': ['incompatible', 'opposes', 'contradicts']
    }
    
    # Generate triples
    for concept in concepts:
        # Basic classification triples
        triples.extend(generate_basic_triples(concept))
        
        # Semantic relationships
        for other in concepts:
            if concept != other:
                rel = infer_relationship(concept, other, patterns, guideline_context)
                if rel:
                    triples.append({
                        'subject': concept.uri,
                        'predicate': rel.type,
                        'object': other.uri,
                        'confidence': rel.confidence,
                        'explanation': rel.reasoning
                    })
    
    return triples
```

#### 3.2 Guideline-Specific Triples
```turtle
# Guideline defines concepts
:guideline_190 proethica:defines proethica:ProfessionalIntegrity ;
    proethica:emphasizes proethica:PublicSafety ;
    proethica:introduces proethica:EnvironmentalStewardship ;
    proethica:appliesTo proethica:Engineer .

# Guideline sections relate to concepts
:guideline_190_section_1 proethica:discusses proethica:Honesty ;
    proethica:providesExampleOf proethica:EthicalDilemma .
```

### Phase 4: Review Interface (Week 7-8)

#### 4.1 Term Review UI
```html
<!-- New Term Candidate Review -->
<div class="term-candidate">
    <h4>{{ term.label }} <span class="badge new">New Term</span></h4>
    <p>{{ term.definition }}</p>
    
    <div class="ontology-placement">
        <label>Suggested Parent:</label>
        <select name="parent_class">
            <option value="{{ term.parent_suggestion.uri }}">
                {{ term.parent_suggestion.label }} ({{ term.confidence }}%)
            </option>
            <!-- Other options -->
        </select>
    </div>
    
    <div class="actions">
        <button class="approve">Add to Ontology</button>
        <button class="reject">Reject</button>
        <button class="defer">Review Later</button>
    </div>
</div>
```

#### 4.2 Triple Validation Interface
- Show inferred relationships with explanations
- Allow confidence threshold filtering
- Enable batch approval/rejection
- Export approved triples to TTL

### Phase 5: Integration (Week 9-10)

#### 5.1 Ontology Synchronization
```python
class OntologySyncService:
    def sync_approved_terms(self, approved_terms):
        # Update database
        for term in approved_terms:
            OntologyEntity.create(term)
        
        # Update TTL file
        graph = self.load_ontology()
        for term in approved_terms:
            self.add_to_graph(graph, term)
        
        # Validate and save
        if self.validate_ontology(graph):
            graph.serialize('engineering-ethics-updated.ttl', format='turtle')
            self.create_version_record()
```

#### 5.2 Case Analysis Integration
- Link guidelines to cases through world association
- Use guideline concepts for case semantic parsing
- Apply guideline triples to case analysis
- Enable cross-reference between cases and guidelines

## Success Metrics

### Quantitative
- **Concept Coverage**: 95% of guideline concepts mapped
- **New Terms**: 15-25 new terms per guideline
- **Relationships**: 5+ semantic relationships per concept
- **Processing Time**: < 2 minutes per guideline

### Qualitative
- **Accuracy**: Domain expert validation > 85%
- **Usability**: User satisfaction > 4/5
- **Integration**: Seamless case analysis enhancement
- **Maintainability**: Clear ontology evolution path

## Technical Requirements

### LLM Integration
- Claude API with native tool support
- OpenAI API as fallback
- Token optimization for large guidelines
- Response caching for efficiency

### Infrastructure
- PostgreSQL with pgvector
- Redis for caching
- Background job processing
- File storage for TTL versions

### Development Tools
- Python 3.11+
- RDFLib for triple processing
- SQLAlchemy for database
- pytest for testing

## Risk Mitigation

### Technical Risks
- **LLM API Limits**: Implement chunking and caching
- **Ontology Conflicts**: Validation pipeline and rollback
- **Performance**: Database indexing and query optimization
- **Data Loss**: Version control and backups

### Process Risks
- **Scope Creep**: Strict phase boundaries
- **Quality Control**: Automated testing and expert review
- **User Adoption**: Intuitive UI and documentation
- **Integration Issues**: Modular architecture

## Next Steps

### Immediate (This Week)
1. Set up enhanced database schema
2. Create ontology index service
3. Implement similarity search
4. Begin enhanced extraction

### Short Term (Next Month)
1. Complete extraction enhancements
2. Build triple generation system
3. Create review interface
4. Test with Guideline 190

### Long Term (Quarter)
1. Full production deployment
2. Process multiple guidelines
3. Ontology version release
4. Case analysis integration

## Conclusion
This plan transforms the guidelines component into a sophisticated ontology management system that will significantly enhance the semantic richness of case analysis while expanding the engineering ethics ontology with domain-specific terms.