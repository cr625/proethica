"""
Embedding Service for processing documents and performing vector similarity search.
This service uses Sentence-Transformers to generate embeddings for document chunks.
"""

import os
import re
from typing import List, Dict, Any, Optional, Tuple
import logging

from sentence_transformers import SentenceTransformer
from sqlalchemy import text
import PyPDF2
from docx import Document as DocxDocument
from bs4 import BeautifulSoup
import requests
from flask import current_app

# Import models directly to avoid circular imports
from app.models.document import Document, DocumentChunk, VECTOR_AVAILABLE
import json

# Set up logging
logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for processing documents and generating embeddings."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize the embedding service with the specified model."""
        try:
            self.model = SentenceTransformer(model_name)
            self.embedding_size = self.model.get_sentence_embedding_dimension()
            logger.info(f"Initialized embedding model: {model_name} with dimension {self.embedding_size}")
        except Exception as e:
            logger.error(f"Error initializing embedding model: {str(e)}")
            raise
    
    def process_document(self, document_id: int) -> None:
        """Process a document: extract text, generate embeddings, and store chunks."""
        try:
            document = Document.query.get(document_id)
            if not document:
                raise ValueError(f"Document with ID {document_id} not found")
            
            # Extract text from file
            logger.info(f"Extracting text from document: {document.title} (ID: {document_id})")
            text = self._extract_text(document.file_path, document.file_type)
            
            # Update document with extracted text
            document.content = text
            from app import db
            db.session.commit()
            
            # Split text into chunks
            logger.info(f"Splitting document into chunks")
            chunks = self._split_text(text)
            
            # Generate embeddings for chunks
            logger.info(f"Generating embeddings for {len(chunks)} chunks")
            embeddings = self.embed_documents(chunks)
            
            # Store chunks with embeddings
            logger.info(f"Storing chunks with embeddings")
            self._store_chunks(document_id, chunks, embeddings)
            
            logger.info(f"Document processing completed: {document.title} (ID: {document_id})")
        except Exception as e:
            logger.error(f"Error processing document {document_id}: {str(e)}")
            raise
    
    def _extract_text(self, file_path: str, file_type: str) -> str:
        """Extract text from a file based on its type."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_type = file_type.lower() if file_type else ""
        
        try:
            if file_type == 'pdf':
                return self._extract_text_from_pdf(file_path)
            elif file_type in ['docx', 'doc']:
                return self._extract_text_from_docx(file_path)
            elif file_type == 'txt':
                return self._extract_text_from_txt(file_path)
            elif file_type in ['html', 'htm']:
                return self._extract_text_from_html(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {str(e)}")
            raise
    
    def _extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from a PDF file."""
        text = ""
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n\n"
        return text
    
    def _extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from a DOCX file."""
        doc = DocxDocument(file_path)
        return "\n\n".join([paragraph.text for paragraph in doc.paragraphs])
    
    def _extract_text_from_txt(self, file_path: str) -> str:
        """Extract text from a TXT file."""
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    
    def _extract_text_from_html(self, file_path: str) -> str:
        """Extract text from an HTML file."""
        with open(file_path, 'r', encoding='utf-8') as file:
            soup = BeautifulSoup(file, 'html.parser')
            return soup.get_text(separator="\n\n")
    
    def _extract_text_from_url(self, url: str) -> str:
        """Extract text from a URL."""
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.get_text(separator="\n\n")
    
    def _split_text(self, text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
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
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        try:
            return self.model.encode(texts, convert_to_numpy=True).tolist()
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise
    
    def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a query."""
        try:
            return self.model.encode(text, convert_to_numpy=True).tolist()
        except Exception as e:
            logger.error(f"Error generating query embedding: {str(e)}")
            raise
    
    def _store_chunks(self, document_id: int, chunks: List[str], embeddings: List[List[float]]) -> None:
        """Store text chunks with their embeddings."""
        try:
            # Get db
            from app import db
            
            # Delete existing chunks for this document
            DocumentChunk.query.filter_by(document_id=document_id).delete()
            
            # Create new chunks
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                # Always store embedding as JSON string
                chunk_record = DocumentChunk(
                    document_id=document_id,
                    chunk_index=i,
                    chunk_text=chunk,
                    embedding=json.dumps(embedding),
                    chunk_metadata={"index": i}
                )
                db.session.add(chunk_record)
            
            db.session.commit()
            logger.info(f"Stored {len(chunks)} chunks for document {document_id}")
        except Exception as e:
            from app import db
            db.session.rollback()
            logger.error(f"Error storing chunks: {str(e)}")
            raise
    
    def search_similar_chunks(self, query: str, k: int = 5, world_id: Optional[int] = None, 
                             document_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for chunks similar to the query."""
        try:
            # Generate query embedding
            query_embedding = self.embed_query(query)
            
            # Get db
            from app import db
            
            if VECTOR_AVAILABLE:
                # Use pgvector for similarity search
                # Build base query
                sql_query = """
                SELECT 
                    dc.id,
                    dc.chunk_text, 
                    dc.chunk_metadata as metadata,
                    d.title,
                    d.source,
                    d.document_type,
                    d.world_id,
                    dc.embedding <-> :query_embedding AS distance
                FROM 
                    document_chunks dc
                JOIN 
                    documents d ON dc.document_id = d.id
                """
                
                # Add filters if provided
                where_clauses = []
                params = {"query_embedding": query_embedding}
                
                if world_id:
                    where_clauses.append("d.world_id = :world_id")
                    params['world_id'] = world_id
                
                if document_type:
                    where_clauses.append("d.document_type = :document_type")
                    params['document_type'] = document_type
                
                if where_clauses:
                    sql_query += " WHERE " + " AND ".join(where_clauses)
                
                # Add ordering and limit
                sql_query += """
                ORDER BY distance
                LIMIT :k
                """
                params['k'] = k
                
                # Execute query
                result = db.session.execute(text(sql_query), params)
                
                # Format results
                results = []
                for row in result:
                    results.append({
                        'id': row.id,
                        'chunk_text': row.chunk_text,
                        'metadata': row.metadata,
                        'title': row.title,
                        'source': row.source,
                        'document_type': row.document_type,
                        'world_id': row.world_id,
                        'distance': float(row.distance)
                    })
            else:
                # Fallback to manual similarity search when pgvector not available
                logger.warning("pgvector not available, using fallback similarity search")
                
                # Build query to get chunks
                sql_query = """
                SELECT 
                    dc.id,
                    dc.chunk_text, 
                    dc.embedding,
                    dc.chunk_metadata as metadata,
                    d.title,
                    d.source,
                    d.document_type,
                    d.world_id
                FROM 
                    document_chunks dc
                JOIN 
                    documents d ON dc.document_id = d.id
                """
                
                # Add filters if provided
                where_clauses = []
                params = {}
                
                if world_id:
                    where_clauses.append("d.world_id = :world_id")
                    params['world_id'] = world_id
                
                if document_type:
                    where_clauses.append("d.document_type = :document_type")
                    params['document_type'] = document_type
                
                if where_clauses:
                    sql_query += " WHERE " + " AND ".join(where_clauses)
                
                # Execute query
                result = db.session.execute(text(sql_query), params)
                
                # Calculate distances manually
                chunks_with_distances = []
                for row in result:
                    # Parse embedding from JSON string
                    chunk_embedding = json.loads(row.embedding)
                    
                    # Calculate cosine distance
                    distance = self._cosine_distance(query_embedding, chunk_embedding)
                    
                    chunks_with_distances.append({
                        'id': row.id,
                        'chunk_text': row.chunk_text,
                        'metadata': row.metadata,
                        'title': row.title,
                        'source': row.source,
                        'document_type': row.document_type,
                        'world_id': row.world_id,
                        'distance': distance
                    })
                
                # Sort by distance and take top k
                chunks_with_distances.sort(key=lambda x: x['distance'])
                results = chunks_with_distances[:k]
            
            logger.info(f"Found {len(results)} similar chunks for query")
            return results
        except Exception as e:
            logger.error(f"Error searching similar chunks: {str(e)}")
            raise
    
    def _cosine_distance(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine distance between two vectors."""
        import numpy as np
        from numpy.linalg import norm
        
        # Convert to numpy arrays
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        
        # Calculate cosine similarity
        cos_sim = np.dot(vec1, vec2) / (norm(vec1) * norm(vec2))
        
        # Convert to distance (1 - similarity)
        return 1.0 - cos_sim
    
    def process_url(self, url: str, title: str, document_type: str, world_id: Optional[int] = None) -> int:
        """Process a URL: extract text, generate embeddings, and store chunks."""
        try:
            # Extract text from URL
            logger.info(f"Extracting text from URL: {url}")
            text = self._extract_text_from_url(url)
            
            # Get db
            from app import db
            
            # Create document record
            document = Document(
                title=title,
                source=url,
                document_type=document_type,
                world_id=world_id,
                content=text,
                file_type='html',
                doc_metadata={}  # Initialize with empty metadata
            )
            db.session.add(document)
            db.session.flush()  # Get document ID
            
            # Split text into chunks
            logger.info(f"Splitting document into chunks")
            chunks = self._split_text(text)
            
            # Generate embeddings for chunks
            logger.info(f"Generating embeddings for {len(chunks)} chunks")
            embeddings = self.embed_documents(chunks)
            
            # Store chunks with embeddings
            logger.info(f"Storing chunks with embeddings")
            self._store_chunks(document.id, chunks, embeddings)
            
            db.session.commit()
            logger.info(f"URL processing completed: {url}")
            
            return document.id
        except Exception as e:
            from app import db
            db.session.rollback()
            logger.error(f"Error processing URL {url}: {str(e)}")
            raise
