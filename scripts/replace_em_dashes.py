"""
Replace em dashes in LLM-generated analysis data.

Applies heuristic rules to replace em dashes (U+2014) with appropriate
punctuation (commas, periods, colons) based on context.

Usage:
    # Preview changes for Case 7
    python scripts/replace_em_dashes.py --case-id 7 --preview

    # Apply changes for Case 7
    python scripts/replace_em_dashes.py --case-id 7 --apply

    # Apply to all cases
    python scripts/replace_em_dashes.py --all --apply
"""

import argparse
import json
import re
import sys
import psycopg2


EM_DASH = '\u2014'

# Conjunctions/transitions that follow em dashes naturally with a comma
COMMA_BEFORE = {
    'but', 'however', 'yet', 'though', 'although', 'rather',
    'while', 'whereas', 'nevertheless', 'nonetheless', 'still',
    'instead', 'and', 'or', 'nor', 'so', 'which', 'who', 'that',
    'particularly', 'especially', 'notably', 'specifically',
    'meaning', 'suggesting', 'indicating', 'including',
}


def replace_em_dashes(text):
    """Replace em dashes with contextually appropriate punctuation."""
    if EM_DASH not in text:
        return text

    # 1. Paired em dashes -> commas (parenthetical insertion)
    # Match: "word — some parenthetical — word"
    text = re.sub(
        r'(\S) ' + EM_DASH + r' ([^' + EM_DASH + r']{3,80}?) ' + EM_DASH + r' ',
        r'\1, \2, ',
        text
    )

    # 2. Handle remaining single em dashes
    def replace_single(match):
        before = match.group(1)  # char before space-emdash
        after_text = match.group(2)  # text after emdash-space

        if not after_text:
            return before + '. '

        first_word = after_text.split()[0].rstrip('.,;:') if after_text.split() else ''
        first_char = after_text[0]

        # Before conjunction/transition word -> comma
        if first_word.lower() in COMMA_BEFORE:
            return before + ', ' + after_text

        # After a colon-like setup (ends with pattern suggesting a list follows)
        # e.g., "three factors — competence, disclosure..."
        if first_char.islower() and ',' in after_text[:80]:
            return before + ': ' + after_text

        # Uppercase start -> likely a new sentence
        if first_char.isupper():
            # But check if it's a proper noun mid-sentence
            # Heuristic: if text before ends with a verb-like word, it's probably
            # a new clause. If it ends with a preposition or article, probably not.
            before_words = before.rstrip('.,;:').split()
            before_word = before_words[-1].lower() if before_words else ''
            not_sentence_break = before_word in {
                'the', 'a', 'an', 'of', 'in', 'by', 'for', 'to', 'from',
                'with', 'as', 'at', 'on', 'and', 'or', 'nor',
            }
            if not_sentence_break:
                return before + ', ' + after_text
            else:
                # Check if 'before' already ends with period
                if before.rstrip().endswith('.'):
                    return before + ' ' + after_text
                return before + '. ' + after_text

        # Lowercase start -> comma (elaboration/continuation)
        return before + ', ' + after_text

    # Match: "text — text" with space around em dash
    text = re.sub(
        r'(\S) ' + EM_DASH + r' (\S[^' + EM_DASH + r']*?)(?= ' + EM_DASH + r' |\Z|$)',
        replace_single,
        text
    )

    # Match: "text— text" or "text —text" (no space on one side)
    text = re.sub(
        r'(\S)' + EM_DASH + r' (\S)',
        lambda m: replace_single(m),
        text
    )
    text = re.sub(
        r'(\S) ' + EM_DASH + r'(\S)',
        lambda m: m.group(1) + ', ' + m.group(2),
        text
    )

    # Catch any remaining bare em dashes
    text = text.replace(' ' + EM_DASH + ' ', ', ')
    text = text.replace(EM_DASH, ', ')

    # Clean up double spaces
    text = re.sub(r'  +', ' ', text)
    # Clean up ", ." -> "."
    text = text.replace(', .', '.')

    return text


def process_json_value(value):
    """Recursively process JSON values, replacing em dashes in strings."""
    if isinstance(value, str):
        return replace_em_dashes(value)
    elif isinstance(value, list):
        return [process_json_value(item) for item in value]
    elif isinstance(value, dict):
        return {k: process_json_value(v) for k, v in value.items()}
    return value


