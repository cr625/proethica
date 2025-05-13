# Guidelines Feature Implementation Progress

> **Note:** For the most up-to-date implementation status, please refer to the [Guidelines Implementation Status](guidelines_implementation_status.md) document which contains the latest information as of 2025-05-13.

## Overview
This document tracks the historical implementation of the guidelines feature for the AI Ethical DM application. The feature allows uploading guidelines associated with a world and linking them to RDF triples from the engineering-ethics ontology.

## Requirements

1. Users should be able to upload guidelines through:
   - File upload
   - Pasted text
   - URL

2. Once guidelines are uploaded, we need a four-phase approach:
   - Phase 1: Present uploaded guidelines properly formatted for display
   - Phase 2: Evaluate guidelines to find concepts matching engineering-ethics ontology entities
   - Phase 3: Allow user confirmation/deselection of matched entities
   - Phase 4: Associate RDF triples with the confirmed entities and the guidelines

## Current Status

### Completed
- ✅ Basic guideline upload functionality (file, text, URL) through `/worlds/{id}/guidelines/add` route
- ✅ GuidelineAnalysisService class with initial structure
- ✅ Support for LLM client initialization with improved version detection
- ✅ Memory optimization for LLM response processing
- ✅ Created test guideline with engineering ethics content
- ✅ Added proper Markdown rendering for guideline content
- ✅ Enhanced world detail page's guidelines section with improved UI
- ✅ Updated concept review page with Markdown support
- ✅ Successfully tested guideline upload functionality
- ✅ Enhanced MCP integration with GuidelineAnalysisModule implementation
- ✅ Improved embeddings client with real OpenAI embeddings (with fallback options)
- ✅ Added structured ontology context for better concept extraction
- ✅ Implemented fallback mechanisms when MCP server is unavailable
- ✅ Enhanced error handling throughout the GuidelineAnalysisService
- ✅ Updated GuidelineAnalysisModule to use Claude 3 Sonnet model
- ✅ Created debugging tools for MCP server integration
- ✅ Added clear model comments for Claude 3 Sonnet in the codebase
- ✅ Created base module architecture for MCP modules
- ✅ Implemented proper tool handling in enhanced MCP server
- ✅ Created client test script for guideline MCP services
- ✅ Added pipeline script for end-to-end MCP-based guideline processing
- ✅ Fixed server startup and module registration issues
- ✅ Fixed Claude model version from claude-3-sonnet-20240229 to claude-3-7-sonnet-20250219
- ✅ Resolved MCP server client connection issues via JSON-RPC endpoint
- ✅ Successfully tested guideline concept extraction with end-to-end pipeline
- ✅ Created comprehensive README_GUIDELINES_TESTING.md with full documentation
- ✅ Generated RDF triples from guideline concepts with proper Turtle format output

### In Progress
- 🔄 Refining the concept review interface
- 🔄 Enhancing error handling and server diagnostics
- 🔄 Implementing integration with app's GuidelineAnalysisService
- 🔄 Improving semantic matching between concepts and ontology entities

### Planned
- 📅 Implement visualization tools for guideline concept relationships
- 📅 Create web interface for guideline management
- 📅 Integrate RDF triple database storage with the guideline workflow
- 📅 Add batch processing for multiple guideline documents
- 📅 Create workflow for associating guidelines with world entities

## Current Architecture

The implementation follows a modular architecture with separate components for:

1. **MCP Server Components**
   - Base Module System (`MCPBaseModule` class)
   - Guideline Analysis Module (`GuidelineAnalysisModule` class)
   - Enhanced Ontology Server with Guidelines support

2. **Client-Side Components**
   - Test Guideline MCP Client for direct testing
   - GuidelineAnalysisService integration with MCP
   - Pipeline script for end-to-end testing

3. **Tools Provided by the Guideline Analysis Module**
   - `extract_guideline_concepts`: Extract key concepts from guideline content
   - `match_concepts_to_ontology`: Match extracted concepts to ontology entities
   - `generate_concept_triples`: Generate RDF triples for selected concepts

## Implementation Plan

### MCP Server Integration

We will use the enhanced ontology MCP server with guidelines support for this feature:

1. **MCP Server Selection**
   - The `enhanced_ontology_server_with_guidelines.py` server is the appropriate one for our needs
   - This server includes the `GuidelineAnalysisModule` which provides tools for extracting and matching concepts
   - The server runs on port 5001 by default

2. **Server Verification and Startup**
   - Verify the server is running using processes check
   - If not running, use `python mcp/run_enhanced_mcp_server_with_guidelines.py`
   - The server should be started automatically through the `start_proethica_updated.sh` script

### Phase 1: Enhanced GuidelineAnalysisService

