# Embedding Model Implementation for AI Ethical Decision-Making Simulator

## Open-Source Embedding Solution

For the AI Ethical Decision-Making Simulator, we'll implement a robust document processing and embedding system using open-source models, specifically Sentence-Transformers, with PostgreSQL's pgvector extension for storage and retrieval.

## Selected Embedding Model

### Primary Model: all-MiniLM-L6-v2
- **Size**: ~80MB
- **Dimensions**: 384
- **Performance**: Excellent balance of quality and efficiency
- **Source**: [Sentence-Transformers](https://www.sbert.net/docs/pretrained_models.html)
- **Advantages**:
  - Small footprint (80MB vs 420MB for larger models)
  - Fast inference time
  - Good semantic search performance
  - Well-suited for ethical text similarity

### Alternative Models
- **all-mpnet-base-v2**: Higher quality but larger (420MB)
- **paraphrase-multilingual-MiniLM-L12-v2**: For multilingual support

## Document Processing Pipeline

### 1. Document Loading

```python
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
    UnstructuredHTMLLoader
)

def load_document(file_path):
    """Load document based on file extension."""
    if file_path.endswith('.pdf'):
        loader = PyPDFLoader(file_path)
    elif file_path.endswith('.docx'):
        loader = Docx2txtLoader(file_path)
    elif file_path.endswith('.txt'):
        loader = TextLoader(file_path)
    elif file_path.endswith('.html'):
        loader = UnstructuredHTMLLoader(file_path)
    else:
        raise ValueError(f"Unsupported file format: {file_path}")
    
    return loader.load()
```

### 2. Text Preprocessing

```python
import re
from langchain.text_splitter import RecursiveCharacterTextSplitter

def preprocess_text(documents):
    """Clean and preprocess document text."""
    processed_docs = []
    
    for doc in documents:
        text = doc.page_content
        
        # Basic cleaning
        text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with single space
        text = re.sub(r'^\s+|\s+$', '', text)  # Trim whitespace
        
        # Update document with cleaned text
        doc.page_content = text
        processed_docs.append(doc)
    
    return processed_docs
```

### 3. Text Splitting

```python
def split_documents(documents, chunk_size=1000, chunk_overlap=100):
    """Split documents into chunks with overlap."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    chunks = text_splitter.split_documents(documents)
    
    # Add chunk index to metadata
    for i, chunk in enumerate(chunks):
        if not chunk.metadata:
            chunk.metadata = {}
        chunk.metadata['chunk_index'] = i
    
    return chunks
```

### 4. Embedding Generation

```python
from sentence_transformers import SentenceTransformer
import numpy as np

class SentenceTransformerEmbeddings:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.embedding_size = self.model.get_sentence_embedding_dimension()
    
    def embed_documents(self, texts):
        """Generate embeddings for a list of documents."""
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()
    
    def embed_query(self, text):
        """Generate embedding for a query."""
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
```

### 5. Cloud Hosting Options

#### Option 1: Hugging Face Inference API

```python
import requests
import json

class HuggingFaceEmbeddings:
    def __init__(self, api_key, model_id="sentence-transformers/all-MiniLM-L6-v2"):
        self.api_url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{model_id}"
        self.headers = {"Authorization": f"Bearer {api_key}"}
    
    def embed_documents(self, texts):
        """Generate embeddings for a list of documents using Hugging Face API."""
        response = requests.post(
            self.api_url,
            headers=self.headers,
            json={"inputs": texts, "options": {"wait_for_model": True}}
        )
        return json.loads(response.content)
    
    def embed_query(self, text):
        """Generate embedding for a query using Hugging Face API."""
        response = requests.post(
            self.api_url,
            headers=self.headers,
            json={"inputs": text, "options": {"wait_for_model": True}}
        )
        return json.loads(response.content)
```

#### Option 2: Lightweight Self-Hosted FastAPI Service

```python
# server.py
from fastapi import FastAPI, Body
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel
from typing import List
import uvicorn

app = FastAPI()
model = SentenceTransformer("all-MiniLM-L6-v2")

class EmbeddingRequest(BaseModel):
    texts: List[str]

@app.post("/embed")
def create_embeddings(request: EmbeddingRequest):
    embeddings = model.encode(request.texts).tolist()
    return {"embeddings": embeddings}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## pgvector Integration

### 1. Database Schema

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create documents table
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    source TEXT,
    file_path TEXT,
    file_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- Create document_embeddings table
CREATE TABLE document_embeddings (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER,
    chunk_text TEXT NOT NULL,
    embedding vector(384),  -- For all-MiniLM-L6-v2
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster similarity search
CREATE INDEX ON document_embeddings USING ivfflat (embedding vector_cosine_ops);
```

### 2. SQLAlchemy Models

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class Document(Base):
    __tablename__ = 'documents'
    
    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    source = Column(Text)
    file_path = Column(Text)
    file_type = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    metadata = Column(JSON)

class DocumentEmbedding(Base):
    __tablename__ = 'document_embeddings'
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'))
    chunk_index = Column(Integer)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(384))  # For all-MiniLM-L6-v2
    metadata = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
