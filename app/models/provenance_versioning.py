"""
PROV-O Compliant Versioning Extensions for Provenance Tracking

This module extends the base provenance models with versioning capabilities
following PROV-O standards for revision tracking (prov:wasRevisionOf).

Key PROV-O Relationships:
- prov:wasRevisionOf: Links versions of the same conceptual entity
- prov:hadPrimarySource: Links derived versions to their authoritative source
- prov:alternateOf: Links different representations of the same thing
- prov:specializationOf: Links specific versions to general concepts

Versioning Strategy:
1. Development Mode: Temporary versions with optional auto-cleanup
2. Production Mode: Permanent versions with full revision history
3. Version Consolidation: Ability to merge multiple test versions into production record
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean, Enum, Index, Float
from sqlalchemy.orm import relationship
import enum

from app.models import db


class VersionEnvironment(enum.Enum):
    """Environment types for version tracking."""
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class VersionStatus(enum.Enum):
    """Status of a version in the workflow."""
    DRAFT = "draft"           # Being developed/tested
    CANDIDATE = "candidate"   # Ready for production
    RELEASED = "released"     # In production use
    SUPERSEDED = "superseded" # Replaced by newer version
    ARCHIVED = "archived"     # No longer active but retained


class ProvenanceRevision(db.Model):
    """
    PROV-O wasRevisionOf relationship tracking.
    
    Tracks the revision history between different versions of activities or entities.
    This implements the PROV-O wasRevisionOf relationship for version tracking.
    """
    __tablename__ = 'provenance_revisions'
    
    id = Column(Integer, primary_key=True)
    
    # Revision relationship (newer wasRevisionOf older)
    newer_activity_id = Column(Integer, ForeignKey('provenance_activities.id'))
    older_activity_id = Column(Integer, ForeignKey('provenance_activities.id'))
    newer_entity_id = Column(Integer, ForeignKey('provenance_entities.id'))
    older_entity_id = Column(Integer, ForeignKey('provenance_entities.id'))
    
    # Revision metadata
    revision_type = Column(String(50), nullable=False)  # 'major', 'minor', 'patch', 'experimental'
    revision_reason = Column(Text)  # Why this revision was created
    changes_summary = Column(JSON)  # Structured summary of changes
    
    # Version tracking
    version_number = Column(String(20))  # Semantic version (e.g., "1.2.3")
    version_tag = Column(String(50))     # Tag (e.g., "v1.0-stable", "dev-20250111")
    
    # Approval and validation
    approved_by = Column(String(100))    # Who approved this revision
    approved_at = Column(DateTime)
    validation_status = Column(String(50))  # 'pending', 'validated', 'rejected'
    validation_notes = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    newer_activity = relationship('ProvenanceActivity', foreign_keys=[newer_activity_id])
    older_activity = relationship('ProvenanceActivity', foreign_keys=[older_activity_id])
    newer_entity = relationship('ProvenanceEntity', foreign_keys=[newer_entity_id])
    older_entity = relationship('ProvenanceEntity', foreign_keys=[older_entity_id])
    
    __table_args__ = (
        Index('idx_prov_revision_newer_activity', 'newer_activity_id'),
        Index('idx_prov_revision_older_activity', 'older_activity_id'),
        Index('idx_prov_revision_newer_entity', 'newer_entity_id'),
        Index('idx_prov_revision_older_entity', 'older_entity_id'),
        Index('idx_prov_revision_type', 'revision_type'),
    )


class ProvenanceVersion(db.Model):
    """
    Version management for provenance workflows.
    
    Groups related activities and entities into versioned workflows,
    enabling tracking of different implementations of the same process.
    """
    __tablename__ = 'provenance_versions'
    
    id = Column(Integer, primary_key=True)
    
    # Version identification
    workflow_name = Column(String(200), nullable=False)  # e.g., "step1a_extraction"
    version_number = Column(String(20), nullable=False)  # e.g., "1.0.0", "2.1.3"
    version_tag = Column(String(100))  # e.g., "stable", "experimental", "dev"
    
    # Environment and status (store as string values in DB)
    environment = Column(String(20), nullable=False, default='DEVELOPMENT')
    status = Column(String(20), nullable=False, default='DRAFT')
    
    # Version metadata
    description = Column(Text)  # What this version implements/changes
    implementation_notes = Column(Text)  # Technical notes about the implementation
    
    # Consolidation tracking
    is_consolidated = Column(Boolean, default=False)  # Whether this combines multiple test runs
    consolidated_from = Column(JSON)  # List of version IDs this was consolidated from
    consolidation_strategy = Column(String(100))  # How versions were consolidated
    
    # Lifecycle management
    created_at = Column(DateTime, default=datetime.utcnow)
    released_at = Column(DateTime)  # When moved to production
    superseded_at = Column(DateTime)  # When replaced by newer version
    expires_at = Column(DateTime)  # For auto-cleanup of dev versions
    
    # Performance metrics (for comparing versions)
    performance_metrics = Column(JSON)  # Token usage, accuracy, timing, etc.
    
    # Primary source tracking (prov:hadPrimarySource)
    primary_source_id = Column(Integer, ForeignKey('provenance_versions.id'))
    primary_source = relationship('ProvenanceVersion', remote_side=[id])
    
    __table_args__ = (
        Index('idx_prov_version_workflow', 'workflow_name'),
        Index('idx_prov_version_number', 'version_number'),
        Index('idx_prov_version_environment', 'environment'),
        Index('idx_prov_version_status', 'status'),
    )


class ProvenanceAlternate(db.Model):
    """
    PROV-O alternateOf relationship for tracking equivalent versions.
    
    Used when multiple versions represent the same conceptual thing
    (e.g., different test runs of the same extraction logic).
    """
    __tablename__ = 'provenance_alternates'
    
    id = Column(Integer, primary_key=True)
    
    # Entities that are alternates of each other
    entity1_id = Column(Integer, ForeignKey('provenance_entities.id'), nullable=False)
    entity2_id = Column(Integer, ForeignKey('provenance_entities.id'), nullable=False)
    
    # Alternate relationship metadata
    alternate_type = Column(String(100))  # 'equivalent', 'variant', 'test_run'
    equivalence_criteria = Column(JSON)  # What makes these alternates
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    entity1 = relationship('ProvenanceEntity', foreign_keys=[entity1_id])
    entity2 = relationship('ProvenanceEntity', foreign_keys=[entity2_id])
    
    __table_args__ = (
        Index('idx_prov_alternate_entity1', 'entity1_id'),
        Index('idx_prov_alternate_entity2', 'entity2_id'),
    )


# Extensions to existing models (added as mixins or direct modifications)

class VersionedProvenanceMixin:
    """
    Mixin to add versioning capabilities to existing provenance models.
    
    Add this to ProvenanceActivity and ProvenanceEntity models.
    """
    
    # Version tracking
    version_id = Column(Integer, ForeignKey('provenance_versions.id'))
    version_number = Column(String(20))  # Local version within this record
    version_environment = Column(Enum(VersionEnvironment), default=VersionEnvironment.DEVELOPMENT)
    version_status = Column(Enum(VersionStatus), default=VersionStatus.DRAFT)
    
    # Revision tracking (for PROV-O wasRevisionOf)
    revision_of_id = Column(Integer)  # Self-referential FK to same table
    revision_number = Column(Integer, default=1)  # Incremental revision counter
    
    # Development mode flags
    is_development = Column(Boolean, default=False)  # Mark as development/test data
    auto_cleanup = Column(Boolean, default=False)  # Should be auto-deleted
    cleanup_after = Column(DateTime)  # When to auto-delete
    
    # Consolidation support
    consolidation_group = Column(String(100))  # Group ID for records to consolidate
    consolidation_weight = Column(JSON)  # Weight/importance for consolidation


class VersionConfiguration(db.Model):
    """
    Configuration for version management behavior.
    
    Controls how versioning works for different workflows and environments.
    """
    __tablename__ = 'provenance_version_config'
    
    id = Column(Integer, primary_key=True)
    
    # Configuration scope
    workflow_name = Column(String(200), nullable=False, unique=True)
    
    # Version management rules
    auto_increment_version = Column(Boolean, default=True)
    version_pattern = Column(String(50), default="major.minor.patch")  # Semantic versioning
    
    # Development mode settings
    dev_mode_enabled = Column(Boolean, default=True)
    dev_retention_hours = Column(Integer, default=24)  # How long to keep dev versions
    auto_cleanup_dev = Column(Boolean, default=False)  # Auto-delete old dev versions
    
    # Consolidation rules
    consolidation_enabled = Column(Boolean, default=True)
    consolidation_strategy = Column(String(100), default="latest_best")  # How to merge versions
    min_versions_to_consolidate = Column(Integer, default=3)
    
    # Production promotion rules
    require_approval = Column(Boolean, default=True)
    min_test_runs = Column(Integer, default=3)  # Minimum test runs before production
    required_validation_score = Column(Float, default=0.8)  # Minimum score to promote
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)