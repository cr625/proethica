"""
Test script for Step 4 Part D: Institutional Rule Analyzer

Tests the analyzer on Case 8 to analyze principle tensions,
obligation conflicts, and constraint influences.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.services.case_analysis.institutional_rule_analyzer import InstitutionalRuleAnalyzer
from sqlalchemy import text

def get_entities_from_db(case_id, entity_type):
    """Fetch entities from temporary_rdf_storage."""
    from app.models import db
    
    query = text("""
        SELECT entity_label, entity_definition, rdf_json_ld, uri
        FROM temporary_rdf_storage
        WHERE case_id = :case_id AND entity_type = :entity_type
    """)
    
    result = db.session.execute(query, {
        'case_id': case_id,
        'entity_type': entity_type
    })
    
    entities = []
    for row in result:
        # Create a simple object with attributes
        class Entity:
            def __init__(self, label, definition, rdf_json_ld, uri):
                self.label = label
                self.definition = definition
                self.rdf_json_ld = rdf_json_ld
                self.uri = uri
        
        entities.append(Entity(
            row.entity_label,
            row.entity_definition,
            row.rdf_json_ld,
            row.uri
        ))
    
    return entities


def test_institutional_analyzer():
    """Test institutional rule analyzer on Case 8."""
    
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("Testing Step 4 Part D: Institutional Rule Analyzer (Case 8)")
        print("=" * 80)
        
        case_id = 8
        
        # Step 1: Fetch entities from database
        print("\n[1/4] Fetching entities from database...")
        principles = get_entities_from_db(case_id, 'Principles')
        obligations = get_entities_from_db(case_id, 'Obligations')
        constraints = get_entities_from_db(case_id, 'Constraints')
        
        print(f"  Principles: {len(principles)}")
        print(f"  Obligations: {len(obligations)}")
        print(f"  Constraints: {len(constraints)}")
        
        if not principles and not obligations:
            print("\n  ERROR: No principles or obligations found!")
            print("  Make sure Case 8 has completed Pass 2 extraction.")
            return
        
        # Step 2: Initialize analyzer
        print("\n[2/4] Initializing Institutional Rule Analyzer...")
        analyzer = InstitutionalRuleAnalyzer()
        
        # Step 3: Run analysis
        print("\n[3/4] Running institutional rule analysis...")
        print("  (This may take 30-60 seconds as LLM analyzes all entities...)")
        
        try:
            analysis = analyzer.analyze_case(
                case_id=case_id,
                principles=principles,
                obligations=obligations,
                constraints=constraints
            )
            
            print("\n  ✓ Analysis complete!")
            
            # Display results
            print("\n" + "=" * 80)
            print("INSTITUTIONAL ANALYSIS RESULTS")
            print("=" * 80)
            
            print("\n### PRINCIPLE TENSIONS ###")
            print(f"Found {len(analysis.principle_tensions)} principle tensions\n")
            for i, pt in enumerate(analysis.principle_tensions, 1):
                print(f"{i}. {pt.principle1} vs {pt.principle2}")
                print(f"   Tension: {pt.tension_description}")
                print(f"   Significance: {pt.symbolic_significance}")
                print()
            
            print(f"Overall: {analysis.principle_conflict_description}\n")
            
            print("\n### OBLIGATION CONFLICTS ###")
            print(f"Found {len(analysis.obligation_conflicts)} obligation conflicts\n")
            for i, oc in enumerate(analysis.obligation_conflicts, 1):
                print(f"{i}. {oc.obligation1} ({oc.obligation1_code_section})")
                print(f"   vs {oc.obligation2} ({oc.obligation2_code_section})")
                print(f"   Conflict: {oc.conflict_description}")
                print()
            
            print(f"Overall: {analysis.obligation_conflict_description}\n")
            
            print("\n### CONSTRAINING FACTORS ###")
            print(f"Found {len(analysis.constraining_factors)} constraining factors\n")
            for i, cf in enumerate(analysis.constraining_factors, 1):
                print(f"{i}. {cf.constraint} (Type: {cf.constraint_type})")
                print(f"   Impact: {cf.impact_description}")
                print()
            
            print(f"Overall: {analysis.constraint_influence_description}\n")
            
            print("\n### CASE SIGNIFICANCE ###")
            print(analysis.case_significance)
            print()
            
            # Step 4: Save to database
            print("\n[4/4] Saving to database...")
            success = analyzer.save_to_database(
                case_id=case_id,
                analysis=analysis,
                llm_model='claude-sonnet-4-5-20250929'
            )
            
            if success:
                print("  ✓ Saved to case_institutional_analysis table")
                
                # Verify database save
                from app.models import db
                verify_query = text("""
                    SELECT case_significance
                    FROM case_institutional_analysis
                    WHERE case_id = :case_id
                """)
                result = db.session.execute(verify_query, {'case_id': case_id})
                row = result.fetchone()
                if row:
                    print(f"  ✓ Verified in database")
                else:
                    print("  ✗ Not found in database after save")
            
            print("\n" + "=" * 80)
            print("TEST COMPLETE!")
            print("=" * 80)
            
            # Show how to query
            print("\nTo view this analysis later, query:")
            print(f"  SELECT * FROM case_institutional_analysis WHERE case_id = {case_id};")
            
        except Exception as e:
            print(f"\n  ✗ Analysis failed: {e}")
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    test_institutional_analyzer()
