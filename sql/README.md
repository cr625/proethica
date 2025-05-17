# SQL Utilities for ProEthica

This directory contains SQL queries that are useful for exploring and managing the ProEthica database. These scripts are meant to be run directly against the PostgreSQL database.

## Running the Queries

You can execute these queries in several ways:

### Using Docker

```bash
# Basic format for running queries in the Docker container
docker exec -it proethica-postgres psql -U postgres -d ai_ethical_dm -c "SELECT * FROM tablename;"

# To run a query without paging (for large result sets)
docker exec -it proethica-postgres psql -U postgres -d ai_ethical_dm -P pager=off -c "SELECT * FROM tablename;"

# To run a script file
docker exec -it proethica-postgres psql -U postgres -d ai_ethical_dm -f /path/to/script.sql
```

### Using psql Directly

If you have PostgreSQL client tools installed locally:

```bash
psql -h localhost -p 5432 -U postgres -d ai_ethical_dm -c "SELECT * FROM tablename;"
```

## Available Query Files

### `document_guideline_relationship.sql`

Queries to explore the relationship between documents (uploaded guidelines) and the corresponding guideline entities in the database. These queries help trace how document IDs (as seen in URLs) relate to guideline IDs (used in the entity_triples table).

### `guideline_rdf_triples.sql`

Queries for working with the RDF triples that represent concepts extracted from guidelines. These allow you to view, analyze, and manage the semantic representation of guidelines in the knowledge graph.

### `GET_CONCEPT_INFO.sql`

Queries for extracting and analyzing concept information, focusing on the concepts and their relationships.

### `DELETE_CONCEPTS.sql`

Utilities for safely removing concept data, including cleanup operations for guidelines processing.

## Database Structure Overview

The main tables involved in the guidelines concept extraction workflow are:

1. `documents` - Contains the raw guideline documents (text, PDFs, URLs)
2. `guidelines` - Contains processed guideline records with metadata
3. `entity_triples` - Contains the RDF triples (subject-predicate-object) that represent concepts extracted from guidelines

The relationship flow is:
- Document → Guideline (via doc_metadata->guideline_id)
- Guideline → Triples (via guideline_id foreign key in entity_triples)

## Common Query Patterns

### Finding a Document's Associated Guideline

```sql
SELECT id, title, doc_metadata->>'guideline_id' AS guideline_id
FROM public.documents
WHERE id = 189;
```

### Getting Triples for a Specific Guideline

```sql
SELECT subject_label, predicate_label, COALESCE(object_label, object_literal, object_uri) AS object
FROM public.entity_triples
WHERE guideline_id = 4 AND entity_type = 'guideline_concept';
```

### Extracting Distinct Concepts

```sql
SELECT 
    SPLIT_PART(subject, '/concept/', 2) AS concept_name,
    MAX(CASE WHEN predicate = 'http://www.w3.org/2000/01/rdf-schema#comment' 
             THEN object_literal ELSE NULL END) AS description
FROM 
    public.entity_triples
WHERE 
    guideline_id = 4 AND entity_type = 'guideline_concept'
    AND subject NOT LIKE '%/guideline/%'
GROUP BY 
    subject;
