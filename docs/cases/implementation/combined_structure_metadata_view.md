# Combined Structure and Metadata View

## Overview

The Structure Triples viewer now combines the Section Metadata display with the Structure Triples, creating a unified view that shows both the document structure and the actual content in an intuitive format.

## Implementation

### Changes Made

1. **Enhanced Structure Triple Formatter**
   - Added `_extract_all_section_items()` method to extract individual items with full content
   - Returns section items separately from the main section structure
   - Preserves item IDs, types, URIs, and full content

2. **Updated JavaScript Viewer**
   - Added `formatSectionItems()` method to display combined view
   - Groups items by parent section (Facts, Discussion, Questions, Conclusion, References)
   - Shows each item with:
     - Item ID (e.g., `conclusion_item_1`)
     - Type badge (e.g., "Conclusion Item")
     - Full URI in smaller text
     - Complete content in a highlighted box below

3. **Removed Duplicate Section**
   - Removed the separate "Section Metadata" card from the template
   - All information is now consolidated in the Structure Triples viewer

## Display Format

### Example: Case 276 "Temporary Disability"

**Questions Section:**
```
question_1    Question    http://proethica.org/document/case_21_4/question_1
Is he obligated to reveal his condition to his clients?

question_2    Question    http://proethica.org/document/case_21_4/question_2
Should he refrain from accepting engineering work until he is fully recovered?
```

**Conclusion Section:**
```
conclusion_item_1    Conclusion Item    http://proethica.org/document/case_21_4/conclusion_item_1
Engineer C is not obligated to reveal his condition to his clients.

conclusion_item_2    Conclusion Item    http://proethica.org/document/case_21_4/conclusion_item_2
Engineer C may continue accepting work while under treatment provided Engineer C retains a trusted colleague to review his work.
```

## Benefits

1. **Unified View**: No need to look at two separate sections to understand the document structure
2. **Clear Content Display**: Full text content is immediately visible under each item
3. **Better Context**: Items are grouped by their parent section for logical organization
4. **Preserved Metadata**: URIs and types are still visible for technical reference
5. **Cleaner Interface**: Reduces visual clutter by combining related information

## Technical Details

- Items are identified by checking for patterns like `_item_`, `question_`, `conclusion_item_` in the URI
- Parent sections are determined by analyzing the `isPartOf` predicate
- The view maintains all original functionality including the raw triples toggle
- Content is displayed with proper formatting and escaping for security

## Usage for Similarity and LLM

The combined view enhances usability for:
- **Similarity Analysis**: Clear content display makes it easier to identify similar sections
- **LLM Integration**: Structured format with full content is ideal for prompting
- **Human Review**: Researchers can quickly scan questions and conclusions
- **Data Export**: All information is available in both formatted and raw views