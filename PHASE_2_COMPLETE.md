# Phase 2 Complete: Database Schema for Section Prompts

**Date**: 2025-10-01
**Status**: ✅ COMPLETED

## What Was Accomplished

### 1. Database Table Created
- **Table**: `extraction_section_prompts`
- **Purpose**: Store section-specific prompts for multi-section NSPE case extraction
- **Separate from**: `section_prompt_templates` (used for LangExtract ontology-driven extraction)

### 2. Schema Features
- **Section identification**: section_type, extraction_pass, concept_type
- **Prompt components**: system_prompt, instruction_template, examples (JSONB)
- **Section-specific guidance**: extraction_guidance field
- **Versioning**: version tracking with created_at/updated_at
- **Usage statistics**: times_used, avg_entities_extracted, avg_confidence
- **Constraints**: Validation for section types, passes (1-4), concept types

### 3. Baseline Prompts Seeded
**9 prompts for Facts section** (working baseline from current implementation):
- **Pass 1 (Contextual)**: roles, states, resources
- **Pass 2 (Normative)**: principles, obligations, constraints, capabilities
- **Pass 3 (Temporal)**: actions, events

### 4. SQLAlchemy Model Created
**File**: `/app/models/extraction_section_prompt.py`

**Key methods**:
- `get_prompt_for_section()` - Get prompt for specific section/pass/concept
- `get_all_prompts_for_section()` - Get all prompts for section and pass
- `get_all_prompts_for_pass()` - Get all prompts for a pass
- `record_usage()` - Track usage statistics

### 5. Testing Completed
**All tests passed**:
- ✓ Model queries work correctly
- ✓ Baseline prompts accessible
- ✓ Usage statistics recording works
- ✓ 9 active prompts in database

## Database Location
- **Database**: `ai_ethical_dm` (ProEthica)
- **Table**: `extraction_section_prompts`
- **Migration Script**: `/db_migration/add_extraction_section_prompts.sql`

## Next Steps (Phase 3)
Ready to implement Discussion section extraction with entity matching:
1. Create step1b route for Discussion extraction
2. Implement EntityMatchingService for cross-section references
3. Build step1b template showing entity matching
4. Add Discussion prompts to database

## PROV-O Decision
**Decision**: Keep provenance distributed with shared ontology reference
- ✅ ProEthica keeps PROV tables in `ai_ethical_dm`
- ✅ OntServe keeps PROV-O ontology as reference
- ✅ Extend existing ProvenanceService for multi-section tracking
- No architectural changes needed NOW

