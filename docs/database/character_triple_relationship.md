# Character to Triple Relationship

This document explains the relationship between the `characters` table and the `character_triples` table in the ProEthica system.

## Overview

The system employs a dual representation approach for character data:

1. **Traditional structured representation** in the `characters` table
2. **RDF triple-based semantic representation** in the `character_triples` table

This design allows for a gradual transition from the conventional relational model to a more flexible, semantically rich graph-based representation.

## Database Relationship

### Foreign Key Relationship

- The `character_triples` table has a `character_id` foreign key that references the `characters.id` column.
- This establishes a many-to-one relationship where:
  - One character can have many associated triples
  - Each triple belongs to at most one character

```
Character (1) ----< Character Triples (many)
```

### Cascade Deletion

- The foreign key is defined with `ondelete='CASCADE'`, ensuring that when a character is deleted, all its associated triples are automatically deleted.
- This maintains referential integrity and prevents orphaned triple data.

## Code Implementation

### Triple Model

In `app/models/triple.py`:

```python
character_id = db.Column(Integer, db.ForeignKey('characters.id', ondelete='CASCADE'), nullable=True)
```

The `nullable=True` means that triples don't necessarily have to be associated with a character, providing flexibility for other triple types in the future.

### Character Model

In the Character model (`app/models/character.py`), there's no direct relationship back to the triples. When triples need to be accessed for a character, they are queried explicitly through the RDF service.

## Data Flow

1. When a character is created/updated in the traditional system, the `RDFService` can:
   - Delete all existing triples for that character
   - Generate new triples based on the character's current state
   - Store those triples with the character_id reference

2. When querying character data through the semantic interface:
   - Triples can be retrieved directly by character_id
   - SPARQL-like queries can find characters matching specific patterns
   - Results can reference back to the original character objects

## Benefits of This Design

1. **Backward Compatibility**: The traditional character model continues to work with existing code
2. **Gradual Migration**: Features can be progressively moved to use the triple-based representation
3. **Parallel Access Paths**: Data can be accessed through either the relational or graph-based model
4. **Semantic Richness**: The triple model allows linking to ontologies and complex graph queries
5. **Flexibility**: New attributes can be added as triples without changing the character schema

## Future Directions

As the system evolves, we may consider:

1. Making the character model thinner, with more data living primarily in triples
2. Adding a direct relationship from Character to its triples for easier access
3. Implementing caching mechanisms to efficiently reconstruct characters from triples
