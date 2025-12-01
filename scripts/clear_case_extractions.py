#!/usr/bin/env python
"""
Clear Case Extractions Script

Clears all extraction data for a specific case:
- ExtractionPrompt entries
- TemporaryRDFStorage entities
- PipelineRun records (optional)

Usage:
    python scripts/clear_case_extractions.py <case_id>
    python scripts/clear_case_extractions.py <case_id> --include-runs  # Also clear pipeline runs
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import TemporaryRDFStorage
from app.models.extraction_prompt import ExtractionPrompt


def clear_case_extractions(case_id: int, include_runs: bool = False):
    """Clear all extraction data for a case."""

    # Clear ExtractionPrompts
    prompts = ExtractionPrompt.query.filter_by(case_id=case_id).all()
    prompt_count = len(prompts)
    for p in prompts:
        db.session.delete(p)
    print(f"Deleted {prompt_count} extraction prompts")

    # Clear TemporaryRDFStorage
    rdf_entities = TemporaryRDFStorage.query.filter_by(case_id=case_id).all()
    rdf_count = len(rdf_entities)
    for e in rdf_entities:
        db.session.delete(e)
    print(f"Deleted {rdf_count} RDF entities")

    # Optionally clear PipelineRun records
    if include_runs:
        try:
            from app.models.pipeline_run import PipelineRun
            runs = PipelineRun.query.filter_by(case_id=case_id).all()
            run_count = len(runs)
            for r in runs:
                db.session.delete(r)
            print(f"Deleted {run_count} pipeline runs")
        except Exception as e:
            print(f"Could not clear pipeline runs: {e}")

    db.session.commit()
    print(f"\nCase {case_id} extraction data cleared.")

    return {
        'prompts': prompt_count,
        'rdf_entities': rdf_count
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/clear_case_extractions.py <case_id> [--include-runs]")
        sys.exit(1)

    case_id = int(sys.argv[1])
    include_runs = '--include-runs' in sys.argv

    app = create_app()
    with app.app_context():
        print(f"Clearing extraction data for case {case_id}...")
        clear_case_extractions(case_id, include_runs)


if __name__ == '__main__':
    main()
