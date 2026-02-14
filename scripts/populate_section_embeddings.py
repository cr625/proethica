#!/usr/bin/env python3
"""
Populate section embeddings for cases missing document_sections rows.

Parses raw HTML from the documents table, extracts section text (facts,
discussion, conclusion, question, references), generates 384-dim embeddings
using the local SentenceTransformer model, and stores results in both
document_sections and case_precedent_features.

Usage:
    python scripts/populate_section_embeddings.py --cases 71,72
    python scripts/populate_section_embeddings.py --cases 71,72 --dry-run
"""

import argparse
import re
import sys
import os
from datetime import datetime
from html.parser import HTMLParser
from typing import Dict, List, Optional

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '/home/chris/onto')

from app import create_app
from app.models import Document, db
from app.models.document_section import DocumentSection
from sqlalchemy import text


class HTMLTextExtractor(HTMLParser):
    """Strip HTML tags and extract plain text."""

    def __init__(self):
        super().__init__()
        self.result = []
        self.skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = False
        if tag in ('p', 'div', 'br', 'h1', 'h2', 'h3', 'li'):
            self.result.append('\n')

    def handle_data(self, data):
        if not self.skip:
            self.result.append(data)

    def get_text(self):
        return ''.join(self.result).strip()


def html_to_text(html: str) -> str:
    """Convert HTML to plain text."""
    extractor = HTMLTextExtractor()
    extractor.feed(html)
    return extractor.get_text()


def parse_sections(html_content: str) -> Dict[str, str]:
    """
    Parse NSPE case HTML into named sections.

    Splits on <h2> tags to find Facts, Question, Discussion,
    Conclusion, References sections.
    """
    sections = {}

    # Split by h2 headers
    parts = re.split(r'<h2[^>]*>', html_content, flags=re.IGNORECASE)

    for part in parts[1:]:  # Skip content before first h2
        # Extract section name from the text before </h2>
        header_match = re.match(r'([^<]+)</h2>', part, re.IGNORECASE)
        if not header_match:
            continue

        section_name = header_match.group(1).strip().lower()
        section_content = part[header_match.end():]

        # Map variations to canonical names
        name_map = {
            'facts': 'facts',
            'question': 'question',
            'questions': 'question',
            'discussion': 'discussion',
            'conclusion': 'conclusion',
            'references': 'references',
            'dissenting opinion': 'dissenting_opinion',
        }

        canonical = name_map.get(section_name)
        if canonical:
            plain_text = html_to_text(section_content)
            if plain_text.strip():
                sections[canonical] = plain_text.strip()

    return sections


def get_local_model():
    """Get the SentenceTransformer model instance."""
    from app.services.embedding_service import EmbeddingService
    svc = EmbeddingService()
    if 'local' not in svc.providers or not svc.providers['local'].get('available'):
        raise RuntimeError("Local embedding provider not available")
    return svc.providers['local']['model']


def generate_embedding(model, text: str) -> Optional[np.ndarray]:
    """Generate L2-normalized 384-dim embedding."""
    if not text or not text.strip():
        return None

    emb = model.encode(text[:2000])  # Match truncation from other code paths
    if not isinstance(emb, np.ndarray):
        emb = np.array(emb)

    # L2 normalize
    norm = np.linalg.norm(emb)
    if norm > 0:
        emb = emb / norm

    return emb


