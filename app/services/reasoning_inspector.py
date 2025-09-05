"""
Universal Reasoning Inspector Service

Captures and tracks all reasoning chains across ProEthica processes including:
- LLM interactions (prompts, responses, parsed results)
- Ontology queries (MCP calls, SPARQL queries)
- Algorithmic processing steps
- Text preprocessing operations

Provides a single interface for capturing reasoning data that can be inspected
through the web UI for debugging and analysis.
"""

import os
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from uuid import uuid4

from app.models import db
from app.models.reasoning_trace import ReasoningTrace, ReasoningStep

logger = logging.getLogger(__name__)


class ReasoningInspector:
    """Universal service for capturing all reasoning chains across ProEthica"""
    
    def __init__(self):
        self.current_trace: Optional[ReasoningTrace] = None
        self.debug_to_console = os.getenv('DEBUG_CONSOLE', 'false').lower() == 'true'
        self._step_counter = 0
        
    def start_trace(self, case_id: int, feature_type: str, session_prefix: str = None) -> str:
        """Start capturing a new reasoning chain
        
        Args:
            case_id: ID of case/document being processed
            feature_type: 'scenario', 'annotation', 'guideline'
            session_prefix: Optional prefix for session ID
            
        Returns:
            session_id: Unique identifier for this trace
        """
        try:
            # Generate unique session ID
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            uuid_part = str(uuid4())[:8]
            
            if session_prefix:
                session_id = f"{session_prefix}_{case_id}_{timestamp}_{uuid_part}"
            else:
                session_id = f"{feature_type}_{case_id}_{timestamp}_{uuid_part}"
            
            # Create new trace
            self.current_trace = ReasoningTrace(
                case_id=case_id,
                feature_type=feature_type,
                session_id=session_id
            )
            
            db.session.add(self.current_trace)
            db.session.commit()
            
            self._step_counter = 0
            
            if self.debug_to_console:
                print(f"🔍 Started reasoning trace: {session_id}")
            
            logger.info(f"Started reasoning trace {session_id} for case {case_id} ({feature_type})")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to start reasoning trace: {e}")
            self.current_trace = None
            return f"error_{uuid4()}"
    
    def capture_llm_interaction(self, phase: str, prompt: str, response: str, 
                               parsed_result: Any, model: str = None, 
                               tokens: int = None, temperature: float = None,
                               confidence_score: float = None,
                               processing_time: float = None) -> int:
        """Capture LLM request/response - ALWAYS saves to DB
        
        Args:
            phase: Name of the processing phase (e.g. 'timeline_extraction')
            prompt: The prompt sent to the LLM
            response: Raw response from the LLM
            parsed_result: Processed/parsed version of the response
            model: Model name used (e.g. 'claude-3-sonnet')
            tokens: Number of tokens used
            temperature: Temperature setting used
            confidence_score: Confidence in the result (0.0-1.0)
            processing_time: Time taken for this step in seconds
            
        Returns:
            step_id: Database ID of created step, or -1 if failed
        """
        if not self.current_trace:
            if self.debug_to_console:
                print(f"⚠️  No active trace for LLM interaction: {phase}")
            return -1
        
        try:
            self._step_counter += 1
            
            # Prepare input data
            input_data = {
                'prompt': prompt[:5000] if len(prompt) > 5000 else prompt,  # Truncate very long prompts
                'model': model,
                'temperature': temperature,
                'tokens_requested': tokens
            }
            
            # Prepare output data
            output_data = {
                'response': response[:10000] if len(response) > 10000 else response,  # Truncate very long responses
                'tokens_used': tokens,
                'model_used': model
            }
            
            # Create step
            step = ReasoningStep(
                trace_id=self.current_trace.id,
                step_number=self._step_counter,
                phase_name=phase,
                step_type='llm_call',
                input_data=input_data,
                output_data=output_data,
                processed_result=self._truncate_json_data(parsed_result),
                confidence_score=confidence_score,
                processing_time=processing_time,
                model_used=model,
                tokens_used=tokens,
                temperature=temperature
            )
            
            db.session.add(step)
            db.session.commit()
            
            if self.debug_to_console:
                conf_str = f" ({int(confidence_score * 100)}%)" if confidence_score else ""
                time_str = f" in {processing_time:.1f}s" if processing_time else ""
                print(f"🤖 LLM {phase}{conf_str}{time_str}")
            
            logger.info(f"Captured LLM interaction: {phase} (step {self._step_counter})")
            return step.id
            
        except Exception as e:
            logger.error(f"Failed to capture LLM interaction: {e}")
            return -1
    
    def capture_ontology_query(self, phase: str, entity_type: str, query: str, 
                              query_type: str, results: List[Dict],
                              processing_time: float = None) -> int:
        """Capture MCP/ontology server interactions
        
        Args:
            phase: Name of the processing phase
            entity_type: Type of entity being queried ('Principle', 'Role', etc.)
            query: The query string or parameters
            query_type: Type of query ('sparql', 'concept_lookup', 'mcp_tool', etc.)
            results: Results returned from the query
            processing_time: Time taken for this step in seconds
            
        Returns:
            step_id: Database ID of created step, or -1 if failed
        """
        if not self.current_trace:
            if self.debug_to_console:
                print(f"⚠️  No active trace for ontology query: {phase}")
            return -1
        
        try:
            self._step_counter += 1
            
            # Prepare input data
            input_data = {
                'query': query[:2000] if len(str(query)) > 2000 else str(query),
                'entity_type': entity_type,
                'query_type': query_type
            }
            
            # Prepare output data
            output_data = {
                'results': results[:50] if len(results) > 50 else results,  # Limit large result sets
                'result_count': len(results)
            }
            
            # Create step
            step = ReasoningStep(
                trace_id=self.current_trace.id,
                step_number=self._step_counter,
                phase_name=phase,
                step_type='ontology_query',
                input_data=input_data,
                output_data=output_data,
                processing_time=processing_time,
                entity_type=entity_type,
                query_type=query_type
            )
            
            db.session.add(step)
            db.session.commit()
            
            if self.debug_to_console:
                time_str = f" in {processing_time:.1f}s" if processing_time else ""
                print(f"🔍 Ontology {entity_type} query: {len(results)} results{time_str}")
            
            logger.info(f"Captured ontology query: {phase} ({entity_type}) -> {len(results)} results")
            return step.id
            
        except Exception as e:
            logger.error(f"Failed to capture ontology query: {e}")
            return -1
    
    def capture_algorithm_step(self, phase: str, input_data: Dict, 
                              output_data: Dict, processing_time: float = 0.0,
                              algorithm_name: str = None) -> int:
        """Capture algorithmic processing steps
        
        Args:
            phase: Name of the processing phase
            input_data: Input data for the algorithm
            output_data: Output data from the algorithm
            processing_time: Time taken for this step in seconds
            algorithm_name: Name of the algorithm used
            
        Returns:
            step_id: Database ID of created step, or -1 if failed
        """
        if not self.current_trace:
            if self.debug_to_console:
                print(f"⚠️  No active trace for algorithm step: {phase}")
            return -1
        
        try:
            self._step_counter += 1
            
            # Create step
            step = ReasoningStep(
                trace_id=self.current_trace.id,
                step_number=self._step_counter,
                phase_name=phase,
                step_type='algorithm',
                input_data=self._truncate_json_data(input_data),
                output_data=self._truncate_json_data(output_data),
                processing_time=processing_time,
                model_used=algorithm_name  # Reuse model_used field for algorithm name
            )
            
            db.session.add(step)
            db.session.commit()
            
            if self.debug_to_console:
                time_str = f" in {processing_time:.1f}s" if processing_time else ""
                print(f"⚙️  Algorithm {phase}{time_str}")
            
            logger.info(f"Captured algorithm step: {phase}")
            return step.id
            
        except Exception as e:
            logger.error(f"Failed to capture algorithm step: {e}")
            return -1
    
    def capture_preprocessing_step(self, phase: str, original_text: str, 
                                  processed_text: str, metadata: Dict,
                                  processing_time: float = 0.0) -> int:
        """Capture text preprocessing steps
        
        Args:
            phase: Name of the processing phase
            original_text: Original text before processing
            processed_text: Text after processing
            metadata: Metadata about the preprocessing (e.g., what was removed/changed)
            processing_time: Time taken for this step in seconds
            
        Returns:
            step_id: Database ID of created step, or -1 if failed
        """
        if not self.current_trace:
            if self.debug_to_console:
                print(f"⚠️  No active trace for preprocessing step: {phase}")
            return -1
        
        try:
            self._step_counter += 1
            
            # Prepare input/output data with length limits
            input_data = {
                'original_text': original_text[:3000] if len(original_text) > 3000 else original_text,
                'original_length': len(original_text),
                'preprocessing_type': metadata.get('type', 'unknown')
            }
            
            output_data = {
                'processed_text': processed_text[:3000] if len(processed_text) > 3000 else processed_text,
                'processed_length': len(processed_text),
                'changes_made': metadata
            }
            
            # Create step
            step = ReasoningStep(
                trace_id=self.current_trace.id,
                step_number=self._step_counter,
                phase_name=phase,
                step_type='preprocessing',
                input_data=input_data,
                output_data=output_data,
                processing_time=processing_time
            )
            
            db.session.add(step)
            db.session.commit()
            
            if self.debug_to_console:
                reduction = len(original_text) - len(processed_text)
                print(f"📝 Preprocessing {phase}: -{reduction} chars")
            
            logger.info(f"Captured preprocessing step: {phase}")
            return step.id
            
        except Exception as e:
            logger.error(f"Failed to capture preprocessing step: {e}")
            return -1
    
    def add_error_to_current_step(self, error_message: str, step_id: int = None):
        """Add error message to the most recent step or specified step
        
        Args:
            error_message: Error message to record
            step_id: Optional specific step ID to update
        """
        try:
            if step_id:
                step = ReasoningStep.query.get(step_id)
            else:
                # Find most recent step for current trace
                if not self.current_trace:
                    return
                step = ReasoningStep.query.filter_by(trace_id=self.current_trace.id)\
                                         .order_by(ReasoningStep.step_number.desc())\
                                         .first()
            
            if step:
                step.error_message = error_message
                db.session.commit()
                
                if self.debug_to_console:
                    print(f"❌ Error in {step.phase_name}: {error_message[:100]}")
                
                logger.warning(f"Added error to step {step.id}: {error_message}")
                
        except Exception as e:
            logger.error(f"Failed to add error to step: {e}")
    
    def complete_trace(self, status: str = 'completed') -> Optional[ReasoningTrace]:
        """Complete current trace and calculate summary statistics
        
        Args:
            status: Final status ('completed', 'failed', 'cancelled')
            
        Returns:
            The completed trace object, or None if no active trace
        """
        if not self.current_trace:
            return None
        
        try:
            # Update trace status and completion time
            self.current_trace.completed_at = datetime.utcnow()
            self.current_trace.status = status
            
            # Calculate summary statistics
            self.current_trace.calculate_statistics()
            
            if self.debug_to_console:
                print(f"✅ Completed trace {self.current_trace.session_id}: "
                      f"{self.current_trace.total_steps} steps, "
                      f"{self.current_trace.processing_time:.1f}s total")
            
            logger.info(f"Completed reasoning trace {self.current_trace.session_id} "
                       f"with {self.current_trace.total_steps} steps")
            
            completed_trace = self.current_trace
            self.current_trace = None
            self._step_counter = 0
            
            return completed_trace
            
        except Exception as e:
            logger.error(f"Failed to complete trace: {e}")
            return None
    
    def get_trace_for_ui(self, trace_id: int) -> Optional[Dict]:
        """Get complete trace with all steps formatted for UI display
        
        Args:
            trace_id: ID of the trace to retrieve
            
        Returns:
            Dictionary with trace data formatted for UI, or None if not found
        """
        try:
            trace = ReasoningTrace.query.get(trace_id)
            if not trace:
                return None
            
            # Get all steps ordered by step number
            steps = ReasoningStep.query.filter_by(trace_id=trace_id)\
                                     .order_by(ReasoningStep.step_number)\
                                     .all()
            
            # Convert to dictionaries
            trace_dict = trace.to_dict()
            steps_dict = [step.to_dict() for step in steps]
            
            # Add case information if available
            if trace.case:
                trace_dict['case'] = {
                    'id': trace.case.id,
                    'title': getattr(trace.case, 'title', f'Case {trace.case.id}'),
                    'document_type': getattr(trace.case, 'document_type', 'case')
                }
            
            return {
                'trace': trace_dict,
                'steps': steps_dict,
                'ui_metadata': {
                    'total_duration': trace.processing_time,
                    'steps_by_type': self._group_steps_by_type(steps_dict),
                    'timeline_summary': self._build_timeline_summary(steps_dict)
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get trace for UI: {e}")
            return None
    
    def _truncate_json_data(self, data: Any, max_size: int = 5000) -> Any:
        """Truncate JSON data to prevent database bloat"""
        try:
            import json
            json_str = json.dumps(data)
            
            if len(json_str) <= max_size:
                return data
            
            # For large data, store a summary instead
            if isinstance(data, dict):
                return {
                    '_truncated': True,
                    '_original_size': len(json_str),
                    '_summary': str(data)[:max_size]
                }
            elif isinstance(data, list):
                return {
                    '_truncated': True,
                    '_original_size': len(json_str),
                    '_item_count': len(data),
                    '_sample_items': data[:3] if len(data) > 3 else data
                }
            else:
                return {
                    '_truncated': True,
                    '_original_size': len(json_str),
                    '_summary': str(data)[:max_size]
                }
                
        except Exception:
            return {'_error': 'Could not serialize data'}
    
    def _group_steps_by_type(self, steps: List[Dict]) -> Dict[str, int]:
        """Group steps by type for UI summary"""
        counts = {}
        for step in steps:
            step_type = step.get('step_type', 'unknown')
            counts[step_type] = counts.get(step_type, 0) + 1
        return counts
    
    def _build_timeline_summary(self, steps: List[Dict]) -> List[str]:
        """Build a timeline summary for UI"""
        summary = []
        for step in steps[:10]:  # First 10 steps
            phase = step.get('phase_name', 'unknown')
            step_type = step.get('step_type', 'unknown')
            summary.append(f"{phase} ({step_type})")
        
        if len(steps) > 10:
            summary.append(f"... and {len(steps) - 10} more steps")
        
        return summary


# Global inspector instance for singleton access
_global_inspector: Optional[ReasoningInspector] = None


def get_reasoning_inspector() -> ReasoningInspector:
    """Get the global reasoning inspector instance (singleton pattern)"""
    global _global_inspector
    if _global_inspector is None:
        _global_inspector = ReasoningInspector()
    return _global_inspector


def start_reasoning_trace(case_id: int, feature_type: str, session_prefix: str = None) -> str:
    """Convenience function to start a reasoning trace"""
    inspector = get_reasoning_inspector()
    return inspector.start_trace(case_id, feature_type, session_prefix)


def capture_llm_call(phase: str, prompt: str, response: str, parsed_result: Any, **kwargs) -> int:
    """Convenience function to capture LLM interaction"""
    inspector = get_reasoning_inspector()
    return inspector.capture_llm_interaction(phase, prompt, response, parsed_result, **kwargs)


def capture_ontology_query(phase: str, entity_type: str, query: str, query_type: str, results: List[Dict], **kwargs) -> int:
    """Convenience function to capture ontology query"""
    inspector = get_reasoning_inspector()
    return inspector.capture_ontology_query(phase, entity_type, query, query_type, results, **kwargs)


def complete_reasoning_trace(status: str = 'completed') -> Optional[ReasoningTrace]:
    """Convenience function to complete reasoning trace"""
    inspector = get_reasoning_inspector()
    return inspector.complete_trace(status)
