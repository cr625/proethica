#!/usr/bin/env python3
"""
Fix hasEthicalTension and hasActiveObligation arrays that were incorrectly split into characters.

This script fixes a bug where strings were iterated character-by-character instead of being
treated as single values in lists.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.models import TemporaryRDFStorage, db

def fix_character_split_arrays(dry_run=True):
    """
    Fix arrays that were incorrectly split into individual characters.

    Args:
        dry_run: If True, only show what would be fixed without making changes
    """
    app = create_app()

    with app.app_context():
        # Find all entities with rdf_json_ld data
        entities = TemporaryRDFStorage.query.filter(
            TemporaryRDFStorage.rdf_json_ld.isnot(None)
        ).all()

        fixed_count = 0

        for entity in entities:
            modified = False
            json_data = entity.rdf_json_ld

            # Check if entityData exists (for cross-references)
            if 'entityData' in json_data and isinstance(json_data['entityData'], dict):
                entity_data = json_data['entityData']
                props = entity_data.get('properties', {})

                # Fix hasEthicalTension
                if 'hasEthicalTension' in props:
                    value = props['hasEthicalTension']
                    if isinstance(value, list) and len(value) > 5 and all(isinstance(x, str) and len(x) <= 1 for x in value):
                        # This looks like character splitting - join them back
                        fixed_value = ''.join(value)
                        print(f"Entity {entity.entity_label} (ID {entity.id}):")
                        print(f"  BEFORE: {value[:20]}... ({len(value)} items)")
                        print(f"  AFTER:  [{fixed_value}]")

                        if not dry_run:
                            props['hasEthicalTension'] = [fixed_value]
                            modified = True

                # Fix hasActiveObligation
                if 'hasActiveObligation' in props:
                    value = props['hasActiveObligation']
                    if isinstance(value, list) and len(value) > 10 and all(isinstance(x, str) and len(x) <= 1 for x in value):
                        # This looks like character splitting - join them back
                        fixed_value = ''.join(value)
                        print(f"Entity {entity.entity_label} (ID {entity.id}):")
                        print(f"  BEFORE (obligations): {value[:20]}... ({len(value)} items)")
                        print(f"  AFTER:  [{fixed_value}]")

                        if not dry_run:
                            props['hasActiveObligation'] = [fixed_value]
                            modified = True

            # Also check top-level properties
            if 'properties' in json_data:
                props = json_data['properties']

                # Fix hasEthicalTension
                if 'hasEthicalTension' in props:
                    value = props['hasEthicalTension']
                    if isinstance(value, list) and len(value) > 5 and all(isinstance(x, str) and len(x) <= 1 for x in value):
                        fixed_value = ''.join(value)
                        print(f"Entity {entity.entity_label} (ID {entity.id}) [top-level]:")
                        print(f"  BEFORE: {value[:20]}... ({len(value)} items)")
                        print(f"  AFTER:  [{fixed_value}]")

                        if not dry_run:
                            props['hasEthicalTension'] = [fixed_value]
                            modified = True

                # Fix hasActiveObligation
                if 'hasActiveObligation' in props:
                    value = props['hasActiveObligation']
                    if isinstance(value, list) and len(value) > 10 and all(isinstance(x, str) and len(x) <= 1 for x in value):
                        fixed_value = ''.join(value)
                        print(f"Entity {entity.entity_label} (ID {entity.id}) [top-level]:")
                        print(f"  BEFORE (obligations): {value[:20]}... ({len(value)} items)")
                        print(f"  AFTER:  [{fixed_value}]")

                        if not dry_run:
                            props['hasActiveObligation'] = [fixed_value]
                            modified = True

            if modified:
                # Mark the JSON as modified
                entity.rdf_json_ld = json_data
                fixed_count += 1

        if not dry_run and fixed_count > 0:
            db.session.commit()
            print(f"\n✓ Fixed {fixed_count} entities")
        elif dry_run:
            print(f"\n[DRY RUN] Would fix {fixed_count} entities")
            print("Run with --apply to make changes")
        else:
            print("\nNo entities needed fixing")

if __name__ == '__main__':
    dry_run = '--apply' not in sys.argv

    if dry_run:
        print("=" * 60)
        print("DRY RUN - No changes will be made")
        print("=" * 60)
    else:
        print("=" * 60)
        print("APPLYING FIXES")
        print("=" * 60)

    fix_character_split_arrays(dry_run=dry_run)
