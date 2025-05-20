# ProEthica Project Development Log

## 2025-05-20: Implemented "Save and View Case" Button in Extraction Template

Added the previously documented "Save and View Case" button to the case extraction template to allow direct saving and viewing of cases without going through the edit step:

**Implementation**:
1. Added a new "Save and View Case" button to the extraction template that:
   - Submits directly to the `/cases/save-and-view` route
   - Passes all extracted content sections as hidden form fields
   - Includes structured data for questions and conclusions
   - Uses a green button to distinguish it from the regular save button

2. Positioned the new button next to the original "Save as Case" button, maintaining both workflows:
   - "Save and View Case" (green) - Bypasses the edit step and displays the case with the same formatting
   - "Save as Case" (blue) - Original workflow that goes to the edit form first

**How It Works**:
- When a user clicks "Save and View Case", the form submits all extracted content to the `save_and_view_case` route
- This route generates HTML that matches the extraction page format with the same cards and styling
- It also sets a special `display_format: 'extraction_style'` metadata flag
- The case_detail template checks for this flag and renders the case in the same style as the extraction page
- No further processing or editing step is required

**Benefits**:
- Cases are now displayed exactly as they appear during extraction, with identical formatting and Bootstrap styling
- The card-based layout with proper headers is preserved in the saved view
- Numbered lists in conclusions are properly preserved with ordered list HTML
- Users can save and view cases in one click without going through an edit step
- The original "Save as Case" option is still available for users who need the edit step

## 2025-05-20: Case Extraction Pipeline Enhancement (Updated)

Implemented a comprehensive enhancement to the case extraction pipeline to properly preserve formatting and layout in NSPE cases and streamline the user workflow:

**Issue**: When a user processed a URL to extract NSPE case content:
1. The content was displayed correctly on the extraction page after clicking "Process as NSPE Case"
2. When clicking "Save as Case" and redirected to the edit page, proper formatting (especially numbered lists in conclusions) was lost
3. Users had to go through an unnecessary edit step even when no edits were needed
4. After saving with the initial "Save and View" implementation, the content display format was still different from how it appeared on the extraction page

**Analysis**:
- NSPE case conclusions often contain numbered lists that should be preserved in the saved document
- The existing pipeline reprocessed the content during the save operation, causing format loss
- The nl2br Jinja filter in the template was converting newlines to <br> tags, breaking HTML formatting
- The workflow required clicking through an edit page even when no edits were needed
- The first version of the solution preserved content but not the card-based Bootstrap layout/styling

**Solution**:
1. Added individual conclusion item extraction in NSPECaseExtractionStep:
   ```python
   def _extract_individual_conclusions(self, html):
       """
       Extract individual conclusion items from HTML content.
       Handles ordered lists, unordered lists, and text with numbered items.
       """
       # Implementation extracts list items into a structured array
   ```

2. Added a new "Save and View Case" button to `case_extracted_content.html`:
   ```html
   <form method="post" action="{{ url_for('cases.save_and_view_case') }}" class="me-2">
       <input type="hidden" name="url" value="{{ result.url }}">
       <input type="hidden" name="title" value="{{ result.title }}">
       <!-- Other metadata fields -->
       <input type="hidden" name="world_id" value="1">

       <!-- Include all extracted content sections -->
       <input type="hidden" name="extracted_content" value="true">
       <input type="hidden" name="facts" value="{{ result.sections.facts|e }}">
       <!-- Other content sections -->
       
       <!-- Structured list data as JSON -->
       {% if result.questions_list %}
       <input type="hidden" name="questions_list" value="{{ result.questions_list|tojson|e }}">
       {% endif %}
       {% if result.conclusion_items %}
       <input type="hidden" name="conclusion_items" value="{{ result.conclusion_items|tojson|e }}">
       {% endif %}

       <button type="submit" class="btn btn-primary">Save and View Case</button>
   </form>
   ```

