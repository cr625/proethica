"""
Quick test script for Step 4 Part E (ActionRuleMapper)
Tests on Case 8 with existing entities
"""

import sys
from app import create_app
from app.services.case_analysis.action_rule_mapper import ActionRuleMapper
from app.models import TemporaryRDFStorage
from sqlalchemy import func

def test_part_e_case_8():
    """Test Part E on Case 8"""
    app = create_app()

    with app.app_context():
        case_id = 8

        # Fetch all entities for Case 8
        print(f"[Test] Fetching entities for Case {case_id}...")

        entity_types = [
            'actions', 'events', 'states', 'roles', 'resources',
            'Capabilities', 'Principles', 'Obligations', 'Constraints'
        ]

        entities = {}
        for entity_type in entity_types:
            entities[entity_type] = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                func.lower(TemporaryRDFStorage.entity_type) == entity_type.lower(),
                TemporaryRDFStorage.storage_type == 'individual'
            ).all()
            print(f"  - {entity_type}: {len(entities[entity_type])} entities")

        # Initialize ActionRuleMapper
        print("\n[Test] Initializing ActionRuleMapper...")
        mapper = ActionRuleMapper()

        # Build case context
        case_context = {
            'questions': ['Is it ethical for Engineer to walk away?'],
            'conclusions': ['Engineer has duty to notify authorities'],
            'provisions': ['III.1.a - Public safety paramount', 'III.2.a - Practice competently']
        }

        # Run action-rule mapping
        print("\n[Test] Running action-rule mapping analysis...")
        try:
            mapping = mapper.analyze_case(
                case_id=case_id,
                actions=entities['actions'],
                events=entities['events'],
                states=entities['states'],
                roles=entities['roles'],
                resources=entities['resources'],
                capabilities=entities['Capabilities'],
                principles=entities['Principles'],
                obligations=entities['Obligations'],
                constraints=entities['Constraints'],
                case_context=case_context
            )

            print("\n[Test] ✓ Analysis complete!")
            print(f"\n=== ACTION RULE (What?) ===")
            print(f"Actions taken: {len(mapping.action_rule.actions_taken)}")
            for action in mapping.action_rule.actions_taken:
                print(f"  - {action}")

            print(f"\nActions NOT taken: {len(mapping.action_rule.actions_not_taken)}")
            for action in mapping.action_rule.actions_not_taken:
                print(f"  - {action}")

            print(f"\nAlternatives: {len(mapping.action_rule.alternatives_available)}")
            for alt in mapping.action_rule.alternatives_available:
                print(f"  - {alt}")

            print(f"\n=== INSTITUTIONAL RULE (Why?) ===")
            print(f"Justifications: {len(mapping.institutional_rule.justifications)}")
            for just in mapping.institutional_rule.justifications:
                print(f"  - {just}")

            print(f"\nOppositions: {len(mapping.institutional_rule.oppositions)}")
            for opp in mapping.institutional_rule.oppositions:
                print(f"  - {opp}")

            print(f"\nRelevant Obligations: {len(mapping.institutional_rule.relevant_obligations)}")
            for obl in mapping.institutional_rule.relevant_obligations:
                print(f"  - {obl}")

            print(f"\n=== OPERATIONS RULE (How?) ===")
            print(f"Situational Context: {len(mapping.operations_rule.situational_context)}")
            for ctx in mapping.operations_rule.situational_context:
                print(f"  - {ctx}")

            print(f"\nKey Events: {len(mapping.operations_rule.key_events)}")
            for event in mapping.operations_rule.key_events:
                print(f"  - {event}")

            print(f"\n=== STEERING RULE (Transformation?) ===")
            print(f"Transformation Points: {len(mapping.steering_rule.transformation_points)}")
            for point in mapping.steering_rule.transformation_points:
                print(f"  - {point}")

            print(f"\nRule Shifts: {len(mapping.steering_rule.rule_shifts)}")
            for shift in mapping.steering_rule.rule_shifts:
                print(f"  - {shift}")

            print(f"\n=== OVERALL ANALYSIS ===")
            print(mapping.overall_analysis)

            # Test database save
            print("\n[Test] Saving to database...")
            saved = mapper.save_to_database(case_id, mapping)
            if saved:
                print("[Test] ✓ Successfully saved to database!")
            else:
                print("[Test] ✗ Failed to save to database")

            # Verify saved data
            from sqlalchemy import text
            from app.models import db
            result = db.session.execute(
                text("SELECT actions_taken, transformation_points FROM case_action_mapping WHERE case_id = :case_id"),
                {'case_id': case_id}
            ).fetchone()

            if result:
                print(f"\n[Test] ✓ Verified: Found saved mapping in database")
                print(f"  - Actions taken (DB): {len(eval(result[0]))} items")
                print(f"  - Transformation points (DB): {len(eval(result[1]))} items")
            else:
                print("[Test] ✗ Could not verify saved data")

            return True

        except Exception as e:
            print(f"\n[Test] ✗ Error during analysis: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    print("=" * 80)
    print("TESTING STEP 4 PART E: ACTION-RULE MAPPER")
    print("=" * 80)

    success = test_part_e_case_8()

    print("\n" + "=" * 80)
    if success:
        print("TEST PASSED ✓")
    else:
        print("TEST FAILED ✗")
    print("=" * 80)

    sys.exit(0 if success else 1)
