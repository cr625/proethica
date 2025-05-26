import os
os.environ['FLASK_ENV'] = 'development'
os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'

from app import create_app
from app.models import db, Document, EntityTriple

app = create_app()
with app.app_context():
    # Find a document in world 1 that has concepts in metadata
    docs = Document.query.filter_by(world_id=1).filter(
        Document.doc_metadata.op('?')('concepts_extracted')
    ).limit(5).all()
    
    print("Documents with extracted concepts:")
    for doc in docs:
        concepts_count = doc.doc_metadata.get('concepts_extracted', 0)
        triples_count = doc.doc_metadata.get('triples_created', 0)
        print(f"  Doc {doc.id}: {doc.title[:40]}... - {concepts_count} concepts, {triples_count} triples")
        print(f"    URL: http://localhost:3333/worlds/1/guidelines/{doc.id}")
        
        # Check if it has a guideline_id
        if 'guideline_id' in doc.doc_metadata:
            guideline_id = doc.doc_metadata['guideline_id']
            triple_count = EntityTriple.query.filter_by(
                guideline_id=guideline_id,
                entity_type='guideline_concept'
            ).count()
            print(f"    Linked to guideline {guideline_id} with {triple_count} entity_triples")
