# Section-to-Triple Association Plan

This document outlines the plan for associating RDF triples with case document sections, leveraging the section embeddings we've already generated. The goal is to enhance the semantic understanding of each case section by connecting it with relevant ethical concepts from our ontology.

## Current State Assessment

1. **Section Embeddings**: Successfully generated and stored 384-dimensional embeddings for all sections of 19 cases using the all-MiniLM-L6-v2 model.
2. **Document Structure**: Each case has been properly structured with section types (facts, discussion, questions, conclusion).
3. **Similarity Search**: We've verified the similarity search functionality works correctly for finding semantically related sections.
4. **Ontology**: The ProEthica intermediate ontology defines key types needed for ethical reasoning:
   - Roles (primary focus - role-based ethics)
   - Principles
   - Obligations
   - Conditions
   - Resources
   - Actions
   - Events
   - Capabilities

## Key Challenges

1. The current triples generated from guidelines may not be properly derived or comprehensive.
2. Need to ensure accurate semantic association between case sections and relevant triples.
3. Principles and Obligations need additional development in the ontology.
4. Need to create a batch process while carefully validating the associations.

## Implementation Plan

### Phase 1: Triple Analysis and Ontology Refinement

1. **Database Triple Analysis**
   - Examine existing triples in the database
   - Identify patterns in current guideline-to-triple associations
   - Categorize existing triples by ontology type (Role, Event, etc.)
   - Identify gaps in coverage, especially for Principles and Obligations

2. **Ontology Refinement**
   - Enhance the engineering-ethics ontology with additional Principles and Obligations
   - Add more specific Role subclasses based on engineering disciplines
   - Define clear relationships between Principles and Obligations
   - Update the ttl files with refined ontology elements

### Phase 2: Triple-to-Section Association Process Development

1. **Association Mechanism Design**
   - Create a section-to-triple association service similar to the existing GuidelineSectionService
   - Develop semantic similarity matching between section content and triple descriptions
   - Implement confidence scoring for triple-to-section relevance
   - Define storage format for the associations in document metadata

2. **Test Process on Sample Case**
   - Select a representative case (e.g., Case 267 "Public Welfare at What Cost?")
   - Manually create expected triple associations as ground truth
   - Test automated association against ground truth
   - Refine algorithm and scoring thresholds based on results

### Phase 3: Batch Processing Implementation

1. **Batch Association Script**
   - Develop a script to process all cases and their sections
   - Include logging and progress tracking
   - Implement error handling and recovery mechanisms
   - Create backup functionality for document metadata

2. **Validation and Verification Tools**
   - Create a tool to sample and manually review triple associations
   - Implement section-to-triple visualization for review
   - Develop metrics for association quality assessment
   - Create reports of coverage by ontology type

### Phase 4: Interactive Refinement System

1. **Section Association UI Enhancement**
   - Add triple association display to the document structure UI
   - Implement manual override and correction functionality
   - Support for filtering and sorting triples by type
   - Provide feedback mechanism for association quality

2. **Iterative Refinement Process**
   - Process cases in batches with manual review between iterations
   - Refine ontology based on missed associations
   - Update association algorithm parameters
   - Reprocess problematic cases or sections

## Technical Implementation Details

### Triple Storage and Querying

#### Triple Querying Implementation

We've implemented two specialized tools to query triples in our system:

**1. World-to-Triples Querying** (`list_world_triples.py`)

This tool retrieves triples associated with a specific world via its guidelines:

```python
def get_triples_for_world(conn, world_id, limit=50):
    """
    Get entity triples associated with a world through guidelines.
    """
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # First, get guideline IDs for this world
            cur.execute('SELECT id, title FROM guidelines WHERE world_id = %s', (world_id,))
            guidelines = cur.fetchall()
            
            # ... process guidelines and prepare query ...
            
            # Get triples associated with these guidelines
            placeholders = ', '.join(['%s'] * len(guideline_ids))
            query = f'''
                SELECT 
                    et.id,
                    et.subject,
                    et.predicate,
                    et.object_uri,
                    et.object_literal,
                    et.is_literal,
                    et.subject_label,
                    et.predicate_label,
                    et.object_label,
                    et.guideline_id,
                    et.entity_type
                FROM 
                    entity_triples et
                WHERE 
                    et.guideline_id IN ({placeholders})
                    AND et.entity_type = 'guideline_concept'
                ORDER BY 
                    et.guideline_id, et.id
                LIMIT %s
            '''
            
            # ... execute query and process results ...
    except Exception as e:
        print(f"Error retrieving triples: {e}")
        return []
```

**2. Guideline-to-Triples Querying** (`list_guideline_triples.py`)

This tool retrieves triples associated directly with a specific guideline:

