#!/usr/bin/env python
"""Check Pass 3 entity review page"""

import requests
from bs4 import BeautifulSoup

# Get the Pass 3 review page
response = requests.get('http://localhost:5000/scenario_pipeline/case/8/entities/review/pass3')
if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')

    # Look for entity counts
    print("=== PASS 3 ENTITY REVIEW ===\n")

    # Find RDF entity count
    rdf_count = soup.find(text=lambda text: text and 'RDF entities extracted' in text)
    if rdf_count:
        print(f"RDF Count: {rdf_count.strip()}")

    # Find temporal classes/individuals counts
    temporal_labels = soup.find_all(text=lambda text: text and 'Temporal' in text)
    for label in temporal_labels[:5]:  # Show first 5 matches
        print(f"Found: {label.strip()}")

    # Check for actions_events in the HTML
    if 'actions_events' in response.text:
        print("\n✓ actions_events found in page")
    else:
        print("\n✗ actions_events NOT found in page")

    # Check for temporal properties
    if 'temporal_interval' in response.text or 'Temporal' in response.text:
        print("✓ Temporal properties found in page")
    else:
        print("✗ Temporal properties NOT found in page")

    # Look for actual entity data
    cards = soup.find_all('div', class_='card')
    print(f"\nFound {len(cards)} card elements")

    # Look for specific headers
    headers = soup.find_all('h4')
    print("\nHeaders found:")
    for h in headers:
        if 'Actions' in h.text or 'Events' in h.text or 'Temporal' in h.text:
            print(f"  - {h.text.strip()}")

else:
    print(f"Error: Status {response.status_code}")