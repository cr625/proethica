# 3.2 ProEthica Conceptual Framework

ProEthica implements a world-based domain organization approach that transforms professional ethics guidelines into structured ontological representations. This transformation enables constraint-based reasoning over LLM outputs. The conceptual framework addresses the challenge of bridging between unstructured ethical guidelines and machine-interpretable constraints.

## World-Based Domain Organization

The system organizes professional ethics knowledge through "worlds." These are self-contained domains that encapsulate the ontological structures, canonical guidelines, and case precedents specific to a professional field. Each world represents a cohesive ethical framework derived from authoritative sources.

For engineering ethics, the NSPE world encompasses the complete NSPE Code of Ethics, Board of Ethical Review cases, and derived ontological relationships. This domain-specific organization enables targeted ethical reasoning within established professional boundaries. The approach maintains flexibility to extend to additional professional domains.

## Professional Ethics Formalization Process

The transformation from canonical guidelines to operational ontologies follows a systematic pipeline.

**Guideline Analysis and Concept Extraction**: Professional codes undergo automated analysis to identify key entities, relationships, and constraints. The system extracts roles such as Engineer, Client, and Public. It identifies principles including Public Safety, Professional Competence, and Honesty. The system also extracts obligations like Report Safety Concerns and Maintain Confidentiality, along with contextual conditions such as Budget Constraints and Time Pressure.

**RDF Triple Generation**: Extracted concepts are formalized as RDF triples encoding semantic relationships. Examples include "Engineer hasObligation PublicSafety" and "Client hasRight Confidentiality." These triples represent fundamental professional relationships that constrain ethical reasoning.

**Document Structure Annotation**: Cases undergo automatic structural analysis using Basic Formal Ontology (BFO) principles. The analysis identifies Facts, Issues, Rules, Analysis, and Conclusion (FIRAC) components. This segmentation enables precise matching between case components and ontological elements.

**Multi-Metric Association Calculation**: The system computes relevance scores between case sections and ontological concepts. This process uses the comprehensive scoring approach detailed in Section 3.4. The calculation establishes connections between abstract principles and concrete case content.

## Bidirectional LLM-Ontology Integration

The framework implements bidirectional integration where ontological knowledge both constrains LLM inputs and validates LLM outputs. This two-way relationship ensures that reasoning remains grounded in professional ethical frameworks while leveraging LLM capabilities for flexible analysis.

**Constraint Application**: Relevant ontological concepts, professional obligations, and precedent patterns are integrated into LLM prompts. This integration provides structured context that guides reasoning toward ontologically consistent conclusions.

**Output Validation**: Generated reasoning undergoes validation against professional ethics constraints. This process ensures consistency with established principles and identifies potential conflicts with professional standards.

## Concrete Example of NSPE Case Analysis

NSPE Case 23-4 "Acknowledging Errors in Design" involves an engineer's obligations regarding design errors that may have contributed to worker injury. The ProEthica pipeline processes this case through several steps.

**World Activation**: The system activates the NSPE engineering ethics world. This loads relevant professional obligations, ethical principles, and precedent cases specific to engineering practice.

**Document Processing**: Automatic annotation identifies the case structure. The Facts section describes Engineer T's design approach and subsequent worker injury. The Questions section poses three specific ethical questions about error acknowledgment. The Discussion section provides analysis incorporating precedent cases. The Conclusion section presents the NSPE Board determination.

**Ontological Mapping**: The system identifies relevant NSPE Code provisions including I.1 Public Safety, II.3.a Professional Competence, III.1.a Honesty, and III.8 Disclosure Obligations. The system calculates the relevance of these provisions to each case section using multi-metric scoring.

**Precedent Retrieval**: Vector embeddings identify similar historical Board of Ethical Review cases. These cases involve design errors, safety concerns, and disclosure obligations. The identified cases provide analogical context for ethical reasoning.

**Constrained Reasoning**: The LLM receives structured context including case facts, relevant ethical principles, precedent patterns, and professional obligations. Reasoning is constrained to remain consistent with established NSPE standards.

**Validation and Output**: The system validates generated analysis against ontological constraints. The output provides structured evidence supporting ethical decision-making rather than autonomous ethical judgment.

## Evaluative AI Integration

The conceptual framework aligns with evaluative AI principles by providing structured evidence and precedent analysis to support human ethical decision-making. The system implements evidence-based decision support that preserves human agency while enhancing the systematic consideration of relevant ethical factors.

This approach reflects the evaluative AI paradigm emphasis on hypothesis-driven decision support. AI systems provide comprehensive evidence analysis to support human reasoning rather than autonomous recommendations.

**Figure 1: System Architecture Overview** *(To be created)*  
*Illustrates the complete ProEthica architecture showing world-based organization, bidirectional LLM-ontology integration, and the flow from canonical guidelines through ontological constraints to supported ethical reasoning.*

The conceptual framework establishes the foundation for systematic professional ethics reasoning. The approach combines the flexibility of LLM capabilities with the structured constraints of professional ethical frameworks. This combination enables principled ethical analysis within established professional boundaries.
