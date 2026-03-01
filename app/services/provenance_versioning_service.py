"""
Enhanced Provenance Service with PROV-O Compliant Versioning

This service extends the base ProvenanceService with versioning capabilities,
enabling tracking of multiple versions of extraction implementations and
consolidation of test runs into production records.
"""

import os
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models import db
from app.models.provenance import (
    ProvenanceAgent, ProvenanceActivity, ProvenanceEntity,
    ProvenanceDerivation, ProvenanceUsage, ProvenanceCommunication,
    ProvenanceBundle, VersionEnvironment, VersionStatus
)
from app.models.provenance_versioning import (
    ProvenanceRevision, ProvenanceVersion, ProvenanceAlternate,
    VersionConfiguration
)
from app.services.provenance_service import ProvenanceService


class VersionedProvenanceService(ProvenanceService):
    """
    Extended provenance service with versioning capabilities.
    
    Features:
    - Automatic version tracking for activities and entities
    - Development/production mode management
    - Version consolidation for merging test runs
    - PROV-O compliant revision relationships
    """
    
    def __init__(self, session: Optional[Session] = None):
        """Initialize the versioned provenance service."""
        super().__init__(session)
        self._current_version = None
        self._version_config = None
        self._environment = self._detect_environment()
    
    def _detect_environment(self) -> VersionEnvironment:
        """Detect the current environment from configuration."""
        env = os.getenv('PROVENANCE_ENVIRONMENT', 'development').lower()
        
        env_map = {
            'development': VersionEnvironment.DEVELOPMENT,
            'dev': VersionEnvironment.DEVELOPMENT,
            'test': VersionEnvironment.TEST,
            'staging': VersionEnvironment.STAGING,
            'production': VersionEnvironment.PRODUCTION,
            'prod': VersionEnvironment.PRODUCTION
        }
        
        return env_map.get(env, VersionEnvironment.DEVELOPMENT)
    
    def _get_enum_value(self, enum_val):
        """Get the string value from an enum, handling both enum and string inputs."""
        if hasattr(enum_val, 'value'):
            # It's an enum, get the value but uppercase it
            return enum_val.value.upper()
        # It's already a string, just uppercase it
        return str(enum_val).upper()
    
    def get_or_create_version_config(self, workflow_name: str) -> VersionConfiguration:
        """Get or create version configuration for a workflow."""
        config = VersionConfiguration.query.filter_by(
            workflow_name=workflow_name
        ).first()
        
        if not config:
            # Create default configuration
            config = VersionConfiguration(
                workflow_name=workflow_name,
                auto_increment_version=True,
                version_pattern="major.minor.patch",
                dev_mode_enabled=(self._environment == VersionEnvironment.DEVELOPMENT),
                dev_retention_hours=24,
                auto_cleanup_dev=False,
                consolidation_enabled=True,
                consolidation_strategy="latest_best",
                min_versions_to_consolidate=3,
                require_approval=(self._environment == VersionEnvironment.PRODUCTION),
                min_test_runs=3,
                required_validation_score=0.8
            )
            self.session.add(config)
            self.session.flush()
        
        return config
    
    @contextmanager
    def track_versioned_workflow(self, workflow_name: str, 
                                description: Optional[str] = None,
                                version_tag: Optional[str] = None,
                                auto_version: bool = True):
        """
        Context manager for tracking a versioned workflow.
        
        Args:
            workflow_name: Name of the workflow (e.g., "step1a_extraction")
            description: Description of this version
            version_tag: Optional tag for the version
            auto_version: Automatically increment version number
            
        Yields:
            ProvenanceVersion instance
        """
        # Get configuration
        config = self.get_or_create_version_config(workflow_name)
        self._version_config = config
        
        # Determine version number
        if auto_version and config.auto_increment_version:
            version_number = self._get_next_version_number(workflow_name)
        else:
            version_number = version_tag or "0.0.1"
        
        # Create version record
        version = ProvenanceVersion(
            workflow_name=workflow_name,
            version_number=version_number,
            version_tag=version_tag or ("dev" if self._environment == VersionEnvironment.DEVELOPMENT else "stable"),
            environment=self._environment.value.upper(),  # Use uppercase value for string
            status=VersionStatus.DRAFT.value.upper() if self._environment == VersionEnvironment.DEVELOPMENT else VersionStatus.CANDIDATE.value.upper(),
            description=description,
            is_consolidated=False
        )
        
        # Set expiration for development versions
        if self._environment == VersionEnvironment.DEVELOPMENT and config.auto_cleanup_dev:
            version.expires_at = datetime.utcnow() + timedelta(hours=config.dev_retention_hours)
        
        self.session.add(version)
        self.session.flush()
        
        self._current_version = version
        
        try:
            yield version
            # Success - update status
            if self._environment == VersionEnvironment.PRODUCTION:
                version.status = VersionStatus.RELEASED.value.upper()
                version.released_at = datetime.utcnow()
        except Exception as e:
            # Failure - mark version as failed
            version.status = VersionStatus.ARCHIVED.value.upper()
            raise
        finally:
            self.session.flush()
            self._current_version = None
    
    def _get_next_version_number(self, workflow_name: str) -> str:
        """Calculate the next version number for a workflow."""
        latest = ProvenanceVersion.query.filter_by(
            workflow_name=workflow_name,
            environment=self._environment.value.upper()  # Use uppercase value to get string
        ).order_by(ProvenanceVersion.created_at.desc()).first()
        
        if not latest:
            return "1.0.0" if self._environment == VersionEnvironment.PRODUCTION else "0.1.0"
        
        # Parse semantic version
        parts = latest.version_number.split('.')
        if len(parts) != 3:
            return "1.0.0"
        
        try:
            major, minor, patch = map(int, parts)
            
            # Increment based on environment
            if self._environment == VersionEnvironment.PRODUCTION:
                minor += 1  # Increment minor version for production
                patch = 0
            else:
                patch += 1  # Increment patch version for development
            
            return f"{major}.{minor}.{patch}"
        except ValueError:
            return "1.0.0"
    
    @contextmanager
    def track_activity(self, activity_type: str, activity_name: str,
                      case_id: Optional[int] = None,
                      session_id: Optional[str] = None,
                      agent_type: str = 'system',
                      agent_name: str = 'proethica',
                      execution_plan: Optional[Dict] = None,
                      revision_of: Optional[ProvenanceActivity] = None):
        """
        Enhanced activity tracking with versioning support.
        
        Additional Args:
            revision_of: Previous activity this is a revision of
        """
        # Get or create agent
        agent = self.get_or_create_agent(agent_type, agent_name)
        
        # Create activity with versioning
        activity = ProvenanceActivity(
            activity_type=activity_type,
            activity_name=activity_name,
            case_id=case_id,
            session_id=session_id,
            agent_id=agent.id,
            execution_plan=execution_plan or {},
            started_at=datetime.utcnow(),
            status='started',
            # Version tracking
            version_id=self._current_version.id if self._current_version else None,
            version_number=self._current_version.version_number if self._current_version else None,
            version_environment=self._environment.value.upper(),  # Use uppercase value for string
            version_status=VersionStatus.DRAFT.value.upper() if self._environment == VersionEnvironment.DEVELOPMENT else VersionStatus.CANDIDATE.value.upper(),
            is_development=(self._environment == VersionEnvironment.DEVELOPMENT)
        )
        
        # Handle revision relationship
        if revision_of:
            activity.revision_of_id = revision_of.id
            activity.revision_number = (revision_of.revision_number or 0) + 1
            
            # Create PROV-O revision record
            revision = ProvenanceRevision(
                newer_activity_id=activity.id,
                older_activity_id=revision_of.id,
                revision_type='minor' if self._environment == VersionEnvironment.DEVELOPMENT else 'major',
                revision_reason=f"Version {activity.version_number} of {activity_name}",
                version_number=activity.version_number,
                version_tag=self._current_version.version_tag if self._current_version else None
            )
            self.session.add(revision)
        
        # Set cleanup if in development mode
        if self._environment == VersionEnvironment.DEVELOPMENT and self._version_config:
            if self._version_config.auto_cleanup_dev:
                activity.auto_cleanup = True
                activity.cleanup_after = datetime.utcnow() + timedelta(
                    hours=self._version_config.dev_retention_hours
                )
        
        self.session.add(activity)
        self.session.flush()
        
        try:
            yield activity
            # Success - mark as completed
            activity.ended_at = datetime.utcnow()
            activity.duration_ms = int((activity.ended_at - activity.started_at).total_seconds() * 1000)
            activity.status = 'completed'
            
            # Update version status
            if self._environment == VersionEnvironment.PRODUCTION:
                activity.version_status = VersionStatus.RELEASED.value.upper()
            elif self._environment == VersionEnvironment.TEST:
                activity.version_status = VersionStatus.CANDIDATE.value.upper()
        except Exception as e:
            # Failure - mark as failed
            activity.ended_at = datetime.utcnow()
            activity.duration_ms = int((activity.ended_at - activity.started_at).total_seconds() * 1000)
            activity.status = 'failed'
            activity.error_message = str(e)
            activity.version_status = VersionStatus.ARCHIVED.value.upper()
            raise
        finally:
            self.session.flush()
    
    def consolidate_versions(self, workflow_name: str, 
                           version_ids: List[int],
                           consolidation_strategy: Optional[str] = None) -> ProvenanceVersion:
        """
        Consolidate multiple test versions into a single production version.
        
        Args:
            workflow_name: Name of the workflow
            version_ids: List of version IDs to consolidate
            consolidation_strategy: Strategy for consolidation (default from config)
            
        Returns:
            Consolidated ProvenanceVersion
        """
        config = self.get_or_create_version_config(workflow_name)
        strategy = consolidation_strategy or config.consolidation_strategy
        
        # Get versions to consolidate
        versions = ProvenanceVersion.query.filter(
            ProvenanceVersion.id.in_(version_ids)
        ).all()
        
        if len(versions) < config.min_versions_to_consolidate:
            raise ValueError(f"Need at least {config.min_versions_to_consolidate} versions to consolidate")
        
        # Create consolidated version
        consolidated = ProvenanceVersion(
            workflow_name=workflow_name,
            version_number=self._get_next_version_number(workflow_name),
            version_tag="consolidated",
            environment=VersionEnvironment.PRODUCTION.value.upper(),  # Use uppercase value
            status=VersionStatus.CANDIDATE.value.upper(),
            description=f"Consolidated from {len(versions)} test versions",
            is_consolidated=True,
            consolidated_from=version_ids,
            consolidation_strategy=strategy
        )
        
        # Calculate consolidated metrics
        metrics = self._calculate_consolidated_metrics(versions, strategy)
        consolidated.performance_metrics = metrics
        
        self.session.add(consolidated)
        self.session.flush()
        
        # Create activities for consolidated version based on strategy
        if strategy == "latest_best":
            self._consolidate_latest_best(versions, consolidated)
        elif strategy == "average":
            self._consolidate_average(versions, consolidated)
        elif strategy == "union":
            self._consolidate_union(versions, consolidated)
        
        # Mark source versions as superseded
        for version in versions:
            version.status = VersionStatus.SUPERSEDED.value.upper()
            version.superseded_at = datetime.utcnow()
        
        self.session.flush()
        return consolidated
    
    def _calculate_consolidated_metrics(self, versions: List[ProvenanceVersion], 
                                       strategy: str) -> Dict[str, Any]:
        """Calculate performance metrics for consolidated version."""
        metrics = {
            'source_versions': len(versions),
            'consolidation_strategy': strategy,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Aggregate performance metrics from source versions
        token_counts = []
        durations = []
        accuracy_scores = []
        
        for version in versions:
            if version.performance_metrics:
                if 'token_count' in version.performance_metrics:
                    token_counts.append(version.performance_metrics['token_count'])
                if 'duration_ms' in version.performance_metrics:
                    durations.append(version.performance_metrics['duration_ms'])
                if 'accuracy' in version.performance_metrics:
                    accuracy_scores.append(version.performance_metrics['accuracy'])
        
        if token_counts:
            metrics['avg_token_count'] = sum(token_counts) / len(token_counts)
            metrics['min_token_count'] = min(token_counts)
            metrics['max_token_count'] = max(token_counts)
        
        if durations:
            metrics['avg_duration_ms'] = sum(durations) / len(durations)
            metrics['min_duration_ms'] = min(durations)
            metrics['max_duration_ms'] = max(durations)
        
        if accuracy_scores:
            metrics['avg_accuracy'] = sum(accuracy_scores) / len(accuracy_scores)
            metrics['best_accuracy'] = max(accuracy_scores)
        
        return metrics
    
    def _consolidate_latest_best(self, versions: List[ProvenanceVersion], 
                                consolidated: ProvenanceVersion):
        """Consolidate using the latest best-performing version."""
        # Find best performing version
        best_version = max(versions, key=lambda v: 
                          v.performance_metrics.get('accuracy', 0) if v.performance_metrics else 0)
        
        # Copy activities from best version to consolidated
        activities = ProvenanceActivity.query.filter_by(
            version_id=best_version.id
        ).all()
        
        for activity in activities:
            # Create new activity for consolidated version
            new_activity = ProvenanceActivity(
                activity_type=activity.activity_type,
                activity_name=activity.activity_name,
                case_id=activity.case_id,
                session_id=activity.session_id,
                agent_id=activity.agent_id,
                execution_plan=activity.execution_plan,
                started_at=activity.started_at,
                ended_at=activity.ended_at,
                duration_ms=activity.duration_ms,
                status=activity.status,
                version_id=consolidated.id,
                version_number=consolidated.version_number,
                version_environment=VersionEnvironment.PRODUCTION.value.upper(),
                version_status=VersionStatus.CANDIDATE.value.upper(),
                revision_of_id=activity.id,
                revision_number=(activity.revision_number or 0) + 1
            )
            self.session.add(new_activity)
            
            # Create revision record
            revision = ProvenanceRevision(
                newer_activity_id=new_activity.id,
                older_activity_id=activity.id,
                revision_type='consolidation',
                revision_reason=f"Consolidated from version {best_version.version_number}",
                version_number=consolidated.version_number
            )
            self.session.add(revision)
    
    def _consolidate_average(self, versions: List[ProvenanceVersion], 
                            consolidated: ProvenanceVersion):
        """Consolidate by averaging results across versions."""
        # This would aggregate and average extraction results
        # Implementation depends on specific use case
        pass
    
    def _consolidate_union(self, versions: List[ProvenanceVersion], 
                          consolidated: ProvenanceVersion):
        """Consolidate by taking union of all results."""
        # This would combine all unique results from all versions
        # Implementation depends on specific use case
        pass
    
    def mark_as_production(self, version_id: int, approved_by: Optional[str] = None) -> ProvenanceVersion:
        """
        Promote a version to production status.
        
        Args:
            version_id: ID of the version to promote
            approved_by: Who approved the promotion
            
        Returns:
            Updated ProvenanceVersion
        """
        version = ProvenanceVersion.query.get_or_404(version_id)
        config = self.get_or_create_version_config(version.workflow_name)
        
        # Check requirements
        if config.require_approval and not approved_by:
            raise ValueError("Approval required for production promotion")
        
        # Count test runs
        test_runs = ProvenanceActivity.query.filter_by(
            version_id=version_id,
            status='completed'
        ).count()
        
        if test_runs < config.min_test_runs:
            raise ValueError(f"Need at least {config.min_test_runs} successful test runs")
        
        # Update version status
        version.status = VersionStatus.RELEASED.value.upper()
        version.environment = VersionEnvironment.PRODUCTION.value.upper()
        version.released_at = datetime.utcnow()
        
        # Update all activities and entities
        ProvenanceActivity.query.filter_by(version_id=version_id).update({
            'version_environment': VersionEnvironment.PRODUCTION.value.upper(),
            'version_status': VersionStatus.RELEASED.value.upper(),
            'is_development': False,
            'auto_cleanup': False
        })
        
        ProvenanceEntity.query.filter_by(version_id=version_id).update({
            'version_environment': VersionEnvironment.PRODUCTION.value.upper(),
            'version_status': VersionStatus.RELEASED.value.upper(),
            'is_development': False,
            'auto_cleanup': False
        })
        
        self.session.flush()
        return version
    
    def cleanup_development_versions(self, force: bool = False) -> int:
        """
        Clean up expired development versions.
        
        Args:
            force: Force cleanup regardless of expiration
            
        Returns:
            Number of records cleaned up
        """
        count = 0
        
        # Find expired versions
        query = ProvenanceVersion.query.filter(
            ProvenanceVersion.environment == VersionEnvironment.DEVELOPMENT.value.upper(),
            ProvenanceVersion.expires_at <= datetime.utcnow() if not force else True
        )
        
        versions = query.all()
        
        for version in versions:
            # Delete associated activities and entities
            activities = ProvenanceActivity.query.filter_by(version_id=version.id).all()
            entities = ProvenanceEntity.query.filter_by(version_id=version.id).all()
            
            for activity in activities:
                self.session.delete(activity)
                count += 1
            
            for entity in entities:
                self.session.delete(entity)
                count += 1
            
            self.session.delete(version)
            count += 1
        
        self.session.flush()
        return count
    
    def get_version_history(self, workflow_name: str, 
                           environment: Optional[VersionEnvironment] = None) -> List[ProvenanceVersion]:
        """
        Get version history for a workflow.
        
        Args:
            workflow_name: Name of the workflow
            environment: Filter by environment (optional)
            
        Returns:
            List of ProvenanceVersion objects
        """
        query = ProvenanceVersion.query.filter_by(workflow_name=workflow_name)
        
        if environment:
            query = query.filter_by(environment=environment.value.upper() if isinstance(environment, VersionEnvironment) else environment.upper())
        
        return query.order_by(ProvenanceVersion.created_at.desc()).all()


def get_versioned_provenance_service(session: Optional[Session] = None) -> VersionedProvenanceService:
    """Create a versioned provenance service instance.

    Returns a fresh instance per call to avoid shared mutable state
    (_current_version, session) across concurrent Flask requests.
    """
    return VersionedProvenanceService(session)