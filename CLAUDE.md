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

## Recent Work and Progress

### Guidelines - MCP Server Integration
- ✅ Enhanced MCP server with guideline analysis capabilities
- ✅ Added `GuidelineAnalysisModule` with concept extraction, matching, and triple generation
- ✅ Created end-to-end testing pipeline
- ✅ Fixed model version and server connectivity issues
- ✅ Successfully generated RDF triples from guideline content

### Next Steps
1. **Web Interface Integration**
   - Update `GuidelineAnalysisService` to use the MCP tools
   - Enhance the concept review interface
   - Add visualization for relationships

2. **Enhanced Triple Generation**
   - Create more sophisticated RDF patterns
   - Support additional ontology sources
   - Implement export options for various formats

3. **Batch Processing**
   - Add capabilities for processing multiple guidelines
   - Implement caching for better performance
   - Create comparison tools for guidelines analysis

## Development Resources

### Documentation
- `README_GUIDELINES_TESTING.md` - Testing the guideline features
- `guidelines_progress.md` - Implementation progress and plan
- `docs/ontology_case_analysis_plan.md` - Overall ontology integration

### Tools
- `run_guidelines_mcp_pipeline.sh` - End-to-end testing script
- `test_guideline_mcp_client.py` - MCP client for guideline testing
- `fix_test_guideline_mcp_client.py` - Fix for the client connectivity

### Server
- `mcp/enhanced_ontology_server_with_guidelines.py` - Main MCP server
- `mcp/modules/guideline_analysis_module.py` - Guidelines analysis module
- `mcp/modules/base_module.py` - Base module system

## Technical Architecture

The system uses a modular design with:
1. Core Flask application for web interface
2. MCP server for ontology and AI operations
3. PostgreSQL database with pgvector for embeddings
4. LLM integration (Claude and OpenAI)
5. RDF/OWL ontology with SPARQL for querying

## Environment Setup

To work on the guidelines feature:
1. Ensure the proper environment variables are set in `.env`
2. Install required packages with `pip install -r requirements-mcp.txt`
3. Start the MCP server: `python mcp/run_enhanced_mcp_server_with_guidelines.py`
4. Run tests: `./run_guidelines_mcp_pipeline.sh`

## Guidelines Integration with MCP Server (Updated: 2025-05-13)

The guidelines integration with the MCP server and triples extraction process has been successfully implemented. This integration enables the extraction of concepts from ethical guidelines, matching them to ontology entities, and generating RDF triples to represent the relationships.

### Key Components

1. **Enhanced Ontology Server**:
   - Integration with `GuidelineAnalysisModule` for processing guidelines
   - JSON-RPC endpoint for reliable client-server communication
   - Updated to use the latest Claude model (`claude-3-7-sonnet-20250219`)

2. **MCP Client Improvements**:
   - Updated to use JSON-RPC endpoints instead of deprecated API endpoints
   - Fixed model references for consistency across the system
   - Added comprehensive error handling for connection failures

3. **Pipeline Tools**:
   - `test_mcp_jsonrpc_connection.py`: Tests server connectivity via JSON-RPC
   - `fix_mcp_client.py`: Updates client to use JSON-RPC communications
   - `update_claude_models_in_mcp_server.py`: Ensures consistent model usage
   - `run_guidelines_mcp_pipeline.sh`: End-to-end testing pipeline

4. **Documentation**:
   - `RUN_WEBAPP_WITH_GUIDELINES.md`: Instructions for running the web app
   - `README_GUIDELINES_TESTING.md`: Testing procedures and troubleshooting
   - `guidelines_progress.md`: Tracking document for progress and next steps

### Running the Application

To run ProEthica with guidelines support:

```bash
./start_with_enhanced_ontology_server.sh
```

This script handles all necessary setup, including:
- Starting the enhanced ontology server
- Updating MCP client configuration
- Ensuring proper model usage
- Starting the Flask web application

### Testing Guidelines Integration

Guidelines integration can be tested using:

```bash
# Test the MCP server connection
./test_mcp_jsonrpc_connection.py --verbose

# Run the full pipeline test
./run_guidelines_mcp_pipeline.sh
```

### Next Steps

1. **Web Interface Enhancements**:
   - Improve concept visualization in the web UI
   - Add better management of guideline triples
   - Implement batch processing for multiple guidelines

2. **Integration with Existing Ontologies**:
   - Connect guideline concepts with engineering ethics ontology
   - Map to existing case analysis frameworks
   - Establish links to the McLaren model

3. **Performance Optimization**:
   - Add caching for extracted concepts
   - Implement parallel processing for large guidelines
   - Optimize triple generation algorithms
