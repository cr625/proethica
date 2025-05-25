# Embeddings Improvement Plan

This document outlines a comprehensive roadmap for enhancing the embeddings system with larger models, API integrations, visualizations, and improved similarity capabilities.

## Executive Summary

The current embeddings system provides a solid foundation with 384-dimensional local embeddings, but has significant room for improvement. Priority enhancements include upgrading to larger embedding models, integrating commercial APIs, adding visualization capabilities, and implementing advanced similarity features.

**Current State**: 384-dim local SentenceTransformers model with basic similarity search
**Target State**: Multi-provider system with large embeddings, hybrid search, clustering, and interactive visualizations

## Phase 1: Model and API Upgrades (Priority: High)

### 1.1 Larger Embedding Models

**Objective**: Improve semantic understanding with higher-dimensional embeddings

**Local Model Upgrades**:
```python
# Current: all-MiniLM-L6-v2 (384 dims, 90MB)
# Target options:
MODEL_CANDIDATES = {
    'all-mpnet-base-v2': {
        'dimensions': 768,
        'size': '420MB', 
        'performance': 'Better quality, 2x slower',
        'use_case': 'General upgrade'
    },
    'all-roberta-large-v1': {
        'dimensions': 1024,
        'size': '1.4GB',
        'performance': 'Best quality, 4x slower',
        'use_case': 'High-quality applications'
    },
    'e5-large-v2': {
        'dimensions': 1024,
        'size': '1.2GB',
        'performance': 'State-of-the-art, optimized',
        'use_case': 'Production deployment'
    }
}
```

**Implementation Plan**:
1. **Database Migration**: Support variable embedding dimensions
2. **Model Configuration**: Dynamic model selection based on use case
3. **Backward Compatibility**: Maintain support for existing 384-dim embeddings
4. **Performance Testing**: Benchmark quality vs speed tradeoffs

### 1.2 Commercial API Integration

**Objective**: Leverage high-quality commercial embedding APIs

**API Provider Roadmap**:

**OpenAI Embeddings**:
```python
# Current: text-embedding-ada-002 (1536 dims, $0.0001/1K tokens)
# New: text-embedding-3-large (3072 dims, $0.00013/1K tokens)
OPENAI_MODELS = {
    'text-embedding-3-small': {
        'dimensions': 1536,
        'cost': '$0.00002/1K tokens',
        'performance': 'Fast, cost-effective'
    },
    'text-embedding-3-large': {
        'dimensions': 3072, 
        'cost': '$0.00013/1K tokens',
        'performance': 'Highest quality'
    }
}
```

**Cohere API Integration** (NEW):
```python
COHERE_MODELS = {
    'embed-english-v3.0': {
        'dimensions': 1024,
        'cost': '$0.0001/1K tokens',
        'features': ['semantic_search', 'classification', 'clustering'],
        'performance': 'Optimized for search tasks'
    },
    'embed-multilingual-v3.0': {
        'dimensions': 1024,
        'features': ['100+ languages'],
        'performance': 'Global case repository support'
    }
}
```

**Voyage AI Integration** (NEW):
```python
VOYAGE_MODELS = {
    'voyage-large-2': {
        'dimensions': 1536,
        'context_length': 16000,  # 4x longer than current
        'performance': 'Optimized for long documents',
        'use_case': 'Long case discussions'
    }
}
```

### 1.3 Database Schema Enhancements

**Dynamic Embedding Storage**:
```sql
-- New schema supporting multiple embedding dimensions
CREATE TABLE embeddings (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    section_id VARCHAR(255),
    section_type VARCHAR(100),
    content TEXT,
    embedding_vector VECTOR,  -- Dynamic dimensions
    embedding_model VARCHAR(100),
    embedding_dimensions INTEGER,
    embedding_provider VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(document_id, section_id, embedding_model)
);

-- Model-specific indexes
CREATE INDEX embeddings_384_idx ON embeddings 
    USING ivfflat (embedding_vector vector_cosine_ops)
    WHERE embedding_dimensions = 384;

CREATE INDEX embeddings_1536_idx ON embeddings 
    USING ivfflat (embedding_vector vector_cosine_ops) 
    WHERE embedding_dimensions = 1536;
```

**Migration Strategy**:
1. Create new embeddings table alongside existing document_sections
2. Migrate existing data with model metadata
3. Support both schemas during transition period
4. Deprecate document_sections.embedding column

## Phase 2: Advanced Similarity and Search (Priority: High)

### 2.1 Hybrid Search Implementation

**Objective**: Combine semantic and keyword search for better retrieval

