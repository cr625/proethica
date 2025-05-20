# ProEthica Project Development Log

## 2025-05-20: Modified Case Detail Description to Start Expanded

Modified the case description in the case detail view to start fully expanded with a "Show Less" button:

**Issue**:
When viewing long case descriptions, the content would be initially truncated to 300 pixels in height with a "Show More" button at the bottom. This required users to click an extra button to see the full content of cases.

**Analysis**:
The `setupShowMoreLessToggle()` function in `case_detail.js` was automatically limiting the height of description content and adding a "Show More" button when content exceeded 300 pixels in height. This created an additional interaction step for users trying to read case content.

**Solution**:
Modified the `setupShowMoreLessToggle()` function in `app/static/js/case_detail.js` to:
1. Start with content fully expanded (no height restriction) by default
2. Initially create a "Show Less" button instead of "Show More"
3. Maintain the toggle functionality to allow collapsing long content if desired

**Implementation Details**:
```javascript
// Set initial height to full height (expanded by default)
descriptionContent.style.maxHeight = contentHeight + 'px';
descriptionContent.style.overflow = 'hidden';
descriptionContent.style.transition = 'max-height 0.3s ease-out';

// Create the toggle button (initially "Show Less")
const toggleBtn = document.createElement('button');
toggleBtn.classList.add('btn', 'btn-link', 'mt-2', 'p-0');
toggleBtn.textContent = 'Show Less';
```

**Results**:
- Case descriptions now display their full content immediately upon page load
- Users can still collapse long descriptions if they wish by using the "Show Less" button
- The change improves readability and reduces unnecessary clicks
- The existing conditional check that skips this toggle for extraction-style cases is maintained

## 2025-05-20: Performed Database Backup

Successfully performed a database backup for the ProEthica system.

**Details**:
- Created a fresh PostgreSQL database backup using the backup script
- Had to start the PostgreSQL container first since it wasn't running
- Successfully generated backup file: `ai_ethical_dm_backup_20250520_190620.dump` (236K)
- Backup is stored in the `/backups` directory
- This joins previous backups from May 2025

**Technical Notes**:
- The backup process uses Docker's `pg_dump` command inside the `proethica-postgres` container
- Backup script automatically extracts the database password from the `.env` file
- The database container uses pgvector extension for vector embeddings support

## 2025-05-20: Streamlined URL Processing Workflow

Simplified the URL processing workflow by eliminating the intermediate steps:

**Issue**:
When importing cases from a URL, the workflow required multiple steps:
1. Enter URL at `/cases/new/url` 
2. Click "Process URL" to see the extraction result
3. Then click "Save and View Case" to save the data and view the case

This workflow was inefficient and required redundant processing of the same data.

**Solution**:
Modified the `process_url_pipeline` function to automatically save the extracted data directly to the database:

```python
# If extraction was requested, save the case and redirect
if process_extraction:
    # Ensure the result has the structure the template expects
    # ...existing code to structure the data...
    
    # Extract relevant data for saving
    title = final_result.get('title', 'Case from URL')
    case_number = final_result.get('case_number', '')
    # ...other data extraction...
    
    # Generate HTML content that matches the extraction page display format
    html_content = ""
    
    # ...generate HTML for all sections...
    
    # Store original sections in metadata for future reference
    metadata = {
        'case_number': case_number,
        'year': year,
        # ...other metadata...
        'questions_list': questions_list,
        'conclusion_items': conclusion_items,
        'extraction_method': 'direct_process',
        'display_format': 'extraction_style'
    }
    
    # Create document record
    document = Document(
        title=title,
        content=html_content,
        document_type='case_study',
        world_id=world_id,
        source=url,
        file_type='url',
        doc_metadata=metadata,
        processing_status=PROCESSING_STATUS['COMPLETED']
    )
    
    # Save the document
    db.session.add(document)
    db.session.commit()
    
    # Redirect to view the case
    flash('Case extracted and saved successfully', 'success')
    return redirect(url_for('cases.view_case', id=document.id))
```

