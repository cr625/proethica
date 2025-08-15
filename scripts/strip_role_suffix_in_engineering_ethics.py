#!/usr/bin/env python3
"""
Strip trailing 'Role'/'Roles' from rdfs:label for Role classes in the
engineering-ethics ontology while keeping URIs unchanged.

Usage:
  python scripts/strip_role_suffix_in_engineering_ethics.py [--dry-run]

Notes:
- Only updates labels of classes typed as proethica:Role or subclasses of it.
- Writes a new OntologyVersion unless --dry-run is used.
"""
from __future__ import annotations

import sys
from rdflib import Graph, Namespace, RDF, RDFS, Literal

from app import create_app, db
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion
from app.utils.label_normalization import strip_role_suffix


def process(graph: Graph) -> int:
    proeth = Namespace("http://proethica.org/ontology/intermediate#")
    changed = 0

    # Collect role-like classes: typed as Role or subclasses of Role
    role_nodes = set(graph.subjects(RDF.type, proeth.Role))
    role_nodes.update(graph.subjects(RDFS.subClassOf, proeth.Role))

    for s in list(role_nodes):
        labels = list(graph.objects(s, RDFS.label))
        for lbl in labels:
            if not isinstance(lbl, Literal):
                continue
            text = str(lbl)
            stripped = strip_role_suffix(text)
            if stripped != text:
                graph.remove((s, RDFS.label, lbl))
                graph.add((s, RDFS.label, Literal(stripped, lang=lbl.language) if lbl.language else Literal(stripped)))
                changed += 1
    return changed


def main():
    dry = '--dry-run' in sys.argv
    app = create_app('config')
    with app.app_context():
        ont = Ontology.query.filter_by(domain_id='engineering-ethics').first()
        if not ont:
            print("engineering-ethics ontology not found")
            sys.exit(1)

        g = Graph()
        g.parse(data=ont.content, format='turtle')
        before = len(g)
        changed = process(g)
        after = len(g)

        print(f"Triples: {before} -> {after}. Labels changed: {changed}")
        if changed == 0:
            return

        new_content = g.serialize(format='turtle')
        if dry:
            print("--dry-run: not writing changes")
            return

        # Persist changes and version
        ont.content = new_content
        version = OntologyVersion(
            ontology_id=ont.id,
            content=new_content,
            version_number=(OntologyVersion.query.filter_by(ontology_id=ont.id)
                            .order_by(OntologyVersion.version_number.desc())
                            .first().version_number + 1 if OntologyVersion.query.filter_by(ontology_id=ont.id).count() else 1),
            commit_message="Strip 'Role' suffix from labels for Role classes"
        )
        db.session.add(version)
        db.session.commit()
        print("Saved changes and created new OntologyVersion.")


if __name__ == '__main__':
    main()
