# ProEthica Development Notes

## 2025-05-11 - Fixed PostgreSQL Configuration in WSL Environment

### Issue
When running the `start_proethica_updated.sh` script in a WSL environment, the system was trying to start the native PostgreSQL service unnecessarily, despite the project being configured to use a Docker PostgreSQL container on port 5433. This resulted in the error message:
```
Detected WSL environment
Starting in WSL mode using Flask dev server...
PostgreSQL is not running. Starting it...
You might need to enter your sudo password.
```

### Investigation
1. The `docker-compose.yml` file confirmed that PostgreSQL should be running in a Docker container on port 5433.
2. The `.env` file correctly referenced the Docker PostgreSQL with `DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm`.
3. In `start_proethica_updated.sh`, native PostgreSQL was properly stopped to avoid port conflicts.
4. However, in `auto_run.sh`, there was problematic code that:
   - First stopped the native PostgreSQL service (which was redundant)
   - Then checked if PostgreSQL was running using `pg_isready`, and if not, started the native PostgreSQL service again
   - This effectively undid the stopping of PostgreSQL from the previous script

### Solution
Modified `auto_run.sh` in the WSL environment section to:
1. Stop native PostgreSQL service if running (kept this as a safety measure)
2. Check if Docker PostgreSQL is running specifically on port 5433 (not the default 5432)
3. Provide a helpful message if Docker PostgreSQL is not running, suggesting how to start it
4. Remove the problematic code that was starting native PostgreSQL

### Results
- The startup script no longer attempts to start the native PostgreSQL service
- The system now properly checks for Docker PostgreSQL on port 5433
- Eliminates the unnecessary sudo password prompt during startup
- Provides more helpful error messages if Docker PostgreSQL is not running


## 2025-05-11 - Ontology File Fix and MCP Server Configuration

### Issue
The ProEthica application was started using `start_proethica_updated.sh`, but the database entries were not showing up. Specifically, the BFO ontology and proethica-intermediate ontology were not accessible through the ontology editor.

### Investigation
1. Initial diagnostics showed the MCP server could access the ontologies, but wasn't returning any entities.
2. Testing revealed format issues with the TTL files:
   - The ontology files (bfo.ttl, proethica-intermediate.ttl, and engineering-ethics.ttl) had unexpected '+' characters at line endings
   - These characters prevented proper parsing by RDFLib

3. Path inconsistency discovered:
   - The MCP server was looking for proethica-intermediate.ttl at `/home/chris/ai-ethical-dm/mcp/ontology/` 
   - But the file was located at `/home/chris/ai-ethical-dm/ontologies/`

### Solution
1. Created and ran a script `clean_ttl_files.py` to remove the problematic '+' characters from the TTL files
2. Added symbolic links from the main ontologies directory to the mcp/ontology directory:
   ```bash
   mkdir -p mcp/ontology
   ln -sf "$PWD/ontologies/bfo.ttl" mcp/ontology/bfo.ttl
   ln -sf "$PWD/ontologies/proethica-intermediate.ttl" mcp/ontology/proethica-intermediate.ttl
   ln -sf "$PWD/ontologies/engineering-ethics.ttl" mcp/ontology/engineering-ethics.ttl
   ```
3. Restarted the unified ontology server with the script `restart_unified_ontology_server.sh`

### Results
- The MCP server now successfully accesses all ontologies (bfo, proethica-intermediate, and engineering-ethics)
- Entity counts are as expected:
  - bfo: 36 entities
  - proethica-intermediate: 47 entities
  - engineering-ethics: 113 entities
- The ontology editor can now properly display these ontologies

### Scripts Created/Updated
1. `scripts/clean_ttl_files.py` - Cleans TTL files by removing problematic characters
2. `scripts/check_all_ontologies.py` - Verifies that ontology files can be parsed correctly
3. `scripts/test_bfo_parsing.py` - Tests specific parsing of the BFO ontology
4. `scripts/restart_unified_ontology_server.sh` - Properly restarts the unified ontology server

### Future Recommendations
1. Implement regular validation of ontology files as part of the build/start process
2. Consider standardizing the paths for ontology files to prevent path inconsistencies
3. Add error handling in MCP server to detect and report TTL parsing issues more clearly
ProEthica Development Log

## 2025-05-11: Created Ontology-Focused Branch