```

### 3. Document Storage and Retrieval

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import json

class PgVectorStore:
    def __init__(self, connection_string, embedding_model):
        self.engine = create_engine(connection_string)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.embedding_model = embedding_model
    
    def add_document(self, title, chunks, source=None, file_path=None, file_type=None, metadata=None):
        """Add a document and its chunks to the database."""
        # Create document record
        doc = Document(
            title=title,
            source=source,
            file_path=file_path,
            file_type=file_type,
            metadata=metadata
        )
        self.session.add(doc)
        self.session.flush()
        
        # Get document ID
        doc_id = doc.id
        
        # Process chunks in batches
        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            texts = [chunk.page_content for chunk in batch]
            embeddings = self.embedding_model.embed_documents(texts)
            
            # Create embedding records
            for j, (chunk, embedding) in enumerate(zip(batch, embeddings)):
                chunk_embedding = DocumentEmbedding(
                    document_id=doc_id,
                    chunk_index=chunk.metadata.get('chunk_index', i+j),
                    chunk_text=chunk.page_content,
                    embedding=embedding,
                    metadata=chunk.metadata
                )
                self.session.add(chunk_embedding)
        
        self.session.commit()
        return doc_id
    
    def similarity_search(self, query, k=5, filter_criteria=None):
        """Search for similar chunks using vector similarity."""
        # Generate query embedding
        query_embedding = self.embedding_model.embed_query(query)
        
        # Build query
        base_query = self.session.query(
            DocumentEmbedding.chunk_text,
            DocumentEmbedding.metadata,
            Document.title,
            Document.source,
            "embedding <-> :query_embedding AS distance"
        ).join(
            Document, DocumentEmbedding.document_id == Document.id
        )
        
        # Apply filters if provided
        if filter_criteria:
            for key, value in filter_criteria.items():
                if key == 'document_id':
                    base_query = base_query.filter(DocumentEmbedding.document_id == value)
                elif key == 'source':
                    base_query = base_query.filter(Document.source == value)
                # Add more filters as needed
        
        # Execute query
        results = base_query.params(
            query_embedding=query_embedding
        ).order_by(
            "distance"
        ).limit(k).all()
        
        # Format results
        formatted_results = []
        for chunk_text, metadata, title, source, distance in results:
            formatted_results.append({
                'chunk_text': chunk_text,
                'metadata': metadata,
                'title': title,
                'source': source,
                'distance': distance
            })
        
        return formatted_results
```

## Optimization Strategies

### 1. Batch Processing

```python
def process_document_batch(file_paths, vector_store, batch_size=5):
    """Process multiple documents in batches."""
    for i in range(0, len(file_paths), batch_size):
        batch = file_paths[i:i+batch_size]
        for file_path in batch:
            try:
                # Extract file info
                file_name = os.path.basename(file_path)
                file_type = os.path.splitext(file_name)[1][1:]
                
                # Process document
                raw_docs = load_document(file_path)
                processed_docs = preprocess_text(raw_docs)
                chunks = split_documents(processed_docs)
                
                # Store document and embeddings
                vector_store.add_document(
                    title=file_name,
                    chunks=chunks,
                    file_path=file_path,
                    file_type=file_type
                )
                
                print(f"Processed {file_name}")
            except Exception as e:
                print(f"Error processing {file_path}: {str(e)}")
```

### 2. Caching

```python
import hashlib
from functools import lru_cache

class CachedEmbeddingModel:
    def __init__(self, embedding_model, cache_size=1000):
        self.embedding_model = embedding_model
        self.embed_query = lru_cache(maxsize=cache_size)(self._embed_query)
    
    def _embed_query(self, text):
        """Generate embedding for a query with caching."""
        return self.embedding_model.embed_query(text)
    
    def embed_documents(self, texts):
        """Generate embeddings for documents with caching for duplicates."""
        # Create a mapping of text to hash for deduplication
        text_hashes = {}
        for text in texts:
            text_hash = hashlib.md5(text.encode()).hexdigest()
            text_hashes[text_hash] = text
        
        # Get unique texts
        unique_texts = list(text_hashes.values())
        
        # Generate embeddings for unique texts
        unique_embeddings = self.embedding_model.embed_documents(unique_texts)
        
        # Create mapping of text to embedding
        text_to_embedding = {text: embedding for text, embedding in zip(unique_texts, unique_embeddings)}
        
        # Return embeddings in original order
        return [text_to_embedding[text] for text in texts]
```