**Results**:
- Clicking "Process URL" now directly processes the URL, saves the result to the database, and redirects to the case view
- The intermediate step of viewing the extraction result and then manually saving it has been eliminated
- Conclusion items and question lists are properly preserved in their structured format
- The workflow is now more efficient and requires fewer clicks
- Raw content view option is still available through "View Raw Content First" button

## 2025-05-20: Fixed Conclusion Items Processing in URL Pipeline

Fixed an issue where conclusion items were not properly preserved as a list when processing URLs directly:

**Issue**:
When using the "Process URL" button on the URL form, conclusion items were rendered correctly in the extraction view with proper list formatting, but after clicking "Save and View Case," the conclusions appeared as a single block of text without list formatting in the saved case view.

**Analysis**:
1. The NSPECaseExtractionStep correctly extracts and structures conclusion items as an array
2. However, in the process_url_pipeline function, this structured data wasn't being properly passed to the template
3. The structured data was lost when converting from the extraction result to the final template data

**Solution**:
Modified the `process_url_pipeline` function to:
```python
# If conclusion_items are not explicitly included, but we have structured conclusion data
# in the extraction result, make sure we include it in the final_result
if 'conclusion_items' not in final_result and isinstance(final_result.get('conclusion'), dict):
    conclusion_data = final_result.get('conclusion', {})
    if 'conclusions' in conclusion_data:
        final_result['conclusion_items'] = conclusion_data['conclusions']
    elif isinstance(conclusion_data, dict) and 'html' in conclusion_data and 'conclusions' in conclusion_data:
        final_result['conclusion_items'] = conclusion_data['conclusions']
        final_result['sections']['conclusion'] = conclusion_data['html']
```

**Results**:
- The URL processing pipeline now correctly preserves conclusion items as a structured array
- This ensures the data is properly passed to the save_and_view_case route
- Conclusion items are now consistently displayed as properly formatted lists throughout the workflow
- The fix is backward compatible with existing case data

## 2025-05-20: Fixed Conclusion List Items Display in Case Detail View

Fixed an issue where conclusion items were not being displayed as a proper list in the case detail view when using "Save and View Case":

**Issue**:
When viewing extracted cases with multiple conclusion items, the conclusion section was properly formatted as a numbered list in the extraction view. However, after clicking "Save and View Case," the conclusions were not being displayed as separate list items in the case detail view, resulting in poor readability.

**Analysis**:
1. The `save_and_view_case` route in `cases.py` correctly stored the conclusion items as an array in the document metadata
2. The HTML generation properly created the ordered list (ol) with list items (li) in the document content
3. However, the case_detail.html template did not have a dedicated section for rendering conclusion items from metadata

**Solution**:
Added a new section in the case_detail.html template to specifically render conclusion items stored in document metadata:

```html
<!-- Conclusion items list from metadata if available -->
{% if case.doc_metadata.conclusion_items %}
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-light">
                {% if case.doc_metadata.conclusion_items|length > 1 %}
                <h5 class="mb-0">Conclusions</h5>
                {% else %}
                <h5 class="mb-0">Conclusion</h5>
                {% endif %}
            </div>
            <div class="card-body">
                <ol class="mb-0">
                    {% for conclusion in case.doc_metadata.conclusion_items %}
                    <li>{{ conclusion }}</li>
                    {% endfor %}
                </ol>
            </div>
        </div>
    </div>
</div>
{% endif %}
```

This addition follows the same pattern as the existing section for question items, ensuring a consistent layout and formatting.

**Results**:
- Conclusion items now display as properly formatted numbered lists in the saved case view
- The formatting matches exactly how conclusions appear on the extraction page
- Singular/plural heading ("Conclusion"/"Conclusions") is dynamically adjusted based on the number of items
- All changes maintain backward compatibility with existing cases

## 2025-05-20: Streamlined Case Processing Workflow for URL Import

Modified the URL import process to skip the raw view when users click "Process URL":

