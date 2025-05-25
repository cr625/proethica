# Multiple Guidelines Support

This document describes the implementation of multiple guidelines support for worlds in the AI Ethical Decision-Making Simulator.

## Overview

Previously, each world could only have a single set of guidelines, stored directly in the `World` model as:
- `guidelines_url`: A URL to an external guidelines document
- `guidelines_text`: Text content of guidelines

The new implementation allows multiple guidelines to be attached to a world, with support for different types:
- Uploaded files (PDF, DOCX, TXT, HTML)
- URLs to external resources
- Directly entered text

## Implementation Details

### Data Model Changes

1. **Removed fields from World model**:
   - `guidelines_url`
   - `guidelines_text`

2. **Using Document model for guidelines**:
   - Each guideline is stored as a `Document` record
   - `document_type` is set to "guideline"
   - `world_id` links the document to a specific world
   - Different types of guidelines are distinguished by their fields:
     - File uploads: `file_path` and `file_type` are set
     - URLs: `source` is set
     - Text: `content` is set

### User Interface Changes

1. **World Detail Page**:
   - Added a link to view all guidelines for a world
   - Updated the Guidelines tab to show a summary and link to the guidelines page

2. **Guidelines Page**:
   - Created a new page to display all guidelines for a world
   - Shows different types of guidelines with appropriate icons/indicators
   - Provides options to download, view, or delete guidelines

3. **Edit World Page**:
   - Updated to allow adding multiple guidelines
   - Added separate sections for different types of guidelines (file, URL, text)
   - Each guideline can have its own title

### Backend Changes

1. **Routes**:
   - Added a new route to display guidelines for a specific world
   - Added a route to delete a specific guideline
   - Updated the world update route to handle multiple guidelines

2. **Migration**:
   - Created scripts to migrate existing guidelines to Document records
   - Created a script to remove the old fields from the World model

## Migration Process

To migrate existing data:

1. Run the migration script:
   ```
   ./scripts/run_guidelines_migration.sh
   ```

This script will:
1. Create Document records for existing guidelines_text and guidelines_url
2. Remove the guidelines_url and guidelines_text fields from the World model

## Usage

### Adding Guidelines

1. Go to the Edit World page
2. Fill in the appropriate section:
   - **Document**: Upload a file (PDF, DOCX, TXT, HTML)
   - **URL**: Provide a URL to an external resource
   - **Text**: Enter text directly
3. Provide a title for the guidelines
4. Save changes

### Viewing Guidelines

1. Go to the World Detail page
2. Click on the Guidelines tab
3. Click "View All Guidelines" to see the full list
4. Each guideline can be viewed, downloaded, or deleted

## Technical Notes

- Guidelines documents are processed using the EmbeddingService to generate vector embeddings
- These embeddings enable semantic search across guidelines
- The system supports various file types through appropriate text extraction methods
