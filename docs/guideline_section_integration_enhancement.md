# Guideline Section Integration Enhancement

## Background

The guideline section integration process was taking a long time due to processing too many guideline triples. This document outlines the improvements made to streamline this process.

## Issue Analysis

The original process was attempting to associate all guideline triples with document sections, which led to excessive processing time. Our analysis identified the following:

1. There were 127 guideline concept triples in the `entity_triples` table with IDs between 3096 and 3222
2. These triples relate to up to 18 different engineering ethics concepts
3. All guideline concept triples are associated with guideline ID 43, which is linked to document ID 190 ("Engineering Ethics")
4. The association between document 190 and guideline 43 is maintained through the `guideline_metadata` column in the `guidelines` table which contains a `document_id` reference

## Solution Implemented

We created a selective cleanup process that preserves only the guideline concept triples needed for the application:

1. **Identification**: We identified that only triples with entity_type 'guideline_concept' and IDs between 3096-3222 were needed
2. **Cleanup Script**: Created `cleanup_selective_guideline_triples_v2.sql` to selectively preserve these triples
3. **Execution Wrapper**: Implemented `run_cleanup_selective_guideline_triples_v2.py` to safely execute the cleanup

## Implementation Details

The solution includes:

1. **SQL Script (`cleanup_selective_guideline_triples_v2.sql`)**
   - Preserves only triples for guideline ID 43 (linked to document 190)
   - Uses a transaction to ensure atomicity
   - Verifies counts before and after the operation

2. **Python Runner (`run_cleanup_selective_guideline_triples_v2.py`)**
   - Provides a user interface with confirmation prompt
   - Handles container verification
   - Logs results for audit purposes

## Usage

To use this enhancement:

```bash
# Ensure the PostgreSQL container is running
docker ps | grep proethica-postgres

# Run the selective cleanup script
./run_cleanup_selective_guideline_triples_v2.py

# Confirm by entering 'y' when prompted
```

## Current State

After applying this fix, only the guideline concept triples for document 190 / guideline 43 should remain in the database. This reduces the processing time in the guideline section integration process by limiting the number of triples that need to be analyzed.

## Future Considerations

1. For future guideline imports, consider implementing a more selective approach to triple generation and storage
2. Further optimize by adding database indexes on the `entity_type` and `world_id` columns if they are frequently queried
3. Consider pruning unused guideline concepts periodically as part of database maintenance
