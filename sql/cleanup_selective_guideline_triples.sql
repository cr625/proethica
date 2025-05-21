-- SQL Script to selectively clean up guideline triples
-- This script will:
-- 1. Keep only the guideline with ID 190
-- 2. Delete all entity_triples related to other guideline concepts
-- 3. Update document metadata to remove references to deleted guidelines

-- First, lets see what would be preserved vs deleted

-- Check the guideline we want to keep
SELECT id, title, world_id
FROM public.guidelines
WHERE id = 190;

-- Count total guideline triples vs. those we'll keep
SELECT COUNT(*) AS "Total Guideline Concept Triples"
FROM public.entity_triples
WHERE entity_type = 'guideline_concept';

SELECT COUNT(*) AS "Guideline Triples to Keep"
FROM public.entity_triples
WHERE entity_type = 'guideline_concept' 
AND guideline_id = 190;

SELECT COUNT(*) AS "Guideline Triples to Delete"
FROM public.entity_triples
WHERE entity_type = 'guideline_concept'
AND (guideline_id IS NULL OR guideline_id != 190);

-- View documents with guideline_id references
SELECT id, title, doc_metadata->>'guideline_id' AS referenced_guideline_id
FROM public.documents
WHERE doc_metadata->>'guideline_id' IS NOT NULL;

-- Now, the actual delete operations:

-- 1. Delete all entity_triples for guideline concepts EXCEPT those associated with guideline ID 190
DELETE FROM public.entity_triples
WHERE entity_type = 'guideline_concept' 
AND (guideline_id IS NULL OR guideline_id != 190);

-- 2. Delete all guidelines EXCEPT ID 190
DELETE FROM public.guidelines
WHERE id != 190;

-- 3. Update document metadata to remove guideline_id references EXCEPT for 190
UPDATE public.documents
SET doc_metadata = doc_metadata - 'guideline_id'
WHERE doc_metadata->>'guideline_id' IS NOT NULL
AND doc_metadata->>'guideline_id' != '190';

-- Also remove analyzed flag and related counts for documents that are no longer linked to guidelines
UPDATE public.documents
SET doc_metadata = doc_metadata - 'analyzed'
WHERE doc_metadata->>'guideline_id' IS NULL 
AND doc_metadata->>'analyzed' IS NOT NULL;

UPDATE public.documents
SET doc_metadata = doc_metadata - 'concepts_extracted'
WHERE doc_metadata->>'guideline_id' IS NULL
AND doc_metadata->>'concepts_extracted' IS NOT NULL;

UPDATE public.documents
SET doc_metadata = doc_metadata - 'concepts_selected'
WHERE doc_metadata->>'guideline_id' IS NULL
AND doc_metadata->>'concepts_selected' IS NOT NULL;

UPDATE public.documents
SET doc_metadata = doc_metadata - 'triples_created'
WHERE doc_metadata->>'guideline_id' IS NULL
AND doc_metadata->>'triples_created' IS NOT NULL;

UPDATE public.documents
SET doc_metadata = doc_metadata - 'analysis_date'
WHERE doc_metadata->>'guideline_id' IS NULL
AND doc_metadata->>'analysis_date' IS NOT NULL;

-- Confirm the results
SELECT COUNT(*) AS "Remaining Guideline Concept Triples"
FROM public.entity_triples
WHERE entity_type = 'guideline_concept';

SELECT id, title, world_id AS "Remaining Guidelines"
FROM public.guidelines;

SELECT COUNT(*) AS "Documents still having guideline references"
FROM public.documents
WHERE doc_metadata->>'guideline_id' IS NOT NULL;
