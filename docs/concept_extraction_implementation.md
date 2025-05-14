# Guideline Concept Extraction Implementation

## Overview

This document outlines the implementation of the concept extraction feature for guidelines in the AI Ethical DM system. This feature allows users to analyze ethical guidelines and extract key concepts, which can then be integrated into the knowledge graph as RDF triples.

## Architecture

The guideline concept extraction feature involves several components:

### 1. User Interface Components

- **Guideline Content Page** (`app/templates/guideline_content.html`): Contains the "Analyze Concepts" button that initiates the concept extraction process.
- **Extracted Concepts Review Page** (`app/templates/guideline_extracted_concepts.html`): Displays the extracted concepts for user review and selection.
- **Concepts Review Page** (`app/templates/guideline_concepts_review.html`): An alternative, more robust template for reviewing and selecting extracted concepts.

### 2. Routes

- **Fix Concept Extraction** (`app/routes/fix_concept_extraction.py`): Provides routes for extracting concepts with improved error handling and fallback mechanisms.
- **Direct Concept Extraction** (`app/routes/worlds_direct_concepts.py`): Contains the direct concept extraction implementation that bypasses extensive processing to just show extracted concepts.
- **Extract-Only Logic** (`app/routes/worlds_extract_only.py`): Provides routes for extracting concepts directly from guidelines without requiring entity integration.

### 3. Services

- **Guideline Analysis Service** (`app/services/guideline_analysis_service.py`): The core service that handles the extraction and processing of concepts.
- **MCP Client** (`app/services/mcp_client.py`): Provides communication with the Model Context Protocol server for enhanced concept extraction.
- **LLM Utils** (`app/utils/llm_utils.py`): Utilities for interacting with Large Language Models for concept extraction.

## Flow

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

## Implementation Details

### Concept Extraction Methods

The system uses a multi-layer approach to concept extraction:

1. **MCP Server Extraction**: Uses the JSON-RPC endpoint of the MCP server to extract concepts.
2. **Direct LLM Processing**: Uses the LLM directly when the MCP server is unavailable.
3. **Mock Concept Generation**: Generates mock concepts based on pattern matching when both MCP and LLM are unavailable.

### Fallback Mechanism

The fallback mechanism ensures that the concept extraction feature always provides results, even when services are unavailable:

```
MCP Server → Direct LLM → Mock Concepts
```

### LLM Integration

The service support multiple LLM client APIs:

- Anthropic API v2+ (preferred)
- OpenAI API
- Anthropic API v1.x (legacy)

### Error Handling

The system includes robust error handling:

- Timeouts for API calls to prevent hanging requests
- Error propagation from MCP server to client
- Clear error messages when services are unavailable
- Always providing mock concepts as a fallback

## Configuration

Relevant configuration options:

- `ANTHROPIC_API_KEY`: API key for the Anthropic Claude models
- `CLAUDE_MODEL_VERSION`: Preferred Claude model version
- `MCP_SERVER_URL`: URL of the MCP server

## Troubleshooting

Common issues and solutions:

### 1. Template Rendering Errors

**Issue**: Error in templates with URL routing using old format (`url_for('index')` instead of `url_for('index.index')`).

**Solution**: Ensure all templates use the blueprint-prefixed format for URL endpoints.

### 2. LLM Connection Issues

**Issue**: Error connecting to the LLM service.

**Solution**: 
- Verify the API key is set in the environment variables
- Run `test_llm_connection.py` to diagnose connection issues
- Check the model availability in the LLM client

### 3. MCP Server Connection Issues

**Issue**: Cannot connect to the MCP server.

**Solution**:
- Verify the MCP server is running
- Check the MCP server URL configuration
- Look for error messages in the MCP server logs

## Testing

To test the concept extraction feature:

1. Navigate to a guideline page (e.g., `/worlds/1/guidelines/189`)
2. Click the "Analyze Concepts" button
3. Verify that concepts are extracted and displayed
4. Select concepts and save them
5. Verify that the selected concepts appear on the guideline page

## Future Improvements

Planned improvements for the feature:

1. Add concept filtering options to help users focus on specific concept types
2. Improve matching with ontology entities for better integration
3. Add real-time feedback during the extraction process
4. Implement concept clustering to group related concepts
5. Add support for concept extraction from multiple guidelines simultaneously
