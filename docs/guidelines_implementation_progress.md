# Guidelines Feature Implementation Progress

## Overview

The Guidelines Feature allows users to upload, process, and analyze ethical guidelines documents, extracting key concepts that match with the engineering ethics ontology. This document synthesizes the current implementation status and progress based on the most recent development work.

## Current Status (Updated: 2025-05-14)

### Core Functionality

- ✅ **Guidelines Upload**: Implemented basic upload functionality through file, text, and URL methods
- ✅ **Concept Extraction**: Successfully extracting concepts from guidelines using Claude 3.7 Sonnet
- ✅ **Ontology Matching**: Matching extracted concepts to ontology entities
- ✅ **Triple Generation**: Generating RDF triples from guideline concepts in Turtle format
- ✅ **Web Interface**: Enhanced UI for guidelines display and concept review

### MCP Server Integration

- ✅ **Enhanced Server**: Implemented enhanced ontology server with GuidelineAnalysisModule
- ✅ **JSON-RPC Communication**: Fixed server connectivity using JSON-RPC endpoints
- ✅ **Model Updates**: Updated all Claude model references to claude-3-7-sonnet-20250219
- ✅ **Pipeline Testing**: Created end-to-end testing pipeline for verification
- ✅ **Client Error Handling**: Added comprehensive error handling for connection failures

### GitHub Codespaces Support

- ✅ **Database Configuration**: Fixed PostgreSQL setup for Codespaces environment
- ✅ **Startup Scripts**: Updated startup scripts for automatic configuration
- ✅ **Environment Detection**: Added automatic environment detection
- ✅ **Documentation**: Created comprehensive documentation for Codespaces operation

### In Progress

- 🔄 **Concept Review Interface**: Refining the UI for better user experience
- 🔄 **Web Service Integration**: Implementing GuidelineAnalysisService connection to MCP
- 🔄 **Semantic Matching**: Improving ontology entity matching with better algorithms
- 🔄 **Error Handling**: Enhancing diagnostics and error recovery

## Architecture

The guidelines feature follows a modular architecture with distinct components:

### Data Model

- **Guidelines Storage**: Multiple guidelines are stored in the `Document` model
  - `document_type` is set to "guideline"
  - `world_id` links the document to a specific world
  - Different types of guidelines are supported:
    - File uploads: stored with `file_path` and `file_type`
    - URLs: stored with `source` field
    - Text: stored with `content` field

### RDF Knowledge Representation

