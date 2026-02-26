#!/usr/bin/env python3
"""
Post-extraction QC audit for ProEthica cases.

Runs V0-V9 verification checks against extracted case data and stores
results in the case_verification_results table for provenance tracking.

Usage:
    python scripts/analysis/run_qc_audit.py 4                  # Single case
    python scripts/analysis/run_qc_audit.py --batch 4 5 6 7 8  # Specific cases
    python scripts/analysis/run_qc_audit.py --phase1            # All 25 Phase 1 cases
    python scripts/analysis/run_qc_audit.py 4 --dry-run         # Check without storing
    python scripts/analysis/run_qc_audit.py --phase1 -v         # Verbose (show all checks)
    python scripts/analysis/run_qc_audit.py --phase1 --report   # Generate markdown report

Checks:
    V0  Section Text Integrity    CRITICAL  Facts + discussion sections exist
    V1  Duplicate Sessions        CRITICAL  No entity in multiple sessions
    V2  Arg/Val Count Mismatch    CRITICAL  argument_generated = argument_validation
    V3  Ungrammatical Claims      CRITICAL  No policy statements in argument claims
    V4  Decision Point Options    CRITICAL  Options are action phrases (verb form)
    V5  Argument Data Structure   CRITICAL  claim, warrant, argument_id fields present
    V6  Completeness              CRITICAL  All 16 extraction types present
    V7  Count Sanity              INFO      Counts within empirical Phase 1 ranges
    V8  Model Consistency         WARNING   Single LLM model used throughout
    V9  Publish Status            WARNING   All entities committed to OntServe

Reference: docs-internal/VERIFICATION_CRITERIA.md
"""

import json
import os
import re
import sys
import statistics
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, '/home/chris/onto')

import argparse
from app import create_app
from app.models import Document, db
from sqlalchemy import text

PROTOCOL_VERSION = '1.0'

# Phase 1 case IDs (25 cases, full injection mode extraction, Feb 2026)
PHASE1_CASE_IDS = [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22,
                   56, 57, 58, 59, 60, 71, 72]

# 16 extraction types expected from current pipeline (Steps 1-3 + Step 4)
REQUIRED_TYPES = [
    # Steps 1-3 (8 concept types)
    'roles', 'states', 'resources', 'principles', 'obligations',
    'constraints', 'capabilities', 'temporal_dynamics_enhanced',
    # Step 4 (8 analysis types)
    'code_provision_reference', 'precedent_case_reference',
    'ethical_question', 'ethical_conclusion', 'causal_normative_link',
    'question_emergence', 'resolution_pattern', 'canonical_decision_point',
]

# Empirical count ranges from Phase 1 (25 cases, Feb 2026)
EMPIRICAL_RANGES = {
    'roles':                       (6, 25),
    'states':                      (11, 33),
    'resources':                   (10, 26),
    'principles':                  (12, 33),
    'obligations':                 (12, 35),
    'constraints':                 (11, 57),
    'capabilities':                (15, 42),
    'temporal_dynamics_enhanced':  (14, 40),
    'code_provision_reference':    (3, 9),
    'precedent_case_reference':    (1, 11),
    'ethical_question':            (17, 21),
    'ethical_conclusion':          (20, 31),
    'causal_normative_link':      (4, 10),
    'question_emergence':          (17, 21),
    'resolution_pattern':          (20, 31),
    'canonical_decision_point':    (5, 18),
}

