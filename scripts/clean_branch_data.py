"""
Clean branch question em dashes and verbose decision-maker labels.

Fixes:
  1. Em dashes in branch questions and contexts -> comma or period
  2. Overly verbose decision_maker_label -> short role label

Usage:
    python scripts/clean_branch_data.py --dry-run     # Preview
    python scripts/clean_branch_data.py               # Apply all
    python scripts/clean_branch_data.py --case-ids 7  # Specific cases
"""
import argparse
import json
import logging
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, ExtractionPrompt

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def clean_em_dashes(text: str) -> str:
    """Replace em dashes with contextually appropriate alternatives."""
    if not text or '\u2014' not in text:
        return text

    # " — " (spaced em dash, parenthetical) -> ", "
    text = re.sub(r'\s*\u2014\s*', ', ', text)

    # Clean up resulting ", ," or ", and," patterns
    text = re.sub(r',\s*,', ',', text)
    # Clean up ", ?" at end of questions
    text = re.sub(r',\s*\?', '?', text)
    # Clean up leading comma after opening
    text = re.sub(r'^,\s*', '', text)

    return text


def shorten_label(label: str) -> str:
    """Shorten a verbose decision_maker_label to a concise role label.

    Strategy:
      1. If it starts with a known name pattern (Engineer X, Firm X, Dr. X),
         extract that core and optionally keep a short role descriptor.
      2. If it has an em dash, take only the part before it.
      3. If it's a generic role (Client, Public, Owner, Employer), keep as-is.
      4. Otherwise, truncate intelligently.
    """
    if not label:
        return label

    original = label

    # Remove em dashes first -- take the part before
    if '\u2014' in label:
        label = label.split('\u2014')[0].strip()
        # If what remains is empty or too short, try after the dash
        if len(label) < 3:
            label = original.split('\u2014')[-1].strip()

    # Already short enough
    if len(label) <= 40:
        return label

    # Pattern: starts with a generic role word followed by jargon -- keep just the role
    generic_roles = ['Client', 'Public', 'Employer', 'Owner', 'Contractor']
    for role in generic_roles:
        if label.startswith(role + ' ') and len(label) > len(role) + 1:
            return role

    # Pattern: "Engineer[s] X [and Engineer Y] [long description]"
    m = re.match(
        r'^(Engineers?\s+[A-Z](?:\s+and\s+Engineers?\s+[A-Z])?)'
        r'(?:\s+.*)?$',
        label
    )
    if m:
        core = m.group(1)
        remainder = label[len(core):].strip()
        # Only keep remainder as a role if it looks like a genuine job title.
        # Genuine roles: "Mentor Engineer", "Senior Engineering Supervisor",
        #   "State DOT Traffic Engineer", "Building Inspection Director"
        # NOT roles: "Public Interest Environmental Testimony", "Inspection Report Sign-Off",
        #   "Construction Observation Engineer" (too generic), case-specific details
        # Heuristic: remainder must contain a role keyword to be kept.
        role_keywords = {
            'Engineer', 'Director', 'Supervisor', 'Manager', 'Inspector',
            'Consultant', 'Principal', 'Superintendent', 'Commissioner',
            'Officer', 'Mentor', 'Partner', 'Architect',
        }
        remainder_words = remainder.split()
        has_role_keyword = any(w in role_keywords for w in remainder_words[:4])
        if has_role_keyword:
            # Take words up to and including the role keyword
            kept = []
            for w in remainder_words:
                kept.append(w)
                if w in role_keywords:
                    break
            role_str = ' '.join(kept)
            if len(role_str) <= 35:
                return f"{core}, {role_str}"
        return core

    # Pattern: "Dr. Lastname ..."
    m = re.match(r'^(Dr\.\s+\w+(?:\s+\w+)?)\s+', label)
    if m:
        return m.group(1)

    # Pattern: "Person Name, P.E. ..."
    m = re.match(r'^(\w+\s+\w+,?\s*P\.?E\.?)\s*', label)
    if m and len(m.group(1)) <= 30:
        return m.group(1).rstrip(',').strip()

    # Pattern: "Firm X ..."
    m = re.match(r'^(Firm\s+[A-Z]+)\s+', label)
    if m:
        return m.group(1)

    # Pattern: "Licensed Professional Engineer ..."
    if label.startswith('Licensed Professional Engineer'):
        return 'Licensed Professional Engineer'

    # Pattern: "Former Government Forensic Consultant ..."
    m = re.match(r'^((?:Former\s+)?(?:Government|Municipal|Federal|State)\s+\w+(?:\s+\w+)?)', label)
    if m and len(m.group(1)) <= 40:
        return m.group(1)

    # Pattern: known person names that aren't "Engineer X" (e.g., "Wasser", "Marcus Chen")
    # Try single-word name first, then two-word name
    noise_after_name = {
        'Task', 'Obligation', 'Assessment', 'Compliance', 'Prohibition',
        'Verification', 'Certification', 'Sufficiency', 'Determination',
        'Requirement', 'Question', 'Analysis', 'Inclusion', 'Initiation',
        'Proportionality', 'Completeness', 'Receiving', 'Deciding',
    }
    # Single-word name: "Wasser Task Refusal..."
    m1 = re.match(r'^([A-Z][a-z]+)\s+(\w+)', label)
    if m1 and m1.group(2) in noise_after_name:
        return m1.group(1)
    # Two-word name: "Marcus Chen Proportionality..."
    m2 = re.match(r'^([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(\w+)', label)
    if m2 and m2.group(2) in noise_after_name:
        return m2.group(1)

    # Pattern: abstract concept labels (no person name at all) -- these shouldn't
    # be decision-maker labels but they exist. Keep first 3-4 meaningful words.
    words = label.split()
    if len(words) > 5:
        noise = {
            'Obligation', 'Assessment', 'Compliance', 'Prohibition',
            'Verification', 'Certification', 'Sufficiency', 'Determination',
            'Requirement', 'Question', 'Analysis', 'Inclusion', 'Initiation',
        }
        kept = []
        for w in words:
            if w in noise:
                break
            kept.append(w)
            if len(' '.join(kept)) > 40:
                break
        if kept:
            result = ' '.join(kept)
            if len(result) > 45:
                result = result[:42] + '...'
            return result

    # Fallback: truncate
    if len(label) > 45:
        return label[:42] + '...'

    return label


