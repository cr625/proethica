"""
Script to create all database tables for ProEthica provenance models.
Run this with your virtual environment activated.
"""

from app import create_app
from app.models import db
from app.models.provenance import *

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
        print("✅ All tables created.")
