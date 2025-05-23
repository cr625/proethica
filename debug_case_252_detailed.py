#!/usr/bin/env python3

import os
import json
from dotenv import load_dotenv
from app import create_app, db
from app.models.document import Document
from app.models.document_section import DocumentSection
from app.services.experiment.prediction_service import PredictionService

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
        print(f'Document type: {case.document_type}')
        print(f'Content length: {len(case.content or "")}')
        
        # Check metadata structure
        print('\n--- DOCUMENT METADATA ---')
        if case.doc_metadata:
            print(f'Metadata type: {type(case.doc_metadata)}')
            if isinstance(case.doc_metadata, dict):
                print('Metadata keys:')
                for key in case.doc_metadata.keys():
                    print(f'  - {key}')
                
                # Check for document_structure
                if 'document_structure' in case.doc_metadata:
                    doc_struct = case.doc_metadata['document_structure']
                    print(f'\nDocument structure keys: {list(doc_struct.keys()) if isinstance(doc_struct, dict) else "Not a dict"}')
                    
                    if isinstance(doc_struct, dict) and 'sections' in doc_struct:
                        sections = doc_struct['sections']
                        print(f'Document structure sections: {list(sections.keys()) if isinstance(sections, dict) else "Not a dict"}')
                        
                        # Show section details
                        if isinstance(sections, dict):
                            for section_id, section_data in sections.items():
                                if isinstance(section_data, dict):
                                    section_type = section_data.get('type', 'unknown')
                                    content_preview = section_data.get('content', '')[:100]
                                    print(f'    {section_id}: type="{section_type}", content="{content_preview}..."')
                
                # Check for top-level sections
                if 'sections' in case.doc_metadata:
                    sections = case.doc_metadata['sections']
                    print(f'\nTop-level sections: {list(sections.keys()) if isinstance(sections, dict) else "Not a dict"}')
            else:
                print(f'Metadata content preview: {str(case.doc_metadata)[:500]}...')
        else:
            print('No metadata found')
            
        # Check DocumentSection records
        print('\n--- DOCUMENT SECTIONS TABLE ---')
        sections = DocumentSection.query.filter_by(document_id=252).all()
        if sections:
            for section in sections:
                print(f'- Section Type: "{section.section_type}"')
                print(f'  ID: {section.id}')
                print(f'  Content preview: {section.content[:100]}...' if len(section.content) > 100 else f'  Content: {section.content}')
                print()
        else:
            print('No DocumentSection records found for Case 252')
            
        # Test the prediction service method
        print('\n--- PREDICTION SERVICE TEST ---')
        prediction_service = PredictionService()
        
        print('Testing get_document_sections with leave_out_conclusion=True:')
        sections_exclude = prediction_service.get_document_sections(252, leave_out_conclusion=True)
        for section_type, content in sections_exclude.items():
            print(f'  {section_type}: {content[:100]}...' if len(content) > 100 else f'  {section_type}: {content}')
            
        print('\nTesting get_document_sections with leave_out_conclusion=False:')
        sections_include = prediction_service.get_document_sections(252, leave_out_conclusion=False)
        for section_type, content in sections_include.items():
            print(f'  {section_type}: {content[:100]}...' if len(content) > 100 else f'  {section_type}: {content}')
            
        # Check if there's a conclusion section specifically
        if 'conclusion' in sections_include:
            print(f'\n✅ CONCLUSION FOUND: {sections_include["conclusion"][:200]}...')
        else:
            print('\n❌ NO CONCLUSION SECTION FOUND')
            # Let's check what section types we do have
            print(f'Available sections: {list(sections_include.keys())}')

if __name__ == "__main__":
    main()
