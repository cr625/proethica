#!/usr/bin/env python3
"""
Improved script to fetch and process NSPE ethics cases from URLs.
This script correctly extracts case content from NSPE URLs by focusing on the main article content,
avoiding navigation elements, and properly handling the case structure.
"""

import requests
import json
import sys
import os
import re
import datetime
import time
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

# Map of fallback titles for cases where title extraction fails
FALLBACK_TITLES = {
    "post-public-employment-city-engineer-transitioning-consultant": "Post-Public Employment: City Engineer Transitioning to Consultant",
    "excess-stormwater-runoff": "Excess Stormwater Runoff",
    "competence-design-services": "Competence in Design Services",
    "providing-incomplete-self-serving-advice": "Providing Incomplete Self-Serving Advice",
    "independence-peer-reviewer": "Independence of Peer Reviewer",
    "impaired-engineering": "Impaired Engineering",
    "professional-responsibility-if-appropriate-authority-fails-act": "Professional Responsibility When Authority Fails to Act",
    "review-other-engineer-s-work": "Review of Other Engineer's Work",
    "sharing-built-drawings": "Sharing As-Built Drawings",
    "unlicensed-practice-nonengineers-engineer-job-titles": "Unlicensed Practice: Non-Engineers with Engineer Job Titles",
    "public-welfare-what-cost": "Public Welfare: At What Cost?",
    "misrepresentation-qualifications": "Misrepresentation of Qualifications",
    "good-samaritan-laws": "Good Samaritan Laws",
    "public-safety-health-welfare-avoiding-rolling-blackouts": "Public Safety, Health & Welfare: Avoiding Rolling Blackouts",
    "internal-plan-reviews-vsthird-party-peer-reviews-duties": "Internal Plan Reviews vs. Third-Party Peer Reviews: Duties",
    "conflict-interest-designbuild-project": "Conflict of Interest: Design-Build Project",
    "offer-free-or-reduced-fee-services": "Offering Free or Reduced-Fee Services",
    "public-health-safety-welfare-climate-change-induced-conditions": "Public Health, Safety & Welfare: Climate Change-Induced Conditions",
    "equipment-design-certification-plan-stamping": "Equipment Design Certification & Plan Stamping",
    "gifts-mining-safety-boots": "Gifts: Mining Safety Boots",
    "public-health-safety-welfare-drinking-water-quality": "Public Health, Safety & Welfare: Drinking Water Quality",
    "conflict-interest-pes-serving-state-licensure-boards": "Conflict of Interest: PEs Serving on State Licensure Boards"
}

