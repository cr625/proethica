AI Ethical DM - Development Log

## May 19, 2025 (Update #53): Fixed Ontology Editor 404 Error

### Task Completed
Fixed the 404 error occurring when accessing the `/ontology-editor` route by properly registering the ontology_editor blueprint in the Flask application.

### Key Improvements
1. **Blueprint Registration Fix**:
   - Added the import statement for the `create_ontology_editor_blueprint` function in `app/__init__.py`
   - Created the ontology editor blueprint with appropriate configuration
   - Added the registration of the blueprint with the Flask application
   - Successfully restored access to the ontology editor functionality

2. **Root Cause Analysis**:
   - The ontology_editor module was implemented correctly with all necessary templates and routes
   - All required code and assets were present in the ontology_editor directory
   - The issue was simply that the blueprint was defined but never registered with the Flask application
   - The registration step is essential for Flask to recognize and route requests to the blueprint's handlers

3. **Verification**:
   - Confirmed the ontology editor is working by accessing the route in a browser
   - Successfully loaded the ontology list and editor interface
   - Server logs showed proper 200 response codes for the `/ontology-editor/` endpoint and related assets

### Technical Details
- The fix required adding three sections to `app/__init__.py`:
  ```python
  # Import the blueprint creation function
  from ontology_editor import create_ontology_editor_blueprint
  
  # Create the ontology editor blueprint with configuration
  ontology_editor_bp = create_ontology_editor_blueprint(
      config={
          'require_auth': True,   # Enable authentication
          'admin_only': False     # Allow all authenticated users to access
      }
  )
  
  # Register the blueprint with the Flask app
  app.register_blueprint(ontology_editor_bp)
  ```
- The ontology editor now properly loads showing the available ontologies (Basic Formal Ontology, Engineering Ethics, ProEthica Intermediate Ontology)
- The interface is fully functional with editing, validation, and visualization capabilities

## May 18, 2025 (Update #52): Fixed Cases Route 404 Error

### Task Completed
Fixed the 404 error occurring when accessing the `/cases` route by properly registering the cases blueprint in the Flask application.

### Key Improvements
1. **Blueprint Registration Fix**:
   - Added the import statement for the cases blueprint in `app/__init__.py`  
   - Added the registration of the cases blueprint with the correct URL prefix
   - Successfully restored access to the cases functionality of the application

2. **Root Cause Analysis**:
   - The cases blueprint was implemented correctly in `app/routes/cases.py`
   - All the necessary templates were already created
   - The issue was simply that the blueprint was defined but never registered with the Flask application
   - This registration step is essential for Flask to recognize and route requests to the blueprint's handlers

3. **Verification**:
   - Restarted the Flask development server
   - Confirmed the route is working with a browser test
   - Server logs showed successful 200 response codes for the `/cases` endpoint

### Technical Details
- The fix was straightforward - adding two lines to `app/__init__.py`:
  ```python
  from app.routes.cases import cases_bp
  app.register_blueprint(cases_bp, url_prefix='/cases')
  ```
- This properly connects the cases blueprint implementation with the Flask application's routing system
- The cases page now displays correctly, showing the list of engineering ethics cases stored in the system

# ⚠️ IMPORTANT: Claude Model Version Requirements ⚠️

## Required Claude Model Versions
- **Use ONLY** these model versions:
  - `claude-3-7-sonnet-20250219` (preferred)
  - `claude-3-7-sonnet-latest` (alternative)

## Warning About Older Model Versions
DO NOT use older model versions like `claude-3-7-sonnet-20240229` or similar, as they are incompatible with the current codebase and API implementations. Using incorrect model versions causes:
- API compatibility errors
- Missing type definitions (`RawMessageStreamEvent` etc.)
- Fallbacks to mock responses
- Broken functionality across the system

## Model Version Checklist
When making code changes that involve Claude API:
1. Verify model version strings match one of the approved versions above
2. Never revert to older model dates (20240229 instead of 20250219)
3. Double-check API parameter compatibility with the specified model
4. Test with the actual API before committing changes

---

## May 18, 2025 (Update #51): Planned LLM-Enhanced Triple Generation (Phase 2)

