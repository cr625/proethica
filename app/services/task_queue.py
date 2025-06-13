"""
Background task queue for processing documents asynchronously.
"""

import threading
import logging
import time
from app import db
from app.models.document import Document, PROCESSING_STATUS, PROCESSING_PHASES
from app.services.embedding_service import EmbeddingService

# Set up logging
logger = logging.getLogger(__name__)

# Association processing phases
ASSOCIATION_PHASES = {
    'ANALYZING': 'analyzing',
    'LLM_PROCESSING': 'llm_processing', 
    'SAVING_RESULTS': 'saving_results'
}

class BackgroundTaskQueue:
    """Simple background task queue for processing documents asynchronously."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance of BackgroundTaskQueue."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """Initialize the task queue."""
        self.embedding_service = EmbeddingService()
        self.active_threads = {}
    
    def process_document_async(self, document_id):
        """Process a document asynchronously in a background thread."""
        # Update document status to processing
        document = Document.query.get(document_id)
        if not document:
            logger.error(f"Document with ID {document_id} not found")
            return False
        
        document.processing_status = PROCESSING_STATUS['PROCESSING']
        db.session.commit()
        
        # Create and start a new thread for processing
        thread = threading.Thread(
            target=self._process_document_task,
            args=(document_id,),
            daemon=True
        )
        
        self.active_threads[document_id] = thread
        thread.start()
        
        logger.info(f"Started background processing for document {document_id}")
        return True
    
    def process_associations_async(self, document_id, association_method='embedding'):
        """Process document associations asynchronously in a background thread."""
        # Get document
        document = Document.query.get(document_id)
        if not document:
            logger.error(f"Document with ID {document_id} not found")
            return False
        
        # Check if already processing
        if hasattr(document, 'association_processing_status') and document.association_processing_status == 'processing':
            logger.warning(f"Document {document_id} is already being processed for associations")
            return False
        
        # Create and start a new thread for association processing
        thread = threading.Thread(
            target=self._process_associations_task,
            args=(document_id, association_method),
            daemon=True
        )
        
        thread_key = f"assoc_{document_id}"
        self.active_threads[thread_key] = thread
        thread.start()
        
        logger.info(f"Started background association processing for document {document_id}")
        return True
    
    def _process_document_task(self, document_id):
        """Background task to process a document."""
        try:
            # Get a new db session for this thread
            from app import create_app
            import os
            
            # Ensure environment is set
            os.environ.setdefault('ENVIRONMENT', 'development')
            
            # Create app with proper config
            app = create_app('config')
            
            with app.app_context():
                # Get document
                document = Document.query.get(document_id)
                if not document:
                    logger.error(f"Document with ID {document_id} not found in background task")
                    return
                
                logger.info(f"Processing document {document_id} in background")
                
                # Update progress: Initializing (10%)
                document.processing_phase = PROCESSING_PHASES['INITIALIZING']
                document.processing_progress = 10
                db.session.commit()
                
                # Skip extraction if content already exists (e.g., pasted text)
                if document.content:
                    logger.info(f"Document {document_id} already has content, skipping extraction")
                    # Jump directly to chunking phase
                    document.processing_progress = 30
                    db.session.commit()
                # Extract content based on document type
                elif document.file_type == "url" and document.source:
                    # Handle URL type documents
                    logger.info(f"Processing URL document: {document.source}")
                    document.processing_phase = PROCESSING_PHASES['EXTRACTING']
                    document.processing_progress = 20
                    db.session.commit()
                    
                    # Extract text from URL
                    try:
                        text = self.embedding_service._extract_from_url(document.source)
                        document.content = text
                        document.processing_progress = 30
                        db.session.commit()
                        logger.info(f"Successfully extracted {len(text)} characters from URL")
                    except Exception as e:
                        logger.error(f"Error extracting text from URL {document.source}: {str(e)}")
                        document.processing_error = f"URL extraction error: {str(e)}"
                        document.processing_status = PROCESSING_STATUS['FAILED']
                        db.session.commit()
                        return
                
                # Extract text from file if needed
                elif document.file_path and not document.content:
                    # Update progress: Extracting text (20%)
                    document.processing_phase = PROCESSING_PHASES['EXTRACTING']
                    document.processing_progress = 20
                    db.session.commit()
                    
                    try:
                        text = self.embedding_service._extract_text(document.file_path, document.file_type)
                        document.content = text
                        
                        # Update progress: Text extracted (30%)
                        document.processing_progress = 30
                        db.session.commit()
                    except Exception as e:
                        logger.error(f"Error extracting text from file {document.file_path}: {str(e)}")
                        document.processing_error = f"File extraction error: {str(e)}"
                        document.processing_status = PROCESSING_STATUS['FAILED']
                        db.session.commit()
                        return
                
                # Process document content if available
                if document.content:
                    # Update progress: Chunking text (40%)
                    document.processing_phase = PROCESSING_PHASES['CHUNKING']
                    document.processing_progress = 40
                    db.session.commit()
                    
                    # Split text into chunks
                    chunks = self.embedding_service._split_text(document.content)
                    
                    # Update progress: Generating embeddings (50%)
                    document.processing_phase = PROCESSING_PHASES['EMBEDDING']
                    document.processing_progress = 50
                    db.session.commit()
                    
                    # Generate embeddings for chunks
                    embeddings = self.embedding_service.embed_documents(chunks)
                    
                    # Update progress: Storing chunks (70%)
                    document.processing_phase = PROCESSING_PHASES['STORING']
                    document.processing_progress = 70
                    db.session.commit()
                    
                    # Store chunks with embeddings
                    self.embedding_service._store_chunks(document.id, chunks, embeddings)
                    
                    # Update progress: Finalizing (90%)
                    document.processing_phase = PROCESSING_PHASES['FINALIZING']
                    document.processing_progress = 90
                    db.session.commit()
                else:
                    # No content to process
                    logger.error(f"Document {document_id} has no content to process")
                    document.processing_error = "No content available for processing"
                    document.processing_status = PROCESSING_STATUS['FAILED']
                    db.session.commit()
                    return
                
                # Update document status to completed (100%)
                document.processing_status = PROCESSING_STATUS['COMPLETED']
                document.processing_progress = 100
                document.processing_phase = PROCESSING_PHASES['FINALIZING']
                db.session.commit()
                
                logger.info(f"Completed background processing for document {document_id}")
        
        except Exception as e:
            logger.error(f"Error processing document {document_id} in background: {str(e)}")
            
            try:
                # Update document status to failed
                # Create a new app context for error handling
                from app import create_app
                import os
                os.environ.setdefault('ENVIRONMENT', 'development')
                error_app = create_app('config')
                
                with error_app.app_context():
                    document = Document.query.get(document_id)
                    if document:
                        document.processing_status = PROCESSING_STATUS['FAILED']
                        document.processing_error = str(e)
                        db.session.commit()
            except Exception as inner_e:
                logger.error(f"Error updating document status: {str(inner_e)}")
        
        finally:
            # Remove thread from active threads
            if document_id in self.active_threads:
                del self.active_threads[document_id]
    
    def _process_associations_task(self, document_id, association_method='embedding'):
        """Background task to process associations for a document."""
        try:
            # Get a new db session for this thread
            from app import create_app
            import os
            
            # Ensure environment is set
            os.environ.setdefault('ENVIRONMENT', 'development')
            
            # Create app with proper config
            app = create_app('config')
            
            with app.app_context():
                # Get document
                document = Document.query.get(document_id)
                if not document:
                    logger.error(f"Document with ID {document_id} not found in background association task")
                    return
                
                logger.info(f"Processing associations for document {document_id} in background")
                
                # Initialize association processing status (using doc_metadata for now)
                if not document.doc_metadata:
                    document.doc_metadata = {}
                
                document.doc_metadata['association_processing_status'] = 'processing'
                document.doc_metadata['association_processing_progress'] = 10
                document.doc_metadata['association_processing_phase'] = ASSOCIATION_PHASES['ANALYZING']
                db.session.commit()
                
                # Import the enhanced service
                from app.services.enhanced_guideline_association_service import EnhancedGuidelineAssociationService
                enhanced_service = EnhancedGuidelineAssociationService()
                
                # Update progress: Starting analysis (30%)
                document.doc_metadata['association_processing_progress'] = 30
                db.session.commit()
                
                # Generate enhanced associations
                logger.info(f"Generating associations using {association_method} method")
                document.doc_metadata['association_processing_phase'] = ASSOCIATION_PHASES['LLM_PROCESSING']
                document.doc_metadata['association_processing_progress'] = 40
                db.session.commit()
                
                associations = enhanced_service.generate_associations_for_case(document_id)
                
                if not associations:
                    logger.warning(f"No associations generated for document {document_id}")
                    document.doc_metadata['association_processing_status'] = 'failed'
                    document.doc_metadata['association_processing_error'] = 'No associations could be generated'
                    db.session.commit()
                    return
                
                # Update progress: Saving results (80%)
                document.doc_metadata['association_processing_phase'] = ASSOCIATION_PHASES['SAVING_RESULTS']
                document.doc_metadata['association_processing_progress'] = 80
                db.session.commit()
                
                # Save associations to database
                associations_created = enhanced_service.save_associations_to_database(associations)
                
                # Calculate statistics
                total_associations = len(associations)
                avg_confidence = sum(assoc.score.overall_confidence for assoc in associations) / total_associations
                high_confidence_count = sum(1 for assoc in associations if assoc.score.overall_confidence > 0.7)
                
                # Store results in metadata
                document.doc_metadata['association_results'] = {
                    'total_associations': total_associations,
                    'avg_confidence': avg_confidence,
                    'high_confidence_count': high_confidence_count,
                    'method_used': association_method,
                    'processed_at': datetime.utcnow().isoformat()
                }
                
                # Mark as completed (100%)
                document.doc_metadata['association_processing_status'] = 'completed'
                document.doc_metadata['association_processing_progress'] = 100
                document.doc_metadata['association_processing_phase'] = ASSOCIATION_PHASES['SAVING_RESULTS']
                db.session.commit()
                
                logger.info(f"Completed background association processing for document {document_id}: {total_associations} associations with {avg_confidence:.2f} avg confidence")
        
        except Exception as e:
            logger.error(f"Error processing associations for document {document_id} in background: {str(e)}")
            
            try:
                # Update document status to failed
                from app import create_app
                import os
                os.environ.setdefault('ENVIRONMENT', 'development')
                error_app = create_app('config')
                
                with error_app.app_context():
                    document = Document.query.get(document_id)
                    if document:
                        if not document.doc_metadata:
                            document.doc_metadata = {}
                        document.doc_metadata['association_processing_status'] = 'failed'
                        document.doc_metadata['association_processing_error'] = str(e)
                        db.session.commit()
            except Exception as inner_e:
                logger.error(f"Error updating association status: {str(inner_e)}")
        
        finally:
            # Remove thread from active threads
            thread_key = f"assoc_{document_id}"
            if thread_key in self.active_threads:
                del self.active_threads[thread_key]
