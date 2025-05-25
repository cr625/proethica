# Implementation Steps - Dual-Layer Ontology and UI Fix

This document provides step-by-step instructions to implement both the dual-layer ontology tagging for case #168 and fix the JavaScript error in the case detail view.

## Part 1: Implement Dual-Layer Ontology Tagging

The dual-layer ontology tagging approach creates two types of entity triples for cases:
1. McLaren extensional elements at the case level (BFO-aligned principles, instantiations, conflicts)
2. Intermediate ontology elements at the scenario level (roles, resources, events, actions, conditions)

### Steps to Implement:

1. Run the dual-layer ontology tagging script:
   ```bash
   ./dual_layer_ontology_tagging.py
   ```

2. This will:
   - Connect to your database
   - Create McLaren extensional triples for case #168
   - Create intermediate ontology triples for the same case
   - Print a summary of all added triples

3. After the script completes, view the tagged case in your browser:
   http://127.0.0.1:3333/cases/168

## Part 2: Fix the "Show More" JavaScript Error

The JavaScript error occurs because the code tries to attach event listeners to elements that might not exist on the page. The solution adds null checks and proper error handling.

### Steps to Fix:

1. Open `app/templates/case_detail.html` in your editor

2. Find the JavaScript section where the error occurs, inside the `<script>` tags at the bottom of the file.

3. Replace the problematic JavaScript with the improved version:
   - Look for the DOM Content Loaded event listener section
   - Replace it with the code from `fix_triple_labels.js`
   - Make sure to keep the template variable `{{ case.id }}` instead of the placeholder value

4. The main fixes include:
   - Proper null checks for all DOM elements
   - Better error handling
   - Improved Show More/Less toggle functionality with null checks

5. After implementing these changes, reload the case detail page in your browser to see:
   - No more JavaScript errors in the console
   - Working "Show More" button for long case descriptions
   - Properly functioning triple label selection

## Verification

After implementing both parts:

1. The case detail page (http://127.0.0.1:3333/cases/168) should show:
   - RDF Properties section with the entity triples you added
   - Working interactive selection of triple labels
   - No JavaScript errors in the browser console

2. The console should output:
   - "Initializing case detail page interactions..."
   - "Initializing triple labels interaction..."
   - "Found X triple labels" (where X is the number of entity triples)