def process_case(case_id: int, model, dry_run: bool = False) -> dict:
    """
    Parse sections and generate embeddings for a single case.

    Returns dict with status and details.
    """
    result = {
        'case_id': case_id,
        'success': False,
        'sections_found': [],
        'sections_embedded': [],
        'message': ''
    }

    # Get document
    doc = Document.query.get(case_id)
    if not doc or not doc.content:
        result['message'] = 'No document or content found'
        return result

    # Parse sections from HTML
    sections = parse_sections(doc.content)
    result['sections_found'] = list(sections.keys())

    if not sections:
        result['message'] = 'No sections parsed from HTML'
        return result

    # Check existing document_sections
    existing = DocumentSection.query.filter_by(document_id=case_id).count()
    if existing > 0:
        result['message'] = f'Already has {existing} document_sections rows'
        result['success'] = True
        return result

    if dry_run:
        result['success'] = True
        result['message'] = f'Would create {len(sections)} sections: {list(sections.keys())}'
        return result

    # Generate embeddings and create document_sections rows
    embeddings = {}
    for section_type, text_content in sections.items():
        emb = generate_embedding(model, text_content)

        # Create document_sections row
        ds = DocumentSection(
            document_id=case_id,
            section_id=section_type,
            section_type=section_type,
            position=['facts', 'question', 'discussion', 'conclusion', 'references',
                      'dissenting_opinion'].index(section_type)
                     if section_type in ['facts', 'question', 'discussion', 'conclusion',
                                         'references', 'dissenting_opinion'] else 99,
            content=text_content,
        )

        if emb is not None:
            ds.embedding = emb.tolist()
            embeddings[section_type] = emb
            result['sections_embedded'].append(section_type)

        db.session.add(ds)

    db.session.flush()

    # Update case_precedent_features with facts and discussion embeddings
    facts_emb = embeddings.get('facts')
    disc_emb = embeddings.get('discussion')

    update_parts = []
    params = {'case_id': case_id}

    if facts_emb is not None:
        update_parts.append('facts_embedding = :facts_emb')
        params['facts_emb'] = facts_emb.tolist()

    if disc_emb is not None:
        update_parts.append('discussion_embedding = :disc_emb')
        params['disc_emb'] = disc_emb.tolist()

    conclusion_emb = embeddings.get('conclusion')
    if conclusion_emb is not None:
        update_parts.append('conclusion_embedding = :conc_emb')
        params['conc_emb'] = conclusion_emb.tolist()

    if update_parts:
        query = text(f"""
            UPDATE case_precedent_features
            SET {', '.join(update_parts)}
            WHERE case_id = :case_id
        """)
        db.session.execute(query, params)

    db.session.commit()

    result['success'] = True
    result['message'] = (
        f'Created {len(sections)} document_sections, '
        f'embedded {len(result["sections_embedded"])} sections'
    )
    return result


def main():
    parser = argparse.ArgumentParser(
        description='Populate section embeddings for cases missing document_sections'
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--cases', type=str,
                       help='Comma-separated list of case IDs')
    group.add_argument('--all', action='store_true',
                       help='Process all cases missing document_sections')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without saving')

    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.all:
            rows = db.session.execute(text("""
                SELECT d.id FROM documents d
                WHERE d.content IS NOT NULL
                  AND LENGTH(d.content) > 100
                  AND NOT EXISTS (
                      SELECT 1 FROM document_sections ds
                      WHERE ds.document_id = d.id
                  )
                ORDER BY d.id
            """)).fetchall()
            case_ids = [r[0] for r in rows]
        else:
            case_ids = [int(c.strip()) for c in args.cases.split(',')]
        print("Loading embedding model...")
        model = get_local_model()

        print(f"\nSection Embedding Population")
        print(f"{'='*60}")
        print(f"Cases: {case_ids}")
        print(f"Dry run: {args.dry_run}")
        print()

        for case_id in case_ids:
            print(f"Case {case_id}:")
            result = process_case(case_id, model, dry_run=args.dry_run)

            print(f"  Sections found: {result['sections_found']}")
            if result['sections_embedded']:
                print(f"  Sections embedded: {result['sections_embedded']}")
            status = "OK" if result['success'] else "FAIL"
            print(f"  [{status}] {result['message']}")
            print()

        # Verify
        if not args.dry_run:
            print(f"{'='*60}")
            print("Verification:")
            for case_id in case_ids:
                ds_count = DocumentSection.query.filter_by(document_id=case_id).count()
                cpf = db.session.execute(text("""
                    SELECT facts_embedding IS NOT NULL as has_facts,
                           discussion_embedding IS NOT NULL as has_disc
                    FROM case_precedent_features WHERE case_id = :cid
                """), {'cid': case_id}).fetchone()

                print(f"  Case {case_id}: {ds_count} document_sections, "
                      f"facts_emb={cpf[0] if cpf else 'N/A'}, "
                      f"disc_emb={cpf[1] if cpf else 'N/A'}")


if __name__ == '__main__':
    main()