**Architecture**:
```python
class HybridSearchService:
    def search(self, query: str, alpha: float = 0.7) -> List[SearchResult]:
        """
        alpha: Weight between semantic (1.0) and keyword (0.0) search
        """
        # Semantic search using embeddings
        semantic_results = self.embedding_search(query, k=20)
        
        # Keyword search using PostgreSQL full-text search
        keyword_results = self.fulltext_search(query, k=20)
        
        # Combine and re-rank results
        return self.fuse_results(semantic_results, keyword_results, alpha)
```

**Full-Text Search Enhancement**:
```sql
-- Add full-text search capabilities
ALTER TABLE document_sections ADD COLUMN content_vector tsvector;

CREATE INDEX document_sections_fts_idx ON document_sections 
    USING gin(content_vector);

-- Update trigger for automatic vector updates
CREATE TRIGGER update_content_vector 
    BEFORE INSERT OR UPDATE ON document_sections
    FOR EACH ROW EXECUTE FUNCTION 
    tsvector_update_trigger(content_vector, 'pg_catalog.english', content);
```

### 2.2 Re-ranking with Cross-Encoders

**Objective**: Improve relevance of top search results

**Implementation**:
```python
class ReRankingService:
    def __init__(self):
        # Load cross-encoder for re-ranking
        self.cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
    
    def rerank_results(self, query: str, candidates: List[str], top_k: int = 10):
        """Re-rank candidates using cross-encoder scores"""
        scores = self.cross_encoder.predict([(query, candidate) for candidate in candidates])
        
        # Sort by cross-encoder scores and return top_k
        ranked_results = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return ranked_results[:top_k]
```

### 2.3 Contextual and Multi-Vector Search

**Document-Level Context**:
```python
class ContextualSearchService:
    def search_with_context(self, query: str, document_context: bool = True):
        """Search considering document-level context"""
        if document_context:
            # Include document title, case number, year in search context
            enhanced_query = self.enhance_query_with_document_context(query)
            return self.embedding_search(enhanced_query)
        else:
            return self.embedding_search(query)
```

**Multi-Vector Representation**:
```python
class MultiVectorService:
    def generate_multi_vectors(self, section_content: str):
        """Generate multiple embeddings for different aspects"""
        return {
            'content': self.embed_text(section_content),
            'legal_concepts': self.embed_legal_concepts(section_content),
            'ethical_principles': self.embed_ethical_principles(section_content),
            'factual_circumstances': self.embed_facts(section_content)
        }
```

## Phase 3: Clustering and Pattern Discovery (Priority: Medium)

### 3.1 Automatic Section Clustering

**Objective**: Discover thematic groups in case sections

**Implementation**:
```python
from sklearn.cluster import KMeans, HDBSCAN
import numpy as np

class SectionClusteringService:
    def cluster_sections(self, embeddings: np.ndarray, method: str = 'hdbscan'):
        """Cluster sections by semantic similarity"""
        
        if method == 'kmeans':
            # Fixed number of clusters
            clusterer = KMeans(n_clusters=10, random_state=42)
        elif method == 'hdbscan':
            # Automatic cluster discovery
            clusterer = HDBSCAN(min_cluster_size=5, metric='cosine')
        
        cluster_labels = clusterer.fit_predict(embeddings)
        return self.analyze_clusters(cluster_labels, embeddings)
    
    def analyze_clusters(self, labels: np.ndarray, embeddings: np.ndarray):
        """Analyze cluster characteristics and themes"""
        clusters = {}
        for cluster_id in set(labels):
            if cluster_id == -1:  # Noise cluster in HDBSCAN
                continue
                
            cluster_mask = labels == cluster_id
            cluster_embeddings = embeddings[cluster_mask]
            
            clusters[cluster_id] = {
                'size': np.sum(cluster_mask),
                'centroid': np.mean(cluster_embeddings, axis=0),
                'cohesion': self.calculate_cohesion(cluster_embeddings),
                'representative_sections': self.find_representative_sections(cluster_embeddings)
            }
        
        return clusters
```

### 3.2 Temporal Pattern Analysis

**Objective**: Identify how ethical reasoning patterns change over time

**Implementation**:
```python
class TemporalAnalysisService:
    def analyze_temporal_patterns(self, start_year: int, end_year: int):
        """Analyze how case patterns evolve over time"""
        
        yearly_embeddings = {}
        for year in range(start_year, end_year + 1):
            cases = self.get_cases_by_year(year)
            embeddings = self.get_embeddings_for_cases(cases)
            yearly_embeddings[year] = np.mean(embeddings, axis=0)
        
        # Calculate year-to-year similarity
        temporal_trends = self.calculate_temporal_trends(yearly_embeddings)
        
        # Identify significant shifts
        shift_points = self.detect_trend_shifts(temporal_trends)
        
        return {
            'yearly_centroids': yearly_embeddings,
            'trends': temporal_trends,
            'shift_points': shift_points
        }
```

