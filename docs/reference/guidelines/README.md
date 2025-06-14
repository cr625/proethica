# Guidelines Component Documentation

## Overview
The Guidelines component enables extraction of ethical concepts and generation of RDF triples from professional ethics guidelines (e.g., NSPE Code of Ethics). Guidelines are associated with worlds (currently Engineering World - ID 1) and provide semantic enrichment for case analysis.

## Current Architecture

### Components
1. **GuidelineAnalysisService** - Core service for concept extraction and triple generation
2. **MCP Server Integration** - HTTP-based server providing ontology tools
3. **Database Models** - Guideline and Document models with associations
4. **Processing Pipeline** - Async document processing with status tracking

### Data Flow
```
User Input (File/URL/Text) → Document Creation → Background Processing
    ↓
Concept Extraction (MCP/LLM) → Review Interface → Concept Selection
    ↓
Triple Generation → Ontology Matching → Storage (EntityTriples)
    ↓
World Association → Case Enrichment
```

## Current Implementation Status

### Working Features
- ✅ Multi-source guideline input (file upload, URL, text)
- ✅ Two-phase approach: concept extraction → triple generation
- ✅ LLM integration (Claude preferred, OpenAI fallback)
- ✅ MCP server with guideline analysis tools
- ✅ Mock mode for development/testing
- ✅ Basic RDF triple generation
- ✅ PostgreSQL storage with associations

### Limitations
- ❌ Basic triple generation (only explicit relationships)
- ❌ Limited ontology alignment capabilities
- ❌ No native Claude tool-calling support
- ❌ Simple list-based review interface
- ❌ Manual ontology synchronization
- ❌ No concept versioning/history

## File Structure
```
docs/guidelines/
├── README.md (this file)
├── concept_extraction_process.md - Detailed extraction workflow
├── triple_generation_plan.md - Enhanced triple generation roadmap
├── ontology_alignment_strategy.md - Matching concepts to ontology
├── implementation_status.md - Current feature status
└── archived/ - Legacy documentation
```

## Key Concepts

### Concept Categories
- **Principles** - Fundamental ethical values
- **Obligations** - Required duties and responsibilities
- **Roles** - Professional positions and their characteristics
- **Conditions** - Circumstances and constraints
- **Resources** - Tools, materials, information
- **Actions** - Activities and behaviors
- **Events** - Occurrences and situations
- **Capabilities** - Skills and competencies

### Triple Types
1. **Basic Triples** - Type, label, description
2. **Relationship Triples** - Connections between concepts
3. **Ontology Triples** - Alignment with existing ontology

## Next Steps
See `triple_generation_plan.md` for the comprehensive improvement roadmap.