#!/usr/bin/env python

import os
import sys
import json
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def reimport_case():
    """Re-import case #23-4 to test the new question parsing logic."""
    # Get database URL from environment variable with fallback
    database_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
    print(f"Using database URL: {database_url}")
    
    # URL of the case to import
    case_url = "https://www.nspe.org/career-growth/ethics/board-ethical-review-cases/acknowledging-errors-design"
    
    # Use process_url_pipeline endpoint directly using requests
    print(f"Fetching case URL: {case_url}")
    try:
        # First, get the raw content
        response = requests.get(case_url)
        if not response.ok:
            print(f"Failed to fetch URL: {response.status_code}")
            return
            
        # Now call the local endpoint to process with NSPE extraction (running locally)
        # We'll use Flask's development server at port 5000
        base_url = "http://localhost:5000"
        process_url = f"{base_url}/cases/process/url"
        
        # Submit form data
        form_data = {
            'url': case_url,
            'process_extraction': 'true'
        }
        
        print("Processing URL through extraction pipeline...")
        process_response = requests.post(process_url, data=form_data)
        
        if not process_response.ok:
            print(f"Failed to process URL: {process_response.status_code}")
            print(process_response.text[:500])
            return
            
        print("Successfully processed URL, now saving and viewing...")
        
        # Find the form data in the HTML response by looking for the hidden form fields
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(process_response.text, 'html.parser')
        
        # Find the "Save and View Case" form
        save_form = soup.find('form', {'action': '/cases/save-and-view'})
        if not save_form:
            print("Could not find Save and View Case form in response")
            return
            
        # Extract form data
        save_form_data = {}
        for hidden_field in save_form.find_all('input', {'type': 'hidden'}):
            name = hidden_field.get('name')
            value = hidden_field.get('value')
            if name and value:
                save_form_data[name] = value
                
        # Add the world_id
        save_form_data['world_id'] = '1'  # Engineering Ethics world
        
        # Print the form data keys
        print(f"Form data keys: {list(save_form_data.keys())}")
        
        # Save the case using the save and view endpoint
        save_url = f"{base_url}/cases/save-and-view"
        save_response = requests.post(save_url, data=save_form_data)
        
        if not save_response.ok:
            print(f"Failed to save case: {save_response.status_code}")
            print(save_response.text[:500])
            return
            
        # If successful, the response will be a redirect to the case detail page
        # Extract the case ID from the redirect URL
        case_id = None
        if 'Location' in save_response.headers:
            location = save_response.headers['Location']
            print(f"Redirected to: {location}")
            if '/cases/' in location:
                case_id = location.split('/cases/')[-1]
                print(f"Extracted case ID: {case_id}")
        
        if not case_id:
            print("Could not determine case ID from redirect")
            return
            
        print(f"Case successfully imported with ID: {case_id}")
        
        # Now check the database to verify the questions_list
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Query for the case
        result = session.execute(
            text("SELECT doc_metadata FROM documents WHERE id = :id"),
            {"id": case_id}
        )
        row = result.fetchone()
        
        if row and row.doc_metadata:
            metadata = row.doc_metadata
            questions_list = metadata.get('questions_list', [])
            print(f"\nQuestions List from Metadata:")
            print(f"Type: {type(questions_list)}")
            print(f"Length: {len(questions_list)}")
            for i, q in enumerate(questions_list, 1):
                print(f"{i}. {q}")
                
            # Also update the question HTML in the content field
            if questions_list:
                # Check if the content field has questions in the wrong format
                content_result = session.execute(
                    text("SELECT content FROM documents WHERE id = :id"),
                    {"id": case_id}
                )
                content_row = content_result.fetchone()
                if content_row and content_row.content:
                    content = content_row.content
                    # Find questions section in content
                    import re
                    questions_section = re.search(r'<div class="card-header bg-light">\s*<h5 class="mb-0">Question(?:s)?</h5>\s*</div>\s*<div class="card-body">\s*(.*?)\s*</div>', content, re.DOTALL)
                    if questions_section and "<ol" not in questions_section.group(1):
                        print("\nFoundd questions section with incorrect formatting, updating...")
                        # Create a properly formatted ordered list
                        new_questions_html = "<ol class=\"mb-0\">\n"
                        for q in questions_list:
                            new_questions_html += f"    <li>{q}</li>\n"
                        new_questions_html += "</ol>"
                        
                        # Replace the questions section
                        updated_content = re.sub(
                            r'(<div class="card-header bg-light">\s*<h5 class="mb-0">Question(?:s)?</h5>\s*</div>\s*<div class="card-body">)\s*(.*?)\s*(</div>)',
                            f'\\1\n{new_questions_html}\n\\3',
                            content,
                            flags=re.DOTALL
                        )
                        
                        # Update the database
                        session.execute(
                            text("UPDATE documents SET content = :content WHERE id = :id"),
                            {"id": case_id, "content": updated_content}
                        )
                        session.commit()
                        print("Updated content with properly formatted questions list")
                    else:
                        print("Questions section already has proper formatting or not found")
        else:
            print("No metadata found for the case")
        
        session.close()
        
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    reimport_case()