## Phase 4: Visualization and Analytics (Priority: Medium)

### 4.1 Interactive Embedding Visualization

**Objective**: Provide visual exploration of embedding spaces

**Technology Stack**:
- **Frontend**: D3.js, Plotly.js, or Observable Plot
- **Dimensionality Reduction**: UMAP, t-SNE, PCA
- **Backend**: Flask API endpoints for embedding data

**Visualization Types**:

**1. Section Similarity Map**:
```javascript
// Interactive scatter plot of sections in 2D embedding space
class SectionSimilarityMap {
    constructor(containerId) {
        this.container = d3.select(containerId);
        this.width = 800;
        this.height = 600;
    }
    
    async renderSections(documentId) {
        // Fetch section embeddings and reduce to 2D
        const embeddings = await this.fetchEmbeddings(documentId);
        const reduced = await this.reduceEmbeddings(embeddings);
        
        // Create interactive scatter plot
        this.createScatterPlot(reduced);
    }
    
    createScatterPlot(data) {
        const svg = this.container.append('svg')
            .attr('width', this.width)
            .attr('height', this.height);
            
        // Plot points with hover details
        svg.selectAll('circle')
            .data(data)
            .enter()
            .append('circle')
            .attr('cx', d => this.xScale(d.x))
            .attr('cy', d => this.yScale(d.y))
            .attr('r', 5)
            .attr('fill', d => this.colorScale(d.section_type))
            .on('mouseover', this.showTooltip)
            .on('click', this.showSectionDetail);
    }
}
```

**2. Case Similarity Network**:
```javascript
// Network graph showing relationships between similar cases
class CaseSimilarityNetwork {
    async renderNetwork(threshold = 0.7) {
        const similarities = await this.fetchCaseSimilarities(threshold);
        
        const force = d3.forceSimulation(similarities.nodes)
            .force('link', d3.forceLink(similarities.links))
            .force('charge', d3.forceManyBody().strength(-300))
            .force('center', d3.forceCenter(this.width / 2, this.height / 2));
            
        // Render nodes and links with interactive features
        this.renderNodes(similarities.nodes);
        this.renderLinks(similarities.links);
    }
}
```

**3. Temporal Evolution Heatmap**:
```javascript
// Heatmap showing how case themes evolve over time
class TemporalHeatmap {
    renderEvolution(temporalData) {
        // Create heatmap with years on x-axis, themes on y-axis
        // Color intensity represents theme prevalence
        
        const heatmap = d3.select(this.container)
            .append('svg')
            .selectAll('rect')
            .data(temporalData.flatten())
            .enter()
            .append('rect')
            .attr('x', d => this.xScale(d.year))
            .attr('y', d => this.yScale(d.theme))
            .attr('width', this.xScale.bandwidth())
            .attr('height', this.yScale.bandwidth())
            .attr('fill', d => this.colorScale(d.intensity));
    }
}
```

### 4.2 Analytics Dashboard

**Flask API Endpoints**:
```python
@app.route('/api/embeddings/analytics/<int:document_id>')
def embedding_analytics(document_id):
    """Return comprehensive embedding analytics for a document"""
    service = EmbeddingAnalyticsService()
    
    return jsonify({
        'section_similarities': service.get_section_similarities(document_id),
        'related_cases': service.find_related_cases(document_id),
        'cluster_membership': service.get_cluster_info(document_id),
        'temporal_context': service.get_temporal_context(document_id),
        'quality_metrics': service.calculate_quality_metrics(document_id)
    })

@app.route('/api/embeddings/similarity_matrix')
def similarity_matrix():
    """Return pairwise similarity matrix for visualization"""
    case_ids = request.args.getlist('case_ids', type=int)
    service = EmbeddingAnalyticsService()
    
    matrix = service.compute_similarity_matrix(case_ids)
    return jsonify({
        'matrix': matrix.tolist(),
        'case_ids': case_ids,
        'labels': service.get_case_labels(case_ids)
    })
```

**Dashboard Components**:
```html
<!-- Embedding Dashboard Template -->
<div class="embedding-dashboard">
    <div class="row">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header">Section Similarity Map</div>
                <div class="card-body">
                    <div id="similarity-map"></div>
                </div>
            </div>
        </div>
        <div class="col-md-6">
            <div class="card">
                <div class="card-header">Related Cases Network</div>
                <div class="card-body">
                    <div id="network-graph"></div>
                </div>
            </div>
        </div>
    </div>
    <div class="row mt-4">
        <div class="col-12">
            <div class="card">
                <div class="card-header">Temporal Trends</div>
                <div class="card-body">
                    <div id="temporal-heatmap"></div>
                </div>
            </div>
        </div>
    </div>
</div>
```

