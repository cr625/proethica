#!/usr/bin/env python3
"""
Pre-extraction source URL validation.

Fetches the live NSPE source page for a case, extracts sections from
Drupal field elements (the canonical source), and compares with what's
stored in sections/sections_dual. Flags missing or substantially shorter
sections.

Usage:
    python scripts/validate_source_sections.py <case_id>
    python scripts/validate_source_sections.py <case_id> --fix    # update DB from live page
    python scripts/validate_source_sections.py --batch             # validate next N from queue
    python scripts/validate_source_sections.py --batch --fix       # validate + fix all
"""

import argparse
import json
import logging
import os
import sys

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Drupal field class -> our section name
DRUPAL_FIELD_MAP = {
    'field--name-field-case-facts': 'facts',
    'field--name-field-case-question': 'question',
    'field--name-field-case-description': 'discussion',
    'field--name-field-code-of-ethics': 'references',
    'field--name-field-case-conclusion': 'conclusion',
}

SECTION_NAMES = ['facts', 'question', 'references', 'discussion', 'conclusion']

# Stored section must be >= this fraction of live section length
RATIO_THRESHOLD = 0.90


def get_db_connection():
    import psycopg2
    return psycopg2.connect(
        host='localhost', port=5432,
        dbname='ai_ethical_dm', user='postgres', password='PASS'
    )


def fetch_case_info(conn, case_id):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, source, title,
                   doc_metadata->'sections' as sections,
                   doc_metadata->'sections_dual' as sections_dual,
                   doc_metadata->>'case_number' as case_number,
                   doc_metadata->>'year' as year,
                   doc_metadata as full_metadata
            FROM documents WHERE id = %s
        """, (case_id,))
        row = cur.fetchone()
        if not row:
            return None
        to_dict = lambda v: v if isinstance(v, dict) else (json.loads(v) if v else {})
        return {
            'id': row[0],
            'source_url': row[1],
            'title': row[2],
            'sections': to_dict(row[3]),
            'sections_dual': to_dict(row[4]),
            'case_number': row[5],
            'year': row[6],
            'full_metadata': to_dict(row[7]),
        }


def fetch_live_sections(url):
    """Fetch the live NSPE page and extract sections from Drupal fields.

    Returns (dict of section_name -> {text, html}, error_string_or_None).
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    sections = {}
    for drupal_class, section_name in DRUPAL_FIELD_MAP.items():
        el = soup.find('div', class_=drupal_class)
        if el:
            # Get the inner content div (skip the label div)
            items_div = el.find('div', class_='field__items') or el.find('div', class_='field__item') or el
            text = _extract_clean_text(items_div)
            html = str(items_div)
            if text.strip():
                sections[section_name] = {'text': text.strip(), 'html': html}

    if not sections:
        return None, "No Drupal field elements found on page"

    return sections, None


def _extract_clean_text(element):
    """Extract text from a BeautifulSoup element, preserving paragraph breaks."""
    # Use get_text with newline separator, then normalize
    # This avoids double-counting from nested element traversal
    paragraphs = []
    for p in element.find_all(['p', 'div', 'li'], recursive=False):
        text = p.get_text(separator=' ', strip=True)
        if text:
            paragraphs.append(text)
    if paragraphs:
        return '\n'.join(paragraphs)
    # Fallback: direct get_text
    return element.get_text(separator='\n', strip=True)


def get_stored_len(case_info, section):
    """Get stored text length for a section."""
    # sections_dual has {text, html} for facts/discussion/references/etc
    dual = case_info.get('sections_dual', {}).get(section)
    if dual:
        if isinstance(dual, dict):
            return len(dual.get('text', ''))
        return len(dual)
    # Fallback to original sections
    orig = case_info.get('sections', {}).get(section, '')
    return len(orig)


def compare_sections(case_info, live):
    """Compare stored sections with live Drupal fields.

    Returns list of issues.
    """
    issues = []

    for section in SECTION_NAMES:
        live_entry = live.get(section)
        live_len = len(live_entry['text']) if live_entry else 0
        stored_len = get_stored_len(case_info, section)

        if live_len == 0 and stored_len == 0:
            continue
        if live_len == 0 and stored_len > 0:
            issues.append({
                'severity': 'INFO',
                'section': section,
                'message': f'Stored ({stored_len}) but not in Drupal fields',
                'live_len': 0, 'stored_len': stored_len,
            })
            continue
        if stored_len == 0 and live_len > 0:
            issues.append({
                'severity': 'CRITICAL',
                'section': section,
                'message': f'MISSING from stored data (live has {live_len} chars)',
                'live_len': live_len, 'stored_len': 0,
            })
            continue

        ratio = stored_len / live_len
        if ratio < RATIO_THRESHOLD:
            severity = 'CRITICAL' if ratio < 0.5 else 'WARNING'
            issues.append({
                'severity': severity,
                'section': section,
                'message': f'Stored ({stored_len}) is {ratio:.0%} of live ({live_len})',
                'live_len': live_len, 'stored_len': stored_len,
            })

    return issues