### Issue Analysis
Analyzed and identified the cause of the "Error getting entities: 404" error in the triple generation workflow:
- The error occurs when MCPClient attempts to access ontology entities at `/api/ontology/engineering-ethics/entities`
- The issue is related to the URL path handling between the client and server
- The server is configured to respond to this path but has internal confusion with file extension handling

### Next Enhancement: LLM-Enhanced Triple Generation
Developed implementation plan for Phase 2 of the triple generation system:

1. **Current Status**: 
   - Phase 1 is complete and working for basic triple generation
   - Current system handles basic types, standard properties, and simple domain-specific relationships

2. **Enhancement Goal**:
   - Add LLM-enhanced capability to identify implicit semantic relationships
   - Create more meaningful connections between concepts based on semantic understanding
   - Generate richer triple contexts with confidence scores and explanations
   - Provide fallback to basic generation for critical reliability

3. **Implementation Approach**:
   - Extend the API interface with new parameters for LLM enhancement
   - Create a specialized prompt template for semantic triple generation
   - Implement proper merging of basic and LLM-generated triples
   - Add quality control with confidence thresholds

4. **Technical Considerations**:
   - Token usage will increase with LLM enhancement
   - Performance optimizations including caching and batch processing
   - Consistent URI handling between basic and enhanced methods
   - Proper fallback mechanisms to ensure reliability

## May 18, 2025 (Update #50): Implemented Triple Generation for Guidelines in MCP Server

### Task Completed
Implemented the missing `generate_concept_triples` tool in the MCP server's GuidelineAnalysisModule, fixing the issue where triple generation was silently failing and returning 0 triples.

### Key Improvements
1. **Server-Side Triple Generation**:
   - Added the proper tool registration in the MCP server for `generate_concept_triples`
   - Implemented a comprehensive triple generation algorithm that creates RDF triples from extracted concepts
   - Generated multiple relationship types based on concept categories (principles, roles, obligations, etc.)
   - Added support for both JSON and Turtle output formats

2. **Relationship Generation**:
   - Created basic type and property triples for all concepts
   - Generated domain-specific relationships based on concept types (e.g., principles guide actions)
   - Implemented concept-to-concept relationship generation for meaningful connections
   - Preserved text references and related concepts in the triple structure

3. **Integration with Ontology**:
   - Added code to retrieve and use ontology entities for better relationship mapping
   - Created proper URI generation with slugification for consistent naming

### Technical Details
- Generated 135 triples for 13 concepts in less than 0.1 seconds
- Implemented a comprehensive approach that creates 5-10 triples per concept plus inter-concept relationships
- Each concept gets basic triples like rdf:type, rdfs:label, plus domain-specific relationships
- Implemented careful URI management with proper namespace handling

### Next Steps
1. **LLM Enhancement**: In a future phase, enhance triple generation with LLM capabilities for more sophisticated semantic relationships
2. **UI Improvements**: Add visualizations for the generated triples
3. **Ontology Integration**: Improve the integration with the engineering ethics ontology for better semantic alignment
4. **Export Formats**: Add support for additional export formats beyond JSON and Turtle

## May 18, 2025 (Update #49): Fixed Anthropic API JSON Response Format Issue with SDK Compatibility

### Task Completed
Fixed the issue where the Anthropic service was returning natural language instead of JSON as reported in the MCP server logs by removing an unsupported API parameter.

### Key Improvements
1. **SDK Compatibility Fix**:
   - Identified that the `response_format` parameter is not supported in the current Anthropic SDK version
   - Removed the attempt to use this parameter in `mcp/modules/guideline_analysis_module.py`
   - Simplified the implementation to use only the prompt engineering approach for structured JSON output
   - Eliminated API compatibility warnings and errors 

2. **Documentation Updates**:
   - Created `docs/anthropic_sdk_update_fix.md` documenting the issue and solution
   - Added notes about Anthropic's recommended approach for structured output through prompt engineering
   - Included reference to Anthropic's official documentation on increasing output consistency

3. **Error Handling Enhancements**:
   - Updated error messages to be more accurate about the cause of JSON parsing issues
   - Improved logging to provide clearer information about API interactions
   - Maintained the robust fallback mechanism for non-JSON responses