# V7 doc ranges (from VERIFICATION_CRITERIA.md, known to be stale -- kept for comparison)
V7_DOC_RANGES = {
    'roles': (3, 10), 'states': (5, 20), 'resources': (8, 30),
    'principles': (5, 20), 'obligations': (5, 20), 'constraints': (4, 15),
    'capabilities': (4, 15), 'temporal_dynamics_enhanced': (10, 30),
    'ethical_question': (5, 20), 'question_emergence': (5, 20),
    'ethical_conclusion': (3, 15), 'resolution_pattern': (3, 15),
    'canonical_decision_point': (2, 10), 'code_provision_reference': (3, 20),
    'causal_normative_link': (2, 15),
}


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_v0(case_id):
    """V0: Section Text Integrity -- facts and discussion sections exist and are non-empty."""
    result = {'check_id': 'V0', 'name': 'Section Text Integrity', 'severity': 'CRITICAL',
              'status': 'PASS', 'details': {}}

    row = db.session.execute(text("""
        SELECT id, LEFT(title, 80) as title,
               LENGTH(doc_metadata->'sections_dual'->'facts'->>'text') as facts_len,
               LENGTH(doc_metadata->'sections_dual'->'discussion'->>'text') as disc_len,
               doc_metadata->'sections_dual' IS NOT NULL as has_sections_dual
        FROM documents WHERE id = :case_id
    """), {'case_id': case_id}).fetchone()

    if not row:
        result['status'] = 'FAIL'
        result['details'] = {'error': f'Case {case_id} not found'}
        return result

    result['details']['title'] = row.title
    result['details']['facts_len'] = row.facts_len or 0
    result['details']['discussion_len'] = row.disc_len or 0

    issues = []
    if not row.has_sections_dual:
        issues.append('No sections_dual in doc_metadata')
    elif (row.facts_len or 0) == 0:
        issues.append('Empty facts section')
    elif (row.disc_len or 0) == 0:
        issues.append('Empty discussion section')

    if issues:
        result['status'] = 'FAIL'
        result['details']['issues'] = issues
    return result


def check_v1(case_id):
    """V1: Duplicate Sessions -- no entity appears in multiple extraction sessions."""
    result = {'check_id': 'V1', 'name': 'Duplicate Sessions', 'severity': 'CRITICAL',
              'status': 'PASS', 'details': {'multi_session_types': [], 'actual_duplicates': []}}

    multi = db.session.execute(text("""
        SELECT extraction_type, COUNT(DISTINCT extraction_session_id) as sessions, COUNT(*) as total
        FROM temporary_rdf_storage WHERE case_id = :cid
        GROUP BY extraction_type HAVING COUNT(DISTINCT extraction_session_id) > 1
    """), {'cid': case_id}).fetchall()

    if not multi:
        return result

    for row in multi:
        etype, sessions, total = row[0], row[1], row[2]
        result['details']['multi_session_types'].append({
            'type': etype, 'sessions': sessions, 'total': total})

        dupes = db.session.execute(text("""
            SELECT entity_label, COUNT(DISTINCT extraction_session_id) as in_sessions
            FROM temporary_rdf_storage
            WHERE case_id = :cid AND extraction_type = :etype
            GROUP BY entity_label HAVING COUNT(DISTINCT extraction_session_id) > 1
        """), {'cid': case_id, 'etype': etype}).fetchall()

        for d in dupes:
            result['details']['actual_duplicates'].append({
                'type': etype, 'entity_label': d[0], 'in_sessions': d[1]})

    if result['details']['actual_duplicates']:
        result['status'] = 'FAIL'
    elif result['details']['multi_session_types']:
        result['status'] = 'INFO'
        result['severity'] = 'INFO'
    return result


def check_v2(case_id):
    """V2: Arg/Val Count Mismatch."""
    result = {'check_id': 'V2', 'name': 'Arg/Val Count Mismatch', 'severity': 'CRITICAL',
              'status': 'NOT_APPLICABLE', 'details': {}}

    row = db.session.execute(text("""
        SELECT COUNT(CASE WHEN extraction_type = 'argument_generated' THEN 1 END) as args,
               COUNT(CASE WHEN extraction_type = 'argument_validation' THEN 1 END) as vals
        FROM temporary_rdf_storage WHERE case_id = :cid
    """), {'cid': case_id}).fetchone()

    result['details'] = {'argument_generated': row[0], 'argument_validation': row[1]}
    if row[0] == 0 and row[1] == 0:
        result['details']['note'] = 'Current pipeline does not produce argument entities'
        return result

    result['status'] = 'PASS' if row[0] == row[1] else 'FAIL'
    return result


def check_v3(case_id):
    """V3: Ungrammatical Claims."""
    result = {'check_id': 'V3', 'name': 'Ungrammatical Claims', 'severity': 'CRITICAL',
              'status': 'NOT_APPLICABLE', 'details': {}}

    cnt = db.session.execute(text(
        "SELECT COUNT(*) FROM temporary_rdf_storage "
        "WHERE case_id = :cid AND extraction_type = 'argument_generated'"
    ), {'cid': case_id}).scalar()

    if cnt == 0:
        result['details']['note'] = 'No argument_generated entities'
        return result

    bad = db.session.execute(text("""
        SELECT entity_label, LEFT(entity_definition, 120) as defn
        FROM temporary_rdf_storage
        WHERE case_id = :cid AND extraction_type = 'argument_generated'
          AND (entity_definition ILIKE '%should make the No %'
               OR entity_definition ILIKE '%should NOT make the No %'
               OR entity_definition ILIKE '%should the %')
    """), {'cid': case_id}).fetchall()

    result['status'] = 'FAIL' if bad else 'PASS'
    if bad:
        result['details']['violations'] = [{'label': r[0], 'text': r[1]} for r in bad]
    return result


