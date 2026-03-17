"""
Batch rewrite scenario opening_context fields for quality.

Fixes:
  1. Wrong protagonist (must match primary branch decision-maker)
  2. Em dashes (removed/reworded)
  3. Prejudging choices or revealing outcomes
  4. Missing concrete facts from source case
  5. Editorializing or flowery language

Usage:
    python scripts/rewrite_opening_contexts.py --dry-run          # Preview changes
    python scripts/rewrite_opening_contexts.py                    # Apply all
    python scripts/rewrite_opening_contexts.py --case-ids 9 10    # Specific cases
    python scripts/rewrite_opening_contexts.py --skip-ids 4 5 6 7 8  # Skip already done
"""
import argparse
import json
import logging
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, ExtractionPrompt, Document
from app.utils.llm_utils import get_llm_client
from model_config import ModelConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def get_case_facts(case_id: int) -> str:
    """Load the Facts section from document_sections."""
    from sqlalchemy import text
    result = db.session.execute(
        text("SELECT content FROM document_sections WHERE document_id = :cid AND section_type = 'facts'"),
        {'cid': case_id}
    ).fetchone()
    if result:
        return result[0][:2000]
    # Fallback to document content
    doc = db.session.get(Document, case_id)
    if doc and doc.content:
        return doc.content[:2000]
    return ""


def build_rewrite_prompt(case_id: int, case_title: str, facts: str,
                          current_context: str, branches: list,
                          resolution: dict) -> str:
    """Build the LLM prompt for rewriting an opening_context."""

    # Identify primary decision-maker from branches
    maker_counts = {}
    for b in branches:
        maker = b.get('decision_maker_label', '')
        if maker:
            maker_counts[maker] = maker_counts.get(maker, 0) + 1
    makers_summary = ", ".join(f"{m} ({c}x)" for m, c in
                               sorted(maker_counts.items(), key=lambda x: -x[1]))

    # Branch questions summary
    branch_lines = []
    for i, b in enumerate(branches):
        maker = b.get('decision_maker_label', '')
        q = b.get('question', '')[:200]
        branch_lines.append(f"  {i+1}. [{maker}] {q}")
    branches_text = "\n".join(branch_lines)

    # Resolution
    res_type = resolution.get('resolution_type', '')
    res_summary = resolution.get('summary', '')[:300]

    return f"""Rewrite the opening_context for a professional engineering ethics scenario.

## Case
Title: {case_title}
Case ID: {case_id}

## Source Facts
{facts[:1500]}

## Current Opening Context (to be rewritten)
{current_context}

## Decision-Makers in Branches
{makers_summary}

## Branch Questions (what the user will decide)
{branches_text}

## Resolution
Type: {res_type}
Summary: {res_summary}

## Rewrite Rules (strict)
1. PROTAGONIST: The "You are..." must match the primary decision-maker from the branches above. If multiple decision-makers appear, use the most frequent one.
2. NO EM DASHES: Do not use the em dash character. Rewrite sentences to avoid needing one. Use commas, periods, or restructure.
3. NO PREJUDGING: Do not narrate what the protagonist did or chose. Set up the situation BEFORE the decisions. The user will make those choices.
4. CONCRETE FACTS: Include the specific parties, projects, technical details, and circumstances from the source facts. Do not be abstract or vague.
5. NO EDITORIALIZING: No flattery ("seasoned professional"), no dramatic framing ("now sits at the center of"), no rhetorical questions. State facts plainly.
6. NO REVEALING OUTCOMES: Do not mention the board's conclusions, the resolution, or what happened as a result of decisions. The user discovers those through play.
7. LENGTH: 3-6 sentences. Aim for 500-800 characters.
8. FINAL SENTENCE: End with a forward-looking sentence about the decisions ahead, without naming specific choices.

## Output
Return ONLY the rewritten opening_context text, no commentary or formatting."""


def rewrite_case(client, case_id: int, data: dict, dry_run: bool) -> tuple:
    """Rewrite one case's opening_context. Returns (changed: bool, new_text: str)."""
    seeds = data.get('scenario_seeds', {})
    current = seeds.get('opening_context', '')
    branches = seeds.get('branches', [])
    ne = data.get('narrative_elements', {})
    resolution = ne.get('resolution', {})

    case = db.session.get(Document, case_id)
    title = case.title if case else f"Case {case_id}"
    facts = get_case_facts(case_id)

    prompt = build_rewrite_prompt(
        case_id=case_id,
        case_title=title,
        facts=facts,
        current_context=current,
        branches=branches,
        resolution=resolution,
    )

    try:
        response = client.messages.create(
            model=ModelConfig.get_claude_model("default"),
            max_tokens=1000,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        new_context = response.content[0].text.strip()

        # Strip any markdown quotes the LLM might wrap it in
        if new_context.startswith('"') and new_context.endswith('"'):
            new_context = new_context[1:-1]
        if new_context.startswith('> '):
            new_context = new_context[2:]

        # Validate: no em dashes
        if '\u2014' in new_context:
            new_context = new_context.replace('\u2014', ', ')
            logger.warning(f"  Case {case_id}: LLM still produced em dashes, replaced with commas")

        return True, new_context

    except Exception as e:
        logger.error(f"  Case {case_id}: LLM call failed: {e}")
        return False, current


def main():
    parser = argparse.ArgumentParser(description='Batch rewrite opening contexts')
    parser.add_argument('--case-ids', nargs='+', type=int, help='Specific case IDs')
    parser.add_argument('--skip-ids', nargs='+', type=int, default=[],
                        help='Case IDs to skip (already done)')
    parser.add_argument('--dry-run', action='store_true', help='Preview without saving')
    parser.add_argument('--limit', type=int, default=0, help='Max cases to process')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        # Load all phase4_narrative prompts, deduplicate
        query = ExtractionPrompt.query.filter_by(concept_type='phase4_narrative')
        if args.case_ids:
            query = query.filter(ExtractionPrompt.case_id.in_(args.case_ids))

        prompts = query.order_by(ExtractionPrompt.case_id).all()
        seen = {}
        for p in prompts:
            if p.case_id not in seen or p.created_at > seen[p.case_id].created_at:
                seen[p.case_id] = p

        skip = set(args.skip_ids)
        case_ids = [cid for cid in sorted(seen.keys()) if cid not in skip]
        if args.limit:
            case_ids = case_ids[:args.limit]

        logger.info(f"Processing {len(case_ids)} cases (skipping {len(skip)})")

        client = get_llm_client()
        updated = 0
        failed = 0

        for case_id in case_ids:
            p = seen[case_id]
            data = json.loads(p.raw_response)
            seeds = data.get('scenario_seeds', {})
            old_context = seeds.get('opening_context', '')

            logger.info(f"Case {case_id}: rewriting ({len(old_context)} chars)...")

            changed, new_context = rewrite_case(client, case_id, data, args.dry_run)

            if not changed:
                failed += 1
                continue

            if args.dry_run:
                has_em = '\u2014' in old_context
                logger.info(f"  [DRY RUN] Would update ({len(old_context)} -> {len(new_context)} chars)"
                           f"{' [had em dashes]' if has_em else ''}")
                logger.info(f"  OLD: {old_context[:120]}...")
                logger.info(f"  NEW: {new_context[:120]}...")
            else:
                data['scenario_seeds']['opening_context'] = new_context
                p.raw_response = json.dumps(data)
                db.session.commit()
                logger.info(f"  Saved ({len(old_context)} -> {len(new_context)} chars)")

            updated += 1

        logger.info(f"Done: {updated} updated, {failed} failed, {len(skip)} skipped")


if __name__ == '__main__':
    main()