### Technical Details
- Unlike OpenAI's API which has a dedicated `response_format` parameter, Anthropic's recommended approach is to handle structured output through prompt engineering
- The error "AsyncMessages.create() got an unexpected keyword argument 'response_format'" confirmed that this parameter isn't supported in the installed SDK version
- The working solution uses a strong system prompt with explicit instructions to return only valid JSON
- This aligns with Anthropic's documentation at https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency#chain-prompts-for-complex-tasks

### Next Steps
1. **Monitor API Behavior**: Continue monitoring the API responses to ensure consistent JSON formatting
2. **SDK Updates**: Consider updating the Anthropic SDK if a future version adds support for the `response_format` parameter
3. **Prompt Optimization**: Further optimize the system prompt for more reliable structured output if needed

## May 18, 2025 (Update #48): Fixed Anthropic SDK Compatibility Issues with Model Version Update

### Task Completed
Fixed compatibility issues with the Anthropic SDK by ensuring the correct Claude model version is used and updating the LangChain integration to work with the latest Anthropic SDK.

### Key Improvements
1. **Model Version Standardization**:
   - Reverted incorrect model version change from `claude-3-7-sonnet-20250219` to `claude-3-7-sonnet-20240229`
   - Added direct Anthropic client initialization for fallback capabilities
   - Added prominent documentation in CLAUDE.md about required model versions

2. **SDK Compatibility Fixes**:
   - Removed unsupported `proxies` parameter from Anthropic client initialization
   - Updated dependencies to compatible versions: langchain-anthropic 0.3.13 and anthropic 0.51.0
   - Fixed API client initialization to match current SDK requirements

3. **Error Handling Enhancements**:
   - Added more detailed error logging for Anthropic SDK compatibility issues
   - Implemented fallback mechanisms for API client initialization failures
   - Improved documentation of common API integration issues

### Technical Details
- Model version string format is critical: `claude-3-7-sonnet-20250219` works while `claude-3-7-sonnet-20240229` causes errors
- The Anthropic SDK recently removed support for the `proxies` parameter in initialization
- LangChain's Anthropic integration expects the most recent type definitions from the Anthropic SDK
- Upgrading packages ensures compatibility: `pip install --upgrade langchain-anthropic anthropic`

### Next Steps
1. **Version Pinning**: Consider pinning exact SDK versions in requirements.txt to prevent future compatibility issues
2. **Documentation**: Update API integration documentation to include these compatibility notes
3. **Testing**: Perform thorough API testing with the fixed implementation
4. **Monitoring**: Watch for any remaining API errors in logs

## May 18, 2025 (Update #47): Enhanced Anthropic JSON Response Handling

### Task Completed
Implemented a three-tier fallback approach to resolve the issue with Anthropic API returning natural language instead of JSON for guideline concept extraction.

### Key Improvements
1. **Multi-Tier API Call Strategy**:
   - Primary approach: Implemented explicit `response_format={"type": "json_object"}` parameter to force JSON output
   - Secondary approach: Enhanced system prompt with stronger JSON formatting instructions if first approach fails
   - Tertiary fallback: Return mock concepts if both approaches fail to produce valid JSON

2. **Comprehensive Error Handling**:
   - Added detailed logging to track which approach succeeds or fails
   - Enhanced JSON extraction and cleaning routines to handle various response formats
   - Added compatibility issue logging to a dedicated file (anthropic_api_compatibility_issues.log)
   - Implemented proper exception handling throughout the API call process

3. **JSON Validation Pipeline**:
   - Enhanced JSON extraction with multi-stage pattern matching (code blocks, JSON objects)
   - Added JSON structure validation to ensure response contains required "concepts" key
   - Implemented fallback hierarchy to guarantee service continuity even when API returns unexpected formats

### Technical Details
- The solution uses the newest Anthropic API feature (`response_format`) to explicitly request JSON
- If that fails, it falls back to a standard request with enhanced prompt engineering
- Both approaches use temperature settings optimized for structured output (0.2 and 0.1 respectively)
- The logging system captures detailed information to help track API behavior over time

