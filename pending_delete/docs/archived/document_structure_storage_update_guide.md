# Document Structure Storage Update Guide

This guide explains how to use the `update_document_structure_storage.py` script to apply document structure annotations to existing case documents, implementing Phase 2.4 of the document structure enhancement plan.

## Overview

The document structure storage update script enhances existing case documents by:

- Adding ontology-based document structure annotations to the doc_metadata
- Preparing section-level embedding metadata for future semantic search
- Maintaining backward compatibility with existing document retrieval code

## Prerequisites

Before running the script, ensure:

1. You have database connection credentials configured
2. The ProEthica ontology is loaded and accessible
3. The cases you want to update have structured sections in their metadata

## Usage

### Basic Usage

To run the script against all case study documents:

```bash
python update_document_structure_storage.py
```

This will process all case study documents and update their doc_metadata with structure annotations.

### Process a Specific Case

To process only a single case document, specify the case ID:

```bash
python update_document_structure_storage.py --case-id 222
```

### Dry Run (No Database Changes)

To test the script without making actual database changes:

```bash
python update_document_structure_storage.py --dry-run
```

You can also combine options:

```bash
python update_document_structure_storage.py --case-id 222 --dry-run
```

## Output

The script provides detailed logging information:

- Progress information for each document processed
- Success/failure status for each operation
- Statistics summary at the end
- List of any errors encountered

### Example Output

```
2025-05-20 23:19:52,553 - __main__ - INFO - Starting document structure storage update...
2025-05-20 23:19:52,553 - __main__ - INFO - Processing specific case ID: 222
2025-05-20 23:19:52,556 - __main__ - INFO - Found 1 case study documents to process.
2025-05-20 23:19:52,556 - __main__ - INFO - Processing document ID: 222 - 'Acknowledging Errors in Design'
2025-05-20 23:19:52,569 - app.services.case_processing.pipeline_steps.document_structure_annotation_step - INFO - Document structure annotation complete for case 23-4: 127 triples generated
2025-05-20 23:19:52,589 - __main__ - INFO - Document 222 updated with structure information.
2025-05-20 23:19:52,589 - __main__ - INFO - ==================================================
2025-05-20 23:19:52,589 - __main__ - INFO - Document Structure Update Summary
2025-05-20 23:19:52,590 - __main__ - INFO - ==================================================
2025-05-20 23:19:52,590 - __main__ - INFO - Total documents processed: 1
2025-05-20 23:19:52,590 - __main__ - INFO - Documents updated: 1
2025-05-20 23:19:52,590 - __main__ - INFO - Documents skipped: 0
2025-05-20 23:19:52,590 - __main__ - INFO - Documents with errors: 0
2025-05-20 23:19:52,590 - __main__ - INFO - ==================================================
2025-05-20 23:19:52,590 - __main__ - INFO - UPDATE COMPLETE
```

## Verification

To verify that a document has been properly annotated, use the `check_case_structure.py` script:

```bash
python check_case_structure.py <case_id>
```

This will display the document structure information, including:
- Document URI
- Structure triples
- Section embedding metadata

## Additional Notes

- The script is idempotent - running it multiple times on the same document will not duplicate annotations
- Documents that already have document structure annotations will be skipped
- Documents without proper section data will be skipped with a warning
