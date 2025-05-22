# Ontology Enhancement Implementation Plan

## 1. Project Overview
- **Objective**: Enhance the engineering-ethics ontology using guideline triples while maintaining proper integration with the proethica-intermediate ontology
- **Timeline**: May 22, 2025 - Ongoing
- **Key deliverables**: Updated engineering-ethics.ttl and potentially proethica-intermediate.ttl files

## 2. Implementation Phases

### Phase 1: Extraction and Analysis
- [x] 1.1 Retrieve all guideline triples from Engineering Ethics guideline (ID 43)
- [x] 1.2 Group triples by subject to identify distinct concepts
- [x] 1.3 Normalize concept data (extract identifiers, labels, descriptions)
- [x] 1.4 Clean descriptions by removing formulaic prefixes
- [x] 1.5 Categorize concepts by type (principle, role, action, etc.)

### Phase 2: Existing Class Refinement
- [x] 2.1 Audit existing engineering-ethics.ttl classes
- [x] 2.2 Check for naming consistency, description quality, property usage
- [x] 2.3 Identify classes needing improvement
- [x] 2.4 Refine existing class definitions
- [x] 2.5 Assess ontology organization (domain-general vs. domain-specific)

### Phase 3: Two-Way Refinement
- [x] 3.1 Identify concepts for proethica-intermediate.ttl enhancement
- [x] 3.2 Prepare plan for enhancing proethica-intermediate.ttl
- [x] 3.3 Prepare engineering-specific concepts for engineering-ethics.ttl
- [x] 3.4 Add new concepts to engineering-ethics.ttl
- [x] 3.5 Ensure proper referencing between ontologies

### Phase 4: Semantic Enhancement
- [x] 4.1 Design semantic matching properties for all classes
- [x] 4.2 Implement semantic matching properties
- [x] 4.3 Create coherent class groupings
- [x] 4.4 Final validation and consistency check
- [x] 4.5 Documentation of implementation plan

## 3. Implementation Log
| Date | Phase | Step | Status | Notes |
|------|-------|------|--------|-------|
| 2025-05-22 | 1 | 1.1 | Complete | Retrieved guideline triples using run_list_guideline_triples.sh |
| 2025-05-22 | 1 | 1.2 | Complete | Grouped and analyzed concepts in guideline_concept_analysis.md |
| 2025-05-22 | 1 | 1.3-1.5 | Complete | Normalized and categorized concepts by type |
| 2025-05-22 | 2 | 2.1-2.5 | Complete | Completed audit of engineering-ethics.ttl in engineering_ethics_ontology_audit.md |
| 2025-05-22 | 3 | 3.1-3.3 | Complete | Identified concepts for both ontologies and prepared implementation plan |
| 2025-05-22 | 3 | 3.4 | Complete | Added 5 new classes to engineering-ethics.ttl from guideline concepts |
| 2025-05-22 | 3 | 3.5 | Complete | Fixed reference integrity between ontologies |
| 2025-05-22 | 4 | 4.1, 4.5 | Complete | Designed semantic matching properties and documented implementation plan |
| 2025-05-22 | 4 | 4.2 | Complete | Added semantic matching properties to 5 new principle classes |
| 2025-05-22 | 4 | 4.3 | Complete | Created coherent groupings for principle classes |
| 2025-05-22 | 4 | 4.4 | Complete | Validated ontologies with validate_ontologies.py - all tests passing |
| 2025-05-22 | - | - | Complete | Fixed circular references in engineering-ethics.ttl |
| 2025-05-22 | - | - | Complete | Created test_ontology_enhancement.py to verify enhancements |

## 4. Decisions and Observations
- **Structural decisions**: 
  - Engineering-specific concepts will remain in engineering-ethics.ttl
  - Domain-general concepts will be moved to proethica-intermediate.ttl if not already present
  - All concepts will include matching properties for section association

- **Pattern observations**:
  - Many guideline triples use formulaic prefixes in descriptions that should be normalized (e.g., "The principle that...", "The obligation for...")
  - Some concepts may already exist in the ontology with different naming conventions
  - Duplicate concepts exist with different URI formats (underscore vs hyphen)
  - Concepts with hyphen-format URIs have additional properties like hasCategory, relatedTo, and hasTextReference
  - Categories in the triples provide useful classification hints (e.g., "core ethical principle", "professional obligation", "communication ethics")

- **Challenges encountered**:
  - Need to ensure proper hierarchy between intermediate and domain-specific ontologies
  - Maintaining consistent naming and description patterns across both ontologies

- **Improvement opportunities**:
  - Add semantic matching properties to facilitate section-triple association
  - Standardize description formats for improved readability and matching

## 5. Results and Verification
- **Concept coverage**: Added 5 new principle classes derived from core engineering ethics concepts
- **Validation tests**: All ontology validation tests passing with validate_ontologies.py
- **Semantic properties**: Added hasCategory, hasMatchingTerm, hasTextReference, and hasRelevanceScore properties to facilitate semantic matching
- **Improvements**: Fixed 4 circular reference issues and 1 reference integrity issue
- **Testing**: Created test_ontology_enhancement.py to verify ontology enhancements

## 6. Next Steps
- Integrate the enhanced ontologies with the section-triple association service
- Test the association service with the new semantic properties
- Monitor performance and fine-tune as needed
- Consider adding semantic properties to more existing classes in the ontology