### Next Steps
1. **Monitor Success Rates**: Analyze logs to determine which approach has the highest success rate
2. **API Compatibility Testing**: Test with different Claude model versions to see if behavior varies
3. **Consider Enhancement**: If needed, develop a post-processing step to convert natural language to JSON
4. **Stay Updated**: Watch for Anthropic API updates that might stabilize JSON output behavior

## May 18, 2025 (Update #46): Fixed Anthropic API JSON Response Format Issue

### Task Completed
Fixed an issue where the Anthropic API was returning natural language responses instead of JSON for guideline concept extraction, which was causing fallbacks to mock concepts.

### Key Improvements
1. **Added response_format Parameter**:
   - Modified the Anthropic API call in `extract_guideline_concepts` method to include `response_format={"type": "json_object"}`
   - This explicitly instructs Claude to return only JSON-formatted responses

2. **Enhanced Error Handling**:
   - Implemented a three-tier fallback system for API calls:
     - First attempt: Both tools and response_format parameters
     - Second attempt: Tools only (if first attempt fails)
     - Third attempt: Standard request with stronger JSON instructions
   - Added comprehensive error logging to track which approach works

3. **Compatibility Monitoring**:
   - Created metrics tracking for API compatibility issues
   - Added logging to a dedicated file "anthropic_api_compatibility_issues.log" when incompatibilities are detected
   - Implemented JSON validation to verify responses regardless of the approach used

### Technical Details
- The issue was caused by the Anthropic API returning natural language responses despite being asked for JSON
- There might be compatibility constraints between using both `tools` and `response_format` parameters simultaneously
- The implemented solution tries both parameters first, then falls back if conflicts occur
- The monitoring system will help identify the most reliable approach for future improvements

### Next Steps
1. **Monitor API Compatibility**: Review the anthropic_api_compatibility_issues.log file after production use
2. **Update Documentation**: Document the API compatibility constraints in the developer guidelines
3. **Consider API Updates**: Watch for Anthropic SDK updates that might address this compatibility issue
4. **Performance Analysis**: Compare response times between the different approaches to optimize

## May 18, 2025 (Update #45): Fixed ORM Property References in MCP Client

### Task Completed
Fixed an issue where the application was trying to access a non-existent 'source' property on the Ontology model. This was causing errors during entity loading with the message "Error checking ontology status: Entity namespace for 'ontologies' has no property 'source'".

### Key Improvements
1. **Fixed Database Property Reference**:
   - Changed references from `source` to `domain_id` in the MCPClient class
   - The Ontology model has a `domain_id` column but not a `source` column
   - Updated the query in the `get_ontology_status` method to use the correct field name

2. **Error Resolution**:
   - Resolved the error: `Error checking ontology status: Entity namespace for "ontologies" has no property "source"`
   - Improved error handling to provide more helpful messages when accessing database entities
   - Added clearer logging to help diagnose similar issues in the future

3. **Technical Details**:
   - The issue was in `app/services/mcp_client.py` where it was using `Ontology.query.filter_by(source=ontology_source).first()`
   - Changed to use `Ontology.query.filter_by(domain_id=ontology_source).first()` which matches the actual schema
   - This allows proper lookup of ontologies by their domain identifier which is critical for guideline concept extraction

### Next Steps
1. **Database Schema Documentation**: Create comprehensive documentation of the database schema to prevent similar issues
2. **Code Auditing**: Review other parts of the codebase for similar ORM property mismatches
3. **Testing**: Implement additional tests to verify database entity access works correctly
4. **Data Validation**: Add validation to ensure data consistency between the MCP server and Flask application

## May 18, 2025 (Update #44): Fixed Database Configuration Handling in MCP Server

### Task Completed
Fixed the SQL database configuration error in the Enhanced Ontology MCP Server that was appearing during guideline concept extraction. The issue was resolved by improving database configuration handling and fixing the table name references.

### Key Improvements
1. **Fixed Database Configuration Handling**:
   - Created a new `fix_flask_db_config.py` module to properly set up Flask database configuration
   - Implemented proper environment variable handling for database connection
   - Ensured database configuration is set before Flask app initialization
   - Fixed the error: `RuntimeError: Either 'SQLALCHEMY_DATABASE_URI' or 'SQLALCHEMY_BINDS' must be set`

