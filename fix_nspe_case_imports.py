import os
import json
import sys
import datetime
from app import db, create_app
from app.models import Document, World

CORRECT_URL_PREFIX = "https://www.nspe.org/career-resources/ethics/"

# Original URLs provided by user
ORIGINAL_URLS = [
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

def fix_case_titles_and_urls(world_id=1):
    """Fix case titles and URLs for NSPE cases in the specified world"""
    print(f"===== Fixing NSPE Case Titles and URLs for World {world_id} =====")
    
    # Initialize the app with its context
    app = create_app()
    with app.app_context():
        world = db.session.get(World, world_id)
        if not world:
            print(f"Error: World with ID {world_id} not found")
            return
        
        print(f"Working with world: {world.name}")
        
        # Get all case study documents for this world
        cases = Document.query.filter_by(
            document_type="case_study", 
            world_id=world_id
        ).all()
        
        print(f"Found {len(cases)} case study documents")
        
        # Track which of the original URLs have been processed
        processed_urls = set()
        
        for case in cases:
            original_url = case.source
            
            # Skip cases that don't have a URL starting with either prefix
            if not original_url or (
                not original_url.startswith(CORRECT_URL_PREFIX) and 
                not original_url.startswith("https://www.nspe.org/resources/")
            ):
                print(f"Skipping case {case.id} with URL: {original_url}")
                continue
                
            path = extract_path_from_url(original_url)
            correct_url = f"{CORRECT_URL_PREFIX}{path}"
            
            if correct_url in ORIGINAL_URLS:
                processed_urls.add(correct_url)
                
                # Get a better title for the case
                better_title = get_title_for_url(correct_url)
                
                print(f"Updating case {case.id}:")
                if case.source != correct_url:
                    print(f"  URL: {case.source} -> {correct_url}")
                if case.title != better_title:
                    print(f"  Title: {case.title} -> {better_title}")
                
                # Update the case
                case.source = correct_url
                case.title = better_title
                db.session.commit()
            else:
                print(f"Skipping case {case.id} with URL not in original list: {original_url}")
        
        # Report on URLs that weren't processed
        missing_urls = set(ORIGINAL_URLS) - processed_urls
        if missing_urls:
            print("\nThe following URLs were not found in the database:")
            for url in missing_urls:
                print(f"  {url}")
        
        print("\nCase title and URL fixes completed!")

if __name__ == "__main__":
    world_id = 1
    if len(sys.argv) > 1:
        world_id = int(sys.argv[1])
    
    fix_case_titles_and_urls(world_id)
