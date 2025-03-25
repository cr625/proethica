"""
Add progress tracking fields to the documents table.
"""

import os
import sys
from datetime import datetime

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.document import Document

def add_progress_fields():
    """Add progress tracking fields to the documents table."""
    app = create_app()
    
    with app.app_context():
        # Check if columns already exist
        inspector = db.inspect(db.engine)
        columns = [column['name'] for column in inspector.get_columns('documents')]
        
        if 'processing_phase' not in columns:
            print("Adding processing_phase column to documents table...")
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE documents ADD COLUMN processing_phase VARCHAR(50) DEFAULT \'initializing\''))
                conn.commit()
        else:
            print("processing_phase column already exists.")
        
        if 'processing_progress' not in columns:
            print("Adding processing_progress column to documents table...")
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE documents ADD COLUMN processing_progress INTEGER DEFAULT 0'))
                conn.commit()
        else:
            print("processing_progress column already exists.")
        
        # Update existing documents with default values
        documents = Document.query.all()
        for document in documents:
            if document.processing_status == 'pending':
                document.processing_phase = 'initializing'
                document.processing_progress = 0
            elif document.processing_status == 'processing':
                document.processing_phase = 'processing'
                document.processing_progress = 50
            elif document.processing_status == 'completed':
                document.processing_phase = 'finalizing'
                document.processing_progress = 100
            elif document.processing_status == 'failed':
                document.processing_phase = 'failed'
                document.processing_progress = 0
        
        db.session.commit()
        print(f"Updated {len(documents)} existing documents with default progress values.")
        
        print("Migration completed successfully.")

if __name__ == '__main__':
    add_progress_fields()