def process_case(case_id: int, data: dict, dry_run: bool) -> dict:
    """Clean branch data for one case. Returns stats dict."""
    seeds = data.get('scenario_seeds', {})
    branches = seeds.get('branches', [])

    stats = {
        'em_dash_questions': 0,
        'em_dash_contexts': 0,
        'labels_shortened': 0,
        'em_dash_options': 0,
    }

    for b in branches:
        # Clean em dashes in question
        q = b.get('question', '')
        cleaned_q = clean_em_dashes(q)
        if cleaned_q != q:
            stats['em_dash_questions'] += 1
            b['question'] = cleaned_q

        # Clean em dashes in context
        ctx = b.get('context', '')
        cleaned_ctx = clean_em_dashes(ctx)
        if cleaned_ctx != ctx:
            stats['em_dash_contexts'] += 1
            b['context'] = cleaned_ctx

        # Shorten verbose label
        lbl = b.get('decision_maker_label', '')
        short = shorten_label(lbl)
        if short != lbl:
            stats['labels_shortened'] += 1
            b['decision_maker_label'] = short

        # Clean em dashes in option labels
        for opt in b.get('options', []):
            ol = opt.get('label', '')
            cleaned_ol = clean_em_dashes(ol)
            if cleaned_ol != ol:
                stats['em_dash_options'] += 1
                opt['label'] = cleaned_ol

            od = opt.get('description', '')
            cleaned_od = clean_em_dashes(od)
            if cleaned_od != od:
                opt['description'] = cleaned_od

    return stats


def main():
    parser = argparse.ArgumentParser(description='Clean branch questions and labels')
    parser.add_argument('--case-ids', nargs='+', type=int, help='Specific case IDs')
    parser.add_argument('--dry-run', action='store_true', help='Preview without saving')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        query = ExtractionPrompt.query.filter_by(concept_type='phase4_narrative')
        if args.case_ids:
            query = query.filter(ExtractionPrompt.case_id.in_(args.case_ids))

        prompts = query.order_by(ExtractionPrompt.case_id).all()
        seen = {}
        for p in prompts:
            if p.case_id not in seen or p.created_at > seen[p.case_id].created_at:
                seen[p.case_id] = p

        total_stats = {
            'em_dash_questions': 0,
            'em_dash_contexts': 0,
            'labels_shortened': 0,
            'em_dash_options': 0,
            'cases_modified': 0,
        }

        for case_id in sorted(seen.keys()):
            p = seen[case_id]
            data = json.loads(p.raw_response)
            stats = process_case(case_id, data, args.dry_run)

            changed = any(v > 0 for v in stats.values())
            if changed:
                total_stats['cases_modified'] += 1
                for k, v in stats.items():
                    total_stats[k] += v

                if args.dry_run:
                    parts = [f"{k}={v}" for k, v in stats.items() if v > 0]
                    logger.info(f"Case {case_id}: [DRY RUN] {', '.join(parts)}")
                else:
                    p.raw_response = json.dumps(data)
                    db.session.commit()

        if not args.dry_run:
            logger.info("All changes committed")

        logger.info(
            f"Done: {total_stats['cases_modified']} cases modified, "
            f"{total_stats['em_dash_questions']} questions cleaned, "
            f"{total_stats['em_dash_contexts']} contexts cleaned, "
            f"{total_stats['em_dash_options']} option labels cleaned, "
            f"{total_stats['labels_shortened']} labels shortened"
        )


if __name__ == '__main__':
    main()