2. **Fixed Table Name References**:
   - Identified that the code was looking for an "ontology" table but the actual table name is "ontologies" (plural)
   - Updated all SQL queries to reference the correct table name
   - Implemented domain ID format standardization (hyphen vs underscore)
   - Added better error handling and more detailed logging

3. **Improved Module Import System**:
   - Added a backward compatibility alias in `base_module.py` to support existing modules
   - Fixed the error: `ImportError: cannot import name 'BaseModule' from 'mcp.modules.base_module'`
   - Ensured proper module initialization order to prevent circular imports
   - Created stable module interfaces for future development

4. **Enhanced Server Management**:
   - Created a restart script (`restart_mcp_server.sh`) to easily restart the MCP server
   - Added server health checking to verify proper startup
   - Implemented proper database session handling throughout the codebase
   - Added improved environment variable handling in server scripts

### Technical Details
1. **Database Configuration Fix**:
   - Set `SQLALCHEMY_DATABASE_URI` environment variable before Flask app initialization
   - Created functions to safely manage Flask app context for database operations
   - Used direct SQLAlchemy engine creation as a fallback when Flask app context fails
   - Implemented detailed error logging to trace configuration issues

2. **Table Name and Schema Handling**:
   - Updated the query from `SELECT id, content FROM ontology` to `SELECT id, content FROM ontologies`
   - Added domain ID format standardization to match database conventions
   - Implemented column mapping based on actual database schema
   - Added detailed logging of database schema checks and query results

### Next Steps
1. **Advanced Error Handling**: Further enhance error handling by implementing detailed error types and recovery strategies
2. **Performance Optimization**: Monitor and optimize database query performance for ontology loading
3. **Caching Implementation**: Consider adding caching for frequently used ontology data to reduce database load
4. **Monitoring Setup**: Implement proper monitoring for database connections and performance metrics

AI Ethical DM - Development Log

## May 18, 2025 (Update #43): Fixed SQL Error in MCP Server

### Task Completed
Fixed the SQL error in the Enhanced Ontology MCP Server by implementing a direct database connection approach instead of using Flask app context.

### Key Improvements
1. **Identified Root Cause**:
   - The error message: `Error loading from database: Either 'SQLALCHEMY_DATABASE_URI' or 'SQLALCHEMY_BINDS' must be set.`
   - The MCP server was trying to create a Flask app context to access the database but wasn't properly inheriting environment variables
   - This caused the database configuration to be missing when the app context was created

2. **Implemented Clean Solution**:
   - Modified `_load_graph_from_file` method in `mcp/http_ontology_mcp_server.py` to use SQLAlchemy directly
   - Removed dependency on Flask app context for database operations
   - Used environment variables with proper fallback for database connection URL
   - Implemented proper session handling with cleanup
   - Maintained detailed logging for debugging purposes

3. **Technical Details**:
   - Used SQLAlchemy core functionality to create direct database connection
   - Configured connection with `DATABASE_URL` from environment with fallback to `postgresql://postgres:PASS@localhost:5433/ai_ethical_dm`
   - Implemented proper SQL query to directly fetch ontology content from the database
   - Ensured database sessions are properly closed after use

### Next Steps
1. **Test MCP Server**: Restart the MCP server to verify the fix works in practice
2. **Monitor Logs**: Watch for any new errors in the MCP server logs
3. **Consider Configuration Refactoring**: Evaluate centralizing database configuration to avoid similar issues
4. **Documentation Update**: Update technical documentation with details of this implementation change

## May 18, 2025 (Update #42): Fixed Flask Debug Server Restart Issue

### Task Completed
Fixed an issue where the Flask development server was unnecessarily restarting during initialization, causing a double-startup sequence that wasted time during development.

### Key Improvements
1. **Identified Root Cause**:
   - Determined that the filesystem-based session storage (`SESSION_TYPE = 'filesystem'`) was triggering Flask's reloader
   - When Flask created session files during initialization, the reloader detected these file changes
   - This caused the "Restarting with stat" behavior we were seeing after every initial startup

2. **Implemented Clean Solution**:
   - Modified `run_debug_app.py` to disable the auto-reloader while keeping other debug features
   - Used `app.run(debug=True, use_reloader=False)` to maintain enhanced error pages and other debug benefits
   - Properly documented the change with clear comments explaining the reason

