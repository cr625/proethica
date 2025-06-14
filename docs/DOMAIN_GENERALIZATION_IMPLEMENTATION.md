# Domain Generalization Implementation Plan

## Overview
Transform ProEthica's ontology functionality into a generic, domain-agnostic system while maintaining all current engineering ethics capabilities.

## Implementation Phases

### Phase 1: Abstract Current Implementation ⏳
**Goal**: Create generic interfaces from existing code while maintaining backward compatibility

#### Tasks:
- [ ] Create base adapter interfaces
  - [ ] `base/domain_adapter.py` - Abstract base for all domain logic
  - [ ] `base/document_processor.py` - Generic document processing interface
  - [ ] `base/ontology_mapper.py` - Ontology alignment interface
  - [ ] `base/concept_extractor.py` - Term extraction interface

- [ ] Refactor engineering-specific logic
  - [ ] Move NSPE-specific code to `adapters/engineering/`
  - [ ] Create `engineering_adapter.py` implementing all interfaces
  - [ ] Extract engineering patterns to `patterns.py`
  - [ ] Create `config.yaml` for engineering domain

- [ ] Update existing services
  - [ ] Make `GuidelineAnalysisService` domain-agnostic
  - [ ] Update `CaseDeconstructionService` to use new adapter pattern
  - [ ] Modify `OntologyService` for multi-domain support

### Phase 2: Build Framework 🔨
**Goal**: Implement core framework components

#### Tasks:
- [ ] Domain registration system
  - [ ] Create `DomainRegistry` class
  - [ ] Implement dynamic adapter loading
  - [ ] Add domain validation

- [ ] Configuration management
  - [ ] Design domain configuration schema
  - [ ] Create configuration loader
  - [ ] Implement configuration validation

- [ ] Generic document types
  - [ ] Replace "guidelines" with "master documents"
  - [ ] Replace "cases" with "analysis documents"
  - [ ] Update database models

- [ ] Enhanced World/Domain Collection
  - [ ] Refactor `World` model to `DomainCollection`
  - [ ] Add adapter type field
  - [ ] Update relationships

### Phase 3: Test with New Domain 🧪
**Goal**: Validate generic pipeline with second domain

#### Tasks:
- [ ] Create medical ethics adapter
  - [ ] `adapters/medical/adapter.py`
  - [ ] Medical-specific patterns
  - [ ] Configuration file

- [ ] Test end-to-end workflow
  - [ ] Upload medical guidelines as master document
  - [ ] Extract medical concepts
  - [ ] Process medical cases
  - [ ] Generate medical scenarios

- [ ] Refine abstractions
  - [ ] Identify missing generic functionality
  - [ ] Update base interfaces
  - [ ] Document learnings

### Phase 4: Enhanced Features 🚀
**Goal**: Add advanced multi-domain capabilities

#### Tasks:
- [ ] Cross-domain concept mapping
  - [ ] Implement concept similarity service
  - [ ] Create mapping interface
  - [ ] Build visualization tools

- [ ] Transfer learning
  - [ ] Design knowledge transfer mechanism
  - [ ] Implement concept suggestion system
  - [ ] Create domain templates

- [ ] Plugin architecture
  - [ ] Design plugin interface
  - [ ] Implement hot-loading
  - [ ] Create plugin documentation

## Technical Components

### 1. Domain Adapter Structure
```
/adapters/
├── base/
│   ├── __init__.py
│   ├── domain_adapter.py      # Abstract base class
│   ├── document_processor.py  # Document processing interface
│   ├── ontology_mapper.py     # Ontology alignment
│   └── concept_extractor.py   # Concept extraction
├── engineering/
│   ├── __init__.py
│   ├── adapter.py            # Engineering implementation
│   ├── config.yaml          # Domain configuration
│   └── patterns.py          # NSPE-specific patterns
└── medical/                 # Example new domain
    ├── __init__.py
    ├── adapter.py
    ├── config.yaml
    └── patterns.py
```

### 2. Key Interfaces

#### DomainAdapter
```python
class DomainAdapter(ABC):
    @abstractmethod
    def process_master_document(self, document: Document) -> List[Concept]
    
    @abstractmethod
    def extract_concepts(self, text: str) -> List[Concept]
    
    @abstractmethod
    def analyze_document(self, document: Document, concepts: List[Concept]) -> Analysis
    
    @abstractmethod
    def generate_scenario(self, analysis: Analysis) -> Scenario
```

#### DomainCollection (formerly World)
```python
class DomainCollection:
    name: str
    adapter_type: str
    master_document: Document
    ontology: Ontology
    concept_mappings: List[ConceptMapping]
    analysis_documents: List[Document]
    metadata: Dict
```

### 3. Configuration Schema
```yaml
domain:
  name: "Domain Name"
  type: "domain_type"
  version: "1.0"

document_types:
  master:
    name: "Master Document Type"
    sections: ["section1", "section2"]
  analysis:
    name: "Analysis Document Type"
    sections: ["section1", "section2"]

concept_extraction:
  patterns:
    - type: "concept_type"
      keywords: ["keyword1", "keyword2"]
      
ontology_alignment:
  namespace: "http://example.org/ontology#"
  mappings:
    "term1": "onto:Concept1"
```

## Migration Strategy

### Database Changes
- Add `adapter_type` to World model
- Rename guideline references to master_document
- Update case references to analysis_document
- Maintain backward compatibility with views

### API Changes
- Create generic endpoints alongside existing ones
- Deprecate domain-specific endpoints over time
- Maintain backward compatibility

### UI Updates
- Update terminology in templates
- Make UI elements configurable by domain
- Create domain selection interface

## Success Criteria
- [ ] All existing engineering ethics functionality works unchanged
- [ ] Can add new domain without code changes to core
- [ ] Generic interfaces cover all domain needs
- [ ] Performance remains comparable
- [ ] Documentation updated for generic system

## Timeline
- **Phase 1**: 2 weeks
- **Phase 2**: 3 weeks
- **Phase 3**: 2 weeks
- **Phase 4**: 3 weeks

Total: ~10 weeks

## Risks and Mitigations
1. **Risk**: Breaking existing functionality
   - **Mitigation**: Comprehensive test coverage before refactoring

2. **Risk**: Over-abstraction making system complex
   - **Mitigation**: Start with minimal abstraction, iterate

3. **Risk**: Performance degradation
   - **Mitigation**: Benchmark before and after changes

4. **Risk**: Domain differences too large
   - **Mitigation**: Prototype with very different domain early

## Notes
- Maintain backward compatibility throughout
- Document all breaking changes
- Create migration guides for each phase
- Keep engineering ethics as reference implementation