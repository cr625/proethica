#!/usr/bin/env python3
"""
Script to fetch and process NSPE ethics cases from URLs.
This script fetches case content from NSPE URLs, extracts relevant information,
and prepares the data for import into the ProEthica system.
"""

import requests
import json
import sys
import os
import re
import datetime
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Constants
OUTPUT_FILE = "data/modern_nspe_cases.json"
CASE_TRIPLES_DIR = "data/case_triples"

# List of NSPE case URLs to process
NSPE_CASE_URLS = [
    "https://www.nspe.org/career-resources/ethics/post-public-employment-city-engineer-transitioning-consultant",
    "https://www.nspe.org/career-resources/ethics/excess-stormwater-runoff",
    "https://www.nspe.org/career-resources/ethics/competence-design-services",
    "https://www.nspe.org/career-resources/ethics/providing-incomplete-self-serving-advice",
    "https://www.nspe.org/career-resources/ethics/independence-peer-reviewer",
    "https://www.nspe.org/career-resources/ethics/impaired-engineering",
    "https://www.nspe.org/career-resources/ethics/professional-responsibility-if-appropriate-authority-fails-act",
    "https://www.nspe.org/career-resources/ethics/review-other-engineer-s-work",
    "https://www.nspe.org/career-resources/ethics/sharing-built-drawings",
    "https://www.nspe.org/career-resources/ethics/unlicensed-practice-nonengineers-engineer-job-titles",
    "https://www.nspe.org/career-resources/ethics/public-welfare-what-cost",
    "https://www.nspe.org/career-resources/ethics/misrepresentation-qualifications",
    "https://www.nspe.org/career-resources/ethics/good-samaritan-laws",
    "https://www.nspe.org/career-resources/ethics/public-safety-health-welfare-avoiding-rolling-blackouts",
    "https://www.nspe.org/career-resources/ethics/internal-plan-reviews-vsthird-party-peer-reviews-duties",
    "https://www.nspe.org/career-resources/ethics/conflict-interest-designbuild-project",
    "https://www.nspe.org/career-resources/ethics/offer-free-or-reduced-fee-services",
    "https://www.nspe.org/career-resources/ethics/public-health-safety-welfare-climate-change-induced-conditions",
    "https://www.nspe.org/career-resources/ethics/equipment-design-certification-plan-stamping",
    "https://www.nspe.org/career-resources/ethics/gifts-mining-safety-boots",
    "https://www.nspe.org/career-resources/ethics/public-health-safety-welfare-drinking-water-quality",
    "https://www.nspe.org/career-resources/ethics/conflict-interest-pes-serving-state-licensure-boards"
]

