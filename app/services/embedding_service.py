import os
import numpy as np
from typing import List, Dict, Any, Union, Optional
import requests
import json
from sqlalchemy import text
import io
import logging

# Set up logging
logger = logging.getLogger(__name__)


def resolve_embedding_device() -> str:
    """Resolve the device for the local SentenceTransformer model.

    Controlled by the EMBEDDINGS_DEVICE environment variable:
      - "cpu" (default): always use the CPU. The model is small (all-MiniLM-L6-v2),
        CPU is fast enough, and it never fails.
      - "cuda": force the GPU (operator opt-in; trusted as-is).
      - "auto": use the GPU only after verifying a CUDA kernel actually runs.

    The default is CPU on purpose. torch.cuda.is_available() can return True for a GPU
    whose compute capability this torch build has no kernels for; the device then raises
    cudaErrorNoKernelImageForDevice at encode time, which previously left embeddings
    silently ungenerated. Set EMBEDDINGS_DEVICE=cuda or =auto to opt in to the GPU.
    """
    requested = os.environ.get("EMBEDDINGS_DEVICE", "cpu").lower()
    if requested == "cpu":
        return "cpu"
    try:
        import torch
    except Exception:
        return "cpu"
    if requested == "cuda":
        return "cuda"
    # "auto": probe that the GPU can run a real kernel, not just that a device exists.
    if not torch.cuda.is_available():
        return "cpu"
    try:
        torch.zeros(1).to("cuda").add_(1)
        return "cuda"
    except Exception as e:
        logger.warning("EMBEDDINGS_DEVICE=auto: CUDA present but unusable (%s); using CPU", e)
        return "cpu"


