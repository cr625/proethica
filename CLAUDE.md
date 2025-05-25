# AI Ethical DM Project Progress

## Document Structure and Section Embeddings (2025 Update)

This project models professional domains ("worlds") and supports ethical decision-making using structured document analysis, ontology-based concepts, and LLM reasoning. The current pipeline is:

### 1. Case Import and Parsing
- Cases (e.g., NSPE) are imported via URL or file upload.
- Each case is parsed into sections (facts, discussion, conclusion, etc.).

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

## Next Steps
- Process remaining cases with enhanced pipeline
- Test similarity search with granular fact/discussion items
- Run LLM experiments with structured triples
- Deploy MCP server for production use

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
