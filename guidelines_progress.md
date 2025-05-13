# Guidelines Feature Implementation Progress

## Overview
This document tracks the implementation of the guidelines feature for the AI Ethical DM application. The feature allows uploading guidelines associated with a world and linking them to RDF triples from the engineering-ethics ontology.

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

### In Progress
- 🔄 Testing guideline concept extraction and entity matching
- 🔄 Refining the concept review interface
- 🔄 Enhancing error handling and server diagnostics
- 🔄 Implementing integration with app's GuidelineAnalysisService

### Planned
- 📅 Complete concept extraction and matching implementation
- 📅 Implement RDF triple association with guidelines
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

### Phase 2: Concept Matching Enhancement

1. **Direct Use of MCP Guidelines Module**
   ```python
   def match_concepts(self, concepts: List[Dict[str, Any]], ontology_source: Optional[str] = None) -> Dict[str, Any]:
       """Match concepts to ontology entities with improved MCP integration."""
       try:
           # Try to use the MCP server's match_concepts_to_ontology tool directly
           response = requests.post(
               f"{self.mcp_client.mcp_url}/jsonrpc",
               json={
                   "jsonrpc": "2.0",
                   "method": "call_tool",
                   "params": {
                       "name": "match_concepts_to_ontology",
                       "arguments": {
                           "concepts": concepts,
                           "ontology_source": ontology_source,
                           "match_threshold": 0.6
                       }
                   },
                   "id": 1
               },
               timeout=30
           )
           
           if response.status_code == 200:
               # Process and return the matches
               result = response.json()
               if "result" in result:
                   return result["result"]
           
           # Fall back to LLM-based matching if MCP fails
       except Exception as e:
           logger.warning(f"Error calling MCP: {str(e)}, falling back to LLM")
   ```

### Phase 3: Triple Generation Enhancement

1. **Improved Triple Generation**
   ```python
   def generate_triples(self, concepts: List[Dict[str, Any]], selected_indices: List[int], 
                       ontology_source: Optional[str] = None) -> Dict[str, Any]:
       """Generate RDF triples for selected concepts."""
       # Try MCP server first
       try:
           response = requests.post(
               f"{self.mcp_client.mcp_url}/jsonrpc",
               json={
                   "jsonrpc": "2.0",
                   "method": "call_tool",
                   "params": {
                       "name": "generate_concept_triples",
                       "arguments": {
                           "concepts": concepts,
                           "selected_indices": selected_indices,
                           "ontology_source": ontology_source,
                           "namespace": "http://proethica.org/guidelines/",
                           "output_format": "turtle"
                       }
                   },
                   "id": 1
               },
               timeout=20
           )
           
           if response.status_code == 200:
               return response.json().get("result", {})
       except Exception as e:
           logger.warning(f"Error using MCP for triple generation: {str(e)}")
       
       # Fall back to direct implementation
   ```

## Technical Notes

- The `GuidelineAnalysisService` class is the central component for processing guidelines
- We've enhanced this service with better MCP integration rather than rewriting from scratch
- The Enhanced Ontology Server with Guidelines should be running (port 5001) with the GuidelineAnalysisModule
- We've implemented a graceful fallback to direct LLM processing when MCP is unavailable
- The MCPClient is used for all MCP server communication with improved error handling
- The server can use OpenAI embeddings when available, falling back to a simple similarity calculator otherwise
- All components follow a pattern of trying the MCP service first, then falling back to local processing

### MCP Server Components

1. **Base Module System**
   - Introduced `MCPBaseModule` class for consistent module architecture
   - Provides tools and resources registration and access methods
   - Standardized error handling for tool execution

2. **GuidelineAnalysisModule**
   - Module added to the Enhanced Ontology Server
   - Provides three main tools:
     - `extract_guideline_concepts`: Extract concepts from guideline content
     - `match_concepts_to_ontology`: Match extracted concepts to ontology entities
     - `generate_concept_triples`: Generate RDF triples from matched concepts
   - Integrates with the ontology client for entity access
   - Uses LLM and embedding clients for analysis

3. **Client Integration**
   - Updated GuidelineAnalysisService to use MCP tools
   - Added fallback to direct LLM when MCP is unavailable
   - Improved error handling and logging throughout

## Testing

1. **Server Testing**
   - Test script `debug_mcp_guideline_server.py` verifies server operation
   - Can be used for debugging MCP server issues

2. **Client Testing**
   - `test_guideline_mcp_client.py` tests direct interaction with MCP server
   - Tests all three tools independently
   - Captures JSON output for further analysis

3. **Pipeline Testing**
   - `run_guidelines_mcp_pipeline.sh` provides end-to-end testing
   - Starts server, runs client test, and shuts down server
   - Useful for integration verification

## Future Enhancements

- Allow batch processing of multiple guidelines
- Implement more sophisticated concept matching algorithms
- Add visualizations of guideline-entity relationships
- Support for comparing multiple guidelines across different engineering ethics frameworks
- Add McLaren principles integration in Phase 2
- Implement advanced semantic similarity using BERT/transformers-based embeddings
- Add cached embeddings to improve performance and reduce API costs
- Support for categorized concept grouping in the UI
