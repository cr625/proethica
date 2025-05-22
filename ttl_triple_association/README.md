# TTL-based Section-Triple Association System

This component provides functionality to associate document sections with relevant ontology concepts by directly loading TTL files and using vector similarity with semantic property matching.

## Overview

The system implements a two-phase matching algorithm:

1. **Coarse matching phase**: Uses vector similarity between section embeddings and concept embeddings to identify candidate matches
2. **Fine-grained matching phase**: Refines matches using semantic properties and section context awareness

## Components

- `OntologyTripleLoader`: Loads ontology concepts from TTL files
- `EmbeddingService`: Provides embedding generation for text
- `SectionTripleAssociator`: Associates sections with concepts based on similarity
- `SectionTripleAssociationStorage`: Handles database storage operations
- `SectionTripleAssociationService`: Coordinates the overall process

## Usage

### Step 1: Generate Embeddings for Sections

Before running the association process, ensure that the document sections have embeddings:

```bash
# Generate embeddings for a document
./run_generate_section_embeddings.sh 252  # Replace 252 with your document ID
```

### Step 2: Run the Association Process

Once embeddings are generated, run the association process:

```bash
# Run the association process for a document
./run_ttl_section_triple_association.sh --document 252 --threshold 0.3 --max-matches 10
```

Parameters:
- `--document`: Document ID to process
- `--threshold`: Minimum similarity threshold (0-1)
- `--max-matches`: Maximum number of matches per section
- `--batch-size`: Number of sections to process in each batch

### Step 3: View the Results

After the association process completes, you can view the results in the database:

```sql
-- View associations for a specific section
SELECT * FROM section_ontology_associations 
WHERE section_id = 101
ORDER BY match_score DESC;

-- View all associations for a document
SELECT soa.*, ds.section_type
FROM section_ontology_associations soa
JOIN document_sections ds ON soa.section_id = ds.id
WHERE ds.document_id = 252
ORDER BY soa.section_id, soa.match_score DESC;
```

## CLI Options

The command-line interface supports various options:

```
usage: cli.py [-h] [--db-url DB_URL]
              (--document-id DOCUMENT_ID | --section-ids SECTION_IDS [SECTION_IDS ...] | --with-embeddings)
              [--similarity SIMILARITY] [--max-matches MAX_MATCHES]
              [--batch-size BATCH_SIZE] [--output OUTPUT]
              [--format {json,pretty}]

Section-Triple Association CLI

options:
  -h, --help            show this help message and exit
  --db-url DB_URL       Database connection URL (defaults to environment
                        variable)

Section Selection:
  --document-id DOCUMENT_ID
                        Process all sections from a specific document
  --section-ids SECTION_IDS [SECTION_IDS ...]
                        Process specific section IDs
  --with-embeddings     Process all sections that have embeddings

Association Options:
  --similarity SIMILARITY
                        Minimum similarity threshold (0-1) (default: 0.6)
  --max-matches MAX_MATCHES
                        Maximum matches per section (default: 10)
  --batch-size BATCH_SIZE
                        Batch size for processing (default: 10)

Output Options:
  --output OUTPUT       Save results to JSON file (default: None)
  --format {json,pretty}
                        Output format (default: pretty)
```

## Troubleshooting

### No Matches Found

If no matches are found for any sections, check the following:

1. Ensure the sections have embeddings:
   ```sql
   SELECT id, document_id, section_type FROM document_sections 
   WHERE embedding IS NOT NULL AND document_id = 252;
   ```

2. Try lowering the similarity threshold:
   ```bash
   ./run_ttl_section_triple_association.sh --document 252 --threshold 0.2 --max-matches 10
   ```

3. Check the ontology files are loaded correctly:
   ```bash
   python -c "from ttl_triple_association.ontology_triple_loader import OntologyTripleLoader; loader = OntologyTripleLoader(); loader.load(); print(f'Loaded {len(loader.concepts)} concepts')"
   ```

### Database Issues

If you encounter database-related errors, check the following:

1. Database connection URL is correct
2. The `section_ontology_associations` table exists:
   ```sql
   SELECT * FROM information_schema.tables 
   WHERE table_name = 'section_ontology_associations';
   ```

3. The table has the correct schema:
   ```sql
   SELECT column_name, data_type 
   FROM information_schema.columns 
   WHERE table_name = 'section_ontology_associations';
