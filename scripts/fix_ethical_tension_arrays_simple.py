#!/usr/bin/env python3
"""
Fix hasEthicalTension and hasActiveObligation arrays that were incorrectly split into characters.

Simple script using direct database connection.
"""

import psycopg2
import json
import sys

def fix_character_split_arrays(dry_run=True):
    """
    Fix arrays that were incorrectly split into individual characters.

    Args:
        dry_run: If True, only show what would be fixed without making changes
    """
    # Connect to database
    conn = psycopg2.connect(
        host="localhost",
        database="ai_ethical_dm",
        user="postgres",
        password="PASS"
    )
    cur = conn.cursor()

    # Find all entities with rdf_json_ld data
    cur.execute("""
        SELECT id, entity_label, rdf_json_ld
        FROM temporary_rdf_storage
        WHERE rdf_json_ld IS NOT NULL
    """)

    fixed_count = 0
    updates = []

    for row in cur.fetchall():
        entity_id, entity_label, json_data = row
        modified = False

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
                    print(f"Entity {entity_label} (ID {entity_id}):")
                    print(f"  BEFORE: {value[:20]}... ({len(value)} items)")
                    print(f"  AFTER:  [{fixed_value}]")

                    props['hasEthicalTension'] = [fixed_value]
                    modified = True

            # Fix hasActiveObligation
            if 'hasActiveObligation' in props:
                value = props['hasActiveObligation']
                if isinstance(value, list) and len(value) > 10 and all(isinstance(x, str) and len(x) <= 1 for x in value):
                    # This looks like character splitting - join them back
                    fixed_value = ''.join(value)
                    print(f"Entity {entity_label} (ID {entity_id}):")
                    print(f"  BEFORE (obligations): {value[:20]}... ({len(value)} items)")
                    print(f"  AFTER:  [{fixed_value}]")

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
                    print(f"Entity {entity_label} (ID {entity_id}) [top-level]:")
                    print(f"  BEFORE: {value[:20]}... ({len(value)} items)")
                    print(f"  AFTER:  [{fixed_value}]")

                    props['hasEthicalTension'] = [fixed_value]
                    modified = True

            # Fix hasActiveObligation
            if 'hasActiveObligation' in props:
                value = props['hasActiveObligation']
                if isinstance(value, list) and len(value) > 10 and all(isinstance(x, str) and len(x) <= 1 for x in value):
                    fixed_value = ''.join(value)
                    print(f"Entity {entity_label} (ID {entity_id}) [top-level]:")
                    print(f"  BEFORE (obligations): {value[:20]}... ({len(value)} items)")
                    print(f"  AFTER:  [{fixed_value}]")

                    props['hasActiveObligation'] = [fixed_value]
                    modified = True

        if modified:
            updates.append((json.dumps(json_data), entity_id))
            fixed_count += 1

    # Apply updates
    if not dry_run and updates:
        cur.executemany("""
            UPDATE temporary_rdf_storage
            SET rdf_json_ld = %s::json
            WHERE id = %s
        """, updates)
        conn.commit()
        print(f"\n✓ Fixed {fixed_count} entities")
    elif dry_run and updates:
        print(f"\n[DRY RUN] Would fix {fixed_count} entities")
        print("Run with --apply to make changes")
    else:
        print("\nNo entities needed fixing")

    cur.close()
    conn.close()

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
