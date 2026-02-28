#!/usr/bin/env python3
"""
Fix decision point coherence: ensure options are discrete answers to the question.

For each canonical_decision_point, checks whether the options logically answer
the decision_question/description. If not, rewrites the question as an actionable
"Should X do Y or Z?" framing and regenerates discrete options grounded in
the Toulmin context already stored in the DP.

Usage:
    python scripts/fix_decision_point_coherence.py                  # Audit all
    python scripts/fix_decision_point_coherence.py --case 72        # Single case
    python scripts/fix_decision_point_coherence.py --fix            # Audit + fix
    python scripts/fix_decision_point_coherence.py --fix --case 72  # Fix single case
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.utils.llm_utils import streaming_completion, get_llm_client
from app.utils.llm_json_utils import parse_json_response
from sqlalchemy import text

MODEL = 'claude-sonnet-4-6'


def get_all_cases():
    """Return all case IDs with decision points."""
    rows = db.session.execute(text("""
        SELECT DISTINCT case_id
        FROM temporary_rdf_storage
        WHERE extraction_type = 'canonical_decision_point'
        ORDER BY case_id
    """)).fetchall()
    return [r[0] for r in rows]


def get_decision_points(case_id):
    """Return list of (id, entity_label, rdf_json_ld) for a case's decision points."""
    rows = db.session.execute(text("""
        SELECT id, entity_label, rdf_json_ld
        FROM temporary_rdf_storage
        WHERE case_id = :cid AND extraction_type = 'canonical_decision_point'
        ORDER BY entity_label
    """), {'cid': case_id}).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def build_audit_prompt(decision_points):
    """Build a prompt that audits question-option coherence."""
    dp_texts = []
    for i, (db_id, entity_label, data) in enumerate(decision_points):
        description = data.get('description', '')
        question = data.get('decision_question', '')
        toulmin = data.get('toulmin') or {}
        role = data.get('role_label', '')
        options = data.get('options', [])

        opt_lines = []
        for j, opt in enumerate(options):
            label = opt.get('label', '')
            desc = opt.get('description', '')[:150]
            board = " [BOARD]" if opt.get('is_board_choice') else ""
            opt_lines.append(f"    O{j+1}: {label} -- {desc}{board}")

        dp_texts.append(f"""  DP{i+1} (db_id={db_id}):
    ROLE: {role}
    DESCRIPTION: {description[:250]}
    QUESTION: {question[:250] if question else '(none)'}
    TOULMIN DATA: {toulmin.get('data_summary', '')[:200]}
    TOULMIN WARRANTS: {toulmin.get('warrants_summary', '')[:200]}
    TOULMIN REBUTTALS: {toulmin.get('rebuttals_summary', '')[:200]}
    OPTIONS:
""" + "\n".join(opt_lines))

    prompt = f"""Audit each decision point below for COHERENCE between the question and the options.

A COHERENT decision point has:
1. A question framed as a choice the named role/agent must make (e.g., "Should Engineer A disclose X or keep it confidential?")
2. Options that are DIRECT ANSWERS to that question -- discrete alternative courses of action the agent could plausibly take
3. Each option must logically follow from the question -- if you read the question, then read the option, the option must be a plausible answer

INCOHERENT patterns to flag:
- Question asks "at what point / when / whether" but options are generic actions unrelated to the timing/scope question
- Question is an abstract analytical statement but options are concrete actions that don't map to it
- Options are all variants of the same action (e.g., three flavors of "disclose") rather than genuinely different choices
- Options don't relate to the specific role and decision described

For each DP, return:
- "coherent": true/false
- "issue": brief explanation of the mismatch (only if incoherent)

Return JSON array:
```json
[
  {{"db_id": 12345, "coherent": true}},
  {{"db_id": 12346, "coherent": false, "issue": "Question asks about timing of obligation but options are disclosure actions"}},
  ...
]
```

Decision points:
{chr(10).join(dp_texts)}
"""
    return prompt


def audit_coherence(decision_points):
    """Call LLM to audit coherence of a batch of DPs. Returns db_id -> issue mapping."""
    prompt = build_audit_prompt(decision_points)

    client = get_llm_client()
    response = streaming_completion(
        client=client,
        model=MODEL,
        max_tokens=4096,
        prompt=prompt,
        temperature=0.0,
    )

    results = parse_json_response(response, "coherence audit", strict=False)
    if not results:
        print("    WARNING: No JSON parsed from audit response")
        return {}

    issues = {}
    for item in results:
        db_id = item.get('db_id')
        if db_id and not item.get('coherent', True):
            issues[db_id] = item.get('issue', 'unspecified')

    return issues


