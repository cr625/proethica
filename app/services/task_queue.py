"""
Background task queue for processing documents asynchronously.
"""

import threading
import logging
import time
from datetime import datetime
from app import db
from app.models.document import Document, PROCESSING_STATUS, PROCESSING_PHASES
from app.services.embedding.embedding_service import EmbeddingService

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
        self.embedding_service = None  # Initialize lazily
        self.active_threads = {}
    
    def _get_embedding_service(self):
        """Lazily initialize embedding service only when needed."""
        if self.embedding_service is None:
            self.embedding_service = EmbeddingService.get_instance()
        return self.embedding_service
    
    def process_document_async(self, document_id):
        """Process a document or guideline asynchronously in a background thread."""
        # Get the document/guideline
        document = Document.query.get(document_id)
        if not document:
            logger.error(f"Document with ID {document_id} not found")
            return False
        
        # Determine entity type for logging
        entity_type = "guideline" if document.document_type == "guideline" else "document"
        
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
        
        logger.info(f"Started background processing for {entity_type} {document_id}")
        return True
    
    def process_task_async(self, task_function):
        """Process a generic task asynchronously in a background thread.
        
        Args:
            task_function: A callable that performs the background task
            
        Returns:
            str: Task ID for tracking
        """
        import uuid
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # Create and start a new thread for the task
        thread = threading.Thread(
            target=task_function,
            daemon=True
        )
        
        self.active_threads[task_id] = thread
        thread.start()
        
        logger.info(f"Started background task with ID {task_id}")
        return task_id
    
    def _process_document_task(self, document_id):
        """Background task to process a document or guideline."""
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
                
                # Determine if this is a guideline
                is_guideline = document.document_type == "guideline"
                entity_type = "guideline" if is_guideline else "document"
                
                logger.info(f"Processing {entity_type} {document_id} in background")
                
                # Update progress: Initializing (10%)
                document.processing_phase = PROCESSING_PHASES['INITIALIZING']
                document.processing_progress = 10
                db.session.commit()
                
                # Skip extraction if content already exists (e.g., pasted text)
                if document.content:
                    logger.info(f"{entity_type.capitalize()} {document_id} already has content, skipping extraction")
                    # Jump directly to chunking phase
                    document.processing_progress = 30
                    db.session.commit()
                # Extract content based on document type
                elif document.file_type == "url" and document.source:
                    # Handle URL type documents/guidelines
                    logger.info(f"Processing URL {entity_type}: {document.source}")
                    document.processing_phase = PROCESSING_PHASES['EXTRACTING']
                    document.processing_progress = 20
                    db.session.commit()
                    
                    # Extract text from URL
                    try:
                        text = self._get_embedding_service()._extract_from_url(document.source)
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
                        text = self._get_embedding_service()._extract_text(document.file_path, document.file_type)
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
                
                # Process content if available
                if document.content:
                    # Check if this is a guideline that needs structure annotation
                    if is_guideline:
                        # Update progress: Analyzing guideline structure (35%)
                        document.processing_phase = PROCESSING_PHASES.get('ANALYZING', PROCESSING_PHASES['CHUNKING'])
                        document.processing_progress = 35
                        db.session.commit()
                        
                        # Extract guideline sections
                        try:
                            from app.services.guideline.guideline_structure_annotation_step import GuidelineStructureAnnotationStep
                            
                            # Create Guideline record if it doesn't exist
                            from app.models.guideline import Guideline
                            guideline = Guideline.query.filter_by(
                                world_id=document.world_id,
                                title=document.title
                            ).first()
                            
                            if not guideline:
                                guideline = Guideline(
                                    world_id=document.world_id,
                                    title=document.title,
                                    content=document.content,
                                    source_url=document.source,
                                    file_path=document.file_path,
                                    file_type=document.file_type,
                                    guideline_metadata={}
                                )
                                db.session.add(guideline)
                                db.session.commit()
                                logger.info(f"Created Guideline record {guideline.id} for guideline document {document.id}")
                            
                            # Extract guideline sections
                            structure_annotator = GuidelineStructureAnnotationStep()
                            result = structure_annotator.process(guideline)
                            
                            if result['success']:
                                logger.info(f"Successfully extracted {result['sections_created']} sections from guideline {guideline.id}")
                                # Update document metadata with guideline info
                                if not document.doc_metadata:
                                    document.doc_metadata = {}
                                document.doc_metadata['guideline_structure'] = {
                                    'guideline_id': guideline.id,
                                    'format_type': result['format_type'],
                                    'sections_count': result['sections_created'],
                                    'processed_at': datetime.utcnow().isoformat()
                                }
                                db.session.commit()
                            else:
                                logger.warning(f"Guideline structure annotation failed: {result.get('error', 'Unknown error')}")
                            
                        except Exception as e:
                            logger.error(f"Error during guideline structure annotation: {str(e)}")
                            # Continue with normal processing even if guideline annotation fails
                    
                    # Update progress: Chunking text (40%)
                    document.processing_phase = PROCESSING_PHASES['CHUNKING']
                    document.processing_progress = 40
                    db.session.commit()
                    
                    # Split text into chunks
                    chunks = self._get_embedding_service()._split_text(document.content)
                    
                    # Update progress: Generating embeddings (50%)
                    document.processing_phase = PROCESSING_PHASES['EMBEDDING']
                    document.processing_progress = 50
                    db.session.commit()
                    
                    # Generate embeddings for chunks
                    embeddings = self._get_embedding_service().embed_documents(chunks)
                    
                    # Update progress: Storing chunks (70%)
                    document.processing_phase = PROCESSING_PHASES['STORING']
                    document.processing_progress = 70
                    db.session.commit()
                    
                    # Store chunks with embeddings
                    self._get_embedding_service()._store_chunks(document.id, chunks, embeddings)
                    
                    # Update progress: Finalizing (90%)
                    document.processing_phase = PROCESSING_PHASES['FINALIZING']
                    document.processing_progress = 90
                    db.session.commit()
                else:
                    # No content to process
                    logger.error(f"{entity_type.capitalize()} {document_id} has no content to process")
                    document.processing_error = "No content available for processing"
                    document.processing_status = PROCESSING_STATUS['FAILED']
                    db.session.commit()
                    return
                
                # Update status to completed (100%)
                document.processing_status = PROCESSING_STATUS['COMPLETED']
                document.processing_progress = 100
                document.processing_phase = PROCESSING_PHASES['FINALIZING']
                db.session.commit()
                
                logger.info(f"Completed background processing for {entity_type} {document_id}")
        
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
    
