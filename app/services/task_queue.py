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
    
    def _process_document_task(self, document_id):
        """Background task to process a document."""
        try:
            # Get a new db session for this thread
            from app import create_app
            app = create_app()
            
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
                
                # Extract text if needed
                if document.file_path and not document.content:
                    # Update progress: Extracting text (20%)
                    document.processing_phase = PROCESSING_PHASES['EXTRACTING']
                    document.processing_progress = 20
                    db.session.commit()
                    
                    text = self.embedding_service._extract_text(document.file_path, document.file_type)
                    document.content = text
                    
                    # Update progress: Text extracted (30%)
                    document.processing_progress = 30
                    db.session.commit()
                
                # Process document content
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
                
                # Update document status to completed (100%)
                document.processing_status = PROCESSING_STATUS['COMPLETED']
                document.processing_progress = 100
                db.session.commit()
                
                logger.info(f"Completed background processing for document {document_id}")
        
        except Exception as e:
            logger.error(f"Error processing document {document_id} in background: {str(e)}")
            
            try:
                # Update document status to failed
                with app.app_context():
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
