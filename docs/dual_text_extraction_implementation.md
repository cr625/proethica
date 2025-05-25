# Dual Text Extraction Implementation

## Overview

Updated the case processing pipeline to extract and store both HTML and plain text versions of case sections. This optimizes similarity matching by using clean text for embeddings while preserving formatted HTML for display.

## Changes Made (2025-01-24)

### 1. NSPE Extraction Step Updates (`nspe_extraction_step.py`)

#### Added `extract_text_only()` Method
Extracts clean plain text from HTML while preserving semantic structure:
- Removes all HTML tags and attributes
- Preserves list structure with markers (1., 2., •)
- Maintains paragraph breaks for readability
- Cleans up HTML entities (&amp; → &, etc.)

#### Updated `process()` Method
Now returns three formats:
```python
{
    'sections': {...},           # Original HTML (backward compatibility)
    'sections_dual': {           # New dual format
        'facts': {
            'html': '<p>...</p>',
            'text': 'Plain text...'
        },
        // ... other sections
    },
    'sections_text': {...}       # Convenience text-only access
}
```

### 2. Document Structure Annotation Updates

Updated `_prepare_section_embedding_metadata_v2()` to:
- Check for `sections_text` in input data
- Use plain text version when available
- Add `content_type` field to track text vs HTML

### 3. Route Updates (`cases.py`)

Updated metadata storage to include:
- `sections_dual`: Complete dual format data
- `sections_text`: Text-only versions for quick access

### 4. Section Embedding Service Updates

#### Updated `generate_section_embeddings()`
- Checks `content_type` field in metadata
- Logs whether using text or HTML for embeddings

#### Updated `process_document_sections()`
- Prioritizes text versions from dual format
- Falls back to HTML for legacy data
- Handles all existing metadata formats

## Benefits

1. **Better Similarity Scores**
   - No HTML noise in embeddings
   - Consistent text representation
   - More accurate semantic matching

2. **Flexibility**
   - HTML preserved for rich display
   - Plain text optimized for NLP tasks
   - Backward compatible with existing data

3. **Performance**
   - Smaller embedding vectors (no HTML tags)
   - Faster similarity calculations
   - Better use of vector space

## Usage

### Processing New Cases
When cases are processed through the pipeline, both versions are automatically extracted and stored.

### Accessing Text Versions
```python
# In routes or services
text_content = metadata['sections_text']['facts']
# or
text_content = metadata['sections_dual']['facts']['text']
```

### Embedding Generation
The embedding service automatically uses text versions when available:
```python
# Automatic selection in section_embedding_service.py
if has_dual_format and 'sections_text' in doc_metadata:
    content = doc_metadata['sections_text'][section_id]
    content_type = 'text'
```

## Migration Notes

- Existing 20 cases can be reimported through the pipeline
- No database schema changes required
- Backward compatible with legacy single-format data

## Testing Recommendations

1. Process a new case URL and verify:
   - Both HTML and text versions are stored
   - Embeddings use text version
   - Display still shows formatted HTML

2. Compare similarity scores:
   - Test searches before/after reimport
   - Should see improved relevance

3. Verify backward compatibility:
   - Legacy cases still work
   - Mixed old/new data handled correctly