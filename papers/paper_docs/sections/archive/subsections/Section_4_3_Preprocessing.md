# 4.3 Preprocessing Pipeline

The preprocessing pipeline transforms raw NSPE cases and ethical guidelines into structured representations suitable for both ontology-constrained reasoning and comparative evaluation. The pipeline emphasizes automated processing with validation checkpoints to ensure consistency and accuracy.

## World Creation and Ontology Development

**NSPE Ethics Framework Construction**: The NSPE Code of Ethics undergoes systematic analysis to extract professional roles, ethical principles, obligations, and constraints. This process creates the foundational ontology that constrains subsequent reasoning processes.

**Concept Extraction and Formalization**: Professional ethics concepts are identified through automated analysis combined with domain expertise validation. Extracted concepts include roles (Engineer, Client, Public), principles (Safety, Competence, Honesty), and contextual factors (Conflicts of Interest, Confidentiality Requirements).

**Relationship Formalization**: Professional obligations and ethical relationships are encoded as RDF triples that specify permissible and required actions under various circumstances, providing structured constraints for reasoning processes.

## Document Processing and Annotation

**Structured Section Identification**: Cases undergo automatic analysis to identify semantic sections according to professional ethics reasoning patterns. The system identifies Facts, Questions, Discussion, and Conclusion sections using pattern recognition and content analysis.

**Entity Recognition and Linking**: Professional entities mentioned in case content (roles, actions, principles, outcomes) are identified and linked to corresponding ontological representations, enabling systematic analysis of ethical relationships and obligations.

**Semantic Annotation**: Case sections receive semantic tags that specify their evidential role within ethical reasoning, enabling targeted retrieval and analysis during system operation.

## Embedding Generation and Storage

**Section-Level Embedding**: Each case section is processed using MiniLM-L6-v2 to generate 384-dimensional semantic embeddings that capture content meaning while maintaining computational efficiency.

**Ontology Concept Embedding**: Professional ethics concepts from the ontology are embedded using the same model to ensure compatibility with case content embeddings and enable direct similarity computation.

**Vector Database Integration**: Embeddings are stored using pgvector with HNSW indices to provide efficient similarity search capabilities across the complete case and ontology corpus.

## Multi-Metric Association Calculation

**Relevance Score Computation**: The system calculates relevance scores between case sections and ontological concepts using the comprehensive multi-metric approach detailed in Section 3.4, combining vector similarity, term overlap, structural relevance, and optional LLM enhancement.

**Threshold Optimization**: Relevance thresholds are calibrated using statistical analysis of score distributions to ensure appropriate sensitivity while maintaining precision in concept association.

**Association Validation**: Computed associations undergo validation to ensure semantic consistency and remove spurious relationships that may arise from processing artifacts.

## Cross-Validation Preparation

**Case Partitioning**: The 20-case dataset is prepared for leave-one-out cross-validation with systematic redaction procedures that remove target sections (conclusion, discussion, or both) while preserving contextual information needed for reasoning.

**Baseline System Preparation**: Standard retrieval-augmented prompts are prepared using the same case database and NSPE Code access but without ontological constraints, ensuring fair comparison between approaches.

**Evaluation Interface Preparation**: Cases are formatted for the online evaluation platform with randomization support and standardized presentation across all evaluation conditions.

## Quality Assurance and Validation

**Processing Validation**: Automated checks verify that document processing correctly identifies case sections, entities, and relationships without introducing systematic errors or biases.

**Ontology Consistency**: The constructed ontology undergoes consistency checking to ensure logical coherence and absence of contradictory constraints that could compromise reasoning quality.

**Embedding Quality Assessment**: Embedding quality is validated through similarity assessment and clustering analysis to ensure that semantic relationships are accurately captured in vector representations.

The preprocessing pipeline creates a systematic foundation for comparative evaluation while maintaining the semantic richness and contextual nuances essential for meaningful professional ethics reasoning assessment.
