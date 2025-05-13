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
