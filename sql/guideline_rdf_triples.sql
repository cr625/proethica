-- Guideline RDF Triples Queries
-- These queries are for working with the RDF triples (concepts) extracted from guidelines

-- 1. View all triples for a specific guideline (human-readable format)
SELECT 
    SPLIT_PART(et.subject, '/concept/', 2) as concept,
    CASE 
        WHEN et.predicate = 'http://www.w3.org/2000/01/rdf-schema#label' THEN 'label'
        WHEN et.predicate = 'http://www.w3.org/2000/01/rdf-schema#comment' THEN 'description'
        WHEN et.predicate = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type' THEN 'type'
        WHEN et.predicate = 'http://proethica.org/ontology/isDefinedIn' THEN 'defined in'
        ELSE SPLIT_PART(et.predicate, '/', -1)
    END as predicate,
    CASE 
        WHEN et.is_literal THEN et.object_literal
        WHEN et.object_label IS NOT NULL THEN et.object_label
        ELSE SPLIT_PART(et.object_uri, '/', -1)
    END as object
FROM 
    public.entity_triples et
WHERE 
    et.guideline_id = 4  -- Change this to the guideline ID you're interested in
    AND et.entity_type = 'guideline_concept'
ORDER BY 
    concept, predicate;

-- 2. Show all triples in technical RDF format
SELECT 
    et.subject as subject,
    et.predicate as predicate,
    CASE 
        WHEN et.is_literal THEN et.object_literal::text
        ELSE et.object_uri
    END as object
FROM 
    public.entity_triples et
WHERE 
    et.guideline_id = 4  -- Change this to the guideline ID you're interested in
    AND et.entity_type = 'guideline_concept'
ORDER BY 
    et.subject, et.predicate;

-- 3. Extract just the concepts (distinct subjects) with their definitions
SELECT 
    SPLIT_PART(et.subject, '/concept/', 2) as concept_name,
    MAX(CASE WHEN et.predicate = 'http://www.w3.org/2000/01/rdf-schema#comment' 
             THEN et.object_literal ELSE NULL END) as description,
    MAX(CASE WHEN et.predicate = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type' 
             THEN SPLIT_PART(et.object_uri, '/', -1) ELSE NULL END) as concept_type
FROM 
    public.entity_triples et
WHERE 
    et.guideline_id = 4  -- Change this to the guideline ID you're interested in
    AND et.entity_type = 'guideline_concept'
    AND et.subject NOT LIKE '%/guideline/%'
GROUP BY 
    et.subject
ORDER BY 
    concept_name;

-- 4. Count triples by predicate type
SELECT 
    CASE 
        WHEN et.predicate = 'http://www.w3.org/2000/01/rdf-schema#label' THEN 'label'
        WHEN et.predicate = 'http://www.w3.org/2000/01/rdf-schema#comment' THEN 'description'
        WHEN et.predicate = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type' THEN 'type'
        WHEN et.predicate = 'http://proethica.org/ontology/isDefinedIn' THEN 'defined in'
        ELSE et.predicate
    END as predicate_type,
    COUNT(*) as count
FROM 
    public.entity_triples et
WHERE 
    et.guideline_id = 4  -- Change this to the guideline ID you're interested in
    AND et.entity_type = 'guideline_concept'
GROUP BY 
    predicate_type
ORDER BY 
    count DESC;

-- 5. Find guideline with the most triples
SELECT 
    g.id as guideline_id,
    g.title,
    COUNT(et.id) as triple_count
FROM 
    public.guidelines g
JOIN 
    public.entity_triples et ON g.id = et.guideline_id
WHERE 
    et.entity_type = 'guideline_concept'
GROUP BY 
    g.id, g.title
ORDER BY 
    triple_count DESC;

-- 6. View triples for a specific concept across all guidelines
SELECT 
    g.title as guideline,
    et.subject_label as concept,
    et.predicate_label as predicate,
    COALESCE(et.object_label, et.object_literal, et.object_uri) as object
FROM 
    public.entity_triples et
JOIN 
    public.guidelines g ON et.guideline_id = g.id
WHERE 
    et.subject LIKE '%/concept/confidentiality'  -- Change this to the concept you're interested in
    AND et.entity_type = 'guideline_concept'
ORDER BY 
    guideline, et.predicate;

-- 7. Trace guidelines for document to triples (complete path)
WITH doc_guideline AS (
    SELECT 
        d.id as document_id,
        d.title as document_title,
        (d.doc_metadata->>'guideline_id')::integer as guideline_id
    FROM 
        public.documents d
    WHERE 
        d.id = 189  -- Change this to the document ID you're interested in
)
SELECT 
    dg.document_id,
    dg.document_title,
    g.id as guideline_id,
    g.title as guideline_title,
    SPLIT_PART(et.subject, '/concept/', 2) as concept,
    CASE 
        WHEN et.predicate = 'http://www.w3.org/2000/01/rdf-schema#label' THEN 'label'
        WHEN et.predicate = 'http://www.w3.org/2000/01/rdf-schema#comment' THEN 'description'
        WHEN et.predicate = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type' THEN 'type'
        ELSE SPLIT_PART(et.predicate, '/', -1)
    END as predicate,
    CASE 
        WHEN et.is_literal THEN et.object_literal
        ELSE SPLIT_PART(et.object_uri, '/', -1)
    END as object
FROM 
    doc_guideline dg
JOIN 
    public.guidelines g ON dg.guideline_id = g.id
JOIN 
    public.entity_triples et ON g.id = et.guideline_id
WHERE 
    et.entity_type = 'guideline_concept'
ORDER BY 
    concept, predicate
LIMIT 20;  -- Limit results for readability