def fetch_case_content(url):
    """
    Fetch the HTML content from a given URL.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching URL {url}: {str(e)}")
        return None

def parse_case_number_from_url(url):
    """
    Extract a potential case number from a URL.
    """
    path = urlparse(url).path
    segments = path.split('/')
    
    # Look for a segment that might be a case number
    for segment in segments:
        if re.match(r'case-\d+-\d+', segment.lower()):
            return segment.upper()
    
    # Extract the last path segment as a fallback
    last_segment = segments[-1] if segments else ""
    if last_segment:
        # Convert kebab-case to title case
        title = ' '.join(word.capitalize() for word in last_segment.split('-'))
        return f"Case {title}"
    
    return None

def extract_title_from_content(soup):
    """
    Extract the case title from the HTML content.
    """
    # Try to find the title in a heading
    for heading in soup.find_all(['h1', 'h2', 'h3']):
        text = heading.get_text().strip()
        if text and len(text) < 150 and not text.startswith('Submit'):
            # Clean up the title
            title = re.sub(r'Case \d+-\d+:', '', text).strip()
            if not title:
                title = text
            return title
    
    # Fallback to meta title
    title_tag = soup.find('title')
    if title_tag:
        title = title_tag.get_text().strip()
        # Remove website name if present
        title = re.sub(r'\s*\|\s*NSPE$', '', title)
        return title
    
    return None

def extract_case_number_from_content(soup):
    """
    Extract the case number from the HTML content.
    """
    for heading in soup.find_all(['h1', 'h2', 'h3']):
        text = heading.get_text().strip()
        match = re.search(r'Case (\d+-\d+)', text)
        if match:
            return f"Case {match.group(1)}"
    
    # Search in paragraphs
    for p in soup.find_all('p'):
        text = p.get_text().strip()
        match = re.search(r'Case (\d+-\d+)', text)
        if match:
            return f"Case {match.group(1)}"
    
    return None

def extract_year_from_content(soup):
    """
    Extract the year from the HTML content.
    """
    # Try to get the year from the case number
    case_number = extract_case_number_from_content(soup)
    if case_number:
        match = re.search(r'Case (\d+)-', case_number)
        if match:
            return int(match.group(1)) + 2000  # Assuming 20xx years
    
    # Try to find a date in the content
    for p in soup.find_all('p'):
        text = p.get_text().strip()
        date_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+,\s+(\d{4})', text)
        if date_match:
            return int(date_match.group(2))
    
    # Default to current year if nothing found
    return datetime.datetime.now().year

def extract_date_from_content(soup):
    """
    Extract the date from the HTML content.
    """
    for p in soup.find_all('p'):
        text = p.get_text().strip()
        date_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+,\s+\d{4}', text)
        if date_match:
            return date_match.group(0)
    
    return None

def extract_main_content(soup):
    """
    Extract the main content from the HTML.
    """
    # Look for the main content divs
    content_div = soup.find('div', class_='content')
    
    if not content_div:
        # Try to find the main content area
        content_div = soup.find('main')
        if not content_div:
            content_div = soup.find('article')
            if not content_div:
                content_div = soup
    
    # Extract just the relevant content (excluding navigation, etc.)
    # Remove irrelevant sections
    for nav in content_div.find_all(['nav', 'footer', 'aside', 'script', 'style']):
        nav.decompose()
    
    # Extract paragraphs and headings
    content_elements = content_div.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li'])
    
    if not content_elements:
        # Fallback to div text if structured elements aren't found
        content = content_div.get_text().strip()
    else:
        content = '\n\n'.join([elem.get_text().strip() for elem in content_elements if elem.get_text().strip()])
    
    return content

def extract_html_content(soup):
    """
    Extract a cleaned HTML content section.
    """
    # Look for the main content divs
    content_div = soup.find('div', class_='content')
    
    if not content_div:
        # Try to find the main content area
        content_div = soup.find('main')
        if not content_div:
            content_div = soup.find('article')
            if not content_div:
                # Create a new div with the body content
                content_div = soup.new_tag('div')
                content_div.append(soup.body.prettify() if soup.body else soup.prettify())
    
    # Remove irrelevant sections
    for nav in content_div.find_all(['nav', 'footer', 'aside', 'script', 'style']):
        nav.decompose()
    
    return str(content_div)

def extract_principles_from_content(content):
    """
    Extract ethical principles from the content.
    """
    principles = []
    
    # Common principles in engineering ethics
    principle_keywords = [
        "public safety", "safety", "public health", "health", "welfare", 
        "confidentiality", "competency", "honesty", "professional responsibility",
        "conflicts of interest", "objectivity", "disclosure", "integrity",
        "professional judgment", "professional conduct", "whistleblowing"
    ]
    
    content_lower = content.lower()
    
    for principle in principle_keywords:
        if principle in content_lower:
            principles.append(principle)
    
    return list(set(principles))  # Remove duplicates

def extract_codes_from_content(content):
    """
    Extract NSPE Code of Ethics sections from the content.
    """
    codes = []
    
    # Look for code references like "Code I.1", "Code II.4.a", etc.
    code_pattern = r'Code\s+([IVX]+)\.(\d+)(?:\.([a-z]))?'
    matches = re.finditer(code_pattern, content, re.IGNORECASE)
    
    for match in matches:
        section = match.group(1)
        subsection = match.group(2)
        item = match.group(3)
        
        if item:
            code = f"Code {section}.{subsection}.{item}"
        else:
            code = f"Code {section}.{subsection}"
        
        codes.append(code)
    
    return list(set(codes))  # Remove duplicates

def extract_related_cases(content):
    """
    Extract related NSPE case numbers from the content.
    """
    related_cases = []
    
    # Pattern to match case references like "Case 97-3", "BER Case 89-7-1", etc.
    case_pattern = r'(?:BER\s+)?Case\s+(\d+-\d+(?:-\d+)?)'
    matches = re.finditer(case_pattern, content, re.IGNORECASE)
    
    for match in matches:
        case_num = match.group(1)
        related_cases.append(f"Case {case_num}")
    
    return list(set(related_cases))  # Remove duplicates

def extract_outcome(content):
    """
    Extract the outcome/decision from the content.
    """
    content_lower = content.lower()
    
    if "not ethical" in content_lower or "unethical" in content_lower:
        return "unethical"
    elif "ethical" in content_lower:
        return "ethical"
    elif "mixed finding" in content_lower or "partially ethical" in content_lower:
        return "mixed finding"
    
    return "outcome not specified"

def analyze_board_decision(content):
    """
    Analyze the board's decision and reasoning.
    """
    # Try to find the section containing the board's decision
    lines = content.split('\n')
    decision_text = ""
    capturing = False
    
    # Keywords that might indicate the start of a decision section
    decision_keywords = [
        "DISCUSSION", "CONCLUSION", "BOARD DISCUSSION", "BOARD'S DISCUSSION",
        "NSPE CODE OF ETHICS REFERENCES", "BER DISCUSSION"
    ]
    
    for line in lines:
        # Check if we should start capturing
        if not capturing:
            for keyword in decision_keywords:
                if keyword in line.upper() and len(line) < 100:
                    capturing = True
                    break
        
        # If we're capturing, add the line to the decision text
        if capturing:
            decision_text += line + "\n"
    
    # If we couldn't find a dedicated decision section, use the last 20% of the content
    if not decision_text:
        text_length = len(content)
        start_index = int(text_length * 0.8)
        decision_text = content[start_index:]
    
    # Summarize to a reasonable length
    if len(decision_text) > 1000:
        # Take first and last parts of the decision
        first_part = decision_text[:500]
        last_part = decision_text[-500:]
        decision_text = first_part + "..." + last_part
    
    return decision_text.strip()

def extract_ethical_questions(content):
    """
    Extract the ethical questions posed in the case.
    """
    questions = []
    
    # Look for question section
    question_section = re.search(r'(?:QUESTION|QUESTIONS|Question|Questions)(?:\s*:\s*|\s*\?\s*)(.*?)(?=\n\n|\Z)', content, re.DOTALL)
    
    if question_section:
        question_text = question_section.group(1).strip()
        
        # Split into multiple questions if numbered
        if re.search(r'^\s*\d+\.', question_text, re.MULTILINE):
            for line in question_text.split('\n'):
                question_match = re.search(r'^\s*\d+\.\s*(.*?)$', line)
                if question_match:
                    questions.append(question_match.group(1).strip())
        else:
            # Otherwise treat as a single question
            questions.append(question_text)
    
    return questions

def process_case_url(url):
    """
    Process a single NSPE case URL and extract all relevant information.
    """
    print(f"Processing URL: {url}")
    
    # Fetch the content
    html_content = fetch_case_content(url)
    if not html_content:
        print(f"Failed to fetch content for URL: {url}")
        return None
    
    # Parse the HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract case information
    title = extract_title_from_content(soup)
    case_number = extract_case_number_from_content(soup)
    if not case_number:
        case_number = parse_case_number_from_url(url)
    
    year = extract_year_from_content(soup)
    date = extract_date_from_content(soup)
    full_text = extract_main_content(soup)
    cleaned_html = extract_html_content(soup)
    
    # Extract metadata
    principles = extract_principles_from_content(full_text)
    codes_cited = extract_codes_from_content(full_text)
    related_cases = extract_related_cases(full_text)
    outcome = extract_outcome(full_text)
    board_analysis = analyze_board_decision(full_text)
    ethical_questions = extract_ethical_questions(full_text)
    
    # Create the case object
    case = {
        "case_number": case_number,
        "title": title,
        "year": year,
        "date": date,
        "full_text": full_text,
        "html_content": cleaned_html,
        "url": url,
        "pdf_url": None,  # This would need additional processing to find PDF links
        "scraped_at": datetime.datetime.now().isoformat(),
        "metadata": {
            "related_cases": related_cases,
            "codes_cited": codes_cited,
            "principles": principles,
            "outcome": outcome,
            "operationalization_techniques": [
                "Principle Instantiation",
                "Case Instantiation" if related_cases else None,
                "Conflicting Principles Resolution" if len(principles) > 1 else None
            ],
            "board_analysis": board_analysis,
            "ethical_questions": ethical_questions
        }
    }
    
    # Remove None values from operationalization_techniques
    case["metadata"]["operationalization_techniques"] = [
        tech for tech in case["metadata"]["operationalization_techniques"] if tech
    ]
    
    print(f"Successfully processed case: {title} ({case_number})")
    return case

def process_all_cases(output_file=OUTPUT_FILE):
    """
    Process all NSPE case URLs and save to a JSON file.
    """
    cases = []
    
    # Process each URL
    for url in NSPE_CASE_URLS:
        case = process_case_url(url)
        if case:
            cases.append(case)
    
    # Save to file
    with open(output_file, 'w') as f:
        json.dump(cases, f, indent=2)
    
    print(f"Saved {len(cases)} cases to {output_file}")
    return cases

def main():
    """
    Main function to process all NSPE case URLs.
    """
    import argparse
    parser = argparse.ArgumentParser(description='Fetch and process NSPE ethics cases')
    parser.add_argument('--output', type=str, default=OUTPUT_FILE,
                        help=f'Output JSON file path (default: {OUTPUT_FILE})')
    args = parser.parse_args()
    
    print("===== Fetching and Processing NSPE Ethics Cases =====")
    cases = process_all_cases(output_file=args.output)
    print(f"Processed {len(cases)} NSPE ethics cases")

if __name__ == "__main__":
    main()
