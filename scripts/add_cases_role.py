#!/usr/bin/env python3
"""
One-off helper to add a role to the per-world cases ontology and mirror it into DB Roles.
Usage: Run within the project venv. Adjust SCENARIO_ID, ROLE_LABEL, and DESCRIPTION as needed.
"""
import os
import sys

from app import create_app, db
from app.models.scenario import Scenario
from app.models.world import World
from app.services.cases_ontology_service import CasesOntologyService

SCENARIO_ID = int(os.environ.get("SCENARIO_ID", "17"))
ROLE_LABEL = os.environ.get("ROLE_LABEL", "Professional Engineer")
DESCRIPTION = os.environ.get(
    "ROLE_DESCRIPTION",
    "Licensed engineer responsible for safeguarding public welfare, adhering to ethical codes, and ensuring compliance with standards."
)

def main():
    app = create_app('config')
    with app.app_context():
        scenario = Scenario.query.get(SCENARIO_ID)
        if not scenario:
            print(f"ERROR: Scenario {SCENARIO_ID} not found", file=sys.stderr)
            sys.exit(1)
        world = World.query.get(scenario.world_id)
        if not world:
            print(f"ERROR: World {scenario.world_id} not found", file=sys.stderr)
            sys.exit(1)

        svc = CasesOntologyService()
        ontology = svc.get_or_create_world_cases_ontology(world)
        print(f"Cases ontology ensured: id={ontology.id}, domain_id={ontology.domain_id}, base_uri={ontology.base_uri}")
        uri, role_row = svc.add_role_to_cases_ontology(world, ROLE_LABEL, DESCRIPTION)
        print(f"Added role: id={role_row.id}, name='{role_row.name}', ontology_uri={uri}, world_id={role_row.world_id}")

if __name__ == "__main__":
    main()