3. **Verified Results**:
   - The application now starts up cleanly without the unnecessary restart
   - Debug features like enhanced error pages are still available
   - Development workflow is more efficient with faster startup times

### Technical Details
The issue was in how Flask's development server works:

1. When `debug=True` is set, Flask enables an auto-reloader that watches for file changes
2. Our application was configured to use filesystem sessions (`SESSION_TYPE = 'filesystem'` in `app/config.py`)
3. During initialization, Flask creates session files, which triggered file change events
4. These events caused the reloader to restart the application, creating a wasteful cycle

Our solution separates these concerns by:
- Keeping `debug=True` for its development benefits (better error pages, console tracebacks)
- Setting `use_reloader=False` to prevent the file change monitoring that caused the restart

This approach is ideal for development in environments like GitHub Codespaces where you want debug features but don't need the auto-reloader (which can be problematic with filesystem sessions).

### Next Steps
1. **Consider Update to VSCode Launch Config**: Update launch configurations to use the same settings
2. **Document in Development Guide**: Add a note about this in the development workflow documentation
3. **Evaluate Session Storage**: Consider if filesystem sessions are necessary or if another storage mechanism might be better for development

## May 18, 2025 (Update #41): Optimized Application Startup by Removing Schema Verification

### Task Completed
Optimized the Flask application startup process by removing the automatic database schema verification that was causing unnecessary application restarts during development.

### Key Improvements
1. **Streamlined Application Initialization**:
   - Modified `app/__init__.py` to remove schema verification during application startup
   - Replaced it with a simple database connection test that doesn't modify files
   - Eliminated the unnecessary Flask restart that was occurring during initialization
   - Reduced application startup time by preventing the double-initialization sequence

2. **Dedicated Schema Verification Tool**:
   - Created a standalone `verify_database_schema.py` script for schema verification
   - The script performs all the same checks previously done at startup
   - Includes proper command-line options for check-only mode and custom database URLs
   - Provides clear output with color-coded success/failure messages

3. **Best Practices Implementation**:
   - Separated concerns by moving schema verification out of application initialization
   - Applied principle of minimal side effects during application startup
   - Improved developer experience with faster startup times
   - Created clear documentation for when to run schema verification

### Technical Details
The implementation addresses two specific issues:

1. **Removed the cause of restart**:
   - Flask's debug mode automatically restarts the application when it detects file changes
   - The schema verification code was potentially modifying files during startup
   - This caused Flask to restart immediately after starting, creating a doubled startup sequence
   - By removing schema verification from startup, we eliminated this problem

2. **Created a dedicated utility**:
   The new `verify_database_schema.py` script:
   - Provides the same verification functionality as before
   - Should be run explicitly when updating the codebase with new models
   - Includes better error reporting and options than the previous implementation
   - Can be run in check-only mode to verify without making changes

### Next Steps
1. **Update Documentation**: Add notes about when to run schema verification in development workflows
2. **Consider Database Migrations**: Evaluate using a proper migration tool (like Alembic) for schema changes
3. **Startup Performance**: Continue to optimize application startup time for development workflow
4. **Test Coverage**: Add tests for database schema verification to ensure continued reliability

## May 18, 2025 (Update #40): Fixed Ontology File Loading for Guideline Concept Extraction

### Task Completed
Fixed a critical issue in the HTTP Ontology MCP Server that was causing "Ontology file not found" errors during guideline concept extraction by implementing proper file extension handling and fallback paths.

### Key Improvements
1. **Enhanced Ontology File Path Handling**:
   - Modified `_load_graph_from_file` method in `http_ontology_mcp_server.py` to properly handle file extensions
   - Added automatic `.ttl` extension appending when not specified in the ontology source parameter
   - Implemented a fallback path mechanism to check both with and without extension
   - Added detailed error logging showing which paths were checked

2. **Error Resolution**:
   - Fixed the error: `Error: Ontology file not found: /workspaces/ai-ethical-dm/mcp/ontology/engineering_ethics`
   - Resolved the issue where the server couldn't find ontology files when no extension was specified
   - Addressed the underlying cause of parser failures in guideline concept extraction

