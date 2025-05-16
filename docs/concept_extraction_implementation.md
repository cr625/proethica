# Guideline Concept Extraction Implementation

This document outlines the implementation of the guideline concept extraction feature in the AI Ethical DM system.

## Architecture Overview

The guideline concept extraction flow consists of several components:

1. **Flask Application Routes**:
   - `worlds.py`: Contains routes for managing worlds and guidelines, including the `save_guideline_concepts` function that saves selected concepts to the database
   - `worlds_direct_concepts.py`: Provides simplified routes for direct concept extraction without requiring ontology matching

2. **Service Layer**:
   - `GuidelineAnalysisService`: Interfaces with the MCP server to extract concepts and generate RDF triples

3. **MCP Server Components**:
   - `GuidelineAnalysisModule`: Implements tools for extracting concepts and generating triples using Claude
   - `enhanced_ontology_server_with_guidelines.py`: Integrates the guideline analysis module with the MCP server

4. **Database Models**:
   - `Guideline`: Stores metadata about guideline documents
   - `EntityTriple`: Stores RDF triples in subject-predicate-object format for all ontology entities, including guideline concepts

## Concept Extraction Flow

1. User uploads a guideline document to a world
2. User clicks "Extract Concepts" on the guideline
3. System sends the guideline content to the MCP server via `GuidelineAnalysisService`
4. MCP server uses Claude API to extract ethical concepts from the text
5. Extracted concepts are displayed to the user for review
6. User selects which concepts to save to the ontology
7. System generates RDF triples for the selected concepts
8. Triples are saved to the `entity_triples` table with `guideline_id` and `entity_type='guideline_concept'`

## Implementation Details

### Concept Extraction

The concept extraction is performed by Claude via the `extract_concepts` tool in the `GuidelineAnalysisModule`. The prompt asks Claude to:

1. Identify key ethical concepts, principles, and values
2. Provide a name, definition, and type for each concept
3. Format the output as a structured JSON object

### Triple Generation

For each selected concept, the system generates RDF triples using the `generate_triples` tool. These triples include:

1. Type triples (e.g., "Responsibility is_a EthicalPrinciple")
2. Description triples (e.g., "Responsibility has_description 'The ethical obligation to...'")
3. Relationship triples between concepts (e.g., "Responsibility related_to Public_Safety")

### Database Storage

Concepts are stored in the database as:

1. A `Guideline` record with metadata about the guideline document
2. Multiple `EntityTriple` records for each concept and its relationships, linked to the guideline via `guideline_id`

## Testing and Debugging

Several tools are available for testing and debugging the concept extraction flow:

1. `verify_guideline_concepts.sql`: SQL script to verify the database tables
2. `query_guideline_concepts.py`: Python script to query and display saved concepts
3. `scripts/ensure_schema.py`: Script to ensure the database has the required schema
4. `debug_unified_with_mock.sh`: Combined debug script with mock Claude responses

## Configuration

The concept extraction can be configured through:

1. Environment variables:
   - `USE_MOCK_RESPONSES`: Set to `true` to use mock responses for testing
   - `MOCK_RESPONSES_DIR`: Directory containing mock response JSON files

2. MCP server configuration:
   - `GuidelineAnalysisModule` configuration in `enhanced_ontology_server_with_guidelines.py`

## Error Handling

The system includes error handling at multiple levels:

1. Service level in `GuidelineAnalysisService` for MCP connection errors
2. Route level in `worlds.py` for database and form submission errors
3. Template level with error templates like `guideline_processing_error.html`