def check_v4(case_id):
    """V4: Decision Point Option Format -- options are action phrases."""
    result = {'check_id': 'V4', 'name': 'Decision Point Options', 'severity': 'CRITICAL',
              'status': 'PASS', 'details': {'decision_points': [], 'violations': []}}

    rows = db.session.execute(text("""
        SELECT entity_label, rdf_json_ld
        FROM temporary_rdf_storage
        WHERE case_id = :cid AND extraction_type = 'canonical_decision_point'
        ORDER BY entity_label
    """), {'cid': case_id}).fetchall()

    if not rows:
        result['status'] = 'FAIL'
        result['details']['error'] = 'No decision points found'
        return result

    bad_patterns = [
        (r'^No\s+\w+\s+required', 'Starts with "No ... required"'),
        (r'^(?:The|A|An)\s', 'Starts with article'),
    ]

    for row in rows:
        label, data = row[0], row[1] or {}
        options = data.get('options', [])
        result['details']['decision_points'].append({'label': label, 'options': len(options)})

        for i, opt in enumerate(options):
            desc = opt.get('description', '') if isinstance(opt, dict) else str(opt)
            for pattern, reason in bad_patterns:
                if re.match(pattern, desc):
                    result['details']['violations'].append({
                        'dp': label, 'index': i, 'text': desc[:100], 'reason': reason})

    if result['details']['violations']:
        result['status'] = 'FAIL'
    return result


def check_v5(case_id):
    """V5: Argument Data Structure."""
    result = {'check_id': 'V5', 'name': 'Argument Data Structure', 'severity': 'CRITICAL',
              'status': 'NOT_APPLICABLE', 'details': {}}

    rows = db.session.execute(text("""
        SELECT entity_label, rdf_json_ld FROM temporary_rdf_storage
        WHERE case_id = :cid AND extraction_type = 'argument_generated' LIMIT 5
    """), {'cid': case_id}).fetchall()

    if not rows:
        result['details']['note'] = 'No argument_generated entities'
        return result

    malformed = []
    for row in rows:
        data = row[1] or {}
        missing = [f for f in ['argument_id', 'claim', 'warrant'] if f not in data]
        if missing:
            malformed.append({'label': row[0], 'missing': missing})

    result['status'] = 'FAIL' if malformed else 'PASS'
    if malformed:
        result['details']['malformed'] = malformed
    return result


def check_v6(case_id):
    """V6: Completeness -- all 16 expected extraction types present."""
    result = {'check_id': 'V6', 'name': 'Completeness', 'severity': 'CRITICAL',
              'status': 'PASS', 'details': {}}

    rows = db.session.execute(text("""
        SELECT extraction_type, COUNT(*) as cnt FROM temporary_rdf_storage
        WHERE case_id = :cid GROUP BY extraction_type ORDER BY extraction_type
    """), {'cid': case_id}).fetchall()

    present = {r[0]: r[1] for r in rows}
    missing = [t for t in REQUIRED_TYPES if t not in present]

    result['details']['present_types'] = list(present.keys())
    result['details']['type_count'] = len(present)
    result['details']['missing_types'] = missing
    result['details']['counts'] = present

    if missing:
        result['status'] = 'FAIL'
    return result


def check_v7(case_id, counts=None):
    """V7: Count Sanity -- entity counts within empirical ranges."""
    result = {'check_id': 'V7', 'name': 'Count Sanity', 'severity': 'INFO',
              'status': 'PASS', 'details': {'out_of_range': []}}

    if counts is None:
        rows = db.session.execute(text("""
            SELECT extraction_type, COUNT(*) as cnt FROM temporary_rdf_storage
            WHERE case_id = :cid GROUP BY extraction_type
        """), {'cid': case_id}).fetchall()
        counts = {r[0]: r[1] for r in rows}

    result['details']['total'] = sum(counts.values())

    for etype, (lo, hi) in EMPIRICAL_RANGES.items():
        cnt = counts.get(etype, 0)
        if cnt > 0 and (cnt < lo or cnt > hi):
            result['details']['out_of_range'].append({
                'type': etype, 'count': cnt,
                'range': f'{lo}-{hi}',
                'deviation': 'below' if cnt < lo else 'above'})

    if result['details']['out_of_range']:
        result['status'] = 'INFO'
    return result