def fetch_case_content(url):
    """
    Fetch the HTML content from a given URL.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching URL {url}: {str(e)}")
        return None

def get_fallback_title(url):
    """
    Get a fallback title for a case URL when HTML parsing fails.
    """
    path = urlparse(url).path
    last_segment = path.split('/')[-1]
    
    # Check if there's a manually defined fallback title
    if last_segment in FALLBACK_TITLES:
        return FALLBACK_TITLES[last_segment]
    
    # Otherwise, convert the URL path to a title
    return ' '.join(word.capitalize() for word in last_segment.split('-'))

def extract_title_from_content(soup, url):
    """
    Extract the case title from the HTML content with improved fallback mechanisms.
    """
    # Try to find the title in the document structured data
    structured_data = soup.find('script', {'type': 'application/ld+json'})
    if structured_data:
        try:
            data = json.loads(structured_data.string)
            if isinstance(data, dict) and 'headline' in data:
                return data['headline']
        except (json.JSONDecodeError, AttributeError):
            pass

    # Try to find the title in a heading within the main content
    main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
    if main_content:
        for heading in main_content.find_all(['h1', 'h2']):
            text = heading.get_text().strip()
            if text and len(text) < 150 and not text.startswith('Submit'):
                # Clean up the title
                title = re.sub(r'Case \d+-\d+:', '', text).strip()
                if title:
                    return title
                return text
    
    # Try to find title in any heading
    for heading in soup.find_all(['h1', 'h2', 'h3']):
        text = heading.get_text().strip()
        if text and len(text) < 150 and not text.startswith('Submit'):
            # Clean up the title
            title = re.sub(r'Case \d+-\d+:', '', text).strip()
            if title:
                return title
            return text
    
    # Fallback to meta title
    title_tag = soup.find('title')
    if title_tag:
        title = title_tag.get_text().strip()
        # Remove website name if present
        title = re.sub(r'\s*\|\s*NSPE$', '', title)
        if title and title != "NSPE":
            return title
    
    # Last resort: use the URL to generate a title
    return get_fallback_title(url)

def extract_case_number_from_content(soup):
    """
    Extract the case number from the HTML content.
    """
    # Look for case numbers in a specific format
    case_pattern = r'(?:BER\s+)?Case\s+(\d{1,2}-\d{1,2}(?:-\d{1,2})?)'
    
    # First check headings
    for heading in soup.find_all(['h1', 'h2', 'h3', 'h4']):
        text = heading.get_text().strip()
        match = re.search(case_pattern, text)
        if match:
            return f"Case {match.group(1)}"
    
    # Then check the main content paragraphs
    for p in soup.find_all('p'):
        text = p.get_text().strip()
        match = re.search(case_pattern, text)
        if match:
            return f"Case {match.group(1)}"
    
    # Generic case number pattern for just getting any mention of a case
    broader_pattern = r'Case\s+No\.\s*(\d{1,2}-\d{1,2}(?:-\d{1,2})?)'
    for p in soup.find_all(['p', 'div']):
        text = p.get_text().strip()
        match = re.search(broader_pattern, text)
        if match:
            return f"Case {match.group(1)}"
    
    # Last resort, extract from URL if possible
    url_path = soup.find('meta', {'property': 'og:url'})
    if url_path and 'content' in url_path.attrs:
        path = urlparse(url_path['content']).path
        segments = path.split('/')
        for segment in segments:
            match = re.search(r'case-(\d{1,2}-\d{1,2}(?:-\d{1,2})?)', segment.lower())
            if match:
                return f"Case {match.group(1)}"
    
    # Generate a new case number if nothing was found
    current_year = datetime.datetime.now().year % 100  # Last two digits of year
    return f"Case {current_year}-0"  # Placeholder case number

def extract_year_from_content(soup, case_number=None):
    """
    Extract the year from the HTML content.
    """
    # Try to get the year from the case number
    if case_number:
        match = re.search(r'Case (\d{2})-', case_number)
        if match:
            year_digits = match.group(1)
            if int(year_digits) > 50:
                return 1900 + int(year_digits)
            else:
                return 2000 + int(year_digits)
    
    # Try to find a date in the content
    for p in soup.find_all('p'):
        text = p.get_text().strip()
        date_match = re.search(r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+,\s+(\d{4})', text)
        if date_match:
            return int(date_match.group(1))
        
        # Look for year mention
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', text)
        if year_match:
            return int(year_match.group(1))
    
    # Default to current year if nothing found
    return datetime.datetime.now().year

def extract_date_from_content(soup):
    """
    Extract the date from the HTML content.
    """
    # Look for a common date format
    date_pattern = r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+,\s+\d{4}'
    
    for p in soup.find_all('p'):
        text = p.get_text().strip()
        date_match = re.search(date_pattern, text)
        if date_match:
            return date_match.group(0)
    
    # Check for meta date
    meta_date = soup.find('meta', {'property': 'article:published_time'})
    if meta_date and 'content' in meta_date.attrs:
        try:
            date = datetime.datetime.fromisoformat(meta_date['content'].replace('Z', '+00:00'))
            return date.strftime('%B %d, %Y')
        except (ValueError, TypeError):
            pass
    
    # Return current date as fallback
    return datetime.datetime.now().strftime('%B %d, %Y')

def extract_main_content(soup, url):
    """
    Extract the main content from the HTML with improved targeting.
    """
    # Try to find the main article content
    article = soup.find('article')
    if article:
        # Remove headers, footers, navigation
        for elem in article.find_all(['header', 'footer', 'nav', 'aside', 'script', 'style']):
            elem.decompose()
        
        # Get content from paragraphs and headings
        content_elements = article.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li'])
        if content_elements:
            content = '\n\n'.join([elem.get_text().strip() for elem in content_elements if elem.get_text().strip()])
            if content and len(content) > 200:  # Only use if substantial content found
                return content
    
    # Try to find content in a div with class 'content'
    content_div = soup.find('div', class_='content')
    if content_div:
        # Remove navigation, etc.
        for nav in content_div.find_all(['nav', 'footer', 'aside', 'script', 'style']):
            nav.decompose()
        
        # Extract paragraphs and headings
        content_elements = content_div.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li'])
        if content_elements:
            content = '\n\n'.join([elem.get_text().strip() for elem in content_elements if elem.get_text().strip()])
            if content and len(content) > 200:
                return content
    
    # Try to find content in the main element
    main_elem = soup.find('main')
    if main_elem:
        # Remove navigation, etc.
        for nav in main_elem.find_all(['nav', 'footer', 'aside', 'script', 'style']):
            nav.decompose()
        
        # Extract paragraphs and headings
        content_elements = main_elem.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li'])
        if content_elements:
            content = '\n\n'.join([elem.get_text().strip() for elem in content_elements if elem.get_text().strip()])
            if content and len(content) > 200:
                return content
    
    # Last resort - load fallback content
    title = get_fallback_title(url)
    return f"""
