#!/usr/bin/env python3
"""
Export Provisions to RDF/Turtle Format

Exports all provisions and their relationships from OntServe to
a Turtle (.ttl) file that can be loaded into any RDF store.

Usage:
    cd proethica
    source venv-proethica/bin/activate
    python scripts/export_provisions_to_rdf.py [--output FILE]
"""

import argparse
import logging
import sys
from datetime import datetime
from typing import Dict, List

import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

ONTSERVE_DB = {
    'dbname': 'ontserve',
    'user': 'postgres',
    'password': 'PASS',
    'host': 'localhost',
    'port': 5432
}

# Turtle prefixes
PREFIXES = """@prefix : <http://proethica.org/ontology/provisions#> .
@prefix proeth-core: <http://proethica.org/ontology/core#> .
@prefix proeth-concepts: <http://proethica.org/ontology/concepts#> .
@prefix proeth-guidelines: <http://proethica.org/ontology/guidelines#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dcterms: <http://purl.org/dc/terms/> .

"""

ONTOLOGY_HEADER = """
###############################################################
# ProEthica Provisions Ontology
# Exported: {date}
# Contains: {provision_count} provisions with {triple_count} relationships
###############################################################

<http://proethica.org/ontology/provisions> a owl:Ontology ;
    rdfs:label "ProEthica Guideline Provisions"@en ;
    dcterms:created "{date}"^^xsd:date ;
    rdfs:comment "Individual provisions from professional codes of ethics with their established concepts."@en ;
    owl:imports <http://proethica.org/ontology/core> .

"""


def escape_turtle_string(s: str) -> str:
    """Escape a string for Turtle format."""
    if not s:
        return ""
    return (s
            .replace('\\', '\\\\')
            .replace('"', '\\"')
            .replace('\n', '\\n')
            .replace('\r', '\\r')
            .replace('\t', '\\t'))


def get_uri_local_name(uri: str) -> str:
    """Extract local name from URI."""
    if '#' in uri:
        return uri.split('#')[-1]
    return uri.split('/')[-1]


def get_provisions(conn) -> List[Dict]:
    """Fetch all provisions."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                uri, label, semantic_label, description, metadata
            FROM concepts
            WHERE primary_type = 'Provision'
            ORDER BY label
        """)
        return cur.fetchall()


def get_guidelines(conn) -> List[Dict]:
    """Fetch all guidelines."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                uri, label, semantic_label, description
            FROM concepts
            WHERE primary_type = 'Guideline'
            ORDER BY label
        """)
        return cur.fetchall()


def get_established_concepts(conn) -> List[Dict]:
    """Fetch concepts established by provisions."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                uri, label, semantic_label, primary_type, description
            FROM concepts
            WHERE metadata->>'derived_from_provisions' = 'true'
            ORDER BY primary_type, label
        """)
        return cur.fetchall()


def get_triples(conn) -> List[Dict]:
    """Fetch all provision-related triples."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                subject, predicate, object_uri
            FROM concept_triples
            WHERE entity_type = 'provision_linkage'
            ORDER BY subject
        """)
        return cur.fetchall()


