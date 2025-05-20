# Case Processing Pipeline Implementation Plan

## Overview

This document outlines the plan for implementing a step-by-step case processing pipeline for the AI Ethical DM project. The pipeline will start with simple URL-based case retrieval and progressively enhance capability with more sophisticated processing steps in future iterations.

## Goals

1. Build a modular case processing pipeline that starts with URL content retrieval
2. Implement each processing step independently to allow incremental development
3. Create a system that can be extended with advanced ontology-based analysis
4. Minimize changes to the main Flask application files

## Architecture

The pipeline follows a modular architecture with these components:

```
app/services/case_processing/
├── __init__.py
├── pipeline_steps/
│   ├── __init__.py
│   ├── base_step.py           # Base class for all pipeline steps
│   ├── url_retrieval_step.py  # Step 1: Basic URL content retrieval
│   ├── nspe_extraction_step.py # Step 2: Extract structured content from NSPE case HTML
│   └── [future_steps].py      # Additional steps to be added later
├── pipeline_manager.py        # Orchestrates the execution of pipeline steps
└── pipeline_result.py         # Standardized result format
```

## Implementation Phases

### Phase 1: Foundation & URL Retrieval (Completed)

#### Implemented Components:

1. **BaseStep Interface**
   - Defines common interface for all pipeline steps
   - Includes step metadata (name, description, version)
   - Standardizes input/output formats
   - Implements error handling and logging

2. **URLRetrievalStep Implementation**
   - Creates step for fetching content from URLs
   - Implements proper validation and error handling
   - Returns raw content without processing
   - Supports various content types (HTML, PDF, etc.)

3. **PipelineManager**
   - Creates class to manage pipeline execution
   - Supports running individual steps or complete pipeline
   - Handles state management between steps
   - Implements proper error handling and recovery

4. **Pipeline Integration**
   - Created new route at `/cases/process/url` for pipeline access
   - Integrated with existing URL processing route
   - Allows specifying which steps to run
   - Returns results in a standardized format

### Phase 2: NSPE Case Structure Extraction (Current Phase - Implemented)

Building on Phase 1, we have implemented a new extraction step:

#### NSPECaseExtractionStep

This step extracts structured content from NSPE case HTML pages by:

1. **Identifying Key Metadata**
   - Case Number (e.g., "23-4")
   - Year
   - Title
   - PDF URL (if available)

2. **Extracting Standard Case Sections**
   - Facts: The core narrative of the engineering ethics case
   - Question: The ethical question(s) being addressed
   - References: NSPE Code of Ethics references relevant to the case
   - Discussion: The detailed ethical analysis by the Board of Ethical Review
   - Conclusion: The Board's determination on the ethical issue

3. **Implementation Details**
   - Uses BeautifulSoup for HTML parsing
   - Employs multiple extraction methods for each section to handle variations in NSPE page structures
   - Cleans extracted text to remove unnecessary formatting
   - Validates input and provides meaningful error messages
   - Returns results in a standardized format consistent with the pipeline architecture

4. **UI Integration**
   - Updated the case processing view to display extracted content in a structured format
   - Added proper templating to show each section in an organized layout
   - Implemented extraction result rendering in `case_extracted_content.html` template

5. **Extraction Process**
   - First attempts to find section content using HTML structure and specific class markers
   - Falls back to text pattern matching for cases with less structured HTML
   - Uses a combination of regular expressions and text analysis to identify section boundaries
   - Preserves internal formatting and links to other cases within the discussion section

6. **Structured Content Parsing (Enhanced - May 2025)**
   - Added ability to extract individual questions as separate items within ordered lists
   - Enhanced conclusion handling to parse multiple conclusion items when present in numbered lists
   - Added pattern matching to detect numbered statements even when not in HTML list format
   - Implemented dynamic UI presentation that adapts based on content structure:
     - Shows single conclusion/question as paragraph
     - Shows multiple items as ordered lists
     - Dynamically adjusts headings (singular/plural) based on content

#### Technical Details:

- Section identification uses both HTML structure and content markers
- Multiple extraction strategies for each section to handle variations in page structure
- Proper error handling for cases where sections cannot be found
- Standardized input validation and error reporting
- Clean, consistent output structure that can be used for further processing
- Structured content extraction preserves both HTML representation and structured items

### Phase 3: Metadata & Structure Analysis (Future)

Extending the pipeline with:
- Enhanced metadata extraction techniques
- Document type classification
- More sophisticated section identification
- Reference extraction with normalization

### Phase 4: Semantic Analysis Integration (Future)

Incorporating ontology-based analysis:
- Entity extraction using engineering ethics ontology
- McLaren's extensional definition approach
- Ethical concept mapping
- Principle instantiation identification

### Phase 5: Knowledge Integration (Future)

Final phase focusing on:
- Triple generation from extracted entities
- Integration with existing ontology
- Case similarity analysis
- Cross-case learning

## Testing and Validation

### Testing Approach
1. **Unit Testing**: Test individual components of the extraction logic
2. **Integration Testing**: Test the pipeline as a whole with various NSPE case inputs
3. **Validation**: Compare extracted results with manual analysis of cases

### Key Test Cases
- NSPE case "23-4: Acknowledging Errors in Design" - Successfully extracts all major sections
- Future NSPE cases with different structures will be used to validate robustness

## Next Steps

1. **Refine NSPE Extraction**
   - Improve extraction of embedded links and references to other cases
   - Add support for footnotes and special annotations
   - Enhance handling of cases with non-standard section organization

2. **Extend to Other Case Sources**
   - Add support for other engineering ethics case sources
   - Implement a more general case extraction framework
   - Create adapters for different source formats

3. **Ontology Integration**
   - Develop methods to map extracted case content to engineering ethics ontology
   - Implement semantic analysis of case components
   - Create tools for comparative case analysis

## Database Schema Considerations

### Schema Migrations and Data Integrity

When enhancing the case processing pipeline, it's important to ensure database schema compatibility with all components. As the system evolves, we need to maintain proper schema synchronization and data integrity.

#### Key Considerations:

1. **Model-Schema Alignment**
   - Ensure SQLAlchemy models properly align with actual database tables
   - Use migrations for schema changes rather than manual alterations
   - Test model operations against the actual database

2. **Schema Validation**
   - Implement regular schema validation checks
   - Detect and resolve potential schema discrepancies early
   - Document all schema requirements for each component

3. **Backup Procedures**
   - Always create backups before schema modifications
   - Use the `backup_before_db_fix.py` script for easy database backups
   - Follow a "backup, test, implement" workflow for all schema changes

#### Lessons from Recent Issues (May 2025)

A critical finding during development was the mismatch between SQLAlchemy models and actual database schema for the `document_chunks` table:

- Required columns like `content` and `updated_at` were missing from database tables
- The `embedding` column had incorrect data type (was using pgvector's vector type while SQLAlchemy expected FLOAT[])
- These misalignments caused errors when attempting case deletion operations

The fix involved:
- Creating SQL scripts to add missing columns
- Converting vector type to FLOAT arrays
- Proper error handling and validation in scripts

This experience reinforced the importance of schema validation checks and proper migration procedures for all future database changes.

## Conclusion

The implementation of the case processing pipeline has successfully progressed through the initial phases. The URL retrieval and NSPE case extraction steps provide a solid foundation for more advanced processing. The modular design ensures we can extend the pipeline with additional capabilities in future phases. As we continue development, proper attention to database schema alignment will be essential to maintain system integrity and stability.
