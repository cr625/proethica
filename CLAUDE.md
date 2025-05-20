# ProEthica Project Development Log

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
