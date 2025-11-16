"""
Test Data Reset Service for ProEthica Authentication System.

This service provides safe reset capabilities for test user data while preserving
system data (admin-owned content like NSPE cases).
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy import text
from app import db
from app.models.user import User
from app.models.world import World
from app.models import Document
from app.models.guideline import Guideline
from app.models.scenario import Scenario
from app.models.deconstructed_case import DeconstructedCase
from app.models.document_section import DocumentSection
from app.models.entity_triple import EntityTriple

logger = logging.getLogger(__name__)

class TestDataResetService:
    """Service for safely resetting test user data while preserving system content."""
    
    def __init__(self):
        """Initialize the reset service."""
        self.dry_run = False
        self.reset_log = []
    
    def get_user_data_summary(self, user_id: int) -> Dict:
        """
        Get a summary of data that would be affected by a user reset.
        
        Args:
            user_id: ID of the user to analyze
            
        Returns:
            Dictionary with counts of data that would be deleted
        """
        user = User.query.get(user_id)
        if not user:
            return {'error': 'User not found'}
        
        # Only analyze user data (not system data)
        summary = {
            'user_info': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'is_admin': user.is_admin,
                'login_count': user.login_count,
                'data_reset_count': user.data_reset_count,
                'last_data_reset': user.last_data_reset.isoformat() if user.last_data_reset else None
            },
            'data_to_delete': {
                'worlds': 0,
                'documents': 0,
                'guidelines': 0,
                'scenarios': 0,
                'deconstructed_cases': 0,
                'document_sections': 0,
                'entity_triples': 0
            },
            'data_to_preserve': {
                'system_worlds': 0,
                'system_documents': 0,
                'system_guidelines': 0,
                'admin_content': 0
            }
        }
        
        # Count user-created data (data_type='user' and created_by=user_id)
        summary['data_to_delete']['worlds'] = World.query.filter_by(
            created_by=user_id, data_type='user'
        ).count()
        
        summary['data_to_delete']['documents'] = Document.query.filter_by(
            created_by=user_id, data_type='user'
        ).count()
        
        summary['data_to_delete']['guidelines'] = Guideline.query.filter_by(
            created_by=user_id, data_type='user'
        ).count()
        
        # Scenarios don't have created_by/data_type yet, but we can add them
        # For now, count scenarios in user-created worlds
        user_worlds = World.query.filter_by(created_by=user_id, data_type='user').all()
        user_world_ids = [w.id for w in user_worlds]
        
        if user_world_ids:
            summary['data_to_delete']['scenarios'] = Scenario.query.filter(
                Scenario.world_id.in_(user_world_ids)
            ).count()
        
        # Count related data that would be cascade deleted
        user_documents = Document.query.filter_by(created_by=user_id, data_type='user').all()
        user_doc_ids = [d.id for d in user_documents]
        
        if user_doc_ids:
            summary['data_to_delete']['deconstructed_cases'] = DeconstructedCase.query.filter(
                DeconstructedCase.case_id.in_(user_doc_ids)
            ).count()
            
            summary['data_to_delete']['document_sections'] = DocumentSection.query.filter(
                DocumentSection.document_id.in_(user_doc_ids)
            ).count()
        
        # Count entity triples related to user content
        user_guideline_ids = [g.id for g in Guideline.query.filter_by(created_by=user_id, data_type='user').all()]
        if user_guideline_ids:
            summary['data_to_delete']['entity_triples'] = EntityTriple.query.filter(
                EntityTriple.guideline_id.in_(user_guideline_ids)
            ).count()
        
        # Count system data that will be preserved
        summary['data_to_preserve']['system_worlds'] = World.query.filter_by(data_type='system').count()
        summary['data_to_preserve']['system_documents'] = Document.query.filter_by(data_type='system').count()
        summary['data_to_preserve']['system_guidelines'] = Guideline.query.filter_by(data_type='system').count()
        
        # Count admin-created content
        admin_users = User.query.filter_by(is_admin=True).all()
        admin_user_ids = [u.id for u in admin_users]
        if admin_user_ids:
            summary['data_to_preserve']['admin_content'] = (
                World.query.filter(World.created_by.in_(admin_user_ids)).count() +
                Document.query.filter(Document.created_by.in_(admin_user_ids)).count() +
                Guideline.query.filter(Guideline.created_by.in_(admin_user_ids)).count()
            )
        
        return summary
    
    def reset_user_data(self, user_id: int, confirm: bool = False, dry_run: bool = False) -> Dict:
        """
        Reset all user-created data for a specific user.
        
        Args:
            user_id: ID of the user whose data should be reset
            confirm: Must be True to actually perform the reset
            dry_run: If True, only simulate the reset without making changes
            
        Returns:
            Dictionary with reset results and statistics
        """
        if not confirm and not dry_run:
            return {'error': 'Reset must be confirmed or run in dry-run mode'}
        
        user = User.query.get(user_id)
        if not user:
            return {'error': 'User not found'}
        
        if user.is_admin:
            return {'error': 'Cannot reset admin user data for safety reasons'}
        
        self.dry_run = dry_run
        self.reset_log = []
        
        try:
            # Get data summary before reset
            summary = self.get_user_data_summary(user_id)
            
            if dry_run:
                self._log(f"DRY RUN: Would reset data for user {user.username} (ID: {user_id})")
            else:
                self._log(f"Starting data reset for user {user.username} (ID: {user_id})")
            
            # Reset user statistics
            if not dry_run:
                user.data_reset_count = (user.data_reset_count or 0) + 1
                user.last_data_reset = datetime.utcnow()
                user.login_count = 0  # Reset login count
                self._log(f"Updated user statistics: reset count = {user.data_reset_count}")
            else:
                self._log("DRY RUN: Would update user statistics")
            
            # Delete user-created content in proper order (respecting foreign key constraints)
            deleted_counts = self._delete_user_content(user_id, dry_run)
            
            # Reset database sequences for clean ID numbering
            if not dry_run:
                self._reset_database_sequences()
            else:
                self._log("DRY RUN: Would reset database sequences")
            
            # Commit changes
            if not dry_run:
                db.session.commit()
                self._log("All changes committed successfully")
            else:
                self._log("DRY RUN: Would commit changes")
            
            return {
                'success': True,
                'dry_run': dry_run,
                'user_id': user_id,
                'username': user.username,
                'deleted_counts': deleted_counts,
                'original_summary': summary,
                'reset_log': self.reset_log,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            if not dry_run:
                db.session.rollback()
            
            error_msg = f"Error during reset: {str(e)}"
            self._log(error_msg)
            logger.error(error_msg, exc_info=True)
            
            return {
                'success': False,
                'error': error_msg,
                'reset_log': self.reset_log
            }
    
    def bulk_reset_all_test_users(self, confirm: bool = False, dry_run: bool = False) -> Dict:
        """
        Reset data for all test users (non-admin users).
        
        Args:
            confirm: Must be True to actually perform the reset
            dry_run: If True, only simulate the reset without making changes
            
        Returns:
            Dictionary with bulk reset results
        """
        if not confirm and not dry_run:
            return {'error': 'Bulk reset must be confirmed or run in dry-run mode'}
        
        # Find all test users (non-admin users)
        test_users = User.query.filter_by(is_admin=False).all()
        
        if not test_users:
            return {'message': 'No test users found to reset'}
        
        self.dry_run = dry_run
        self.reset_log = []
        
        if dry_run:
            self._log(f"DRY RUN: Would reset data for {len(test_users)} test users")
        else:
            self._log(f"Starting bulk reset for {len(test_users)} test users")
        
        results = {
            'success': True,
            'dry_run': dry_run,
            'total_users': len(test_users),
            'user_results': [],
            'overall_stats': {
                'users_processed': 0,
                'users_failed': 0,
                'total_deleted': {}
            },
            'reset_log': [],
            'timestamp': datetime.utcnow().isoformat()
        }
        
        try:
            for user in test_users:
                self._log(f"Processing user: {user.username} (ID: {user.id})")
                
                # Reset individual user
                user_result = self.reset_user_data(user.id, confirm=True, dry_run=dry_run)
                
                if user_result.get('success'):
                    results['overall_stats']['users_processed'] += 1
                    
                    # Aggregate deletion counts
                    if 'deleted_counts' in user_result:
                        for key, count in user_result['deleted_counts'].items():
                            if key not in results['overall_stats']['total_deleted']:
                                results['overall_stats']['total_deleted'][key] = 0
                            results['overall_stats']['total_deleted'][key] += count
                else:
                    results['overall_stats']['users_failed'] += 1
                    results['success'] = False
                
                results['user_results'].append({
                    'user_id': user.id,
                    'username': user.username,
                    'success': user_result.get('success', False),
                    'error': user_result.get('error'),
                    'deleted_counts': user_result.get('deleted_counts', {})
                })
            
            # Final database sequence reset
            if not dry_run and results['success']:
                self._reset_database_sequences()
                self._log("Reset database sequences after bulk operation")
            
            results['reset_log'] = self.reset_log
            
            return results
            
        except Exception as e:
            error_msg = f"Error during bulk reset: {str(e)}"
            self._log(error_msg)
            logger.error(error_msg, exc_info=True)
            
            results['success'] = False
            results['error'] = error_msg
            results['reset_log'] = self.reset_log
            
            return results
    
    def _delete_user_content(self, user_id: int, dry_run: bool) -> Dict[str, int]:
        """
        Delete user-created content in the correct order to respect foreign key constraints.
        
        Args:
            user_id: ID of the user whose content should be deleted
            dry_run: If True, only count what would be deleted
            
        Returns:
            Dictionary with counts of deleted items
        """
        deleted_counts = {
            'entity_triples': 0,
            'document_sections': 0,
            'deconstructed_cases': 0,
            'scenarios': 0,
            'guidelines': 0,
            'documents': 0,
            'worlds': 0
        }
        
        # 1. Delete entity triples first (they reference other entities)
        user_guidelines = Guideline.query.filter_by(created_by=user_id, data_type='user').all()
        user_guideline_ids = [g.id for g in user_guidelines]
        
        if user_guideline_ids:
            entity_triples = EntityTriple.query.filter(
                EntityTriple.guideline_id.in_(user_guideline_ids)
            ).all()
            
            deleted_counts['entity_triples'] = len(entity_triples)
            
            if not dry_run:
                for triple in entity_triples:
                    db.session.delete(triple)
                self._log(f"Deleted {deleted_counts['entity_triples']} entity triples")
            else:
                self._log(f"DRY RUN: Would delete {deleted_counts['entity_triples']} entity triples")
        
        # 2. Delete document sections (they reference documents)
        user_documents = Document.query.filter_by(created_by=user_id, data_type='user').all()
        user_doc_ids = [d.id for d in user_documents]
        
        if user_doc_ids:
            document_sections = DocumentSection.query.filter(
                DocumentSection.document_id.in_(user_doc_ids)
            ).all()
            
            deleted_counts['document_sections'] = len(document_sections)
            
            if not dry_run:
                for section in document_sections:
                    db.session.delete(section)
                self._log(f"Deleted {deleted_counts['document_sections']} document sections")
            else:
                self._log(f"DRY RUN: Would delete {deleted_counts['document_sections']} document sections")
        
        # 3. Delete deconstructed cases (they reference documents)
        if user_doc_ids:
            deconstructed_cases = DeconstructedCase.query.filter(
                DeconstructedCase.case_id.in_(user_doc_ids)
            ).all()
            
            deleted_counts['deconstructed_cases'] = len(deconstructed_cases)
            
            if not dry_run:
                for case in deconstructed_cases:
                    db.session.delete(case)
                self._log(f"Deleted {deleted_counts['deconstructed_cases']} deconstructed cases")
            else:
                self._log(f"DRY RUN: Would delete {deleted_counts['deconstructed_cases']} deconstructed cases")
        
        # 4. Delete scenarios (they reference worlds)
        user_worlds = World.query.filter_by(created_by=user_id, data_type='user').all()
        user_world_ids = [w.id for w in user_worlds]
        
        if user_world_ids:
            scenarios = Scenario.query.filter(Scenario.world_id.in_(user_world_ids)).all()
            
            deleted_counts['scenarios'] = len(scenarios)
            
            if not dry_run:
                for scenario in scenarios:
                    db.session.delete(scenario)
                self._log(f"Deleted {deleted_counts['scenarios']} scenarios")
            else:
                self._log(f"DRY RUN: Would delete {deleted_counts['scenarios']} scenarios")
        
        # 5. Delete guidelines (they reference worlds)
        deleted_counts['guidelines'] = len(user_guidelines)
        
        if not dry_run:
            for guideline in user_guidelines:
                db.session.delete(guideline)
            self._log(f"Deleted {deleted_counts['guidelines']} guidelines")
        else:
            self._log(f"DRY RUN: Would delete {deleted_counts['guidelines']} guidelines")
        
        # 6. Delete documents
        deleted_counts['documents'] = len(user_documents)
        
        if not dry_run:
            for document in user_documents:
                db.session.delete(document)
            self._log(f"Deleted {deleted_counts['documents']} documents")
        else:
            self._log(f"DRY RUN: Would delete {deleted_counts['documents']} documents")
        
        # 7. Delete worlds last (they're referenced by other entities)
        deleted_counts['worlds'] = len(user_worlds)
        
        if not dry_run:
            for world in user_worlds:
                db.session.delete(world)
            self._log(f"Deleted {deleted_counts['worlds']} worlds")
        else:
            self._log(f"DRY RUN: Would delete {deleted_counts['worlds']} worlds")
        
        return deleted_counts
    
    def _reset_database_sequences(self):
        """Reset database sequences to start from clean numbers after deletions."""
        try:
            # List of tables and their ID columns to reset sequences for
            tables_to_reset = [
                ('worlds', 'id'),
                ('documents', 'id'),
                ('guidelines', 'id'),
                ('scenarios', 'id'),
                ('deconstructed_cases', 'id'),
                ('document_sections', 'id'),
                ('entity_triples', 'id')
            ]
            
            for table_name, id_column in tables_to_reset:
                # Get the maximum ID currently in the table
                max_id_result = db.session.execute(
                    text(f"SELECT COALESCE(MAX({id_column}), 0) FROM {table_name}")
                ).fetchone()
                
                max_id = max_id_result[0] if max_id_result else 0
                next_id = max_id + 1
                
                # Reset the sequence to start from the next available ID
                sequence_name = f"{table_name}_{id_column}_seq"
                db.session.execute(
                    text(f"SELECT setval('{sequence_name}', {next_id}, false)")
                )
                
                self._log(f"Reset sequence {sequence_name} to start from {next_id}")
            
        except Exception as e:
            self._log(f"Warning: Could not reset some database sequences: {str(e)}")
            # Don't fail the entire operation for sequence reset issues
    
    def _log(self, message: str):
        """Add a message to the reset log."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.reset_log.append(log_entry)
        logger.info(message)
