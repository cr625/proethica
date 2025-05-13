# AI Ethical Design Manager

## Project Overview

The AI Ethical Design Manager is a platform to help engineers and designers think through the ethical implications of their work using real-world case studies, guidelines, and ontology-based reasoning.

## Key Features and Components

### 1. Case Analysis System
- Import and process engineering ethics case studies
- Extract ethical concepts and principles
- Link cases to ontology concepts

### 2. Ontology System
- Engineering ethics ontology
- Semantic matching with case content
- RDF triple store for knowledge representation
- Integration with:
  - World entities (roles, resources, actions)
  - McLaren's engineering ethics framework

### 3. Guidelines Feature
- Upload and process ethical guidelines
- Extract concepts from guidelines
- Match concepts to ontology entities
- Generate RDF triples for relationships
- Associate guidelines with worlds and entities

### 4. User Interface
- World management
- Case browsing and analysis
- Interactive ethical reasoning tools
- Guideline management and visualization

## Current Status (Updated: 2025-05-13)

### GitHub Codespaces Support
- ✅ Updated `start_proethica_updated.sh` for GitHub Codespaces compatibility
- ✅ Enhanced server startup process to use the guidelines-enabled MCP server
- ✅ Created comprehensive documentation for running in Codespaces
- ✅ Fixed PostgreSQL container setup in Codespaces environment
- ✅ Improved JSON-RPC connectivity for Codespaces networking

### Guidelines - MCP Server Integration
- ✅ Enhanced MCP server with guideline analysis capabilities
- ✅ Added `GuidelineAnalysisModule` with concept extraction, matching, and triple generation
- ✅ Created end-to-end testing pipeline
- ✅ Fixed model version and server connectivity issues (Now using `claude-3-7-sonnet-20250219`)
- ✅ Successfully generated RDF triples from guideline content
- ✅ Implemented robust JSON-RPC communication between client and server

### In Progress
- 🔄 Refining the concept review interface
- 🔄 Enhancing error handling and server diagnostics
- 🔄 Implementing integration with app's GuidelineAnalysisService
- 🔄 Improving semantic matching between concepts and ontology entities

## Next Steps

1. **Web Interface Integration**
   - Complete the GuidelineAnalysisService integration with the MCP tools
   - Enhance the concept review interface with better visualization
   - Add relationship visualization for guideline concepts

2. **Enhanced Triple Generation**
   - Create more sophisticated RDF patterns for ethical relationships
   - Support additional ontology sources beyond engineering ethics
   - Implement export options for various RDF formats

3. **Batch Processing and Performance**
   - Add capabilities for processing multiple guidelines simultaneously
   - Implement caching for extracted concepts
   - Add parallel processing for large guidelines
   - Optimize triple generation algorithms

## Key Implementation Documents

For the most up-to-date information on implementation status and plans:

- `mcp_integration_plan.md` - Current detailed plan for MCP server UI integration
- `guidelines_progress.md` - Tracking document for progress and implementation details
- `CODESPACE_GUIDELINES_STARTUP.md` - Latest instructions for running in Codespaces
- `README_GUIDELINES_TESTING.md` - Current testing procedures and troubleshooting

## Technical Architecture

The system uses a modular design with:
1. Core Flask application for web interface
2. MCP server for ontology and AI operations
3. PostgreSQL database with pgvector for embeddings
4. LLM integration (Claude and OpenAI)
5. RDF/OWL ontology with SPARQL for querying

## Running in GitHub Codespaces

```bash
./start_proethica_updated.sh
```

This script:
- Automatically detects the Codespaces environment
- Sets up PostgreSQL using Docker in the codespace
- Starts the enhanced MCP server with guidelines support
- Applies necessary fixes for JSON-RPC and model references
- Launches the Flask application with proper configuration

## Testing Guidelines Integration

```bash
# Test the MCP server connection
./test_mcp_jsonrpc_connection.py --verbose

# Run the full pipeline test
./run_guidelines_mcp_pipeline.sh
```

These scripts verify the complete guidelines processing pipeline from extraction to triple generation.
