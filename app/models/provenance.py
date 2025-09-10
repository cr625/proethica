"""
PROV-O Provenance Models for ProEthica LLM Interactions

Based on the OntExtract paper's PROV-O implementation, this module provides
provenance tracking for all LLM interactions, extraction operations, and
analytical workflows in ProEthica.

PROV-O Elements Tracked:
- prov:Agent: LLMs (Claude, GPT-4, Gemini), extraction services, users
- prov:Activity: Extraction operations, LLM queries, analysis steps
- prov:Entity: Prompts, responses, extracted concepts, analysis results
- prov:wasGeneratedBy: Links outputs to the activities that created them
- prov:wasDerivedFrom: Tracks lineage between entities
- prov:wasAssociatedWith: Links activities to agents
- prov:used: Records inputs to activities
- prov:wasInformedBy: Captures activity dependencies
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Float, Boolean, Index
from sqlalchemy.orm import relationship
from app.models import db

class ProvenanceAgent(db.Model):
    """
    PROV-O Agent: Represents entities that perform activities.
    Examples: Users, LLM models (Claude, GPT-4), extraction services
    """
    __tablename__ = 'provenance_agents'
    
    id = Column(Integer, primary_key=True)
    agent_type = Column(String(50), nullable=False)  # 'user', 'llm_model', 'extraction_service', 'system'
    agent_name = Column(String(200), nullable=False)  # e.g., 'claude-3-opus', 'RolesExtractor', 'user_42'
    agent_version = Column(String(50))  # Model version or service version
    agent_metadata = Column(JSON)  # Additional agent details (API keys hash, config, etc.)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    activities = relationship('ProvenanceActivity', back_populates='agent')
    
    __table_args__ = (
        Index('idx_prov_agent_type', 'agent_type'),
        Index('idx_prov_agent_name', 'agent_name'),
    )


class ProvenanceActivity(db.Model):
    """
    PROV-O Activity: Represents operations that use and generate entities.
    Examples: Prompt execution, extraction operation, analysis step
    """
    __tablename__ = 'provenance_activities'
    
    id = Column(Integer, primary_key=True)
    activity_type = Column(String(100), nullable=False)  # 'llm_query', 'extraction', 'analysis', 'synthesis'
    activity_name = Column(String(200), nullable=False)  # e.g., 'entities_pass_extraction', 'role_extraction'
    case_id = Column(Integer, ForeignKey('documents.id'))  # Associated case/document
    session_id = Column(String(255))  # Session identifier for grouping related activities
    
    # Timing
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime)
    duration_ms = Column(Integer)  # Duration in milliseconds
    
    # Agent association (wasAssociatedWith)
    agent_id = Column(Integer, ForeignKey('provenance_agents.id'), nullable=False)
    
    # Plan/Strategy (hadPlan via metadata)
    execution_plan = Column(JSON)  # Execution strategy, parameters, config
    
    # Activity metadata
    activity_metadata = Column(JSON)  # Additional context (temperature, model params, etc.)
    
    # Status and error tracking
    status = Column(String(50), default='started')  # 'started', 'completed', 'failed'
    error_message = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    agent = relationship('ProvenanceAgent', back_populates='activities')
    entities = relationship('ProvenanceEntity', back_populates='generating_activity')
    used_entities = relationship('ProvenanceUsage', back_populates='activity')
    informed_by = relationship('ProvenanceCommunication', 
                               foreign_keys='ProvenanceCommunication.informed_activity_id',
                               back_populates='informed_activity')
    informs = relationship('ProvenanceCommunication',
                           foreign_keys='ProvenanceCommunication.informing_activity_id', 
                           back_populates='informing_activity')
    
    __table_args__ = (
        Index('idx_prov_activity_type', 'activity_type'),
        Index('idx_prov_activity_case', 'case_id'),
        Index('idx_prov_activity_session', 'session_id'),
        Index('idx_prov_activity_status', 'status'),
    )


class ProvenanceEntity(db.Model):
    """
    PROV-O Entity: Represents data objects that are used and generated.
    Examples: Prompts, responses, extracted concepts, analysis results
    """
    __tablename__ = 'provenance_entities'
    
    id = Column(Integer, primary_key=True)
    entity_type = Column(String(100), nullable=False)  # 'prompt', 'response', 'extracted_roles', 'extracted_resources'
    entity_name = Column(String(200), nullable=False)  # Descriptive name
    case_id = Column(Integer, ForeignKey('documents.id'))  # Associated case/document
    
    # Content storage
    content = Column(Text)  # The actual prompt text, response text, or serialized data
    content_hash = Column(String(64))  # SHA-256 hash for integrity
    content_size = Column(Integer)  # Size in bytes
    
    # Generation tracking (wasGeneratedBy)
    generating_activity_id = Column(Integer, ForeignKey('provenance_activities.id'))
    generation_time = Column(DateTime)
    
    # Confidence and quality metrics
    confidence_score = Column(Float)  # For extracted entities
    quality_metrics = Column(JSON)  # Additional quality indicators
    
    # Entity metadata
    entity_metadata = Column(JSON)  # Type-specific metadata (token counts, model used, etc.)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    generating_activity = relationship('ProvenanceActivity', back_populates='entities')
    derived_from = relationship('ProvenanceDerivation',
                                foreign_keys='ProvenanceDerivation.derived_entity_id',
                                back_populates='derived_entity')
    derives = relationship('ProvenanceDerivation',
                          foreign_keys='ProvenanceDerivation.source_entity_id',
                          back_populates='source_entity')
    used_by = relationship('ProvenanceUsage', back_populates='entity')
    
    __table_args__ = (
        Index('idx_prov_entity_type', 'entity_type'),
        Index('idx_prov_entity_case', 'case_id'),
        Index('idx_prov_entity_hash', 'content_hash'),
    )


class ProvenanceDerivation(db.Model):
    """
    PROV-O wasDerivedFrom: Tracks lineage between entities.
    Example: Response derived from prompt, synthesis derived from extractions
    """
    __tablename__ = 'provenance_derivations'
    
    id = Column(Integer, primary_key=True)
    derived_entity_id = Column(Integer, ForeignKey('provenance_entities.id'), nullable=False)
    source_entity_id = Column(Integer, ForeignKey('provenance_entities.id'), nullable=False)
    derivation_type = Column(String(100))  # 'transformation', 'extraction', 'synthesis'
    derivation_metadata = Column(JSON)  # Additional context about the derivation
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    derived_entity = relationship('ProvenanceEntity', foreign_keys=[derived_entity_id], back_populates='derived_from')
    source_entity = relationship('ProvenanceEntity', foreign_keys=[source_entity_id], back_populates='derives')
    
    __table_args__ = (
        Index('idx_prov_derivation_derived', 'derived_entity_id'),
        Index('idx_prov_derivation_source', 'source_entity_id'),
    )


class ProvenanceUsage(db.Model):
    """
    PROV-O used: Records which entities were used by activities.
    Example: Extraction activity used prompt entity
    """
    __tablename__ = 'provenance_usage'
    
    id = Column(Integer, primary_key=True)
    activity_id = Column(Integer, ForeignKey('provenance_activities.id'), nullable=False)
    entity_id = Column(Integer, ForeignKey('provenance_entities.id'), nullable=False)
    usage_role = Column(String(100))  # 'input', 'reference', 'context'
    usage_metadata = Column(JSON)  # Additional usage context
    used_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    activity = relationship('ProvenanceActivity', back_populates='used_entities')
    entity = relationship('ProvenanceEntity', back_populates='used_by')
    
    __table_args__ = (
        Index('idx_prov_usage_activity', 'activity_id'),
        Index('idx_prov_usage_entity', 'entity_id'),
    )


class ProvenanceCommunication(db.Model):
    """
    PROV-O wasInformedBy: Captures dependencies between activities.
    Example: Synthesis activity was informed by extraction activity
    """
    __tablename__ = 'provenance_communications'
    
    id = Column(Integer, primary_key=True)
    informed_activity_id = Column(Integer, ForeignKey('provenance_activities.id'), nullable=False)
    informing_activity_id = Column(Integer, ForeignKey('provenance_activities.id'), nullable=False)
    communication_type = Column(String(100))  # 'dependency', 'sequence', 'trigger'
    communication_metadata = Column(JSON)  # Additional context
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    informed_activity = relationship('ProvenanceActivity', foreign_keys=[informed_activity_id], back_populates='informed_by')
    informing_activity = relationship('ProvenanceActivity', foreign_keys=[informing_activity_id], back_populates='informs')
    
    __table_args__ = (
        Index('idx_prov_comm_informed', 'informed_activity_id'),
        Index('idx_prov_comm_informing', 'informing_activity_id'),
    )


class ProvenanceBundle(db.Model):
    """
    Groups related provenance records for a complete workflow.
    Example: All provenance for a single extraction pass
    """
    __tablename__ = 'provenance_bundles'
    
    id = Column(Integer, primary_key=True)
    bundle_name = Column(String(200), nullable=False)
    bundle_type = Column(String(100))  # 'extraction_workflow', 'analysis_session'
    case_id = Column(Integer, ForeignKey('documents.id'))
    session_id = Column(String(255))
    
    # Bundle metadata
    bundle_metadata = Column(JSON)
    
    # Timing
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_prov_bundle_case', 'case_id'),
        Index('idx_prov_bundle_session', 'session_id'),
    )