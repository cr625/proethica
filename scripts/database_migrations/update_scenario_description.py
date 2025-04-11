#!/usr/bin/env python3
"""
Script to update the description of a specific scenario.
"""

import sys
import os

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import Scenario

def update_scenario_description(scenario_id, new_description):
    """Update the description of a specific scenario."""
    app = create_app()
    with app.app_context():
        scenario = Scenario.query.get(scenario_id)
        if scenario:
            old_description = scenario.description
            scenario.description = new_description
            from app import db
            db.session.commit()
            print(f"Updated scenario {scenario_id}: {scenario.name}")
            print(f"Old description: {old_description}")
            print(f"New description: {new_description}")
        else:
            print(f"Scenario {scenario_id} not found")

if __name__ == "__main__":
    # Our new description
    new_description = """An engineer is hired to evaluate the structural integrity of an aging, occupied building that the client intends to sell. The contract specifies that the engineer's report must remain confidential. The client explicitly states that the building will be sold "as is" with no plans to repair or renovate any systems prior to sale.

Upon conducting structural tests, the engineer determines the building is structurally sound. However, during the assessment, the client reveals that the building has deficiencies in its electrical and mechanical systems that violate applicable codes and standards. Although not specialized in these areas, the engineer recognizes these deficiencies could potentially harm the building's occupants and informs the client of this concern.

In the final report to the client, the engineer briefly mentions the conversation about these deficiencies but, adhering to the confidentiality agreement, does not report the safety violations to any regulatory authorities or third parties.

This scenario creates an ethical dilemma regarding whether the engineer's duty to maintain client confidentiality outweighs the professional obligation to protect public safety when potentially dangerous conditions are discovered."""
    
    # Update scenario 1
    update_scenario_description(1, new_description)
