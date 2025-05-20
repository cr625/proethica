#!/usr/bin/env python

import os
import sys
import json
import re
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from bs4 import BeautifulSoup

def verify_formatting():
    """Verify that case #206 has proper formatting for questions and conclusions."""
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
        metadata = case.doc_metadata
        
        # Verify metadata
        print("\n--- Metadata Verification ---")
        print(f"Case Number: {metadata.get('case_number')}")
        print(f"Year: {metadata.get('year')}")
        
        # Check if questions_list exists in metadata
        questions_list = metadata.get('questions_list', [])
        if questions_list:
            print(f"Questions list in metadata: {len(questions_list)} items")
            for i, q in enumerate(questions_list, 1):
                print(f"  {i}. {q[:80]}..." if len(q) > 80 else f"  {i}. {q}")
        else:
            print("No questions list found in metadata")
            
        # Check if conclusion_items exists in metadata
        conclusion_items = metadata.get('conclusion_items', [])
        if conclusion_items:
            print(f"Conclusion items in metadata: {len(conclusion_items)} items")
            for i, c in enumerate(conclusion_items, 1):
                print(f"  {i}. {c[:80]}..." if len(c) > 80 else f"  {i}. {c}")
        else:
            print("No conclusion items found in metadata")
        
        # Now analyze the HTML content
        print("\n--- HTML Content Verification ---")
        html_content = case.content
        
        # Use BeautifulSoup to parse and analyze the HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all card sections
        cards = soup.find_all('div', class_='card')
        print(f"Found {len(cards)} card sections in HTML")
        
        # Check for Questions and Conclusions specifically
        question_card = None
        conclusion_card = None
        
        for card in cards:
            header = card.find('div', class_='card-header')
            if header:
                heading = header.find('h5')
                if heading:
                    if 'Question' in heading.text:
                        question_card = card
                    elif 'Conclusion' in heading.text:
                        conclusion_card = card
        
        # Analyze question formatting
        if question_card:
            print("\nQuestion section:")
            print(f"Heading: {question_card.find('h5').text}")
            
            card_body = question_card.find('div', class_='card-body')
            if card_body:
                ordered_list = card_body.find('ol')
                if ordered_list:
                    list_items = ordered_list.find_all('li')
                    print(f"Found ordered list with {len(list_items)} items")
                    for i, item in enumerate(list_items, 1):
                        print(f"  {i}. {item.text[:80]}..." if len(item.text) > 80 else f"  {i}. {item.text}")
                else:
                    print("No ordered list found in question section")
                    print(f"Raw content: {card_body.text[:100]}...")
        else:
            print("No question section found in HTML")
        
        # Analyze conclusion formatting
        if conclusion_card:
            print("\nConclusion section:")
            print(f"Heading: {conclusion_card.find('h5').text}")
            
            card_body = conclusion_card.find('div', class_='card-body')
            if card_body:
                ordered_list = card_body.find('ol')
                if ordered_list:
                    list_items = ordered_list.find_all('li')
                    print(f"Found ordered list with {len(list_items)} items")
                    for i, item in enumerate(list_items, 1):
                        print(f"  {i}. {item.text[:80]}..." if len(item.text) > 80 else f"  {i}. {item.text}")
                else:
                    print("No ordered list found in conclusion section")
                    print(f"Raw content: {card_body.text[:100]}...")
        else:
            print("No conclusion section found in HTML")
        
        session.close()
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_formatting()
