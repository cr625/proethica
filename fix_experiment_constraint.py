#!/usr/bin/env python3
"""
Fix Database Constraint Issue for Experiment System

This script addresses the critical database constraint issue where experiment_run_id
cannot be NULL in the experiment_predictions table, which is blocking the ProEthica
experiment system from functioning properly.

Solutions implemented:
1. Make experiment_run_id nullable for standalone predictions
2. Create default experiment run for standalone predictions
3. Update existing NULL values if any exist

Usage:
    python fix_experiment_constraint.py
"""

import logging
import sys
import os
from datetime import datetime
from sqlalchemy import text
from app import create_app
from app.models import db
from app.models.experiment import ExperimentRun

# Set up environment variables before creating app
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
os.environ.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', 'false')
os.environ.setdefault('ENVIRONMENT', 'development')

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_experiment_constraint():
    """Fix the experiment_run_id constraint issue."""
    
    try:
        # Create Flask application context with config
        app = create_app('config')
        
        with app.app_context():
            logger.info("Starting database constraint fix...")
            
            # Check current constraint status
            logger.info("Checking current constraint status...")
            result = db.session.execute(text("""
                SELECT column_name, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'experiment_predictions' 
                AND column_name = 'experiment_run_id'
            """))
            
            constraint_info = result.fetchone()
            if constraint_info:
                logger.info(f"Current constraint: column={constraint_info[0]}, nullable={constraint_info[1]}, default={constraint_info[2]}")
            else:
                logger.error("experiment_predictions table or experiment_run_id column not found!")
                return False
            
            # Solution 1: Make experiment_run_id nullable
            logger.info("Making experiment_run_id column nullable...")
            db.session.execute(text("""
                ALTER TABLE experiment_predictions 
                ALTER COLUMN experiment_run_id DROP NOT NULL
            """))
            
            # Solution 2: Create a default experiment run for standalone predictions
            logger.info("Creating default experiment run for standalone predictions...")
            
            # Check if default experiment run already exists
            default_run = ExperimentRun.query.filter_by(name="Default Standalone Predictions").first()
            
            if not default_run:
                default_run = ExperimentRun(
                    name="Default Standalone Predictions",
                    description="Default experiment run for standalone predictions that don't belong to a formal experiment",
                    status="active",
                    created_at=datetime.utcnow(),
                    config={
                        "type": "standalone",
                        "auto_created": True,
                        "purpose": "Handle predictions without formal experiment setup"
                    }
                )
                db.session.add(default_run)
                db.session.flush()  # Get the ID
                logger.info(f"Created default experiment run with ID: {default_run.id}")
            else:
                logger.info(f"Default experiment run already exists with ID: {default_run.id}")
            
            # Solution 3: Update any existing NULL experiment_run_id values
            logger.info("Updating any existing NULL experiment_run_id values...")
            update_result = db.session.execute(text("""
                UPDATE experiment_predictions 
                SET experiment_run_id = :default_run_id 
                WHERE experiment_run_id IS NULL
            """), {"default_run_id": default_run.id})
            
            updated_rows = update_result.rowcount
            logger.info(f"Updated {updated_rows} rows with NULL experiment_run_id")
            
            # Commit all changes
            db.session.commit()
            logger.info("✓ Database constraint fix completed successfully!")
            
            # Verify the fix
            logger.info("Verifying the fix...")
            
            # Check constraint status again
            result = db.session.execute(text("""
                SELECT column_name, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'experiment_predictions' 
                AND column_name = 'experiment_run_id'
            """))
            
            new_constraint_info = result.fetchone()
            if new_constraint_info:
                logger.info(f"New constraint: column={new_constraint_info[0]}, nullable={new_constraint_info[1]}, default={new_constraint_info[2]}")
            
            # Check for any remaining NULL values
            null_count_result = db.session.execute(text("""
                SELECT COUNT(*) FROM experiment_predictions WHERE experiment_run_id IS NULL
            """))
            null_count = null_count_result.scalar()
            logger.info(f"Remaining NULL experiment_run_id values: {null_count}")
            
            if null_count == 0:
                logger.info("✓ No NULL values remaining - constraint fix verified!")
                return True
            else:
                logger.warning(f"⚠️  Still {null_count} NULL values remain")
                return False
                
    except Exception as e:
        logger.exception(f"Error fixing database constraint: {str(e)}")
        try:
            db.session.rollback()
        except:
            pass
        return False

def test_constraint_fix():
    """Test that the constraint fix works by attempting a prediction operation."""
    
    try:
        app = create_app('config')
        
        with app.app_context():
            logger.info("Testing constraint fix...")
            
            # Try to create a test prediction record without experiment_run_id
            logger.info("Attempting to create prediction without experiment_run_id...")
            
            # This would previously fail with the constraint error
            test_result = db.session.execute(text("""
                INSERT INTO experiment_predictions 
                (document_id, condition_name, prediction_text, created_at) 
                VALUES (252, 'test', 'Test prediction', NOW())
                RETURNING id
            """))
            
            test_id = test_result.scalar()
            logger.info(f"✓ Successfully created test prediction with ID: {test_id}")
            
            # Clean up test record
            db.session.execute(text("DELETE FROM experiment_predictions WHERE id = :id"), {"id": test_id})
            db.session.commit()
            
            logger.info("✓ Constraint fix test passed!")
            return True
            
    except Exception as e:
        logger.exception(f"Constraint fix test failed: {str(e)}")
        try:
            db.session.rollback()
        except:
            pass
        return False

def main():
    """Main function to run the constraint fix."""
    
    logger.info("=" * 60)
    logger.info("PROETHICA EXPERIMENT CONSTRAINT FIX")
    logger.info("=" * 60)
    
    # Step 1: Fix the constraint
    if fix_experiment_constraint():
        logger.info("✓ Database constraint fix successful!")
        
        # Step 2: Test the fix
        if test_constraint_fix():
            logger.info("✓ Constraint fix verification successful!")
            logger.info("🎉 The experiment system should now work without constraint errors!")
            return True
        else:
            logger.error("❌ Constraint fix verification failed!")
            return False
    else:
        logger.error("❌ Database constraint fix failed!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
