#!/usr/bin/env python3
"""
Create Provision-Concept Linkage Triples in OntServe

This script reads the "establishes" metadata from provisions and creates
RDF triples linking provisions to the concepts they establish.

This enables SPARQL queries like:
  SELECT ?provision ?concept WHERE {
    ?provision proeth-core:establishes ?concept .
  }

Usage:
    cd proethica
    source venv-proethica/bin/activate
    python scripts/create_provision_linkage_triples.py [--dry-run]
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

# Database connection
ONTSERVE_DB = {
    'dbname': 'ontserve',
    'user': 'postgres',
    'password': 'PASS',
    'host': 'localhost',
    'port': 5432
}

# URIs
BASE_URI = "http://proethica.org/ontology"
CORE_NS = f"{BASE_URI}/core#"
ESTABLISHES_PREDICATE = f"{CORE_NS}establishes"
PART_OF_GUIDELINE_PREDICATE = f"{CORE_NS}partOfGuideline"


def get_provisions_with_establishes(conn) -> List[Dict]:
    """Fetch provisions that have establishes metadata."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                id,
                uri,
                label,
                metadata
            FROM concepts
            WHERE primary_type = 'Provision'
            AND metadata->'establishes' IS NOT NULL
            AND jsonb_array_length(metadata->'establishes') > 0
            ORDER BY label
        """)
        return cur.fetchall()


def get_guideline_uri(conn) -> Optional[str]:
    """Get the NSPE guideline URI."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT uri FROM concepts
            WHERE primary_type = 'Guideline'
            AND label LIKE '%NSPE%'
            LIMIT 1
        """)
        result = cur.fetchone()
        return result['uri'] if result else None


def find_or_create_concept(conn, label: str, concept_type: str, domain_id: int = 1) -> str:
    """Find existing concept or create a new one, return its URI."""
    # Map type to primary_type
    type_map = {
        'principle': 'Principle',
        'obligation': 'Obligation',
        'constraint': 'Constraint'
    }
    primary_type = type_map.get(concept_type.lower(), 'Principle')

    # Generate URI
    slug = label.replace(' ', '_').replace('-', '_')
    uri = f"{BASE_URI}/concepts#{slug}"

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check if exists
        cur.execute("SELECT uri FROM concepts WHERE uri = %s", (uri,))
        result = cur.fetchone()
        if result:
            return result['uri']

        # Create new concept
        cur.execute("""
            INSERT INTO concepts (
                uuid, domain_id, uri, label, semantic_label, primary_type,
                description, status, confidence_score, extraction_method,
                source_document, created_by, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'approved', 1.0,
                    'provision_derivation', 'guideline_provisions', 'provision_linkage', %s)
            RETURNING uri
        """, (
            str(uuid4()),
            domain_id,
            uri,
            f"{label} ({primary_type})",
            label,
            primary_type,
            f"{primary_type} established by ethics code provisions",
            Json({'derived_from_provisions': True, 'created_at': datetime.now().isoformat()})
        ))
        conn.commit()
        return cur.fetchone()['uri']


def triple_exists(conn, subject: str, predicate: str, object_uri: str) -> bool:
    """Check if a triple already exists."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM concept_triples
            WHERE subject = %s AND predicate = %s AND object_uri = %s
        """, (subject, predicate, object_uri))
        return cur.fetchone() is not None


def create_triple(conn, subject: str, predicate: str, object_uri: str,
                  subject_label: str, predicate_label: str, object_label: str,
                  concept_id: int = None, dry_run: bool = False) -> bool:
    """Create a single triple."""

    if triple_exists(conn, subject, predicate, object_uri):
        logger.debug(f"  Triple already exists: {subject_label} -> {object_label}")
        return False

    if dry_run:
        logger.info(f"  [DRY RUN] Would create: {subject_label} --{predicate_label}--> {object_label}")
        return True

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO concept_triples (
                concept_id, subject, predicate, object_uri, is_literal,
                subject_label, predicate_label, object_label,
                entity_type, triple_metadata
            )
            VALUES (%s, %s, %s, %s, false, %s, %s, %s, 'provision_linkage', %s)
        """, (
            concept_id,
            subject,
            predicate,
            object_uri,
            subject_label,
            predicate_label,
            object_label,
            Json({'created_at': datetime.now().isoformat()})
        ))
        conn.commit()
        return True


def main():
    parser = argparse.ArgumentParser(description='Create provision linkage triples')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without making changes')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("=" * 60)
    logger.info("Creating Provision-Concept Linkage Triples")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    # Connect to database
    try:
        conn = psycopg2.connect(**ONTSERVE_DB)
        logger.info(f"Connected to OntServe database: {ONTSERVE_DB['dbname']}")
    except Exception as e:
        logger.error(f"Failed to connect to OntServe database: {e}")
        sys.exit(1)

    try:
        # Get guideline URI for partOfGuideline relationships
        guideline_uri = get_guideline_uri(conn)
        if guideline_uri:
            logger.info(f"Found guideline: {guideline_uri}")

        # Fetch provisions with establishes metadata
        provisions = get_provisions_with_establishes(conn)
        logger.info(f"\nFound {len(provisions)} provisions with 'establishes' metadata")

        if not provisions:
            logger.warning("No provisions found with 'establishes' metadata!")
            return

        # Statistics
        stats = {
            'provisions_processed': 0,
            'triples_created': 0,
            'triples_skipped': 0,
            'concepts_created': 0
        }

        # Process each provision
        for provision in provisions:
            metadata = provision['metadata']
            establishes = metadata.get('establishes', [])

            if not establishes:
                continue

            stats['provisions_processed'] += 1
            provision_uri = provision['uri']
            provision_label = provision['label'].replace(' (Provision)', '')

            logger.info(f"\nProcessing: {provision_label}")
            logger.info(f"  Establishes {len(establishes)} concepts")

            # Create partOfGuideline triple
            if guideline_uri and not args.dry_run:
                if create_triple(
                    conn,
                    provision_uri,
                    PART_OF_GUIDELINE_PREDICATE,
                    guideline_uri,
                    provision_label,
                    'partOfGuideline',
                    'NSPE Code of Ethics',
                    provision['id'],
                    args.dry_run
                ):
                    stats['triples_created'] += 1

            # Create establishes triples
            for concept in establishes:
                concept_label = concept.get('label', 'Unknown')
                concept_type = concept.get('type', 'principle')

                # Find or create the target concept
                concept_uri = find_or_create_concept(conn, concept_label, concept_type)

                # Check if we created a new concept
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT metadata->'derived_from_provisions' as derived
                        FROM concepts WHERE uri = %s
                    """, (concept_uri,))
                    result = cur.fetchone()
                    if result and result[0]:
                        stats['concepts_created'] += 1

                # Create the establishes triple
                if create_triple(
                    conn,
                    provision_uri,
                    ESTABLISHES_PREDICATE,
                    concept_uri,
                    provision_label,
                    'establishes',
                    concept_label,
                    provision['id'],
                    args.dry_run
                ):
                    stats['triples_created'] += 1
                else:
                    stats['triples_skipped'] += 1

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Provisions processed: {stats['provisions_processed']}")
        logger.info(f"Triples created: {stats['triples_created']}")
        logger.info(f"Triples skipped (already exist): {stats['triples_skipped']}")
        logger.info(f"New concepts created: {stats['concepts_created']}")

        if args.dry_run:
            logger.info("\nThis was a DRY RUN - no changes were made")

    finally:
        conn.close()
        logger.info("\nDatabase connection closed")


if __name__ == '__main__':
    main()
