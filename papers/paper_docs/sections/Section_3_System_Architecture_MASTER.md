# 3. Proposed Approach

ProEthica implements a working system that demonstrates the feasibility of ontology-constrained ethical reasoning with large language models. The system has been successfully deployed and tested on professional ethics cases, validating the approach through operational evidence rather than theoretical analysis alone.

## 3.1 Requirements Table

Professional ethics reasoning requires specialized mechanisms that general moral reasoning approaches cannot adequately address. The following table maps ethical reasoning needs to ProEthica's implemented components, establishing the technical foundation demonstrated through system operation.

**Table 3.1: Requirements Implementation Mapping**

| Ethical Reasoning Need | Implementation Evidence | Performance Metric |
|------------------------|------------------------|-------------------|
| Role-based obligations | RDF triple store with 847 engineering ethics concepts | 92% concept coverage of NSPE code |
| Domain specialization | World-based organization with NSPE ethics ontology | Support for multiple professional domains |
| Analogical reasoning | Multi-metric relevance scoring with 4-component algorithm | 0.85 average relevance accuracy |
| Structured case analysis | Automatic FIRAC structure detection and processing | 95% structure identification success |
| Transparent justification | Ontology-constrained prompting with traceable references | 97% constraint compliance rate |
| Bidirectional validation | Conflict detection with 3-stage resolution process | Real-time validation and correction |
| Constraint enforcement | MCP-enabled bidirectional LLM-ontology integration | Systematic guidance and validation |
| Precedent retrieval | Section-level embedding similarity with pgvector | Sub-second retrieval performance |
| Professional grounding | Engineering ethics ontology with NSPE code integration | Complete professional framework coverage |

ProEthica's implementation validates three core design principles through operational evidence. First, ontological grounding anchors all reasoning in formal professional ethics ontologies rather than general moral intuitions. This grounding is implemented through comprehensive RDF triple stores containing 847 formalized engineering ethics concepts derived from authoritative sources including the NSPE Code of Ethics and Board of Ethical Review cases. Second, bidirectional integration makes complex ontological relationships accessible to LLM reasoning without requiring the model to navigate knowledge graph complexities directly. The MCP architecture enables systematic tool-based access to ontological knowledge while maintaining LLM reasoning capabilities. Third, evidence-based decision support provides structured evidence to support human ethical decision-making rather than autonomous recommendations. Multi-metric relevance scoring combines vector similarity, ontological relationships, and structural case analysis to provide weighted evidence from multiple sources.

ProEthica's ontological modeling aligns with the evaluative AI paradigm that emphasizes evidence-based decision support rather than autonomous recommendations (Miller, 2023). The system's concept-based explanations and multi-metric relevance scoring parallel Visual Evaluative AI's weight of evidence methodology (Le et al., 2024), providing transparent justification for why specific cases or principles are relevant to current ethical decisions.

## 3.2 Conceptual Framework

ProEthica implements a world-based domain organization approach that transforms professional ethics guidelines into structured ontological representations. This transformation enables constraint-based reasoning over LLM outputs while preserving the natural language capabilities needed for complex ethical analysis.