class EmbeddingService:
    """
    Service for generating and managing embeddings for RDF triples.
    Supports using local or remote embedding models with configurable provider priority.
    
    This is a singleton class - use EmbeddingService.get_instance() to get the shared instance.
    """
    
    _instance = None  # Singleton instance
    _initialized = False  # Track if instance has been initialized
    
    @classmethod
    def get_instance(cls, model_name=None, embedding_dimension=None):
        """
        Get the singleton instance of EmbeddingService.
        
        Args:
            model_name: The name of the local embedding model to use (only used on first call)
            embedding_dimension: The dimension of the embedding vectors (only used on first call)
            
        Returns:
            The singleton EmbeddingService instance
        """
        if cls._instance is None:
            cls._instance = cls(model_name, embedding_dimension)
        return cls._instance
    
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
        # Determine default priority: if any hosted API key exists, prefer hosted first unless overridden
        any_hosted_key = any([
            bool(os.environ.get("OPENAI_API_KEY")),
            bool(os.environ.get("ANTHROPIC_API_KEY")),
            bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
        ])
        default_priority = "openai,gemini,claude,local" if any_hosted_key else "local,openai,gemini,claude"
        self.provider_priority = os.environ.get(
            "EMBEDDING_PROVIDER_PRIORITY",
            default_priority
        ).lower().split(',')
        
        # Model dimensions (these will be used if embeddings need to be generated from scratch)
        self.dimensions = {
            "local": embedding_dimension or 384,   # all-MiniLM-L6-v2
            "claude": 1024,                       # Claude embeddings
            "openai": 1536,                      # text-embedding-ada-002
            "gemini": 768                        # text-embedding-004
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
        """Extract text from a file based on its type.

        Delegates to `app.services.document_text_extractors`; kept as an
        instance method so existing call sites (case-creation pipeline,
        task_queue) are unchanged.
        """
        from app.services.document_text_extractors import extract_text
        return extract_text(file_path, file_type)

    def _extract_from_url(self, url: str) -> str:
        """Extract text from a URL. Delegates to document_text_extractors."""
        from app.services.document_text_extractors import extract_from_url
        return extract_from_url(url)

    def _setup_providers(self):
        """Initialize and validate all configured providers."""
        # Emit basic diagnostics for priority and switches
        priority_str = ",".join(self.provider_priority)
        disable_local = os.environ.get("DISABLE_LOCAL_EMBEDDINGS", "false").lower() in ("1", "true", "yes")
        # Collect provider status for single line output
        provider_status = []
        # Local model setup
        if "local" in self.provider_priority and not disable_local:
            try:
                from sentence_transformers import SentenceTransformer
                import torch

                # Configure offline mode to avoid HuggingFace Hub requests
                os.environ["HF_HUB_OFFLINE"] = "1"
                os.environ["TRANSFORMERS_OFFLINE"] = "1"
                # Device selection with CPU fallback option
                device = resolve_embedding_device()

                self.providers["local"] = {
                    "model": SentenceTransformer(self.model_name, local_files_only=True, device=device),
                    "available": True,
                    "dimension": self.dimensions["local"],
                    "device": device
                }
                provider_status.append(f"Local:{self.model_name}({device})")
            except Exception as e:
                # If we hit a meta-tensor or device move issue, mark local unavailable and proceed
                err_msg = str(e)
                # Optional fallback: allow one-time download if cache is missing
                allow_dl = os.environ.get("ALLOW_HF_DOWNLOAD", "false").lower() in ("1", "true", "yes")
                tried_download = False
                if allow_dl:
                    try:
                        from sentence_transformers import SentenceTransformer
                        # Reconfigure to allow online download
                        os.environ["HF_HUB_OFFLINE"] = "0"
                        os.environ["TRANSFORMERS_OFFLINE"] = "0"
                        import torch
                        device = resolve_embedding_device()
                        # Silent download attempt
                        model = SentenceTransformer(self.model_name, local_files_only=False, device=device)
                        self.providers["local"] = {
                            "model": model,
                            "available": True,
                            "dimension": self.dimensions["local"],
                            "device": device
                        }
                        provider_status.append(f"Local:{self.model_name}({device})")
                        tried_download = True
                    except Exception as e2:
                        provider_status.append("Local:unavailable")
                if not tried_download:
                    provider_status.append("Local:unavailable")
                    self.providers["local"] = {"available": False, "reason": err_msg}

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
                provider_status.append(f"Claude:ready")
            else:
                provider_status.append(f"Claude:no-key")
                self.providers["claude"] = {"available": False, "reason": "invalid_api_key"}

        # OpenAI API setup
        if "openai" in self.provider_priority:
            # Get API key from .env file - read the actual .env variable
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key and not api_key.startswith("your-") and len(api_key) > 20:
                self.providers["openai"] = {
                    "api_key": api_key,
                    "available": True,
                    "api_base": os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1"),
                    "model": os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
                    "dimension": self.dimensions["openai"]
                }
                provider_status.append(f"OpenAI:ready")
            else:
                provider_status.append(f"OpenAI:no-key")
                self.providers["openai"] = {"available": False, "reason": "invalid_api_key"}

        # Gemini API setup (Google Generative Language API)
        if "gemini" in self.provider_priority:
            gkey = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if gkey and len(gkey) > 20:
                self.providers["gemini"] = {
                    "api_key": gkey,
                    "available": True,
                    "api_base": os.environ.get("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta"),
                    "model": os.environ.get("GEMINI_EMBEDDING_MODEL", "text-embedding-004"),
                    "dimension": self.dimensions["gemini"]
                }
                provider_status.append(f"Gemini:ready")
            else:
                provider_status.append(f"Gemini:no-key")
                self.providers["gemini"] = {"available": False, "reason": "invalid_api_key"}
        
        # Single line status output - only on first initialization
        if not EmbeddingService._initialized:
            logger.info(f"Embedding service initialized: [{', '.join(provider_status)}] Priority: {priority_str}")
            EmbeddingService._initialized = True
                
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
                elif provider == "gemini":
                    embedding = self._get_gemini_embedding(text)
                    self.embedding_dimension = len(embedding)
                    return embedding
            except Exception as e:
                logger.warning(f"Error using {provider} embeddings: {str(e)}")
                continue
        
        # Fallback to random if all providers fail
        try:
            states = {p: (self.providers.get(p, {}).get("available", False)) for p in self.provider_priority}
            reasons = {p: self.providers.get(p, {}).get("reason") for p in self.provider_priority}
            logger.warning(f"All embedding providers failed. Using random embeddings. States={states} Reasons={reasons}")
        except Exception:
            logger.warning("All embedding providers failed. Using random embeddings.")
        return self._get_random_embedding()
    
    def _get_local_embedding(self, text: str) -> List[float]:
        """Get embedding from local sentence-transformers model."""
        model = self.providers["local"]["model"]
        try:
            embedding = model.encode(text)
        except Exception as e:
            # Force CPU fallback if a CUDA-related error occurs
            if "CUDA" in str(e).upper():
                try:
                    from sentence_transformers import SentenceTransformer
                    model_name = self.model_name
                    self.providers["local"]["model"] = SentenceTransformer(model_name, local_files_only=True, device="cpu")
                    logger.warning("Local embedding: CUDA error detected, falling back to CPU")
                    embedding = self.providers["local"]["model"].encode(text)
                except Exception:
                    raise
            else:
                raise
        return embedding.tolist()

    def _get_gemini_embedding(self, text: str) -> List[float]:
        """Get embedding from Google Gemini embeddings API (text-embedding-004)."""
        provider = self.providers.get("gemini", {})
        api_key = provider.get("api_key")
        api_base = provider.get("api_base", "https://generativelanguage.googleapis.com/v1beta")
        model = provider.get("model", "text-embedding-004")
        url = f"{api_base.rstrip('/')}/models/{model}:embedText?key={api_key}"
        payload = {"text": text}
        headers = {"Content-Type": "application/json"}
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        if resp.status_code != 200:
            raise Exception(f"Gemini embeddings error {resp.status_code}: {resp.text}")
        data = resp.json()
        # Response shape: { "embedding": { "value": [floats] } }
        if "embedding" in data and isinstance(data["embedding"], dict) and "value" in data["embedding"]:
            return data["embedding"]["value"]
        # Some SDKs return { "embeddings": [ { "value": [...] } ] }
        if "embeddings" in data and isinstance(data["embeddings"], list) and data["embeddings"]:
            emb = data["embeddings"][0]
            if isinstance(emb, dict) and "value" in emb:
                return emb["value"]
        raise Exception(f"Unexpected Gemini embedding response: {data}")

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
            logger.debug(f"Using Claude embeddings API: {embeddings_endpoint}")
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
                logger.debug("Original endpoint not found, trying alternative API version...")
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
                logger.warning("Embeddings API unavailable. Falling back to simulated embedding...")
                return self._get_random_embedding()  # Fall back to random for now
            
            # Other errors
            raise Exception(f"Claude API error: {response.status_code} {response.text}")
        except Exception as e:
            logger.error(f"Claude embedding API error: {str(e)}")
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
        
        logger.info(f"Updating embeddings for {len(triples)} triples...")
        
        for triple in triples:
            self.update_triple_embeddings(triple, commit=False)
        
        db.session.commit()
        
        return len(triples)
    
    def search_similar_chunks(self, query: str, k: int = 5, world_id: Optional[int] = None, document_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find document chunks similar to the query text.
        
        Args:
            query: The query text to find similar chunks for
            k: Maximum number of results to return
            world_id: Optional world ID to filter chunks by
            document_type: Optional document type to filter by
            
        Returns:
            List of similar document chunks with metadata
        """
        from app import db
        from app.models import Document, DocumentChunk

        # Helper cosine (shared pure-Python implementation)
        from app.services.similarity_utils import cosine_similarity_list as cosine

        # Prefer local 384-dim embedding (matches embedding_384)
        try:
            qvec_384 = self._get_local_embedding(query)
        except Exception:
            qvec_384 = []

        use_db_vector = os.environ.get("USE_DB_VECTOR_SEARCH", "false").lower() in ("1", "true", "yes")
        can_use_db = use_db_vector and len(qvec_384) == 384

        if can_use_db:
            try:
                embedding_str = f"[{','.join(str(x) for x in qvec_384)}]"
                parts = [
                    "SELECT dc.id, dc.content AS chunk_text, dc.chunk_index, d.title, d.document_type,",
                    "dc.embedding_384 <-> (:embedding)::vector AS distance",
                    "FROM document_chunks dc",
                    "JOIN documents d ON dc.document_id = d.id",
                    "WHERE dc.embedding_384 IS NOT NULL",
                ]
                params = {"embedding": embedding_str, "k": k}
                if world_id is not None:
                    parts.append("AND d.world_id = :world_id")
                    params["world_id"] = world_id
                if document_type is not None:
                    parts.append("AND d.document_type = :document_type")
                    params["document_type"] = document_type
                parts.append("ORDER BY distance")
                parts.append("LIMIT :k")
                sql = text(" ".join(parts))
                res = db.session.execute(sql, params)
                out = []
                for row in res:
                    out.append({
                        "id": row.id,
                        "chunk_text": row.chunk_text,
                        "chunk_index": row.chunk_index,
                        "title": row.title,
                        "document_type": row.document_type,
                        "distance": row.distance,
                        "similarity": 1.0 - float(row.distance) if row.distance is not None else 0.0,
                    })
                return out
            except Exception as e:
                try:
                    db.session.rollback()
                except Exception:
                    pass
                logger.warning(f"DB vector search failed, falling back to Python cosine: {e}")

        # Python fallback: support both 384 and legacy embeddings
        # Lazily compute a generic embedding if needed
        qvec_legacy: Optional[List[float]] = None
        q = db.session.query(DocumentChunk, Document).join(Document, DocumentChunk.document_id == Document.id)
        q = q.filter((DocumentChunk.embedding_384.isnot(None)) | (DocumentChunk.embedding.isnot(None)))
        if world_id is not None:
            q = q.filter(Document.world_id == world_id)
        if document_type is not None:
            q = q.filter(Document.document_type == document_type)

        rows = q.all()
        scored: List[Dict[str, Any]] = []
        for dc, d in rows:
            emb = dc.embedding_384 if getattr(dc, "embedding_384", None) is not None else dc.embedding
            if emb is None:
                continue
            if len(emb) == 384 and qvec_384:
                sim = cosine(qvec_384, emb)
            else:
                if qvec_legacy is None:
                    try:
                        qvec_legacy = self.get_embedding(query)
                    except Exception:
                        qvec_legacy = []
                sim = cosine(qvec_legacy or [], emb)
            scored.append({
                "id": dc.id,
                "chunk_text": dc.content,
                "chunk_index": dc.chunk_index,
                "title": d.title,
                "document_type": d.document_type,
                "distance": 1.0 - sim,
                "similarity": sim,
            })

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:k]
    
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
        
        logger.info(f"Generating embeddings for {len(chunks)} chunks...")
        
        for chunk in chunks:
            try:
                embedding = self.get_embedding(chunk)
                embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Error generating embedding for chunk: {str(e)}")
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
                content=chunk_text,
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
        from app.models import Document
        from app.models.document import PROCESSING_STATUS
        
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
