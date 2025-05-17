SELECT 
    SPLIT_PART(et.subject, '/concept/', 2) AS concept_id,
    MAX(CASE WHEN et.predicate = 'http://www.w3.org/2000/01/rdf-schema#label' 
             THEN et.object_literal ELSE NULL END) AS concept_name,
    MAX(CASE WHEN et.predicate = 'http://www.w3.org/2000/01/rdf-schema#comment' 
             THEN et.object_literal ELSE NULL END) AS description,
    MAX(CASE WHEN et.predicate = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type' 
             THEN et.object_uri ELSE NULL END) AS concept_type
FROM 
    public.entity_triples et
JOIN 
    public.guidelines g ON et.guideline_id = g.id
WHERE 
    g.guideline_metadata->>'document_id' = '189'
    AND et.subject LIKE '%/concept/%'
GROUP BY 
    et.subject
ORDER BY 
    concept_name;
