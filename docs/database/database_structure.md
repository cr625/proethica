# Database Structure Documentation

This document outlines the key relationships and structure of the AI Ethical DM database, particularly focusing on worlds, guidelines, and section embeddings.

## World-Guideline Relationship

The system organizes ethical content using a "world" concept that provides domain context:

- **Direct Foreign Key Relationship**: Each guideline in the `guidelines` table has a `world_id` column that establishes a direct relationship to a world
- **Cardinality**: One-to-many (a world can have multiple guidelines, but each guideline belongs to exactly one world)
- **UI Path**: Guidelines for a world can be accessed at: `http://localhost:3333/worlds/{world_id}/guidelines/{guideline_id}`

### Database Tables

The primary tables involved in this relationship are:

```
worlds
├── id (PK)
├── name
├── description
├── ontology_id
└── ontology_source

guidelines
├── id (PK)
├── title
├── content
├── world_id (FK → worlds.id)
├── source_url
└── file_path
```

### Implementation Note

There was a discrepancy between the UI and the toolkit scripts where:
- The UI correctly showed guideline ID 190 associated with world ID 1
- The `run_list_worlds.sh --detail` script initially showed 0 guidelines for world ID 1

This was due to a limitation in the implementation of `list_worlds.py`, which initialized an empty list for guidelines but never populated it. The script has been fixed to properly query and count guidelines associated with each world.

## Section Embeddings System

The section embeddings represent vector embeddings for document sections, enabling semantic search across case content:

### Database Structure

```
document_sections
├── id (PK)
├── document_id (FK → documents.id)
├── section_id
├── section_type
├── content
├── embedding (pgvector type, 384 dimensions)
└── section_metadata
```

### Key Features

- Uses pgvector extension for vector storage and similarity search
- Each embedding is 384-dimensional (standard for embeddings from text-embedding-ada-002)
- Sections are extracted from documents and include types like "facts", "question", "conclusion", etc.
- Enables semantic similarity searches across document sections

### Generation Process

1. **Document Structure Annotation Step**: Prepares section metadata with URIs like `http://proethica.org/document/case_252/facts`
2. **SectionEmbeddingService**: Generates embeddings for section content and stores them in the document_sections table
3. **Batch Processing**: Scripts like `batch_update_embeddings.py` facilitate processing all documents with structured content

## Toolkit Scripts

The `scripts/triple_toolkit` directory contains utilities for examining database content:

- `run_list_worlds.sh`: Lists all worlds with their metadata
- `run_list_guidelines.sh`: Lists guidelines for a specific world
- `run_list_section_embeddings.sh`: Lists section embeddings with various format options
- `run_find_orphaned_triples.sh`: Identifies orphaned triple references

Each toolkit script accepts various command-line options for formatting and filtering results. 
For example:

```bash
# View detailed world information
./scripts/triple_toolkit/run_list_worlds.sh --detail

# List guidelines for a specific world
./scripts/triple_toolkit/run_list_guidelines.sh --world-id 1

# View section embeddings with detailed output
./scripts/triple_toolkit/run_list_section_embeddings.sh --format detailed
```

## Database Connection

The toolkit scripts use environment variables for database connection. The connection string is typically loaded from:

1. The `DATABASE_URL` environment variable
2. A `.env` file in the project root
3. Default configuration in the application

This ensures consistent database access across different utilities and application components.
