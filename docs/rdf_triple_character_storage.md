# RDF Triple Character Storage

This document explains the approach of using RDF triples to store character data in the ProEthica system, particularly for representing ethics domain knowledge.

## Overview

The Resource Description Framework (RDF) triple storage approach allows for flexible, graph-based representation of character data and attributes within a semantic web context. This approach makes it easier to:

1. Connect characters to domain-specific ontologies
2. Query characters based on attributes and relationships
3. Expand the character model without schema changes
4. Enable semantic reasoning and inference

## Implementation

The triple-based approach stores character data as subject-predicate-object triples where:

- **Subject**: The character URI (e.g., `http://proethica.org/character/20_jane_smith_[uuid]`)
- **Predicate**: A property or relationship (e.g., `http://proethica.org/ontology/hasRole`)
- **Object**: Either a literal value or another URI referencing a concept

### Triple Model

The `Triple` model in `app/models/triple.py` contains:

- `subject`: URI identifier for the character
- `predicate`: Property or relationship
- `object_literal`: Literal values (strings, numbers)
- `object_uri`: Reference to other entities by URI
- `is_literal`: Boolean flag indicating if the object is a literal or URI
- `graph`: Context/named graph for the triple
- `*_embedding`: Vector embeddings for semantic search
- `character_id`: Foreign key to the original character
- `scenario_id`: Foreign key to the scenario

### RDF Service

The `RDFService` in `app/services/rdf_service.py` provides methods to:

- Convert character objects to triples
- Reconstruct characters from triples
- Query triples with SPARQL-like patterns
- Manage namespaces for different ethics domains

## Namespaces

We use several namespaces to organize concepts:

- `PROETHICA`: Base ontology (`http://proethica.org/ontology/`)
- `ENG_ETHICS`: Engineering ethics concepts (`http://proethica.org/ontology/engineering-ethics#`)
- `NSPE`: NSPE code of ethics (`http://proethica.org/ontology/engineering-ethics/nspe#`)
- `IEEE`: IEEE code of ethics (`http://proethica.org/ontology/engineering-ethics/ieee#`)
- `RDF` and `RDFS`: Standard RDF vocabularies

## Character Representation Example

A Professional Engineer character like Jane Smith is represented with triples such as:

```
<http://proethica.org/character/20_jane_smith_[uuid]> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://proethica.org/ontology/Character>
<http://proethica.org/character/20_jane_smith_[uuid]> <http://www.w3.org/2000/01/rdf-schema#label> "Jane Smith"
<http://proethica.org/character/20_jane_smith_[uuid]> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://proethica.org/ontology/engineering-ethics#ProfessionalEngineer>
<http://proethica.org/character/20_jane_smith_[uuid]> <http://proethica.org/ontology/hasRole> "ProfessionalEngineer"
<http://proethica.org/character/20_jane_smith_[uuid]> <http://proethica.org/ontology/yearsOfExperience> "15"
<http://proethica.org/character/20_jane_smith_[uuid]> <http://proethica.org/ontology/ethicalPriorities> ["public_safety", "professional_integrity", "client_interests"]
```

## Querying Benefits

The triple structure enables complex queries like:

- Find all characters with a specific role: `?character rdf:type eng:ProfessionalEngineer`
- Find characters with specific ethical priorities: `?character proethica:ethicalPriorities "public_safety"`
- Find characters that can be categorized by specific ethics codes: `?character rdf:type nspe:CategoryII`

## Integration with Vector Embeddings

The triple model includes embedding fields for subjects, predicates, and objects, allowing:

- Semantic similarity searches
- Contextual recommendation of relevant ethics rules
- Clustering characters with similar features

## Example Usage

See `scripts/test_character_rdf_triples.py` for a working example of:

1. Creating characters
2. Converting them to triples
3. Querying the triple store
4. Simulating domain-specific ethics queries

## Future Directions

- Expand to other ethics domains (medical, legal, business, etc.)
- Implement full SPARQL query capabilities
- Connect with larger ethics ontologies and knowledge graphs
- Enable cross-domain reasoning (e.g., how medical ethics relates to engineering ethics)