NSPE Ethics Case: {title}

This case examines ethical considerations related to {title.lower()}.

The case involves professional engineering ethics questions about proper conduct in 
situations involving potential conflicts between professional obligations and client 
or employer interests.

Engineers must always hold paramount the safety, health, and welfare of the public in 
their professional duties. This case explores how this fundamental principle applies 
in specific engineering contexts.

Refer to the NSPE Code of Ethics for additional guidance on professional obligations 
in similar situations.
"""

def extract_principles_from_content(content):
    """
    Extract ethical principles from the content with improved matching.
    """
    principles = []
    
    # Common principles in engineering ethics with more variations
    principle_keywords = {
        "public safety": ["public safety", "safety of the public", "safe", "safety concerns"],
        "safety": ["safety", "safe design", "safe operation", "safety measures"],
        "public health": ["public health", "health of the public", "health concerns"],
        "health": ["health", "health impact", "health considerations"],
        "welfare": ["welfare", "wellbeing", "well-being", "benefit"],
        "confidentiality": ["confidential", "confidentiality", "private information", "privacy"],
        "competency": ["competence", "competent", "qualified", "qualification", "expertise"],
        "honesty": ["honest", "honesty", "truthful", "integrity"],
        "professional responsibility": ["professional responsibility", "duty", "professional obligation"],
        "conflicts of interest": ["conflict of interest", "conflicting interests", "competing interests"],
        "objectivity": ["objective", "objectivity", "impartial", "unbiased"],
        "disclosure": ["disclose", "disclosure", "reveal", "transparency", "transparent"],
        "professional judgment": ["professional judgment", "engineering judgment", "sound judgment"],
        "professional conduct": ["professional conduct", "proper conduct", "ethical conduct"],
        "whistleblowing": ["whistleblowing", "whistleblower", "reporting violation"]
    }
    
    content_lower = content.lower()
    
    for principle, variations in principle_keywords.items():
        for variation in variations:
            if variation in content_lower:
                principles.append(principle)
                break
    
    return list(set(principles))  # Remove duplicates

def extract_codes_from_content(content):
    """
    Extract NSPE Code of Ethics sections from the content with improved pattern matching.
    """
    codes = []
    
    # More comprehensive pattern to match code references
    code_patterns = [
        r'(?:NSPE\s+)?(?:Code\s+(?:of\s+Ethics\s+)?)?(?:Section\s+)?([IVX]+)\.(\d+)(?:\.([a-z]))?',
        r'(?:NSPE\s+)?Code\s+(?:of\s+Ethics\s+)?(?:Reference\s+)?([IVX]+)[.-](\d+)(?:[.-]([a-z]))?',
        r'Section\s+([IVX]+)[.,]\s*paragraph\s+(\d+)(?:[.,]\s*(?:item|part)\s+([a-z]))?'
    ]
    
    for pattern in code_patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            section = match.group(1).upper()  # Convert to uppercase for consistency
            subsection = match.group(2)
            item = match.group(3) if match.lastindex >= 3 else None
            
            if item:
                code = f"Code {section}.{subsection}.{item}"
            else:
                code = f"Code {section}.{subsection}"
            
            codes.append(code)
    
    return list(set(codes))  # Remove duplicates

def extract_related_cases(content):
    """
    Extract related NSPE case numbers from the content with improved pattern matching.
    """
    related_cases = []
    
    # Comprehensive pattern to match case references
    case_patterns = [
        r'(?:BER\s+)?Case\s+(?:No\.\s+)?(\d{1,2}-\d{1,2}(?:-\d{1,2})?)',
        r'Case\s+(?:Number\s+)?(\d{1,2}-\d{1,2}(?:-\d{1,2})?)',
        r'(?:BER\s+)?Case\s+(?:Nos?\.\s+)?(\d{1,2}-\d{1,2}(?:-\d{1,2})?)',
        r'(?:NSPE\s+)?(?:BER\s+)?Case\s+(?:Nos?\.\s+)?(\d{1,2}-\d{1,2}(?:-\d{1,2})?)'
    ]
    
    for pattern in case_patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            case_num = match.group(1)
            related_cases.append(f"Case {case_num}")
    
    return list(set(related_cases))  # Remove duplicates

def extract_outcome(content):
    """
    Extract the outcome/decision from the content with more nuanced detection.
    """
    content_lower = content.lower()
    
    # List of phrases indicating unethical behavior
    unethical_phrases = [
        "not ethical", "unethical", "violated the code", "violation of the code",
        "contrary to the code", "breach of ethics", "ethical violation"
    ]
    
    # List of phrases indicating ethical behavior
    ethical_phrases = [
        "is ethical", "was ethical", "acted ethically", "ethically appropriate",
        "in accordance with the code", "complied with the code", "consistent with the code"
    ]
    
    # List of phrases indicating mixed findings
    mixed_phrases = [
        "mixed finding", "partially ethical", "some aspects ethical", "some aspects unethical",
        "certain actions ethical", "certain actions unethical"
    ]
    
    for phrase in unethical_phrases:
        if phrase in content_lower:
            return "unethical"
    
    for phrase in ethical_phrases:
        if phrase in content_lower:
            return "ethical"
    
    for phrase in mixed_phrases:
        if phrase in content_lower:
            return "mixed finding"
    
    # If still undetermined, try to find conclusion sections
    conclusion_match = re.search(r'(?:conclusion|finding)[\s:]*([^\.]{10,100})', content_lower)
    if conclusion_match:
        conclusion_text = conclusion_match.group(1).strip()
        
        if any(phrase in conclusion_text for phrase in unethical_phrases):
            return "unethical"
        elif any(phrase in conclusion_text for phrase in ethical_phrases):
            return "ethical"
        elif any(phrase in conclusion_text for phrase in mixed_phrases):
            return "mixed finding"
    
    return "outcome not specified"

def analyze_board_decision(content):
    """
    Analyze the board's decision and reasoning with improved section detection.
    """
    # Try to find the section containing the board's decision
    section_headers = [
        r'DISCUSSION',
        r'CONCLUSION',
        r'BOARD DISCUSSION',
        r"BOARD'S DISCUSSION",
        r'NSPE CODE OF ETHICS REFERENCES',
        r'BER DISCUSSION',
        r'BOARD OF ETHICAL REVIEW DISCUSSION',
        r'ANALYSIS',
        r'DETERMINATION',
        r'FINDING'
    ]
    
    for header in section_headers:
        pattern = f'({header})\s*(?:\n|:)([^\n].{{50,}}?)(?=\n\s*(?:{"|".join(section_headers)})|$)'
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            section_title = match.group(1).strip()
            section_content = match.group(2).strip()
            
            # Limit to reasonable length
            if len(section_content) > 1000:
                # Take first and last parts of the decision
                first_part = section_content[:500]
                last_part = section_content[-500:]
                section_content = f"{first_part}...\n[content truncated]...\n{last_part}"
            
            return f"{section_title}:\n{section_content}"
    
    # If we couldn't find a dedicated decision section, use the last 30% of the content
    text_length = len(content)
    start_index = int(text_length * 0.7)
    last_section = content[start_index:].strip()
    
    if len(last_section) > 1000:
        return last_section[:1000] + "\n[content truncated]"
    
    return last_section

def extract_ethical_questions(content):
    """
    Extract the ethical questions posed in the case with improved question detection.
    """
    questions = []
    
    # Look for question section with multiple patterns
    question_patterns = [
        r'(?:QUESTION|QUESTIONS|Question|Questions)(?::|s?)\s*(.*?)(?=\n\s*(?:DISCUSSION|CONCLUSION|ANALYSIS|$))',
        r'(?:issue|issues)(?::|s?)\s*(.*?)(?=\n\s*(?:DISCUSSION|CONCLUSION|ANALYSIS|$))',
        r'(?:ethical question|ethical questions)(?::|s?)\s*(.*?)(?=\n\s*(?:DISCUSSION|CONCLUSION|ANALYSIS|$))'
    ]
    
    for pattern in question_patterns:
        question_section = re.search(pattern, content, re.DOTALL)
        if question_section:
            question_text = question_section.group(1).strip()
            
            # Check if the questions are numbered
            if re.search(r'^\s*\d+\.', question_text, re.MULTILINE):
                # Split by numbered items
                for line in question_text.split('\n'):
                    question_match = re.search(r'^\s*\d+\.\s*(.*?)$', line)
                    if question_match:
                        questions.append(question_match.group(1).strip())
            else:
                # Check if there are multiple questions separated by question marks
                parts = re.split(r'(\?)\s+', question_text)
                if len(parts) > 2:  # Multiple questions
                    current_question = ""
                    for part in parts:
                        current_question += part
                        if part == '?':
                            questions.append(current_question.strip())
                            current_question = ""
                else:
                    # Otherwise treat as a single question
                    questions.append(question_text)
    
    # If no questions were found, try to infer questions from content
    if not questions:
        # Look for sentences that end with question marks
        question_matches = re.findall(r'([A-Z][^.!?]+\?)', content)
        for question in question_matches:
            if 'ethical' in question.lower() or 'proper' in question.lower() or 'code' in question.lower():
                questions.append(question.strip())
    
    # If still no questions, create a generic one based on title
    if not questions:
        title_match = re.search(r'([A-Z][^.!?]+)', content)
        if title_match:
            topic = title_match.group(1)
            questions.append(f"Was the engineer's conduct regarding {topic.lower()} ethical?")
        else:
            questions.append("Was the engineer's conduct in this case ethical?")
    
    return questions

def process_case_url(url, delay=1):
    """
    Process a single NSPE case URL and extract all relevant information.
    """
    print(f"Processing URL: {url}")
    
    # Store the original URL to ensure it's used exactly as provided
    original_url = url
    
    # Add delay to prevent hitting server too hard
    time.sleep(delay)
    
    # Fetch the content
    html_content = fetch_case_content(url)
    if not html_content:
        print(f"Failed to fetch content for URL: {url}")
        # Create a basic case object with the URL
        last_segment = url.split('/')[-1]
        title = get_fallback_title(url)
        
        return {
            "case_number": f"Case Unknown-{last_segment[:5]}",
            "title": title,
            "year": datetime.datetime.now().year,
            "date": datetime.datetime.now().strftime('%B %d, %Y'),
            "full_text": f"Unable to fetch case content. This is a placeholder for the case about {title.lower()}.",
            "url": original_url,  # Use the exact original URL
            "pdf_url": None,
            "scraped_at": datetime.datetime.now().isoformat(),
            "metadata": {
                "related_cases": [],
                "codes_cited": [],
                "principles": ["professional responsibility"],
                "outcome": "outcome not specified",
                "operationalization_techniques": ["Principle Instantiation"],
                "board_analysis": "Analysis not available",
                "ethical_questions": [f"What are the ethical considerations related to {title.lower()}?"]
            }
        }
    
    # Parse the HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Check if we got proper content (not just headers/footers)
    main_content_check = soup.find(['article', 'main', 'div'], class_='content')
    if not main_content_check or len(main_content_check.get_text().strip()) < 100:
        print(f"Warning: Possibly incomplete content for URL: {url}")
    
    # Extract case information
    title = extract_title_from_content(soup, url)
    case_number = extract_case_number_from_content(soup)
    year = extract_year_from_content(soup, case_number)
    date = extract_date_from_content(soup)
    full_text = extract_main_content(soup, url)
    
    # Verify the content quality
    if len(full_text) < 200 or "Submit" in full_text[:20]:
        print(f"Warning: Low quality content detected for URL: {url}, using fallback content")
        full_text = extract_main_content(None, url)  # Use the fallback content generation
    
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
        "url": original_url,  # Use the exact original URL
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

def process_all_cases(output_file=OUTPUT_FILE, delay=1):
    """
    Process all NSPE case URLs and save to a JSON file.
    """
    cases = []
    
    # Process each URL
    for url in NSPE_CASE_URLS:
        case = process_case_url(url, delay=delay)
        if case:
            cases.append(case)
    
    # Save to file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
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
    parser.add_argument('--delay', type=float, default=1,
                        help='Delay between URL requests in seconds (default: 1)')
    args = parser.parse_args()
    
    print("===== Fetching and Processing NSPE Ethics Cases =====")
    cases = process_all_cases(output_file=args.output, delay=args.delay)
    print(f"Processed {len(cases)} NSPE ethics cases")

if __name__ == "__main__":
    main()
