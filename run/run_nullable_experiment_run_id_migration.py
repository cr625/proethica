"""
Migration script to make experiment_run_id nullable in experiment_predictions table.
This allows for standalone predictions that aren't part of formal experiments.
"""

import os
import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import app components
from app import create_app, db
from sqlalchemy import text

def run_migration():
    """Run the migration to make experiment_run_id nullable."""
    
    # Create app context
    app = create_app()
    
    with app.app_context():
        try:
            print("Making experiment_run_id nullable in experiment_predictions table...")
            
            # Read migration SQL
            migration_path = project_root / "migrations" / "sql" / "make_experiment_run_id_nullable.sql"
            with open(migration_path, 'r') as f:
                migration_sql = f.read()
            
            # Execute migration
            db.session.execute(text(migration_sql))
            db.session.commit()
            
            print("✅ Migration completed successfully!")
            print("   - experiment_run_id is now nullable")
            print("   - Standalone predictions can now be created")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            db.session.rollback()
            return False
            
    return True

def update_model():
    """Update the Prediction model to reflect the nullable constraint."""
    
    model_path = project_root / "app" / "models" / "experiment.py"
    
    try:
        with open(model_path, 'r') as f:
            content = f.read()
        
        # Update the model definition
        old_line = "experiment_run_id = db.Column(db.Integer, db.ForeignKey('experiment_runs.id'), nullable=False)"
        new_line = "experiment_run_id = db.Column(db.Integer, db.ForeignKey('experiment_runs.id'), nullable=True)"
        
        if old_line in content:
            content = content.replace(old_line, new_line)
            
            with open(model_path, 'w') as f:
                f.write(content)
                
            print("✅ Model updated successfully!")
            print("   - experiment_run_id is now nullable=True in Prediction model")
            return True
        else:
            print("⚠️  Model definition not found or already updated")
            return True
            
    except Exception as e:
        print(f"❌ Model update failed: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Running experiment_run_id nullable migration...")
    print("=" * 60)
    
    # Run database migration
    if run_migration():
        # Update model definition
        if update_model():
            print("=" * 60)
            print("✅ All migration steps completed successfully!")
            print("   You can now create standalone predictions without experiment_run_id")
        else:
            print("=" * 60)
            print("⚠️  Database migration succeeded but model update failed")
            print("   You may need to manually update the model")
    else:
        print("=" * 60)
        print("❌ Migration failed!")
        sys.exit(1)
