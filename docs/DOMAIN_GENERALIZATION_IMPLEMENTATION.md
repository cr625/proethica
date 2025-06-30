# Domain Generalization Implementation Plan

## Overview
Transform ProEthica from an engineering ethics system into a generic domain-agnostic framework while maintaining all current functionality. The analysis reveals ProEthica already has excellent architectural foundations for this transformation.

## 🎯 Key Discovery
**ProEthica is surprisingly well-architected for domain generalization!** The existing adapter pattern, modular services, flexible data models, and MCP architecture provide an excellent foundation. This is an **enhancement project**, not a major refactoring.

## Current Architecture Strengths
✅ **Adapter Pattern**: `BaseCaseDeconstructionAdapter` with `EngineeringEthicsAdapter` implementation  
✅ **Modular Services**: Base classes, pipeline system, pluggable MCP modules  
✅ **Flexible Data Models**: `World` model supports multiple domains with JSON metadata  
✅ **Configuration Infrastructure**: `ModelConfig` with environment-specific settings  
✅ **Processing Pipeline**: Generic `PipelineManager` with `BaseStep` interface  
✅ **MCP Architecture**: Production-ready modular system in `/mcp/modules/`  

## Implementation Phases

### Phase 1: Domain Registry & Factory System 🏗️
**Goal**: Create coordination layer for existing components while maintaining backward compatibility

#### High Impact Tasks:
- [ ] Create domain registry system
  - [ ] `app/services/domain_registry.py` - Central domain management
  - [ ] `app/models/domain_config.py` - Standardized domain configuration
  - [ ] `app/services/domain_factory.py` - Factory for domain-specific components
  - [ ] `config/domains/` - Directory for domain configuration files

- [ ] Enhance adapter factory
  - [ ] `app/services/case_deconstruction/adapter_factory.py` - Multi-domain adapter creation
  - [ ] `app/services/case_deconstruction/domain_adapters/` - Domain-specific adapters directory
  - [ ] Auto-discovery of adapter classes

- [ ] Create engineering domain configuration
  - [ ] `config/domains/engineering.yaml` - Engineering ethics configuration
  - [ ] Extract NSPE-specific patterns from existing code
  - [ ] Document existing adapter interface

### Phase 2: Extend Processing Pipeline 🔨
**Goal**: Make document processing pipeline domain-agnostic

#### Medium Impact Tasks:
- [ ] Generic extraction strategies
  - [ ] `app/services/case_processing/extraction_strategies/` - Domain-specific extraction
  - [ ] `app/services/case_processing/domain_validators/` - Domain validation rules
  - [ ] Abstract base extraction strategy class

- [ ] Enhance pipeline steps
  - [ ] Make `DocumentStructureAnnotationStep` domain-configurable
  - [ ] Create domain-specific section mappers
  - [ ] Add flexible validation rules per domain

- [ ] Configuration-driven processing
  - [ ] Domain-specific extraction patterns
  - [ ] Configurable section structures
  - [ ] Flexible metadata handling

- [ ] Update terminology (optional)
  - [ ] Consider "master documents" vs "guidelines" terminology
  - [ ] Consider "analysis documents" vs "cases" terminology
  - [ ] Update UI labels to be domain-neutral

### Phase 3: Validate with New Domain 🧪
**Goal**: Validate generic framework with a second domain (medical ethics)

#### Validation Tasks:
- [ ] Create medical ethics domain
  - [ ] `config/domains/medical.yaml` - Medical ethics configuration
  - [ ] `app/services/case_deconstruction/domain_adapters/medical_adapter.py`
  - [ ] Medical-specific extraction patterns
  - [ ] Medical concept mapping

- [ ] Test complete workflow
  - [ ] Create medical ethics world via domain factory
  - [ ] Upload medical guidelines (e.g., AMA Code of Medical Ethics)
  - [ ] Process medical cases using domain adapter
  - [ ] Generate medical scenarios
  - [ ] Verify all components work generically

