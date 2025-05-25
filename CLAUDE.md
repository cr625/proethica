# AI Ethical DM Project Progress

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

### 4. Guideline Association
- Ethical guidelines are associated with each world.
- Guideline associations can be generated for each case section, linking them to relevant ethical principles.

### 5. LLM Reasoning (Experiment Phase)
- LLMs can be prompted with case sections, extracted concepts, and triples for ontology-based reasoning.
- Two experiment modes: ontology-augmented and prompt-only.

## Technical Notes
- All new cases use the nested `document_structure` format in metadata.
- Section embeddings use 384-dim vectors (MiniLM-L6-v2) and are stored with pgvector.
- Legacy/obsolete migration scripts and top-level structure fields are no longer used for new data.
- NLTK resources are managed at setup, not runtime.

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

## Next Steps
- Process remaining cases with enhanced pipeline
- Test similarity search with granular fact/discussion items
- Run LLM experiments with structured triples
- Deploy MCP server for production use
- Implement LLM-enhanced triple generation (Phase 2)

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

## Archived Documentation
Legacy and outdated documentation has been moved to `docs/archived/` for reference.
