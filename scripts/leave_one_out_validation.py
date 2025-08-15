"""
Leave-One-Out validation over NSPE BER cases (baseline).

Approach:
- For each NSPE case document, exclude it, query similar cases by section embeddings,
  extract their outcome signal from conclusions, and predict the majority signal.
- Compare to the held-out case's extracted conclusion signal. Report accuracy and summary.

Notes:
- Uses existing services: SectionEmbeddingService and find_similar_cases helpers.
- "Outcome signal" is a coarse ethical/unethical/neutral detection from conclusion text.
- This is a baseline to support paper claims; refine scoring and metrics as needed.
"""

import sys
import re
from collections import Counter
from typing import Optional, Tuple

from app import create_app
from app.models import db
from app.models.document import Document
from app.services.section_embedding_service import SectionEmbeddingService
from app.services.experiment.find_similar_cases import (
    find_similar_cases,
    get_document_conclusion,
    extract_outcome_from_conclusion,
)


def outcome_label_from_text(text: Optional[str]) -> Optional[str]:
    """Map conclusion sentence to a coarse label: 'ethical' | 'unethical' | 'neutral' | None."""
    if not text:
        return None
    t = text.lower()
    # Priority: explicit unethical/not ethical
    if re.search(r"not ethical|unethical|does not comply|violates|not in accordance|in conflict", t):
        return "unethical"
    if re.search(r"ethical|complies|in accordance|not in conflict", t):
        return "ethical"
    return "neutral"


def predict_from_neighbors(doc_id: int, ses: SectionEmbeddingService, k: int = 5) -> Optional[str]:
    """Predict label for doc by majority label of top-k similar cases' conclusions."""
    neighbors = find_similar_cases(doc_id, ses, limit=k + 2, exclude_self=True)
    labels = []
    for n in neighbors:
        nid = n.get("id")
        if not nid:
            # The helper returns 'id' in doc_data; if absent, skip
            nid = n.get("document_id")
        if not nid:
            continue
        concl = get_document_conclusion(nid)
        sent = extract_outcome_from_conclusion(concl) if concl else None
        lab = outcome_label_from_text(sent)
        if lab and lab != "neutral":
            labels.append(lab)
    if not labels:
        return None
    return Counter(labels).most_common(1)[0][0]


def evaluate(limit: Optional[int] = None, k: int = 5) -> None:
    app = create_app("config")
    with app.app_context():
        ses = SectionEmbeddingService()

        # Select NSPE cases: document_type 'case_study' and source URL containing nspe.org if available
        query = Document.query.filter(Document.document_type == "case_study")
        # Prefer NSPE subset when possible
        query = query.filter((Document.source.ilike("%nspe.org%")) | (Document.title.ilike("%BER%")))
        docs = query.order_by(Document.id.asc()).all()
        if limit:
            docs = docs[:limit]

        total = 0
        matched = 0
        skipped = 0
        conf_matrix = Counter()

        for d in docs:
            total += 1

            gold_concl = get_document_conclusion(d.id)
            gold_sent = extract_outcome_from_conclusion(gold_concl) if gold_concl else None
            gold = outcome_label_from_text(gold_sent)

            pred = predict_from_neighbors(d.id, ses, k=k)

            if gold is None or pred is None:
                skipped += 1
                continue

            if gold == pred:
                matched += 1
            conf_matrix[(gold, pred)] += 1

        evaluated = total - skipped
        acc = (matched / evaluated) if evaluated else 0.0

        print("Leave-One-Out (baseline) summary:")
        print(f"  Total docs: {total}")
        print(f"  Evaluated:  {evaluated}")
        print(f"  Skipped:    {skipped}  (no gold or no prediction)")
        print(f"  Accuracy:   {acc:.3f}")
        if conf_matrix:
            print("  Confusion (gold -> pred counts):")
            for (g, p), c in conf_matrix.most_common():
                print(f"    {g:9s} -> {p:9s} : {c}")


if __name__ == "__main__":
    # Optional CLI: python scripts/leave_one_out_validation.py [limit] [k]
    arg_limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    arg_k = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    evaluate(limit=arg_limit, k=arg_k)
