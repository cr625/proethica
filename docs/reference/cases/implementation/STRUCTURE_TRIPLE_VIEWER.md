# Structure Triple Viewer Implementation

**Status**: Implemented  
**Date**: 2025-01-24  
**Author**: Assistant

## Overview

The Structure Triple Viewer provides a user-friendly interface for viewing and understanding RDF triples generated from case documents. It replaces the raw triple display with an interactive, organized view that combines section metadata with document structure.

## Key Components

### 1. Structure Triple Formatter (`app/services/structure_triple_formatter.py`)

Parses RDF triples in Turtle format and extracts structured information:

```python
formatter = StructureTripleFormatter()
structured_data = formatter.parse_triples(turtle_string)
```

Returns:
- `document_info`: Case number, title, year
- `section_items`: All items (facts, questions, conclusions, etc.) with full content
- `statistics`: Triple counts and entity breakdowns
- `raw_triples`: Original turtle string

### 2. JavaScript Viewer (`app/static/js/structure-triples-viewer.js`)

Interactive client-side component:

```javascript
structureTriplesViewer = new StructureTriplesViewer('container-id', structuredData);
```

Features:
- Toggle between formatted and raw views
- Copy-to-clipboard for raw triples
- Grouped display by section type
- Responsive design

### 3. Enhanced Document Structure Annotation

The `DocumentStructureAnnotationStep` now breaks down all sections into semantic items:

#### Facts Section
- Individual `FactStatement` items
- Intelligent sentence grouping (combines pronoun-starting sentences)
- Sequence numbers for ordering

#### Discussion Section  
- `DiscussionSegment` items with semantic types:
  - `ethical_analysis`: Ethical reasoning
  - `reasoning`: Logical arguments
  - `code_reference`: Standards references
  - `general`: Other content

## Usage

### In Routes (`app/routes/document_structure.py`)

```python
# Format structure triples if available
structured_triples_data = None
if has_structure and structure_triples:
    formatter = StructureTripleFormatter()
    structured_triples_data = formatter.parse_triples(structure_triples)
```

### In Templates

```html
{% if structured_triples_data %}
<div id="structure-triples-viewer"></div>
<script src="{{ url_for('static', filename='js/structure-triples-viewer.js') }}"></script>
<script>
    const structuredData = {{ structured_triples_data | tojson | safe }};
    structureTriplesViewer = new StructureTriplesViewer('structure-triples-viewer', structuredData);
</script>
{% endif %}
```

## Display Format

### Unified Section View

Each section displays its items in a consistent format:

```
[Section Name]
──────────────
item_id    [Type Badge]    [Segment Type Badge]    URI
Full content text displayed below...
```

Example:
```
Questions
─────────
question_1    Question    http://proethica.org/document/case_21_4/question_1
Is he obligated to reveal his condition to his clients?

question_2    Question    http://proethica.org/document/case_21_4/question_2  
Should he refrain from accepting engineering work until he is fully recovered?
```

## Technical Details

### Triple Types Added

```turtle
# Fact statements
<case_uri/fact_1> a proethica:FactStatement ;
    proethica:hasTextContent "Engineer C owns a consulting firm." ;
    proethica:hasSequenceNumber 1 ;
    proethica:isPartOf <case_uri/facts> .

# Discussion segments  
<case_uri/discussion_segment_1> a proethica:DiscussionSegment ;
    proethica:hasTextContent "Engineers have ethical duties..." ;
    proethica:hasSegmentType "ethical_analysis" ;
    proethica:hasSequenceNumber 1 ;
    proethica:isPartOf <case_uri/discussion> .
```

### Clean Text Extraction

All text content is cleaned before storage:
- HTML tags removed from semantic predicates
- Original HTML preserved in `hasHtmlContent` 
- Plain text used for embeddings and display

## Benefits

1. **User-Friendly**: No need to understand RDF/Turtle syntax
2. **Searchable**: Granular items enable precise similarity matching
3. **LLM-Ready**: Structured format ideal for AI reasoning
4. **Consistent**: All sections follow same display pattern
5. **Semantic**: Discussion segments classified by content type

## Files Modified

- `/app/services/structure_triple_formatter.py` - New formatter service
- `/app/services/case_processing/pipeline_steps/document_structure_annotation_step.py` - Enhanced annotation
- `/app/static/js/structure-triples-viewer.js` - New JavaScript viewer
- `/app/static/css/structure-viewer.css` - Viewer styles
- `/app/routes/document_structure.py` - Route integration
- `/app/templates/document_structure.html` - Template updates