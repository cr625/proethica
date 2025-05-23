#!/usr/bin/env python3

import os
import json
from dotenv import load_dotenv
from app import create_app, db
from app.models.document import Document

# Load environment variables from .env file if it exists
if os.path.exists('.env'):
    load_dotenv()

# Set environment
os.environ['ENVIRONMENT'] = 'development'

def main():
    app = create_app('config')
    with app.app_context():
        # Get Case 252
        case = Document.query.get(252)
        if not case:
            print('Case 252 not found')
            return
            
        print(f'Case 252: {case.title}')
        
        # Examine the sections metadata structure
        if case.doc_metadata and 'sections' in case.doc_metadata:
            sections = case.doc_metadata['sections']
            print(f'\nSections type: {type(sections)}')
            print(f'Sections keys: {list(sections.keys()) if isinstance(sections, dict) else "Not a dict"}')
            
            if isinstance(sections, dict):
                for section_key, section_value in sections.items():
                    print(f'\nSection "{section_key}":')
                    print(f'  Type: {type(section_value)}')
                    if isinstance(section_value, dict):
                        print(f'  Keys: {list(section_value.keys())}')
                        # Show a preview
                        for key, value in section_value.items():
                            if isinstance(value, str) and len(value) > 100:
                                print(f'    {key}: {value[:100]}...')
                            else:
                                print(f'    {key}: {value}')
                    elif isinstance(section_value, str):
                        if len(section_value) > 100:
                            print(f'  Content: {section_value[:100]}...')
                        else:
                            print(f'  Content: {section_value}')
                    else:
                        print(f'  Content: {section_value}')

if __name__ == "__main__":
    main()
