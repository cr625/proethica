# Guidelines Implementation Next Steps

This document outlines the planned improvements and next steps for the guidelines concept extraction feature.

## Immediate Next Steps

### 1. ✅ Test with Live LLM Integration (Completed May 17, 2025)

#### Current Status
The guideline concept extraction feature is now working with live LLM integration. The database connection issues have been fixed by updating all configuration files to use the correct PostgreSQL credentials (using 'PASS' instead of 'postgres' for the password). The application now properly initializes using the factory pattern, ensuring all routes and templates are registered correctly.

#### Implementation Details
1. Fixed database connection strings in all launch configurations:
   ```
   postgresql://postgres:PASS@localhost:5433/ai_ethical_dm
   ```

2. Created multiple launch scripts for testing:
   - `run_with_live_llm.sh` - Script to start both MCP server and Flask app with live LLM
   - `test_flask_app_ui.sh` - Simplified script for testing the full Flask app UI

3. Fixed schema verification by properly passing the database engine to initialization functions

4. Verified the workflow functions with the live LLM integration:
   - ✅ Upload guideline document
   - ✅ Extract concepts using Claude API
   - ✅ Review and select concepts
   - ✅ Generate triples
   - ✅ Review and save triples
   - ✅ Display saved triples in the guideline view

#### Next Steps for Live LLM Integration
1. Conduct thorough testing with various guideline documents
2. Analyze the quality of concepts extracted by the live Claude API
3. Compare performance and results between mock data and live API
4. Document any differences or issues discovered during testing

## 2. Upgrade to Native Claude Tool Use

### Current Approach
Currently, the guideline concept extraction uses simple prompts with Claude to extract ethical concepts and generate RDF triples. While functional, this approach doesn't allow Claude to dynamically access the ontology during extraction.

### Planned Improvement
Implement native Claude tool use to allow the model to:
- Query the existing ontology in real-time while extracting concepts
- Look up ontology entities to match extracted concepts with existing ones
- Generate better-aligned triples based on ontology knowledge

### Implementation Steps
1. Modify the `GuidelineAnalysisModule` to define Claude tools:
   ```python
   tools = [
       {
           "name": "query_ontology",
           "description": "Query the ontology for existing concepts",
           "parameters": {...}
       },
       {
           "name": "search_similar_concepts",
           "description": "Find concepts in the ontology similar to an extracted concept",
           "parameters": {...}
       }
   ]
   ```

2. Update the `extract_concepts` method to use tool-calling:
   ```python
   messages = [
       {"role": "system", "content": system_prompt},
       {"role": "user", "content": f"Analyze the following guideline: {content}"}
   ]
   response = self.anthropic_client.messages.create(
       model="claude-3-opus-20240229",
       messages=messages,
       tools=tools,
       tool_choice="auto",
       max_tokens=4000
   )
   ```

3. Implement tool handlers in the module to process Claude's tool calls

## 3. Enhance Ontology Alignment

### Current Approach
The current system extracts concepts but has limited ability to align them with the existing ontology structure.

### Planned Improvement
Create better ontology alignment through:
- Improved matching of extracted concepts to existing ontology entities
- Hierarchical placement of new concepts in the ontology
- Better relationship mapping between new and existing concepts

### Implementation Steps
1. Create an ontology mapping service that uses embedding similarity
2. Implement hierarchical placement suggestions for new concepts
3. Add UI components to show ontology alignment options

## 4. Improve User Review Interface

### Current Approach
The current interface shows extracted concepts in a simple list for selection.

### Planned Improvement
Enhance the user review interface to:
- Visualize concept relationships
- Show conflicts with existing concepts
- Allow editing of concepts before saving
- Provide interactive graph visualization

### Implementation Steps
1. Update `guideline_concepts_review.html` with interactive visualization
2. Add concept editing capabilities to the review page
3. Implement conflict detection and resolution UI

## 5. Enable Batch Processing

### Current Approach
Guidelines can only be processed individually, which is inefficient for organizations with many documents.

### Planned Improvement
Implement batch processing to:
- Extract concepts from multiple guidelines simultaneously
- Compare concepts across multiple documents
- Identify common themes and principles

### Implementation Steps
1. Add batch selection UI in `guidelines.html`
2. Create a batch processing queue in the background task system
3. Implement a batch review interface

## 6. Add Ontology Impact Analysis

### Current Approach
There's no way to preview how adding new concepts will impact the existing ontology.

### Planned Improvement
Implement ontology impact analysis to:
- Preview changes before saving
- Highlight potential inconsistencies
- Suggest refinements to the ontology

### Implementation Steps
1. Create an ontology diff visualization
2. Implement consistency checking algorithms
3. Add an impact preview step before saving

## 7. Implement Concept Versioning

### Current Approach
Concepts are saved without version history, making it difficult to track changes over time.

### Planned Improvement
Add concept versioning to:
- Track changes to concepts over time
- Support rollback to previous versions
- Show evolution of ethical understanding

### Implementation Steps
1. Extend the `entity_triples` model to include version information
2. Update the save flow to handle versioning
3. Create a version history UI

## 8. Integrate with Simulation System

### Current Approach
Extracted concepts exist separately from the simulation system.

### Planned Improvement
Integrate with the simulation system to:
- Use extracted principles in simulations
- Test ethical scenarios against guideline principles
- Validate simulations against guidelines

### Implementation Steps
1. Create bridge between guideline concepts and simulation models
2. Implement guideline validation for simulations
3. Add guideline reference in simulation reports
