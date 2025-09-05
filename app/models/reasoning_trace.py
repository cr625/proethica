"""
Reasoning Trace Models

Database models for capturing complete reasoning chains across all ProEthica processes.
Stores every LLM interaction, ontology query, and algorithmic step for debugging and analysis.
"""

from datetime import datetime
from sqlalchemy import func
from app.models import db


class ReasoningTrace(db.Model):
    """Captures complete reasoning chain for any ProEthica process"""
    __tablename__ = 'reasoning_traces'
    
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, nullable=False)  # Remove foreign key constraint temporarily
    feature_type = db.Column(db.String(50), nullable=False)  # 'scenario', 'annotation', 'guideline'
    session_id = db.Column(db.String(100), unique=True, index=True, nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime)
    total_steps = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='in_progress')  # 'in_progress', 'completed', 'failed'
    
    # Summary statistics
    total_llm_calls = db.Column(db.Integer, default=0)
    total_ontology_queries = db.Column(db.Integer, default=0)
    average_confidence = db.Column(db.Float)
    processing_time = db.Column(db.Float)  # Total seconds
    
    # Relationships
    steps = db.relationship('ReasoningStep', back_populates='trace', lazy='dynamic', cascade='all, delete-orphan')
    # Note: case relationship handled manually due to complex Document model structure
    
    @property
    def case(self):
        """Get the associated document/case"""
        from app.models.document import Document
        return Document.query.get(self.case_id)
    
    def __repr__(self):
        return f'<ReasoningTrace {self.session_id}: {self.feature_type} for case {self.case_id}>'
    
    def to_dict(self):
        """Convert trace to dictionary for API responses"""
        return {
            'id': self.id,
            'case_id': self.case_id,
            'feature_type': self.feature_type,
            'session_id': self.session_id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'total_steps': self.total_steps,
            'status': self.status,
            'total_llm_calls': self.total_llm_calls,
            'total_ontology_queries': self.total_ontology_queries,
            'average_confidence': self.average_confidence,
            'processing_time': self.processing_time
        }
    
    def calculate_statistics(self):
        """Calculate and update summary statistics from steps"""
        steps = self.steps.all()
        
        self.total_steps = len(steps)
        self.total_llm_calls = len([s for s in steps if s.step_type == 'llm_call'])
        self.total_ontology_queries = len([s for s in steps if s.step_type == 'ontology_query'])
        
        # Calculate average confidence from steps that have confidence scores
        confident_steps = [s for s in steps if s.confidence_score is not None]
        if confident_steps:
            self.average_confidence = sum(s.confidence_score for s in confident_steps) / len(confident_steps)
        
        # Calculate total processing time
        self.processing_time = sum(s.processing_time or 0 for s in steps)
        
        db.session.commit()


class ReasoningStep(db.Model):
    """Individual step in reasoning chain"""
    __tablename__ = 'reasoning_steps'
    
    id = db.Column(db.Integer, primary_key=True)
    trace_id = db.Column(db.Integer, db.ForeignKey('reasoning_traces.id'), nullable=False)
    step_number = db.Column(db.Integer, nullable=False)
    phase_name = db.Column(db.String(100), nullable=False)  # 'timeline_extraction', 'boundary_validation', etc.
    step_type = db.Column(db.String(50), nullable=False)  # 'llm_call', 'ontology_query', 'algorithm', 'preprocessing'
    
    # Input/Output capture
    input_data = db.Column(db.JSON)  # What was sent (prompt, query params, etc.)
    output_data = db.Column(db.JSON)  # What was received (response, results)
    processed_result = db.Column(db.JSON)  # After parsing/validation
    
    # Metadata
    confidence_score = db.Column(db.Float)
    processing_time = db.Column(db.Float)  # Seconds for this step
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    error_message = db.Column(db.Text)
    
    # LLM-specific fields
    model_used = db.Column(db.String(100))  # 'claude-3', 'gpt-4', etc.
    tokens_used = db.Column(db.Integer)
    temperature = db.Column(db.Float)
    
    # Ontology-specific fields
    entity_type = db.Column(db.String(100))  # 'Principle', 'Role', etc.
    query_type = db.Column(db.String(50))  # 'sparql', 'concept_lookup', etc.
    
    # Relationships
    trace = db.relationship('ReasoningTrace', back_populates='steps')
    
    def __repr__(self):
        return f'<ReasoningStep {self.step_number}: {self.phase_name} ({self.step_type})>'
    
    def to_dict(self):
        """Convert step to dictionary for API responses"""
        return {
            'id': self.id,
            'trace_id': self.trace_id,
            'step_number': self.step_number,
            'phase_name': self.phase_name,
            'step_type': self.step_type,
            'input_data': self.input_data,
            'output_data': self.output_data,
            'processed_result': self.processed_result,
            'confidence_score': self.confidence_score,
            'processing_time': self.processing_time,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'error_message': self.error_message,
            'model_used': self.model_used,
            'tokens_used': self.tokens_used,
            'temperature': self.temperature,
            'entity_type': self.entity_type,
            'query_type': self.query_type
        }
    
    @property
    def duration_display(self):
        """Human-readable processing time"""
        if not self.processing_time:
            return "0.0s"
        return f"{self.processing_time:.1f}s"
    
    @property
    def confidence_display(self):
        """Human-readable confidence score"""
        if not self.confidence_score:
            return "N/A"
        return f"{int(self.confidence_score * 100)}%"
    
    @property
    def step_icon(self):
        """Icon for display based on step type"""
        icons = {
            'llm_call': '🤖',
            'ontology_query': '🔍',
            'algorithm': '⚙️',
            'preprocessing': '📝'
        }
        return icons.get(self.step_type, '📋')


# Add indexes for better query performance
db.Index('idx_reasoning_traces_case_id', ReasoningTrace.case_id)
db.Index('idx_reasoning_traces_feature_type', ReasoningTrace.feature_type)
db.Index('idx_reasoning_traces_status', ReasoningTrace.status)
db.Index('idx_reasoning_traces_started_at', ReasoningTrace.started_at)

db.Index('idx_reasoning_steps_trace_id', ReasoningStep.trace_id)
db.Index('idx_reasoning_steps_step_number', ReasoningStep.step_number)
db.Index('idx_reasoning_steps_step_type', ReasoningStep.step_type)
db.Index('idx_reasoning_steps_timestamp', ReasoningStep.timestamp)
