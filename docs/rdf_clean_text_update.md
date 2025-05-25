# RDF Triple Clean Text Update

## Overview

Updated the document structure annotation step to use clean plain text for RDF triple generation, specifically for the `hasTextContent` predicate, while preserving HTML content in `hasHtmlContent` predicate.

## Problem

Previously, RDF triples for document sections used HTML content for both `hasTextContent` and `hasHtmlContent` predicates. This resulted in HTML tags appearing in the triple display, making them difficult to read and less useful for semantic reasoning.

## Solution

Modified the document structure annotation pipeline to:
1. Accept clean text versions from the NSPE extraction step
2. Use plain text for `hasTextContent` predicates
3. Keep HTML for `hasHtmlContent` predicates
4. Handle both plain text and HTML in code reference extraction

## Changes Made (2025-01-24)

### 1. Document Structure Annotation Step Updates

#### Modified `process()` method:
```python
sections_text = input_data.get('sections_text', {})  # Get clean text versions
structure_graph = self._create_structure_graph(
    document_uri, case_number, year, title, 
    sections, questions_list, conclusion_items,
    sections_text  # Pass clean text versions
)
```

#### Updated `_create_structure_graph()` method:
- Added `sections_text` parameter
- For each section, uses clean text for `hasTextContent`:
```python
text_content = sections_text.get('facts', sections['facts']) if sections_text else sections['facts']
g.add((facts_uri, PROETHICA.hasTextContent, Literal(text_content)))
g.add((facts_uri, PROETHICA.hasHtmlContent, Literal(sections['facts'])))
```

#### Enhanced `_extract_code_references()` method:
- Now handles both HTML and plain text input
- Detects format automatically
- Extracts references from numbered/bulleted lists in plain text

## Result

RDF triples now have clean, readable text content:

### Before:
```turtle
:discussion proethica:hasTextContent "<p>The engineer must <a href='/case/123'>consider</a> all <strong>relevant</strong> factors...</p>"
```

### After:
```turtle
:discussion proethica:hasTextContent "The engineer must consider all relevant factors..."
:discussion proethica:hasHtmlContent "<p>The engineer must <a href='/case/123'>consider</a> all <strong>relevant</strong> factors...</p>"
```

## Benefits

1. **Cleaner RDF Display**: Triples are more readable without HTML tags
2. **Better Semantic Reasoning**: Plain text is more suitable for ontology reasoning
3. **Preserved Formatting**: HTML still available in `hasHtmlContent` for display
4. **Backward Compatible**: Works with legacy data that only has HTML

## Testing

To test the changes:
1. Process a new case through the pipeline
2. View the document structure page
3. Check that RDF triples show clean text in `hasTextContent`
4. Verify HTML is preserved in `hasHtmlContent`

## Integration with Dual Text Extraction

This update works seamlessly with the dual text extraction feature:
- NSPE extraction provides `sections_text`
- Document structure annotation uses it for clean triples
- Section embeddings use the same clean text
- Everything is optimized for semantic processing