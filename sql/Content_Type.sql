SELECT 
    et.subject,
    et.subject_label,
    et.object_uri AS concept_type,
    et.object_label AS concept_type_label,
    et.guideline_id,
    g.title AS guideline_title
FROM 
    public.entity_triples et
JOIN 
    public.guidelines g ON et.guideline_id = g.id
WHERE 
    et.entity_type = 'guideline_concept'
    AND et.predicate = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type';