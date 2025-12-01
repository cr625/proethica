#!/usr/bin/env python
"""
Backfill section_type in provenance_metadata for RDF entities.

Uses the section_type from linked ExtractionPrompt records.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import TemporaryRDFStorage
from app.models.extraction_prompt import ExtractionPrompt


def backfill_section_type():
    """Backfill section_type from prompts to RDF entities."""
    # Get all extraction prompts with their session IDs and section_types
    prompts = ExtractionPrompt.query.filter(
        ExtractionPrompt.extraction_session_id.isnot(None)
    ).all()

    print(f"Found {len(prompts)} prompts with session IDs")

    # Build mapping from session_id to section_type
    session_to_section = {}
    for p in prompts:
        if p.extraction_session_id and p.section_type:
            session_to_section[p.extraction_session_id] = p.section_type

    print(f"Built mapping for {len(session_to_section)} session IDs")

    # Update RDF entities with section_type
    updated = 0
    rdf_entities = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.extraction_session_id.isnot(None)
    ).all()

    for entity in rdf_entities:
        section_type = session_to_section.get(entity.extraction_session_id)
        if section_type:
            # Update provenance_metadata
            prov = entity.provenance_metadata or {}
            if prov.get('section_type') != section_type:
                prov['section_type'] = section_type
                entity.provenance_metadata = prov
                updated += 1

    db.session.commit()
    print(f"Updated {updated} RDF entities with section_type")

    return updated


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        backfill_section_type()
