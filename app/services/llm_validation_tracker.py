"""
LLM Validation Tracker: Track and log LLM feedback during temporal reasoning validation.

This service captures abbreviated LLM feedback at each validation phase for:
- Debugging and monitoring LLM reasoning quality
- Understanding how validation improves results
- Tracking confidence and reasoning patterns
- Providing insights for system improvement
"""

import logging
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

@dataclass
class LLMValidationFeedback:
    """Structured feedback from LLM validation step."""
    validation_phase: str
    case_id: int
    timestamp: datetime
    confidence_score: float
    key_insights: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    improvements_suggested: List[str] = field(default_factory=list)
    validation_status: str = "success"  # success, failed, partial
    processing_time: float = 0.0  # seconds
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'validation_phase': self.validation_phase,
            'case_id': self.case_id,
            'timestamp': self.timestamp.isoformat(),
            'confidence_score': self.confidence_score,
            'key_insights': self.key_insights,
            'warnings': self.warnings,
            'improvements_suggested': self.improvements_suggested,
            'validation_status': self.validation_status,
            'processing_time': self.processing_time
        }


@dataclass 
class LLMValidationSession:
    """Complete LLM validation session for a case."""
    session_id: str
    case_id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    feedbacks: List[LLMValidationFeedback] = field(default_factory=list)
    session_status: str = "in_progress"  # in_progress, completed, failed
    total_processing_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'case_id': self.case_id,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'feedbacks': [f.to_dict() for f in self.feedbacks],
            'session_status': self.session_status,
            'total_processing_time': self.total_processing_time,
            'phases_completed': len(self.feedbacks),
            'average_confidence': sum(f.confidence_score for f in self.feedbacks) / len(self.feedbacks) if self.feedbacks else 0.0
        }


