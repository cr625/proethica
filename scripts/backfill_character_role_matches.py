#!/usr/bin/env python3
"""
Backfill matched_ontology_role_id and matching_* fields for characters
based on their assigned database Role's ontology_uri.

Usage:
  SCENARIO_ID=17 python3 scripts/backfill_character_role_matches.py
  WORLD_ID=1 python3 scripts/backfill_character_role_matches.py
If neither is set, processes all characters.
"""
import os
from typing import Optional

from app import create_app, db
from app.models.character import Character
from app.models.scenario import Scenario
from app.models.role import Role
from app.models.world import World


def backfill_for_scenario(scenario_id: int) -> int:
    scenario = Scenario.query.get(scenario_id)
    if not scenario:
        print(f"Scenario {scenario_id} not found")
        return 0
    chars = Character.query.filter_by(scenario_id=scenario_id).all()
    return _backfill(chars, scenario.world_id)


def backfill_for_world(world_id: int) -> int:
    chars = Character.query.join(Scenario, Scenario.id == Character.scenario_id) \
        .filter(Scenario.world_id == world_id).all()
    return _backfill(chars, world_id)


def backfill_all() -> int:
    chars = Character.query.all()
    # world_id not known globally here; pass None and let per-character world lookup occur
    return _backfill(chars, None)


def _backfill(characters, default_world_id: Optional[int]) -> int:
    updated = 0
    for ch in characters:
        if ch.matched_ontology_role_id:
            continue  # already set, skip

        # Determine world_id via scenario if needed
        world_id = default_world_id
        if world_id is None and ch.scenario_id:
            sc = Scenario.query.get(ch.scenario_id)
            world_id = sc.world_id if sc else None

        ontology_uri = None
        if ch.role_id:
            role = Role.query.get(ch.role_id)
            if role and role.ontology_uri:
                ontology_uri = role.ontology_uri
        # Optional: fallback by role name lookup within world
        if not ontology_uri and ch.role and world_id:
            role = Role.query.filter_by(world_id=world_id, name=ch.role).first()
            if role and role.ontology_uri:
                ontology_uri = role.ontology_uri
        if not ontology_uri:
            continue

        # Backfill fields
        ch.matched_ontology_role_id = ontology_uri
        ch.matching_confidence = 1.0  # DB mapping is authoritative
        ch.matching_method = ch.matching_method or 'db_role_linked'
        ch.matching_reasoning = (ch.matching_reasoning or '') + \
            ("\n" if ch.matching_reasoning else "") + \
            f"Backfilled from DB role mapping to ontology URI: {ontology_uri}"
        updated += 1
    if updated:
        db.session.commit()
    return updated


def main():
    app = create_app('config')
    with app.app_context():
        scenario_id = os.environ.get('SCENARIO_ID')
        world_id = os.environ.get('WORLD_ID')
        total = 0
        if scenario_id:
            total = backfill_for_scenario(int(scenario_id))
        elif world_id:
            total = backfill_for_world(int(world_id))
        else:
            total = backfill_all()
        print(f"Backfilled {total} characters")


if __name__ == '__main__':
    main()
