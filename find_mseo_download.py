#!/usr/bin/env python3
"""
Script to find MSEO download links from the matportal.org website.
"""

import requests
from bs4 import BeautifulSoup
import re
import sys

def find_download_links(url):
    """Find potential download links on the page."""
    print(f"Examining {url} for download links...")
    
    # Send request with timeout
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    
    # Parse HTML
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Look for download links
    download_links = []
    
    # Method 1: Look for links with specific text
    for a in soup.find_all('a'):
        text = a.get_text().lower()
        href = a.get('href')
        if href and any(keyword in text for keyword in ['download', 'owl', 'ontology', 'rdf']):
            download_links.append((text.strip(), href))
    
    # Method 2: Look for links with specific extensions
    for a in soup.find_all('a'):
        href = a.get('href')
        if href and any(href.endswith(ext) for ext in ['.owl', '.rdf', '.xml', '.ttl']):
            download_links.append((a.get_text().strip() or '[No text]', href))
    
    # Method 3: Look for links with specific patterns in URL
    for a in soup.find_all('a'):
        href = a.get('href')
        if href and any(pattern in href for pattern in ['download', 'ontology', 'mseo']):
            download_links.append((a.get_text().strip() or '[No text]', href))
    
    # Print all found links
    print(f"Found {len(download_links)} potential download links:")
    for text, href in download_links:
        print(f"  - {text}: {href}")
    
    # Also look for embedded ontology data
    for script in soup.find_all('script'):
        text = script.get_text()
        if any(keyword in text.lower() for keyword in ['owl', 'rdf', 'ontology']):
            print("Potential embedded ontology data found in script tag")
    
    # Look for iframes that might load the ontology
    for iframe in soup.find_all('iframe'):
        src = iframe.get('src')
        if src:
            print(f"Iframe found with src: {src}")
    
    return download_links

def main():
    """Main function."""
    url = "https://matportal.org/ontologies/MSEO"
    
    try:
        download_links = find_download_links(url)
        
        # If no download links found, print a message
        if not download_links:
            print("No download links found on the page.")
            print("You may need to manually inspect the website.")
        
        return 0
    
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
