#!/usr/bin/env python3
"""
Debug script to check template loading.
"""

import os
import sys

# Add app path
sys.path.append(os.path.dirname(__file__))

# Set environment variables
os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:PASS@localhost:5432/ai_ethical_dm'

from app import create_app
from app.models.prompt_templates import SectionPromptTemplate

def debug_templates():
    """Debug template loading."""
    
    app = create_app('development')
    
    with app.app_context():
        print("=== All Templates ===")
        all_templates = SectionPromptTemplate.query.all()
        for t in all_templates:
            print(f"ID: {t.id}, Domain: '{t.domain}', Section: {t.section_type}, Name: {t.name}, Active: {t.active}")
        
        print("\n=== Engineering Domain Templates ===")
        engineering_templates = SectionPromptTemplate.query.filter_by(
            domain='engineering',
            active=True
        ).all()
        for t in engineering_templates:
            print(f"ID: {t.id}, Section: {t.section_type}, Name: {t.name}")
        
        print(f"\nFound {len(engineering_templates)} engineering templates")

if __name__ == "__main__":
    debug_templates()