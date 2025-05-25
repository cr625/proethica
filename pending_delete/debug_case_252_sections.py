#!/usr/bin/env python3

import os
from dotenv import load_dotenv
from app import create_app, db
from app.models.document import Document
from app.models.document_section import DocumentSection

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
        if case:
            print(f'Case 252: {case.title}')
            print(f'Document type: {case.document_type}')
            print(f'Content length: {len(case.content or "")}')
            print('\nSections for Case 252:')
            sections = DocumentSection.query.filter_by(document_id=252).all()
            if sections:
                for section in sections:
                    print(f'- Section Type: "{section.section_type}"')
                    print(f'  Title: "{section.title}"')
                    print(f'  Content preview: {section.content[:200]}...' if len(section.content) > 200 else f'  Content: {section.content}')
                    print()
            else:
                print('No sections found for Case 252')
                
            # Also check if there's raw content in the main document
            print('\n--- RAW DOCUMENT CONTENT ---')
            if case.content:
                print(f'Raw content preview: {case.content[:500]}...')
            else:
                print('No raw content found')
        else:
            print('Case 252 not found')

if __name__ == "__main__":
    main()