def get_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='ai_ethical_dm',
        user='postgres',
        password='PASS'
    )


def run(case_id=None, preview=True):
    conn = get_connection()
    cur = conn.cursor()

    where = "WHERE rdf_json_ld::text LIKE '%%\\u2014%%'"
    params = {}
    if case_id:
        where += " AND case_id = %(case_id)s"
        params['case_id'] = case_id

    cur.execute(
        f"SELECT id, case_id, extraction_type, entity_label, rdf_json_ld "
        f"FROM temporary_rdf_storage {where} "
        f"ORDER BY case_id, extraction_type, id",
        params
    )
    rows = cur.fetchall()
    print(f"Found {len(rows)} rows with em dashes"
          + (f" for case {case_id}" if case_id else " across all cases"))

    changes = []
    sample_count = 0
    MAX_SAMPLES = 30

    for row_id, c_id, ext_type, label, rdf_data in rows:
        if rdf_data is None:
            continue

        original_json = json.dumps(rdf_data, ensure_ascii=False)
        if EM_DASH not in original_json:
            continue

        new_data = process_json_value(rdf_data)
        new_json = json.dumps(new_data, ensure_ascii=False)

        if original_json != new_json:
            changes.append((row_id, new_data))

            if preview and sample_count < MAX_SAMPLES:
                # Show diffs for individual string fields
                _show_field_diffs(rdf_data, new_data, ext_type, label, row_id)
                sample_count += 1

    print(f"\n{'=' * 60}")
    print(f"Total rows to update: {len(changes)}")

    if not preview and changes:
        print("Applying changes...")
        for row_id, new_data in changes:
            cur.execute(
                "UPDATE temporary_rdf_storage SET rdf_json_ld = %s WHERE id = %s",
                (json.dumps(new_data), row_id)
            )
        conn.commit()
        print(f"Updated {len(changes)} rows.")
    elif preview and changes:
        print("(preview mode, no changes written. Use --apply to write.)")

    cur.close()
    conn.close()


def _show_field_diffs(old, new, ext_type, label, row_id):
    """Show before/after for changed string fields."""
    diffs = _collect_diffs(old, new, prefix='')
    if not diffs:
        return

    print(f"\n--- [{ext_type}] {label[:60]} (id={row_id}) ---")
    for path, old_val, new_val in diffs[:4]:
        field = path or '(root)'
        # Show just the part around the em dash
        print(f"  {field}:")
        print(f"    BEFORE: ...{_excerpt(old_val)}...")
        print(f"    AFTER:  ...{_excerpt(new_val)}...")


def _collect_diffs(old, new, prefix=''):
    """Collect (path, old_str, new_str) tuples for changed string fields."""
    diffs = []
    if isinstance(old, str) and isinstance(new, str):
        if old != new:
            diffs.append((prefix, old, new))
    elif isinstance(old, dict) and isinstance(new, dict):
        for k in old:
            if k in new:
                diffs.extend(_collect_diffs(old[k], new[k], f"{prefix}.{k}" if prefix else k))
    elif isinstance(old, list) and isinstance(new, list):
        for i, (o, n) in enumerate(zip(old, new)):
            diffs.extend(_collect_diffs(o, n, f"{prefix}[{i}]"))
    return diffs


def _excerpt(text, width=120):
    """Extract a short excerpt around the first em dash or change point."""
    idx = text.find(EM_DASH)
    if idx == -1:
        # Show middle of text
        idx = len(text) // 2
    start = max(0, idx - width // 2)
    end = min(len(text), idx + width // 2)
    return text[start:end]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Replace em dashes in analysis data')
    parser.add_argument('--case-id', type=int, help='Process only this case')
    parser.add_argument('--all', action='store_true', help='Process all cases')
    parser.add_argument('--preview', action='store_true', help='Preview changes (default)')
    parser.add_argument('--apply', action='store_true', help='Apply changes to database')

    args = parser.parse_args()

    if not args.case_id and not args.all:
        print("Specify --case-id N or --all")
        sys.exit(1)

    preview = not args.apply
    run(case_id=args.case_id, preview=preview)
