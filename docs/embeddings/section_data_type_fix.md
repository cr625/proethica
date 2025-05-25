# Section Data Type Fix

## Issue
The error `'str' object has no attribute 'get'` occurred in `section_embedding_service.py` when processing sections from `document_structure.sections`.

## Root Cause
The `document_structure.sections` can contain either:
1. **String values**: Where the section ID maps directly to content (e.g., `{"facts": "content here"}`)
2. **Dictionary values**: Where the section ID maps to metadata dict (e.g., `{"facts": {"content": "...", "type": "..."}}`)

The code was assuming dictionary format and calling `.get()` on string values.

## Fix Applied
Modified the section processing logic to:
1. First check if `section_data` is a string or dictionary
2. If string: use it directly as content
3. If dictionary: extract content and metadata from it
4. Properly handle both formats throughout the processing

## Result
The embedding generation now works with both legacy string format and newer dictionary format for sections.