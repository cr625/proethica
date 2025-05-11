#!/usr/bin/env python3
"""
Script to fix case titles in the documents table by updating them from their source URLs.
This ensures case titles match their original source rather than just using code numbers.

For example:
- Case with title "I.3." from source "https://www.nspe.org/career-resources/ethics/public-safety-health-welfare-avoiding-rolling-blackouts" 
  would be updated to "Public Safety, Health & Welfare: Avoiding Rolling Blackouts"
"""

import sys
import logging
import traceback
import psycopg2
import psycopg2.extras
import requests
from datetime import datetime
import json
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fix_case_titles")

# Database connection parameters
DB_PARAMS = {
    "dbname": "ai_ethical_dm",
    "user": "postgres",
    "password": "PASS",
    "host": "localhost",
    "port": "5433"
}

def extract_title_from_url(url):
    """
    Extract a title from the URL.
    For NSPE URLs, attempt to create a descriptive title from the URL path segments
    """
    if not url:
        return None
    
    url_parts = urlparse(url)
    path = url_parts.path.strip('/')
    
    # For NSPE URLs, create a title from the path segments
    if 'nspe.org' in url_parts.netloc:
        path_segments = path.split('/')
        
        # Remove common segments like 'career-resources', 'ethics', etc.
        segments_to_remove = ['resources', 'career-resources', 'ethics', 'board-ethical-review-cases']
        filtered_segments = [s for s in path_segments if s not in segments_to_remove]
        
        if filtered_segments:
            # Convert hyphens to spaces and capitalize words
            title_parts = []
            for segment in filtered_segments:
                segment = segment.replace('-', ' ')
                segment = ' '.join(word.capitalize() for word in segment.split())
                title_parts.append(segment)
            
            return ': '.join(title_parts)
    
    return None

def fetch_web_title(url):
    """
    Fetch the title from a web page
    """
    if not url:
        return None
        
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try to get the page title
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.text.strip()
            
            # For NSPE cases, extract just the case title
            if 'NSPE' in title:
                # Try to extract just the case title
                title_parts = title.split(' | ')
                if len(title_parts) > 1:
                    title = title_parts[0].strip()
                
                # Remove "Case X-XX" prefix if present
                title = re.sub(r'^Case \d+-\d+:?\s*', '', title)
                
                # Remove "NSPE Board of Ethical Review" suffix if present
                title = re.sub(r'\s*-\s*NSPE Board of Ethical Review\s*$', '', title)
            
            return title
            
        # If no title tag, try to find the main heading
        h1 = soup.find('h1')
        if h1:
            return h1.text.strip()
            
        return None
    except Exception as e:
        logger.warning(f"Error fetching title from {url}: {str(e)}")
        return None

def fix_case_titles():
    """
    Update case titles in the documents table based on their source URLs
    """
    try:
        # Connect to database
        conn = psycopg2.connect(**DB_PARAMS)
        conn.autocommit = False
        cur = conn.cursor()
        
        logger.info("Connected to database")

        # Get all case documents where title is just a code and source URL is available
        cur.execute(
            """
            SELECT id, title, source
            FROM documents
            WHERE document_type = 'case_study'
            AND source IS NOT NULL
            AND source <> ''
            ORDER BY id
            """
        )
        
        cases = cur.fetchall()
        logger.info(f"Found {len(cases)} cases to process")
        
        updated_count = 0
        
        for case in cases:
            case_id = case[0]
            current_title = case[1]
            source_url = case[2]
            
            # Check if title appears to be just a code number
            title_is_code = re.match(r'^[A-Z0-9\.-]+$', current_title.strip()) is not None
            
            if title_is_code or len(current_title.split()) <= 2:
                logger.info(f"Case {case_id}: Title '{current_title}' appears to be a code or very short")
                
                # First try to fetch title from web page
                new_title = fetch_web_title(source_url)
                
                # If that fails, try to generate a title from the URL
                if not new_title:
                    logger.info(f"Could not fetch title from URL, generating from URL path")
                    new_title = extract_title_from_url(source_url)
                
                if new_title and new_title != current_title:
                    logger.info(f"Updating title for case {case_id} from '{current_title}' to '{new_title}'")
                    
                    # Update the title
                    cur.execute(
                        """
                        UPDATE documents
                        SET title = %s,
                            updated_at = %s
                        WHERE id = %s
                        """,
                        (new_title, datetime.now(), case_id)
                    )
                    
                    updated_count += 1
                else:
                    logger.info(f"No better title found for case {case_id}")
            
            # Commit every 5 cases to avoid long transactions
            if updated_count > 0 and updated_count % 5 == 0:
                conn.commit()
                logger.info(f"Committed batch of cases - {updated_count} processed so far")
        
        # Final commit
        conn.commit()
        
        # Close cursor and connection
        cur.close()
        conn.close()
        
        logger.info(f"Updated titles for {updated_count} cases in total")
        return True
    except Exception as e:
        logger.error(f"Error fixing case titles: {str(e)}")
        traceback.print_exc()
        
        # Rollback and close connections if there's an error
        if 'conn' in locals() and conn:
            conn.rollback()
            
            if 'cur' in locals() and cur:
                cur.close()
            
            conn.close()
            
        return False

if __name__ == "__main__":
    if fix_case_titles():
        logger.info("Case title fix completed successfully")
        sys.exit(0)
    else:
        logger.error("Case title fix failed")
        sys.exit(1)
