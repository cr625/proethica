# AI Ethical DM Project Progress

## Document Structure and Section Embeddings (2025 Update)

This project models professional domains ("worlds") and supports ethical decision-making using structured document analysis, ontology-based concepts, and LLM reasoning. The current pipeline is:

### 1. Case Import and Parsing
- Cases (e.g., NSPE) are imported via URL or file upload.
- Each case is parsed into sections (facts, discussion, conclusion, etc.).

### 2. Document Structure Generation
- For each case, run the document structure pipeline (via UI or script).
- This creates a `document_structure` entry in the case's `doc_metadata` with:
  - `document_uri`: Unique identifier for the case
  - `structure_triples`: RDF triples representing the case structure (ProEthica intermediate ontology)
  - `sections`: Section metadata
  - `annotation_timestamp`: When structure was generated

### 3. Section Embeddings
- Section embeddings are generated and stored in both the `DocumentSection` table (with pgvector) and in `section_embeddings_metadata` in `doc_metadata`.
- Enables semantic similarity search between sections across cases.

### 4. Guideline Association
- Ethical guidelines are associated with each world.
- Guideline associations can be generated for each case section, linking them to relevant ethical principles.

### 5. LLM Reasoning (Experiment Phase)
- LLMs can be prompted with case sections, extracted concepts, and triples for ontology-based reasoning.
- Two experiment modes: ontology-augmented and prompt-only.

## Technical Notes
- All new cases use the nested `document_structure` format in metadata.
- Section embeddings use 384-dim vectors (MiniLM-L6-v2) and are stored with pgvector.
- Legacy/obsolete migration scripts and top-level structure fields are no longer used for new data.
- NLTK resources are managed at setup, not runtime.

## Next Steps
- Batch run the document structure pipeline for all imported cases.
- Generate section embeddings and guideline associations as needed.
- Run LLM experiments as described in the project plan.

## Archived Documentation
Legacy and outdated documentation has been moved to `docs/archived/` for reference.
