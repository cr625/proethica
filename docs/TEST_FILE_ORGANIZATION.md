# Test File Organization Summary

## Overview
All `test_*.py` files from the root directory have been organized based on their domain relevance.

## Files Moved to `/utils/test/` (Domain-Generic)
These tests cover generic functionality that could work with any domain:

1. **test_enhanced_schema.py** - Database schema for enhanced guideline associations
2. **test_type_mapping_database.py** - Generic type mapping database functionality
3. **test_mcp_field_mapping_fix.py** - MCP protocol field mapping
4. **test_real_mcp_scenario.py** - MCP response handling
5. **test_association_service.py** - Guideline association service
6. **test_document_19.py** - Document retrieval and processing
7. **test_concept_remapping.py** - Concept type remapping
8. **test_existing_data_migration.py** - Data migration for type assignments

## Files Moved to `/utils/other/` (Domain-Specific)
These tests are specific to engineering ethics:

1. **test_adapter_simple.py** - Tests EngineeringEthicsAdapter for NSPE cases
2. **test_real_case_deconstruction.py** - Case deconstruction for Engineering Ethics world
3. **test_scenario_generation.py** - Scenario generation using NSPE cases
4. **test_ontology_entity_matching.py** - Engineering ethics concept matching

## Benefits
- **Clear separation** between generic infrastructure tests and domain-specific tests
- **Easier to identify** which tests need updating when generalizing
- **Better organization** for adding tests for new domains
- **Cleaner root directory** with all test files properly categorized

## Current Test Organization
```
utils/
├── test/                    # Generic tests (16 files)
│   ├── conftest.py
│   ├── test_all_routes.py
│   ├── test_association_service.py
│   ├── test_auth_routes.py
│   ├── test_concept_remapping.py
│   ├── test_document_19.py
│   ├── test_document_routes.py
│   ├── test_enhanced_schema.py
│   ├── test_entities_routes.py
│   ├── test_existing_data_migration.py
│   ├── test_mcp_api.py
│   ├── test_mcp_field_mapping_fix.py
│   ├── test_real_mcp_scenario.py
│   ├── test_scenarios_routes.py
│   ├── test_simulation_controller.py
│   ├── test_type_mapping_database.py
│   └── test_worlds_routes.py
└── other/                   # Domain-specific (8 files)
    ├── cleanup_orphaned_triples_guideline_8.py
    ├── test_adapter_simple.py
    ├── test_case_deconstruction.py
    ├── test_ontology_entity_matching.py
    ├── test_phase3_case_generation.py
    ├── test_phase3_llm_reasoning.py
    ├── test_real_case_deconstruction.py
    └── test_scenario_generation.py
```