```python
def get_triples_for_guideline(conn, guideline_id, entity_type='guideline_concept', limit=50):
    """
    Get entity triples associated with a guideline.
    """
    try:
        with conn.cursor() as cur:
            # Get triples associated with the guideline
            query = '''
                SELECT 
                    et.id,
                    et.subject,
                    et.predicate,
                    et.object_uri,
                    et.object_literal,
                    et.is_literal,
                    et.subject_label,
                    et.predicate_label,
                    et.object_label,
                    et.entity_type
                FROM 
                    entity_triples et
                WHERE 
                    et.guideline_id = %s
                    AND et.entity_type = %s
                ORDER BY 
                    et.id
                LIMIT %s
            '''
            
            # ... execute query and process results ...
    except Exception as e:
        print(f"Error retrieving triples: {e}")
        return []
```

Both tools support different output formats and can be used from the command line:

```bash
# World-level triples
./scripts/triple_toolkit/run_list_world_triples.sh --world-id 1 --limit 10
./scripts/triple_toolkit/run_list_world_triples.sh --world-id 1 --format detailed --limit 5

# Guideline-level triples
./scripts/triple_toolkit/run_list_guideline_triples.sh --guideline-id 43 --limit 10
./scripts/triple_toolkit/run_list_guideline_triples.sh --guideline-id 43 --format detailed --limit 5
```

### Semantic Triple Association

```python
def associate_triples_with_section(section_content, candidate_triples, confidence_threshold=0.5):
    """
    Associate relevant triples with a document section based on semantic similarity.
    
    Args:
        section_content: Text content of the section
        candidate_triples: List of candidate triples to match
        confidence_threshold: Minimum confidence score to include a triple
        
    Returns:
        List of associated triples with confidence scores
    """
    # Implementation will:
    # 1. Generate embedding for section content
    # 2. Compare with embeddings of triple descriptions
    # 3. Calculate confidence scores
    # 4. Filter by threshold
    # 5. Return matches
    pass
```

### Triple Categorization

```python
def categorize_triple_by_ontology_type(triple):
    """
    Categorize a triple based on the ontology type it represents.
    
    Args:
        triple: Triple dictionary with subject, predicate, object
        
    Returns:
        Ontology type (Role, Principle, etc.) and subtype if applicable
    """
    # Implementation will:
    # 1. Check predicate against known ontology type predicates
    # 2. Analyze object for class membership
    # 3. Parse subject and object for type indicators
    # 4. Return categorization information
    pass
```

## Progress Tracking

We'll track our progress through this plan using a simple status table that will be updated as we complete each phase:

| Phase | Task | Status | Notes | Completion Date |
|-------|------|--------|-------|----------------|
| 1 | Database Triple Analysis | In Progress | Created world-triples listing tool | 2025-05-22 |
| 1 | Ontology Refinement | Not Started | | |
| 2 | Association Mechanism Design | Not Started | | |
| 2 | Test Process on Sample Case | Not Started | | |
| 3 | Batch Association Script | Not Started | | |
| 3 | Validation and Verification Tools | Not Started | | |
| 4 | Section Association UI Enhancement | Not Started | | |
| 4 | Iterative Refinement Process | Not Started | | |

## Next Steps

1. ✓ Begin with Database Triple Analysis by querying and categorizing existing triples
   - Created `list_world_triples.py` tool for analyzing world-guideline-triple relationships
   - Created `list_guideline_triples.py` for targeted guideline concept analysis
   - Initial findings show key ethical concepts in the Engineering Ethics guideline:
     - Public Safety Primacy: "Engineers must prioritize public safety, health, and welfare above all other considerations"
     - Professional Competence: "Engineers should only perform work within their areas of expertise"
     - Truthfulness: "Engineers must communicate honestly and objectively in all professional statements"
     - Fiduciary Duty: Duty of care engineers owe to clients and employers
2. Continue with categorization of triples by ontology type (Role, Principle, etc.)
3. Develop initial categorization of section content by ontology type
4. Create a prototype association between a single case section and relevant triples
5. Review the results and refine the approach
6. Continue to the next steps based on initial findings

## Sample Queries for Triple Analysis

To start the triple analysis phase, we'll use the following SPARQL queries to examine the existing triples:

```sparql
# Query to find all Role-related triples
SELECT ?subject ?predicate ?object
WHERE {
  ?subject ?predicate ?object .
  ?object a <http://proethica.org/ontology/intermediate#Role> .
}
LIMIT 100

# Query to find Principles and Obligations
SELECT ?subject ?predicate ?object
WHERE {
  ?subject ?predicate ?object .
  {?object a <http://proethica.org/ontology/intermediate#EthicalPrinciple>} 
  UNION 
  {?object a <http://proethica.org/ontology/intermediate#ProfessionalResponsibility>}
}
LIMIT 100