3. Enhanced the `save_and_view_case` route in `cases.py` to generate HTML that exactly matches the extraction page format:
   ```python
   @cases_bp.route('/save-and-view', methods=['POST'])
   def save_and_view_case():
       """Save case with extracted content and view it directly (no edit step)."""
       # Code to get form data...
       
       # Generate HTML content that exactly matches the extraction page display format
       # with the same cards and layout as case_extracted_content.html
       html_content = ""
       
       # Facts section
       if facts:
           html_content += f"""
   <div class="row mb-4">
       <div class="col-12">
           <div class="card">
               <div class="card-header bg-light">
                   <h5 class="mb-0">Facts</h5>
               </div>
               <div class="card-body">
                   <p class="mb-0">{facts}</p>
               </div>
           </div>
       </div>
   </div>
   """
       
       # Questions section with similar card structure
       # References section with similar card structure
       # Discussion section with similar card structure
       # Conclusion section with similar card structure
       
       # Store display format flag in metadata
       metadata = {
           # Other metadata fields...
           'display_format': 'extraction_style' # Flag to indicate special display format
       }
   ```

4. Modified the case detail template to check for the display format flag and render accordingly:
   ```html
   {% if case.doc_metadata and case.doc_metadata.display_format == 'extraction_style' %}
       {{ case.description|safe }}
   {% else %}
       <h4>Description</h4>
       <div class="mb-4">
           <div id="description-container">
               <div id="description-content">
                   {{ case.description|safe }}
               </div>
           </div>
       </div>
   {% endif %}
   ```

5. Added `world_id` hidden field with default value of 1 (Engineering Ethics) to both forms:
   ```html
   <input type="hidden" name="world_id" value="1">
   ```

**Benefits**:
- Cases are now displayed exactly as they appear during extraction, with identical formatting and Bootstrap styling
- The card-based layout with proper headers is preserved in the saved view
- Numbered lists in conclusions are properly preserved with ordered list HTML
- Users can save and view cases in one click without going through an edit step
- The original "Save as Case" option is still available for users who need the edit step
- Improved workflow reduces redundant reprocessing of URLs

**Technical Implementation Details**:
- Uses hidden form fields to preserve pre-extracted content without reprocessing
- Generates HTML with matching Bootstrap card components and styling to ensure visual consistency
- Special metadata flag enables conditional rendering in the case detail template
- Handles both structured list data (as JSON) and raw HTML content
- Maintains backward compatibility with existing code paths
- Implements safe error handling for JSON parsing
- Properly sets document processing status to completed

## 2025-05-20: Fixed "Edit Triples" Button Error in Case Edit Form

Fixed a routing error in the case edit form that occurred after successfully saving a case:

**Issue**: After successfully saving a case from the URL processor, the application would redirect to `/cases/<id>/edit` but then display an error:
```
BuildError: Could not build url for endpoint 'cases_triple.edit_triples' with values ['id']. 
Did you mean 'cases.edit_case' instead?
```

**Analysis**:
- The error occurred in the `edit_case_details.html` template
- The template tried to generate a URL for the `cases_triple.edit_triples` endpoint
- This endpoint exists but expects a different URL pattern than what the template was providing
- The "Edit Triples" button was causing the routing error even though the case was saving correctly

**Solution**:
- Commented out the problematic "Edit Triples" button in the template:
```html
<!-- Edit Triples button removed to fix routing error -->
<!-- <a href="{{ url_for('cases_triple.edit_triples', id=document.id) }}" class="btn btn-primary">Edit Triples</a> -->
```
- Added a comment explaining why the button was removed
- Preserved all other functionality of the edit case form

**Benefits**:
- Eliminates the routing error when editing cases
- Allows users to view and edit case details without errors
- Maintains core functionality while removing a non-critical feature
- No changes to route functions or backend code required

**Next Steps**:
- If the "Edit Triples" functionality is needed, proper routes should be implemented in the `cases_triple` blueprint
- URL patterns between templates and routes should be standardized

## 2025-05-20: Fixed BuildError for Cases Triple Edit Routes

Fixed issues where accessing case triple editing URLs was causing BuildErrors:

**Issue**: When trying to access triple editing URLs, the application would display errors like:
```
werkzeug.routing.exceptions.BuildError: Could not build url for endpoint 'cases_triple.edit_triples' with values ['id']. Did you mean 'cases.edit_case' instead?
```