def build_fix_prompt(decision_points_with_issues):
    """Build a prompt to rewrite incoherent DPs."""
    dp_texts = []
    for i, (db_id, entity_label, data, issue) in enumerate(decision_points_with_issues):
        description = data.get('description', '')
        question = data.get('decision_question', '')
        toulmin = data.get('toulmin') or {}
        role = data.get('role_label', '')
        options = data.get('options', [])

        opt_lines = []
        for j, opt in enumerate(options):
            label = opt.get('label', '')
            desc = opt.get('description', '')[:200]
            board = " [BOARD]" if opt.get('is_board_choice') else ""
            opt_lines.append(f"    O{j+1}: {label} -- {desc}{board}")

        dp_texts.append(f"""  DP{i+1} (db_id={db_id}):
    ROLE: {role}
    CURRENT DESCRIPTION: {description[:300]}
    CURRENT QUESTION: {question[:300] if question else '(none)'}
    COHERENCE ISSUE: {issue}
    TOULMIN DATA: {toulmin.get('data_summary', '')[:300]}
    TOULMIN WARRANTS: {toulmin.get('warrants_summary', '')[:300]}
    TOULMIN REBUTTALS: {toulmin.get('rebuttals_summary', '')[:300]}
    BACKING PROVISIONS: {', '.join(toulmin.get('backing_provisions', []))}
    CURRENT OPTIONS:
""" + "\n".join(opt_lines))

    prompt = f"""Rewrite each incoherent decision point below so that the question and options form a coherent decision.

REQUIREMENTS:

1. DESCRIPTION: Keep the existing description or lightly edit for clarity. Do not wholesale replace it.

2. DECISION QUESTION: Reframe as an actionable choice the named role faces.
   - Format: "Should [role] [action A] or [action B]?" or "Must [role] [choice]?"
   - The question must present the core tension between competing courses of action.
   - The question must relate to the description and the Toulmin context.

3. OPTIONS: Generate 2-3 options that are DIRECT ANSWERS to the reframed question.
   - Each option must be a discrete, plausible course of action the role could take.
   - Each option label: 3-8 words, Title Case, starting with a verb.
   - Each option description: 1-2 sentences elaborating the action with case-specific detail.
   - One option should be marked is_board_choice=true (the one closest to the NSPE board's resolution).
   - Options must represent genuinely different positions, not variations of the same action.
   - Ground options in the Toulmin context: DATA (what happened), WARRANTS (competing obligations), REBUTTALS (uncertainty).

4. Preserve existing option_id values (O1, O2, O3) and action_uri values if present.

GOOD EXAMPLE (case 18):
  Question: "Should Engineer B provide a complete verbal warning about lead risk to the Commissioners -- including danger to children -- even at risk of the client relationship, or moderate the disclosure?"
  Options:
    O1: "Deliver Complete Verbal Risk Warning" -- Full technical warning including child danger [BOARD]
    O2: "Moderate Disclosure to Preserve Relationship" -- Partial warning omitting most alarming details
    O3: "Issue Written Report Without Verbal Escalation" -- Skip verbal warning, rely on written report only

Return JSON array:
```json
[
  {{
    "db_id": 12345,
    "description": "lightly edited description if needed, or keep original",
    "decision_question": "Should [role] do X or Y?",
    "options": [
      {{"option_id": "O1", "label": "Short Label Here", "description": "1-2 sentences", "is_board_choice": true}},
      {{"option_id": "O2", "label": "Short Label Here", "description": "1-2 sentences", "is_board_choice": false}},
      {{"option_id": "O3", "label": "Short Label Here", "description": "1-2 sentences", "is_board_choice": false}}
    ]
  }}
]
```

Decision points to fix:
{chr(10).join(dp_texts)}
"""
    return prompt


def fix_incoherent(decision_points_with_issues):
    """Call LLM to rewrite incoherent DPs. Returns db_id -> fixed_data mapping."""
    prompt = build_fix_prompt(decision_points_with_issues)

    client = get_llm_client()
    response = streaming_completion(
        client=client,
        model=MODEL,
        max_tokens=8192,
        prompt=prompt,
        temperature=0.2,
    )

    results = parse_json_response(response, "coherence fix", strict=False)
    if not results:
        print("    WARNING: No JSON parsed from fix response")
        return {}

    fixes = {}
    for item in results:
        db_id = item.get('db_id')
        if db_id:
            fixes[db_id] = item

    return fixes