1. **Enhance MCP Client Integration**
   ```python
   def extract_concepts(self, content: str, ontology_source: Optional[str] = None) -> Dict[str, Any]:
       """
       Extract concepts from guideline content with enhanced MCP integration.
       """
       # First try to use the MCP server
       try:
           # Make JSON-RPC call to extract concepts
           response = requests.post(
               f"{self.mcp_client.mcp_url}/jsonrpc",
               json={
                   "jsonrpc": "2.0",
                   "method": "call_tool",
                   "params": {
                       "name": "extract_guideline_concepts",
                       "arguments": {
                           "content": content,
                           "ontology_source": ontology_source
                       }
                   },
                   "id": 1
               },
               timeout=60
           )
           
           if response.status_code == 200:
               result = response.json()
               if "result" in result:
                   return result["result"]
               
       except Exception as e:
           logger.warning(f"Error using MCP for concept extraction: {str(e)}")
           
       # Fall back to direct LLM processing if MCP fails
       return self._extract_concepts_direct(content, ontology_source)
   ```

2. **Format Structured Ontology Context**
   ```python
   def _format_ontology_context(self, entities_data: Dict[str, Any]) -> str:
       """Format ontology entities into a structured context for the LLM prompt."""
       context = "## Engineering Ethics Ontology Entities\n\n"
       
       # Format by entity type
       for category, entities in entities_data.get("entities", {}).items():
           if not entities:
               continue
               
           context += f"### {category.upper()}\n"
           for entity in entities:
               label = entity.get("label", "")
               desc = entity.get("description", "No description")
               uri = entity.get("uri", "")
               
               context += f"- {label}: {desc}\n"
           
           context += "\n"
       
       return context
   ```

3. **Update LLM Prompt for World Entity Types**
   ```python
   system_prompt = """
   You are an expert in ethical engineering and ontology analysis. Your task is to extract key ethical concepts
   from engineering guidelines and standards. Focus on identifying specific types of entities:
   
   1. Roles (e.g., professional positions like Engineer, Manager)
   2. Principles (e.g., core ethical principles like Honesty, Integrity)
   3. Obligations (e.g., professional duties like Public Safety, Confidentiality)
   4. Conditions (e.g., contextual factors like Budget Constraints, Time Pressure)
   5. Resources (e.g., tools or standards like Technical Specifications)
   6. Actions (e.g., professional activities like Report Safety Concern)
   7. Events (e.g., occurrences like Project Milestone, Safety Incident)
   8. Capabilities (e.g., skills like Technical Design, Leadership)
   
   For each concept, provide:
   - A label (short name for the concept)
   - A description (brief explanation of what it means in this context)
   - Type (one of the categories above)
   - Confidence score (0.0-1.0) indicating how clearly this concept appears in the text
   - Key related concepts (if any)
   - Text references (direct quotes or section references supporting this concept)
   """
   ```

### Next Steps: Expand API Integration

Now that we have successfully tested the MCP server integration with the triples extraction process, our next steps are:

1. **Full Integration with Web Application**
   - Update the GuidelineAnalysisService to use our new MCP tools
   - Enhance the web interface to display extracted concepts and relationships
   - Add visualization of the generated triples

2. **Optimization and Refinement**
   - Improve matching algorithms with feedback-based learning
   - Add caching of extracted concepts for performance improvement
   - Implement batch processing capabilities

3. **Expand Triple Generation**
   - Create more sophisticated RDF patterns for representing ethical relationships
   - Add support for additional ontology sources beyond engineering ethics
   - Implement export options for various RDF formats

## Technical Notes

- The `GuidelineAnalysisService` class is the central component for processing guidelines
- We've enhanced this service with better MCP integration rather than rewriting from scratch
- The Enhanced Ontology Server with Guidelines should be running (port 5001) with the GuidelineAnalysisModule
- We've implemented a graceful fallback to direct LLM processing when MCP is unavailable
- The MCPClient is used for all MCP server communication with improved error handling
- The server can use OpenAI embeddings when available, falling back to a simple similarity calculator otherwise
- All components follow a pattern of trying the MCP service first, then falling back to local processing

## Testing

1. **Server Testing**
   - Test script `test_guideline_mcp_client.py` verifies MCP server operations
   - Can be used for debugging MCP server issues

2. **Pipeline Testing**
   - `run_guidelines_mcp_pipeline.sh` provides end-to-end testing
   - Starts server, runs client test, and shuts down server
   - Generates output files: guideline_concepts.json, guideline_matches.json, guideline_triples.json, guideline_triples.ttl

3. **Documentation Added**
   - Created `README_GUIDELINES_TESTING.md` with comprehensive testing documentation
   - Added troubleshooting guidance for common issues

## Future Enhancements

- Allow batch processing of multiple guidelines
- Implement more sophisticated concept matching algorithms
- Add visualizations of guideline-entity relationships
- Support for comparing multiple guidelines across different engineering ethics frameworks
- Add McLaren principles integration in Phase 2
- Implement advanced semantic similarity using BERT/transformers-based embeddings
- Add cached embeddings to improve performance and reduce API costs
- Support for categorized concept grouping in the UI
