#!/usr/bin/env python3
"""
Migration script to add URIs to guideline section 'establishes' metadata.

This script:
1. Reads all guideline_sections with establishes data
2. Generates URIs for each concept using the standard pattern
3. Optionally syncs concepts to OntServe concepts table
4. Updates section_metadata with enriched data (type, label, uri)

IRI Pattern:
    http://proethica.org/ontology/{type}s#{Normalized_Label}

Examples:
    - http://proethica.org/ontology/principles#Public_Safety
    - http://proethica.org/ontology/obligations#Duty_of_Care
    - http://proethica.org/ontology/constraints#Conflict_of_Interest_Prohibition

Usage:
    cd /home/chris/onto/proethica
    source venv-proethica/bin/activate
    python scripts/migrate_establishes_uris.py [--dry-run] [--sync-ontserve]
"""

import sys
import os
import json
import argparse
from typing import Dict, List, Any, Optional

# Add proethica to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app import create_app
from app.models import db
from app.models.guideline_section import GuidelineSection


def normalize_label(label: str) -> str:
    """Normalize a label for use in IRI."""
    return label.replace(' ', '_').replace('-', '_').replace("'", "")


def generate_concept_uri(label: str, concept_type: str) -> str:
    """Generate IRI for a concept based on type and label."""
    normalized_label = normalize_label(label)
    # Pluralize type for path (principle -> principles)
    type_path = f"{concept_type.lower()}s"
    return f"http://proethica.org/ontology/{type_path}#{normalized_label}"


def enrich_establishes_data(establishes: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Add URI to each concept in establishes list."""
    enriched = []
    for concept in establishes:
        if isinstance(concept, dict):
            concept_type = concept.get('type', 'concept')
            label = concept.get('label', '')
            uri = generate_concept_uri(label, concept_type)
            enriched.append({
                'type': concept_type,
                'label': label,
                'uri': uri
            })
        elif isinstance(concept, str):
            # Legacy string format - treat as unknown type
            uri = generate_concept_uri(concept, 'concept')
            enriched.append({
                'type': 'concept',
                'label': concept,
                'uri': uri
            })
    return enriched


def sync_to_ontserve(concepts: List[Dict[str, Any]], dry_run: bool = True) -> Dict[str, int]:
    """
    Sync concepts to OntServe concepts table.

    Returns dict with counts: {created: N, existing: N, errors: N}
    """
    import psycopg2

    stats = {'created': 0, 'existing': 0, 'errors': 0}

    if dry_run:
        print(f"[DRY RUN] Would sync {len(concepts)} concepts to OntServe")
        return stats

    try:
        conn = psycopg2.connect(
            host='localhost',
            database='ontserve',
            user='postgres',
            password='PASS'
        )
        cursor = conn.cursor()

        for concept in concepts:
            uri = concept['uri']
            label = concept['label']
            concept_type = concept['type'].title()

            # Check if already exists
            cursor.execute("SELECT id FROM concepts WHERE uri = %s", (uri,))
            if cursor.fetchone():
                stats['existing'] += 1
                continue

            # Insert new concept
            try:
                cursor.execute("""
                    INSERT INTO concepts (uri, label, primary_type, domain_id, status, source_document, created_at)
                    VALUES (%s, %s, %s, 1, 'approved', 'guideline:1', NOW())
                """, (uri, label, concept_type))
                stats['created'] += 1
            except Exception as e:
                print(f"  Error inserting {uri}: {e}")
                stats['errors'] += 1

        conn.commit()
        cursor.close()
        conn.close()

    except Exception as e:
        print(f"OntServe connection error: {e}")
        stats['errors'] += 1

    return stats


def migrate_establishes_uris(dry_run: bool = True, sync_ontserve: bool = False):
    """Main migration function."""

    print("=" * 60)
    print("Migrating guideline section 'establishes' data to include URIs")
    print("=" * 60)

    if dry_run:
        print("[DRY RUN MODE - No changes will be made]")

    # Query sections with establishes data
    sections = GuidelineSection.query.filter(
        GuidelineSection.section_metadata.isnot(None)
    ).all()

    print(f"\nFound {len(sections)} sections with metadata")

    updated_count = 0
    skipped_count = 0
    all_concepts = []

    for section in sections:
        metadata = section.section_metadata or {}
        establishes = metadata.get('establishes', [])

        if not establishes:
            continue

        # Check if already has URIs
        has_uris = all(
            isinstance(c, dict) and c.get('uri')
            for c in establishes
        )

        if has_uris:
            skipped_count += 1
            continue

        # Enrich with URIs
        enriched = enrich_establishes_data(establishes)
        all_concepts.extend(enriched)

        print(f"\n{section.section_code}:")
        for original, enriched_concept in zip(establishes, enriched):
            orig_label = original.get('label', original) if isinstance(original, dict) else original
            print(f"  {orig_label} -> {enriched_concept['uri']}")

        if not dry_run:
            # Update metadata - must use flag_modified for JSONB columns
            metadata['establishes'] = enriched
            section.section_metadata = metadata
            flag_modified(section, 'section_metadata')
            db.session.add(section)

        updated_count += 1

    if not dry_run:
        db.session.commit()

    print(f"\n{'=' * 60}")
    print(f"Summary:")
    print(f"  Updated: {updated_count} sections")
    print(f"  Skipped (already has URIs): {skipped_count} sections")
    print(f"  Total unique concepts: {len(set(c['uri'] for c in all_concepts))}")

    # Optionally sync to OntServe
    if sync_ontserve and all_concepts:
        print(f"\n{'=' * 60}")
        print("Syncing concepts to OntServe...")
        unique_concepts = {c['uri']: c for c in all_concepts}.values()
        stats = sync_to_ontserve(list(unique_concepts), dry_run=dry_run)
        print(f"  Created: {stats['created']}")
        print(f"  Already existed: {stats['existing']}")
        print(f"  Errors: {stats['errors']}")

    return updated_count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migrate establishes data to include URIs')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Show what would be done without making changes (default)')
    parser.add_argument('--execute', action='store_true',
                       help='Actually execute the migration')
    parser.add_argument('--sync-ontserve', action='store_true',
                       help='Also sync concepts to OntServe concepts table')

    args = parser.parse_args()

    dry_run = not args.execute

    app = create_app()
    with app.app_context():
        migrate_establishes_uris(dry_run=dry_run, sync_ontserve=args.sync_ontserve)
