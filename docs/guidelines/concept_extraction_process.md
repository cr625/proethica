# Guideline Concept Extraction Process

## Overview
This document details the current concept extraction process and identifies areas for improvement.

## Current Process Flow

### 1. Input Processing
```python
# Guideline sources
- File upload (PDF, TXT, DOC)
- URL (web scraping)
- Direct text input
```

### 2. Concept Extraction Pipeline

#### Phase 1: Text Analysis
1. **Document Loading** - Raw text extraction from various formats
2. **LLM Analysis** - Claude/OpenAI analyzes text for ethical concepts
3. **Structured Output** - JSON format with standardized fields:
   ```json
   {
     "id": "unique-identifier",
     "label": "Concept Name",
     "description": "Detailed description",
     "category": "principle|obligation|role|...",
     "related_concepts": ["concept1", "concept2"],
     "text_references": ["quote from guideline"]
   }
   ```

#### Phase 2: Ontology Matching
1. **Embedding Generation** - Create vector embeddings for concepts
2. **Similarity Search** - Find similar concepts in existing ontology
3. **Match Scoring** - Calculate confidence scores for matches
4. **User Review** - Present matches for confirmation

### 3. Storage and Association
1. **Concept Storage** - Save selected concepts to database
2. **World Association** - Link concepts to Engineering World
3. **Guideline Linking** - Maintain relationship to source guideline

## Current Implementation Details

### LLM Prompts
```python
EXTRACT_CONCEPTS_PROMPT = """
Analyze the following ethics guideline text and extract key concepts...
Categories: principle, obligation, role, condition, resource, action, event, capability
```

### MCP Server Tools
- `extract_guideline_concepts` - Main extraction tool
- `match_concepts_to_ontology` - Find existing ontology matches
- `get_ontology_structure` - Understand ontology hierarchy

### Fallback Mechanisms
1. Try MCP server (preferred)
2. Fall back to direct LLM API
3. Use mock data if all else fails

## Areas for Improvement

### 1. Enhanced Category Detection
**Current**: Simple category assignment
**Proposed**: 
- Multi-label classification (concepts can belong to multiple categories)
- Hierarchical categorization (sub-categories)
- Context-aware category assignment

### 2. Improved Text Reference Extraction
**Current**: Basic quote extraction
**Proposed**:
- Maintain paragraph/section context
- Link to specific guideline sections
- Support for cross-references

### 3. Concept Relationship Discovery
**Current**: Manual related_concepts list
**Proposed**:
- Automatic relationship inference
- Typed relationships (requires, enables, conflicts_with)
- Confidence scoring for relationships

### 4. Interactive Extraction
**Current**: Single-pass extraction
**Proposed**:
- Iterative refinement with user feedback
- Real-time ontology querying during extraction
- Concept disambiguation interface

## Technical Improvements

### 1. Native Claude Tool Use
```python
# Current: Simple prompt
response = claude.complete(prompt=EXTRACT_CONCEPTS_PROMPT)

# Proposed: Tool-calling
tools = [
    query_ontology_tool,
    check_concept_exists_tool,
    suggest_relationships_tool
]
response = claude.complete(prompt=prompt, tools=tools)
```

### 2. Batch Processing
- Process multiple guidelines simultaneously
- Detect cross-guideline patterns
- Merge duplicate concepts

### 3. Validation Pipeline
- Concept completeness checks
- Consistency validation
- Ontology conflict detection

## Next Steps
1. Implement native Claude tool-calling
2. Enhance category detection algorithm
3. Build interactive extraction interface
4. Add validation pipeline
5. Create batch processing capabilities