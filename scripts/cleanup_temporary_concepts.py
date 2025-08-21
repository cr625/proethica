#!/usr/bin/env python3
"""
Script to cleanup expired temporary concepts from the database.
Can be run periodically via cron or as needed.
"""

import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.services.temporary_concept_service import TemporaryConceptService


def cleanup_expired_concepts():
    """Clean up expired temporary concepts."""
    app = create_app()
    
    with app.app_context():
        print(f"Starting cleanup at {datetime.utcnow()}")
        
        # Cleanup expired concepts
        deleted_count = TemporaryConceptService.cleanup_expired()
        
        print(f"Deleted {deleted_count} expired temporary concepts")
        
        # Optional: Show statistics
        try:
            from app.models.temporary_concept import TemporaryConcept
            
            # Count remaining concepts by status
            pending = TemporaryConcept.query.filter_by(status='pending').count()
            reviewed = TemporaryConcept.query.filter_by(status='reviewed').count()
            committed = TemporaryConcept.query.filter_by(status='committed').count()
            discarded = TemporaryConcept.query.filter_by(status='discarded').count()
            
            print(f"\nRemaining concepts:")
            print(f"  Pending: {pending}")
            print(f"  Reviewed: {reviewed}")
            print(f"  Committed: {committed}")
            print(f"  Discarded: {discarded}")
            print(f"  Total: {pending + reviewed + committed + discarded}")
            
        except Exception as e:
            print(f"Error getting statistics: {e}")
        
        print(f"\nCleanup completed at {datetime.utcnow()}")


if __name__ == "__main__":
    cleanup_expired_concepts()