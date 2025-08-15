#!/usr/bin/env python3
"""
Backfill 384-dim embeddings for document_chunks.embedding_384 using a local SentenceTransformer.

Defaults to all-MiniLM-L6-v2 (384 dims). Processes in batches.

Env:
  - BATCH_SIZE: number of rows per batch (default 256)
  - WHERE_CLAUSE: optional SQL WHERE to restrict rows (e.g., "document_type='guideline'")
"""
import os
import sys
import time
from typing import List

import numpy as np
from sqlalchemy import text

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db  # type: ignore


MODEL_NAME = os.getenv("EMBEDDING_384_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


def get_model():
    try:
        from sentence_transformers import SentenceTransformer
    except Exception:
        raise RuntimeError(
            "sentence-transformers not installed. Please add it to requirements and install."
        )
    return SentenceTransformer(MODEL_NAME)


def batched(iterable, n):
    it = iter(iterable)
    while True:
        chunk = []
        try:
            for _ in range(n):
                chunk.append(next(it))
        except StopIteration:
            pass
        if chunk:
            yield chunk
        else:
            return


def main():
    cfg = os.getenv("CONFIG_MODULE", "config")
    app = create_app(cfg)
    with app.app_context():
        batch_size = int(os.getenv("BATCH_SIZE", "256"))
        where = os.getenv("WHERE_CLAUSE", "")
        if where.strip():
            where = f"WHERE {where}"

        # Select chunks missing embedding_384
        select_sql = text(
            f"""
            SELECT id, content
            FROM document_chunks
            {where if where else ''}
            AND embedding_384 IS NULL
            ORDER BY id
            """
        ) if where else text(
            """
            SELECT id, content
            FROM document_chunks
            WHERE embedding_384 IS NULL
            ORDER BY id
            """
        )

        rows = db.session.execute(select_sql).fetchall()
        total = len(rows)
        if total == 0:
            print("No rows to backfill.")
            return

        print(f"Backfilling embedding_384 for {total} rows using {MODEL_NAME}...")
        model = get_model()

        update_sql = text(
            """
            UPDATE document_chunks
            SET embedding_384 = :vec
            WHERE id = :id
            """
        )

        processed = 0
        start = time.time()
        for batch in batched(rows, batch_size):
            texts = [r[1] or "" for r in batch]
            ids = [r[0] for r in batch]
            # Compute embeddings
            embs = model.encode(texts, batch_size=batch_size, show_progress_bar=False, normalize_embeddings=False)
            # Ensure list[float]
            if isinstance(embs, np.ndarray):
                embs = embs.tolist()

            for id_, vec in zip(ids, embs):
                # Convert to pgvector input format: Python list is accepted via SQLAlchemy bindproc in our Vector type
                db.session.execute(update_sql, {"vec": vec, "id": id_})

            db.session.commit()
            processed += len(batch)
            if processed % (batch_size * 4) == 0 or processed == total:
                rate = processed / (time.time() - start)
                print(f"Processed {processed}/{total} ({rate:.1f} rows/sec)")

        print("Backfill complete.")


if __name__ == "__main__":
    main()
