#!/usr/bin/env python
"""
Fix provenance model imports to ensure SQLAlchemy recognizes all tables.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db

# Explicitly import all provenance models to ensure they're registered
from app.models.provenance import (
    ProvenanceAgent, ProvenanceActivity, ProvenanceEntity,
    ProvenanceDerivation, ProvenanceUsage, ProvenanceCommunication,
    ProvenanceBundle, VersionEnvironment, VersionStatus
)

from app.models.provenance_versioning import (
    ProvenanceRevision, ProvenanceVersion, ProvenanceAlternate,
    VersionConfiguration
)

def verify_models():
    """Verify that all provenance models are properly loaded."""
    app = create_app('development')
    
    with app.app_context():
        # Get all table names from metadata
        tables = db.metadata.tables.keys()
        provenance_tables = [t for t in tables if 'provenance' in t]
        
        print("SQLAlchemy recognized provenance tables:")
        for table in sorted(provenance_tables):
            print(f"  - {table}")
        
        # Try a simple query to verify models work
        try:
            # Check if we can query the version config
            from app.models.provenance_versioning import VersionConfiguration
            configs = VersionConfiguration.query.all()
            print(f"\nFound {len(configs)} version configurations")
            
            # Check activities
            from app.models.provenance import ProvenanceActivity
            activities = ProvenanceActivity.query.limit(5).all()
            print(f"Found {len(activities)} provenance activities")
            
            print("\n✓ All models are working correctly!")
            return True
            
        except Exception as e:
            print(f"\n✗ Error accessing models: {e}")
            return False

if __name__ == "__main__":
    verify_models()