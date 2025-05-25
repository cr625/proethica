# Section Embeddings Implementation Quick Start

## Fixing the Current Error

The "'str' object has no attribute 'keys'" error occurs because the section data is sometimes a string instead of a dictionary. Here's the immediate fix:

### 1. Update the Route Handler
In `/app/routes/document_structure.py`, modify the section embedding generation endpoint:

```python
@bp.route('/documents/<int:document_id>/generate-section-embeddings', methods=['POST'])
def generate_section_embeddings(document_id):
    try:
        document = Document.query.get_or_404(document_id)
        
        # Ensure metadata is properly loaded
        if isinstance(document.doc_metadata, str):
            try:
                document.doc_metadata = json.loads(document.doc_metadata)
            except:
                return jsonify({
                    'success': False,
                    'message': 'Invalid document metadata format'
                }), 400
        
        # Check for document structure
        doc_structure = document.doc_metadata.get('document_structure', {})
        if not doc_structure or not isinstance(doc_structure.get('sections'), dict):
            return jsonify({
                'success': False,
                'message': 'Document structure not found. Please generate structure first.'
            }), 400
        
        # Process embeddings
        service = SectionEmbeddingService()
        results = service.process_document_sections(document)
        
        return jsonify({
            'success': True,
            'message': f'Generated embeddings for {results["sections_processed"]} sections'
        })
    except Exception as e:
        logger.error(f"Error generating embeddings: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error processing section embeddings: {str(e)}'
        }), 500
```

## Implementing Granular Section Embeddings

### Step 1: Parse Structure Triples for Individual Items

Create a new utility function to extract individual section items from structure triples:

```python
# In app/services/structure_triple_formatter.py
def extract_section_items(structure_triples):
    """Extract individual items (fact_1, question_1, etc.) from structure triples"""
    items = []
    
    # Parse RDF triples
    g = Graph()
    g.parse(data=structure_triples, format='turtle')
    
    # Query for FactStatements
    fact_query = """
    PREFIX proethica: <http://proethica.ai/ontology#>
    SELECT ?fact ?content ?number
    WHERE {
        ?fact a proethica:FactStatement ;
              proethica:hasTextContent ?content ;
              proethica:hasSequenceNumber ?number .
    }
    ORDER BY ?number
    """
    
    for row in g.query(fact_query):
        items.append({
            'type': 'fact',
            'number': int(row.number),
            'content': str(row.content),
            'uri': str(row.fact),
            'parent_section': 'Facts'
        })
    
    # Similar queries for Questions, DiscussionSegments, Conclusions
    # ...
    
    return items
```

### Step 2: Update Embedding Service

Modify `section_embedding_service.py` to handle granular items:

```python
def process_granular_sections(self, document):
    """Generate embeddings for individual section items"""
    
    # Get structure triples
    doc_structure = document.doc_metadata.get('document_structure', {})
    structure_triples = doc_structure.get('structure_triples', '')
    
    if not structure_triples:
        return {'error': 'No structure triples found'}
    
    # Extract individual items
    items = extract_section_items(structure_triples)
    
    # Generate embeddings for each item
    for item in items:
        embedding = self.model.encode(item['content'])
        
        # Create or update DocumentSection record
        section = DocumentSection(
            document_id=document.id,
            section_type=item['type'],
            section_number=item['number'],
            parent_section=item['parent_section'],
            content=item['content'],
            embedding_vector=embedding,
            metadata={
                'uri': item['uri'],
                'generated_at': datetime.utcnow().isoformat()
            }
        )
        db.session.add(section)
    
    db.session.commit()
    return {'sections_processed': len(items)}
```

### Step 3: Create Similarity Search Endpoints

Add new routes for section-specific similarity search:

```python
# In app/routes/api.py or create new similarity.py
@bp.route('/api/similarity/search', methods=['POST'])
def similarity_search():
    data = request.json
    query_text = data.get('text')
    section_type = data.get('section_type')  # Optional filter
    limit = data.get('limit', 10)
    
    # Generate embedding for query
    embedding_service = SectionEmbeddingService()
    query_embedding = embedding_service.model.encode(query_text)
    
    # Build query
    query = DocumentSection.query
    
    if section_type:
        query = query.filter_by(section_type=section_type)
    
    # Use pgvector similarity search
    results = query.order_by(
        DocumentSection.embedding_vector.l2_distance(query_embedding)
    ).limit(limit).all()
    
    return jsonify({
        'results': [{
            'document_id': r.document_id,
            'section_type': r.section_type,
            'section_number': r.section_number,
            'content': r.content,
            'similarity': 1 - r.distance  # Convert distance to similarity
        } for r in results]
    })
```

## Testing the Implementation

### 1. Test Data Preparation
```python
# Script to test embedding generation
from app import create_app, db
from app.models import Document
from app.services.section_embedding_service import SectionEmbeddingService

app = create_app()
with app.app_context():
    # Get a document with structure
    doc = Document.query.filter(
        Document.doc_metadata.contains('document_structure')
    ).first()
    
    if doc:
        service = SectionEmbeddingService()
        result = service.process_granular_sections(doc)
        print(f"Generated embeddings: {result}")
```

### 2. Verify Similarity Search
```python
# Test similarity search
import requests

response = requests.post('http://localhost:5000/api/similarity/search', json={
    'text': 'engineer disclosed confidential information',
    'section_type': 'fact',
    'limit': 5
})

print(response.json())
```

## UI Integration

Update the structure view template to show granular embeddings:

```javascript
// In structure-viewer.js
function generateSectionEmbeddings(documentId) {
    fetch(`/documents/${documentId}/generate-section-embeddings`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('success', data.message);
            // Refresh the view to show embedding status
            setTimeout(() => location.reload(), 1500);
        } else {
            showNotification('error', data.message);
        }
    });
}

// Add "Find Similar" buttons to each section item
function addSimilarityButtons() {
    document.querySelectorAll('.section-item').forEach(item => {
        const button = document.createElement('button');
        button.className = 'btn btn-sm btn-outline-primary ms-2';
        button.innerHTML = '<i class="fas fa-search"></i> Find Similar';
        button.onclick = () => findSimilarSections(item.dataset.type, item.dataset.content);
        item.appendChild(button);
    });
}
```

## Next Steps

1. **Immediate**: Apply the error fix to handle string metadata
2. **This Week**: Implement granular section extraction from triples
3. **Next Week**: Add similarity search endpoints and UI
4. **Following Week**: Add ontology concept extraction

This approach provides a working system quickly while building toward the full vision.