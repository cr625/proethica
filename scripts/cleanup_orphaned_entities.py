#!/usr/bin/env python
"""
Cleanup Legacy Data Script

Detects and removes:
1. RDF entities that have no matching extraction_prompts (orphaned entities)
2. Old temporary_concepts entries (legacy format before RDF migration)

Usage:
    python scripts/cleanup_orphaned_entities.py          # Dry run - just show what would be deleted
    python scripts/cleanup_orphaned_entities.py --delete # Actually delete legacy data
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, TemporaryRDFStorage, TemporaryConcept
from app.models.extraction_prompt import ExtractionPrompt


def find_orphaned_rdf_entities():
    """Find all RDF entities that have no matching extraction_prompts."""
    all_prompts = ExtractionPrompt.query.all()
    session_ids_with_prompts = {p.extraction_session_id for p in all_prompts if p.extraction_session_id}

    if session_ids_with_prompts:
        orphaned = TemporaryRDFStorage.query.filter(
            ~TemporaryRDFStorage.extraction_session_id.in_(session_ids_with_prompts)
        ).all()
    else:
        orphaned = TemporaryRDFStorage.query.all()

    return orphaned


def find_legacy_concepts():
    """Find all entries in the old temporary_concepts table."""
    return TemporaryConcept.query.all()


def summarize_rdf(entities):
    """Summarize orphaned RDF entities by case and type."""
    summary = {}
    for e in entities:
        key = (e.case_id, e.extraction_type)
        if key not in summary:
            summary[key] = 0
        summary[key] += 1
    return summary


def summarize_concepts(concepts):
    """Summarize legacy concepts by document."""
    summary = {}
    for c in concepts:
        if c.document_id not in summary:
            summary[c.document_id] = 0
        summary[c.document_id] += 1
    return summary


def main():
    delete_mode = '--delete' in sys.argv

    app = create_app()
    with app.app_context():
        # Check for orphaned RDF entities
        print("Scanning for orphaned RDF entities...")
        orphaned_rdf = find_orphaned_rdf_entities()
        rdf_summary = summarize_rdf(orphaned_rdf)

        # Check for legacy concepts
        print("Scanning for legacy temporary_concepts...")
        legacy_concepts = find_legacy_concepts()
        concept_summary = summarize_concepts(legacy_concepts)

        total_issues = len(orphaned_rdf) + len(legacy_concepts)

        if total_issues == 0:
            print("\nNo legacy data found. Database is clean.")
            return

        print(f"\n{'='*50}")
        print("LEGACY DATA DETECTED")
        print('='*50)

        if orphaned_rdf:
            print(f"\nOrphaned RDF entities ({len(orphaned_rdf)} total):")
            print("-" * 40)
            for (case_id, extraction_type), count in sorted(rdf_summary.items()):
                print(f"  Case {case_id}: {extraction_type} - {count} entities")

        if legacy_concepts:
            print(f"\nLegacy temporary_concepts ({len(legacy_concepts)} total):")
            print("-" * 40)
            for doc_id, count in sorted(concept_summary.items()):
                print(f"  Document {doc_id}: {count} concepts")

        print('='*50)

        if delete_mode:
            print(f"\nDeleting {total_issues} legacy entries...")

            if orphaned_rdf:
                for e in orphaned_rdf:
                    db.session.delete(e)
                print(f"  - Deleted {len(orphaned_rdf)} orphaned RDF entities")

            if legacy_concepts:
                for c in legacy_concepts:
                    db.session.delete(c)
                print(f"  - Deleted {len(legacy_concepts)} legacy concepts")

            db.session.commit()
            print("\nDone. Legacy data has been removed.")
        else:
            print(f"\nTo delete this legacy data, run:")
            print(f"  python scripts/cleanup_orphaned_entities.py --delete")


if __name__ == '__main__':
    main()
