#!/usr/bin/env python3
"""
Publish Guideline Provisions to OntServe

This script reads provisions from ProEthica's guideline_sections table and
publishes them to OntServe as CodeProvision entities.

Usage:
    cd proethica
    source venv-proethica/bin/activate
    python scripts/publish_provisions_to_ontserve.py [--dry-run] [--guideline-id N]
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
from uuid import uuid4

import psycopg2
from psycopg2.extras import RealDictCursor, Json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection configurations
PROETHICA_DB = {
    'dbname': 'ai_ethical_dm',
    'user': 'postgres',
    'password': 'PASS',
    'host': 'localhost',
    'port': 5432
}

ONTSERVE_DB = {
    'dbname': 'ontserve',
    'user': 'postgres',
    'password': 'PASS',
    'host': 'localhost',
    'port': 5432
}

# Guideline to domain mapping
GUIDELINE_DOMAIN_MAP = {
    'NSPE': 'engineering-ethics',
    'NEA': 'education-ethics',
    'ACM': 'computing-ethics',
}

# URI generation
BASE_URI = "http://proethica.org/ontology"


def generate_provision_uri(guideline_code: str, provision_code: str) -> str:
    """Generate a URI for a provision."""
    # Normalize: II.1.c -> II_1_c
    normalized_code = provision_code.replace('.', '_').replace(' ', '_')
    guideline_slug = guideline_code.upper().replace(' ', '_')
    return f"{BASE_URI}/provisions#{guideline_slug}_{normalized_code}"


def generate_guideline_uri(guideline_title: str) -> str:
    """Generate a URI for a guideline."""
    slug = guideline_title.replace(' ', '_').replace('-', '_')
    return f"{BASE_URI}/guidelines#{slug}"


def get_proethica_provisions(conn, guideline_id: Optional[int] = None) -> List[Dict]:
    """Fetch provisions from ProEthica database."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        query = """
            SELECT
                gs.id,
                gs.guideline_id,
                gs.section_code,
                gs.section_title,
                gs.section_text,
                gs.section_category,
                gs.section_subcategory,
                gs.section_order,
                gs.section_metadata,
                g.title as guideline_title,
                g.source_url as guideline_source
            FROM guideline_sections gs
            JOIN guidelines g ON gs.guideline_id = g.id
        """
        params = []

        if guideline_id:
            query += " WHERE gs.guideline_id = %s"
            params.append(guideline_id)

        query += " ORDER BY gs.guideline_id, gs.section_order, gs.section_code"

        cur.execute(query, params)
        return cur.fetchall()


def get_or_create_domain(conn, domain_name: str) -> int:
    """Get or create a domain in OntServe."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check if exists
        cur.execute("SELECT id FROM domains WHERE name = %s", (domain_name,))
        result = cur.fetchone()

        if result:
            return result['id']

        # Create domain
        namespace_uri = f"{BASE_URI}/{domain_name.replace('-', '/')}#"
        cur.execute("""
            INSERT INTO domains (uuid, name, display_name, namespace_uri, description, is_active)
            VALUES (%s, %s, %s, %s, %s, true)
            RETURNING id
        """, (
            str(uuid4()),
            domain_name,
            domain_name.replace('-', ' ').title(),
            namespace_uri,
            f"Professional ethics domain for {domain_name}"
        ))
        conn.commit()
        return cur.fetchone()['id']


def provision_exists(conn, uri: str) -> bool:
    """Check if a provision already exists in OntServe."""
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM concepts WHERE uri = %s", (uri,))
        return cur.fetchone() is not None


