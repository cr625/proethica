# Document Structure SPARQL Tests

This document contains sample SPARQL queries to test the document structure ontology extensions.

## Test Queries

### Query 1: Retrieve all document sections for a case

This query retrieves all document sections for a specific case, showing the hierarchy of document elements.

```sparql
PREFIX : <http://proethica.org/ontology/intermediate#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?section ?type ?content
WHERE {
  :case23_4_document :hasPart ?section .
  ?section rdf:type ?type .
  ?section :hasTextContent ?content .
  
  # Only include document sections, not other document elements
  FILTER(?type IN (:FactsSection, :QuestionsSection, :ReferencesSection, :DiscussionSection, :ConclusionSection))
}
ORDER BY ?section
```

### Query 2: Find all question items related to a specific ethical principle

This query finds all questions that relate to a specific ethical principle, showing the connection between document structure and ethical concepts.

```sparql
PREFIX : <http://proethica.org/ontology/intermediate#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?question ?content
WHERE {
  ?question rdf:type :QuestionItem .
  ?question :hasTextContent ?content .
  
  # Find questions that pose ethical questions related to honesty
  ?question :posesEthicalQuestion ?ethicalQuestion .
  ?ethicalQuestion :concernsPrinciple :honesty_principle .
}
```

### Query 3: Retrieve all conclusion items and their associated ethical decisions

This query shows the relationship between document structure elements (conclusion items) and their semantic interpretation (ethical decisions).

```sparql
PREFIX : <http://proethica.org/ontology/intermediate#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?conclusion ?content ?decision
WHERE {
  ?conclusion rdf:type :ConclusionItem .
  ?conclusion :hasTextContent ?content .
  ?conclusion :representsEthicalDecision ?decision .
}
```

### Query 4: Find document sections that mention specific agents

This query demonstrates how the ontology can be used to find all document sections that mention specific agents.

```sparql
PREFIX : <http://proethica.org/ontology/intermediate#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?section ?sectionType ?agent ?agentLabel
WHERE {
  ?section rdf:type ?sectionType .
  ?section :mentionsAgent ?agent .
  ?agent rdfs:label ?agentLabel .
  
  # Only include document sections
  FILTER(?sectionType IN (:FactsSection, :QuestionsSection, :ReferencesSection, :DiscussionSection, :ConclusionSection))
}
```

### Query 5: Document structure sequence

This query shows the sequence of document elements, using the precedesInDocument and followsInDocument properties.

```sparql
PREFIX : <http://proethica.org/ontology/intermediate#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?section1 ?section1Label ?section2 ?section2Label
WHERE {
  ?section1 :precedesInDocument ?section2 .
  ?section1 rdf:type ?type1 .
  ?section2 rdf:type ?type2 .
  ?section1 rdfs:label ?section1Label .
  ?section2 rdfs:label ?section2Label .
}
ORDER BY ?section1
```

### Query 6: Find sections with embeddings and their similarity

This query would retrieve sections with embeddings for similarity calculations (in a real system, the similarity would be calculated using a vector database or embedding similarity function).

```sparql
PREFIX : <http://proethica.org/ontology/intermediate#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?section ?sectionType ?embedding
WHERE {
  ?section rdf:type ?sectionType .
  ?section :hasEmbedding ?embedding .
  
  # Only include document sections
  FILTER(?sectionType IN (:FactsSection, :QuestionsSection, :ReferencesSection, :DiscussionSection, :ConclusionSection))
}
```

### Query 7: Find all code references cited in a document

This query retrieves all code references cited in a specific case document.

```sparql
PREFIX : <http://proethica.org/ontology/intermediate#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?reference ?content
WHERE {
  ?reference rdf:type :CodeReferenceItem .
  ?reference :hasTextContent ?content .
  ?reference :isPartOf ?section .
  ?section :isPartOf :case23_4_document .
}
```

## Using These Queries

These sample queries demonstrate how the document structure ontology can be used to:

1. Retrieve structured document content
2. Connect document elements to semantic interpretations
3. Find relationships between document elements and ethical concepts
4. Analyze the structure and sequence of document elements
5. Support semantic search across document sections

In a real implementation, these queries would be integrated into the application to:

- Enhance case search and retrieval
- Support section-based similarity calculations
- Enable targeted ethical reasoning across document sections
- Provide more precise context for LLM-based processing
