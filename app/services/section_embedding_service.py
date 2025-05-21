"""
Section Embedding Service - Extension of EmbeddingService for document section embeddings.
"""
import logging
import json
import time
from typing import Dict, List, Any, Optional
from .embedding_service import EmbeddingService

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
        Store section embeddings in the database.
        
        Args:
            document_id: ID of the document
            section_embeddings: Dictionary mapping section URIs to embedding vectors
            
        Returns:
            Dictionary with storage results
        """
        from app import db
        from app.models.document import Document
        
        try:
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
                
            # Add the section embeddings
            doc_metadata['document_structure']['section_embeddings'] = {
                'count': len(section_embeddings),
                'updated_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Store the actual embeddings in the sections data
            if 'sections' not in doc_metadata['document_structure']:
                doc_metadata['document_structure']['sections'] = {}
                
            for section_uri, embedding in section_embeddings.items():
                # Get the section ID from the URI
                section_id = section_uri.split('/')[-1]
                
                # Initialize section if needed
                if section_id not in doc_metadata['document_structure']['sections']:
                    doc_metadata['document_structure']['sections'][section_id] = {}
                    
                # Store the embedding
                doc_metadata['document_structure']['sections'][section_id]['embedding'] = embedding
            
            # Update the document metadata
            document.doc_metadata = doc_metadata
            db.session.commit()
            
            return {
                'success': True,
                'document_id': document_id,
                'sections_embedded': len(section_embeddings)
            }
            
        except Exception as e:
            logger.exception(f"Error storing section embeddings: {str(e)}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def find_similar_sections(self, query_text: str, document_id: Optional[int] = None, 
                             section_type: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Find document sections similar to the query text.
        
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
            
            # Query documents with section embeddings
            query = Document.query
            
            # Filter by document ID if provided
            if document_id:
                query = query.filter(Document.id == document_id)
            
            # Filter documents with document_structure.section_embeddings
            documents = query.all()
            
            for doc in documents:
                if not doc.doc_metadata or 'document_structure' not in doc.doc_metadata:
                    continue
                    
                doc_structure = doc.doc_metadata.get('document_structure', {})
                if 'sections' not in doc_structure:
                    continue
                
                sections = doc_structure.get('sections', {})
                
                for section_id, section_data in sections.items():
                    # Skip if no embedding
                    if 'embedding' not in section_data:
                        continue
                        
                    # Filter by section type if provided
                    if section_type and section_data.get('type') != section_type:
                        continue
                        
                    # Get the section embedding
                    section_embedding = section_data.get('embedding')
                    
                    # Calculate cosine similarity
                    similarity = self.calculate_similarity(query_embedding, section_embedding)
                    
                    # Add to results
                    similar_sections.append({
                        'document_id': doc.id,
                        'document_title': doc.title,
                        'section_id': section_id,
                        'section_type': section_data.get('type', 'unknown'),
                        'similarity': similarity,
                        'content': section_data.get('content', '')
                    })
            
            # Sort by similarity (descending)
            similar_sections.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Limit results
            similar_sections = similar_sections[:limit]
            
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
                section_metadata = doc_metadata['section_embeddings_metadata']
                
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
