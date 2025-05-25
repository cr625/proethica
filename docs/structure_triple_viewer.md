# Structure Triple Viewer

## Overview

The Structure Triple Viewer provides a user-friendly interface for viewing RDF triples generated from case documents. It offers both a formatted view for easy human comprehension and a raw view for technical inspection.

## Features

### 1. Formatted View (Default)
- **Document Information**: Displays case number, title, and year
- **Section Overview**: Shows each document section with:
  - Content preview (first 200 characters)
  - Full content length
  - Number of items within the section
  - Item details (questions, conclusions, references)
- **Statistics**: Total triples, entities, and sections

### 2. Raw View
- Complete RDF triples in Turtle format
- Copy-to-clipboard functionality
- Preserves exact ontology structure

### 3. LLM-Friendly Format
- Hidden div containing a text format optimized for LLM consumption
- Structured summary of document sections
- Useful for similarity analysis and LLM reasoning

## Implementation Details

### Backend Components
- `StructureTripleFormatter` service: Parses RDF triples and extracts structured data
- Integrated into `document_structure.py` route
- Uses ProEthica intermediate ontology concepts

### Frontend Components
- `structure-triples-viewer.js`: JavaScript class for view management
- `structure-viewer.css`: Styling for the viewer
- Bootstrap-based responsive design

## Usage for Similarity Analysis

The structured triples are designed to be useful for:

1. **Section-level similarity**: Each section has clear boundaries and content
2. **Semantic search**: Triples capture document structure semantically
3. **Cross-case comparison**: Standardized format enables comparison
4. **LLM integration**: The LLM-friendly format provides context for reasoning

## Example Output

```
Case 21-11 (2021)
Title: Public Welfare at What Cost?

Document Structure:

Facts:
  (No content available)

Discussion:
  Content preview: Engineer Intern D's adherence to DOT policy...
  (Full content: 6199 characters)

Questions:
  Contains 2 items:
    - Question: Would it be ethical for Engineer Intern D...
    - Question: Would it be unethical for Engineer W...

Conclusion:
  Contains 2 items:
    - Conclusion Item: It would not be ethical...
    - Conclusion Item: It would not be ethical...

References:
  Content preview: I.3. Issue public statements...
  (Full content: 2755 characters)
  Contains 42 items
```

## Future Enhancements

1. Add filtering options to show/hide specific triple types
2. Implement search within triples
3. Add export functionality for different formats (JSON-LD, N-Triples)
4. Integrate with ontology visualization tools