# Case Import and Processing Pipeline

This document describes the complete case import and processing pipeline in the ProEthica system, starting from URL input at http://localhost:3333/cases/new/url.

## Overview

The case processing pipeline transforms engineering ethics cases (primarily NSPE cases) from URLs into structured documents with:
- Parsed sections (facts, questions, references, discussion, conclusion)
- Document structure annotations (RDF triples)
- Section embeddings for semantic search
- Guideline associations linking sections to ethical principles

## Pipeline Architecture

### 1. URL Input Interface (`/cases/new/url`)
- **Route**: `app/routes/cases.py@267`
- **Template**: `create_case_from_url.html`
- User provides:
  - URL of the case (e.g., NSPE case page)
  - Target world (Engineering Ethics by default)
  - Option to process extraction immediately

### 2. Pipeline Processing (`/cases/process/url`)
- **Route**: `app/routes/cases.py@275`
- **Manager**: `app/services/case_processing/pipeline_manager.py`
- Orchestrates sequential pipeline steps:
  1. URL Retrieval
  2. NSPE Extraction
  3. Document Structure Annotation (optional)

### 3. Pipeline Steps

#### 3.1 URL Retrieval Step
- **Class**: `URLRetrievalStep` (`pipeline_steps/url_retrieval_step.py`)
- **Function**: Fetches HTML content from the provided URL
- **Features**:
  - Validates URL format
  - Handles redirects and timeouts
  - Size limits (10MB default)
  - Encoding detection
- **Output**: Raw HTML content with metadata

#### 3.2 NSPE Case Extraction Step
- **Class**: `NSPECaseExtractionStep` (`pipeline_steps/nspe_extraction_step.py`)
- **Function**: Extracts structured content from NSPE case HTML
- **Extracts**:
  - Case number (e.g., "23-4")
  - Year (derived from case number or page content)
  - Title
  - Facts section
  - Questions (as list if multiple)
  - NSPE Code references
  - Discussion
  - Conclusions (as list if multiple)
  - PDF URL if available
- **Uses**: BeautifulSoup for HTML parsing with NSPE-specific patterns

#### 3.3 Document Structure Annotation Step
- **Class**: `DocumentStructureAnnotationStep` (`pipeline_steps/document_structure_annotation_step.py`)
- **Function**: Creates RDF annotations for document structure
- **Generates**:
  - Document URI (e.g., `http://proethica.org/document/case_23_4`)
  - RDF triples using ProEthica intermediate ontology
  - Section metadata for embeddings
- **Output**: Turtle-formatted RDF triples

### 4. Alternative Processing: CaseUrlProcessor
- **Class**: `CaseUrlProcessor` (`app/services/case_url_processor/`)
- **Features**:
  - URL validation
  - Content extraction with pattern matching
  - LLM-based extraction for complex cases
  - Triple generation
  - Caching support
  - Correction handling

### 5. Document Storage
After pipeline processing, the case is saved as a Document with:
- **Basic fields**: title, content (HTML), source (URL)
- **Metadata** (`doc_metadata` JSON field):
  ```json
  {
    "case_number": "23-4",
    "year": "2023",
    "pdf_url": "...",
    "document_structure": {
      "document_uri": "http://proethica.org/document/case_23_4",
      "structure_triples": "...",
      "sections": {...},
      "annotation_timestamp": "2025-01-24T..."
    },
    "section_embeddings_metadata": {...}
  }
  ```

### 6. Post-Processing Steps

#### 6.1 Section Storage
- **Model**: `DocumentSection` (`app/models/document_section.py`)
- Stores individual sections with:
  - Section type (facts, question, etc.)
  - Content
  - Embeddings (pgvector, 384 dimensions)
  - Position/order

#### 6.2 Section Embeddings Generation
- **Service**: `SectionEmbeddingService`
- **Model**: MiniLM-L6-v2 (384-dim vectors)
- **Storage**: Both in DocumentSection table and metadata
- **Purpose**: Enables semantic similarity search

#### 6.3 Guideline Association
- **Service**: `GuidelineSectionService`
- Links case sections to relevant ethical guidelines
- Uses embeddings for similarity matching
- Stores associations for experiment use

## Usage Flow

1. **Navigate to**: http://localhost:3333/cases/new/url
2. **Enter URL**: Paste NSPE case URL
3. **Select options**:
   - World: Engineering Ethics (default)
   - Process extraction: Yes (recommended)
4. **Submit**: Initiates pipeline processing
5. **View results**: 
   - Extracted content preview
   - Option to save as case
   - Generate document structure
   - View section embeddings

## API Endpoints

- `GET /cases/new/url` - Display URL input form
- `POST /cases/process/url` - Process URL through pipeline
- `GET /structure/view/<id>` - View document structure
- `POST /structure/generate/<id>` - Generate structure annotations
- `GET /structure/embeddings/<id>` - View section embeddings

## Error Handling

The pipeline includes comprehensive error handling:
- Invalid URLs are rejected with validation
- HTTP errors are caught and reported
- Extraction failures fallback to raw content
- Each step can fail independently without breaking the pipeline

## Configuration

Pipeline behavior can be configured through:
- Step registration in pipeline manager
- Timeout settings in URL retrieval
- Pattern configurations for extraction
- LLM provider selection for complex cases

## Next Steps

After case import, typical next steps include:
1. Generate document structure annotations
2. Create section embeddings
3. Associate with guidelines
4. Use in experiments for LLM reasoning

## Technical Notes

- All new cases use nested `document_structure` format in metadata
- Legacy formats are automatically migrated
- Section embeddings use pgvector extension in PostgreSQL
- RDF triples follow ProEthica intermediate ontology