#!/usr/bin/env python3
"""
Test script for URL content extraction.

This script tests the URL content extraction process outside of the Flask application
to diagnose issues with the guideline URL processing pipeline.
"""

import os
import sys
import argparse
import requests
from bs4 import BeautifulSoup
import traceback

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.document import Document, PROCESSING_STATUS
from app.models.world import World
from app.services.embedding_service import EmbeddingService
from app.services.task_queue import BackgroundTaskQueue

def extract_with_direct_method(url):
    """Extract content directly using requests and BeautifulSoup."""
    try:
        print(f"\n\n==== DIRECT EXTRACTION TEST ====")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        print(f"Status code: {response.status_code}")
        print(f"Response length: {len(response.content)} bytes")
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract title
        print(f"Page title: {soup.title.text if soup.title else 'No title found'}")
        
        # Extract main content (looking for common content containers)
        main_content = None
        for selector in [
            'div.wysiwyg', 'article', 'main', 'div.content', 'div.main-content', 
            '#content', '#main', '.content-area'
        ]:
            content = soup.select_one(selector)
            if content and len(content.text.strip()) > 200:
                main_content = content
                print(f"Found content using selector: {selector}")
                break
        
        if not main_content:
            main_content = soup.body
            print("Using body as fallback content container")
        
        # Remove script, style elements, and hidden elements
        for element in main_content.find_all(["script", "style", "head", "meta", "noscript"]):
            element.extract()
        
        # Extract text
        text = main_content.get_text(separator='\n', strip=True)
        
        # Print sample
        text_sample = text[:500] + "..." if len(text) > 500 else text
        print(f"\nContent sample:\n{text_sample}")
        print(f"\nTotal content length: {len(text)} characters")
        
        return text
        
    except Exception as e:
        print(f"Error in direct extraction: {e}")
        traceback.print_exc()
        return None

def test_embedding_service_extraction(url):
    """Test content extraction using the EmbeddingService."""
    try:
        print(f"\n\n==== EMBEDDING SERVICE EXTRACTION TEST ====")
        embedding_service = EmbeddingService()
        content = embedding_service._extract_from_url(url)
        
        # Print sample
        text_sample = content[:500] + "..." if len(content) > 500 else content
        print(f"\nExtracted content sample:\n{text_sample}")
        print(f"\nTotal content length: {len(content)} characters")
        
        return content
    except Exception as e:
        print(f"Error in embedding service extraction: {e}")
        traceback.print_exc()
        return None

def create_test_document(url, world_id=None):
    """Create a test document with the given URL."""
    try:
        print(f"\n\n==== DATABASE DOCUMENT CREATION TEST ====")
        
        # Ensure we have a world
        if not world_id:
            # Get or create a test world
            world = World.query.filter_by(name="Test World").first()
            if not world:
                world = World(name="Test World", description="Test world for URL extraction tests")
                db.session.add(world)
                db.session.commit()
                print(f"Created test world with ID {world.id}")
            else:
                print(f"Using existing test world with ID {world.id}")
            
            world_id = world.id
        
        # Create document
        document = Document(
            title=f"Test Document for URL: {url[:50]}...",
            document_type="guideline",
            world_id=world_id,
            source=url,
            file_type="url",
            doc_metadata={},
            processing_status=PROCESSING_STATUS['PENDING']
        )
        db.session.add(document)
        db.session.commit()
        
        print(f"Created test document with ID {document.id}")
        return document
    except Exception as e:
        print(f"Error creating test document: {e}")
        traceback.print_exc()
        return None

def process_document_manually(document_id):
    """Manually process a document to simulate the task queue."""
    try:
        print(f"\n\n==== MANUAL DOCUMENT PROCESSING TEST ====")
        
        # Get the document
        document = Document.query.get(document_id)
        if not document:
            print(f"Document with ID {document_id} not found")
            return False
        
        # Check if it's a URL type
        if document.file_type != "url" or not document.source:
            print(f"Document is not a URL type or has no source URL")
            return False
        
        print(f"Processing document ID {document.id}: {document.title}")
        print(f"URL: {document.source}")
        
        # Update status
        document.processing_status = PROCESSING_STATUS['PROCESSING']
        document.processing_progress = 10
        db.session.commit()
        
        # Extract content
        embedding_service = EmbeddingService()
        content = embedding_service._extract_from_url(document.source)
        
        # Store content
        document.content = content
        document.processing_status = PROCESSING_STATUS['COMPLETED']
        document.processing_progress = 100
        db.session.commit()
        
        print(f"Document processed successfully")
        print(f"Content length: {len(content)} characters")
        
        # Print sample
        text_sample = content[:500] + "..." if len(content) > 500 else content
        print(f"\nContent sample:\n{text_sample}")
        
        return True
    except Exception as e:
        print(f"Error processing document: {e}")
        traceback.print_exc()
        
        # Update status to failed
        if 'document' in locals() and document:
            document.processing_status = PROCESSING_STATUS['FAILED']
            document.processing_error = str(e)
            db.session.commit()
        
        return False