def apply_fix(conn, case_id, case_info, live_sections):
    """Update stored sections and sections_dual from live Drupal fields."""
    metadata = case_info['full_metadata']
    sections = metadata.get('sections', {})
    sections_dual = metadata.get('sections_dual', {})
    updated = []

    for section_name, live_entry in live_sections.items():
        live_text = live_entry['text']
        live_html = live_entry['html']
        stored_len = get_stored_len(case_info, section_name)
        live_len = len(live_text)

        # Update if live is substantially longer or stored is missing
        if stored_len == 0 or (live_len > 0 and stored_len / live_len < RATIO_THRESHOLD):
            old_len = stored_len
            # Update original sections
            sections[section_name] = live_text
            # Update sections_dual
            sections_dual[section_name] = {
                'text': live_text,
                'html': live_html,
            }
            updated.append(f"{section_name}: {old_len} -> {live_len}")

    if not updated:
        logger.info(f"  No updates needed for case {case_id}")
        return False

    metadata['sections'] = sections
    metadata['sections_dual'] = sections_dual

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE documents SET doc_metadata = %s WHERE id = %s
        """, (json.dumps(metadata), case_id))
    conn.commit()

    for u in updated:
        logger.info(f"  FIXED {u}")

    # Post revision entry to review log
    _post_review_log(case_id, updated)

    return True


def _post_review_log(case_id, updated_sections):
    """Post a revision entry to the review log API."""
    try:
        import requests as req
        payload = {
            'entry_type': 'revision',
            'entry_key': None,
            'status': 'INFO',
            'summary': f'Source sections updated: {", ".join(updated_sections)}',
            'author': 'validate-source-sections',
            'details': {'sections_updated': updated_sections},
        }
        resp = req.post(
            f'http://localhost:5000/api/provenance/case/{case_id}/review-log',
            json=payload, timeout=5)
        if resp.status_code == 201:
            logger.info(f"  Review log entry posted for case {case_id}")
        else:
            logger.warning(f"  Failed to post review log (HTTP {resp.status_code})")
    except Exception as e:
        logger.warning(f"  Could not post review log entry: {e}")


def validate_case(case_id, conn=None, verbose=True, fix=False):
    """Validate a single case. Returns (pass, issues, case_info, fixed)."""
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        case_info = fetch_case_info(conn, case_id)
        if not case_info:
            logger.error(f"Case {case_id} not found in database")
            return False, [{'severity': 'CRITICAL', 'section': '-',
                           'message': 'Case not found'}], None, False

        if not case_info['source_url']:
            logger.error(f"Case {case_id} has no source URL")
            return False, [{'severity': 'CRITICAL', 'section': '-',
                           'message': 'No source URL'}], case_info, False

        if verbose:
            logger.info(f"Case {case_id}: {case_info['title']}")
            logger.info(f"  Source: {case_info['source_url']}")

        try:
            live_sections, error = fetch_live_sections(case_info['source_url'])
        except requests.exceptions.RequestException as e:
            logger.error(f"  Failed to fetch: {e}")
            return False, [{'severity': 'CRITICAL', 'section': '-',
                           'message': f'Fetch failed: {e}'}], case_info, False

        if error:
            logger.error(f"  {error}")
            return False, [{'severity': 'CRITICAL', 'section': '-',
                           'message': error}], case_info, False

        if verbose:
            live_found = [s for s in SECTION_NAMES if s in live_sections]
            logger.info(f"  Drupal fields found: {live_found}")

        issues = compare_sections(case_info, live_sections)

        if verbose:
            if not issues:
                logger.info(f"  PASS")
            else:
                for issue in issues:
                    logger.info(f"  [{issue['severity']}] {issue['section']}: {issue['message']}")

            # Comparison table
            print(f"\n  {'Section':<12} {'Live':>8} {'Stored':>8} {'Ratio':>8} {'Status'}")
            print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
            for section in SECTION_NAMES:
                live_len = len(live_sections[section]['text']) if section in live_sections else 0
                stored_len = get_stored_len(case_info, section)
                ratio = f"{stored_len/live_len:.1%}" if live_len > 0 else '-'
                if live_len == 0 and stored_len == 0:
                    status = '-'
                elif stored_len == 0 and live_len > 0:
                    status = 'MISSING'
                elif live_len > 0 and stored_len / live_len < RATIO_THRESHOLD:
                    status = 'SHORT' if stored_len / live_len >= 0.5 else 'MISMATCH'
                else:
                    status = 'OK'
                print(f"  {section:<12} {live_len:>8} {stored_len:>8} {ratio:>8} {status}")
            print()

        fixed = False
        has_fixable = any(i['severity'] in ('CRITICAL', 'WARNING') for i in issues)
        if fix and has_fixable:
            fixed = apply_fix(conn, case_id, case_info, live_sections)

        passed = not any(i['severity'] == 'CRITICAL' for i in issues)
        return passed, issues, case_info, fixed

    finally:
        if close_conn:
            conn.close()


def get_queue_case_ids(conn, limit=None):
    """Get unextracted case IDs in the correct batch order."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT d.id
            FROM documents d
            LEFT JOIN (
                SELECT case_id, COUNT(*) as total
                FROM temporary_rdf_storage GROUP BY case_id
            ) e ON e.case_id = d.id
            WHERE d.world_id = 1
              AND d.document_type IN ('case_study', 'case')
              AND COALESCE(e.total, 0) = 0
              AND d.title != 'NSPE Code of Ethics for Engineers'
            ORDER BY (d.doc_metadata->>'year') DESC NULLS LAST,
                     d.doc_metadata->>'case_number' ASC
        """)
        rows = cur.fetchall()
        ids = [r[0] for r in rows]
        if limit:
            ids = ids[:limit]
        return ids


def main():
    parser = argparse.ArgumentParser(description='Validate case source sections against live NSPE Drupal fields')
    parser.add_argument('case_id', nargs='?', type=int, help='Case ID to validate')
    parser.add_argument('--fix', action='store_true', help='Update DB sections from live page when issues found')
    parser.add_argument('--batch', action='store_true', help='Validate next cases from queue')
    parser.add_argument('--limit', type=int, default=5, help='Number of cases for --batch (default 5)')
    parser.add_argument('--quiet', action='store_true', help='Only print failures')
    args = parser.parse_args()

    if not args.case_id and not args.batch:
        parser.print_help()
        sys.exit(1)

    conn = get_db_connection()
    try:
        if args.batch:
            case_ids = get_queue_case_ids(conn, limit=args.limit)
            logger.info(f"Validating {len(case_ids)} cases from queue\n")
            results = []
            for cid in case_ids:
                passed, issues, info, fixed = validate_case(
                    cid, conn, verbose=not args.quiet, fix=args.fix)
                results.append((cid, passed, issues, info, fixed))

            print("\n" + "=" * 60)
            print("BATCH VALIDATION SUMMARY")
            print("=" * 60)
            pass_count = sum(1 for _, p, _, _, _ in results if p)
            fail_count = len(results) - pass_count
            fix_count = sum(1 for _, _, _, _, f in results if f)
            for cid, passed, issues, info, fixed in results:
                status = "PASS" if passed else "FAIL"
                fix_tag = " [FIXED]" if fixed else ""
                title = info['title'][:45] if info else "?"
                critical = sum(1 for i in issues if i['severity'] == 'CRITICAL')
                warnings = sum(1 for i in issues if i['severity'] == 'WARNING')
                print(f"  Case {cid:>4} [{status}] {critical}C/{warnings}W{fix_tag}  {title}")
            print(f"\n  {pass_count} pass, {fail_count} fail, {fix_count} fixed out of {len(results)}")

            sys.exit(0 if fail_count == 0 else 1)
        else:
            passed, issues, info, fixed = validate_case(
                args.case_id, conn, fix=args.fix)
            if fixed:
                # Re-validate after fix
                print("Re-validating after fix...")
                passed, issues, info, _ = validate_case(args.case_id, conn, fix=False)
            if passed:
                print(f"PASS: Case {args.case_id} sections validated")
                sys.exit(0)
            else:
                print(f"FAIL: Case {args.case_id} has section issues")
                sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
