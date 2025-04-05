# PostgreSQL pgvector Integration for AI Ethical Decision-Making Simulator

## Overview

This document outlines the implementation plan for integrating PostgreSQL's pgvector extension with the AI Ethical Decision-Making Simulator. The pgvector extension will enable efficient storage and retrieval of vector embeddings for ethical guidelines, case studies, and scenario components.

## PostgreSQL pgvector Setup

### 1. Installation and Configuration

```sql
-- Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify installation
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### 2. Database Schema Updates

```sql
-- Document table for storing uploaded ethical guidelines and case studies
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    source TEXT,
    document_type TEXT NOT NULL, -- 'guideline', 'case_study', 'academic_paper', etc.
    world_id INTEGER REFERENCES worlds(id) ON DELETE CASCADE,
    file_path TEXT,
    file_type TEXT,
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Document chunks table for storing text chunks with embeddings
CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(384), -- For all-MiniLM-L6-v2 (384 dimensions)
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for similarity search
CREATE INDEX ON document_chunks USING ivfflat (embedding vector_cosine_ops);

-- Scenario embeddings for similarity search between scenarios
CREATE TABLE scenario_embeddings (
    id SERIAL PRIMARY KEY,
    scenario_id INTEGER REFERENCES scenarios(id) ON DELETE CASCADE,
    embedding vector(384),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for scenario similarity search
CREATE INDEX ON scenario_embeddings USING ivfflat (embedding vector_cosine_ops);

-- Event embeddings for similarity search between events
CREATE TABLE event_embeddings (
    id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
    embedding vector(384),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for event similarity search
CREATE INDEX ON event_embeddings USING ivfflat (embedding vector_cosine_ops);
```

### 3. SQLAlchemy Models

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class Document(Base):
    __tablename__ = 'documents'
    
    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    source = Column(Text)
    document_type = Column(Text, nullable=False)
    world_id = Column(Integer, ForeignKey('worlds.id', ondelete='CASCADE'))
    file_path = Column(Text)
    file_type = Column(Text)
    content = Column(Text)
    metadata = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    world = relationship("World", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

class DocumentChunk(Base):
    __tablename__ = 'document_chunks'
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'))
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(384))  # For all-MiniLM-L6-v2
    metadata = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    document = relationship("Document", back_populates="chunks")

class ScenarioEmbedding(Base):
    __tablename__ = 'scenario_embeddings'
    
    id = Column(Integer, primary_key=True)
    scenario_id = Column(Integer, ForeignKey('scenarios.id', ondelete='CASCADE'))
    embedding = Column(Vector(384))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    scenario = relationship("Scenario", back_populates="embedding")

class EventEmbedding(Base):
    __tablename__ = 'event_embeddings'
    
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey('events.id', ondelete='CASCADE'))
    embedding = Column(Vector(384))
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    event = relationship("Event", back_populates="embedding")
```

### 4. Update Existing Models

```python
# Add to World model
class World(Base):
    # Existing fields...
    
    # Add relationship
    documents = relationship("Document", back_populates="world", cascade="all, delete-orphan")

# Add to Scenario model
class Scenario(Base):
    # Existing fields...
    
    # Add relationship
    embedding = relationship("ScenarioEmbedding", back_populates="scenario", uselist=False, cascade="all, delete-orphan")

# Add to Event model
class Event(Base):
    # Existing fields...
    
    # Add relationship
    embedding = relationship("EventEmbedding", back_populates="event", uselist=False, cascade="all, delete-orphan")
```

## Vector Store Implementation

### 1. PgVectorStore Class

```python
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from typing import List, Dict, Any, Optional
import numpy as np

class PgVectorStore:
    def __init__(self, db_url, embedding_model):
        """Initialize the PgVector store with database connection and embedding model."""
        self.engine = create_engine(db_url)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.embedding_model = embedding_model
    
    def add_document(self, title, content, document_type, world_id=None, source=None, 
                    file_path=None, file_type=None, metadata=None, chunk_size=1000, 
                    chunk_overlap=200):
        """Add a document to the vector store with chunking and embedding."""
        # Create document record
        document = Document(
            title=title,
            content=content,
            document_type=document_type,
            world_id=world_id,
            source=source,
            file_path=file_path,
            file_type=file_type,
            metadata=metadata
        )
        self.session.add(document)
        self.session.flush()  # Get document ID
        
        # Split content into chunks
        chunks = self._split_text(content, chunk_size, chunk_overlap)
        
        # Generate embeddings for chunks
        chunk_embeddings = self.embedding_model.embed_documents([chunk for chunk in chunks])
        
        # Create chunk records with embeddings
        for i, (chunk, embedding) in enumerate(zip(chunks, chunk_embeddings)):
            chunk_record = DocumentChunk(
                document_id=document.id,
                chunk_index=i,
                chunk_text=chunk,
                embedding=embedding,
                metadata={"index": i, "document_type": document_type}
            )
            self.session.add(chunk_record)
        
        self.session.commit()
        return document.id
    
    def _split_text(self, text, chunk_size, chunk_overlap):
        """Split text into chunks with overlap."""
        if not text:
            return []
            
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = min(start + chunk_size, text_length)
            
            # Try to find a good breaking point (period, newline, etc.)
            if end < text_length:
                # Look for a period or newline within the last 20% of the chunk
                search_start = max(start + int(chunk_size * 0.8), start)
                break_point = text.rfind('. ', search_start, end)
                if break_point == -1:
                    break_point = text.rfind('\n', search_start, end)
                
                if break_point != -1:
                    end = break_point + 1  # Include the period
            
            chunks.append(text[start:end])
            start = end - chunk_overlap
        
        return chunks
    
    def similarity_search(self, query, k=5, filter_criteria=None):
        """Search for similar chunks using vector similarity."""
        # Generate query embedding
        query_embedding = self.embedding_model.embed_query(query)
        
        # Build base query
        sql_query = """
        SELECT 
            dc.chunk_text, 
            dc.metadata,
            d.title,
            d.source,
            d.document_type,
            dc.embedding <-> :query_embedding AS distance
        FROM 
            document_chunks dc
        JOIN 
            documents d ON dc.document_id = d.id
        """
        
        # Add filters if provided
        where_clauses = []
        params = {"query_embedding": query_embedding}
        
        if filter_criteria:
            if 'document_type' in filter_criteria:
                where_clauses.append("d.document_type = :document_type")
                params['document_type'] = filter_criteria['document_type']
            
            if 'world_id' in filter_criteria:
                where_clauses.append("d.world_id = :world_id")
                params['world_id'] = filter_criteria['world_id']
        
        if where_clauses:
            sql_query += " WHERE " + " AND ".join(where_clauses)
        
        # Add ordering and limit
        sql_query += """
        ORDER BY distance
        LIMIT :k
        """
        params['k'] = k
        
        # Execute query
        result = self.session.execute(text(sql_query), params)
        
        # Format results
        results = []
        for row in result:
            results.append({
                'chunk_text': row.chunk_text,
                'metadata': row.metadata,
                'title': row.title,
                'source': row.source,
                'document_type': row.document_type,
                'distance': float(row.distance)
            })
        
        return results
    
    def add_scenario_embedding(self, scenario_id, scenario_text):
        """Add or update embedding for a scenario."""
        # Generate embedding
        embedding = self.embedding_model.embed_query(scenario_text)
        
        # Check if embedding exists
        existing = self.session.query(ScenarioEmbedding).filter_by(scenario_id=scenario_id).first()
        
        if existing:
            # Update existing embedding
            existing.embedding = embedding
            existing.updated_at = func.now()
        else:
            # Create new embedding
            embedding_record = ScenarioEmbedding(
                scenario_id=scenario_id,
                embedding=embedding
            )
            self.session.add(embedding_record)
        
        self.session.commit()
    
    def find_similar_scenarios(self, scenario_text, k=5):
        """Find scenarios similar to the given scenario text."""
        # Generate query embedding
        query_embedding = self.embedding_model.embed_query(scenario_text)
        
        # Query for similar scenarios
        sql_query = """
        SELECT 
            s.id,
            s.name,
            s.description,
            s.world_id,
            se.embedding <-> :query_embedding AS distance
        FROM 
            scenario_embeddings se
        JOIN 
            scenarios s ON se.scenario_id = s.id
        ORDER BY 
            distance
        LIMIT :k
        """
        
        result = self.session.execute(
            text(sql_query), 
            {"query_embedding": query_embedding, "k": k}
        )
        
        # Format results
        results = []
        for row in result:
            results.append({
                'id': row.id,
                'name': row.name,
                'description': row.description,
                'world_id': row.world_id,
                'distance': float(row.distance)
            })
        
        return results
    
    def add_event_embedding(self, event_id, event_text):
        """Add embedding for an event."""
        # Generate embedding
        embedding = self.embedding_model.embed_query(event_text)
        
        # Check if embedding exists
        existing = self.session.query(EventEmbedding).filter_by(event_id=event_id).first()
        
        if existing:
            # Update existing embedding
            existing.embedding = embedding
        else:
            # Create new embedding
            embedding_record = EventEmbedding(
                event_id=event_id,
                embedding=embedding
            )
            self.session.add(embedding_record)
        
        self.session.commit()
    
    def find_similar_events(self, event_text, k=5):
        """Find events similar to the given event text."""
        # Generate query embedding
        query_embedding = self.embedding_model.embed_query(event_text)
        
        # Query for similar events
        sql_query = """
        SELECT 
            e.id,
            e.description,
            e.event_time,
            e.scenario_id,
            ee.embedding <-> :query_embedding AS distance
        FROM 
            event_embeddings ee
        JOIN 
            events e ON ee.event_id = e.id
        ORDER BY 
            distance
        LIMIT :k
        """
        
        result = self.session.execute(
            text(sql_query), 
            {"query_embedding": query_embedding, "k": k}
        )
        
        # Format results
        results = []
        for row in result:
            results.append({
                'id': row.id,
                'description': row.description,
                'event_time': row.event_time,
                'scenario_id': row.scenario_id,
                'distance': float(row.distance)
            })
        
        return results
    
    def close(self):
        """Close the session."""
        self.session.close()
```

### 2. Integration with LangChain Retriever

```python
from langchain.retrievers import BaseRetriever
from langchain.schema import Document as LangchainDocument
from typing import List

class PgVectorRetriever(BaseRetriever):
    def __init__(self, vector_store, filter_criteria=None):
        """Initialize the retriever with a PgVectorStore."""
        self.vector_store = vector_store
        self.filter_criteria = filter_criteria
    
    def get_relevant_documents(self, query: str) -> List[LangchainDocument]:
        """Get documents relevant to the query."""
        results = self.vector_store.similarity_search(
            query=query,
            k=5,
            filter_criteria=self.filter_criteria
        )
        
        # Convert to LangChain documents
        documents = []
        for result in results:
            doc = LangchainDocument(
                page_content=result['chunk_text'],
                metadata={
                    'title': result['title'],
                    'source': result['source'],
                    'document_type': result['document_type'],
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
    def __init__(self, llm_service, vector_store):
        """Initialize the enhanced decision engine with a vector store."""
        super().__init__(llm_service)
        self.vector_store = vector_store
        self.retriever = PgVectorRetriever(vector_store)
    
    def evaluate_decision(self, decision, scenario, character, guidelines=None):
        """Evaluate a decision with relevant guidelines retrieved from vector store."""
        # Construct query from decision and scenario
        query = f"Decision: {decision.description}. Scenario: {scenario.description}."
        
        # Set filter criteria for the world
        self.retriever.filter_criteria = {'world_id': scenario.world_id}
        
        # Retrieve relevant guidelines
        relevant_docs = self.retriever.get_relevant_documents(query)
        
        # Extract guideline texts
        retrieved_guidelines = [doc.page_content for doc in relevant_docs]
        
        # Combine with any explicitly provided guidelines
        all_guidelines = retrieved_guidelines
        if guidelines:
            all_guidelines.extend(guidelines)
        
        # Use the combined guidelines for evaluation
        return super().evaluate_decision_with_guidelines(
            decision, scenario, character, all_guidelines
        )
    
    def find_similar_scenarios(self, scenario):
        """Find scenarios similar to the given scenario."""
        scenario_text = f"{scenario.name}: {scenario.description}"
        return self.vector_store.find_similar_scenarios(scenario_text)
    
    def find_similar_events(self, event):
        """Find events similar to the given event."""
        event_text = event.description
        return self.vector_store.find_similar_events(event_text)
```

## Database Migration

### 1. Alembic Migration Script

```python
"""Add pgvector tables

Revision ID: abc123def456
Revises: previous_revision_id
Create Date: 2025-03-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = 'abc123def456'
down_revision = 'previous_revision_id'
branch_labels = None
depends_on = None

def upgrade():
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Create documents table
    op.create_table('documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('source', sa.Text(), nullable=True),
        sa.Column('document_type', sa.Text(), nullable=False),
        sa.Column('world_id', sa.Integer(), nullable=True),
        sa.Column('file_path', sa.Text(), nullable=True),
        sa.Column('file_type', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create document_chunks table
    op.create_table('document_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(384), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create scenario_embeddings table
    op.create_table('scenario_embeddings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scenario_id', sa.Integer(), nullable=True),
        sa.Column('embedding', Vector(384), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['scenario_id'], ['scenarios.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create event_embeddings table
    op.create_table('event_embeddings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=True),
        sa.Column('embedding', Vector(384), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for similarity search
    op.execute('CREATE INDEX ON document_chunks USING ivfflat (embedding vector_cosine_ops)')
    op.execute('CREATE INDEX ON scenario_embeddings USING ivfflat (embedding vector_cosine_ops)')
    op.execute('CREATE INDEX ON event_embeddings USING ivfflat (embedding vector_cosine_ops)')

def downgrade():
    # Drop tables
    op.drop_table('event_embeddings')
    op.drop_table('scenario_embeddings')
    op.drop_table('document_chunks')
    op.drop_table('documents')
    
    # We don't drop the pgvector extension as it might be used by other applications
```

## Flask Routes for Document Management

### 1. Document Upload and Management

```python
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os
from app.models import Document, World
from app import db
from app.services.embedding_service import EmbeddingService

document_bp = Blueprint('documents', __name__, url_prefix='/api/documents')

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt', 'html'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@document_bp.route('', methods=['POST'])
def upload_document():
    """Upload a document and process it for embeddings."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if not file or not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed"}), 400
    
    # Get form data
    title = request.form.get('title')
    document_type = request.form.get('document_type')
    world_id = request.form.get('world_id')
    source = request.form.get('source')
    
    if not title or not document_type:
        return jsonify({"error": "Title and document type are required"}), 400
    
    # Validate world_id if provided
    if world_id:
        world = World.query.get(world_id)
        if not world:
            return jsonify({"error": f"World with ID {world_id} not found"}), 404
    
    # Save file
    filename = secure_filename(file.filename)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)
    
    # Get file type
    file_type = filename.rsplit('.', 1)[1].lower()
    
    # Create document record
    document = Document(
        title=title,
        document_type=document_type,
        world_id=world_id,
        source=source,
        file_path=file_path,
        file_type=file_type
    )
    
    db.session.add(document)
    db.session.commit()
    
    # Process document in background (could use Celery or similar)
    embedding_service = EmbeddingService()
    embedding_service.process_document(document.id)
    
    return jsonify({
        "message": "Document uploaded successfully",
        "document_id": document.id,
        "title": document.title
    }), 201

@document_bp.route('', methods=['GET'])
def get_documents():
    """Get all documents, optionally filtered by world_id or document_type."""
    world_id = request.args.get('world_id')
    document_type = request.args.get('document_type')
    
    query = Document.query
    
    if world_id:
        query = query.filter_by(world_id=world_id)
    
    if document_type:
        query = query.filter_by(document_type=document_type)
    
    documents = query.all()
    
    result = []
    for doc in documents:
        result.append({
            "id": doc.id,
            "title": doc.title,
            "document_type": doc.document_type,
            "source": doc.source,
            "world_id": doc.world_id,
            "file_type": doc.file_type,
            "created_at": doc.created_at.isoformat() if doc.created_at else None
        })
    
    return jsonify(result)

@document_bp.route('/<int:document_id>', methods=['GET'])
def get_document(document_id):
    """Get a specific document by ID."""
    document = Document.query.get_or_404(document_id)
    
    return jsonify({
        "id": document.id,
        "title": document.title,
        "document_type": document.document_type,
        "source": document.source,
        "world_id": document.world_id,
        "file_type": document.file_type,
        "file_path": document.file_path,
        "content": document.content,
        "metadata": document.metadata,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None
    })

@document_bp.route('/<int:document_id>', methods=['DELETE'])
def delete_document(document_id):
    """Delete a document by ID."""
    document = Document.query.get_or_404(document_id)
    
    # Delete the file if it exists
    if document.file_path and os.path.exists(document.file_path):
        os.remove(document.file_path)
    
    db.session.delete(document)
    db.session.commit()
    
    return jsonify({"message": f"Document {document_id} deleted successfully"})

@document_bp.route('/search', methods=['POST'])
def search_documents():
    """Search for documents using vector similarity."""
    data = request.json
    
    if not data or 'query' not in data:
        return jsonify({"error": "Query is required"}), 400
    
    query = data['query']
    world_id = data.get('world_id')
    document_type = data.get('document_type')
    limit = data.get('limit', 5)
    
    # Create filter criteria
    filter_criteria = {}
    if world_id:
        filter_criteria['world_id'] = world_id
    if document_type:
        filter_criteria['document_type'] = document_type
    
    # Get embedding service
    embedding_service = EmbeddingService()
    
    # Search for similar documents
    results = embedding_service.search_documents(query, limit, filter_criteria)
    
    return jsonify(results)
```

### 2. Embedding Service

```python
from app.models import Document, DocumentChunk
from app import db
from sentence_transformers import SentenceTransformer
import numpy as np
from sqlalchemy import text
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
    UnstructuredHTMLLoader
)

class EmbeddingService:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        """Initialize the embedding service with the specified model."""
        self.model = SentenceTransformer(model_name)
    
    def process_document(self, document_id):
        """Process a document: extract text, generate embeddings, and store chunks."""
        document = Document.query.get(document_id)
        if not document:
            raise ValueError(f"Document with ID {document_id} not found")
        
        # Extract text from file
        text = self._extract_text(document.file_path, document.file_type)
        
        # Update document with extracted text
        document.content = text
        db.session.commit()
        
        # Split text into chunks
        chunks = self._split_text(text)
        
        # Generate embeddings for chunks
        embeddings = self.embed_documents([chunk for chunk in chunks])
        
        # Store chunks with embeddings
        self._store_chunks(document_id, chunks, embeddings)
    
    def _extract_text(self, file_path, file_type):
        """Extract text from a file based on its type."""
        if file_type == 'pdf':
            loader = PyPDFLoader(file_path)
        elif file_type == 'docx':
            loader = Docx2txtLoader(file_path)
        elif file_type == 'txt':
            loader = TextLoader(file_path)
        elif file_type == 'html':
            loader = UnstructuredHTMLLoader(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        documents = loader.load()
        return "\n\n".join(doc.page_content for doc in documents)
    
    def _split_text(self, text, chunk_size=1000, chunk_overlap=200):
        """Split text into chunks with overlap."""
        if not text:
            return []
            
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = min(start + chunk_size, text_length)
            
            # Try to find a good breaking point
            if end < text_length:
                # Look for a period or newline within the last 20% of the chunk
                search_start = max(start + int(chunk_size * 0.8), start)
                break_point = text.rfind('. ', search_start, end)
                if break_point == -1:
                    break_point = text.rfind('\n', search_start, end)
                
                if break_point != -1:
                    end = break_point + 1  # Include the period
            
            chunks.append(text[start:end])
            start = end - chunk_overlap
        
        return chunks
    
    def embed_documents(self, texts):
        """Generate embeddings for a list of texts."""
        return self.model.encode(texts, convert_to_numpy=True).tolist()
    
    def embed_query(self
