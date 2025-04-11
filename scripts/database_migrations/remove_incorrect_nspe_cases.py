import sys
from app import db, create_app
from app.models import Document, World, entity_triple
from sqlalchemy import text

def remove_incorrect_cases(world_id=1):
    """Remove NSPE cases that don't match our expected URL patterns or have code section titles"""
    print(f"===== Removing Incorrect NSPE Cases from World {world_id} =====")
    
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
        
        # List of patterns that indicate incorrect cases
        incorrect_patterns = [
            "Preamble", 
            "I.", "II.", "III.", "IV.", "V.", "VI.", "VII.", "VIII.", "IX.", "X.",
            "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10.",
            "Section", 
            "Pre Header Utility Links"
        ]
        
        # Track cases for removal
        cases_to_remove = []
        for case in cases:
            # Check if title contains any of the incorrect patterns
            if any(pattern in case.title for pattern in incorrect_patterns) or case.title.startswith(tuple(incorrect_patterns)):
                cases_to_remove.append(case)
                print(f"Marking for removal: Case {case.id} - '{case.title}'")
            
            # Also check if URL doesn't match expected NSPE pattern
            elif case.source and "nspe.org" in case.source and not (
                case.source.startswith("https://www.nspe.org/career-resources/ethics/") or
                case.source.startswith("https://www.nspe.org/resources/ethics/")
            ):
                cases_to_remove.append(case)
                print(f"Marking for removal: Case {case.id} - '{case.title}' with invalid URL: {case.source}")
        
        print(f"\nFound {len(cases_to_remove)} cases to remove")
        
        if not cases_to_remove:
            print("No cases to remove!")
            return
        
        # Automatic confirmation for easier execution
        print("\nProceeding with removal...")
        
        # Remove the cases
        removed_count = 0
        for case in cases_to_remove:
            print(f"Removing case {case.id}: {case.title}")
            
            # First delete any associated entity triples
            try:
                # Use raw SQL to avoid potential ORM complexities
                db.session.execute(
                    text("DELETE FROM entity_triples WHERE entity_type = 'document' AND entity_id = :case_id"),
                    {"case_id": case.id}
                )
                # Also delete the document
                db.session.delete(case)
                db.session.commit()
                removed_count += 1
            except Exception as e:
                db.session.rollback()
                print(f"Error removing case {case.id}: {str(e)}")
        
        print(f"\nSuccessfully removed {removed_count} cases")

if __name__ == "__main__":
    world_id = 1
    if len(sys.argv) > 1:
        world_id = int(sys.argv[1])
    
    remove_incorrect_cases(world_id)
