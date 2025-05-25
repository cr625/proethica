# Root Directory Cleanup - January 24, 2025

## Summary

Cleaned up the root directory from 167 files down to 20 essential files, organizing the rest into appropriate directories.

## Actions Taken

### Files Moved to `pending_delete/` (109 files)
**One-off analysis and processing files:**
- `analyze_*.py` - Case-specific analysis scripts
- `process_case_187_ontology.py` - Case 187 specific processing
- `reimport_case_23_4.py` - Case 23-4 specific import
- `import_*.py` - Various one-time import scripts
- `delete_*.py` - One-time deletion scripts
- `regenerate_*.py` - One-time regeneration scripts
- `investigate_*.py` - Investigation scripts for specific issues

**Test and debug files:**
- `*_test_results.json` - Test result files
- `enhanced_prediction_result_*.json` - Experiment results
- `llm_integration_results_*.json` - LLM integration test results
- `test_case_delete.html` - Test HTML file
- `*.bak` - Backup files
- `debug_*.py` - Debug Python scripts
- `run_debug_app.py` - Debug runners
- `simplified_debug_app.py` - Simplified debug versions

**Migration and update files:**
- `update_*.py` - One-time update scripts
- `migrate_*.py` - Database migration scripts
- `backup_before_db_fix.py` - Pre-fix backup script
- `patch_sqlalchemy_url.py` - Patch scripts
- `restore_guideline_190.py` - Restoration scripts

**Old documentation:**
- `ARCHIVED_PLANS.md` - Old planning documents
- `DOCUMENTATION_STRUCTURE_PLAN.md` - Planning documents
- `SECTION_TRIPLE_ASSOCIATION.md` - Moved to cases/docs
- `CODESPACE_*.md` - Codespace-specific docs
- `DEBUG_*.md` - Debug documentation
- `README_CODESPACE_SETUP.md` - Old setup docs

**Optimization and validation files:**
- `optimize_ontology_prediction_service*.py` - Optimization attempts
- `validate_case_252_clean_prediction.py` - Validation scripts
- `force_mock_llm_fix.py` - Force fixes
- `dual_layer_ontology_tagging.py` - Experimental features

**Miscellaneous one-offs:**
- `visualization.html` - Old visualization
- `case_list.txt` - Static case list
- `guideline_*.json` - Temporary guideline files
- `mcp_json_fixer.py` - JSON fixing utilities
- `mseo_ttl_downloader.py` - MSEO downloader
- `standalone_mseo_downloader.py` - Standalone version
- Log files and temporary outputs

### Files Moved to `scripts/` Directory (Added to existing scripts)
**Utility scripts:**
- `add_engineering_ethics_triples.py` - Add ethics triples
- `associate_triples_with_sections.py` - Triple association
- `batch_process_section_triples.py` - Batch processing
- `batch_update_embeddings.py` - Embedding updates
- `count_triple_types.py` - Count utilities
- `sync_ontology_to_database.py` - Sync utilities
- `view_case_triples.py` - View utilities

**Check and validation scripts:**
- `check_*.py` - Various check utilities
- `cleanup_*.py` - Cleanup utilities
- `query_*.py` - Query utilities
- `validate_*.py` - Validation utilities

**Setup and maintenance scripts:**
- `backup_database.sh` - Database backup
- `install_postgres_pgvector.sh` - PostgreSQL setup
- `restart_mcp_server.sh` - Server restart
- `setup_environment.sh` - Environment setup
- `setup_local_postgres_with_pgvector.sh` - Local setup
- `start_mcp_server_with_env.sh` - Server startup
- `start_proethica_updated.sh` - Application startup

**Debug and test scripts:**
- `debug_*.sh` - Debug shell scripts
- `test_flask_app_ui.sh` - UI testing

**Other utilities:**
- `correct_query_triples.py` - Query correction
- `list_*.py` - Listing utilities
- `find_*.py` - Finding utilities
- `generate_section_embeddings.py` - Embedding generation
- `section_triple_association_service.py` - Association service

## Files Remaining in Root (20 files)

### Configuration Files
- `.env` - Environment variables
- `.env.example` - Environment template
- `.gitignore` - Git ignore rules
- `.gitmodules` - Git submodules (empty)
- `config.py` - Application configuration
- `docker-compose.yml` - Docker configuration
- `postgres.Dockerfile` - PostgreSQL Docker setup

### Core Application Files
- `run.py` - Main application runner
- `setup.py` - Application setup

### Documentation
- `README.md` - Main project documentation
- `CLAUDE.md` - Project progress tracking
- `HOW_TO_START.md` - Getting started guide
- `LICENSE` - Project license

### Dependencies
- `requirements.txt` - Python dependencies
- `requirements-mcp.txt` - MCP-specific dependencies
- `consolidated_requirements.txt` - Consolidated dependencies
- `package.json` - Node.js dependencies
- `package-lock.json` - Node.js lock file

### Utilities
- `auto_run.sh` - Automated runner script
- `.db_initialized` - Database initialization marker

## Benefits Achieved

1. **Clarity**: Root directory now contains only essential files
2. **Organization**: Utility scripts properly organized in `/scripts/`
3. **Maintainability**: One-off files identified and segregated
4. **Reversibility**: All moved files preserved in case of need
5. **Standards**: Follows typical project structure conventions

## Next Steps

1. **Review**: Team should review pending_delete directory
2. **Cleanup**: After review period, permanently delete unnecessary files
3. **Documentation**: Update README if needed
4. **Maintenance**: Establish process to prevent root directory clutter

## Recovery

If any moved files are needed:
- Scripts can be moved back from `/scripts/` directory
- Other files can be recovered from `/pending_delete/` directory
- Git history preserves all file locations

## Statistics

- **Before**: 167 files in root directory
- **After**: 20 files in root directory
- **Reduction**: 88% fewer files in root
- **Organized**: 109 files to pending_delete, added to 108 scripts directory