class LLMValidationTracker:
    """Service for tracking and logging LLM validation feedback."""
    
    def __init__(self):
        self.current_session: Optional[LLMValidationSession] = None
        self.log_directory = self._setup_log_directory()
        
    def _setup_log_directory(self) -> str:
        """Set up directory for LLM validation logs."""
        log_dir = os.path.join(os.path.dirname(__file__), "../..", "logs", "llm_validation")
        os.makedirs(log_dir, exist_ok=True)
        return log_dir
    
    def start_validation_session(self, case_id: int) -> str:
        """Start a new LLM validation session."""
        session_id = f"llm_validation_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.current_session = LLMValidationSession(
            session_id=session_id,
            case_id=case_id,
            started_at=datetime.now(timezone.utc)
        )
        
        logger.info(f"Started LLM validation session: {session_id}")
        print(f"📝 Starting LLM validation session: {session_id}")
        return session_id
    
    def log_phase_feedback(self, phase_name: str, validation_data: Dict[str, Any], 
                          processing_time: float = 0.0) -> None:
        """Log feedback from a specific validation phase."""
        if not self.current_session:
            logger.warning("No active validation session - cannot log feedback")
            return
        
        # Extract abbreviated insights from validation data
        insights = self._extract_key_insights(phase_name, validation_data)
        warnings = self._extract_warnings(phase_name, validation_data)
        improvements = self._extract_improvements(phase_name, validation_data)
        confidence = self._extract_confidence(phase_name, validation_data)
        
        feedback = LLMValidationFeedback(
            validation_phase=phase_name,
            case_id=self.current_session.case_id,
            timestamp=datetime.now(timezone.utc),
            confidence_score=confidence,
            key_insights=insights,
            warnings=warnings,
            improvements_suggested=improvements,
            validation_status="success" if validation_data else "failed",
            processing_time=processing_time
        )
        
        self.current_session.feedbacks.append(feedback)
        
        # Log abbreviated feedback
        logger.info(f"LLM Phase {phase_name}: confidence={confidence:.2f}, "
                   f"insights={len(insights)}, warnings={len(warnings)}")
        
        # Print abbreviated feedback to console for immediate visibility
        print(f"🤖 LLM {phase_name}: {insights[0] if insights else 'Processing complete'}")
        if warnings:
            print(f"⚠️  LLM Warning: {warnings[0]}")
        if improvements and len(improvements) > 0:
            print(f"💡 LLM Suggestion: {improvements[0]}")
    
    def complete_validation_session(self) -> Optional[LLMValidationSession]:
        """Complete the current validation session and save to log."""
        if not self.current_session:
            return None
        
        self.current_session.completed_at = datetime.now(timezone.utc)
        self.current_session.session_status = "completed"
        self.current_session.total_processing_time = sum(f.processing_time for f in self.current_session.feedbacks)
        
        # Save session to log file
        self._save_session_log(self.current_session)
        
        # Log session summary
        session = self.current_session
        avg_confidence = session.to_dict()['average_confidence']
        logger.info(f"Completed LLM validation session {session.session_id}: "
                   f"{len(session.feedbacks)} phases, avg_confidence={avg_confidence:.2f}")
        
        # Print session summary
        print(f"\n📋 LLM Validation Complete:")
        print(f"   - Phases: {len(session.feedbacks)}")
        print(f"   - Avg Confidence: {avg_confidence:.2f}")
        print(f"   - Processing Time: {session.total_processing_time:.1f}s")
        
        completed_session = self.current_session
        self.current_session = None
        return completed_session
    
    def _extract_key_insights(self, phase_name: str, validation_data: Dict[str, Any]) -> List[str]:
        """Extract key insights from LLM validation data."""
        insights = []
        
        if phase_name == "boundary_extraction":
            assessment = validation_data.get('overall_assessment', '')
            if assessment:
                insights.append(f"Boundaries: {assessment[:80]}")
                
        elif phase_name == "temporal_relations":
            consistency = validation_data.get('consistency_check', '')
            if consistency:
                insights.append(f"Relations: {consistency[:80]}")
                
        elif phase_name == "process_profile":
            narrative = validation_data.get('narrative_summary', '')
            if narrative:
                insights.append(f"Narrative: {narrative[:80]}")
            
        elif phase_name == "agent_succession":
            dynamics = validation_data.get('stakeholder_dynamics', '')
            if dynamics:
                insights.append(f"Dynamics: {dynamics[:80]}")
                
        elif phase_name == "event_enhancement":
            enhancement_val = validation_data.get('enhancement_validation', {})
            quality = enhancement_val.get('overall_enhancement_quality', 0)
            insights.append(f"Enhancement quality: {quality:.2f}")
        
        # Generic fallback
        if not insights:
            for key in ['reasoning', 'assessment', 'summary']:
                if key in validation_data and validation_data[key]:
                    insights.append(f"{str(validation_data[key])[:60]}")
                    break
        
        return insights
    
    def _extract_warnings(self, phase_name: str, validation_data: Dict[str, Any]) -> List[str]:
        """Extract warnings from LLM validation data."""
        warnings = []
        
        if phase_name == "boundary_extraction":
            false_positives = validation_data.get('false_positives', [])
            missing = validation_data.get('missing_boundaries', [])
            
            if false_positives:
                warnings.append(f"False positives: {len(false_positives)}")
            if missing:
                warnings.append(f"Missing boundaries: {len(missing)}")
                
        elif phase_name == "temporal_relations":
            contradictions = validation_data.get('logical_contradictions', [])
            if contradictions:
                warnings.append(f"Contradictions: {len(contradictions)}")
        
        return warnings
    
    def _extract_improvements(self, phase_name: str, validation_data: Dict[str, Any]) -> List[str]:
        """Extract improvement suggestions from LLM validation data."""
        improvements = []
        
        improvement_keys = ['suggested_adjustments', 'suggestions', 'improvements', 
                           'recommendations', 'suggested_improvements']
        
        for key in improvement_keys:
            if key in validation_data:
                value = validation_data[key]
                if isinstance(value, list) and value:
                    improvements.extend([str(item)[:60] for item in value[:2]])
                elif isinstance(value, dict):
                    for subkey, subval in value.items():
                        if isinstance(subval, list) and subval:
                            improvements.append(f"{subkey}: {str(subval[0])[:50]}")
                elif isinstance(value, str):
                    improvements.append(value[:60])
                break
        
        return improvements[:3]
    
    def _extract_confidence(self, phase_name: str, validation_data: Dict[str, Any]) -> float:
        """Extract confidence score from LLM validation data."""
        confidence_keys = ['confidence', 'overall_coherence', 'overall_enhancement_quality']
        
        for key in confidence_keys:
            if key in validation_data:
                try:
                    return float(validation_data[key])
                except (ValueError, TypeError):
                    continue
        
        return 0.7 if validation_data else 0.0
    
    def _save_session_log(self, session: LLMValidationSession) -> None:
        """Save session log to file."""
        try:
            log_filename = f"{session.session_id}.json"
            log_filepath = os.path.join(self.log_directory, log_filename)
            
            with open(log_filepath, 'w') as f:
                json.dump(session.to_dict(), f, indent=2, default=str)
            
            logger.info(f"Saved LLM validation log: {log_filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save LLM validation log: {e}")


# Global tracker instance
_global_tracker = None

def get_llm_validation_tracker() -> LLMValidationTracker:
    """Get the global LLM validation tracker instance."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = LLMValidationTracker()
    return _global_tracker
