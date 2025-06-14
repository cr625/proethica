# File Organization Summary

## Overview
Files have been reorganized to separate domain-generic (generalizable) content from domain-specific (engineering ethics) content to support the domain generalization initiative.

## Organization Structure

### `/docs/` - Domain-Generic Documentation
Contains documentation relevant to the generalization effort:
- `DOMAIN_GENERALIZATION_IMPLEMENTATION.md` - Main implementation tracking document
- `FILE_ORGANIZATION_SUMMARY.md` - This file
- `database/` - Generic database patterns and schemas
- `embeddings/` - Generic embedding infrastructure docs
- `llm/` - Generic LLM integration documentation
- `mcp_server_integration.md` - Generic MCP protocol docs
- `ontology/` - Generic ontology handling documentation
- `setup/` - Generic setup and installation guides
- Generic system docs (getting_started.md, command_cheat_sheet.md, CI/CD docs)

### `/docs/reference/` - Domain-Specific Reference
Moved engineering ethics specific documentation for future reference:
- `cases/` - NSPE case processing documentation
- `guidelines/` - Ethics guideline processing docs
- `papers/` - Ethics-specific papers and approaches
- `requirements/nspe_case_processing_requirements.txt` - NSPE-specific requirements
- `GUIDELINE_PREDICTION_ENHANCEMENT_PLAN.md`
- `phase1_guideline_analysis_report.md`
- `SCENARIO_DECONSTRUCTION_IMPLEMENTATION_PLAN.md`

### `/utils/` - Domain-Generic Utilities
Contains generic utility scripts and tools:
- `analyze_schema.py` - Generic schema analysis
- `create_test_user.py` - User management utility
- `test_simple_database_validation.py` - Database testing
- `test/` - Generic test files (moved from /tests/)
  - `test_all_routes.py`
  - `test_auth_routes.py`
  - `test_document_routes.py`
  - `test_entities_routes.py`
  - `test_mcp_api.py`
  - `test_scenarios_routes.py`
  - `test_simulation_controller.py`
  - `test_worlds_routes.py`
  - `conftest.py`

### `/utils/other/` - Domain-Specific Utilities
Moved engineering ethics specific scripts for future reference:
- `cleanup_orphaned_triples_guideline_8.py` - Guideline-specific cleanup
- `test_phase3_*.py` - Ethics case testing files
- `test_case_deconstruction.py` - Case-specific testing

## Files Left in Place
The following files remain in their original locations as they are core to the application:
- `config.py` - Core configuration
- `run.py` - Application runner
- `setup_project.py` - Project setup
- `init-pgvector.sql` - Database initialization
- `README.md` - Project readme
- `CLAUDE.md` - AI assistant instructions
- `HOW_TO_START.md` - Getting started guide
- Generic documentation (UI_REFRESH_*.md, TYPE_MANAGEMENT_*.md)

## Benefits of This Organization

1. **Clear Separation**: Domain-generic vs domain-specific content is clearly separated
2. **Focus**: Developers can focus on generic infrastructure without distraction
3. **Preservation**: Domain-specific content is preserved for reference
4. **Modularity**: Supports the adapter pattern implementation
5. **Scalability**: Easy to add new domains without cluttering generic docs

## Next Steps
1. Use the implementation tracking document to guide development
2. Reference domain-specific files when creating the engineering adapter
3. Keep generic documentation updated as the framework evolves
4. Move additional files to appropriate locations as discovered