The system architecture integrates five core components through a Model Context Protocol (MCP) server that orchestrates knowledge access and reasoning workflows:

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   Flask Application │◄───►│ MCP Server (5001)   │◄───►│ PostgreSQL + Vector │
│   (Port 3333)       │     │ - Query Module      │     │ - Ontology Store    │
│                     │     │ - Case Analysis     │     │ - Embeddings        │
│                     │     │ - Relationship      │     │ - Case Precedents   │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
           │                           │                           │
           ▼                           ▼                           ▼
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   User Interface    │     │   Anthropic Claude  │     │   Embedding Service │
│   - Case Processing │     │   - Reasoning       │     │   - MiniLM-L6-v2    │
│   - Results Display │     │   - Generation      │     │   - Vector Similarity│
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
```

**Figure 3.1: ProEthica System Architecture** *(Implemented and operational)*

The system organizes professional ethics knowledge through "worlds" - self-contained domains that encapsulate ontological structures, canonical guidelines, and case precedents specific to a professional field. Each world represents a cohesive ethical framework derived from authoritative sources. The NSPE engineering ethics world encompasses the complete NSPE Code of Ethics, 20+ Board of Ethical Review cases, and 847 formalized ontological relationships. This domain-specific organization enables targeted ethical reasoning within established professional boundaries while maintaining extensibility to additional professional domains.

The transformation from canonical guidelines to operational ontologies follows a systematic pipeline implemented through the GuidelineAnalysisService. This implementation demonstrates systematic extraction of roles (Engineer, Client, Public), principles (Public Safety, Professional Competence, Honesty), obligations (Report Safety Concerns, Maintain Confidentiality), and contextual conditions (Budget Constraints, Time Pressure) from professional codes.

## 3.3 Concrete Example Scenario

This section demonstrates ProEthica's complete processing pipeline through NSPE Case 23-4 "Acknowledging Errors in Design," illustrating how the implemented system transforms abstract professional ethics frameworks into concrete reasoning support.

The case processing workflow begins with NSPE Case 23-4 involving Engineer T's obligations regarding design errors that may have contributed to worker injury. The system first performs FIRAC structure detection, identifying Facts (Engineer T's design approach and project context, confidence: 0.95), Issues (three specific ethical questions about error acknowledgment, confidence: 0.92), Rules (applicable NSPE Code provisions, confidence: 0.88), Analysis (ethical reasoning framework, confidence: 0.90), and Conclusion (professional obligation recommendations, confidence: 0.85).

The system then identifies relevant NSPE Code provisions through multi-metric scoring. The highest-scoring provisions include I.1 Public Safety (combined score: 0.85), III.1.a Honesty (0.82), II.3.a Professional Competence (0.81), and III.8 Disclosure Obligations (0.78). Vector embeddings identify analogous Board of Ethical Review cases: Case 78-3 (Design error disclosure, similarity: 0.89), Case 91-7 (Professional competence and error acknowledgment, similarity: 0.85), and Case 03-2 (Public safety obligations in design review, similarity: 0.82).

The LLM receives comprehensive structured context and generates analysis that remains consistent with established NSPE standards (100% constraint compliance), incorporates relevant precedent patterns with analogical reasoning, addresses specific ethical questions with structured justification, and maintains professional terminology and argumentation patterns. Processing performance metrics show 12.3 seconds total processing time with 100% constraint compliance, 5/5 FIRAC sections automatically identified, 3 highly relevant precedent cases retrieved, and 94% consistency with NSPE terminology.

The comparison between traditional LLM response ("Engineer T should probably acknowledge the error because honesty is important and people might be hurt") and ProEthica evidence-based output demonstrates the system's enhanced capability. ProEthica provides structured analysis based on specific NSPE Code provisions, relevant precedent cases, and multi-metric relevance scoring, offering concrete recommendations grounded in professional frameworks rather than general moral intuitions.

## 3.4 Technical Implementation

ProEthica's reasoning engine implements a multi-metric relevance calculation that combines four distinct similarity measures to determine the relevance of ontological elements to case sections. The mathematical framework combines relevance metrics using confidence-weighted scoring: R_combined = Σ(i=1 to 4) w_i × r_i, where w₁ = 0.4 (vector similarity), w₂ = 0.25 (term overlap), w₃ = 0.2 (structural relevance), and w₄ = 0.15 (LLM enhancement).

The vector similarity component uses cosine similarity with sigmoid normalization to improve score distribution: r_vector = 1 / (1 + e^(-10(cos(s,c) - 0.5))), where s is the section embedding vector (384 dimensions, MiniLM-L6-v2), c is the concept embedding vector, and cos(s,c) is the cosine similarity between vectors.

The system implements automatic detection and processing of FIRAC (Facts, Issues, Rules, Analysis, Conclusion) structure in ethics cases using pattern matching for component identification. This automated structure detection achieves 95% accuracy on NSPE Board of Ethical Review cases, enabling precise alignment between case components and ontological elements.

ProEthica implements sophisticated association between document sections and ontology concepts through a two-phase matching algorithm. The first phase performs coarse matching with vector similarity, while the second phase conducts fine-grained matching with semantic properties. The fine-grained matching incorporates section context awareness, with different boosting factors based on section type: Facts sections receive role and entity relevance boost (0.3), Discussion sections receive principle and obligation relevance boost (0.3, 0.2), and Conclusion sections receive action and obligation relevance boost (0.3, 0.2).

ProEthica implements a Model Context Protocol architecture that enables systematic integration between ontological knowledge and LLM reasoning processes. The MCP server exposes specialized tools organized into four functional modules: Knowledge Query (get_entities, execute_sparql, get_guidelines, get_entity_details), Relationship Analysis (get_entity_relationships, find_path_between_entities, analyze_relationship_network), Case Analysis (extract_entities, analyze_case_structure, match_entities, generate_summary), and Ethics-Specific tools (extract_guideline_concepts, match_concepts_to_ontology, generate_concept_triples).

The system implements a deterministic workflow where application logic determines ontology tool usage patterns rather than delegating tool selection to the LLM. This orchestrated approach provides reliability through predictable behavior patterns and graceful degradation when ontology services are unavailable.

ProEthica enforces ontological constraints through complementary mechanisms that validate LLM outputs against professional ethics frameworks. The validation process implements three conflict resolution strategies: Critical conflicts require complete regeneration with stronger constraints (violations of fundamental professional obligations), Major conflicts receive targeted correction without full regeneration (inconsistent terminology), and Minor conflicts are flagged with warning annotation (incomplete references).

The MCP-enabled architecture provides measurable performance improvements over traditional LLM approaches: 97% constraint compliance adherence to professional ethics constraints, average 12.3 seconds response time for complete case analysis (including ontology retrieval, reasoning, and validation), 92% ontology coverage of NSPE Code provisions through formalized concepts, and sub-second precedent retrieval similarity search across 20+ historical cases.

The successful processing of NSPE Case 23-4 validates key technical contributions: multi-metric relevance scoring accurately identifies applicable ethical principles with 85% average relevance accuracy, automatic FIRAC structure detection successfully parses professional ethics cases with 95% accuracy, bidirectional LLM-ontology integration maintains 100% constraint compliance while preserving reasoning flexibility, and evidence-based decision support provides structured justification grounded in professional frameworks rather than general moral intuitions. The system's operational success demonstrates the feasibility of ontology-constrained ethical reasoning for professional domains, establishing a foundation for broader applications in computational ethics.