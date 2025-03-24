# Vector Embeddings and Document Retrieval Implementation

This document outlines the implementation of vector embeddings and document retrieval functionality for the AI Ethical Decision-Making Simulator.

## Overview

We've implemented a system for processing, storing, and retrieving documents using vector embeddings. This allows for semantic similarity search, which is particularly useful for retrieving relevant guidelines, case studies, and other reference materials when evaluating ethical decisions.

## Components

1. **Database Models**
   - `Document`: Represents a document uploaded to the system (guidelines, case studies, etc.)
   - `DocumentChunk`: Represents a chunk of text from a document with its vector embedding

2. **Embedding Service**
   - Processes documents: extracts text, splits into chunks, generates embeddings
   - Performs vector similarity search to find relevant documents
   - Supports various file types: PDF, DOCX, TXT, HTML

3. **Enhanced Decision Engine**
   - Extends the base DecisionEngine with vector similarity search
   - Retrieves relevant guidelines based on scenario and decision context
   - Provides more accurate and contextually relevant evaluations

4. **API Endpoints**
   - Upload and process documents
   - Search for documents using vector similarity
   - Retrieve document content and metadata

5. **Integration with World Management**
   - Upload guidelines documents when editing worlds
   - Associate documents with specific worlds for context-aware retrieval

## Setup Instructions

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install pgvector Extension**
   ```bash
   ./scripts/install_pgvector.sh
   ```

3. **Enable pgvector in PostgreSQL**
   ```bash
   psql -d your_database_name -f scripts/enable_pgvector.sql
   ```

4. **Create Database Tables**
   Using Flask-Migrate (recommended):
   ```bash
   flask db migrate -m "Add document and document_chunk tables with pgvector support"
   flask db upgrade
   ```
   
   Or using the manual script:
   ```bash
   python scripts/manual_create_document_tables.py
   ```

5. **Create Uploads Directory**
   ```bash
   mkdir -p app/uploads
   ```

Alternatively, you can run the setup script:
```bash
./scripts/setup_embedding_environment.sh
```

## Usage

### Uploading Documents

Documents can be uploaded through:
1. The web interface when editing a world (for guidelines)
2. The API endpoint: `POST /api/documents`

### Searching Documents

To search for documents using vector similarity:
```
POST /api/documents/search
Content-Type: application/json

{
  "query": "Your search query here",
  "world_id": 1,  // Optional: Filter by world
  "document_type": "guideline",  // Optional: Filter by document type
  "limit": 5  // Optional: Number of results to return
}
```

### Using the Enhanced Decision Engine

The EnhancedDecisionEngine can be used in place of the base DecisionEngine:

```python
from app.services import EnhancedDecisionEngine

# Create an instance of the enhanced engine
engine = EnhancedDecisionEngine()

# Evaluate a decision
result = engine.evaluate_decision(decision, scenario, character)
```

## Benefits

1. **Contextual Relevance**: Retrieves guidelines and cases that are semantically relevant to the current scenario and decision, not just keyword matches.

2. **Improved Accuracy**: Provides more accurate evaluations by considering the most relevant guidelines and precedents.

3. **Scalability**: As the document collection grows, the system maintains efficient retrieval through vector indexing.

4. **Flexibility**: Supports various document types and can be extended to include additional sources like web pages.

## Next Steps

1. **Implement Batch Processing**: Add support for processing multiple documents in the background using a task queue (e.g., Celery).

2. **Enhance Search Capabilities**: Add filtering by metadata, date ranges, and other criteria.

3. **Improve Chunking Strategy**: Implement more sophisticated text chunking strategies based on semantic boundaries.

4. **Add Document Versioning**: Track changes to documents over time and maintain version history.

5. **Implement User Feedback**: Allow users to provide feedback on search results to improve relevance.
