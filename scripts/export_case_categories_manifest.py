#!/usr/bin/env python3
"""
Export the OntServe category manifest for the committed case ontologies.

New case commits carry the NSPE case number and decade in the TTL header
(app/services/commit/case_header.py: dcterms:identifier / dcterms:temporal), and
the OntServe sync reads them into the ontology record. Cases committed before
that header existed have no decade on the OntServe side; this script produces
the manifest that backfills them:

    python scripts/export_case_categories_manifest.py ../OntServe/tools/migrations/case_categories.json
    cd ../OntServe && python tools/set_ontology_categories.py --manifest tools/migrations/case_categories.json

The manifest maps ``proethica-case-<id>`` to ``{"subcategory": "<decade>",
"case_number": "<NSPE number>"}`` using the same decade rule as the header, so
the backfill and the live path cannot disagree. Cases without a parseable
number or year are listed on stderr and omitted.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.services.commit.case_header import (  # noqa: E402
    MANIFEST_CASE_NUMBER_KEY, MANIFEST_SUBCATEGORY_KEY, case_header_fields,
)


def main() -> int:
    if len(sys.argv) != 2:
        print('usage: export_case_categories_manifest.py <output.json>', file=sys.stderr)
        return 2
    out_path = Path(sys.argv[1])
    app = create_app()  # prints its configuration banner to stdout, hence the file argument
    with app.app_context():
        from app.models import db
        from app.models.document import Document
        docs = db.session.query(Document.id).filter(
            Document.document_type.in_(('case', 'case_study'))).order_by(Document.id).all()
        manifest = {}
        skipped = []
        for (doc_id,) in docs:
            fields = case_header_fields(doc_id)
            if not fields['decade']:
                skipped.append((doc_id, fields['case_number']))
                continue
            entry = {MANIFEST_SUBCATEGORY_KEY: fields['decade']}
            if fields['case_number']:
                entry[MANIFEST_CASE_NUMBER_KEY] = fields['case_number']
            manifest[f'proethica-case-{doc_id}'] = entry
    out_path.write_text(json.dumps(manifest, indent=1) + '\n')
    for doc_id, num in skipped:
        print(f'skipped case {doc_id}: no decade (case_number={num!r})', file=sys.stderr)
    print(f'{len(manifest)} cases exported to {out_path}, {len(skipped)} skipped', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
