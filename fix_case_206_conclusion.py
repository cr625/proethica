#!/usr/bin/env python

import os
import sys
import json
import re
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def fix_case_conclusion():
    """Fix the conclusion formatting in case #206."""
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
        
        # Get conclusion text from metadata
        conclusion_html = metadata.get('sections', {}).get('conclusion', '')
        if not conclusion_html:
            print("No conclusion HTML found in metadata")
            return
            
        print(f"Raw conclusion HTML: {conclusion_html[:100]}...") # Print first 100 chars
        
        # Parse conclusions from the conclusion HTML
        # Strategy 1: Split by periods followed by "It was" or similar patterns
        conclusions = []
        
        # Pattern for conclusion items: Complete sentence ending with period, followed by another
        # that begins with "It was ethical" or similar beginning pattern
        splits = re.split(r'\.(?=It was|Engineer)', conclusion_html)
        
        if len(splits) > 1:  # If we found multiple items
            print(f"Found {len(splits)} potential conclusion items")
            
            # Clean up each split to be a proper conclusion item
            for item in splits:
                item = item.strip()
                if item:
                    # Add a period if it was removed by the split
                    if not item.endswith('.'):
                        item += '.'
                    conclusions.append(item)
            
            print(f"Parsed {len(conclusions)} conclusion items:")
            for i, c in enumerate(conclusions, 1):
                # Print first 80 chars of each conclusion
                print(f"  {i}. {c[:80]}..." if len(c) > 80 else f"  {i}. {c}")
        else:
            print("Could not parse conclusion into separate items.")
            print("Using original conclusion text as a single item.")
            conclusions = [conclusion_html]
            
        # Update the HTML content to format conclusions as an ordered list
        content = case.content
        if content:
            # Find the conclusion section in the content
            conclusion_section = re.search(r'(<div class="card-header bg-light">\s*<h5 class="mb-0">Conclusion(?:s)?</h5>\s*</div>\s*<div class="card-body">)\s*(.*?)\s*(</div>)', content, re.DOTALL)
            
            if conclusion_section:
                if len(conclusions) > 1:
                    # Create a properly formatted ordered list for multiple conclusions
                    new_conclusion_html = "<ol class=\"mb-0\">\n"
                    for c in conclusions:
                        new_conclusion_html += f"    <li>{c}</li>\n"
                    new_conclusion_html += "</ol>"
                    
                    # Update the heading to plural if needed
                    content = re.sub(
                        r'<h5 class="mb-0">Conclusion</h5>',
                        r'<h5 class="mb-0">Conclusions</h5>',
                        content
                    )
                else:
                    # Single conclusion, keep as paragraph
                    new_conclusion_html = f"<p class=\"mb-0\">{conclusions[0]}</p>"
                
                # Replace the conclusion section with properly formatted content
                updated_content = re.sub(
                    r'(<div class="card-header bg-light">\s*<h5 class="mb-0">Conclusion(?:s)?</h5>\s*</div>\s*<div class="card-body">)\s*(.*?)\s*(</div>)',
                    f'\\1\n{new_conclusion_html}\n\\3',
                    content,
                    flags=re.DOTALL
                )
                
                if updated_content != content:
                    # Update the database with new content
                    session.execute(
                        text("UPDATE documents SET content = :content WHERE id = :id"),
                        {"id": 206, "content": updated_content}
                    )
                    
                    print("Updated content with properly formatted conclusion list")
                    session.commit()
                else:
                    print("No changes were made to the content")
            else:
                print("Conclusion section not found in content")
        
        # Also check if we need to update metadata with conclusion_items list
        if len(conclusions) > 1 and not metadata.get('conclusion_items'):
            print("Would update metadata with parsed conclusions, but skipping due to SQL issues")
            # We're not updating metadata due to issues with SQL/JSON formatting
        
        session.close()
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_case_conclusion()
