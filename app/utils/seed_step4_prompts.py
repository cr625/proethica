"""Seed the Step-4 synthesis prompt templates from their sidecar files.

Sidecars live at app/utils/prompts/step4/<concept_type>.md: a JSON meta
block between a leading pair of '---' fence lines, then the Jinja2 body.
Meta keys: name, description, phase, extractor_file, prompt_method,
output_schema, variable_builders (doubles as variables_schema; every
variable the body references must be declared here -- enforced below,
because an unbound Jinja variable renders as '' silently at run time).

Rows: extraction_type='case', step_number=4, pass_type='all',
domain='engineering'. Create if absent; --replace updates the existing
active row in place and bumps its version (matching the concept-seeder
semantics); existing rows are otherwise skipped. --only restricts to the
named concept_types.

Run: python -m app.utils.seed_step4_prompts [--replace] [--only name ...]
"""

import argparse
import json
import sys
from pathlib import Path

from jinja2 import Environment, meta as jinja_meta

REPO = Path(__file__).resolve().parents[2]
SIDECAR_DIR = REPO / 'app' / 'utils' / 'prompts' / 'step4'

STEP_NUMBER = 4


def parse_sidecar(path: Path):
    text = path.read_text()
    if not text.startswith('---\n'):
        raise ValueError(f'{path.name}: missing leading --- meta fence')
    parts = text.split('---\n', 2)
    if len(parts) < 3:
        raise ValueError(f'{path.name}: missing closing --- meta fence')
    meta = json.loads(parts[1])
    body = parts[2].lstrip('\n')
    for key in ('name', 'description', 'variable_builders'):
        if key not in meta:
            raise ValueError(f'{path.name}: meta lacks required key {key!r}')
    return meta, body


def check_variables(path: Path, meta: dict, body: str):
    env = Environment()
    undeclared = jinja_meta.find_undeclared_variables(env.parse(body))
    declared = set(meta['variable_builders'].keys())
    missing = sorted(undeclared - declared)
    if missing:
        raise RuntimeError(
            f'{path.name}: body references variables not declared in '
            f'variable_builders: {missing} (they would render as empty strings)'
        )
    unused = sorted(declared - undeclared)
    if unused:
        print(f'  NOTE {path.name}: declared but unreferenced variables: {unused}')


def seed_one(path: Path, replace: bool) -> str:
    from app.models import db
    from app.models.extraction_prompt_template import ExtractionPromptTemplate

    concept_type = path.stem
    meta, body = parse_sidecar(path)
    check_variables(path, meta, body)

    row = ExtractionPromptTemplate.query.filter_by(
        extraction_type='case', step_number=STEP_NUMBER,
        concept_type=concept_type, is_active=True,
    ).first()

    fields = dict(
        name=meta['name'],
        description=meta['description'],
        template_text=body,
        system_prompt=meta.get('system_prompt'),
        variables_schema=meta['variable_builders'],
        variable_builders=meta['variable_builders'],
        output_schema=meta.get('output_schema'),
        extractor_file=meta.get('extractor_file'),
        prompt_method=meta.get('prompt_method'),
        source_file=str(path.relative_to(REPO)),
        domain=meta.get('domain', 'engineering'),
    )

    if row is None:
        row = ExtractionPromptTemplate(
            extraction_type='case', step_number=STEP_NUMBER,
            concept_type=concept_type, pass_type='all',
            version=1, is_active=True, created_by='seed_step4_prompts',
            **fields,
        )
        db.session.add(row)
        db.session.commit()
        return 'created'
    if not replace:
        return 'skipped (exists; use --replace)'
    for key, value in fields.items():
        setattr(row, key, value)
    row.version += 1
    db.session.commit()
    return f'replaced (v{row.version})'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--replace', action='store_true')
    parser.add_argument('--only', nargs='+', metavar='CONCEPT_TYPE')
    args = parser.parse_args()

    sidecars = sorted(SIDECAR_DIR.glob('*.md'))
    if args.only:
        wanted = set(args.only)
        sidecars = [p for p in sidecars if p.stem in wanted]
        missing = wanted - {p.stem for p in sidecars}
        if missing:
            print(f'ERROR: no sidecar for: {sorted(missing)}')
            return 1
    if not sidecars:
        print(f'ERROR: no sidecars found under {SIDECAR_DIR}')
        return 1

    sys.path.insert(0, str(REPO))
    from app import create_app
    app = create_app('development')
    failures = 0
    with app.app_context():
        for path in sidecars:
            try:
                outcome = seed_one(path, args.replace)
                print(f'{path.stem}: {outcome}')
            except Exception as exc:
                failures += 1
                print(f'{path.stem}: FAILED: {exc}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