### 3. Asynchronous Processing

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def process_documents_async(file_paths, vector_store, max_workers=4):
    """Process documents asynchronously using a thread pool."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        loop = asyncio.get_event_loop()
        
        async def process_file(file_path):
            return await loop.run_in_executor(
                executor,
                lambda: process_single_document(file_path, vector_store)
            )
        
        # Process files concurrently
        await asyncio.gather(*(process_file(file_path) for file_path in file_paths))

def process_single_document(file_path, vector_store):
    """Process a single document and add it to the vector store."""
    try:
        # Extract file info
        file_name = os.path.basename(file_path)
        file_type = os.path.splitext(file_name)[1][1:]
        
        # Process document
        raw_docs = load_document(file_path)
        processed_docs = preprocess_text(raw_docs)
        chunks = split_documents(processed_docs)
        
        # Store document and embeddings
        doc_id = vector_store.add_document(
            title=file_name,
            chunks=chunks,
            file_path=file_path,
            file_type=file_type
        )
        
        return {"success": True, "file_name": file_name, "doc_id": doc_id}
    except Exception as e:
        return {"success": False, "file_name": file_name, "error": str(e)}
```

## Integration with Existing Components

### 1. Flask Route for Document Upload

```python
from flask import Blueprint, request, jsonify
import os
from werkzeug.utils import secure_filename

document_bp = Blueprint('documents', __name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt', 'html'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@document_bp.route('/upload', methods=['POST'])
def upload_document():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        
        # Ensure upload directory exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        # Save file
        file.save(file_path)
        
        # Process document in background
        # This could be a Celery task or similar
        process_document_task.delay(file_path)
        
        return jsonify({
            "message": "File uploaded successfully",
            "filename": filename
        }), 201
    
    return jsonify({"error": "File type not allowed"}), 400
```

### 2. Integration with LangChain Retriever

```python
from langchain.retrievers import PGVectorRetriever
from langchain.schema import Document as LangchainDocument

class PgVectorRetriever:
    def __init__(self, vector_store):
        self.vector_store = vector_store
    
    def get_relevant_documents(self, query, k=5, filter_criteria=None):
        """Retrieve relevant documents for a query."""
        results = self.vector_store.similarity_search(query, k, filter_criteria)
        
        # Convert to LangChain documents
        documents = []
        for result in results:
            doc = LangchainDocument(
                page_content=result['chunk_text'],
                metadata={
                    'title': result['title'],
                    'source': result['source'],
                    'distance': result['distance'],
                    **result['metadata']
                }
            )
            documents.append(doc)
        
        return documents
```

### 3. Integration with Decision Engine

```python
from app.services.decision_engine import DecisionEngine

class EnhancedDecisionEngine(DecisionEngine):
    def __init__(self, llm_service, retriever):
        super().__init__(llm_service)
        self.retriever = retriever
    
    def evaluate_decision(self, decision, scenario, character, guidelines=None):
        """Evaluate a decision with relevant guidelines retrieved from vector store."""
        # Construct query from decision and scenario
        query = f"Decision: {decision.description}. Scenario: {scenario.description}."
        
        # Retrieve relevant guidelines
        relevant_guidelines = self.retriever.get_relevant_documents(
            query,
            filter_criteria={'world_id': scenario.world_id}
        )
        
        # Extract guideline texts
        guideline_texts = [doc.page_content for doc in relevant_guidelines]
        
        # Combine with any explicitly provided guidelines
        if guidelines:
            guideline_texts.extend(guidelines)
        
        # Use the combined guidelines for evaluation
        return super().evaluate_decision_with_guidelines(
            decision, scenario, character, guideline_texts
        )
```

## Implementation Plan

### Phase 1: Foundation (Week 1)
1. Set up Sentence-Transformers embedding pipeline
2. Implement pgvector schema and basic storage/retrieval
3. Create document processing functions

### Phase 2: Integration (Week 2)
1. Integrate with Flask application
2. Connect to LangChain components
3. Implement background processing

### Phase 3: Optimization (Week 3)
1. Add caching mechanisms
2. Implement batch processing
3. Add asynchronous processing

### Phase 4: Testing and Refinement (Week 4)
1. Test with various document types
2. Optimize retrieval performance
3. Refine integration with decision engine