## Phase 5: Domain Specialization (Priority: Low)

### 5.1 Fine-Tuning for Ethics Domain

**Objective**: Create domain-specific embeddings for ethics and engineering

**Training Data Collection**:
```python
class EthicsCorpusBuilder:
    def build_training_corpus(self):
        """Build training corpus from multiple sources"""
        corpus = []
        
        # NSPE cases
        corpus.extend(self.extract_nspe_cases())
        
        # Engineering ethics textbooks
        corpus.extend(self.extract_textbook_content())
        
        # Professional ethics guidelines
        corpus.extend(self.extract_guidelines())
        
        # Academic papers on engineering ethics
        corpus.extend(self.extract_academic_papers())
        
        return self.format_for_training(corpus)
```

**Fine-Tuning Pipeline**:
```python
from sentence_transformers import SentenceTransformer, losses
from sentence_transformers.evaluation import EmbeddingSimilarityEvaluator

class EthicsEmbeddingTrainer:
    def fine_tune_model(self, base_model: str, training_data: List[Tuple[str, str, float]]):
        """Fine-tune embedding model on ethics-specific data"""
        
        model = SentenceTransformer(base_model)
        
        # Create training dataset with positive/negative pairs
        train_dataloader = self.create_dataloader(training_data)
        
        # Use CosineSimilarityLoss for training
        train_loss = losses.CosineSimilarityLoss(model)
        
        # Train the model
        model.fit(
            train_objectives=[(train_dataloader, train_loss)],
            epochs=5,
            warmup_steps=100,
            output_path='./ethics-embedding-model'
        )
        
        return model
```

### 5.2 Multi-Modal Embeddings

**Objective**: Support cases with diagrams, charts, and images

**Implementation**:
```python
from transformers import CLIPModel, CLIPProcessor

class MultiModalEmbeddingService:
    def __init__(self):
        self.clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    
    def embed_case_with_images(self, text_content: str, images: List[Image]):
        """Generate combined text-image embeddings"""
        
        # Text embedding
        text_embedding = self.embed_text(text_content)
        
        # Image embeddings
        image_embeddings = []
        for image in images:
            inputs = self.clip_processor(images=[image], return_tensors="pt")
            image_emb = self.clip_model.get_image_features(**inputs)
            image_embeddings.append(image_emb.numpy())
        
        # Combine embeddings (various strategies)
        combined_embedding = self.combine_modalities(text_embedding, image_embeddings)
        
        return combined_embedding
```

## Implementation Timeline

### Phase 1: Core Upgrades (Months 1-2)
- [ ] Database schema migration for multi-dimensional embeddings
- [ ] Integrate OpenAI text-embedding-3-large 
- [ ] Add Cohere API support
- [ ] Fix current "Generate Section Embeddings" error
- [ ] Performance benchmarking of different models

### Phase 2: Advanced Search (Months 2-3)
- [ ] Implement hybrid search combining semantic + keyword
- [ ] Add cross-encoder re-ranking
- [ ] Create contextual search with document metadata
- [ ] Build clustering service for automatic theme discovery

### Phase 3: Visualization (Months 3-4)
- [ ] Create interactive embedding visualization dashboard
- [ ] Build section similarity map with D3.js
- [ ] Implement case network graph visualization
- [ ] Add temporal trend analysis and heatmaps

### Phase 4: Optimization (Months 4-5)
- [ ] Optimize database queries and indexing
- [ ] Implement async processing for large batches
- [ ] Add caching layer for frequently accessed embeddings
- [ ] Performance monitoring and alerting

### Phase 5: Domain Specialization (Months 5-6)
- [ ] Collect and curate ethics training corpus
- [ ] Fine-tune domain-specific embedding models
- [ ] Implement multi-modal support for images/diagrams
- [ ] A/B test domain models vs general models

## Success Metrics

### Technical Metrics
- **Embedding Quality**: Improved similarity relevance scores
- **Search Performance**: <100ms average query response time
- **Coverage**: >95% of cases have high-quality embeddings
- **Accuracy**: >90% relevant results in top-5 similarity search

### User Experience Metrics
- **Discovery**: Increased similar case discovery by users
- **Engagement**: Time spent exploring related cases
- **Satisfaction**: User feedback on search result relevance
- **Adoption**: Usage of new visualization features

### Business Impact
- **Research Efficiency**: Faster case precedent discovery
- **Knowledge Discovery**: New patterns identified through clustering
- **Decision Support**: Improved ethical decision-making support
- **Scalability**: Support for larger case repositories (10K+ cases)

This improvement plan provides a comprehensive roadmap for evolving the embeddings system from its current basic implementation to a sophisticated, multi-modal, domain-specialized platform that significantly enhances the application's analytical and discovery capabilities.