**Analysis**:
- The `cases_triple_bp` blueprint exists in `app/routes/cases_triple.py` but isn't registered in `app/__init__.py`
- Multiple issues were found:
  1. Some templates were trying to reference a Flask route using `url_for('cases_triple.edit_triples')`
  2. The case detail template was using a hardcoded URL path `/cases/triple/{{ case.document_id }}/edit`
  3. The URL pattern for triple editing was inconsistent across the application

**Solution**:
1. Added dummy route handlers in `app/routes/cases.py` to handle problematic URL patterns:
   ```python
   @cases_bp.route('/triple/<int:id>/edit', methods=['GET', 'POST'])
   def dummy_edit_triples(id):
       """Temporary route to fix BuildError for cases_triple.edit_triples."""
       # Redirect to the regular case edit form
       return redirect(url_for('cases.edit_case_form', id=id))
       
   @cases_bp.route('/<int:id>/triple/edit', methods=['GET', 'POST'])
   def dummy_edit_triples_alt(id):
       """Alternative temporary route to fix BuildError for cases_triple.edit_triples."""
       # Redirect to the regular case edit form
       return redirect(url_for('cases.edit_case_form', id=id))
   ```

2. Updated hardcoded URL in `case_detail.html` to use the Flask route helper:
   ```html
   <!-- Changed from hardcoded path to url_for function -->
   <a href="{{ url_for('cases.dummy_edit_triples', id=case.document_id) }}" class="btn btn-primary me-2">
       <i class="bi bi-diagram-3"></i> Edit Triples
   </a>
   ```

**Benefits**:
- Completely resolves the BuildError exceptions
- Provides graceful fallback to the standard edit case form
- Maintains user experience by redirecting to a working page
- Ensures consistency in URL generation across templates
- Temporary solution that can easily be replaced with a proper implementation later

**Next Steps**:
- Consider properly registering the `cases_triple_bp` in `app/__init__.py` for a more permanent solution
- Standardize URL patterns for triple editing functionality
- Fully implement triple editing functionality if it's a required feature

## 2025-05-20: Fixed Additional Login Manager Error in CaseUrlProcessor

Fixed another occurrence of `AttributeError: 'Flask' object has no attribute 'login_manager'` in the case URL processor:

**Issue**: After fixing the login manager error in `cases.py`, the error reappeared in a different location. When creating a case from URL, the app would crash with:
```
File "/workspaces/ai-ethical-dm/app/services/case_url_processor/case_processor.py", line 72, in process_url
  if user_id is None and current_user and hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
AttributeError: 'Flask' object has no attribute 'login_manager'
```

**Analysis**:
- The `process_url()` method in `app/services/case_url_processor/case_processor.py` also used `current_user.id` 
- This method experienced the same error when Flask-Login wasn't properly initialized
- The fix needed to be applied to this file as well to ensure all user ID access was safely handled

**Solution**:
Applied the same try-except pattern to safely handle Flask-Login access:
```python
# Safe way to get user_id from current_user if not provided
if user_id is None:
    try:
        if current_user and hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            user_id = current_user.id
    except Exception:
        # If there's any error accessing current_user, just use None
        pass
```

**Benefits**:
- Complete fix for Flask-Login related errors across the codebase
- Ensures the case URL processor works properly without authentication
- Maintains existing functionality when authentication is available

## 2025-05-20: Fixed Case Save Functionality in Case Processing Pipeline

Fixed an issue where the "Save as Case" button in the case extraction page would fail with "World selection is required" error:

**Issue**: When clicking "Save as Case" on the case extraction page, users would get redirected with the error "World selection is required", preventing successful case creation.

**Analysis**:
- The form in `case_extracted_content.html` was missing the required `world_id` input field
- The `create_from_url` route in `app/routes/cases.py` requires a `world_id` parameter
- Without a world ID, the validation would fail with "World selection is required"
- Engineering Ethics (world_id=1) should be the default for NSPE cases

**Solution**:
- Added a hidden input field for `world_id` with a default value of 1 (Engineering Ethics world) to the form:
  ```html
  <input type="hidden" name="world_id" value="1">
  ```
