# Asynchronous Document Processing

This document describes the implementation of asynchronous document processing in the AI Ethical DM application.

## Overview

The application allows users to upload guidelines documents (PDF, DOCX, TXT, HTML) and process them for vector embeddings. Previously, this processing was done synchronously in the request handler, which could cause the application to crash when processing large documents.

The new implementation processes documents asynchronously in background threads, allowing the web server to remain responsive during processing.

## Implementation Details

### 1. Document Model

The Document model has been extended with two new fields:

- `processing_status`: A string field that tracks the current status of document processing. Possible values are:
  - `pending`: Document has been created but processing has not started
  - `processing`: Document is currently being processed
  - `completed`: Document has been successfully processed
  - `failed`: Document processing failed

- `processing_error`: A text field that stores error messages if processing fails

### 2. Background Task Queue

A new service called `BackgroundTaskQueue` has been implemented to handle asynchronous document processing:

- It uses Python's threading module to process documents in background threads
- It maintains a singleton instance to ensure a single queue is used across the application
- It provides a method `process_document_async` to queue documents for processing
- It handles errors gracefully and updates the document status accordingly

### 3. Route Changes

The world routes have been updated to use the background task queue:

- When a document is uploaded, it is saved to the database with a `pending` status
- The document is then queued for processing using `task_queue.process_document_async()`
- The user is redirected to the world detail page immediately, without waiting for processing to complete
- The guidelines page shows the processing status of each document

### 4. UI Changes

The guidelines template has been updated to show the processing status of documents:

- Documents in `pending` or `processing` status show a spinner and a message
- Documents in `failed` status show an error message
- Documents in `completed` status show their content as before

## Benefits

- The application remains responsive even when processing large documents
- Users can continue using the application while documents are being processed
- Processing errors are handled gracefully and displayed to the user
- The application is more stable and less likely to crash

## Usage

No changes are required in how users interact with the application. The processing happens automatically in the background.

## Future Improvements

Potential future improvements include:

1. Using a proper task queue like Celery for more robust background processing
2. Adding a progress indicator for document processing
3. Implementing retry logic for failed processing
4. Adding a way to manually trigger reprocessing of failed documents
