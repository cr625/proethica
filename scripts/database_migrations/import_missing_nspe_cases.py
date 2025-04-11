import os
import json
import sys
import requests
from bs4 import BeautifulSoup
import time
import re
from app import db, create_app
from app.models import Document, World

# URLs of NSPE cases to import
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

# Map URL paths to better title formats
URL_TO_TITLE_MAP = {
    "post-public-employment-city-engineer-transitioning-consultant": "Post-Public Employment: City Engineer Transitioning to Consultant",
    "excess-stormwater-runoff": "Excess Stormwater Runoff",
    "competence-design-services": "Competence in Design Services",
    "providing-incomplete-self-serving-advice": "Providing Incomplete Self-Serving Advice",
    "independence-peer-reviewer": "Independence of Peer Reviewer", 
    "impaired-engineering": "Impaired Engineering Practice",
    "professional-responsibility-if-appropriate-authority-fails-act": "Professional Responsibility When Authority Fails to Act",
    "review-other-engineer-s-work": "Reviewing Another Engineer's Work",
    "sharing-built-drawings": "Sharing As-Built Drawings",
    "unlicensed-practice-nonengineers-engineer-job-titles": "Unlicensed Practice and Non-Engineer Titles",
    "public-welfare-what-cost": "Public Welfare: At What Cost?",
    "misrepresentation-qualifications": "Misrepresentation of Qualifications",
    "good-samaritan-laws": "Good Samaritan Laws for Engineers",
    "public-safety-health-welfare-avoiding-rolling-blackouts": "Public Safety: Avoiding Rolling Blackouts",
    "internal-plan-reviews-vsthird-party-peer-reviews-duties": "Internal vs. Third-Party Plan Reviews",
    "conflict-interest-designbuild-project": "Conflict of Interest in Design-Build Projects",
    "offer-free-or-reduced-fee-services": "Offering Free or Reduced-Fee Services",
    "public-health-safety-welfare-climate-change-induced-conditions": "Public Safety and Climate Change Conditions",
    "equipment-design-certification-plan-stamping": "Equipment Design Certification and Plan Stamping",
    "gifts-mining-safety-boots": "Gifts: Mining Safety Boots",
    "public-health-safety-welfare-drinking-water-quality": "Public Safety: Drinking Water Quality",
    "conflict-interest-pes-serving-state-licensure-boards": "Conflict of Interest: Engineers on Licensing Boards"
}

def extract_path_from_url(url):
    """Extract the path portion from a URL"""
    if not url:
        return ""
    parts = url.split("/")
    if len(parts) > 4:
        return parts[-1]  # Get the last part of the URL
    return ""

def get_title_for_url(url):
    """Get a better title for the given URL"""
    path = extract_path_from_url(url)
    if path in URL_TO_TITLE_MAP:
        return URL_TO_TITLE_MAP[path]
    # Fall back to title-cased path with hyphens replaced by spaces
    return path.replace('-', ' ').title()

def clean_text(text):
    """Clean up text by removing extra whitespace"""
    # Replace multiple spaces with a single space
    text = re.sub(r'\s+', ' ', text)
    # Replace multiple newlines with a single newline
    text = re.sub(r'\n+', '\n', text)
    # Trim whitespace
    return text.strip()

def fetch_case_content(url):
    """Fetch and parse case content from a URL"""
    print(f"Fetching content from {url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title
        title_elem = soup.find('h1')
        title = title_elem.text.strip() if title_elem else get_title_for_url(url)
        
        # Get the main content
        content_elem = soup.find('div', class_='field-name-body')
        if content_elem:
            content = content_elem.get_text('\n', strip=True)
        else:
            # Try alternative content selectors
            content_elem = soup.find('article')
            if content_elem:
                content = content_elem.get_text('\n', strip=True)
            else:
                # Just get the body text if we can't find specific content elements
                content = soup.body.get_text('\n', strip=True)
        
        # Clean up the content
        content = clean_text(content)
        
        return {
            'title': title,
            'content': content,
            'source': url
        }
        
    except Exception as e:
        print(f"Error fetching content from {url}: {str(e)}")
        return None

def check_case_exists(url, world_id):
    """Check if a case with the given URL already exists in the world"""
    app = create_app()
    with app.app_context():
        case = Document.query.filter_by(
            document_type="case_study", 
            world_id=world_id,
            source=url
        ).first()
        return case is not None

def import_nspe_cases(world_id=1):
    """Import NSPE cases from URLs into the given world"""
    print(f"===== Importing NSPE Cases to World {world_id} =====")
    
    app = create_app()
    with app.app_context():
        world = db.session.get(World, world_id)
        if not world:
            print(f"Error: World with ID {world_id} not found")
            return
        
        print(f"Working with world: {world.name}")
        
        # Keep track of successfully imported cases
        imported_count = 0
        skipped_count = 0
        failed_count = 0
        
        for url in NSPE_CASE_URLS:
            # Check if case already exists
            if check_case_exists(url, world_id):
                print(f"Case already exists: {url}")
                skipped_count += 1
                continue
            
            # Fetch case content
            case_data = fetch_case_content(url)
            if not case_data:
                print(f"Failed to fetch case from {url}")
                failed_count += 1
                continue
            
            # Use our improved title if the extracted one is not good
            better_title = get_title_for_url(url)
            if len(case_data['title']) < 10 or any(pattern in case_data['title'] for pattern in ["NSPE", "Case", "Board of Ethical Review"]):
                case_data['title'] = better_title
            
            print(f"Importing case: {case_data['title']}")
            print(f"  URL: {url}")
            print(f"  Content length: {len(case_data['content'])} characters")
            
            # Create the case document
            try:
                case_doc = Document(
                    title=case_data['title'],
                    content=case_data['content'],
                    source=case_data['source'],
                    document_type="case_study",
                    world_id=world_id,
                    doc_metadata=json.dumps({
                        "imported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "improved_title": better_title
                    })
                )
                
                db.session.add(case_doc)
                db.session.commit()
                imported_count += 1
                print(f"  Imported successfully as case ID: {case_doc.id}")
                
            except Exception as e:
                db.session.rollback()
                print(f"Error creating case document: {str(e)}")
                failed_count += 1
            
            # Sleep briefly to be nice to the server
            time.sleep(1)
        
        print(f"\nImport results:")
        print(f"  Successfully imported: {imported_count} cases")
        print(f"  Skipped (already exist): {skipped_count} cases")
        print(f"  Failed: {failed_count} cases")

if __name__ == "__main__":
    world_id = 1
    if len(sys.argv) > 1:
        world_id = int(sys.argv[1])
    
    import_nspe_cases(world_id)