- This ensures that case saving works without requiring users to select a world
- The change is minimal and maintains the existing functionality

**Additional Context**:
- World ID 1 corresponds to the Engineering Ethics world in the system
- This is the most appropriate default for NSPE case studies
- No changes to the backend were needed since it was already checking for the parameter

## 2025-05-20: Fixed Login Manager Error in Case Processing

Fixed an issue where the "Save as Case" functionality on case processing page was failing with the error `AttributeError: 'Flask' object has no attribute 'login_manager'`:

**Issue**: When using the "Save as Case" button in the case extraction route (`/cases/process/url`), the app would crash with the error message `AttributeError: 'Flask' object has no attribute 'login_manager'`.

**Analysis**:
- The `create_from_url()` function in `app/routes/cases.py` was using `current_user.id` to get the current user ID
- When running the app without a login manager configured, this would cause an error
- The issue was similar to previous login requirement issues that were fixed by removing `@login_required` decorators

**Solution**:
1. Removed the import of `login_required` from `flask_login` (even though it wasn't directly used in this function)
2. Modified the user ID extraction in `create_from_url()` to safely handle cases where Flask-Login isn't initialized:
   ```python
   # Safe way to get user_id without relying on Flask-Login being initialized
   user_id = None
   try:
       if current_user and hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
           user_id = current_user.id
   except Exception:
       # If there's any error accessing current_user, just use None
       pass
   ```

3. Kept the original functionality when Flask-Login is properly initialized
4. Made the function resilient to errors when running without authentication

**Benefits**:
- The "Save as Case" functionality now works without requiring authentication
- The change is backward compatible with authenticated sessions
- No other code changes were required
- The fix is resilient and won't break if the authentication system changes

## 2025-05-20: Enhanced NSPE Case Conclusion Handling

Improved the case processing pipeline to handle numbered conclusion items separately:

**Issue**: When processing NSPE cases, the conclusion section sometimes contains multiple numbered items, but they were being treated as a single block. This differs from how questions are handled, where individual questions are extracted and presented separately.

**Analysis**:
- The NSPECaseExtractionStep class had functionality to extract individual questions from the question section but lacked similar functionality for conclusions
- The template was displaying the conclusion as a single block, regardless of whether it contained multiple items
- This inconsistency made structured data extraction less effective for conclusions

**Solution**:
1. Enhanced the `NSPECaseExtractionStep` class with a new method to extract individual conclusion items:
   ```python
   def _extract_individual_conclusions(self, html):
       """
       Extract individual conclusion items from HTML content.
       Handles ordered lists, unordered lists, and text with numbered items.
       """
   ```

2. Modified the `extract_conclusion_section` method to return both the HTML content and a list of individual items:
   ```python
   def extract_conclusion_section(self, soup, base_url=None):
       """
       Extract conclusion section with special handling.
       Returns both the raw HTML and a list of individual conclusion items if available.
       """
   ```

3. Updated the `process` method to include the extracted conclusion items in the result dictionary

4. Modified the template (`case_extracted_content.html`) to:
   - Check if individual conclusion items exist
   - Display them as an ordered list when present
   - Fall back to the full HTML block when no structured items are detected
   - Dynamically change the heading from "Conclusion" to "Conclusions" when multiple items exist

**Benefits**:
- More structured extraction of conclusion data
- Consistent handling of both questions and conclusions
- Better presentation in the UI
- Improved data structure for downstream processing and analysis
- Maintains backward compatibility with existing code

## 2025-05-20: MCP Server Environment Variables Fix

Fixed an issue with environment variables not being passed to the MCP server:

**Issue**: When accessing the codespace from a different computer, the guideline concept extraction process was failing with the error "LLM client not available" despite the API keys being properly set in the .env file.

**Analysis**:
- The Flask app was correctly loading environment variables from .env
- The MCP server logs showed "ANTHROPIC_API_KEY not found in environment" warnings
- The issue was in how VS Code's tasks.json launches the MCP server through preLaunch task
- Child processes started through tasks.json don't automatically inherit environment variables from .env

**Solution**:
1. Created a helper shell script (`start_mcp_server_with_env.sh`) to properly source the .env file:
   ```bash
   #!/bin/bash
   # Load environment variables from .env file
   if [ -f .env ]; then
     export $(grep -v '^#' .env | xargs)
     echo "Loaded environment variables from .env file"
   fi
   
   # Start the MCP server
   python mcp/run_enhanced_mcp_server_with_guidelines.py
   ```

2. Updated `.vscode/tasks.json` to use this script:
   ```json
   {
       "label": "Start MCP Server with Live LLM",
       "type": "shell",
       "command": "./start_mcp_server_with_env.sh",
       "args": [],
   }
   ```

3. Created full documentation in `docs/anthropic_sdk_fix_2025_05_20.md`

4. Created a database backup (`ai_ethical_dm_backup_20250520_005033.dump`) as a precaution

**Prevention**:
For future development, ensure that:
- Use the helper script when starting the MCP server manually
- Environment variables are explicitly passed to child processes
- VSCode launch and task configurations are tested when accessing from different computers

## 2025-05-19: Python Environment Package Resolution Fix

Fixed an issue with Python module imports when accessing the codespace from a different system:

**Issue**: When accessing the codespace from a different system, the application was experiencing module import errors - first `ModuleNotFoundError: No module named 'langchain_core'` and then `ModuleNotFoundError: No module named 'langchain_anthropic'` despite these packages being included in requirements.txt.

**Analysis**: 
- The ProEthica application's Python dependencies are installed in the user site-packages directory (`/home/codespace/.local/lib/python3.12/site-packages`)
- When accessing the codespace from a different system, VSCode's debugger was using the conda Python environment (`/opt/conda/bin/python`)
- While some packages like langchain-core and langchain-anthropic were installed in the conda environment, they weren't installed in the user Python environment

**Solution**:
1. Manually installed the missing packages in the user Python environment:
   ```bash
   pip install --user langchain-core langchain-anthropic
   ```
2. Created a shell script (`fix_dependencies.sh`) to fix similar issues in the future:
   ```bash
   # Set Python to ignore the conda environment
   export USE_CONDA="false"
   
   # Add user site-packages to PYTHONPATH
   export PYTHONPATH="/home/codespace/.local/lib/python3.12/site-packages:$PYTHONPATH"
   
   # Force reinstall packages to user site-packages
   pip install --user --force-reinstall <package-name>
   ```

**Prevention**:
For future development, make sure to:
- Use the VSCode debugging configurations in launch.json which correctly set up the Python path
- Run the `scripts/ensure_python_path.sh` script before debugging
- For any new import errors, install the package directly to the user site-packages:
  ```bash
  pip install --user <package-name>
  ```
- If necessary, force reinstall packages to ensure they're in the correct location

## 2025-05-19: Ontology Enhancements

Updated the proethica-intermediate.ttl ontology with the following:

1. Enhanced temporal modeling aligned with Basic Formal Ontology (BFO):
   - Properly aligned temporal classes with BFO temporal region classes (BFO_0000038, BFO_0000148)
   - Improved temporal relation properties with appropriate domain and range constraints
   - Added temporal granularity concepts with proper BFO subclassing

2. Added decision timeline concepts:
   - Decision timeline classes for representing sequences of decisions and consequences
   - Alternative timeline classes for modeling hypothetical decision scenarios
   - Relations for connecting decisions to their temporal contexts and consequences

3. Enhanced ethical context modeling:
   - Added EthicalContext class with proper BFO alignment
   - Added properties to represent ethical weights and relationships
   - Created ethical agent concepts to represent decision makers

All ontology updates are properly aligned with BFO, using appropriate parent classes:
- Temporal entities are subclasses of BFO temporal region classes
- Material entities are properly aligned with BFO independent continuant hierarchy
- Properties have appropriate domain and range restrictions aligned with BFO types

The enhanced ontology provides improved representation capabilities for:
- Temporal aspects of ethical decision making
- Hypothetical reasoning about alternative decisions
- Contextual factors in ethical judgments

Next steps:
1. Test the enhanced ontology with existing ProEthica case data
2. Integrate with the temporal context service enhancements
3. Update the entity triple service to leverage new ontology concepts
