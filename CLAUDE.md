AI Ethical DM - Development Log

## May 15, 2025 (Update #3): Added Mock Responses and Fixed JSON Parsing for Guideline Concept Extraction

### Task Completed
Implemented a mock response system for guideline concept extraction to speed up development and testing, and fixed JSON parsing issues in the form submission process.

### Key Improvements
1. **Mock Response System**: Added a development mode that uses pre-loaded concepts instead of calling Claude API:
   - Created environment variable `USE_MOCK_GUIDELINE_RESPONSES` to toggle mock mode
   - Implemented loading of mock concept data from JSON files (`guideline_concepts.json` or `test_concepts_output.json`)
   - Added fallback to default mock concepts if no files are found
   - Integrated mock responses in the GuidelineAnalysisModule for faster development cycles

2. **Enhanced JSON Parsing**: Improved the form submission process to handle various JSON formatting issues:
   - Added robust JSON parsing with multiple fallback strategies
   - Fixed missing quotes around property names in malformed JSON
   - Added conversion from single quotes to double quotes
   - Implemented ast.literal_eval fallback for Python-style dictionaries
   - Added comprehensive error logging for JSON parsing failures

3. **Development Utilities**: Created a new debug script to make testing easier:
   - Added `debug_with_mock_guidelines.sh` script to launch both servers with mock mode enabled
   - Improved error handling and logging throughout the concept extraction process

### Technical Details
- Added `_load_mock_concepts()` method to GuidelineAnalysisModule to load sample data
- Modified `extract_guideline_concepts()` to use mock data when in development mode
- Enhanced JSON parsing in `save_extracted_concepts()` route with robust error recovery
- Added a shell script to easily enable mock responses for testing

### Next Steps
1. Complete the implementation of native Claude tool use as previously documented
2. Improve the UI for reviewing and managing saved concepts
3. Enhance the concept matching algorithm to better integrate with the ontology

## May 15, 2025 (Update #2): Improved Guideline Concept Saving to Ontology Database

### Task Completed
Enhanced the guidelines concept saving flow to ensure extracted concepts are properly saved to the ontology database. Improved the triple generation process and entity matching with the ontology.

### Key Improvements
1. **Improved Triple Generation**: Enhanced the triple generation process in the `GuidelineAnalysisService`:
   - Added support for related concepts with proper RDF relationships
   - Improved error handling for JSON-RPC calls to the MCP server
   - Extended timeout periods for complex concept processing
   - Added ontology relationship enhancement to connect guideline concepts with existing ontology entities
   - Added additional triple types (label, category) for better semantic representation

2. **Enhanced Database Saving**: Optimized the process of saving triples to the database:
   - Implemented bulk save operations for better performance
   - Added improved handling of literal values versus URI references
   - Enhanced metadata with timestamps and confidence scores
   - Added better logging throughout the triple generation and saving process

3. **Better Error Handling**: Added robust error handling and reporting:
   - Added detailed error tracking with stack traces
   - Enhanced error handling for MCP server timeouts and connection issues
   - Added better session state management for analysis results

### Technical Details
- Enhanced `generate_triples()` method in `GuidelineAnalysisService` to better integrate with the MCP server
- Added new `_enhance_triples_with_ontology_relationships()` helper method to connect concepts with the ontology
- Improved `save_guideline_concepts()` route to better handle triple data and perform bulk database operations
- Added URI/literal detection to properly store object values in the correct format

### Next Steps
1. Complete the implementation of native Claude tool use as previously documented
2. Add UI improvements for reviewing and managing saved concepts
3. Implement a bulk concept extraction feature for processing multiple guidelines simultaneously

## May 15, 2025: Claude Tool Use & Guidelines Debugging Implementation

### Task Completed
Analyzed the guidelines concept extraction flow and implemented debugging tools. Additionally, identified the need for native tool use with Claude for improved ontology integration.

### Key Findings
1. **Current Integration Method**: The system currently integrates ontology data with Claude through prompt engineering:
   - Ontology entities are retrieved from the specified source
   - These entities are incorporated into the prompt sent to Claude
   - Claude cannot actively query the ontology during its reasoning process
   - All interactions follow a basic "user message → assistant response" pattern

2. **Debugging Flow**: Identified and documented how guideline extraction requests flow through the system:
   - Web UI → Flask route → GuidelineAnalysisService → MCP server JSON-RPC → GuidelineAnalysisModule → Claude API

3. **VSCode Breakpoint Issues**: Discovered that VSCode breakpoints aren't reliably triggered in the MCP server:
   - Likely due to asyncio event loop interactions with the debugger
   - Enhanced logging has been implemented as a workaround
   - Created utilities for tracking execution flow without relying on breakpoints

### Changes Made
1. Created comprehensive debugging tools:
   - `mcp/enhanced_debug_logging.py` - Logging framework for tracking execution flow
   - `debug_patch_server.sh` - Script to patch MCP server with enhanced logging
   - `DEBUG_BREAKPOINTS.md` - Documentation explaining breakpoint issues and solutions
   - Updated `DEBUG_INSTRUCTIONS.md` with improved workflow

2. Updated documentation:
   - Added native Claude tool use as a critical next step in `docs/guidelines_implementation_next_steps.md`
   - Documented current Claude integration approach in `docs/guidelines_implementation_progress.md`
   - Added workflow details for debugging guidelines code

### Future Implementation: Native Tool Use
Added a priority item to implement native Claude tool use:
- Define JSON schema for ontology query operations 
- Create structured tool definitions for dynamic entity retrieval
- Allow Claude to interactively query the ontology during reasoning
- Enable self-validation of extracted concepts against ontology constraints

### How to Debug Guidelines Flow
1. Use the enhanced debug logging tools to trace execution:
   - Run `./debug_patch_server.sh` to add debug logging to the server
   - Set `MCP_DEBUG=true` when running the MCP server
   - Watch console output for detailed execution logs

2. Follow the complete concept extraction flow through:
   - UI → Flask → GuidelineAnalysisService → MCP JSON-RPC → GuidelineAnalysisModule → Claude

### Technical Reference
The execution flow has been traced and documented to show exactly how:
1. Guideline content is sent via JSON-RPC to the MCP server
2. Ontology entities are retrieved and incorporated into Claude's prompt
3. Claude processes the guidelines to extract concepts
4. Response is parsed and returned through the call chain

This analysis will inform the implementation of native tool use that will allow Claude to actively query the ontology during concept extraction.

## May 14, 2025: VSCode Debugging Environment Fix

### Task Completed
Fixed a Python module import issue that was preventing the VSCode debugger from properly running the application.

### Problem
When running the application in VSCode debug mode, there was a module not found error for the `markdown` package. This occurred because the VSCode debugger was using the conda Python environment (`/opt/conda/bin/python`), but the application's dependencies were installed in the user's site-packages directory (`/home/codespace/.local/lib/python3.12/site-packages`).

### Changes Made
1. Installed the `markdown` package using conda to make it available in the conda environment
2. Updated the VSCode debug configuration in `.vscode/launch.json` to add the user's site-packages to the Python path:
   ```json
   "env": {
     "PYTHONPATH": "/home/codespace/.local/lib/python3.12/site-packages:${PYTHONPATH}",
     "USE_CONDA": "false"
   }
   ```
3. Created a script `scripts/ensure_python_path.sh` that properly sets up the Python environment for debugging
4. Modified `scripts/setup
