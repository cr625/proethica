-- Document-Guideline-Triple Relationship Queries
-- These queries help understand and trace the relationship between documents, guidelines, and RDF triples

-- 1. Find which guideline is associated with a specific document
SELECT 
    id AS document_id, 
    title AS document_title,
    doc_metadata->>'guideline_id' AS guideline_id
FROM 
    public.documents 
WHERE 
    id = 189;  -- Change this to the document ID you're interested in

-- 2. Trace the relationship from document to guideline to triples (with count)
WITH guideline_id AS (
    SELECT (doc_metadata->>'guideline_id')::integer AS id 
    FROM public.documents 
    WHERE id = 189  -- Change this to the document ID you're interested in
)
SELECT 
    'Document 189 links to Guideline ' || guideline_id.id AS relationship,
    (SELECT COUNT(*) FROM public.entity_triples WHERE guideline_id = guideline_id.id) AS triple_count
FROM 
    guideline_id;

-- 3. View document metadata and guideline metadata together
SELECT 
    d.id AS document_id,
    d.title AS document_title,
    d.doc_metadata,
    g.id AS guideline_id,
    g.title AS guideline_title,
    g.guideline_metadata
FROM 
    public.documents d
JOIN 
    public.guidelines g ON (d.doc_metadata->>'guideline_id')::integer = g.id
WHERE 
    d.id = 189;  -- Change this to the document ID you're interested in

-- 4. Get all documents with associated guidelines
SELECT 
    d.id AS document_id,
    d.title AS document_title,
    d.document_type,
    d.doc_metadata->>'guideline_id' AS guideline_id
FROM 
    public.documents d
WHERE 
    d.doc_metadata->>'guideline_id' IS NOT NULL
ORDER BY 
    d.id;

-- 5. Find documents where triples have been created
SELECT 
    d.id AS document_id,
    d.title,
    (d.doc_metadata->>'triples_created')::integer AS triples_created,
    (d.doc_metadata->>'concepts_extracted')::integer AS concepts_extracted,
    (d.doc_metadata->>'concepts_selected')::integer AS concepts_selected
FROM 
    public.documents d
WHERE 
    d.doc_metadata->>'triples_created' IS NOT NULL 
    AND (d.doc_metadata->>'triples_created')::integer > 0
ORDER BY 
    (d.doc_metadata->>'triples_created')::integer DESC;