Created a new branch based on the realm-integration branch to focus on enhancing the ontology functionality of ProEthica. This branch is specifically focused on developing ontology-based case analysis capabilities.

### Changes Made:

1. **Created ontology-focused branch** from the realm-integration branch
2. **Fixed database and MCP server configuration**:
   - Set MCP server port to 5001 in `.env` and `start_proethica_updated.sh`
   - Fixed URL escape sequence issues in the MCP client
   - Updated database connection configuration for WSL environment

3. **Created documentation**:
   - Added detailed ontology case analysis plan in `docs/ontology_case_analysis_plan.md`
   - Updated `ONTOLOGY_ENHANCEMENT_README.md` with branch information

### Next Steps:

1. Implement case analysis module in the unified ontology server
2. Create database tables for case analysis
3. Develop API endpoints for case analysis
4. Integrate with the ProEthica UI

## 2025-05-11: Tested Updated ProEthica Application

Ran the updated application using the `start_proethica_updated.sh` script and documented the results.

### Findings:

1. **Unified Ontology MCP Server Status**:
   - Successfully started on port 5001 (PID 84043)
   - Server health check passed: `/health` endpoint returns `{"status": "ok", "service": "unified-ontology-mcp"}`
   - Loaded modules: "query" and "case_analysis" with 8 tools in total
   - No ontology data found: `/api/entities/engineering` returns empty list
   - Error loading temporal_module due to missing abstract method implementations: "Can't instantiate abstract class TemporalModule without an implementation for abstract methods 'description', 'name'"
   - Warning about missing relationship_module.py

2. **Database Status**:
   - PostgreSQL Docker container 'postgres17-pgvector-wsl' running on port 5433
   - Most database tables verified, but 'triples' table was reported as missing

3. **Application Startup Issues**:
   - Port conflict: both Unified Ontology Server and enhanced MCP server configured to use port 5001
   - Flask web application failed to start due to this port conflict

### Required Fixes:

1. **Port Conflict Resolution**:
   - Either stop the Unified Ontology Server before trying to start the enhanced MCP server
   - Or modify configuration to use different ports for each service

2. **Module Implementation Issues**:
   - Fix `temporal_module.py` to properly implement abstract methods
   - Create missing `relationship_module.py` file

3. **Database Schema Issue**:
   - Create missing 'triples' table in the database schema

4. **SQLAlchemy Configuration Issue**:
   - Fix URL parsing error: `Could not parse SQLAlchemy URL from string 'postgresql\x3a//postgres\x3aPASS@localhost\x3a5433/ai_ethical_dm'`
   - URL contains escape sequences that need to be properly handled

5. **Ontology File Missing**:
   - Ontology file not found: engineering-ethics.ttl
   - Need to create or properly load this ontology file

## 2025-05-11: Fixed Module Issues

Addressed two critical module issues that were preventing proper initialization of the Unified Ontology Server:

### Fixed Issues:

1. **TemporalModule Implementation**:
   - Fixed the `temporal_module.py` implementation by properly implementing the required abstract methods:
     - Added `@property` methods for `name` and `description`
     - These properties were previously incorrectly set in the constructor instead of being implemented as methods
   - Error caused by: "Can't instantiate abstract class TemporalModule without an implementation for abstract methods 'description', 'name'"

2. **RelationshipModule Creation**:
   - Created the missing `relationship_module.py` file with a complete implementation
   - Implemented all required abstract methods and properties
   - Added placeholder implementations for relationship management functions:
     - get_entity_relationships
     - find_path_between_entities
     - create_relationship
     - get_relationship_types
     - analyze_relationship_network

## 2025-05-11: Fixed Startup Script and Database Verification

Addressed issues that were causing server conflicts and database verification errors:

### Fixed Issues:

1. **Server Duplication Issue**:
   - Modified `start_proethica_updated.sh` to set an environment variable `MCP_SERVER_ALREADY_RUNNING=true` before calling `auto_run.sh`
   - Updated `auto_run.sh` to check for this environment variable and skip starting another MCP server if it's already running
   - This resolves the port conflict where both scripts were trying to start an MCP server on port 5001

2. **Database Table Name Mismatch**:
   - Updated `scripts/initialize_proethica_db.py` to check for 'entity_triples' table instead of 'triples'
   - This aligns the verification script with the actual database schema

### Remaining Issues:

1. **SQLAlchemy URL Parsing**:
   - There's still an issue with escape sequences in the database URL: `postgresql\x3a//postgres\x3aPASS@localhost\x3a5433/ai_ethical_dm`
   - The `.env` file has the correct URL without escape sequences
   - `initialize_proethica_db.py` works around this by setting the URL directly
   - The `mcp_client.py` has similar escape sequence handling for the MCP server URL

2. **Ontology File Loading**:
   - The system seems to be looking for file-based ontologies like "engineering-ethics.ttl" instead of loading from the database
   - The ontology data should be served from the database as configured

## Future Work

As outlined in the ontology case analysis plan, future enhancements will include:

- Implementing temporal reasoning for case analysis
- Adding support for comparing multiple cases
- Developing machine learning integration for case similarity analysis
- Creating ethical reasoning enhancements based on ontology rules

## Ontology Recovery Process - 2025-05-11 10:26:18

### Summary
The database restoration was necessary to recover the ontology data. While the application was running, 
the ontology data wasn't showing up in the editor. We restored the database from a backup and exported 
the ontology TTL files for better stability.

### Restored Ontologies
The following ontologies were successfully recovered:

- **bfo.ttl**: 541114 bytes
- **proethica-intermediate.ttl**: 82536 bytes
- **engineering-ethics.ttl**: 123651 bytes

### Next Steps
1. Ensure the ontology editor can access and use these ontologies
2. Test loading and editing the ontologies in the editor
3. Consider setting up a regular backup process for both the database and TTL files

### Technical Details
- Used database backup: `ai_ethical_dm_backup_20250428_000814.dump`
- Created export script to generate TTL files from the database ontology content
- Files are now available both in the database and as TTL files in the ontologies directory

## 2025-05-11: Fixed Redundant Initialization in Startup Scripts

### Issue
When running `start_proethica_updated.sh`, various components were being initialized twice, causing inefficiency and potential conflicts:

1. MCPClient was being initialized twice
2. Claude service was initialized twice
3. SentenceTransformer was loaded twice
4. EnhancedMCPClient was initialized twice
5. Database was initialized twice

### Investigation
1. Analyzed the output of `start_proethica_updated.sh` and identified the redundant initializations
2. Found that while `start_proethica_updated.sh` was setting `MCP_SERVER_ALREADY_RUNNING=true`, the condition was only being checked in the codespace section of `auto_run.sh`
3. The WSL and generic development environment sections of `auto_run.sh` were not checking this flag before trying to restart the MCP server

### Solution
Modified `auto_run.sh` to respect the `MCP_SERVER_ALREADY_RUNNING` environment variable in all environment sections:
1. Updated the WSL environment section to check if MCP server is already running
2. Updated the development environment section to do the same check
3. Left the codespace section unchanged as it was already correctly handling this case

### Results
- Running `start_proethica_updated.sh` no longer results in duplicate initializations
- The unified ontology server is started once and reused
- Eliminates confusion from seeing the same initialization messages twice
- Startup process is more efficient and has less potential for conflicts

## 2025-05-11: Fixed Flask Application Factory Pattern Import Issue

### Issue
When running the startup script `./start_proethica_updated.sh`, an error was displayed:
```
Discovered model: World
Could not extract routes from Flask URL map: cannot import name 'app' from 'app' (/home/chris/ai-ethical-dm/app/__init__.py)
```

### Investigation
1. Identified that the MCP server and other components were trying to import a global `app` instance directly from the app package
2. Examined the codebase and found that it was using the Flask "application factory" pattern where `create_app()` is exported from `app/__init__.py` instead of a globally defined app variable
3. Found three files with incorrect import patterns:
   - `app/services/application_context_service.py`: Attempted to import `app` directly instead of using `create_app()`
   - `mcp/http_ontology_mcp_server.py`: Imported `db` before creating the app context
   - `mcp/unified_ontology_server.py`: Lacked a comment about proper import order

### Solution
1. In `app/services/application_context_service.py`:
   - Changed `from app import app` to `from app import create_app`
   - Added code to create the app instance with `app = create_app()`

2. In `mcp/http_ontology_mcp_server.py`:
   - Fixed import order to properly create app context before importing db
   - Changed from:
     ```python
     from app import create_app, db
     ```
   - To:
     ```python
     from app import create_app
     app = create_app()
     from app import db  # Import db after creating app context
     ```

3. In `mcp/unified_ontology_server.py`:
   - Added comment to clarify proper import sequence