def export_to_turtle(conn, output_file: str):
    """Export all provisions and relationships to Turtle format."""

    provisions = get_provisions(conn)
    guidelines = get_guidelines(conn)
    established = get_established_concepts(conn)
    triples = get_triples(conn)

    logger.info(f"Exporting {len(provisions)} provisions")
    logger.info(f"Exporting {len(guidelines)} guidelines")
    logger.info(f"Exporting {len(established)} established concepts")
    logger.info(f"Exporting {len(triples)} relationship triples")

    with open(output_file, 'w', encoding='utf-8') as f:
        # Write prefixes
        f.write(PREFIXES)

        # Write ontology header
        f.write(ONTOLOGY_HEADER.format(
            date=datetime.now().strftime('%Y-%m-%d'),
            provision_count=len(provisions),
            triple_count=len(triples)
        ))

        # Write guidelines
        if guidelines:
            f.write("\n###############################################################\n")
            f.write("# Guidelines (Codes of Ethics)\n")
            f.write("###############################################################\n\n")

            for g in guidelines:
                local = get_uri_local_name(g['uri'])
                f.write(f"proeth-guidelines:{local} a proeth-core:Guideline ;\n")
                f.write(f'    rdfs:label "{escape_turtle_string(g["semantic_label"] or g["label"])}"@en ;\n')
                if g.get('description'):
                    f.write(f'    rdfs:comment "{escape_turtle_string(g["description"][:500])}"@en ;\n')
                f.write("    .\n\n")

        # Write provisions
        f.write("\n###############################################################\n")
        f.write("# Code Provisions\n")
        f.write("###############################################################\n\n")

        for p in provisions:
            local = get_uri_local_name(p['uri'])
            metadata = p.get('metadata') or {}
            category = metadata.get('provision_category', 'general')

            f.write(f":{local} a proeth-core:CodeProvision ;\n")
            f.write(f'    rdfs:label "{escape_turtle_string(p["semantic_label"] or p["label"])}"@en ;\n')
            f.write(f'    proeth-core:provisionCode "{escape_turtle_string(metadata.get("provision_code", local))}"^^xsd:string ;\n')
            f.write(f'    proeth-core:provisionCategory "{escape_turtle_string(category)}"^^xsd:string ;\n')

            if p.get('description'):
                # Truncate very long descriptions
                desc = p['description'][:1000]
                f.write(f'    proeth-core:provisionText "{escape_turtle_string(desc)}"@en ;\n')

            if metadata.get('guideline_title'):
                guideline_local = metadata['guideline_title'].replace(' ', '_').replace('-', '_')
                f.write(f'    proeth-core:partOfGuideline proeth-guidelines:{guideline_local} ;\n')

            f.write("    .\n\n")

        # Write established concepts
        f.write("\n###############################################################\n")
        f.write("# Established Concepts (Principles, Obligations, Constraints)\n")
        f.write("###############################################################\n\n")

        type_map = {
            'Principle': 'proeth-core:Principle',
            'Obligation': 'proeth-core:Obligation',
            'Constraint': 'proeth-core:Constraint'
        }

        for c in established:
            local = get_uri_local_name(c['uri'])
            owl_type = type_map.get(c['primary_type'], 'proeth-core:Principle')

            f.write(f"proeth-concepts:{local} a {owl_type} ;\n")
            f.write(f'    rdfs:label "{escape_turtle_string(c["semantic_label"] or c["label"])}"@en ;\n')
            if c.get('description'):
                f.write(f'    rdfs:comment "{escape_turtle_string(c["description"][:500])}"@en ;\n')
            f.write("    .\n\n")

        # Write relationship triples
        f.write("\n###############################################################\n")
        f.write("# Provision-Concept Relationships (establishes)\n")
        f.write("###############################################################\n\n")

        # Group triples by subject for cleaner output
        from collections import defaultdict
        triples_by_subject = defaultdict(list)
        for t in triples:
            if 'establishes' in t['predicate']:
                triples_by_subject[t['subject']].append(t['object_uri'])

        for subject_uri, objects in triples_by_subject.items():
            subject_local = get_uri_local_name(subject_uri)
            f.write(f":{subject_local}\n")
            for i, obj_uri in enumerate(objects):
                obj_local = get_uri_local_name(obj_uri)
                separator = ";" if i < len(objects) - 1 else "."
                f.write(f"    proeth-core:establishes proeth-concepts:{obj_local} {separator}\n")
            f.write("\n")

    logger.info(f"Exported to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Export provisions to RDF/Turtle')
    parser.add_argument('--output', '-o', default='provisions_export.ttl',
                        help='Output file path (default: provisions_export.ttl)')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Exporting Provisions to RDF/Turtle")
    logger.info("=" * 60)

    try:
        conn = psycopg2.connect(**ONTSERVE_DB)
        logger.info(f"Connected to OntServe database")
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        sys.exit(1)

    try:
        export_to_turtle(conn, args.output)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
