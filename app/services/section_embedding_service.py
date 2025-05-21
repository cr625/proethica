"""
Section Embedding Service - Extension of EmbeddingService for document section embeddings.
Uses the DocumentSection model for storage and retrieval, leveraging pgvector.
"""
import logging
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from .embedding_service import EmbeddingService
from app.models.document_section import DocumentSection
from sqlalchemy import text

# Set up logging
logger = logging.getLogger(__name__)

class SectionEmbeddingService(EmbeddingService):
    """Service for generating and managing embeddings for document sections."""
    
    def __init__(self, model_name=None, embedding_dimension=None):
        """
        Initialize the section embedding service.
        
        Args:
            model_name: The name of the local embedding model to use
            embedding_dimension: The dimension of the embedding vectors
        """
        super().__init__(model_name, embedding_dimension)
        
    def generate_section_embeddings(self, section_metadata: Dict[str, Dict[str, str]]) -> Dict[str, List[float]]:
        """
        Generate embeddings for document sections based on metadata.
        
        Args:
            section_metadata: Dictionary mapping section URIs to metadata including content
                {
                    "http://proethica.org/document/case_12345/facts": {
                        "type": "facts",
                        "content": "The facts of the case..."
                    },
                    ...
                }
            
        Returns:
            Dictionary mapping section URIs to embedding vectors
            {
                "http://proethica.org/document/case_12345/facts": [0.1, 0.2, ...],
                ...
            }
        """
        section_embeddings = {}
        
        if not section_metadata:
            logger.warning("No section metadata provided for embedding generation")
            return section_embeddings
            
        logger.info(f"Generating embeddings for {len(section_metadata)} document sections")
        
        for section_uri, metadata in section_metadata.items():
            try:
                content = metadata.get('content', '')
                if not content:
                    logger.warning(f"Empty content for section {section_uri}")
                    continue
                
                # Generate embedding for this section
                embedding = self.get_embedding(content)
                section_embeddings[section_uri] = embedding
                
                # Add a short delay to avoid rate limits on external providers
                time.sleep(0.05)
                
            except Exception as e:
                logger.error(f"Error generating embedding for section {section_uri}: {str(e)}")
                # Continue with other sections
        
        logger.info(f"Successfully generated embeddings for {len(section_embeddings)} sections")
        return section_embeddings
    
    def store_section_embeddings(self, document_id: int, section_embeddings: Dict[str, List[float]]) -> Dict[str, Any]:
        """
        Store section embeddings in the DocumentSection table using pgvector.
        
        Args:
            document_id: ID of the document
            section_embeddings: Dictionary mapping section URIs to embedding vectors
            
        Returns:
            Dictionary with storage results
        """
        from app import db
        from app.models.document import Document
        
        try:
            # Use a no_autoflush block to prevent premature flushing
            with db.session.no_autoflush:
                # Retrieve the document
                document = Document.query.get(document_id)
                if not document:
                    logger.error(f"Document not found: {document_id}")
                    return {'success': False, 'error': f"Document not found: {document_id}"}
                
                # Get existing metadata or initialize empty dict
                doc_metadata = document.doc_metadata or {}
                
                # Initialize or update the document structure metadata
                if 'document_structure' not in doc_metadata:
                    doc_metadata['document_structure'] = {}
                    
                # Add the section embeddings flag in metadata (for UI compatibility)
                doc_metadata['document_structure']['section_embeddings'] = {
                    'count': len(section_embeddings),
                    'updated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'storage_type': 'pgvector',  # Indicate we're using pgvector storage
                    'embedding_dimension': 384   # Add the dimension for clarity
                }
                
                logger.info(f"Adding {len(section_embeddings)} sections to DocumentSection table")
                
                # Store section content and embeddings in DocumentSection table
                sections_added = 0
                
                # Process each section
                # First, deduplicate sections to avoid unique constraint violations
                processed_section_ids = set()
                deduplicated_embeddings = {}
                
                for section_uri, embedding in section_embeddings.items():
                    # Extract section_id from URI
                    section_id = section_uri.split('/')[-1]
                    
                    # Skip if we've already processed this section ID
                    if section_id in processed_section_ids:
                        logger.warning(f"Skipping duplicate section ID: {section_id} from URI {section_uri}")
                        continue
                        
                    # Use normalized URI with current document ID
                    normalized_uri = f"http://proethica.org/document/case_{document_id}/{section_id}"
                    deduplicated_embeddings[normalized_uri] = embedding
                    processed_section_ids.add(section_id)
                
                # Process each deduplicated section
                for section_uri, embedding in deduplicated_embeddings.items():
                    # Extract section_id from URI
                    section_id = section_uri.split('/')[-1]
                    
                # Get section content and type from metadata
                    section_type = section_id  # Default to section_id as type
                    section_content = ""
                    
                    # Try to find content in document_structure.sections
                    if ('sections' in doc_metadata['document_structure'] and 
                        section_id in doc_metadata['document_structure']['sections']):
                        section_data = doc_metadata['document_structure']['sections'][section_id]
                        section_type = section_data.get('type', section_id)
                        section_content = section_data.get('content', '')
                    
                    # If not found, try top-level sections
                    if not section_content and 'sections' in doc_metadata and section_id in doc_metadata['sections']:
                        section_content = doc_metadata['sections'][section_id]
                    
                    # Skip if no content
                    if not section_content:
                        logger.warning(f"No content found for section {section_id}, skipping")
                        continue
                    
                    # Verify embedding dimensionality
                    if len(embedding) != 384:  # Our embedding dimension is 384
                        logger.warning(f"Embedding dimension mismatch for section {section_id}: " +
                                     f"expected 384, got {len(embedding)}. Skipping.")
                        continue
                    
                    # Process section in a separate transaction to avoid cascade failures
                    try:
                        # Check if section already exists
                        existing_section = DocumentSection.query.filter_by(
                            document_id=document_id, 
                            section_id=section_id
                        ).first()
                        
                        if existing_section:
                            # Update existing section
                            existing_section.section_type = section_type
                            existing_section.content = section_content
                            existing_section.embedding = embedding  # Pass the list directly to our Vector type
                            existing_section.updated_at = datetime.utcnow()
                            logger.info(f"Updated existing section {section_id}")
                        else:
                            # Create new section
                            new_section = DocumentSection(
                                document_id=document_id,
                                section_id=section_id,
                                section_type=section_type,
                                content=section_content,
                                embedding=embedding,  # Pass the list directly to our Vector type
                                section_metadata={'uri': section_uri}
                            )
                            db.session.add(new_section)
                            logger.info(f"Added new section {section_id}")
                        
                        sections_added += 1
                    except Exception as section_error:
                        logger.error(f"Error processing section {section_id}: {str(section_error)}")
                        # Continue with other sections rather than failing the entire batch
                
                # Ensure section_embeddings metadata is properly updated in document_structure
                if 'document_structure' not in doc_metadata:
                    doc_metadata['document_structure'] = {}
                
                # Update the section_embeddings metadata with current information
                count = DocumentSection.query.filter_by(document_id=document_id).count()
                doc_metadata['document_structure']['section_embeddings'] = {
                    'count': count,
                    'updated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'storage_type': 'pgvector',
                    'embedding_dimension': 384
                }
                
                # Log metadata update
                logger.info(f"Updating document metadata with section_embeddings information: {count} sections")
                
                # Save metadata update
                document.doc_metadata = json.loads(json.dumps(doc_metadata))
                
                # Commit all changes
                db.session.commit()
                
                # Verify sections were stored
                count = DocumentSection.query.filter_by(document_id=document_id).count()
                logger.info(f"Verified {count} sections stored in DocumentSection table")
                
                return {
                    'success': True,
                    'document_id': document_id,
                    'sections_embedded': sections_added,
                    'metadata_updated': True
                }
            
        except Exception as e:
            logger.exception(f"Error storing section embeddings: {str(e)}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def find_similar_sections(self, query_text: str, document_id: Optional[int] = None, 
                             section_type: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Find document sections similar to the query text using pgvector.
        
        Args:
            query_text: The query text to compare with document sections
            document_id: Optional document ID to limit search to a specific document
            section_type: Optional section type to limit search (facts, discussion, etc.)
            limit: Maximum number of results to return
            
        Returns:
            List of similar sections with metadata and similarity scores
        """
        from app import db
        from app.models.document import Document
        
        similar_sections = []
        
        try:
            # Generate embedding for the query text
            query_embedding = self.get_embedding(query_text)
            
            # Verify embedding dimension is correct
            if len(query_embedding) != 384:  # Our embedding dimension
                logger.warning(f"Query embedding dimension mismatch: expected 384, got {len(query_embedding)}")
                return []
            
            # Start query with DocumentSection
            query = DocumentSection.query.join(Document)
            
            # Add filters
            if document_id:
                query = query.filter(DocumentSection.document_id == document_id)
                
            if section_type:
                query = query.filter(DocumentSection.section_type == section_type)
            
            # Try using native pgvector similarity if available
            try:
                # Create an instance of our Vector type for proper type handling
                from app.models.document_section import Vector
                vector_type = Vector(384)
                
                # Let our Vector type handle the conversion
                embedding_param = vector_type.bind_processor(None)(query_embedding)
                
                # Use with to ensure transaction consistency
                with db.session.begin():
                    # For pgvector's native cosine similarity
                    # This is more efficient than calculating similarity in Python
                    query_sql = """
                    SELECT 
                        ds.id, 
                        ds.document_id, 
                        ds.section_id, 
                        ds.section_type, 
                        ds.content,
                        ds.embedding <=> :query_embedding::vector(384) AS similarity,
                        d.title AS document_title
                    FROM 
                        document_sections ds
                    JOIN 
                        documents d ON ds.document_id = d.id
                    WHERE 
                        ds.embedding IS NOT NULL
                    """
                    
                    # Dynamically add filters based on parameters
                    params = {'query_embedding': embedding_param}
                    
                    if document_id is not None:
                        query_sql += " AND ds.document_id = :document_id"
                        params['document_id'] = document_id
                    
                    if section_type is not None:
                        query_sql += " AND ds.section_type = :section_type"
                        params['section_type'] = section_type
                    
                    # Add order and limit
                    query_sql += """
                    ORDER BY 
                        similarity ASC
                    LIMIT :limit
                    """
                    params['limit'] = limit
                    
                    # Execute the query with the properly formatted embedding
                    sections = db.session.execute(
                        text(query_sql),
                        params
                    )
                
                for row in sections:
                    # Convert to 0-1 scale where 1 is most similar
                    # pgvector returns distance where 0 is identical
                    normalized_similarity = max(0.0, 1.0 - float(row.similarity))
                    
                    similar_sections.append({
                        'document_id': row.document_id,
                        'document_title': row.document_title,
                        'section_id': row.section_id,
                        'section_type': row.section_type,
                        'similarity': normalized_similarity,
                        'content': row.content
                    })
                
                logger.info(f"Found {len(similar_sections)} similar sections using pgvector")
                return similar_sections
                
            except Exception as e:
                # If pgvector native query fails, fall back to Python similarity calculation
                logger.warning(f"Native pgvector similarity query failed: {str(e)}")
                logger.info("Falling back to Python similarity calculation")
                
                # Get all sections
                sections = query.all()
                
                for section in sections:
                    if section.embedding is None:
                        continue
                    
                    # Calculate similarity in Python
                    similarity = self.calculate_similarity(query_embedding, section.embedding)
                    
                    similar_sections.append({
                        'document_id': section.document_id,
                        'document_title': section.document.title,
                        'section_id': section.section_id,
                        'section_type': section.section_type,
                        'similarity': similarity,
                        'content': section.content
                    })
                
                # Sort by similarity (descending)
                similar_sections.sort(key=lambda x: x['similarity'], reverse=True)
                
                # Limit results
                similar_sections = similar_sections[:limit]
                
                logger.info(f"Found {len(similar_sections)} similar sections using Python calculation")
            
            return similar_sections
            
        except Exception as e:
            logger.exception(f"Error finding similar sections: {str(e)}")
            return []
    
    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score (0-1)
        """
        import numpy as np
        
        # Convert to numpy arrays
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Calculate cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        # Avoid division by zero
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        similarity = dot_product / (norm1 * norm2)
        
        # Ensure result is between 0 and 1
        return max(0.0, min(1.0, similarity))
    
    def process_document_sections(self, document_id: int) -> Dict[str, Any]:
        """
        Process a document to generate and store section embeddings.
        
        Args:
            document_id: ID of the document to process
            
        Returns:
            Dictionary with processing results
        """
        from app import db
        from app.models.document import Document
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info(f"Processing document sections for document ID: {document_id}")
        
        try:
            # Retrieve the document
            document = Document.query.get(document_id)
            if not document:
                logger.error(f"Document not found: {document_id}")
                return {'success': False, 'error': f"Document not found: {document_id}"}
            
            # Get document metadata
            doc_metadata = document.doc_metadata or {}
            
            # Log metadata structure for debugging
            logger.info(f"Document metadata keys: {list(doc_metadata.keys())}")
            
            # Get the structure data - might be missing if using legacy format
            doc_structure = doc_metadata.get('document_structure', {})
            
            # Prepare section metadata
            section_metadata = {}
            
            # Strategy 1: Try to get sections from document_structure.sections
            if 'sections' in doc_structure and doc_structure['sections']:
                logger.info(f"Found sections in document_structure.sections")
                
                for section_id, section_data in doc_structure['sections'].items():
                    # Extract the content from the section data or from the main sections if available
                    if 'content' not in section_data and 'sections' in doc_metadata:
                        # Try to find the content in the top-level sections
                        if section_id in doc_metadata['sections']:
                            section_content = doc_metadata['sections'][section_id]
                        else:
                            logger.warning(f"No content found for section {section_id}")
                            continue
                    else:
                        section_content = section_data.get('content', '')
                    
                    if section_content:
                        section_uri = f"http://proethica.org/document/case_{document_id}/{section_id}"
                        section_metadata[section_uri] = {
                            'type': section_data.get('type', section_id),
                            'content': section_content
                        }
            
            # Strategy 2: Try to get from section_embeddings_metadata
            elif 'section_embeddings_metadata' in doc_metadata and doc_metadata['section_embeddings_metadata']:
                logger.info(f"Found sections in section_embeddings_metadata")
                section_metadata_dict = {}
                seen_section_ids = set()  # Track section IDs we've already processed
                
                # Process and deduplicate sections
                for section_uri, data in doc_metadata['section_embeddings_metadata'].items():
                    section_id = section_uri.split('/')[-1]
                    
                    # Skip if we already processed this section ID to avoid duplicates
                    if section_id in seen_section_ids:
                        logger.warning(f"Skipping duplicate section ID: {section_id} from URI {section_uri}")
                        continue
                    
                    # Mark this section ID as processed
                    seen_section_ids.add(section_id)
                    
                    # Use current case's URI format consistently
                    normalized_uri = f"http://proethica.org/document/case_{document_id}/{section_id}"
                    section_metadata_dict[normalized_uri] = data.copy()
                    
                # Use the deduplicated dictionary
                section_metadata = section_metadata_dict
                
                # Validate each entry has content
                for section_uri, data in list(section_metadata.items()):
                    if 'content' not in data or not data['content']:
                        logger.warning(f"Section {section_uri} has no content, attempting to find it elsewhere")
                        
                        # Try to extract section id from URI
                        section_id = section_uri.split('/')[-1]
                        
                        # Check if content exists in top-level sections
                        if 'sections' in doc_metadata and section_id in doc_metadata['sections']:
                            section_metadata[section_uri]['content'] = doc_metadata['sections'][section_id]
                            logger.info(f"Found content for {section_id} in top-level sections")
                        else:
                            # Remove sections without content
                            del section_metadata[section_uri]
            
            # Strategy 3: Try to use legacy structure format with top-level structure_triples
            elif 'document_uri' in doc_metadata and 'structure_triples' in doc_metadata:
                logger.info(f"Found legacy structure format (top-level structure_triples)")
                
                # Create minimal document_structure to ensure storage works properly
                if 'document_structure' not in doc_metadata:
                    doc_metadata['document_structure'] = {
                        'document_uri': doc_metadata['document_uri'],
                        'structure_triples': doc_metadata['structure_triples'],
                        'sections': {}
                    }
                    # Update document to format structure properly for future use
                    document.doc_metadata = doc_metadata
                    db.session.commit()
                    logger.info(f"Reorganized document metadata to standard format")
                
                # Then fall through to Strategy 4 to use top-level sections
                
            # Strategy 4: Try to get from top-level sections
            if 'sections' in doc_metadata and doc_metadata['sections']:
                logger.info(f"Using top-level sections")
                for section_id, content in doc_metadata['sections'].items():
                    if content:  # Skip empty sections
                        section_uri = f"http://proethica.org/document/case_{document_id}/{section_id}"
                        section_metadata[section_uri] = {
                            'type': section_id,
                            'content': content
                        }
            
            # Log what we found
            logger.info(f"Prepared {len(section_metadata)} sections for embedding generation")
            
            # If still no section metadata, fail
            if not section_metadata:
                logger.error(f"Document {document_id} has no section metadata for embedding")
                return {'success': False, 'error': "No section metadata available for embedding"}
            
            # Generate embeddings for all sections
            section_embeddings = self.generate_section_embeddings(section_metadata)
            
            # Store the embeddings
            result = self.store_section_embeddings(document_id, section_embeddings)
            
            return result
            
        except Exception as e:
            logger.exception(f"Error processing document sections: {str(e)}")
            return {'success': False, 'error': str(e)}
