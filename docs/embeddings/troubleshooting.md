# Section Embeddings Troubleshooting

## Common Issues and Solutions

### 1. "'str' object has no attribute 'keys'" Error

**Problem**: When clicking "Generate Section Embeddings", the system crashes with an AttributeError because it expects `sections` to be a dictionary but finds a string instead.

**Root Cause**: Some documents may have malformed metadata where the `sections` field contains a string instead of a dictionary. This can happen due to:
- Legacy data format issues
- JSON serialization errors
- Data corruption during saves

**Solution Implemented** (2025-01-25):
Added type checking in multiple locations to handle cases where sections might not be a dictionary:

1. **In `app/routes/document_structure.py`**:
   - Added `isinstance(sections, dict)` checks before accessing dictionary methods
   - Logs warnings when sections is not a dictionary
   - Gracefully handles the error instead of crashing

2. **In `app/services/section_embedding_service.py`**:
   - Added type checks in all strategies that access sections
   - Strategy 1: Check `doc_structure['sections']` is a dict
   - Strategy 4: Check `doc_metadata['sections']` is a dict
   - Prevents attempts to iterate over non-dict objects

**Example Fix**:
```python
# Before (would crash if sections is a string):
for section_id, section_data in doc_structure['sections'].items():
    # process section

# After (handles non-dict gracefully):
sections = doc_structure['sections']
if isinstance(sections, dict):
    for section_id, section_data in sections.items():
        # process section
else:
    logger.warning(f"sections is not a dictionary, it's a {type(sections)}")
```

### 2. Missing Section Content

**Problem**: Embeddings generation fails because section content cannot be found.

**Solution**: The service implements multiple fallback strategies:
1. Check `document_structure.sections` with content
2. Check `section_embeddings_metadata` 
3. Check top-level `sections` in metadata
4. Support for dual format (HTML/text) content

### 3. Duplicate Section IDs

**Problem**: Unique constraint violations when storing embeddings.

**Solution**: Implemented deduplication logic that:
- Tracks processed section IDs
- Normalizes URIs to prevent duplicates
- Skips duplicate sections with warnings

## Debugging Tips

1. **Check Metadata Structure**:
   ```python
   # In a Python shell
   from app.models.document import Document
   doc = Document.query.get(document_id)
   print(type(doc.doc_metadata))
   if 'sections' in doc.doc_metadata:
       print(type(doc.doc_metadata['sections']))
   ```

2. **View Logs**: The improved error handling now logs detailed information about:
   - Metadata structure and types
   - Which strategy is being used
   - Where content is found (or not found)
   - Type mismatches with specific details

3. **Manual Metadata Fix**: If a document has corrupted metadata:
   ```python
   # Fix string sections to empty dict
   if isinstance(doc.doc_metadata['sections'], str):
       doc.doc_metadata['sections'] = {}
       db.session.commit()
   ```

## Prevention

To prevent these issues in the future:
1. Always validate metadata structure before saving
2. Use proper JSON serialization when updating metadata
3. Implement data validation in forms and APIs
4. Regular database integrity checks