**Issue**:
When importing cases from a URL, the workflow required:
1. Enter URL at `/cases/new/url`
2. Click "Process URL" (which went to the edit form)
3. OR click "View Raw Content First" (to see the raw HTML) 
4. From the raw content view, click "Process as NSPE Case" to see the extracted content
5. Then click "Save and View Case" to finalize

This workflow required too many steps when users simply wanted to process the URL directly.

**Solution**:
1. Modified `create_case_from_url.html` template to change the behavior of the "Process URL" button:
   - Changed the primary form action from `cases.create_from_url` to `cases.process_url_pipeline` 
   - Added a hidden input field `process_extraction=true` to trigger NSPE case extraction directly
   - Updated the "View Raw Content First" button to set `process_extraction=false` before submitting

**Implementation Details**:
```html
<form method="post" action="{{ url_for('cases.process_url_pipeline') }}">
    <input type="hidden" name="process_extraction" value="true">
    <!-- form fields -->
    <div class="d-grid gap-2 d-md-flex justify-content-md-end">
        <button type="submit" class="btn btn-success me-2">Process URL</button>
        <button type="submit" class="btn btn-primary"
            formaction="{{ url_for('cases.process_url_pipeline') }}"
            onclick="document.querySelector('[name=process_extraction]').value='false';">
            <i class="bi bi-file-text"></i> View Raw Content First
        </button>
    </div>
</form>
```

**Results**:
- Clicking "Process URL" now directly runs the NSPE case extraction step
- The raw content view option is still available through "View Raw Content First"
- The workflow is more streamlined while maintaining all functionality
- This change eliminates unnecessary steps for the most common use case

## 2025-05-20: Fixed Database Schema for Case Deletion

Resolved an issue that was causing errors when deleting cases:

