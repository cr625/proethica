"""
Async Concept Extraction Service - Handles long-running concept extraction tasks
using the existing BackgroundTaskQueue infrastructure.
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import uuid

from app import db
from app.models.guideline import Guideline
from app.services.task_queue import BackgroundTaskQueue
from app.services.guideline_analysis_service import GuidelineAnalysisService
from app.services.temporary_concept_service import TemporaryConceptService

logger = logging.getLogger(__name__)

class AsyncConceptExtractionService:
    """Service for handling async concept extraction tasks."""
    
    def __init__(self):
        self.task_queue = BackgroundTaskQueue.get_instance()
        self.active_extractions = {}  # task_id -> extraction_info
        
    def start_extraction(self, guideline_id: int, world_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Start async concept extraction for a guideline.
        
        Args:
            guideline_id: ID of the guideline to extract concepts from
            world_id: World ID for context (defaults to guideline's world)
            
        Returns:
            Dict with task_id and status info
        """
        try:
            # Get guideline
            guideline = Guideline.query.get(guideline_id)
            if not guideline:
                return {
                    'success': False,
                    'error': f'Guideline {guideline_id} not found'
                }
                
            # Use guideline's world if not specified
            if world_id is None:
                world_id = guideline.world_id
                
            # Generate unique task ID
            task_id = f"extract_{guideline_id}_{uuid.uuid4().hex[:8]}"
            
            # Store extraction info
            extraction_info = {
                'task_id': task_id,
                'guideline_id': guideline_id,
                'world_id': world_id,
                'status': 'starting',
                'progress': 0,
                'phase': 'initializing',
                'started_at': datetime.utcnow().isoformat(),
                'session_id': None,
                'error': None
            }
            self.active_extractions[task_id] = extraction_info
            
            # Create task function
            def extraction_task():
                self._run_extraction_task(task_id, guideline_id, world_id)
                
            # Start background task
            background_task_id = self.task_queue.process_task_async(extraction_task)
            extraction_info['background_task_id'] = background_task_id
            
            logger.info(f"Started async concept extraction task {task_id} for guideline {guideline_id}")
            
            return {
                'success': True,
                'task_id': task_id,
                'status': 'starting',
                'message': 'Concept extraction started in background'
            }
            
        except Exception as e:
            logger.error(f"Error starting async extraction: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Failed to start extraction: {str(e)}'
            }
    
    def get_extraction_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get status of an async extraction task.
        
        Args:
            task_id: Task ID returned from start_extraction
            
        Returns:
            Dict with current status and progress
        """
        if task_id not in self.active_extractions:
            return {
                'success': False,
                'error': 'Task not found'
            }
            
        extraction_info = self.active_extractions[task_id]
        
        return {
            'success': True,
            'task_id': task_id,
            'status': extraction_info.get('status', 'unknown'),
            'progress': extraction_info.get('progress', 0),
            'phase': extraction_info.get('phase', 'unknown'),
            'started_at': extraction_info.get('started_at'),
            'completed_at': extraction_info.get('completed_at'),
            'session_id': extraction_info.get('session_id'),
            'stats': extraction_info.get('stats'),
            'error': extraction_info.get('error')
        }
    
    def _run_extraction_task(self, task_id: str, guideline_id: int, world_id: int):
        """
        Run the actual extraction task in background thread.
        This runs in a separate thread with its own app context.
        """
        try:
            # Create new app context for this thread
            from app import create_app
            import os
            
            os.environ.setdefault('ENVIRONMENT', 'development')
            app = create_app('config')
            
            with app.app_context():
                # Update status
                self._update_extraction_status(task_id, 'running', 10, 'loading_guideline')
                
                # Get guideline
                guideline = Guideline.query.get(guideline_id)
                if not guideline:
                    self._update_extraction_status(task_id, 'failed', 0, 'failed', 
                                                 error=f'Guideline {guideline_id} not found')
                    return
                    
                if not guideline.content:
                    self._update_extraction_status(task_id, 'failed', 0, 'failed',
                                                 error='Guideline has no content to extract from')
                    return
                
                logger.info(f"Starting concept extraction for guideline {guideline_id} (task {task_id})")
                
                # Update status
                self._update_extraction_status(task_id, 'running', 20, 'initializing_service')
                
                # Create extraction service
                analysis_service = GuidelineAnalysisService()
                
                # Update status
                self._update_extraction_status(task_id, 'running', 30, 'extracting_concepts')
                
                # Run extraction (this is now roles-only and should be faster)
                result = analysis_service.extract_concepts(
                    content=guideline.content,
                    guideline_id=guideline_id,
                    world_id=world_id,
                    use_temp_storage=True
                )
                
                if result.get('success'):
                    # Update status
                    self._update_extraction_status(task_id, 'running', 80, 'saving_results')
                    
                    # Get session_id from result
                    session_id = result.get('session_id')
                    stats = result.get('stats', {})
                    
                    logger.info(f"Extraction completed for task {task_id}: {stats.get('total_concepts', 0)} concepts extracted")
                    
                    # Update status to completed
                    self._update_extraction_status(
                        task_id, 'completed', 100, 'completed',
                        session_id=session_id,
                        stats=stats,
                        completed_at=datetime.utcnow().isoformat()
                    )
                else:
                    # Extraction failed
                    error_msg = result.get('error', 'Unknown extraction error')
                    logger.error(f"Extraction failed for task {task_id}: {error_msg}")
                    self._update_extraction_status(task_id, 'failed', 0, 'failed', error=error_msg)
                    
        except Exception as e:
            logger.error(f"Error in extraction task {task_id}: {e}", exc_info=True)
            self._update_extraction_status(task_id, 'failed', 0, 'failed', 
                                         error=f'Extraction failed: {str(e)}')
        finally:
            # Clean up task after some time (keep for 1 hour for status checking)
            import threading
            import time
            
            def cleanup_task():
                time.sleep(3600)  # 1 hour
                if task_id in self.active_extractions:
                    logger.info(f"Cleaning up completed extraction task {task_id}")
                    del self.active_extractions[task_id]
                    
            cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
            cleanup_thread.start()
    
    def _update_extraction_status(self, task_id: str, status: str, progress: int, phase: str,
                                session_id: Optional[str] = None, stats: Optional[Dict] = None,
                                error: Optional[str] = None, completed_at: Optional[str] = None):
        """Update extraction status in memory."""
        if task_id in self.active_extractions:
            extraction_info = self.active_extractions[task_id]
            extraction_info.update({
                'status': status,
                'progress': progress,
                'phase': phase
            })
            
            if session_id is not None:
                extraction_info['session_id'] = session_id
            if stats is not None:
                extraction_info['stats'] = stats
            if error is not None:
                extraction_info['error'] = error
            if completed_at is not None:
                extraction_info['completed_at'] = completed_at
                
            logger.debug(f"Updated extraction status for {task_id}: {status} ({progress}%) - {phase}")

# Global service instance
_async_extraction_service = None

def get_async_extraction_service() -> AsyncConceptExtractionService:
    """Get or create global async extraction service instance."""
    global _async_extraction_service
    if _async_extraction_service is None:
        _async_extraction_service = AsyncConceptExtractionService()
    return _async_extraction_service
