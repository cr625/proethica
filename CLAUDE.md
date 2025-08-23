# ProEthica: AI Ethical Decision-Making System

## 📁 Repository Organization Guidelines

### Directory Structure Rules
- **Tests**: `/tests/` - All test files
- **Documentation**: `/docs/` - All documentation files  
- **Archive**: `/archive/` - Old/deprecated files
- **Demos**: `/docs/demos/` - Publication and demonstration materials
- **Scratch**: `/scratch/` - Temporary working files and experiments

### File Creation Rules
- **NEVER** create files in the root directory unless absolutely necessary
- **ALWAYS** prefer editing existing files over creating new ones
- Keep the repository clean and organized

## 🔄 ONTOLOGY SERVER TRANSITION: ProEthica → OntServe

**Status**: Phase 2 Complete, Phase 3 Planning Complete ✅  
**Plan Document**: `/home/chris/onto/docs/transition-plan.md` - Comprehensive 5-week migration plan  
**Timeline**: August 2025

### Phase 1: OntServe Infrastructure ✅ (2025-08-22)

#### Database & MCP Server Complete
- [x] **PostgreSQL Schema**: Complete database schema supporting ProEthica's requirements
- [x] **Candidate Concept Storage**: Ready to receive concepts from ProEthica's 9-category pipeline
- [x] **Approval Workflows**: Database tables for concept approval tracking
- [x] **MCP Server**: Production-ready server with real database backend
- [x] **Professional Domains**: "engineering-ethics" domain ready for ProEthica concepts
- [x] **Version Control**: Full audit trail and change tracking system

#### OntServe Integration Features
- **Compatible Schema**: Designed to work with ProEthica's entity_triples structure
- **Two-Tier Concept System**: Supports semantic_label + primary_type from ProEthica
- **Confidence Scoring**: Preserves extraction confidence and LLM reasoning
- **Temporal Tracking**: BFO-compliant temporal region support
- **Vector Search**: pgvector embeddings for semantic similarity

### Architectural Division
- **ProEthica Retains**: Concept extraction, analysis, UI, workflow management
- **OntServe Handles**: Ontology storage, versioning, MCP server, candidate concept management

### Migration Impact
- **Concept Extraction**: Continues as current focus - no disruption to 9-category pipeline
- **Ontology Queries**: Will transition from internal MCP server to OntServe MCP endpoints  
- **Candidate Concepts**: Extracted concepts will be stored in OntServe as candidates for review
- **UI Integration**: ProEthica retains all approval UI, connects to OntServe backend

### Phase 3: MCP Migration Planning ✅ COMPLETE
**CRITICAL PLANNING MILESTONE ACHIEVED**: Comprehensive technical plan for migrating ProEthica's ontology serving to OntServe.

#### Key Analysis Results
1. **Critical Integration Point Identified**: `GuidelineAnalysisService._build_ontology_index()` is the primary method that needs replacement
2. **"Extract Concepts" Button Workflow**: Uses `OntologyEntityService.get_entities_for_world()` - this is the exact method to replace
3. **Implementation Strategy**: Service factory pattern with transparent fallback to existing ProEthica MCP server
4. **Response Format**: 100% compatibility maintained through careful interface design

#### Migration Approach
- **Week 3**: Replace ProEthica's internal MCP server with OntServe MCP endpoints
- **Piece-by-piece**: One-to-one replacements where possible, maintaining existing functionality
- **Environment Toggle**: `USE_ONTSERVE=true/false` for gradual rollout
- **Future Enhancement**: Foundation laid for sophisticated RDF/OWL reasoning capabilities

**Complete implementation plan**: `/home/chris/onto/docs/transition-plan.md`

### Next Implementation Phase
Ready to begin Phase 3 implementation:
1. **OntServe Client Library**: `app/clients/ontserve_client.py` with compatibility interface
2. **Service Factory**: `app/services/ontology_service_factory.py` for transparent switching
3. **MCP Proxy**: Redirect existing MCP calls to OntServe with format translation
4. **Validation Framework**: Ensure identical functionality during transition

## 🎯 CURRENT FOCUS: 9-Category Concept Extraction Pipeline

**Objective**: Extract and integrate all 9 ProEthica intermediate ontology categories with the same quality achieved in role extraction.

### ✅ POLICY: Concept Type Suffixes (2025-08-19)
**CRITICAL**: ALL concept labels MUST include their type suffix:
- **Examples**: "Structural Engineer Role", "Public Safety Principle", "Reporting Obligation"
- **9 Categories**: Role, Principle, Obligation, State, Resource, Action, Event, Capability, Constraint
- **Implementation**: `label_normalization.py` ensures suffix consistency

### Current Progress Status

| Category | Status | Completion |
|----------|--------|------------|
| **Role** | ✅ Complete | 100% |
| **Obligation** | 🔄 In Progress | 60% |
| **Principle** | ⏳ Planned | 0% |
| **Remaining 6** | ⏳ Planned | 0% |

