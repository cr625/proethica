import os
import numpy as np
from typing import List, Dict, Any, Union, Optional
import requests
import json
from sqlalchemy import text
import io

class EmbeddingService:
    """
    Service for generating and managing embeddings for RDF triples.
    Supports using local or remote embedding models with configurable provider priority.
    """
    
    def __init__(self, model_name=None, embedding_dimension=None):
        """
        Initialize the embedding service.
        
        Args:
            model_name: The name of the local embedding model to use (defaults to env var or 'all-MiniLM-L6-v2')
            embedding_dimension: The dimension of the embedding vectors (determined by model)
        """
        # Configuration from environment or default values
        self.model_name = model_name or os.environ.get("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        
        # Provider priority (configurable through environment)
        self.provider_priority = os.environ.get(
            "EMBEDDING_PROVIDER_PRIORITY", 
            "local,claude,openai"
        ).lower().split(',')
        
        # Model dimensions (these will be used if embeddings need to be generated from scratch)
        self.dimensions = {
            "local": embedding_dimension or 384,  # Default for all-MiniLM-L6-v2
            "claude": 1024,  # Claude embedding dimension
            "openai": 1536   # OpenAI ada-002 dimension
        }
        
        # Default dimension based on first provider in priority
        for provider in self.provider_priority:
            if provider in self.dimensions:
                self.embedding_dimension = self.dimensions[provider]
                break
        else:
            self.embedding_dimension = embedding_dimension or 384  # Fallback
        
        # Provider setup and validation
        self.providers = {}
        self._setup_providers()
        
    def _extract_text(self, file_path: str, file_type: str) -> str:
        """
        Extract text from a file based on its type.
        
        Args:
            file_path: Path to the file
            file_type: Type of the file (pdf, docx, txt, html, url)
            
        Returns:
            Extracted text content
        """
        file_type = file_type.lower() if file_type else ''
        
        try:
            # Handle different file types
            if file_type == 'pdf':
                return self._extract_from_pdf(file_path)
            elif file_type == 'docx':
                return self._extract_from_docx(file_path)
            elif file_type in ['txt', 'text']:
                return self._extract_from_txt(file_path)
            elif file_type in ['html', 'htm']:
                return self._extract_from_html(file_path)
            elif file_type == 'url':
                return self._extract_from_url(file_path)  # In this case, file_path would be the URL
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
                
        except Exception as e:
            # Log the error and re-raise
            print(f"Error extracting text from {file_path} ({file_type}): {str(e)}")
            raise
    
    def _extract_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file."""
        try:
            from PyPDF2 import PdfReader
            
            with open(file_path, 'rb') as f:
                reader = PdfReader(f)
                text = ""
                
                # Extract text from each page
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n\n"
                
                return text.strip()
        except ImportError:
            raise ImportError("PyPDF2 is required for PDF text extraction. Install it with 'pip install PyPDF2'")
    
    def _extract_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX file."""
        try:
            import docx
            
            doc = docx.Document(file_path)
            text = ""
            
            # Extract text from paragraphs
            for para in doc.paragraphs:
                if para.text:
                    text += para.text + "\n"
            
            # Extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text:
                            text += cell.text + " "
                    text += "\n"
            
            return text.strip()
        except ImportError:
            raise ImportError("python-docx is required for DOCX text extraction. Install it with 'pip install python-docx'")
    
    def _extract_from_txt(self, file_path: str) -> str:
        """Extract text from TXT file."""
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    
    def _extract_from_html(self, file_path: str) -> str:
        """Extract text from HTML file."""
        try:
            from bs4 import BeautifulSoup
            
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.extract()
                
                # Get text
                text = soup.get_text()
                
                # Break into lines and remove leading and trailing space on each
                lines = (line.strip() for line in text.splitlines())
                
                # Break multi-headlines into a line each
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                
                # Drop blank lines
                text = '\n'.join(chunk for chunk in chunks if chunk)
                
                return text
        except ImportError:
            raise ImportError("BeautifulSoup4 is required for HTML text extraction. Install it with 'pip install beautifulsoup4'")
    
    def _extract_from_url(self, url: str) -> str:
        """Extract text from a URL."""
        try:
            from bs4 import BeautifulSoup
            
            # Fetch URL content
            response = requests.get(url)
            response.raise_for_status()
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.extract()
            
            # Get text
            text = soup.get_text()
            
            # Process similar to HTML extraction
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return text
        except ImportError:
            raise ImportError("BeautifulSoup4 is required for URL text extraction. Install it with 'pip install beautifulsoup4'")
        except requests.RequestException as e:
            raise ValueError(f"Error fetching URL {url}: {str(e)}")
    
    def _setup_providers(self):
        """Initialize and validate all configured providers."""
        # Local model setup
        if "local" in self.provider_priority:
            try:
                from sentence_transformers import SentenceTransformer
                self.providers["local"] = {
                    "model": SentenceTransformer(self.model_name),
                    "available": True,
                    "dimension": self.dimensions["local"]
                }
                print(f"Local embedding provider ready: {self.model_name}")
            except Exception as e:
                print(f"Local embedding provider unavailable: {str(e)}")
                self.providers["local"] = {"available": False}
        
        # Claude API setup
        if "claude" in self.provider_priority:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key and not api_key.startswith("your-") and len(api_key) > 20:
                self.providers["claude"] = {
                    "api_key": api_key,
                    "available": True,
                    "model": os.environ.get("CLAUDE_EMBEDDING_MODEL", "claude-3-embedding-3-0"),
                    "dimension": self.dimensions["claude"],
                    "api_base": os.environ.get("ANTHROPIC_API_BASE", "https://api.anthropic.com/v1")
                }
                print(f"Claude embedding provider ready: {self.providers['claude']['model']} (API key: {api_key[:5]}...{api_key[-4:]})")
            else:
                print(f"Claude embedding provider unavailable: Invalid API key [{api_key[:5] if api_key else 'None'}...]")
                self.providers["claude"] = {"available": False}
        
        # OpenAI API setup
        if "openai" in self.provider_priority:
            # Get API key from .env file - read the actual .env variable
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key and not api_key.startswith("your-") and len(api_key) > 20:
                self.providers["openai"] = {
                    "api_key": api_key,
                    "available": True,
                    "api_base": os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1"),
                    "model": os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002"),
                    "dimension": self.dimensions["openai"]
                }
                print(f"OpenAI embedding provider ready: {self.providers['openai']['model']} (API key: {api_key[:5]}...{api_key[-4:]})")
            else:
                print(f"OpenAI embedding provider unavailable: Invalid API key [{api_key[:5] if api_key else 'None'}...]")
                self.providers["openai"] = {"available": False}
                
    def get_embedding(self, text: str) -> List[float]:
        """
        Get an embedding for a text string using configured provider priority.
        
        Args:
            text: The text to embed
            
        Returns:
            A list of floats representing the embedding vector
        """
        if not text:
            # Return a zero vector if text is empty
            return [0.0] * self.embedding_dimension
        
        # Try each provider in priority order
        for provider in self.provider_priority:
            if provider not in self.providers or not self.providers[provider]["available"]:
                continue
                
            try:
                if provider == "local":
                    embedding = self._get_local_embedding(text)
                    self.embedding_dimension = len(embedding)  # Update dimension based on result
                    return embedding
                elif provider == "claude":
                    embedding = self._get_claude_embedding(text)
                    self.embedding_dimension = len(embedding)  # Update dimension based on result
                    return embedding
                elif provider == "openai":
                    embedding = self._get_openai_embedding(text)
                    self.embedding_dimension = len(embedding)  # Update dimension based on result
                    return embedding
            except Exception as e:
                print(f"Error using {provider} embeddings: {str(e)}")
                continue
        
        # Fallback to random if all providers fail
        print("Warning: All embedding providers failed. Using random embeddings.")
        return self._get_random_embedding()
    
    def _get_local_embedding(self, text: str) -> List[float]:
        """Get embedding from local sentence-transformers model."""
        embedding = self.providers["local"]["model"].encode(text)
        return embedding.tolist()

    def _get_claude_embedding(self, text: str) -> List[float]:
        """Get embedding from Claude API."""
        # Claude's API version for embeddings
        # Try the documented approach first (may change over time)
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.providers["claude"]["api_key"],
            "anthropic-version": "2023-06-01"  # API version may change
        }
        
        # Standard format for the request
        data = {
            "model": self.providers["claude"]["model"],
            "input": text
        }
        
        api_base = self.providers["claude"]["api_base"]
        
        # Try the v1 embeddings endpoint
        embeddings_endpoint = f"{api_base.rstrip('/')}/embeddings"
        
        try:
            print(f"Using Claude embeddings API: {embeddings_endpoint}")
            response = requests.post(
                embeddings_endpoint,
                headers=headers, 
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                # Check if the response has the expected structure
                if "embedding" in result:
                    return result["embedding"]
                elif "embeddings" in result and len(result["embeddings"]) > 0:
                    return result["embeddings"][0]
                else:
                    raise Exception(f"Unexpected response format: {result}")
                    
            # Try alternative API path if first attempt fails with 404
            elif response.status_code == 404:
                # Alternative v2 endpoint
                print("Original endpoint not found, trying alternative API version...")
                headers["anthropic-version"] = "2023-01-01"  # Try a different API version
                alt_endpoint = f"{api_base.rstrip('/')}/v1/embeddings"
                
                alt_response = requests.post(
                    alt_endpoint,
                    headers=headers, 
                    json=data
                )
                
                if alt_response.status_code == 200:
                    result = alt_response.json()
                    if "embedding" in result:
                        return result["embedding"]
                    elif "embeddings" in result and len(result["embeddings"]) > 0:
                        return result["embeddings"][0]
                
                # If that also fails, use the Claude completion API to get embeddings
                print("Embeddings API unavailable. Falling back to simulated embedding...")
                return self._get_random_embedding()  # Fall back to random for now
            
            # Other errors
            raise Exception(f"Claude API error: {response.status_code} {response.text}")
        except Exception as e:
            print(f"Claude embedding API error: {str(e)}")
            raise

    def _get_openai_embedding(self, text: str) -> List[float]:
        """Get an embedding from OpenAI API."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.providers['openai']['api_key']}"
        }
        
        data = {
            "input": text,
            "model": self.providers["openai"]["model"]
        }
        
        response = requests.post(
            f"{self.providers['openai']['api_base']}/embeddings", 
            headers=headers, 
            json=data
        )
        
        if response.status_code != 200:
            raise Exception(f"OpenAI API error: {response.status_code} {response.text}")
        
        result = response.json()
        return result["data"][0]["embedding"]
    
    def _get_random_embedding(self) -> List[float]:
        """Generate a random embedding for testing purposes."""
        random_vector = np.random.randn(self.embedding_dimension)
        # Normalize the vector to unit length
        normalized = random_vector / np.linalg.norm(random_vector)
        return normalized.tolist()
    
    def generate_triple_embeddings(self, triple) -> Dict[str, List[float]]:
        """
        Generate embeddings for the subject, predicate, and object of a triple.
        
        Args:
            triple: The Triple object to generate embeddings for
            
        Returns:
            Dictionary with embeddings for subject, predicate, and object
        """
        # Generate embeddings
        subject_embedding = self.get_embedding(triple.subject)
        predicate_embedding = self.get_embedding(triple.predicate)
        
        # Object could be literal or URI
        object_text = triple.object_literal if triple.is_literal else triple.object_uri
        object_embedding = self.get_embedding(object_text)
        
        return {
            "subject_embedding": subject_embedding,
            "predicate_embedding": predicate_embedding,
            "object_embedding": object_embedding
        }
    
    def update_triple_embeddings(self, triple, commit: bool = True):
        """
        Update the embeddings for a triple.
        
        Args:
            triple: The Triple object to update embeddings for
            commit: Whether to commit the session after update
            
        Returns:
            The updated Triple object
        """
        from app import db
        
        embeddings = self.generate_triple_embeddings(triple)
        
        # Update the triple
        triple.subject_embedding = embeddings["subject_embedding"]
        triple.predicate_embedding = embeddings["predicate_embedding"]
        triple.object_embedding = embeddings["object_embedding"]
        
        if commit:
            db.session.commit()
        
        return triple
    
    def batch_update_embeddings(self, triple_ids: List[int] = None, limit: int = 100):
        """
        Update embeddings for multiple triples in batch.
        
        Args:
            triple_ids: Optional list of triple IDs to update. If None, update all triples.
            limit: Maximum number of triples to update at once
            
        Returns:
            Number of triples updated
        """
        from app import db
        from app.models.triple import Triple
        
        query = db.session.query(Triple)
        
        # Filter by IDs if provided
        if triple_ids:
            query = query.filter(Triple.id.in_(triple_ids))
        
        # Filter triples with missing embeddings
        query = query.filter(Triple.subject_embedding.is_(None))
        
        # Limit the batch size
        query = query.limit(limit)
        
        triples = query.all()
        
        print(f"Updating embeddings for {len(triples)} triples...")
        
        for triple in triples:
            self.update_triple_embeddings(triple, commit=False)
        
        db.session.commit()
        
        return len(triples)
    
    def find_similar_triples(self, text: str, field: str = "subject", limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find triples with similar embeddings to the given text.
        
        Args:
            text: The text to find similar triples for
            field: Which field to search (subject, predicate, object)
            limit: Maximum number of results to return
            
        Returns:
            List of (triple, similarity) tuples
        """
        from app import db
        
        # Generate embedding for the query text
        embedding = self.get_embedding(text)
        
        # Determine which embedding field to search
        if field == "subject":
            embedding_field = "subject_embedding"
        elif field == "predicate":
            embedding_field = "predicate_embedding"
        elif field == "object":
            embedding_field = "object_embedding"
        else:
            raise ValueError(f"Invalid field: {field}")
        
        # Convert the embedding to a string representation for SQL
        embedding_str = f"[{','.join(str(x) for x in embedding)}]"
        
        # Query for similar triples
        query = f"""
        SELECT 
            id,
            subject,
            predicate, 
            object_literal,
            object_uri,
            is_literal,
            {embedding_field} <-> '{embedding_str}'::vector AS distance
        FROM 
            character_triples
        WHERE 
            {embedding_field} IS NOT NULL
        ORDER BY 
            distance
        LIMIT {limit}
        """
        
        result = db.session.execute(text(query))
        
        # Format results
        similar_triples = []
        for row in result:
            object_value = row.object_literal if row.is_literal else row.object_uri
            similar_triples.append({
                "id": row.id,
                "subject": row.subject,
                "predicate": row.predicate,
                "object": object_value,
                "is_literal": row.is_literal,
                "similarity": 1.0 - row.distance
            })
        
        return similar_triples
    
    def _split_text(self, text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
        """
        Split text into smaller chunks for processing.
        
        Args:
            text: The text to split
            chunk_size: Maximum size of each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
            
        Returns:
            List of text chunks
        """
        if not text:
            return []
        
        # Simple paragraph-based chunking
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
                
            # If adding this paragraph would exceed chunk size, store current chunk and start a new one
            if len(current_chunk) + len(paragraph) > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                # Include overlap from the end of previous chunk
                if len(current_chunk) > chunk_overlap:
                    current_chunk = current_chunk[-chunk_overlap:] + "\n\n" + paragraph
                else:
                    current_chunk = paragraph
            else:
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
        
        # Add the last chunk if it's not empty
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def embed_documents(self, chunks: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of text chunks.
        
        Args:
            chunks: List of text chunks to embed
            
        Returns:
            List of embedding vectors
        """
        embeddings = []
        
        print(f"Generating embeddings for {len(chunks)} chunks...")
        
        for chunk in chunks:
            try:
                embedding = self.get_embedding(chunk)
                embeddings.append(embedding)
            except Exception as e:
                print(f"Error generating embedding for chunk: {str(e)}")
                # Use zero vector as fallback for failed embeddings
                embeddings.append([0.0] * self.embedding_dimension)
        
        return embeddings
    
    def _store_chunks(self, document_id: int, chunks: List[str], embeddings: List[List[float]]) -> int:
        """
        Store document chunks with their embeddings in the database.
        
        Args:
            document_id: ID of the document these chunks belong to
            chunks: List of text chunks
            embeddings: List of embedding vectors corresponding to chunks
            
        Returns:
            Number of chunks stored
        """
        from app import db
        from app.models.document import DocumentChunk
        
        # Make sure we have the same number of chunks and embeddings
        if len(chunks) != len(embeddings):
            raise ValueError(f"Number of chunks ({len(chunks)}) does not match number of embeddings ({len(embeddings)})")
        
        # Delete existing chunks for this document
        existing_chunks = DocumentChunk.query.filter_by(document_id=document_id).all()
        for chunk in existing_chunks:
            db.session.delete(chunk)
        
        # Store new chunks
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            chunk = DocumentChunk(
                document_id=document_id,
                chunk_index=i,
                chunk_text=chunk_text,
                embedding=embedding,
                chunk_metadata={"position": i}
            )
            db.session.add(chunk)
        
        db.session.commit()
        return len(chunks)
    
    def process_url(self, url: str, title: str, document_type: str, world_id: int) -> int:
        """
        Process a URL into a document with embeddings.
        
        Args:
            url: The URL to process
            title: Title for the document
            document_type: Type of document (guideline, case_study, etc.)
            world_id: ID of the world this document belongs to
            
        Returns:
            ID of the created document
        """
        from app import db
        from app.models.document import Document, PROCESSING_STATUS
        
        # Create document record
        document = Document(
            title=title,
            document_type=document_type,
            world_id=world_id,
            source=url,
            file_type="url",
            doc_metadata={},
            processing_status=PROCESSING_STATUS['PROCESSING']
        )
        db.session.add(document)
        db.session.commit()
        
        try:
            # Extract text from URL
            text = self._extract_from_url(url)
            document.content = text
            
            # Split text into chunks
            chunks = self._split_text(text)
            
            # Generate embeddings
            embeddings = self.embed_documents(chunks)
            
            # Store chunks with embeddings
            self._store_chunks(document.id, chunks, embeddings)
            
            # Update document status
            document.processing_status = PROCESSING_STATUS['COMPLETED']
            document.processing_progress = 100
            db.session.commit()
            
            return document.id
            
        except Exception as e:
            # Update document status to failed
            document.processing_status = PROCESSING_STATUS['FAILED']
            document.processing_error = str(e)
            db.session.commit()
            
            # Re-raise the exception
            raise
