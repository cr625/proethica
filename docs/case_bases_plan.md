  Plan for Changing "Case Studies" to "Cases"

  Based on the comprehensive inventory, here's a systematic plan to change all references from "Case Studies" to "Cases":

  Phase 1: Database Schema Changes

  1. Update Document Model
    - File: app/models/document.py
    - Change comment from "case studies" to "cases"
    - Consider if we need a database migration to change existing document_type='case_study' to document_type='case'
  2. Database Migration Strategy
    - Create a migration script to update all existing records:
    UPDATE documents SET document_type = 'case' WHERE document_type = 'case_study';

  Phase 2: Backend Code Changes

  1. Route Files (6 files to update):
    - app/routes/cases.py - Remove 'case_study' from all filter arrays
    - app/routes/worlds.py - Change document_type="case_study" to document_type="case"
    - app/routes/experiment.py - Update document type filters
    - app/routes/experiment_backup.py - Update document type filters
    - app/routes/cases_structure_update.py - Change document creation type
    - app/routes/cases_triple.py - Change document creation type
    - app/routes/document_structure.py - Update validation logic
  2. Service Files (1 file):
    - app/services/embedding_service.py - Update function documentation
  3. Utility Scripts (5 files):
    - utilities/process_nspe_url.py - Change default document_type
    - utilities/add_nspe_cases_to_engineering_ethics.py - Update document creation
    - utilities/test_process_case.py - Update test references
    - utilities/add_cases_to_world.py - Update default parameters
    - utilities/retrieve_cases.py - Update query filters

  Phase 3: Frontend Template Changes

  1. HTML Templates (4 files):
    - app/templates/world_detail_updated.html - Change "Case Studies" to "Cases" in headers and buttons
    - app/templates/world_detail.html - Update template variables
    - app/templates/create_case_options.html - Update help text
    - app/templates/world_detail_dynamic.html - Change icon text and counts

  Phase 4: Database Migration Scripts

  1. Migration Files (10+ files in scripts/database_migrations/):
    - Update all scripts that create documents with document_type='case_study'
    - Consider creating a cleanup script for existing data

  Phase 5: Documentation and Data Files

  1. Documentation (4 files):
    - docs/bfo_integration_guide.md
    - docs/cases/implementation/case_analysis_using_ontology.md
    - docs/embeddings/current_implementation.md
    - docs/url_processor.md
  2. Test Data (2 files):
    - data/test_cases.json - Update test case titles
    - data/case_triples/case_Case 02_5.json - Update descriptions

  Phase 6: Variable and Function Names

  1. Template Variables:
    - Change case_studies to cases in route handlers
    - Update template loops: {% for case in case_studies %} → {% for case in cases %}
  2. Function Parameters:
    - Update function signatures that reference case_study types

  Implementation Order

  1. Start with Database: Create migration script and update document types
  2. Backend Routes: Update all route files to use only 'case' document type
  3. Templates: Update UI text and variable names
  4. Utilities: Update processing scripts
  5. Documentation: Update all docs and comments
  6. Testing: Run full test suite to ensure nothing breaks

  Risk Mitigation

  1. Backup Database before running migrations
  2. Gradual Rollout: Consider supporting both 'case' and 'case_study' temporarily
  3. Template Compatibility: Ensure template variables work with existing data
  4. API Backward Compatibility: If there are external API consumers