def apply_fixes(decision_points, fixes, dry_run=False):
    """Apply coherence fixes to the database."""
    updated = 0
    for db_id, entity_label, data in decision_points:
        fix = fixes.get(db_id)
        if not fix:
            continue

        # Update question
        new_question = fix.get('decision_question')
        if new_question:
            data['decision_question'] = new_question

        # Update description if provided
        new_desc = fix.get('description')
        if new_desc:
            data['description'] = new_desc

        # Update options -- preserve action_uri from originals
        new_options = fix.get('options', [])
        old_options = data.get('options', [])

        if new_options:
            # Carry forward action_uri from old options by position
            for j, new_opt in enumerate(new_options):
                if j < len(old_options) and 'action_uri' in old_options[j]:
                    new_opt.setdefault('action_uri', old_options[j]['action_uri'])
            data['options'] = new_options

        if dry_run:
            print(f"    DRY RUN {db_id}:")
            print(f"      Q: {data.get('decision_question', '')[:100]}")
            for opt in data.get('options', []):
                board = " [BOARD]" if opt.get('is_board_choice') else ""
                print(f"      - {opt.get('label', '?')}{board}")
        else:
            db.session.execute(text("""
                UPDATE temporary_rdf_storage
                SET rdf_json_ld = :data
                WHERE id = :id
            """), {'id': db_id, 'data': json.dumps(data)})
            updated += 1

    if not dry_run and updated > 0:
        db.session.commit()

    return updated


def process_case(case_id, fix=False):
    """Audit and optionally fix decision points for a case."""
    dps = get_decision_points(case_id)
    if not dps:
        return 0, 0

    print(f"  Case {case_id}: {len(dps)} decision points")

    # Audit in batches of 10
    BATCH_SIZE = 10
    all_issues = {}

    for batch_start in range(0, len(dps), BATCH_SIZE):
        batch = dps[batch_start:batch_start + BATCH_SIZE]
        t0 = time.time()
        issues = audit_coherence(batch)
        elapsed = time.time() - t0
        all_issues.update(issues)
        incoherent = len(issues)
        print(f"    Audit batch {batch_start//BATCH_SIZE + 1}: "
              f"{incoherent}/{len(batch)} incoherent ({elapsed:.0f}s)")

    if not all_issues:
        print(f"    All coherent")
        return len(dps), 0

    # Print issues
    for db_id, issue in all_issues.items():
        # Find the entity label for this db_id
        label = next((el for did, el, _ in dps if did == db_id), '?')
        print(f"    INCOHERENT {db_id} ({label[:60]}): {issue}")

    if not fix:
        return len(dps), len(all_issues)

    # Fix incoherent DPs
    FIX_BATCH_SIZE = 5  # smaller batches for fixes (more context per DP)
    incoherent_dps = [(db_id, el, data, all_issues[db_id])
                      for db_id, el, data in dps if db_id in all_issues]

    total_fixed = 0
    for batch_start in range(0, len(incoherent_dps), FIX_BATCH_SIZE):
        batch = incoherent_dps[batch_start:batch_start + FIX_BATCH_SIZE]
        t0 = time.time()
        fixes = fix_incoherent(batch)
        elapsed = time.time() - t0
        print(f"    Fix batch {batch_start//FIX_BATCH_SIZE + 1}: "
              f"{len(fixes)}/{len(batch)} fixed ({elapsed:.0f}s)")

        # Apply to DB
        dps_in_batch = [(db_id, el, data) for db_id, el, data, _ in batch]
        fixed = apply_fixes(dps_in_batch, fixes)
        total_fixed += fixed

    return len(dps), total_fixed


def main():
    parser = argparse.ArgumentParser(description='Fix decision point question-option coherence')
    parser.add_argument('--case', type=int, help='Process a single case')
    parser.add_argument('--fix', action='store_true', help='Apply fixes (default: audit only)')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.case:
            case_ids = [args.case]
        else:
            case_ids = get_all_cases()

        print(f"{'Fixing' if args.fix else 'Auditing'} {len(case_ids)} cases")
        total_audited = 0
        total_incoherent = 0
        total_fixed = 0

        for case_id in case_ids:
            audited, incoherent_or_fixed = process_case(case_id, fix=args.fix)
            total_audited += audited
            if args.fix:
                total_fixed += incoherent_or_fixed
            else:
                total_incoherent += incoherent_or_fixed

        print(f"\nDone: {total_audited} DPs audited across {len(case_ids)} cases")
        if args.fix:
            print(f"  {total_fixed} DPs fixed")
        else:
            print(f"  {total_incoherent} DPs flagged as incoherent")
            if total_incoherent > 0:
                print(f"  Re-run with --fix to apply corrections")


if __name__ == '__main__':
    main()
