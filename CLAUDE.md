# ProEthica Development Progress

## Deployment Infrastructure (Updated 4/11/2025)

Implemented a comprehensive deployment and Git workflow system:

1. **Multiple Deployment Options:**
   - Direct sync from local to production using rsync (tested & working)
   - Git-based deployment with full workflow support
   - Easy service restart on the production server

2. **Git Workflow Management:**
   - Implemented dev → main → production workflow
   - Created workflow script (`scripts/git_workflow.sh`) for managing branches and deployment
   - Added production sync script (`scripts/sync_from_production.sh`) for syncing back from production

3. **Git Authentication System:**
   - Created wizard for setting up GitHub authentication (`scripts/setup_git_auth.sh`)
   - Added conflict resolution tool for handling Git issues (`scripts/resolve_git_conflicts.sh`)
   - Implemented Windows SSH key management

4. **Documentation:**
   - Added detailed workflow guide (`docs/git_workflow.md`)
   - Created quick reference for Git authentication (`docs/git_auth_quickref.md`)
   - Added clear migration instructions (`docs/migration_clarification.md`)

5. **Next Steps:**
   - Test run the application in the WSL dev environment
   - Run the production update workflow and test on the server
   - Further automate with CI/CD integration if needed

## URL Processing for Case Import (Updated 4/7/2025)

Enhanced the case creation workflow with a comprehensive URL processing system:

1. **Three separate case creation workflows implemented:**
   - Upload document
   - Enter URL (enhanced)
   - Create manually

2. **URL Processor Architecture:**
   - `url_validator.py`: Validates URLs and checks reachability
   - `content_extractor.py`: Extracts and cleans HTML content
   - `patterns/nspe_patterns.py`: Extracts metadata using regex patterns
   - `llm_extractor.py`: Uses Claude to extract structured data
   - `triple_generator.py`: Converts extracted data to RDF triples 
   - `case_cache.py`: Caches processed URLs to avoid redundant processing
   - `correction_handler.py`: Handles user corrections
   - `case_processor.py`: Main orchestrator class
   
3. **Routes Updated:**
   - Enhanced URL processing in `routes/cases.py`
   - Added login requirement for URL processing routes

4. **Documentation and Testing:**
   - Added `docs/url_processor.md` with detailed documentation
   - Created `scripts/test_url_processor.py` for testing the processor
   - Added `scripts/clear_url_cache.py` for clearing the URL cache when needed

5. **Fixed Issues (4/7/2025):**
   - **Entity Type Error**: Resolved 'Invalid entity type: document' error by using 'entity' type instead
   - **Title Extraction**: Fixed title extraction logic for non-case URLs
   - **Content Extraction**: Added fallback content generation for problematic URLs
   - **Special NSPE Handling**: Created special handling for NSPE website URLs
   - **Cache Management**: Added cache clearing functionality to prevent stale issues

6. **Next Steps:**
   - **Triple Extraction**: Enhance triple extraction from article content
   - **Full Text Extraction**: Improve reliability of full text extraction from web pages
   - **Document Upload**: Enhance document upload workflow with similar extraction capabilities
   - **Triple Visualization**: Add visualization for extracted RDF triples
   - **UI Improvements**: Further improve edit case forms

## Database Management (Updated 4/8/2025)

When working with the database backup and restore functionality:

1. **Authentication Check**: Before running database backup or restore scripts, ensure that md5 authentication is properly configured for the postgres user in pg_hba.conf. This is crucial for password-based authentication to work correctly.

2. **Restore Process**: The restore script (`backups/restore_database.sh`) has been updated to include a reminder about the authentication requirement.

3. **Configuration Files**: If encountering authentication issues, check:
   - PostgreSQL configuration in pg_hba.conf
   - Database connection settings in the application's .env file
   - Password export in the backup/restore scripts

## IMPORTANT REMINDER
When returning to this project, focus first on:
1. Adding triples for extracted content
2. Enhancing full text extraction, especially for complex websites
3. Verifying database authentication settings before backup/restore operations
