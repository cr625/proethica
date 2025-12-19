#!/usr/bin/env python3
"""
Backfill Cited Cases Script

Extracts case citations from existing documents and stores them in:
1. document.doc_metadata['cited_cases'] - for reference during ingestion
2. case_precedent_features.cited_case_numbers - for precedent discovery

Usage:
    python scripts/backfill_cited_cases.py [--dry-run] [--case-id CASE_ID]

Options:
    --dry-run   Preview changes without writing to database
    --case-id   Process only a specific case ID
"""

import os
import re
import sys
import argparse
import logging
from typing import List, Dict, Optional, Tuple

# Setup path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def extract_cited_cases(text: str, exclude_case_number: Optional[str] = None) -> List[str]:
    """
    Extract case citations from text.

    Patterns matched:
    - Case 92-1
    - BER Case 88-4
    - Case No. 2010-1
    - Cases 85-1, 85-2

    Args:
        text: Text to search
        exclude_case_number: Case number to exclude (the case itself)

    Returns:
        List of unique case references (e.g., ['Case 92-1', 'Case 88-4'])
    """
    # Pattern to match case references
    pattern = r'(?:BER\s+)?(?:Case(?:\s+No\.)?\s+)(\d{2,4}-\d+(?:-\d+)?)'

    matches = re.finditer(pattern, text, re.IGNORECASE)

    cited_cases = []
    for match in matches:
        case_num = match.group(1)
        case_ref = f"Case {case_num}"

        # Exclude self-references
        if exclude_case_number and case_num == exclude_case_number:
            continue

        if case_ref not in cited_cases:
            cited_cases.append(case_ref)

    return cited_cases


def extract_case_number_from_title(title: str) -> Optional[str]:
    """Extract case number from document title."""
    match = re.search(r'Case\s+(\d{2,4}-\d+)', title, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def get_all_document_text(doc) -> str:
    """Combine all text content from a document for searching."""
    parts = []

    # Main content
    if doc.content:
        parts.append(doc.content)

    # Sections from metadata
    if doc.doc_metadata:
        # sections_dual format
        if 'sections_dual' in doc.doc_metadata:
            for section_name, section_data in doc.doc_metadata['sections_dual'].items():
                if isinstance(section_data, dict) and 'text' in section_data:
                    parts.append(section_data['text'])
                elif isinstance(section_data, str):
                    parts.append(section_data)

        # sections format
        if 'sections' in doc.doc_metadata:
            sections = doc.doc_metadata['sections']
            if isinstance(sections, dict):
                for section_data in sections.values():
                    if isinstance(section_data, str):
                        parts.append(section_data)
                    elif isinstance(section_data, dict):
                        for val in section_data.values():
                            if isinstance(val, str):
                                parts.append(val)

    return ' '.join(parts)


def resolve_case_ids(cited_cases: List[str], db_session) -> List[Tuple[str, Optional[int]]]:
    """
    Try to resolve case references to document IDs.

    Returns:
        List of (case_ref, document_id or None)
    """
    from sqlalchemy import text

    resolved = []
    for case_ref in cited_cases:
        # Extract the case number
        match = re.search(r'(\d{2,4}-\d+)', case_ref)
        if not match:
            resolved.append((case_ref, None))
            continue

        case_num = match.group(1)

        # Try to find in database
        query = text("""
            SELECT id FROM documents
            WHERE title ~* :pattern
               OR doc_metadata->>'case_number' = :case_num
            LIMIT 1
        """)
        result = db_session.execute(query, {
            'pattern': f'Case\\s+{case_num}',
            'case_num': case_num
        }).fetchone()

        if result:
            resolved.append((case_ref, result[0]))
        else:
            resolved.append((case_ref, None))

    return resolved


def backfill_document(doc, db_session, dry_run: bool = False) -> Dict:
    """
    Backfill cited cases for a single document.

    Returns:
        Dict with results
    """
    from app.models.case_precedent_features import CasePrecedentFeatures

    # Get all text content
    full_text = get_all_document_text(doc)

    # Extract the document's own case number
    own_case_number = None
    if doc.doc_metadata and 'case_number' in doc.doc_metadata:
        own_case_number = doc.doc_metadata['case_number']
    if not own_case_number:
        own_case_number = extract_case_number_from_title(doc.title)

    # Extract cited cases
    cited_cases = extract_cited_cases(full_text, own_case_number)

    if not cited_cases:
        return {
            'case_id': doc.id,
            'title': doc.title,
            'cited_cases_found': 0,
            'cited_cases': [],
            'resolved_ids': [],
            'updated': False
        }

    # Resolve case IDs
    resolved = resolve_case_ids(cited_cases, db_session)
    resolved_ids = [r[1] for r in resolved if r[1] is not None]

    result = {
        'case_id': doc.id,
        'title': doc.title,
        'cited_cases_found': len(cited_cases),
        'cited_cases': cited_cases,
        'resolved_ids': resolved_ids,
        'updated': False
    }

    if dry_run:
        return result

    # Update document metadata
    if doc.doc_metadata is None:
        doc.doc_metadata = {}

    # Store cited cases in metadata
    doc.doc_metadata = {**doc.doc_metadata, 'cited_cases': cited_cases}

    # Update case_precedent_features
    features = CasePrecedentFeatures.query.filter_by(case_id=doc.id).first()
    if not features:
        features = CasePrecedentFeatures(case_id=doc.id)
        db_session.add(features)

    features.cited_case_numbers = cited_cases
    features.cited_case_ids = resolved_ids if resolved_ids else None

    db_session.commit()
    result['updated'] = True

    return result


def main():
    parser = argparse.ArgumentParser(description='Backfill cited cases for documents')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing')
    parser.add_argument('--case-id', type=int, help='Process only specific case ID')
    args = parser.parse_args()

    # Setup Flask app context
    os.environ.setdefault('FLASK_APP', 'run.py')
    os.environ.setdefault('FLASK_ENV', 'development')

    from app import create_app, db
    from app.models import Document

    app = create_app()

    with app.app_context():
        logger.info("=" * 60)
        logger.info("CITED CASES BACKFILL SCRIPT")
        logger.info(f"Dry run: {args.dry_run}")
        logger.info("=" * 60)

        # Get documents to process
        if args.case_id:
            docs = Document.query.filter_by(id=args.case_id).all()
        else:
            docs = Document.query.all()

        logger.info(f"Processing {len(docs)} documents...")

        total_citations = 0
        docs_with_citations = 0
        results = []

        for doc in docs:
            result = backfill_document(doc, db.session, args.dry_run)
            results.append(result)

            if result['cited_cases_found'] > 0:
                docs_with_citations += 1
                total_citations += result['cited_cases_found']
                logger.info(
                    f"[{doc.id}] {doc.title[:50]}... - "
                    f"Found {result['cited_cases_found']} citations: {result['cited_cases']}"
                )
                if result['resolved_ids']:
                    logger.info(f"    Resolved IDs: {result['resolved_ids']}")

        # Summary
        logger.info("=" * 60)
        logger.info("SUMMARY")
        logger.info(f"Documents processed: {len(docs)}")
        logger.info(f"Documents with citations: {docs_with_citations}")
        logger.info(f"Total citations found: {total_citations}")

        if args.dry_run:
            logger.info("\nDRY RUN - No changes made to database")
        else:
            logger.info("\nDatabase updated successfully")


if __name__ == '__main__':
    main()