def test_task_queue_processing(document_id):
    """Test document processing using the task queue."""
    try:
        print(f"\n\n==== TASK QUEUE PROCESSING TEST ====")
        
        # Get the document
        document = Document.query.get(document_id)
        if not document:
            print(f"Document with ID {document_id} not found")
            return False
        
        # Reset status
        document.processing_status = PROCESSING_STATUS['PENDING']
        document.processing_progress = 0
        document.processing_error = None
        db.session.commit()
        
        # Get task queue
        task_queue = BackgroundTaskQueue.get_instance()
        
        # Process document asynchronously
        print(f"Submitting document ID {document.id} to task queue")
        task_queue.process_document_async(document.id)
        
        print(f"Document submitted to task queue. Check application logs for processing status.")
        return True
    except Exception as e:
        print(f"Error submitting to task queue: {e}")
        traceback.print_exc()
        return False

def compare_results(document_id, direct_content):
    """Compare the direct extraction results with the database content."""
    try:
        print(f"\n\n==== RESULTS COMPARISON ====")
        
        document = Document.query.get(document_id)
        if not document:
            print(f"Document with ID {document_id} not found")
            return
        
        db_content = document.content or ""
        direct_content = direct_content or ""
        
        print(f"Document ID: {document.id}")
        print(f"Status: {document.processing_status}")
        print(f"Error: {document.processing_error or 'None'}")
        print(f"Direct extraction length: {len(direct_content)} characters")
        print(f"Database content length: {len(db_content)} characters")
        
        if len(db_content) < 100 and len(direct_content) > 100:
            print("\nWARNING: Database content is much shorter than direct extraction")
            print("This suggests the document processing pipeline is not working correctly")
        
        # Compare content samples
        print("\n--- DIRECT EXTRACTION SAMPLE ---")
        print(direct_content[:300] + "..." if len(direct_content) > 300 else direct_content)
        
        print("\n--- DATABASE CONTENT SAMPLE ---")
        print(db_content[:300] + "..." if len(db_content) > 300 else db_content)
        
    except Exception as e:
        print(f"Error comparing results: {e}")
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description="Test URL content extraction pipeline")
    parser.add_argument("url", help="URL to test extraction on")
    parser.add_argument("--world-id", type=int, help="World ID to use (creates test world if not provided)")
    parser.add_argument("--document-id", type=int, help="Existing document ID to process (skips creation if provided)")
    parser.add_argument("--skip-task-queue", action="store_true", help="Skip task queue test")
    parser.add_argument("--only-direct", action="store_true", help="Only perform direct extraction test")
    
    args = parser.parse_args()
    
    if args.only_direct:
        # If only doing direct extraction, no need for Flask app context
        direct_content = extract_with_direct_method(args.url)
        return
    
    # Initialize Flask app context when database access is needed
    try:
        app = create_app()
        with app.app_context():
            # Always do direct extraction for comparison
            direct_content = extract_with_direct_method(args.url)
            
            # Test embedding service extraction
            embedding_service_content = test_embedding_service_extraction(args.url)
            
            # Create or get document
            document = None
            if args.document_id:
                document = Document.query.get(args.document_id)
                if document:
                    print(f"Using existing document with ID {document.id}")
                else:
                    print(f"Document with ID {args.document_id} not found, creating new document")
                    document = create_test_document(args.url, args.world_id)
            else:
                document = create_test_document(args.url, args.world_id)
            
            if not document:
                print("Failed to create or retrieve document")
                return
            
            # Process document manually
            process_document_manually(document.id)
            
            # Process using task queue if requested
            if not args.skip_task_queue:
                test_task_queue_processing(document.id)
                print("Note: Task queue processing happens in the background.")
                print("Check application logs for processing status.")
            
            # Compare results
            compare_results(document.id, direct_content)
            
            print("\n\nTests completed. Check the document in the application to see results.")
            print(f"Document ID: {document.id}")
    except Exception as e:
        print(f"Error initializing Flask app: {e}")
        traceback.print_exc()
        
        # Test embedding service extraction
        embedding_service_content = test_embedding_service_extraction(args.url)
        
        # Create or get document
        document = None
        if args.document_id:
            document = Document.query.get(args.document_id)
            if document:
                print(f"Using existing document with ID {document.id}")
            else:
                print(f"Document with ID {args.document_id} not found, creating new document")
                document = create_test_document(args.url, args.world_id)
        else:
            document = create_test_document(args.url, args.world_id)
        
        if not document:
            print("Failed to create or retrieve document")
            return
        
        # Process document manually
        process_document_manually(document.id)
        
        # Process using task queue if requested
        if not args.skip_task_queue:
            test_task_queue_processing(document.id)
            print("Note: Task queue processing happens in the background.")
            print("Check application logs for processing status.")
        
        # Compare results
        compare_results(document.id, direct_content)
        
        print("\n\nTests completed. Check the document in the application to see results.")
        print(f"Document ID: {document.id}")

if __name__ == "__main__":
    main()