### Results
- The error "cannot import name 'app' from 'app'" no longer appears
- The Flask application factory pattern is now used correctly in all components
- Routes extraction from Flask URL map should now work properly
- System is better aligned with Flask best practices

### Lessons Learned
- When using Flask's application factory pattern, it's important to consistently follow the correct import pattern throughout the codebase
- Services that need to access Flask components should create their own app instance using the `create_app()` function
- Database access (`db`) requires an active app context, so import order matters

## 2025-05-11: Identified Circular Dependency in Application Initialization

### Issue
When running the `start_proethica_updated.sh` script, the system encountered a critical error with an infinite recursion problem during initialization:

```
RecursionError: maximum recursion depth exceeded
```

### Investigation
Analyzed the error stack trace and identified a circular dependency chain in the application initialization:

1. `create_app()` calls `create_proethica_agent_blueprint()`
2. `create_proethica_agent_blueprint()` instantiates `ProEthicaContextProvider()`
3. `ProEthicaContextProvider()` calls `ApplicationContextService.get_instance()`
4. `ApplicationContextService.get_instance()` calls `ApplicationContextService()`
5. `ApplicationContextService()` calls `_build_navigation_map()`
6. `_build_navigation_map()` calls `create_app()` again, creating an infinite loop

### Affected Files
The circular dependency involves these key files:
- `app/__init__.py`: The `create_app()` function
- `app/agent_module/__init__.py`: The `create_proethica_agent_blueprint()` function
- `app/agent_module/adapters/proethica.py`: The `ProEthicaContextProvider.__init__()` method
- `app/services/application_context_service.py`: The circular dependency involving `_build_navigation_map()`

### Recommended Solution
To resolve this circular dependency, the application architecture needs to be refactored in one of these ways:

1. Redesign the `ApplicationContextService` to use lazy initialization for the navigation map, avoiding the call to `create_app()` during initialization
2. Implement a parameter in `create_app()` to prevent recursive calls, like a `skip_context_service` flag
3. Use dependency injection to provide the navigation map to `ApplicationContextService` after application startup
4. Set up a guard condition in the recursive path to prevent infinite loops

### Next Steps
1. Apply the selected solution approach to break the circular dependency
2. Test the implementation thoroughly to ensure all components initialize correctly
3. Add unit tests to verify the system's resilience against circular dependencies
4. Update documentation to explain the architectural choices and initialization flow

## 2025-05-11: Resolved Circular Dependency in Application Initialization

### Solution Implemented
Implemented a lazy loading mechanism for the navigation map in the `ApplicationContextService` class to resolve the circular dependency:

1. Modified `ApplicationContextService.__init__()` to initialize a `_navigation` property as `None` instead of directly calling `_build_navigation_map()`
2. Created a new property getter `navigation` that lazily initializes the navigation map only when first accessed
3. Modified `_build_navigation_map()` to use `flask.current_app` instead of importing and creating a new app

### Code Changes
The key changes in `app/services/application_context_service.py`:

```python
def __init__(self):
    # ...
    # Use lazy initialization for navigation map to avoid circular dependency
    self._navigation = None
    # ...

@property
def navigation(self) -> Dict[str, Any]:
    """
    Property to lazily initialize and access the navigation map.
    This breaks the circular dependency with Flask app creation.
    """
    if self._navigation is None:
        self._navigation = self._build_navigation_map()
    return self._navigation
        
def _build_navigation_map(self) -> Dict[str, Any]:
    # ...
    # Try to extract routes from Flask's URL map if we're in a Flask context
    from flask import current_app
    if current_app:
        try:
            if hasattr(current_app, 'url_map'):
                # Use existing app context
                # ...
```

### Results
1. The application now starts successfully without recursive errors
2. The Flask server starts properly and the ontology editor loads correctly
3. Database tables are created successfully and verified
4. The unified ontology MCP server functions normally

### Benefits of the Solution
1. Breaks the circular dependency in a clean, maintainable way
2. Follows the principle of lazy initialization for resource-intensive operations
3. Improves startup performance as navigation map is only built when needed
4. No longer imports and creates redundant Flask app instances
5. Aligns with Flask best practices by using `current_app` proxy

### Documentation
1. Updated `docs/startup_failure_analysis.md` with detailed explanation of the issue and solution
2. Recorded the implementation in CLAUDE.md to document the work