def check_v8(case_id):
    """V8: Model Consistency -- single extraction model used."""
    result = {'check_id': 'V8', 'name': 'Model Consistency', 'severity': 'WARNING',
              'status': 'PASS', 'details': {}}

    prompt_models = [r[0] for r in db.session.execute(text(
        "SELECT DISTINCT llm_model FROM extraction_prompts WHERE case_id = :cid"
    ), {'cid': case_id}).fetchall()]

    entity_models = [r[0] for r in db.session.execute(text(
        "SELECT DISTINCT extraction_model FROM temporary_rdf_storage "
        "WHERE case_id = :cid AND extraction_model IS NOT NULL"
    ), {'cid': case_id}).fetchall()]

    result['details']['prompt_models'] = prompt_models
    result['details']['entity_models'] = entity_models

    # "algorithmic" is expected for Phase 3 decision synthesis (not a real model)
    all_models = set(prompt_models + entity_models) - {None, 'algorithmic'}
    if len(all_models) > 1:
        result['status'] = 'FAIL'
        result['details']['note'] = f'Multiple models: {sorted(all_models)}'
    return result


def check_v9(case_id):
    """V9: Publish Status -- all entities committed to OntServe."""
    result = {'check_id': 'V9', 'name': 'Publish Status', 'severity': 'WARNING',
              'status': 'PASS', 'details': {}}

    row = db.session.execute(text("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN is_published THEN 1 ELSE 0 END) as published
        FROM temporary_rdf_storage WHERE case_id = :cid
    """), {'cid': case_id}).fetchone()

    result['details'] = {'total': row[0], 'published': row[1],
                         'unpublished': row[0] - row[1]}
    if row[0] > row[1]:
        result['status'] = 'FAIL'
    return result


ALL_CHECKS = [check_v0, check_v1, check_v2, check_v3, check_v4,
              check_v5, check_v6, check_v7, check_v8, check_v9]


# ---------------------------------------------------------------------------
# Audit runner
# ---------------------------------------------------------------------------

def run_audit(case_id):
    """Run all V0-V9 checks and return structured result."""
    checks = []
    counts = None

    for fn in ALL_CHECKS:
        if fn == check_v7:
            # V7 uses counts from V6 if available
            r = fn(case_id, counts)
        else:
            r = fn(case_id)
        checks.append(r)
        # Capture counts from V6 for V7
        if r['check_id'] == 'V6':
            counts = r['details'].get('counts', {})

    critical = sum(1 for r in checks if r['status'] == 'FAIL' and r['severity'] == 'CRITICAL')
    warnings = sum(1 for r in checks if r['status'] == 'FAIL' and r['severity'] == 'WARNING')
    info = sum(1 for r in checks if r['status'] == 'INFO')

    if critical > 0:
        overall = 'FAIL'
    elif warnings > 0:
        overall = 'ISSUES_FOUND'
    else:
        overall = 'PASS'

    entity_total = sum(counts.values()) if counts else 0
    type_count = len(counts) if counts else 0

    return {
        'case_id': case_id,
        'verification_date': datetime.now(timezone.utc).isoformat(),
        'protocol_version': PROTOCOL_VERSION,
        'overall_status': overall,
        'entity_count_total': entity_total,
        'extraction_types_count': type_count,
        'critical_count': critical,
        'warning_count': warnings,
        'info_count': info,
        'check_results': checks,
    }


def store_audit(audit):
    """Store audit result in case_verification_results table."""
    db.session.execute(text("""
        INSERT INTO case_verification_results
            (case_id, verification_date, protocol_version, overall_status,
             entity_count_total, extraction_types_count,
             critical_count, warning_count, info_count, check_results)
        VALUES
            (:case_id, :vdate, :pver, :status,
             :etotal, :tcount, :cc, :wc, :ic, :checks)
    """), {
        'case_id': audit['case_id'],
        'vdate': audit['verification_date'],
        'pver': audit['protocol_version'],
        'status': audit['overall_status'],
        'etotal': audit['entity_count_total'],
        'tcount': audit['extraction_types_count'],
        'cc': audit['critical_count'],
        'wc': audit['warning_count'],
        'ic': audit['info_count'],
        'checks': json.dumps(audit['check_results']),
    })
    db.session.commit()


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def print_audit(audit, verbose=False):
    """Print audit result to stdout."""
    case_id = audit['case_id']
    status = audit['overall_status']
    total = audit['entity_count_total']
    types = audit['extraction_types_count']

    marker = {'PASS': '+', 'FAIL': 'X', 'ISSUES_FOUND': '!'}
    print(f"\n[{marker.get(status, '?')}] Case {case_id}: {status}  "
          f"({total} entities, {types} types, "
          f"{audit['critical_count']}C/{audit['warning_count']}W/{audit['info_count']}I)")

    for r in audit['check_results']:
        s = r['status']
        if s == 'PASS' and not verbose:
            continue
        if s == 'NOT_APPLICABLE' and not verbose:
            continue

        sev = r['severity']
        tag = f"[{sev}]" if s in ('FAIL', 'INFO') else f"[{s}]"
        print(f"  {r['check_id']} {r['name']}: {s} {tag}")

        details = r.get('details', {})
        if s in ('FAIL', 'INFO') or verbose:
            if 'missing_types' in details and details['missing_types']:
                print(f"    Missing: {', '.join(details['missing_types'])}")
            if 'actual_duplicates' in details and details['actual_duplicates']:
                for d in details['actual_duplicates']:
                    print(f"    Duplicate: {d['type']}/{d['entity_label']} ({d['in_sessions']} sessions)")
            if details.get('multi_session_types') and s == 'INFO':
                for m in details['multi_session_types']:
                    print(f"    Supplemental: {m['type']} ({m['sessions']} sessions, {m['total']} entities)")
            if 'violations' in details and details['violations']:
                for v in details['violations']:
                    if 'dp' in v:
                        print(f"    {v['dp']}[{v['index']}]: \"{v['text'][:70]}\" -- {v['reason']}")
                    elif 'label' in v:
                        print(f"    {v['label']}: {v.get('text', '')[:70]}")
            if 'out_of_range' in details and details['out_of_range']:
                for o in details['out_of_range']:
                    print(f"    {o['type']}: {o['count']} ({o['deviation']} range {o['range']})")
            if 'note' in details:
                print(f"    {details['note']}")
            if details.get('unpublished', 0) > 0:
                print(f"    {details['unpublished']} of {details['total']} entities unpublished")
            if 'error' in details:
                print(f"    {details['error']}")
            if 'issues' in details and isinstance(details['issues'], list):
                for issue in details['issues']:
                    print(f"    {issue}")


def write_report(audits, path):
    """Write markdown summary report for multiple audit results."""
    lines = []
    lines.append("# QC Audit Report")
    lines.append("")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Protocol:** v{PROTOCOL_VERSION}")
    lines.append(f"**Cases:** {len(audits)}")
    lines.append(f"**Checks:** V0-V9 (10 checks per case)")
    lines.append("")

    # Summary
    pass_n = sum(1 for a in audits if a['overall_status'] == 'PASS')
    fail_n = sum(1 for a in audits if a['overall_status'] == 'FAIL')
    issues_n = sum(1 for a in audits if a['overall_status'] == 'ISSUES_FOUND')

    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Status | Count |")
    lines.append(f"|--------|------:|")
    lines.append(f"| PASS | {pass_n} |")
    lines.append(f"| FAIL | {fail_n} |")
    lines.append(f"| ISSUES_FOUND | {issues_n} |")
    lines.append("")

    # Per-check aggregation
    check_agg = defaultdict(lambda: {'pass': 0, 'fail': 0, 'info': 0, 'na': 0})
    for a in audits:
        for r in a['check_results']:
            cid = r['check_id']
            if r['status'] == 'PASS':
                check_agg[cid]['pass'] += 1
            elif r['status'] == 'FAIL':
                check_agg[cid]['fail'] += 1
            elif r['status'] == 'INFO':
                check_agg[cid]['info'] += 1
            elif r['status'] == 'NOT_APPLICABLE':
                check_agg[cid]['na'] += 1

    check_names = {
        'V0': 'Section Text Integrity', 'V1': 'Duplicate Sessions',
        'V2': 'Arg/Val Mismatch', 'V3': 'Ungrammatical Claims',
        'V4': 'Decision Point Options', 'V5': 'Argument Structure',
        'V6': 'Completeness', 'V7': 'Count Sanity',
        'V8': 'Model Consistency', 'V9': 'Publish Status',
    }

    lines.append("## Results by Check")
    lines.append("")
    lines.append("| Check | Name | PASS | FAIL | INFO | N/A |")
    lines.append("|-------|------|:----:|:----:|:----:|:---:|")
    for cid in ['V0', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6', 'V7', 'V8', 'V9']:
        s = check_agg[cid]
        lines.append(f"| {cid} | {check_names[cid]} | {s['pass']} | {s['fail']} | "
                     f"{s['info']} | {s['na']} |")
    lines.append("")

    # Per-case table
    lines.append("## Per-Case Results")
    lines.append("")
    lines.append("| Case | Status | Entities | Types | C | W | I |")
    lines.append("|-----:|--------|:--------:|:-----:|:-:|:-:|:-:|")
    for a in audits:
        lines.append(f"| {a['case_id']} | {a['overall_status']} | {a['entity_count_total']} | "
                     f"{a['extraction_types_count']} | {a['critical_count']} | "
                     f"{a['warning_count']} | {a['info_count']} |")
    lines.append("")

    # Critical/warning details
    has_issues = [a for a in audits if a['overall_status'] != 'PASS']
    if has_issues:
        lines.append("## Issue Details")
        lines.append("")
        for a in has_issues:
            lines.append(f"### Case {a['case_id']}")
            lines.append("")
            for r in a['check_results']:
                if r['status'] in ('FAIL', 'INFO'):
                    details = r.get('details', {})
                    summary_parts = []
                    if details.get('missing_types'):
                        summary_parts.append(f"Missing: {', '.join(details['missing_types'])}")
                    if details.get('actual_duplicates'):
                        summary_parts.append(f"{len(details['actual_duplicates'])} duplicates")
                    if details.get('violations'):
                        summary_parts.append(f"{len(details['violations'])} violations")
                    if details.get('out_of_range'):
                        summary_parts.append(f"{len(details['out_of_range'])} out of range")
                    if details.get('unpublished', 0) > 0:
                        summary_parts.append(f"{details['unpublished']} unpublished")
                    if details.get('note'):
                        summary_parts.append(details['note'])

                    summary = '; '.join(summary_parts) if summary_parts else r['status']
                    lines.append(f"- **{r['check_id']}** [{r['severity']}]: {summary}")
            lines.append("")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write('\n'.join(lines))
    print(f"Report: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Post-extraction QC audit')
    parser.add_argument('case_ids', nargs='*', type=int, help='Case ID(s)')
    parser.add_argument('--phase1', action='store_true', help='All 25 Phase 1 cases')
    parser.add_argument('--batch', nargs='+', type=int, help='Specific case IDs')
    parser.add_argument('--dry-run', action='store_true', help='Do not store results')
    parser.add_argument('--report', action='store_true', help='Generate markdown report')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    if args.phase1:
        case_ids = PHASE1_CASE_IDS
    elif args.batch:
        case_ids = args.batch
    elif args.case_ids:
        case_ids = args.case_ids
    else:
        parser.print_help()
        return 1

    app = create_app()
    with app.app_context():
        audits = []
        for case_id in case_ids:
            audit = run_audit(case_id)
            print_audit(audit, verbose=args.verbose)
            audits.append(audit)

            if not args.dry_run:
                store_audit(audit)

        pass_n = sum(1 for a in audits if a['overall_status'] == 'PASS')
        fail_n = sum(1 for a in audits if a['overall_status'] == 'FAIL')
        issues_n = sum(1 for a in audits if a['overall_status'] == 'ISSUES_FOUND')

        print(f"\n{'='*60}")
        print(f"QC Audit: {len(audits)} cases (protocol v{PROTOCOL_VERSION})")
        print(f"  PASS: {pass_n}  FAIL: {fail_n}  ISSUES: {issues_n}")
        if not args.dry_run:
            print(f"  Stored in case_verification_results")
        else:
            print(f"  (dry run)")

        if args.report:
            report_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'docs-internal', 'qc', 'qc_audit_report.md')
            write_report(audits, report_path)

        return 0 if fail_n == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
