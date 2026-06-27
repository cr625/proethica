"""Authoritative seeder for the roles extraction prompt (facts + discussion passes).

SINGLE SOURCE for the roles prompt. Consolidates the former competing seeders:
  - seed_roles_pass_split.py            (the facts/discussion pass split)
  - update_roles_schema_professional_split.py (the professional/participant schema)
  - the legacy 'roles' entry in dual_extractor_template_seeder.py (pass 'all')
  - prompt_template_seeder.py           (old {{ mcp_context }} / {{ text }} scheme)
all of which are archived under docs-internal/scripts/archive/.

The prompt TEXT lives in prompts/roles_facts.md and prompts/roles_discussion.md (the verified DB content,
including the SHACL-resolved {{ role_schema }} variable). The shared METADATA (system prompt, output schema,
documented variables, per-pass name/description) lives in prompts/roles_meta.json. This module only wires
them into ExtractionPromptTemplate rows. See .claude/plans/prompt-harmonization-playbook.md.

Run: python -m app.utils.seed_roles_prompt [--replace]
"""
import json
import logging
import sys
from pathlib import Path

from app import db
from app.models.extraction_prompt_template import ExtractionPromptTemplate

logger = logging.getLogger(__name__)
_DIR = Path(__file__).parent / "prompts"


def seed_roles_prompt(replace_existing: bool = False):
    """Seed the roles facts + discussion templates from the sidecar files. Idempotent: skips existing
    unless replace_existing. Returns (created, updated, skipped)."""
    meta = json.loads((_DIR / "roles_meta.json").read_text())
    created = updated = skipped = 0

    # The roles prompt is pass-split (facts/discussion); deactivate any stale pass-less ('all') row.
    for legacy in ExtractionPromptTemplate.query.filter_by(
            extraction_type='case', concept_type='roles', pass_type='all', is_active=True).all():
        legacy.is_active = False
        logger.info("Deactivated legacy roles 'all' template id %s", legacy.id)

    for pass_type, p in meta["passes"].items():
        template_text = (_DIR / p["template_file"]).read_text()
        existing = ExtractionPromptTemplate.query.filter_by(
            extraction_type='case', concept_type='roles', pass_type=pass_type, is_active=True).first()
        if existing and not replace_existing:
            logger.info("roles/%s already exists, skipping", pass_type)
            skipped += 1
            continue
        t = existing or ExtractionPromptTemplate(
            extraction_type='case', concept_type='roles', pass_type=pass_type,
            is_active=True, created_by='seed_roles_prompt', version=0)
        t.name = p["name"]
        t.description = p["description"]
        t.template_text = template_text
        t.system_prompt = meta["system_prompt"]
        t.output_schema = meta["output_schema"]
        t.variable_builders = meta["variable_builders"]
        t.variables_schema = meta["variable_builders"]
        t.step_number = meta["step_number"]
        t.domain = meta["domain"]
        t.source_file = "app/utils/seed_roles_prompt.py"
        t.version = (t.version or 0) + 1
        if existing:
            updated += 1
            logger.info("Updated roles/%s -> v%s", pass_type, t.version)
        else:
            db.session.add(t)
            created += 1
            logger.info("Created roles/%s", pass_type)

    db.session.commit()
    logger.info("roles prompt seed: %d created, %d updated, %d skipped", created, updated, skipped)
    return created, updated, skipped


if __name__ == '__main__':
    from app import create_app
    with create_app().app_context():
        seed_roles_prompt(replace_existing='--replace' in sys.argv)
