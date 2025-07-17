# AI Ethical DM Project Progress

## 🚀 CURRENT FOCUS: Engineering Ethics Ontology Organization Project (2025-07-17)

**We are currently organizing the engineering ethics ontology according to the 8 main intermediate types (Role, Principle, Obligation, State, Resource, Action, Event, Capability) to improve concept extraction and categorization.**

📋 **PROGRESS TRACKING**: See `/docs/ENGINEERING_ETHICS_ONTOLOGY_ORGANIZATION_PROGRESS.md` for detailed status, tasks, and results.

### Key Challenge
Current ontology has 14 concepts across 6 categories, but is missing Action and Event concepts entirely. Only 2 mapping fixes needed - most intermediate classes are already correctly mapped.

### Implementation Strategy: 5-Phase Ontology-First Approach
- **Phase 1** (Current): Fix Current Ontology Mapping (Week 1)
- **Phase 2**: Populate 8 Categories with Starter Examples (Week 2)
- **Phase 3**: Analyze and Import NSPE Code of Ethics (Week 3)
- **Phase 4**: Process Sample NSPE Cases (Week 4)
- **Phase 5**: External Ontology Integration (Week 5-6)

### Primary Content Sources
- [NSPE Code of Ethics](https://www.nspe.org/career-growth/ethics/code-ethics)
- [NSPE Board of Ethical Review Cases](https://www.nspe.org/career-growth/ethics/board-ethical-review-cases)
- Existing engineering ethics ontology concepts

### Key Files
- **Progress Tracking**: `/docs/ENGINEERING_ETHICS_ONTOLOGY_ORGANIZATION_PROGRESS.md`
- **Main Ontology**: `/ontologies/engineering-ethics.ttl`
- **Intermediate Ontology**: `/ontologies/proethica-intermediate.ttl`
- **Extraction Service**: `/app/services/ontology_entity_service.py`

## 📊 ProEthica Unified Dashboard (2025-01-27)

**A comprehensive dashboard for visualizing the ethical decision-making system capabilities and monitoring progress.**

### Dashboard Features
- **System Overview**: Real-time statistics (worlds, guidelines, cases, documents, ontologies)
- **Pipeline Status**: 8-step ethical decision-making workflow with completion tracking
- **Capabilities Assessment**: 8 capability areas with status indicators and completion rates
- **Processing Statistics**: Document processing rates, embedding generation, analysis completion
- **Recent Activity**: Latest documents, guidelines, and worlds with quick access links
- **World-Specific Dashboards**: Detailed analysis status for individual worlds

### Key Insights from Dashboard
- **Overall System Completion**: 66.2%
- **Operational Components**: Document Import, Structure Annotation, Section Embedding, Concept Extraction, Association Generation
- **Missing Components**: Recommendation Engine (0%), Outcome Tracking (0%)
- **Partial Components**: Decision Visualization (30%)

### Dashboard URLs
- Main Dashboard: `/dashboard`
- World Dashboard: `/dashboard/world/<id>`
- Stats API: `/dashboard/api/stats`
- Workflow API: `/dashboard/api/workflow`
- Capabilities API: `/dashboard/api/capabilities`

### Technical Implementation
- **Route**: `app/routes/dashboard.py` with comprehensive data aggregation
- **Templates**: `app/templates/dashboard/index.html` and `world.html`
- **Navigation**: Integrated into main navigation bar
- **Real Data**: Shows actual system statistics from database models

---

## Document Structure and Section Embeddings (2025 Update)

This project models professional domains ("worlds") and supports ethical decision-making using structured document analysis, ontology-based concepts, and LLM reasoning. The current pipeline is:

### 1. Case Import and Parsing
- Cases (e.g., NSPE) are imported via URL or file upload.
- Each case is parsed into sections (facts, discussion, conclusion, dissenting opinion, etc.).

### 2. Document Structure Generation
- For each case, run the document structure pipeline (via UI or script).
- This creates a `document_structure` entry in the case's `doc_metadata` with:
  - `document_uri`: Unique identifier for the case
  - `structure_triples`: RDF triples representing the case structure (ProEthica intermediate ontology)
  - `sections`: Section metadata
  - `annotation_timestamp`: When structure was generated

### 3. Section Embeddings
- Section embeddings are generated and stored in both the `DocumentSection` table (with pgvector) and in `section_embeddings_metadata` in `doc_metadata`.
- Enables semantic similarity search between sections across cases.

### 4. Enhanced Hybrid Guideline Association (2025-06-10)
- **Hybrid Approach**: Combines fast vector embeddings with nuanced LLM analysis
- **Multi-dimensional Scoring**: 
  - 🔢 Embedding scores: Vector similarity, keyword overlap, contextual patterns
  - 🧠 LLM scores: Semantic analysis, reasoning quality assessment
  - 🎯 Combined: Weighted hybrid confidence (35% embedding + 25% LLM semantic + 20% context + 15% LLM quality + 5% keywords)
- **Separated Component Visibility**: UI shows exactly what each method contributes
- **Database Schema**: Extended `case_guideline_associations` table with LLM-specific columns
- **Fallback Resilience**: Embeddings provide reliable baseline even if LLM unavailable

### 5. LLM Reasoning (Experiment Phase)
- LLMs can be prompted with case sections, extracted concepts, and triples for ontology-based reasoning.
- Two experiment modes: ontology-augmented and prompt-only.
- **Enhanced**: Integrated into hybrid guideline associations with JSON-structured prompts

### 6. Asynchronous Processing with Progress Indicators (2025-06-12)
- **Background Task Queue**: Extended `BackgroundTaskQueue` with `process_associations_async()` for long-running LLM operations
- **Real-time Progress Tracking**: 
  - Progress phases: `ANALYZING` → `LLM_PROCESSING` → `SAVING_RESULTS`
  - Progress updates: 10% → 40% → 80% → 100%
  - Status tracking in `doc_metadata['association_processing_*']` fields
- **User Interface Enhancements**:
  - **Immediate feedback**: Button changes to "Processing Associations..." with spinner
  - **Live progress bar**: Auto-polling every 2 seconds via `/structure/association_progress/<id>` endpoint
  - **Phase indicators**: Real-time status updates ("Processing with LLM...", "Saving results...")
  - **Auto-refresh**: Page reloads when processing completes to show results
- **Prevents Double Processing**: Form disabled during processing to avoid duplicate requests
- **Vanilla JavaScript**: Removed jQuery dependency, uses modern DOM APIs for compatibility

## Technical Notes
- All new cases use the nested `document_structure` format in metadata.
- Section embeddings use 384-dim vectors (MiniLM-L6-v2) and are stored with pgvector.
- Legacy/obsolete migration scripts and top-level structure fields are no longer used for new data.
- NLTK resources are managed at setup, not runtime.
- **Async Processing**: Long-running tasks use threading with separate database sessions to avoid blocking the main UI
- **Progress API**: RESTful endpoint `/structure/association_progress/<id>` returns JSON status for real-time polling

## Recent Updates (2025-01-24)

### 1. URL Processing Pipeline Consolidation
- Merged duplicate case processing routes (`/cases/process_url` and `/cases/process_url_enhanced`)
- Consolidated pipeline to include DocumentStructureAnnotationStep by default
- Fixed template references to use single unified route

### 2. Dual Text/HTML Extraction
- Implemented dual format storage: HTML for display, plain text for embeddings
- NSPEExtractionStep now returns both `sections` (HTML) and `sections_text` (plain)
- Section embeddings use clean text versions for better similarity matching
- RDF triples use clean text for `hasTextContent` predicates

### 3. Enhanced Structure Triple Viewer
- Created `StructureTripleFormatter` service for parsing RDF triples
- Built interactive JavaScript viewer with formatted/raw toggle
- Combined Section Metadata display with Structure Triples
- Added user-friendly display showing:
  - Document information (case number, title, year)
  - Section items with full content (questions, conclusions, references)
  - Statistics about triple counts
  - LLM-friendly text format

### 4. Enhanced Facts and Discussion Sections
- Facts now broken into individual `FactStatement` items
- Discussion broken into `DiscussionSegment` items with types:
  - `ethical_analysis`: Contains ethical reasoning
  - `reasoning`: Contains logical arguments
  - `code_reference`: References specific standards
  - `general`: Other content
- Both maintain sequence numbers for narrative flow
- Consistent with Questions/Conclusions/References pattern

## Technical Improvements
- Structure triples now display section content in unified view
- All sections follow consistent item-based pattern for granular search
- Clean text extraction prevents HTML noise in embeddings
- Segment classification enables semantic querying

## LLM Integration Documentation (2025-01-24)

### Consolidated Documentation
Created comprehensive LLM documentation in `/llm/` directory:
- **README.md**: Overview and quick start guide
- **docs/INDEX.md**: Complete index of 40+ LLM integration points
- **docs/IMPLEMENTATION_GUIDE.md**: How-to guide for using LLM services
- **docs/PROVIDERS.md**: Provider configurations (Claude, OpenAI, Mock)
- **docs/USE_CASES.md**: Detailed use cases with examples
- **docs/ARCHITECTURE.md**: LLM-Ontology integration architecture
- **docs/PROCESSING_CAPABILITIES.md**: Triple generation and processing
- **docs/EXPERIMENTAL_FRAMEWORK.md**: Research framework and evaluation

### Archived Documentation
Moved legacy LLM docs to `/llm/docs/archived/` for reference.

## Dissenting Opinion Support (2025-01-24)

### Enhancement Overview
Added comprehensive support for "Dissenting Opinion" sections found in some NSPE ethics cases:

### 1. Extraction Enhancement
- **NSPECaseExtractionStep**: Added `extract_dissenting_opinion_section()` method
- **Pattern Recognition**: Handles both field-based and label-based HTML patterns
- **Field Detection**: Targets `field--name-field-dissenting-opinion` div structure
- **Fallback Pattern**: Searches for "Dissenting Opinion" field labels

### 2. RDF Triple Generation
- **DocumentStructureAnnotationStep**: Enhanced to create dissenting opinion triples
- **New Ontology Classes**: 
  - `DissentingOpinionSection`: Main section container
  - `DissentingArgument`: Individual arguments within dissenting opinion
- **Content Storage**: Both HTML and clean text versions stored
- **Semantic Segmentation**: Breaks dissenting opinions into individual arguments

### 3. Display Integration
- **Template Updates**: Added dissenting opinion cards to `case_extracted_content.html`
- **Visual Distinction**: Uses warning-colored header (`bg-warning`) to distinguish from majority opinion
- **Form Integration**: Includes dissenting opinion in case saving forms

### 4. Route Updates
- **URL Processing**: Both `process_url_pipeline` and `save_and_view_case` routes handle dissenting opinions
- **Metadata Storage**: Dissenting opinions stored in case metadata sections
- **HTML Generation**: Creates structured card display for dissenting opinions

### 5. Documentation Updates
- **README**: Updated case processing pipeline documentation
- **CLAUDE.md**: Added dissenting opinion to case parsing description

## Full Date Extraction Support (2025-01-24)

### Enhancement Overview
Added comprehensive support for extracting and storing full dates from NSPE cases:

### 1. Date Extraction Logic
- **New Method**: `extract_full_date()` in NSPECaseExtractionStep
- **Field Detection**: Looks for `field--name-field-year` div structure
- **Multiple Formats Supported**:
  - "Wednesday, June 14, 2023" (full weekday format)
  - "June 14, 2023" (standard US format)
  - "14 June 2023" (international format)
  - "2023-06-14" (ISO format)
- **Fallback**: Extracts year even if full date parsing fails

### 2. Date Storage Structure
- **full_date**: Original date string as displayed on page
- **date_parts**: Parsed components including:
  - `year`: Integer year value
  - `month`: Integer month (1-12)
  - `month_name`: Full month name (e.g., "June")
  - `day`: Day of month
  - `weekday`: Day name if available (e.g., "Wednesday")
  - `iso_date`: Standard ISO format (YYYY-MM-DD)

### 3. Display Integration
- **Template Updates**: Shows full date in case metadata table
- **ISO Format**: Displays standardized date in small text
- **Form Integration**: Passes full date and date_parts through save forms

### 4. Route Updates
- **process_url_pipeline**: Extracts and stores full date in metadata
- **save_and_view_case**: Handles full_date and date_parts from form submission
- **Metadata Storage**: Both fields stored in case doc_metadata

### 5. Benefits
- **Better Temporal Context**: Full dates provide complete temporal information
- **Standardized Storage**: ISO format enables date-based queries and sorting
- **Preserved Original**: Keeps original format for display fidelity
- **Backward Compatible**: Still extracts year if full date unavailable

### 6. Template Updates (2025-01-24)
- **case_detail.html**: Added full date display as info badge with calendar icon
- **document_structure.html**: Shows full date with ISO format in Document Information card
- **Note**: Found that `case_extracted_content.html` is not currently attached to any route
  - Template appears designed to preview extracted content before saving
  - Currently, the system directly saves cases without preview step
  - Could be connected to improve user experience in future

## Hybrid Enhanced Associations Implementation (2025-06-10)

### Technical Architecture
- **Service**: `EnhancedGuidelineAssociationService` with hybrid scoring
- **Database**: Extended `case_guideline_associations` table with columns:
  - `llm_semantic_score`, `llm_reasoning_quality`
  - `embedding_reasoning`, `llm_reasoning`, `scoring_method`
- **UI**: Separated component display in document structure viewer
- **Route**: `/structure/associate_ontology_concepts/<id>` with clear/regenerate functionality

### Scoring Methodology
```python
overall_confidence = (
    0.35 * embedding_similarity +    # Fast, reliable semantic matching
    0.25 * llm_semantic_score +      # Nuanced LLM semantic analysis
    0.20 * contextual_relevance +    # Context pattern matching
    0.15 * llm_reasoning_quality +   # LLM reasoning coherence
    0.05 * keyword_overlap           # Simple keyword matching
)
```

### User Interface Features
- **Clear & Regenerate**: Button to clear associations for testing
- **Hybrid Method Selection**: Vector+LLM or LLM+Vector weighting preferences
- **Expandable Reasoning**: Shows combined + individual method explanations
- **Score Breakdown**: Separate columns for embedding vs LLM contributions
- **Pattern Indicators**: Outcome prediction badges (safety, competence, transparency)

### Implementation Status
✅ **Phase 1**: Analyze existing guideline associations and case outcomes  
✅ **Phase 2**: Design enhanced association schema with outcome patterns  
🔄 **Phase 3**: Create outcome pattern recognition service (hybrid approach complete)  
✅ **Connect UI**: Generate button connected to enhanced service with clear/regenerate  
⏳ **Phase 4**: Build historical pattern correlation system  
⏳ **Phase 5**: Implement predictive confidence scoring  
⏳ **Phase 6**: Create case similarity matching based on patterns  
⏳ **Phase 7**: Build UI for viewing predictive associations  
⏳ **Phase 8**: Test and validate prediction accuracy  

## Next Steps
- Debug LLM JSON response parsing for full hybrid functionality
- Complete Phase 4: Historical pattern correlation system
- Process remaining cases with enhanced pipeline
- Test similarity search with granular fact/discussion items
- Run LLM experiments with structured triples
- Deploy MCP server for production use

## Universal Progress Indicator Framework (2025-06-12)
The async processing system implemented for hybrid associations provides a **reusable pattern** for any long-running operations:

### Framework Components
- **`BackgroundTaskQueue`**: Extensible base class for async operations
- **Progress API pattern**: Standardized JSON endpoint for status polling  
- **UI components**: Reusable progress bar, spinner, and state management JavaScript
- **Database schema pattern**: Consistent `*_processing_status/progress/phase` fields in metadata

### Future Applications
This framework can be extended for:
- **Document processing pipelines** (URL extraction, structure annotation)
- **Bulk case analysis** (batch processing multiple cases)
- **Ontology operations** (large-scale triple generation)
- **Export operations** (generating reports, data exports)
- **Machine learning tasks** (training, inference on large datasets)

### Implementation Files
- **Backend**: `app/services/task_queue.py` - Extended with association processing
- **Routes**: `app/routes/document_structure.py` - Added progress endpoint and async route conversion
- **Frontend**: `app/templates/document_structure.html` - Progress UI and vanilla JavaScript polling
- **Documentation**: Updated `CLAUDE.md` with async processing patterns

## MCP Server Status (Updated 2025-01-24)

### Current Implementation
The project uses an HTTP-based MCP (Model Context Protocol) server that provides ontology and guideline analysis capabilities:

- **Server**: `mcp/enhanced_ontology_server_with_guidelines.py` (launched via `start_mcp_server_with_env.sh`)
- **Port**: 5001 (configured in launch.json)
- **Architecture**: HTTP JSON-RPC server extending `OntologyMCPServer`
- **Key Modules**:
  - Guideline Analysis Module: Extract concepts from ethical guidelines using LLM
  - Ontology Query Module: Access ontology entities and relationships
  - Temporal Module: Handle time-based relationships (if enabled)

### Key Capabilities
1. **Ontology Access**: Load ontologies from database (with file fallback)
2. **Guideline Analysis**: Extract concepts and generate RDF triples from text
3. **Entity Matching**: Match guideline concepts to ontology entities
4. **LLM Integration**: Uses Claude/OpenAI for semantic analysis (with mock fallback)

### Integration with Claude via Anthropic API
**Good News**: MCP is available through the Anthropic API using the "MCP connector (beta)" feature:
- Requires beta header: `"anthropic-beta": "mcp-client-2025-04-04"`
- Connect to remote MCP servers directly from Messages API
- Currently supports only tool calls (not resources)
- Server must be publicly exposed via HTTP

**Current Limitation**: The MCP server runs locally on port 5001, so it would need to be:
1. Exposed publicly (e.g., via ngrok, cloud deployment)
2. Secured with proper authentication (OAuth Bearer tokens supported)

### Next Steps for API Integration
1. Deploy MCP server to a public endpoint (AWS, Heroku, etc.)
2. Implement authentication (OAuth or API keys)
3. Use Anthropic API's MCP connector to access the server's tools
4. Claude can then directly call guideline analysis and ontology query functions

### MCP Folder Structure
- `/mcp/` - Main MCP server implementations
- `/mcp/modules/` - Pluggable modules (guideline analysis, query, etc.)
- `/mcp/docs/` - MCP documentation and guides
- `/mcp/ontology/` - Ontology TTL files (fallback when DB unavailable)
- `/mcp/mseo/` - Materials science ontology integration (experimental)

## MCP Production Deployment (Updated 2025-01-27)

### Production Server Details
- **URL**: https://mcp.proethica.org
- **Server**: DigitalOcean droplet (209.38.62.85)
- **Location**: `/home/chris/proethica`
- **Port**: 5002 (production), 5001 (local development)
- **Branch**: `guidelines-enhancement` (latest)

### Deployment Process
1. **Local to Production Sync**:
   ```bash
   # From local development machine
   ./server_config/sync-mcp-to-production.sh
   ```

2. **Check Status**:
   ```bash
   ./server_config/check-mcp-status.sh
   ```

3. **Manual Deployment** (on server):
   ```bash
   ssh digitalocean
   cd /home/chris/proethica
   ./server_config/deploy-mcp-guidelines.sh
   ```

### Key Scripts
- `sync-mcp-to-production.sh` - Push local changes to production
- `deploy-mcp-guidelines.sh` - Deploy on production server
- `check-mcp-status.sh` - Check health and status

### Testing with Anthropic API
Once deployed, the MCP server can be accessed via:
- Endpoint: `https://mcp.proethica.org`
- Use with Anthropic API's MCP connector (beta)
- Requires proper authentication setup

## Type Management System Optimization (2025-06-09)

### Major Improvements Completed
- **Fixed Type Mapping Algorithm**: Enhanced semantic mappings for ethics, rights, safety, competency concepts
- **Resolved Data Quality Issues**: Processed 23 unmapped concept types, eliminated "None" type displays
- **Optimized User Interface**: Concept list now shows 31 relevant concepts instead of 190 structural triples
- **Achieved Full Coverage**: All concept types now properly classified with confidence scores

### Current Status
- **31 concept types mapped** with intelligent classifications
- **12 concepts flagged for review** with clear reasoning
- **77% average confidence** across all mappings
- **Zero unmapped concepts** remaining in system

### Type Distribution
- **principle**: 9 concepts (ethics, rights, safety)
- **state**: 9 concepts (conditions, reputation)  
- **obligation**: 6 concepts (duties, responsibilities)
- **action**: 3 concepts (development, communication)
- **role**: 2 concepts (professional relationships)
- **capability**: 1 concept (competence)

See `TYPE_MANAGEMENT_OPTIMIZATION_2025_06_09.md` for complete details.

## Archived Documentation
Legacy and outdated documentation has been moved to `docs/archived/` for reference.