- [ ] Domain-specific MCP modules (optional)
  - [ ] `mcp/modules/medical_analysis_module.py`
  - [ ] Medical terminology and concept extraction
  - [ ] Medical ontology integration

- [ ] Refinement based on learnings
  - [ ] Identify gaps in generic framework
  - [ ] Update abstractions based on real-world usage
  - [ ] Document domain creation process

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

## Technical Architecture

### 1. Leverage Existing Adapter Pattern
**Current Structure** (already excellent):
```
/app/services/case_deconstruction/
├── adapters/
│   ├── base_adapter.py                    # ✅ Already exists - BaseCaseDeconstructionAdapter
│   └── engineering_ethics_adapter.py     # ✅ Already exists - EngineeringEthicsAdapter
└── models/                                # ✅ Already exists - Comprehensive dataclasses
    ├── stakeholder.py
    ├── decision.py
    ├── reasoning_chain.py
    └── analysis_result.py
```

**Enhanced Structure** (what we'll add):
```
/app/services/
├── domain_registry.py                    # 🆕 Central domain management
├── domain_factory.py                     # 🆕 Domain component factory
└── case_deconstruction/
    ├── adapter_factory.py                # 🆕 Multi-domain adapter creation
    └── domain_adapters/                   # 🆕 Domain-specific adapters
        ├── engineering_adapter.py         # Move existing adapter here
        ├── medical_adapter.py             # New domain adapter
        └── legal_adapter.py               # Future domain adapter

/config/domains/                           # 🆕 Domain configurations
├── engineering.yaml
├── medical.yaml
└── legal.yaml
```

### 2. Key Interfaces (Leverage Existing)

#### BaseCaseDeconstructionAdapter (✅ Already Perfect)
The existing interface is already domain-agnostic:
```python
class BaseCaseDeconstructionAdapter(ABC):
    @abstractmethod
    def extract_stakeholders(self, sections: Dict[str, str]) -> List[Stakeholder]
    
    @abstractmethod
    def extract_decisions(self, sections: Dict[str, str]) -> List[Decision]
    
    @abstractmethod
    def extract_reasoning_chains(self, sections: Dict[str, str]) -> List[ReasoningChain]
    
    @abstractmethod
    def analyze_case(self, sections: Dict[str, str]) -> CaseAnalysisResult
```

#### New Domain Registry Interface
```python
class DomainRegistry:
    def __init__(self):
        self._domains: Dict[str, DomainConfig] = {}
    
    def register_domain(self, config: DomainConfig) -> None
    def get_domain(self, name: str) -> DomainConfig
    def list_domains(self) -> List[str]
    def create_adapter(self, domain_name: str) -> BaseCaseDeconstructionAdapter
```

#### Domain Configuration
```python
@dataclass
class DomainConfig:
    name: str                              # "engineering", "medical", etc.
    display_name: str                      # "Engineering Ethics"
    adapter_class_name: str               # "EngineeringEthicsAdapter"
    extraction_patterns: Dict[str, Any]   # Domain-specific extraction rules
    section_mappings: Dict[str, str]      # How to map document sections
    ontology_namespace: str               # Domain ontology namespace
    mcp_modules: List[str]                # Required MCP modules
    guideline_template: str               # Template for displaying guidelines
```

### 3. Domain Configuration Schema
```yaml
# Example: /config/domains/engineering.yaml
domain:
  name: "engineering"
  display_name: "Engineering Ethics"
  adapter_class: "EngineeringEthicsAdapter"
  description: "NSPE-based engineering ethics analysis"

document_processing:
  guideline_sections:
    - "facts"
    - "discussion"
    - "conclusion"
    - "dissenting_opinion"
  case_sections:
    - "scenario_description"
    - "ethical_considerations"
    - "stakeholder_analysis"
  
extraction_patterns:
  stakeholder_keywords:
    - "engineer"
    - "client"
    - "public"
    - "employer"
  decision_indicators:
    - "should"
    - "must"
    - "shall not"
    - "obligation"
  
ontology:
  namespace: "http://proethica.org/ontology/engineering#"
  concepts:
    competence: "eng:Competence"
    safety: "eng:PublicSafety"
    integrity: "eng:ProfessionalIntegrity"

mcp_modules:
  - "guideline_analysis_module"
  - "ontology_query_module"

ui_templates:
  guideline_display: "engineering_guidelines.html"
  case_analysis: "engineering_case_analysis.html"
```

## Migration Strategy (Minimal Changes Required)

### Database Changes (Optional - Current Models Already Support Multiple Domains)
Current `World` model already supports multiple domains well:
- ✅ `name` field for domain identification
- ✅ `ontology_file` for domain-specific ontologies  
- ✅ JSON metadata fields for flexible domain configuration
- ✅ Relationships to guidelines, cases, scenarios

**Optional enhancements:**
- [ ] Add `domain_type` field to World model for explicit domain classification
- [ ] Add `domain_config` JSON field for structured domain settings
- [ ] Maintain full backward compatibility

### Service Layer Changes (Primary Focus)
- [ ] Add domain registry as singleton service
- [ ] Create adapter factory using existing adapter pattern
- [ ] Enhance MCP client to support domain-specific modules
- [ ] No changes to existing business logic

### API Changes (Additive Only)
- [ ] Add domain listing endpoint: `GET /api/domains`
- [ ] Add domain-specific world creation: `POST /api/worlds/{domain_type}`
- [ ] **Keep all existing APIs unchanged** - perfect backward compatibility
- [ ] Add optional domain parameter to existing endpoints

### UI Updates (Configuration-Driven)
- [ ] Make terminology configurable per domain (optional)
- [ ] Add domain selection dropdown in world creation
- [ ] Domain-specific help text and examples
- [ ] Keep existing UI fully functional

## Success Criteria
- [ ] All existing engineering ethics functionality works unchanged
- [ ] Can add new domain (medical ethics) without modifying core framework
- [ ] Domain registry enables dynamic domain discovery
- [ ] Configuration-driven domain creation
- [ ] Performance remains comparable to current system
- [ ] Clean separation between generic framework and domain logic

## Revised Timeline (Based on Existing Architecture)
- **Phase 1** (Domain Registry & Factory): 1 week
- **Phase 2** (Pipeline Extensions): 1 week  
- **Phase 3** (Medical Domain Validation): 1 week
- **Phase 4** (Advanced Features): 2 weeks

**Total: ~5 weeks** (50% faster due to excellent existing architecture)

## Implementation Advantages
1. **Excellent Foundation**: Existing adapter pattern is perfectly designed for this
2. **Minimal Risk**: Adding coordination layer, not refactoring core logic
3. **Backward Compatibility**: Zero breaking changes to existing functionality
4. **Proven Patterns**: Using existing service patterns and architecture
5. **Fast Validation**: Can test with medical domain immediately

## Quick Start Implementation Order
1. **Domain Registry** (1-2 days) - Central coordination
2. **Engineering Config** (1 day) - Extract current patterns
3. **Medical Adapter** (2-3 days) - Test generalization
4. **Factory Pattern** (1 day) - Dynamic adapter creation
5. **UI Integration** (1-2 days) - Domain selection interface

## Key Files to Create
```
app/services/domain_registry.py           # Day 1
app/models/domain_config.py              # Day 1  
config/domains/engineering.yaml          # Day 2
config/domains/medical.yaml              # Day 3
app/services/case_deconstruction/
  ├── adapter_factory.py                 # Day 4
  └── domain_adapters/
      ├── engineering_adapter.py          # Day 2 (move existing)
      └── medical_adapter.py             # Day 3-4
```

## Notes
- **Zero breaking changes** - This is purely additive enhancement
- **Leverage existing excellence** - The adapter pattern is already perfect
- **Quick validation** - Can test medical domain within first week
- **Production ready** - Built on proven, tested architecture