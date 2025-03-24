# Document Management System

## Overview

The Document Management System is a component of the AI Ethical DM platform that allows users to upload, manage, and search through documents using semantic search. This system enhances the platform by providing a way to search through guidelines, case studies, and other relevant documents.

## Features

- Upload documents in various formats (PDF, DOCX, TXT, HTML)
- Process documents for vector embeddings
- Perform semantic search across documents
- Filter documents by world and document type
- Download original documents
- Process URLs for embedding and search

## API Endpoints

### Document Upload

```
POST /api/documents
```

**Form Parameters:**
- `file`: The document file to upload
- `title`: Document title
- `document_type`: Type of document (e.g., 'guideline', 'case_study', 'academic_paper')
- `world_id` (optional): ID of the world to associate the document with
- `source` (optional): Source of the document

**Response:**
```json
{
  "message": "Document uploaded and processed successfully",
  "document_id": 1,
  "title": "Document Title"
}
```

### Get Documents

```
GET /api/documents
```

**Query Parameters:**
- `world_id` (optional): Filter by world ID
- `document_type` (optional): Filter by document type

**Response:**
```json
[
  {
    "id": 1,
    "title": "Document Title",
    "document_type": "guideline",
    "source": "Source",
    "world_id": 1,
    "file_type": "pdf",
    "created_at": "2025-03-24T13:30:00.000Z"
  }
]
```

### Get Document by ID

```
GET /api/documents/{document_id}
```

**Response:**
```json
{
  "id": 1,
  "title": "Document Title",
  "document_type": "guideline",
  "source": "Source",
  "world_id": 1,
  "file_type": "pdf",
  "file_path": "/path/to/file.pdf",
  "content": "Document content...",
  "metadata": {},
  "created_at": "2025-03-24T13:30:00.000Z",
  "updated_at": "2025-03-24T13:30:00.000Z"
}
```

### Download Document

```
GET /api/documents/{document_id}/download
```

Returns the original document file for download.

### Delete Document

```
DELETE /api/documents/{document_id}
```

**Response:**
```json
{
  "message": "Document 1 deleted successfully"
}
```

### Search Documents

```
POST /api/documents/search
```

**Request Body:**
```json
{
  "query": "search query",
  "world_id": 1,
  "document_type": "guideline",
  "limit": 5
}
```

**Response:**
```json
[
  {
    "id": 1,
    "chunk_text": "Matching text...",
    "metadata": {},
    "title": "Document Title",
    "source": "Source",
    "document_type": "guideline",
    "world_id": 1,
    "distance": 0.15
  }
]
```

### Process URL

```
POST /api/documents/process-url
```

**Request Body:**
```json
{
  "url": "https://example.com",
  "title": "Document Title",
  "document_type": "guideline",
  "world_id": 1
}
```

**Response:**
```json
{
  "message": "URL processed successfully",
  "document_id": 1,
  "title": "Document Title"
}
```

## Usage Examples

### Uploading a Document

```javascript
const formData = new FormData();
formData.append('file', file);
formData.append('title', 'Ethics Guidelines');
formData.append('document_type', 'guideline');
formData.append('world_id', '1');
formData.append('source', 'Organization XYZ');

fetch('/api/documents', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => console.log(data));
```

### Searching Documents

```javascript
fetch('/api/documents/search', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    query: 'ethical dilemma in healthcare',
    world_id: 1,
    document_type: 'case_study',
    limit: 5
  })
})
.then(response => response.json())
.then(results => console.log(results));
```

## Technical Details

### Document Processing Flow

1. Document is uploaded and stored
2. Text is extracted based on file type
3. Text is split into chunks with overlap
4. Embeddings are generated for each chunk
5. Chunks and embeddings are stored in the database

### Search Process

1. Query is converted to an embedding
2. If pgvector is available, vector similarity search is performed in the database
3. If pgvector is not available, a fallback similarity search is performed using cosine distance
4. Results are ranked by similarity and returned

### Supported File Types

- PDF (`.pdf`)
- Microsoft Word (`.docx`, `.doc`)
- Text (`.txt`)
- HTML (`.html`, `.htm`)

## Integration with Other Components

The Document Management System integrates with:

- **Worlds**: Documents can be associated with specific worlds
- **Decision Engine**: Can provide relevant documents during scenario creation
- **Agent**: Can use document search to provide context for agent responses
