#!/usr/bin/env python

import os
import sys
import json
import re
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def fix_case():
    """Fix the questions formatting in case #206."""
    # Get database URL from environment variable with fallback
    database_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
    print(f"Using database URL: {database_url}")
    
    try:
        # Create SQLAlchemy engine and session
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Query for document with ID 206
        result = session.execute(
            text("SELECT id, title, doc_metadata, content FROM documents WHERE id = :id"),
            {"id": 206}
        )
        case = result.fetchone()
        
        if not case:
            print(f"Case #206 not found!")
            return
            
        print(f"Found case #206: {case.title}")
        
        # Extract metadata
        if not case.doc_metadata:
            print("No metadata found for the case")
            return
            
        metadata = case.doc_metadata
        
        # Get question text from metadata
        question_html = metadata.get('sections', {}).get('question', '')
        if not question_html:
            print("No question HTML found in metadata")
            return
            
        print(f"Raw question HTML: {question_html}")
        
        # Parse questions from the question HTML
        questions = []
        
        # Split by question mark followed by capital letter or end of string
        splits = re.split(r'\?((?=[A-Z][a-z])|$)', question_html)
        
        # Process the splits to form complete questions
        if len(splits) > 1:  # If we found at least one question mark
            for i in range(0, len(splits) - 1, 2):
                if i + 1 < len(splits):
                    # Rejoin the question with its question mark
                    q = splits[i] + "?"
                    questions.append(q.strip())
            
            print(f"Parsed {len(questions)} questions from text:")
            for i, q in enumerate(questions, 1):
                print(f"  {i}. {q}")
                
            # We won't update the metadata since it's causing SQL issues
            # Instead, we'll just focus on updating the HTML content
            print("Skipping metadata update due to SQL issues, focusing on HTML content update only")
            
            # Also update the HTML content to use ordered list for questions
            content = case.content
            if content:
                # Find the questions section in the content
                questions_section = re.search(r'(<div class="card-header bg-light">\s*<h5 class="mb-0">Question(?:s)?</h5>\s*</div>\s*<div class="card-body">)\s*(.*?)\s*(</div>)', content, re.DOTALL)
                
                if questions_section:
                    # Create a properly formatted ordered list
                    new_questions_html = "<ol class=\"mb-0\">\n"
                    for q in questions:
                        new_questions_html += f"    <li>{q}</li>\n"
                    new_questions_html += "</ol>"
                    
                    # Replace the questions section with a properly formatted list
                    updated_content = re.sub(
                        r'(<div class="card-header bg-light">\s*<h5 class="mb-0">Question(?:s)?</h5>\s*</div>\s*<div class="card-body">)\s*(.*?)\s*(</div>)',
                        f'\\1\n{new_questions_html}\n\\3',
                        content,
                        flags=re.DOTALL
                    )
                    
                    # Update the database with new content
                    session.execute(
                        text("UPDATE documents SET content = :content WHERE id = :id"),
                        {"id": 206, "content": updated_content}
                    )
                    
                    print("Updated content with properly formatted questions list")
                else:
                    print("Questions section not found in content")
            
            session.commit()
            print("Successfully updated case #206 with parsed questions")
        else:
            print("Could not parse questions from HTML - no question marks found")
        
        session.close()
        
    except Exception as e:
        print(f"Database query error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_case()
