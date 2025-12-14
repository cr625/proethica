#!/usr/bin/env python
"""
Export Case Extraction Fixtures

Exports extraction prompts and responses from a case to JSON fixtures
for use in mock LLM testing.

Usage:
    python scripts/export_case_fixtures.py <case_id>
    python scripts/export_case_fixtures.py 7  # Export Case 7 fixtures
    python scripts/export_case_fixtures.py 7 --output-dir /path/to/fixtures

Output:
    Creates JSON files in tests/mocks/responses/case_<id>/ directory:
    - roles_facts.json
    - roles_discussion.json
    - states_facts.json
    - provisions.json
    - decision_points.json
    - etc.
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.extraction_prompt import ExtractionPrompt


def export_case_fixtures(case_id: int, output_dir: Path = None) -> dict:
    """
    Export all extraction prompts for a case to JSON fixtures.

    Args:
        case_id: The case ID to export
        output_dir: Optional output directory (defaults to tests/mocks/responses/case_<id>/)

    Returns:
        Summary of exported fixtures
    """
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / 'tests' / 'mocks' / 'responses' / f'case_{case_id}'

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Query all prompts for this case
    prompts = ExtractionPrompt.query.filter_by(case_id=case_id).order_by(
        ExtractionPrompt.step_number,
        ExtractionPrompt.concept_type,
        ExtractionPrompt.section_type
    ).all()

    if not prompts:
        print(f"No extraction prompts found for case {case_id}")
        return {'exported': 0, 'files': []}

    exported = []

    for prompt in prompts:
        # Build filename: {concept_type}_{section_type}.json
        # For step4 types without section, just use concept_type.json
        if prompt.section_type in ('facts', 'discussion'):
            filename = f"{prompt.concept_type}_{prompt.section_type}.json"
        else:
            filename = f"{prompt.concept_type}.json"

        filepath = output_dir / filename

        # Parse the raw response if it's JSON
        try:
            response_data = json.loads(prompt.raw_response) if prompt.raw_response else None
        except json.JSONDecodeError:
            response_data = prompt.raw_response

        fixture = {
            'metadata': {
                'case_id': case_id,
                'concept_type': prompt.concept_type,
                'section_type': prompt.section_type,
                'step_number': prompt.step_number,
                'llm_model': prompt.llm_model,
                'created_at': prompt.created_at.isoformat() if prompt.created_at else None,
                'extraction_session_id': prompt.extraction_session_id,
                'results_summary': prompt.results_summary
            },
            'prompt': prompt.prompt_text,
            'response': response_data
        }

        with open(filepath, 'w') as f:
            json.dump(fixture, f, indent=2, ensure_ascii=False)

        exported.append({
            'file': str(filepath),
            'concept_type': prompt.concept_type,
            'section_type': prompt.section_type,
            'step': prompt.step_number
        })

        print(f"  Exported: {filename}")

    # Create index file
    index = {
        'case_id': case_id,
        'exported_at': datetime.utcnow().isoformat(),
        'fixtures': [
            {
                'file': Path(e['file']).name,
                'concept_type': e['concept_type'],
                'section_type': e['section_type'],
                'step': e['step']
            }
            for e in exported
        ]
    }

    with open(output_dir / 'index.json', 'w') as f:
        json.dump(index, f, indent=2)

    print(f"\nCreated index.json with {len(exported)} fixtures")

    return {
        'exported': len(exported),
        'output_dir': str(output_dir),
        'files': exported
    }


def export_flat_fixtures(case_id: int) -> dict:
    """
    Export fixtures in flat format compatible with MockLLMClient.

    Creates files directly in tests/mocks/responses/ without case subdirectory,
    using the same naming convention as existing fixtures.
    """
    output_dir = Path(__file__).parent.parent / 'tests' / 'mocks' / 'responses'
    output_dir.mkdir(parents=True, exist_ok=True)

    prompts = ExtractionPrompt.query.filter_by(case_id=case_id).order_by(
        ExtractionPrompt.step_number,
        ExtractionPrompt.concept_type,
        ExtractionPrompt.section_type
    ).all()

    if not prompts:
        print(f"No extraction prompts found for case {case_id}")
        return {'exported': 0, 'files': []}

    exported = []

    for prompt in prompts:
        # Parse the raw response - this is what MockLLMClient will return
        try:
            response_data = json.loads(prompt.raw_response) if prompt.raw_response else None
        except json.JSONDecodeError:
            # If not valid JSON, wrap it
            response_data = {'raw': prompt.raw_response}

        if response_data is None:
            print(f"  Skipping {prompt.concept_type}_{prompt.section_type} (no response)")
            continue

        # Build filename
        if prompt.section_type in ('facts', 'discussion'):
            filename = f"{prompt.concept_type}_{prompt.section_type}.json"
        else:
            filename = f"{prompt.concept_type}.json"

        filepath = output_dir / filename

        # Write just the response data (what the LLM returns)
        with open(filepath, 'w') as f:
            json.dump(response_data, f, indent=2, ensure_ascii=False)

        exported.append({
            'file': str(filepath),
            'concept_type': prompt.concept_type,
            'section_type': prompt.section_type
        })

        print(f"  Exported: {filename}")

    return {
        'exported': len(exported),
        'output_dir': str(output_dir),
        'files': exported
    }


def main():
    parser = argparse.ArgumentParser(description='Export case extraction fixtures')
    parser.add_argument('case_id', type=int, help='Case ID to export')
    parser.add_argument('--output-dir', type=str, help='Output directory (optional)')
    parser.add_argument('--flat', action='store_true',
                       help='Export flat files to tests/mocks/responses/ (overwrites existing)')
    parser.add_argument('--with-prompts', action='store_true',
                       help='Include full prompts in fixtures (for detailed case directory)')

    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        print(f"Exporting fixtures for case {args.case_id}...")

        if args.flat:
            result = export_flat_fixtures(args.case_id)
        else:
            output_dir = Path(args.output_dir) if args.output_dir else None
            result = export_case_fixtures(args.case_id, output_dir)

        print(f"\nExported {result['exported']} fixtures to {result['output_dir']}")


if __name__ == '__main__':
    main()