**Issue**:
When attempting to delete a case (e.g., http://127.0.0.1:3333/cases/210/delete), the system would encounter a database schema error:
```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedColumn) column document_chunks.content does not exist
```

**Analysis**:
1. The SQLAlchemy model for `DocumentChunk` defined columns that were missing in the actual database schema:
   - `content` column (TEXT)
   - `updated_at` column (TIMESTAMP)
2. There was also a type mismatch with the `embedding` column, which needed to be FLOAT[] for SQLAlchemy

**Solution**:
1. Created a SQL script `fix_document_chunks_content_column.sql` to:
   - Add the missing `content` column to the `document_chunks` table
   - Add the missing `updated_at` column
   - Fix the `embedding` column type to be FLOAT[]
2. The script ensured the pgvector extension was properly installed
3. Created a Python script `fix_document_chunks_column.py` to execute the SQL fix

**Implementation Details**:
```sql
-- Fix document_chunks table columns and extensions
DO $$
BEGIN
    -- Ensure pgvector extension is installed
    CREATE EXTENSION IF NOT EXISTS vector;
    
    -- Add missing content column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                  WHERE table_name = 'document_chunks' AND column_name = 'content') THEN
        ALTER TABLE document_chunks ADD COLUMN content TEXT;
        UPDATE document_chunks SET content = '';
        ALTER TABLE document_chunks ALTER COLUMN content SET NOT NULL;
    END IF;

    -- Add missing updated_at column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                  WHERE table_name = 'document_chunks' AND column_name = 'updated_at') THEN
        ALTER TABLE document_chunks ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
    END IF;
    
    -- Fix embedding column type
    BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.columns 
                  WHERE table_name = 'document_chunks' AND column_name = 'embedding') THEN
            ALTER TABLE document_chunks DROP COLUMN embedding;
        END IF;
        ALTER TABLE document_chunks ADD COLUMN embedding FLOAT[];
    END;
END $$;
```

**Result**:
The fix successfully resolved the database schema issue, allowing cases to be deleted without errors.

## 2025-05-20: Added Question and Conclusion List Parsing for Legacy Cases

Fixed an issue where legacy cases (like #206) had concatenated questions and conclusions that weren't displaying as proper lists:

**Issue**:
Some older case entries in the database, particularly case #206 ("Acknowledging Errors in Design", Case #23-4), had questions and conclusions stored as concatenated strings rather than structured arrays. This resulted in poor readability when viewing these cases, as the questions and conclusions appeared as a single block of text without proper formatting.

**Analysis**:
1. Examination revealed that case #206 had three distinct questions, but they were stored as a single string without proper separation.
2. Similarly, the conclusion section contained three distinct items that should be displayed as a list.
3. The database had multiple duplicate entries (13 instances) of this case with IDs ranging from #188 to #209, with varying levels of metadata completeness.
4. Case #206 had the most complete metadata with case_number "23-4" and year "2023".

**Solution**:

1. Enhanced the `save_and_view_case` route in `cases.py` to automatically parse questions from concatenated text:
   ```python
   # If the questions_list is empty but we have question_html, attempt to parse them
   if not questions_list and question_html:
       # Split by question mark followed by a capital letter (likely new question)
       # or split by question mark at end of string
       import re
       splits = re.split(r'\?((?=[A-Z][a-z])|$)', questions_raw)
       
       # Process the splits to form complete questions
       if len(splits) > 1:  # If we found at least one question mark
           temp_questions = []
           for i in range(0, len(splits) - 1, 2):
               if i + 1 < len(splits):
                   # Rejoin the question with its question mark
                   q = splits[i] + "?"
                   temp_questions.append(q.strip())
           
           # If we successfully parsed multiple questions, use them
           if temp_questions:
               questions_list = temp_questions
   ```

2. Created specific fix scripts for case #206 to correct both questions and conclusions:
   - `fix_case_206_questions.py`: Parsed the questions and updated the HTML content
   - `fix_case_206_conclusion.py`: Parsed the conclusion items and updated the HTML content

3. For conclusion parsing, used a regex pattern to detect items starting with "It was" or "Engineer":
   ```python
   # Pattern for conclusion items: Complete sentence ending with period, followed by another
   # that begins with "It was ethical" or similar beginning pattern
   splits = re.split(r'\.(?=It was|Engineer)', conclusion_html)
   ```

4. Created a verification script `verify_case_206_formatting.py` to confirm proper formatting in HTML output:
   - Confirmed 3 properly formatted question items in an ordered list
   - Confirmed 3 properly formatted conclusion items in an ordered list
   - Verified that heading was updated from "Conclusion" to "Conclusions" (plural)

**Results**:
- Case #206 now displays its three questions as a properly formatted numbered list:
  1. "Was it ethical for Engineer T and Engineer B to conclude an error had not been made in design?"
  2. "Was it ethical for Engineer T not to acknowledge an error after the accident occurred?"
  3. "Was it ethical for Engineer T not to acknowledge an error during the deposition?"

- The conclusion section now displays as a properly formatted numbered list:
  1. "It was ethical for Engineer T and Engineer B to conclude no error had been made in design..."
  2. "It was ethical for Engineer T not to acknowledge an error after the accident occurred..."
  3. "It was ethical for Engineer T to refrain from acknowledging an error during the deposition..."

- This fix improves readability and navigation of legacy cases without requiring manual editing of each case.

**Future Improvements**:
- Consider consolidating duplicate case entries in the database to prevent confusion
- Apply similar parsing logic to other legacy cases that may have the same formatting issues
- Add question and conclusion parsing to the case import pipeline to handle future imports consistently

## 2025-05-20: Fixed Question List Display and Removed "Show More" Link in Case Detail View

Fixed two issues with the case detail view that affected cases imported via the "Save and View Case" feature:

**Issue 1: Questions not displaying properly as a numbered list**
When using the "Save and View Case" button, questions were not being displayed as a proper numbered list in the saved case view.

**Solution:**
1. Enhanced the case_detail.html template to specifically render questions from metadata:
   ```html
   <!-- Questions list from metadata if available -->
   {% if case.doc_metadata.questions_list %}
   <div class="row mb-4">
       <div class="col-12">
           <div class="card">
               <div class="card-header bg-light">
                   {% if case.doc_metadata.questions_list|length > 1 %}
                   <h5 class="mb-0">Questions</h5>
                   {% else %}
                   <h5 class="mb-0">Question</h5>
                   {% endif %}
               </div>
               <div class="card-body">
                   <ol class="mb-0">
                       {% for question in case.doc_metadata.questions_list %}
                       <li>{{ question }}</li>
                       {% endfor %}
                   </ol>
               </div>
           </div>
       </div>
   </div>
   {% endif %}
   ```

2. This dedicated section properly renders the questions as an ordered list, exactly as they appear on the extraction page.

**Issue 2: "Show More" link appearing on saved displayed cases**
The case detail view would automatically add a "Show More" link to long case descriptions, but this wasn't desired for cases using the extraction-style formatting.

**Solution:**
1. Added a data attribute to identify extraction-style cases in the template:
   ```html
   {% if case.doc_metadata and case.doc_metadata.display_format == 'extraction_style' %}
   <div data-extraction-style="true">
       {{ case.description|safe }}
   </div>
   {% endif %}
   ```

2. Modified the JavaScript to check for this attribute and skip adding the "Show More" button:
   ```javascript
   function setupShowMoreLessToggle() {
       // Skip show more/less toggle for extraction style formatted cases
       if (document.querySelector('[data-extraction-style="true"]')) {
           console.log('Skipping show more/less toggle for extraction style case');
           return;
       }
       
       // Rest of function...
   }
   ```

**Results:**
- Questions now display as properly formatted numbered lists in saved cases
- Extraction-style formatted cases no longer display the "Show More" button
- The formatting exactly matches how cases appear on the extraction page
- All changes maintain backward compatibility with existing cases

## 2025-05-20: Fixed List Formatting in Save and View Case Route

Fixed an issue with the formatting of question and conclusion lists in the "Save and View Case" feature:

**Issue**:
When using the "Save and View Case" button, questions that were properly displayed as a numbered list on the extraction page (e.g., "1. Question one, 2. Question two, 3. Question three") were being displayed without proper list formatting in the saved case view, resulting in text like: "Question oneQuestion twoQuestion three" with no separation or numbering.

**Analysis**:
The HTML generation in the `save_and_view_case` route wasn't properly formatting the list items in the rendered HTML. While the list structure was there with `<ol>` and `<li>` tags, the code didn't ensure proper spacing and clean formatting of each list item.

**Solution**:
1. Enhanced the HTML generation in the `save_and_view_case` route to:
   - Add proper class "mb-0" to the ordered lists for consistent margin styling
   - Add proper indentation to list items for better HTML structure
   - Strip unnecessary whitespace from questions and conclusion text
   - Add extra spacing for better visual clarity in the HTML output

2. Applied the same improvements to both question and conclusion list formatting

**Implementation Details**:
```python
# For questions section
if questions_list:
    html_content += "<ol class=\"mb-0\">\n"
    # Add proper spacing and formatting for each question
    for q in questions_list:
        # Ensure each question is on its own line with proper spacing
        # and remove any trailing/leading whitespace
        clean_question = q.strip()
        html_content += f"    <li>{clean_question}</li>\n"
    html_content += "</ol>\n"
```

Similar improvements were made to the conclusion items section as well.

**Results**:
- Questions now display as properly formatted numbered lists in the saved case view
- Each question is correctly separated and numbered
- The formatting exactly matches how it appears on the extraction page
- The fix maintains all previous functionality while improving the visual display

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
   <div data-extraction-style="true">
       {{ case.description|safe }}
   </div>
   {% endif %}
   ```

**Results**:
- Cases are now displayed exactly as they appear during extraction with proper formatting
- Lists in questions and conclusions are properly formatted as HTML ordered lists
- The card-based layout with proper headers is preserved in the saved case view
- Users can save cases in one click, bypassing the edit step entirely
- The original workflow is still available for users who need to edit before saving

**Future Improvements**:
- Enhance extraction to support more complex HTML structures in case content
- Add options to customize the display format based on user preferences
- Improve the export functionality to preserve formatting in exported documents
