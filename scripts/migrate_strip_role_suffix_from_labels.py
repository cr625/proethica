#!/usr/bin/env python3
"""
One-off migration: strip the "Role" suffix from Role labels in a target ontology
(e.g., engineering-ethics), keeping URIs as-is. This updates:
- Ontology TTL content for rdfs:label on Role classes
- Role rows in the relational DB where ontology_uri points to a Role class

Usage:
  python3 scripts/migrate_strip_role_suffix_from_labels.py engineering-ethics [--dry-run]

Notes:
- Safe heuristic: only modifies rdfs:label literals; will not touch URIs.
- Idempotent: running again will find nothing to change.
"""
import re
import sys
from app import create_app, db
from app.models.ontology import Ontology
from app.models.role import Role
from rdflib import Graph, RDFS

ROLE_SUFFIX_RE = re.compile(r"\s*roles?$", re.IGNORECASE)


def strip_suffix(label: str) -> str:
    base = ROLE_SUFFIX_RE.sub("", label or "").rstrip()
    if base.lower().endswith(" role"):
        base = base[:-5].rstrip()
    return base


def update_ontology_labels(ontology: Ontology) -> tuple[int, str]:
    g = Graph()
    g.parse(data=ontology.content, format="turtle")

    changed = 0
    # Collect (subject, old_label, new_label)
    updates = []
    for s, p, o in g.triples((None, RDFS.label, None)):
        if isinstance(o, str) or getattr(o, 'value', None):
            val = str(o)
            new = strip_suffix(val)
            if new != val:
                updates.append((s, val, new))

    if not updates:
        return 0, ontology.content

    ttl = ontology.content
    for s, old, new in updates:
        # conservative replace only for exact label literal
        ttl = ttl.replace(f'"{old}"', f'"{new}"')
        changed += 1

    return changed, ttl


def main():
    if len(sys.argv) < 2:
        print("Usage: migrate_strip_role_suffix_from_labels.py <ontology_domain_id> [--dry-run]")
        sys.exit(1)

    domain_id = sys.argv[1]
    dry = '--dry-run' in sys.argv

    app = create_app('config')
    with app.app_context():
        onto = Ontology.query.filter_by(domain_id=domain_id).first()
        if not onto:
            print(f"Ontology with domain_id '{domain_id}' not found")
            sys.exit(2)

        print(f"Loaded ontology {onto.id} ({onto.domain_id})")
        changed, new_content = update_ontology_labels(onto)
        print(f"TTL label changes: {changed}")
        if not dry and changed:
            onto.content = new_content

        # Update Role table labels that mirror these ontology classes
        role_rows = Role.query.filter(Role.ontology_uri.isnot(None)).all()
        updated_roles = 0
        for r in role_rows:
            new_name = strip_suffix(r.name)
            if new_name != r.name:
                r.name = new_name
                updated_roles += 1

        print(f"Relational Role rows updated: {updated_roles}")
        if not dry and (changed or updated_roles):
            db.session.commit()
            print("Committed changes.")
        else:
            print("Dry-run or no changes.")


if __name__ == "__main__":
    main()