- **Triple Structure**: Guidelines are represented as RDF triples in the `guideline_triples.ttl` file
  - Uses standard ontology prefixes (rdf, rdfs, owl, xsd, dc)
  - Custom prefixes: `proeth` (http://proethica.org/ontology/) and `guide` (http://proethica.org/guidelines/)
  - Each concept is modeled with consistent properties:
    - `rdf:type` - Indicates concept type (Principle, Obligation, Action, etc.)
    - `rdfs:label` - Human-readable name
    - `dc:description` - Detailed description
    - `proethica:hasCategory` - Classification (principle, obligation, value, etc.)
    - `proethica:hasReference` - Links to reference text sources
    - `proethica:relatedTo` - Connections to other concepts

- **Concept Types**: The system models various ethical concept types:
  - Principles (e.g., "Public Safety and Welfare")
  - Obligations (e.g., "Whistleblowing")
  - Values (e.g., "Professional Judgment")
  - Actions (e.g., "Risk Assessment")
  - Stakeholders (e.g., "Public", "Employers and Clients")
  - Considerations (e.g., "Environmental Impact")
  - Constraints (e.g., "Conflict of Interest")

### User Interface Components

- **Guideline Content Page** (`app/templates/guideline_content.html`): Contains the "Analyze Concepts" button that initiates the concept extraction process.
- **Extracted Concepts Review Page** (`app/templates/guideline_extracted_concepts.html`): Displays the extracted concepts for user review and selection.
- **Concepts Review Page** (`app/templates/guideline_concepts_review.html`): An alternative, more robust template for reviewing and selecting extracted concepts.

### Routes

- **Fix Concept Extraction** (`app/routes/fix_concept_extraction.py`): Provides routes for extracting concepts with improved error handling and fallback mechanisms.
- **Direct Concept Extraction** (`app/routes/worlds_direct_concepts.py`): Contains the direct concept extraction implementation that bypasses extensive processing to just show extracted concepts.
- **Extract-Only Logic** (`app/routes/worlds_extract_only.py`): Provides routes for extracting concepts directly from guidelines without requiring entity integration.

### Services

- **Guideline Analysis Service** (`app/services/guideline_analysis_service.py`): The core service that handles the extraction and processing of concepts.
- **MCP Client** (`app/services/mcp_client.py`): Provides communication with the Model Context Protocol server for enhanced concept extraction.
- **LLM Utils** (`app/utils/llm_utils.py`): Utilities for interacting with Large Language Models for concept extraction.
- **Guidelines Agent** (`app/services/agents/guidelines_agent.py`): Specialized agent for retrieving and analyzing guidelines for ethical decision-making.
  - Extends the BaseAgent class with guideline-specific capabilities
  - Uses embedding similarity search to find relevant guidelines
  - Leverages LangChain with Claude to analyze guidelines in the context of decisions
  - Provides detailed analysis of how decision options align with ethical guidelines
  - Returns alignment scores, reasoning, and applicable guideline principles

### MCP Server Components

- **Base Module System** (`MCPBaseModule` class): Provides the foundation for MCP modules.
- **Guideline Analysis Module** (`GuidelineAnalysisModule` class): Implements guideline-specific tools.
- **Enhanced Ontology Server**: JSON-RPC endpoint for guideline analysis.

### Tools Provided by the Guideline Analysis Module

- `extract_guideline_concepts`: Extract key concepts from guideline content
- `match_concepts_to_ontology`: Match extracted concepts to ontology entities
- `generate_concept_triples`: Generate RDF triples for selected concepts

## Implementation Flow

The concept extraction process follows this flow:

1. **User Initiates Analysis**: User clicks the "Analyze Concepts" button on the guideline content page.
2. **Route Handling**: The request is processed by `extract_and_display_concepts` in `fix_concept_extraction.py`, which delegates to the direct extraction function.
3. **Concept Extraction**: The `GuidelineAnalysisService.extract_concepts()` method is called, which:
   - First attempts to use the MCP server for concept extraction
   - Falls back to direct LLM processing if MCP is unavailable
   - Provides mock concepts as a last resort if both MCP and LLM are unavailable
4. **Display Results**: The extracted concepts are rendered in the template for user review.
5. **User Selection**: The user reviews the extracted concepts and selects which ones to include.
6. **Triple Generation**: When the user submits the selection, the `generate_triples()` method creates RDF triples for the selected concepts.
7. **Save to Database**: The generated triples are saved to the knowledge graph.

## Key Implementation Improvements

### 1. Enhanced MCP Integration

The `GuidelineAnalysisService` now integrates with the MCP server using JSON-RPC:

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

### 2. LLM Model Updates

All Claude model references have been updated to use Claude 3.7 Sonnet:

```python
preferred_model = os.getenv('CLAUDE_MODEL_VERSION', 'claude-3-7-sonnet-20250219')
```

### 3. Fallback Mechanism

A comprehensive fallback system ensures functionality even when services are unavailable:

```
MCP Server → Direct LLM → Mock Concepts
```

### 4. Mock Concept Generation

When both MCP and LLM are unavailable, the system generates mock concepts based on guideline content:

```python
def _generate_mock_concepts_from_content(self, content: str) -> List[Dict[str, Any]]:
    """
    Generate mock concepts based on guideline content.
    Uses simple regex patterns to identify potential concepts.
    """
    mock_concepts = []
    concept_id = 0
    
    # Convert content to lowercase for case-insensitive matching
    lowercase_content = content.lower()
    
    # Define common ethical engineering principles and their descriptions
    common_principles = {
        "public safety": "The paramount consideration for engineers to protect the public health, safety, and welfare",
        "integrity": "Upholding ethical standards and being honest in all professional activities",
        # Additional principles...
    }
    
    # Check for common principles in the content
    for principle, description in common_principles.items():
        if principle in lowercase_content:
            mock_concepts.append({
                "id": concept_id,
                "label": principle.title(),
                "description": description,
                "type": "principle",
                "confidence": 0.9
            })
            concept_id += 1
    
    # Additional concept generation logic...
    
    return mock_concepts
```

### 5. MCPClient JSON-RPC Communication

Updated the `MCPClient` to use JSON-RPC for more reliable communication:

```python
def check_connection(self) -> bool:
    """Check if the MCP server is running and accessible."""
    # Try JSON-RPC endpoint with proper POST request
    jsonrpc_endpoint = f"{self.mcp_url}/jsonrpc"
    try:
        # Use POST with proper JSON-RPC request format
        response = self.session.post(
            jsonrpc_endpoint, 
            json={
                "jsonrpc": "2.0",
                "method": "list_tools",
                "params": {},
                "id": 1
            },
            timeout=5
        )
        
        if response.status_code == 200:
            return True
    except Exception as e:
        print(f"Error checking JSON-RPC endpoint: {str(e)}")
    
    return False
```

## Recent Development Achievements

- Fixed the incomplete `generate_triples` method in `GuidelineAnalysisService` class
- Updated MCP client to use JSON-RPC for more reliable server communication
- Created comprehensive documentation for Codespaces operation
- Implemented the GUI for concept review and selection
- Added fallback mechanisms when MCP or LLM services are unavailable
- Resolved Flask template routing issues related to blueprint naming
- Created end-to-end testing tools for validating the guideline analysis pipeline
- Improved error handling throughout the extraction and matching process

## Technical Notes

- The system now uses Claude 3.7 Sonnet (claude-3-7-sonnet-20250219) for all LLM operations
- The Enhanced Ontology Server with Guidelines should be running on port 5001
- All components follow a pattern of trying the MCP service first, then falling back to local processing
- In GitHub Codespaces, the PostgreSQL database runs on port 5433
- The system supports URL, file, and direct text input for guidelines

## Runtime Environment

### Standard Environment

To run the application with guidelines support:

```bash
# Start the application with enhanced server
./start_with_enhanced_ontology_server.sh
```

This script will:
1. Start the enhanced ontology server with guidelines module
2. Check the database schema
3. Start the Flask web application

### GitHub Codespaces Environment

```bash
# Start the application in Codespaces
./start_proethica_updated.sh
```

The Codespaces environment automatically:
1. Configures the PostgreSQL database with proper credentials
2. Starts the MCP server for guidelines integration
3. Launches a debug version of the Flask application

## Testing

### JSON-RPC Communication

Test the JSON-RPC endpoint:

```bash
curl -X POST http://localhost:5001/jsonrpc -H "Content-Type: application/json" \
-d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}'
```

### Full Pipeline Testing

Run the guidelines MCP pipeline test:

```bash
./run_guidelines_mcp_pipeline.sh
```

This will:
1. Load a test guideline
2. Extract concepts using the LLM
3. Match concepts to ontology entities
4. Generate RDF triples
5. Save results to JSON and Turtle files

### Testing through the UI

1. Navigate to a world detail page
2. Click on the "Guidelines" tab
3. Use the "Add Guideline" button to upload or create a guideline
4. View the guideline and click "Analyze Concepts"
5. Review the extracted concepts
6. Select concepts and click "Save Selected Concepts"
7. View the generated triples in the "RDF Knowledge" section