def publish_provision(conn, provision: Dict, domain_id: int, dry_run: bool = False) -> Optional[int]:
    """Publish a single provision to OntServe."""

    # Determine guideline code from title
    guideline_title = provision['guideline_title']
    if 'NSPE' in guideline_title.upper():
        guideline_code = 'NSPE'
    elif 'NEA' in guideline_title.upper():
        guideline_code = 'NEA'
    elif 'ACM' in guideline_title.upper():
        guideline_code = 'ACM'
    else:
        guideline_code = guideline_title.split()[0].upper()

    uri = generate_provision_uri(guideline_code, provision['section_code'])

    # Check if already exists
    if provision_exists(conn, uri):
        logger.info(f"  Provision already exists: {provision['section_code']}")
        return None

    # Build label
    label = f"{provision['section_code']} (Provision)"
    semantic_label = provision['section_title'] or provision['section_code']

    # Extract establishes concepts from metadata
    metadata = provision.get('section_metadata') or {}
    establishes = metadata.get('establishes', [])

    # Build rich metadata
    concept_metadata = {
        'provision_code': provision['section_code'],
        'provision_category': provision['section_category'],
        'provision_subcategory': provision['section_subcategory'],
        'guideline_id': provision['guideline_id'],
        'guideline_title': guideline_title,
        'guideline_source': provision['guideline_source'],
        'proethica_section_id': provision['id'],
        'establishes': establishes,
        'published_at': datetime.now().isoformat()
    }

    if dry_run:
        logger.info(f"  [DRY RUN] Would publish: {label}")
        logger.info(f"    URI: {uri}")
        logger.info(f"    Category: {provision['section_category']}")
        if establishes:
            logger.info(f"    Establishes: {[e.get('label') for e in establishes]}")
        return None

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            INSERT INTO concepts (
                uuid, domain_id, uri, label, semantic_label, primary_type,
                description, status, confidence_score, extraction_method,
                source_document, created_by, metadata
            )
            VALUES (%s, %s, %s, %s, %s, 'Provision', %s, 'approved', 1.0,
                    'guideline_extraction', %s, 'provision_publisher', %s)
            RETURNING id
        """, (
            str(uuid4()),
            domain_id,
            uri,
            label,
            semantic_label,
            provision['section_text'],  # description = full text
            f"guideline:{provision['guideline_id']}",
            Json(concept_metadata)
        ))
        conn.commit()
        return cur.fetchone()['id']


def publish_guideline(conn, guideline_title: str, domain_id: int, dry_run: bool = False) -> Optional[int]:
    """Publish a guideline entity to OntServe."""
    uri = generate_guideline_uri(guideline_title)

    # Check if already exists
    if provision_exists(conn, uri):
        logger.info(f"  Guideline already exists: {guideline_title}")
        return None

    label = f"{guideline_title} (Guideline)"

    if dry_run:
        logger.info(f"  [DRY RUN] Would publish guideline: {label}")
        return None

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            INSERT INTO concepts (
                uuid, domain_id, uri, label, semantic_label, primary_type,
                description, status, confidence_score, extraction_method,
                created_by, metadata
            )
            VALUES (%s, %s, %s, %s, %s, 'Guideline', %s, 'approved', 1.0,
                    'guideline_upload', 'provision_publisher', %s)
            RETURNING id
        """, (
            str(uuid4()),
            domain_id,
            uri,
            label,
            guideline_title,
            f"Professional code of ethics: {guideline_title}",
            Json({'type': 'guideline', 'published_at': datetime.now().isoformat()})
        ))
        conn.commit()
        return cur.fetchone()['id']


def main():
    parser = argparse.ArgumentParser(description='Publish provisions to OntServe')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without making changes')
    parser.add_argument('--guideline-id', type=int,
                        help='Only process specific guideline ID')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("=" * 60)
    logger.info("Publishing Guideline Provisions to OntServe")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    # Connect to databases
    try:
        proethica_conn = psycopg2.connect(**PROETHICA_DB)
        logger.info(f"Connected to ProEthica database: {PROETHICA_DB['dbname']}")
    except Exception as e:
        logger.error(f"Failed to connect to ProEthica database: {e}")
        sys.exit(1)

    try:
        ontserve_conn = psycopg2.connect(**ONTSERVE_DB)
        logger.info(f"Connected to OntServe database: {ONTSERVE_DB['dbname']}")
    except Exception as e:
        logger.error(f"Failed to connect to OntServe database: {e}")
        proethica_conn.close()
        sys.exit(1)

    try:
        # Fetch provisions
        provisions = get_proethica_provisions(proethica_conn, args.guideline_id)
        logger.info(f"\nFound {len(provisions)} provisions to process")

        if not provisions:
            logger.warning("No provisions found!")
            return

        # Group by guideline
        guidelines = {}
        for p in provisions:
            gid = p['guideline_id']
            if gid not in guidelines:
                guidelines[gid] = {
                    'title': p['guideline_title'],
                    'source': p['guideline_source'],
                    'provisions': []
                }
            guidelines[gid]['provisions'].append(p)

        # Process each guideline
        stats = {'guidelines': 0, 'provisions': 0, 'skipped': 0}

        for gid, gdata in guidelines.items():
            logger.info(f"\n--- Processing: {gdata['title']} ---")
            logger.info(f"    Provisions: {len(gdata['provisions'])}")

            # Determine domain
            title_upper = gdata['title'].upper()
            if 'NSPE' in title_upper:
                domain_name = 'engineering-ethics'
            elif 'NEA' in title_upper:
                domain_name = 'education-ethics'
            elif 'ACM' in title_upper:
                domain_name = 'computing-ethics'
            else:
                domain_name = 'general-ethics'

            # Get/create domain
            domain_id = get_or_create_domain(ontserve_conn, domain_name)
            logger.info(f"    Domain: {domain_name} (id={domain_id})")

            # Publish guideline
            if publish_guideline(ontserve_conn, gdata['title'], domain_id, args.dry_run):
                stats['guidelines'] += 1

            # Publish provisions
            for provision in gdata['provisions']:
                result = publish_provision(ontserve_conn, provision, domain_id, args.dry_run)
                if result:
                    stats['provisions'] += 1
                else:
                    stats['skipped'] += 1

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Guidelines processed: {len(guidelines)}")
        logger.info(f"Guidelines published: {stats['guidelines']}")
        logger.info(f"Provisions published: {stats['provisions']}")
        logger.info(f"Provisions skipped (already exist): {stats['skipped']}")

        if args.dry_run:
            logger.info("\nThis was a DRY RUN - no changes were made")

    finally:
        proethica_conn.close()
        ontserve_conn.close()
        logger.info("\nDatabase connections closed")


if __name__ == '__main__':
    main()