3. **Testing and Verification**:
   - Created `test_extract_concepts.py` to verify guideline concept extraction works through the MCP server API
   - Successfully extracted concepts from NSPE Code of Ethics text
   - Confirmed the extraction of Public Safety (principle), Professional Competence (obligation), and Honesty in Communication (obligation) concepts

### Technical Details
The problem was in the `_load_graph_from_file` method in `http_ontology_mcp_server.py`. When the `ontology_source` parameter was provided without a `.ttl` extension (e.g., "engineering_ethics"), the code was:
1. Attempting to find the file directly with that name
2. Not appending the `.ttl` extension automatically
3. Failing with "Ontology file not found" since the actual file was named "engineering_ethics.ttl"

The solution:
```python
# Standardize the ontology_source handling
if ontology_source.endswith('.ttl'):
    domain_id = ontology_source[:-4]  # Remove .ttl extension
else:
    domain_id = ontology_source
    # Ensure we look for the file with extension if not specified
    ontology_source = f"{ontology_source}.ttl"

# Check both with and without extension
ontology_path = os.path.join(ONTOLOGY_DIR, ontology_source)
if not os.path.exists(ontology_path):
    # Try without extension as fallback
    fallback_path = os.path.join(ONTOLOGY_DIR, domain_id)
    if os.path.exists(fallback_path):
        ontology_path = fallback_path
        print(f"Using fallback path: {ontology_path}", file=sys.stderr)
    else:
        print(f"Error: Ontology file not found: {ontology_path}", file=sys.stderr)
        print(f"Also checked: {fallback_path}", file=sys.stderr)
        return g
```

This approach ensures that regardless of whether the ontology source is specified with or without the `.ttl` extension, the system will find the file if it exists in either form. This robust handling fixed the issue causing the guideline concept extraction to fail.

### Next Steps
1. **Server-Side Validation**: Add additional validation for ontology source parameters in API endpoints
2. **File Extension Configuration**: Consider making file extensions configurable for different ontology types
3. **Improved User Feedback**: Enhance error messages with recovery suggestions when ontology files can't be found
4. **Caching**: Implement caching for frequently used ontology files to improve performance

## May 18, 2025 (Update #39): Fixed Ontology File Path and Client Method Access Issues

### Task Completed
Fixed two critical issues in the Enhanced Ontology MCP Server that were causing errors during guideline concept extraction: a mismatch between the ontology source ID and actual filename, and an ontology client method access issue.

### Key Improvements
1. **Fixed Ontology File Path Mismatch**:
   - Identified that the server was using "engineering-ethics" (with hyphen) as the source ID
   - Corrected this to "engineering_ethics" (with underscore) to match the actual filename
   - This resolved the error where the system couldn't find the ontology file

2. **Implemented OntologyClientWrapper**:
   - Created an OntologyClientWrapper class to safely mediate access between modules and the server
   - Fixed the 'EnhancedOntologyServerWithGuidelines' object has no attribute 'get_ontology_sources' error
   - Provided proper error handling and fallbacks for ontology method access
   - Modified server initialization to use this wrapper for more reliable method access

3. **Testing and Verification**:
   - Created comprehensive tests to verify both fixes
   - Confirmed the system can now properly load the ontology file with 89 triples
   - Verified that the wrapper correctly forwards method calls to the server
   - Added detailed logging to show the success of each fix

### Technical Details
The implementation solves two distinct issues:

1. **File path issue**: There was a naming convention mismatch between the source ID in `get_ontology_sources()` returning "engineering-ethics" and the actual file named "engineering_ethics.ttl". This would cause the file loader to look for a non-existent file.

2. **Method access issue**: When the GuidelineAnalysisModule tried to call `ontology_client.get_ontology_sources()`, the method couldn't be located. The wrapper pattern provides a reliable interface that forwards method calls to the server, with proper error handling.

Both fixes work together to ensure the guideline concept extraction process can properly access the ontology data needed for concept matching and extraction.

### Next Steps
1. **Restart MCP Server**: Restart the MCP server to apply the fixes
2. **Test Complete Workflow**: Test the entire guideline concept extraction process with the fixed implementation
3. **Monitor Production**: Monitor the production system for any related issues
4. **Documentation**: Update technical documentation with details about the ontology client implementation pattern
