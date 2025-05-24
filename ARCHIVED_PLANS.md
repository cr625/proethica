# Archived Planning Documents

This file provides a brief summary of planning documents for historical reference. These documents contain early designs, iterations, and ideas that may or may not have been implemented.

## Section Triple Association Plans

### `/cases/docs/section_embedding_and_triple_association_analysis.md`
**Purpose**: Initial analysis of section embedding architecture and its relationship with ontology triples.
**Key Points**:
- Analyzed the generation process for section embeddings
- Identified limitations in direct association between embeddings and triples
- Proposed enhanced association pipeline with two-phase matching
- Outlined database structure and integration points

### `/cases/docs/section_triple_association_plan.md`
**Purpose**: Original implementation plan for section-triple associations.
**Key Points**:
- Defined the core architecture components
- Specified the two-phase matching algorithm
- Outlined database schema requirements
- Listed implementation milestones

### `/cases/docs/updated_section_triple_association_plan.md`
**Purpose**: Revised plan incorporating lessons learned from initial implementation.
**Key Points**:
- Addressed embedding space mismatch issues
- Refined similarity threshold recommendations
- Updated integration strategy with document pipeline

### `/cases/docs/section_triple_association_progress.md`
**Purpose**: Progress tracking document for implementation.
**Key Points**:
- Documented completed tasks and fixes
- Tracked UI integration progress
- Listed remaining issues and next steps
- Included technical notes on solutions

### `/cases/docs/llm_section_triple_association_plan.md`
**Purpose**: Plan for implementing LLM-based approach to improve association quality.
**Key Points**:
- Identified limitations of pure embedding approach
- Proposed multi-metric approach using LLM
- Defined implementation steps and testing checkpoints
- Specified success criteria

## Other Planning Documents

### `/docs/document_structure_enhancement_plan.md`
**Purpose**: Plan for enhancing document structure storage and processing.
**Status**: Check implementation status in codebase.

### `/docs/startup_optimization_plan.md`
**Purpose**: Plan for optimizing application startup performance.
**Status**: May be partially implemented.

### `/docs/future_development_plans.md`
**Purpose**: Long-term roadmap for the project.
**Status**: Living document with future features.

### `/docs/archived/simulation_implementation_plan.md`
**Purpose**: Plan for implementing ethical simulation features.
**Status**: Archived - may not be current priority.

### `/docs/archived/realm_integration_plan.md`
**Purpose**: Plan for integrating REALM material science capabilities.
**Status**: Archived - separate module development.

### `/docs/archived/update_to_case_processing_pipeline_plan.md`
**Purpose**: Plan for updating the case processing pipeline.
**Status**: Archived - likely superseded by current implementation.

## Usage Note

These planning documents represent various stages of the project's evolution. When implementing new features:
1. Check if a relevant plan exists
2. Review what was actually implemented vs. planned
3. Update or create new documentation as needed
4. Move outdated plans to the archived folder