w# Guideline Sections Viewer

This utility provides a way to visualize the guideline section associations that were generated during the guideline section integration test.

## Background

The guideline section integration process associates ethical guidelines with specific document sections. After optimizing this process to handle only the 127 relevant guideline triples (as described in `docs/guideline_section_integration_enhancement.md`), we need a way to visualize the results of this process.

## How to Use

1. **Run the test viewer**:
   ```bash
   ./test_view_guideline_sections.py
   ```

2. **Open in browser**:
   Once the server is running, navigate to:
   ```
   http://localhost:5000/test/guideline_sections/251
   ```
   This will display the guideline associations for document ID 251 (Competence in Design Services).

3. **View different documents**:
   You can view associations for other documents by changing the ID in the URL:
   ```
   http://localhost:5000/test/guideline_sections/<document_id>
   ```
   Or by passing the document ID as an argument when starting the server:
   ```bash
   ./test_view_guideline_sections.py 190
   ```

## Features

The guideline sections viewer provides:

1. **Document Information**:
   - Title, ID, and type
   - Summary of guideline associations (count, sections processed, last updated)

2. **Section Details**:
   - Section type and ID
   - Content preview
   - Associated guidelines with:
     - Guideline URI
     - Relationship type
     - Confidence score (with visual indicator)
     - Additional details when available

3. **Actions**:
   - Regenerate associations button (to reprocess the document if needed)

## Implementation Details

The viewer is implemented as a test route in the Flask application that:

1. Queries the DocumentSection table for sections belonging to the specified document
2. Extracts guideline associations from section metadata
3. Formats and displays the data in a clean, user-friendly interface

## Future Enhancements

This test viewer could be extended to:

1. Allow filtering of guidelines by confidence threshold
2. Provide advanced sorting options
3. Add detailed views of guideline content
4. Integrate with the main document structure UI

## Related Documentation

- [Guideline Section Integration](docs/guideline_section_integration.md)
- [Guideline Section Integration Enhancement](docs/guideline_section_integration_enhancement.md)
- [Features Implemented Update](docs/features_implemented_update.md)