### Next Sprint (4 weeks)
1. **Complete Obligations Extraction** - Finish modular pipeline implementation
2. **Begin Principles Extraction** - Third category using established patterns  
3. **Case Role Matching Phase 2** - Enhanced UI with ontology integration
4. **Cross-Category Linking** - Foundation for remaining categories

## 📋 Key Architecture Components

### Modular Extraction Pipeline
**Architecture**: Extractor → PostProcessor → Matcher → Linker → Persister → Gatekeeper
- **Role Extraction**: ✅ Complete with professional vs stakeholder classification
- **Obligations**: 🔄 In progress with professional-only linking policies
- **Remaining 7**: Planned using same modular approach

### Enhanced LLM Integration
- **Scenario Generation**: ✅ Phase 1 complete with MCP ontology integration
- **Hybrid Associations**: ✅ Vector embeddings + LLM analysis scoring
- **MCP Server**: 🔄 Transitioning to OntServe (https://mcp.proethica.org will redirect)

### Document Processing
- **Pipeline**: Case Import → Structure Generation → Section Embeddings → Concept Extraction
- **Features**: Dual storage (HTML/text), real-time progress, background processing
- **Status**: ✅ Complete and production-ready

### Ontology Integration UI
- **Concept Extraction**: LLM-powered extraction with temporary storage and review workflow
- **Smart Button States**: Dynamic UI switching from "Load Pending" → "View Ontology" + "View Saved Concepts"
- **RDF Parsing Interface**: Direct ontology content parsing with beautiful card-based concept display
- **Status**: ✅ Complete with full workflow integration

## 📚 Core Documentation

**Architecture & Implementation:**
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - Complete system architecture overview including **future MCP integration plan** for LLM-assisted ontology analysis
- [`docs/CONCEPT_EXTRACTION_PIPELINE.md`](docs/CONCEPT_EXTRACTION_PIPELINE.md) - Unified extraction pipeline for all 9 categories  
- [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) - Current progress and next steps
- [`docs/MCP_ONTOLOGY_SERVER_API.md`](docs/MCP_ONTOLOGY_SERVER_API.md) - MCP server API documentation and ontology vocabulary access

**Historical Context:**
- [`docs/archive/`](docs/archive/) - Legacy documentation and completed phases
- [`docs/ROLE_EXTRACTION_AND_MATCHING_INTEGRATED_PLAN.md`](docs/ROLE_EXTRACTION_AND_MATCHING_INTEGRATED_PLAN.md) - Role extraction details (reference)

## 🎯 Success Metrics

- **Role Classification**: 90%+ professional vs stakeholder accuracy ✅ **ACHIEVED**
- **Ontology UI Integration**: Complete extraction-to-review workflow ✅ **ACHIEVED**
- **Obligation Extraction**: ≥80% precision vs principles (target)
- **Ontology Coverage**: 95%+ concept matching across all categories
- **Processing Performance**: <30 seconds per document for all categories

## 💻 System Access

### Key URLs
- **Main Dashboard**: `/dashboard` - Real-time system statistics and progress
- **Document Processing**: `/cases/` - Case import and processing pipeline
- **Concept Review**: `/guidelines/` - Extract and review concepts from guidelines
- **MCP Server**: https://mcp.proethica.org - Production ontology integration

### Development Quick Start
```bash
# Enable enhanced features
export ENHANCED_SCENARIO_GENERATION=true
export ENABLE_OBLIGATIONS_EXTRACTION=true
export MCP_ONTOLOGY_INTEGRATION=true

# Run system
python run.py
```

---

## 📖 Technical Background

### System Overview
ProEthica models professional domains ("worlds") and supports ethical decision-making using:
- **Document Processing**: Case import, structure generation, section embeddings
- **Ontology Integration**: 9-category concept extraction with semantic matching
- **LLM Enhancement**: Hybrid scoring, temporal evidence, real-time progress
- **MCP Integration**: Production server for ontology queries and analysis

### Technology Stack
- **Backend**: Flask, SQLAlchemy, PostgreSQL with pgvector
- **LLM Integration**: LangChain with Claude/OpenAI providers  
- **Ontology**: RDF/Turtle with ProEthica intermediate ontology
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2)
- **Frontend**: Jinja2 templates with vanilla JavaScript

### Key Implementation Details
- **Async Processing**: Background task queue with real-time progress indicators
- **Hybrid Scoring**: 35% embedding + 25% LLM semantic + 20% context + 15% quality + 5% keywords
- **Data Storage**: Dual format (HTML display, plain text embeddings) with pgvector
- **Feature Flags**: Gradual rollout with fallback to legacy pipelines
- **Derived Ontologies**: Per-document/world ontologies preventing sprawl

For complete technical details, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## 📚 Historical Documentation

Extensive legacy documentation covering completed phases has been preserved in:
- [`docs/archive/`](docs/archive/) - Completed implementations and historical context
- **Note**: Historical sections remain in this document for reference but will be gradually migrated to archive

## Next Implementation Priority

**Complete Obligations Extraction Module** - Finish the second category in the 9-category pipeline to establish patterns for the remaining 7 categories.
