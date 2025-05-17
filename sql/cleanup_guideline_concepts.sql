-- SQL Script to clean up guideline concepts and their associated data for testing
-- This script will:
-- 1. Delete all entity_triples related to guideline concepts
-- 2. Update document metadata to remove guideline references
-- 3. Delete all guideline records

-- First, lets see what would be deleted (comment out these SELECTs when ready to delete)

-- View the entity triples that would be deleted
SELECT COUNT(*) AS "Total Guideline Concept Triples"
FROM public.entity_triples
WHERE entity_type = 'guideline_concept';

-- View the guidelines that would be deleted
SELECT id, title, world_id
FROM public.guidelines;

-- View documents with guideline_id references
SELECT id, title, doc_metadata->>'guideline_id' AS referenced_guideline_id
FROM public.documents
WHERE doc_metadata->>'guideline_id' IS NOT NULL;

-- Now, the actual delete operations:

-- 1. Delete all entity_triples for guideline concepts
DELETE FROM public.entity_triples
WHERE entity_type = 'guideline_concept';

-- 2. Update document metadata to remove guideline_id references
-- This uses a Postgres-specific approach to update a value inside a JSONB column
UPDATE public.documents
SET doc_metadata = doc_metadata - 'guideline_id'
WHERE doc_metadata->>'guideline_id' IS NOT NULL;

-- Also remove analyzed flag and related counts
UPDATE public.documents
SET doc_metadata = doc_metadata - 'analyzed'
WHERE doc_metadata->>'analyzed' IS NOT NULL;

UPDATE public.documents
SET doc_metadata = doc_metadata - 'concepts_extracted'
WHERE doc_metadata->>'concepts_extracted' IS NOT NULL;

UPDATE public.documents
SET doc_metadata = doc_metadata - 'concepts_selected'
WHERE doc_metadata->>'concepts_selected' IS NOT NULL;

UPDATE public.documents
SET doc_metadata = doc_metadata - 'triples_created'
WHERE doc_metadata->>'triples_created' IS NOT NULL;

UPDATE public.documents
SET doc_metadata = doc_metadata - 'analysis_date'
WHERE doc_metadata->>'analysis_date' IS NOT NULL;

-- 3. Delete all guidelines
DELETE FROM public.guidelines;

-- Confirm the deletions
SELECT COUNT(*) AS "Remaining Guideline Concept Triples"
FROM public.entity_triples
WHERE entity_type = 'guideline_concept';

SELECT COUNT(*) AS "Remaining Guidelines"
FROM public.guidelines;

SELECT COUNT(*) AS "Documents still having guideline references"
FROM public.documents
WHERE doc_metadata->>'guideline_id' IS NOT NULL;
