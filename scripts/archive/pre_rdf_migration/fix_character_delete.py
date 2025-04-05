from app import create_app, db
from app.models.character import Character
from app.models.event import Action, Event

print("Starting fix_character_delete.py script")

try:
    app = create_app()
    print("App created successfully")

    with app.app_context():
        print("Entered app context")
        
        # Update the delete_character route to handle actions
        from flask import Blueprint, flash, redirect, url_for
        from app.routes.scenarios import scenarios_bp
        
        print(f"Loaded scenarios_bp with routes: {list(scenarios_bp.view_functions.keys())}")
        
        # Save the original function for reference
        if 'delete_character' in scenarios_bp.view_functions:
            original_delete_character = scenarios_bp.view_functions['delete_character']
            print("Found original delete_character function")
        else:
            print("WARNING: delete_character function not found in scenarios_bp.view_functions")
            print(f"Available routes: {list(scenarios_bp.view_functions.keys())}")
        
        # Define the new function
        def delete_character_with_actions(id, character_id):
            """Delete a character and its associated actions."""
            from app.models.scenario import Scenario
            
            print(f"Deleting character {character_id} from scenario {id}")
            
            scenario = Scenario.query.get_or_404(id)
            character = Character.query.get_or_404(character_id)
            
            # Ensure the character belongs to the scenario
            if character.scenario_id != scenario.id:
                flash('Character does not belong to this scenario', 'danger')
                return redirect(url_for('scenarios.view_scenario', id=scenario.id))
            
            # First, find all actions associated with this character
            actions = Action.query.filter_by(character_id=character_id).all()
            print(f"Found {len(actions)} actions associated with this character")
            
            # For each action, delete associated events
            for action in actions:
                events = Event.query.filter_by(action_id=action.id).all()
                print(f"Deleting {len(events)} events for action {action.id}")
                for event in events:
                    db.session.delete(event)
                
                # Then delete the action
                print(f"Deleting action {action.id}")
                db.session.delete(action)
            
            # Now delete the character (conditions will be deleted automatically due to cascade)
            print(f"Deleting character {character.id}")
            db.session.delete(character)
            db.session.commit()
            
            flash('Character and associated actions deleted successfully', 'success')
            return redirect(url_for('scenarios.view_scenario', id=scenario.id))
        
        # Replace the route function
        if 'delete_character' in scenarios_bp.view_functions:
            scenarios_bp.view_functions['delete_character'] = delete_character_with_actions
            print("Character deletion route updated to handle associated actions")
        else:
            print("WARNING: Could not update delete_character route - route not found")
except Exception as e:
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()
