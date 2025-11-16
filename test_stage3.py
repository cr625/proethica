"""
Quick test of Stage 3 participant mapping for Case 8.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.services.scenario_generation.data_collector import ScenarioDataCollector
from app.services.scenario_generation.participant_mapper import ParticipantMapper

def test_stage3():
    """Test Stage 3 participant mapping."""
    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("Testing Stage 3: Participant Mapping for Case 8")
        print("=" * 60)

        # Step 1: Collect data
        print("\n[1/4] Collecting data...")
        collector = ScenarioDataCollector()
        data = collector.collect_all_data(case_id=8)

        roles = data.get_entities_by_type('Roles')
        print(f"  Found {len(roles)} roles")

        # Step 2: Map participants
        print("\n[2/4] Mapping participants...")
        mapper = ParticipantMapper()
        result = mapper.map_participants(roles)

        print(f"  Created {len(result.participants)} participants")
        print(f"  Protagonist: {result.protagonist_id}")
        print(f"  LLM Enhanced: {result.llm_enrichment is not None}")

        # Step 3: Display participant details
        print("\n[3/4] Participant Details:")
        for p in result.participants:
            print(f"\n  {p.name} ({p.narrative_role})")
            print(f"    Role Type: {p.role_type}")
            print(f"    Motivations: {len(p.motivations)}")
            print(f"    Obligations: {len(p.obligations)}")
            print(f"    Tensions: {len(p.ethical_tensions)}")
            print(f"    Character Arc: {p.character_arc[:100]}...")

        # Step 4: Save to database
        print("\n[4/4] Saving to database...")
        saved_count = mapper.save_to_database(
            case_id=8,
            result=result,
            llm_model='claude-3-5-sonnet-20241022'
        )
        print(f"  Saved {saved_count} participants")

        print("\n" + "=" * 60)
        print("Stage 3 Test Complete!")
        print("=" * 60)

        # Display teaching notes if available
        if result.teaching_notes:
            print("\nTeaching Notes:")
            import json
            print(json.dumps(result.teaching_notes, indent=2))

        return result

if __name__ == '__main__':
    test_stage3()
