#!/usr/bin/env python3
"""
Clear old predictions for Case 252 so fresh ones can be generated.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up environment
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
os.environ.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', 'false')
os.environ.setdefault('ENVIRONMENT', 'development')

from app import create_app, db
from app.models.experiment import Prediction

def main():
    app = create_app('config')
    with app.app_context():
        try:
            # Delete existing predictions for Case 252
            old_predictions = Prediction.query.filter_by(document_id=252, target='conclusion').all()
            print(f'Found {len(old_predictions)} existing predictions for Case 252')
            
            for pred in old_predictions:
                print(f'Deleting prediction created at: {pred.created_at}')
                db.session.delete(pred)
            
            db.session.commit()
            print('✅ Old predictions deleted successfully')
            print('Now try the UI again - it should generate a fresh prediction!')
            
        except Exception as e:
            print(f'❌ Error: {e}')
            db.session.rollback()

if __name__ == '__main__':
    main()
