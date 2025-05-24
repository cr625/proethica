# 3. Proposed Approach

## 3.1 Requirements Table

Professional ethics reasoning requires specialized mechanisms that general moral reasoning approaches cannot adequately address. The following table maps ethical reasoning needs to ProEthica components, establishing the conceptual foundation before describing implementation details.

**Table: Mapping Ethical Reasoning Needs to ProEthica Components**

| Ethical Reasoning Need | Why Needed | ProEthica Component |
|------------------------|------------|-------------------|
| **Role-based obligations** | Professional ethics requires domain-specific duties | Role-based ontologies with professional codes extract and formalize duties from canonical ethics documents |
| **Domain specialization** | Different professions have unique ethical frameworks | World-based organization with canonical guidelines for each professional domain |
| **Analogical reasoning** | Legal/ethical precedents inform decisions | Multi-metric relevance scoring combining vector similarity, term overlap, structural relevance, and LLM enhancement |
| **Structured case analysis** | Systematic evaluation prevents oversight | Structured decomposition with document structure annotation |
| **Transparent justification** | Ethical decisions must be explainable | Ontology-constrained prompting with traceable references to specific ethical principles |
| **Bidirectional validation** | LLM outputs must be checked against ethical principles | Ontological admissibility checking validates reasoning against professional frameworks |
| **Constraint enforcement** | LLMs need guidance, not autonomy | Two-way integration where ontology guides LLM input and validates LLM output |
| **Precedent retrieval** | Similar cases inform current decisions | Section-level embedding similarity enables component-specific precedent matching |
| **Professional grounding** | Ethics varies by domain/role | Domain-specific ontology extensions with formalized professional codes |

These requirements derive from identified gaps in current LLM-based ethical reasoning systems and computational ethics literature. Professional ethics requires specialized mechanisms that general moral reasoning approaches cannot adequately address.

### Evaluative AI Framework Integration

ProEthica's ontological modeling aligns with the evaluative AI paradigm that emphasizes evidence-based decision support rather than autonomous recommendations (Miller, 2023). This approach preserves human agency while providing structured evidence for ethical reasoning, addressing the fundamental challenge of incorporating AI capabilities into professional ethical decision-making without compromising human responsibility.

The system's concept-based explanations and multi-metric relevance scoring parallel Visual Evaluative AI's weight of evidence methodology (Le et al., 2024). ProEthica's multi-metric scoring combines vector similarity, ontological relationships, and structural case analysis to provide weighted evidence from multiple sources. This approach enables systematic evaluation of ethical precedents and principles rather than relying on single similarity measures, providing transparent justification for why specific cases or principles are relevant to current ethical decisions.

The ontology-constrained reasoning reflects cognitive psychology principles for explainable complex systems (Hoffman et al., 2022). Professional ethical reasoning involves complex relationships between abstract principles, domain-specific obligations, and concrete case contexts. ProEthica's structured approach mirrors human professional reasoning patterns by organizing evidence according to established cognitive frameworks, enabling professionals to understand and validate AI-generated analysis through familiar reasoning structures.

## 3.2 Conceptual Framework

ProEthica implements a world-based domain organization approach that transforms professional ethics guidelines into structured ontological representations. This transformation enables constraint-based reasoning over LLM outputs while preserving the natural language capabilities needed for complex ethical analysis.

### World-Based Domain Organization

The system organizes professional ethics knowledge through "worlds." These are self-contained domains that encapsulate the ontological structures, canonical guidelines, and case precedents specific to a professional field. Each world represents a cohesive ethical framework derived from authoritative sources.

For engineering ethics, the NSPE world encompasses the complete NSPE Code of Ethics, Board of Ethical Review cases, and derived ontological relationships. This domain-specific organization enables targeted ethical reasoning within established professional boundaries while maintaining flexibility to extend to additional professional domains.

### Professional Ethics Formalization Process

The transformation from canonical guidelines to operational ontologies follows a systematic pipeline. Professional codes undergo automated analysis to identify key entities, relationships, and constraints. The system extracts roles such as Engineer, Client, and Public. It identifies principles including Public Safety, Professional Competence, and Honesty. The system also extracts obligations like Report Safety Concerns and Maintain Confidentiality, along with contextual conditions such as Budget Constraints and Time Pressure.

Extracted concepts are formalized as RDF triples encoding semantic relationships. Examples include "Engineer hasObligation PublicSafety" and "Client hasRight Confidentiality." These triples represent fundamental professional relationships that constrain ethical reasoning.

Cases undergo automatic structural analysis using Basic Formal Ontology (BFO) principles. The analysis identifies Facts, Issues, Rules, Analysis, and Conclusion (FIRAC) components. This segmentation enables precise matching between case components and ontological elements.

### Bidirectional LLM-Ontology Integration

The framework implements bidirectional integration where ontological knowledge both constrains LLM inputs and validates LLM outputs. This two-way relationship ensures that reasoning remains grounded in professional ethical frameworks while leveraging LLM capabilities for flexible analysis.

Relevant ontological concepts, professional obligations, and precedent patterns are integrated into LLM prompts. This integration provides structured context that guides reasoning toward ontologically consistent conclusions. Generated reasoning undergoes validation against professional ethics constraints. This process ensures consistency with established principles and identifies potential conflicts with professional standards.

**Figure 1: System Architecture Overview** *(To be created)*  
*Illustrates the complete ProEthica architecture showing world-based organization, bidirectional LLM-ontology integration, and the flow from canonical guidelines through ontological constraints to supported ethical reasoning.*

## 3.3 Concrete Example Scenario

This section demonstrates ProEthica's complete processing pipeline through NSPE Case 23-4 "Acknowledging Errors in Design," which involves an engineer's obligations regarding design errors that may have contributed to worker injury. This walkthrough illustrates how the system transforms abstract professional ethics frameworks into concrete reasoning support.

### Case Background and Structure

**NSPE Case 23-4 Overview**: Engineer T worked on a project where a worker was subsequently injured. Questions arise about Engineer T's obligations to acknowledge potential design errors that may have contributed to the injury. The case involves complex ethical considerations including professional competence, public safety, honesty, and disclosure obligations.

**FIRAC Structure Identification**: The system automatically identifies the case's structure following the Facts, Issues, Rules, Analysis, and Conclusion (FIRAC) format standard in professional ethics cases. The Facts section describes Engineer T's design approach and subsequent worker injury. The Issues section poses three specific ethical questions about error acknowledgment and professional obligations.

### ProEthica Processing Pipeline Demonstration

**Step 1: World Activation and Context Loading**

The system activates the NSPE engineering ethics world, loading the complete professional framework including the NSPE Code of Ethics, historical precedents from previous Board of Ethical Review cases involving similar ethical issues, ontological relationships formalized between roles, obligations, principles, and contextual factors, and professional standards with domain-specific interpretations of ethical principles in engineering contexts.

**Step 2: Document Processing and Structure Annotation**

The system processes the case text to identify structural components through automatic FIRAC annotation. Each component undergoes embedding generation for similarity matching with precedent cases and ontological concepts. This enables precise alignment between case components and relevant professional framework elements.

**Step 3: Ontological Mapping and Relevance Calculation**

The system identifies relevant NSPE Code provisions through multi-metric scoring including I.1 Public Safety ("Engineers must hold paramount the safety, health, and welfare of the public"), II.3.a Professional Competence ("Engineers shall undertake assignments only when qualified"), III.1.a Honesty ("Engineers shall be objective and truthful in professional reports"), and III.8 Disclosure Obligations ("Engineers shall disclose all known or potential conflicts").

For each Code provision, the system calculates vector similarity (cosine similarity between case text and provision embeddings), term overlap (weighted overlap of key professional terminology), structural relevance (alignment between case components and provision applications), and ontological distance (relationship strength in professional ethics ontology).

**Step 4: Precedent Retrieval and Analogical Analysis**

Vector embeddings identify analogous Board of Ethical Review cases including Case 78-3 (design error disclosure in construction projects), Case 91-7 (professional competence and error acknowledgment), and Case 03-2 (public safety obligations in design review). The system analyzes how these precedent cases define professional obligations in error situations, balance competing interests such as client confidentiality versus public safety, apply NSPE Code provisions to specific contexts, and establish patterns for ethical decision-making.

**Step 5: Ontology-Constrained Reasoning Generation**

The LLM receives comprehensive structured context including professional framework elements with relevance scores, precedent patterns with analogical reasoning connections, FIRAC-structured current case information, constraints from professional obligations and ethical boundaries, and evidence weights through multi-metric relevance scores for all components.

The LLM generates analysis that remains consistent with established NSPE standards, incorporates relevant precedent patterns, addresses specific ethical questions posed in the case, provides structured justification for reasoning conclusions, and maintains professional terminology and argumentation patterns.

**Step 6: Validation and Evidence-Based Output**

Generated reasoning undergoes validation against professional ethics constraints for consistency with NSPE Code provisions, alignment with precedent case patterns, professional terminology and framework compliance, and logical coherence of ethical argumentation.

The system produces structured evidence including relevant principles (applicable NSPE Code provisions with justification), precedent analysis (similar cases and their reasoning patterns), professional obligations (specific duties derived from engineering ethics framework), and reasoning support (structured evidence to support human ethical decision-making).

### Example Output Comparison

**Traditional LLM Response** (unconstrained): "Engineer T should probably acknowledge the error because honesty is important and people might be hurt."

**ProEthica Evidence-Based Output**: "Based on NSPE Code I.1 (Public Safety) and III.1.a (Honesty), Engineer T has professional obligations to acknowledge potential design errors. Precedent Case 78-3 establishes that engineers must prioritize public welfare over client preferences when safety concerns arise. The multi-metric analysis indicates high relevance (0.87) between current case facts and established disclosure obligations. Professional framework analysis suggests three specific actions with detailed evidence-based recommendations and precedent justification."

This concrete example illustrates how ProEthica transforms abstract professional ethics frameworks into practical decision support tools that enhance rather than replace human professional judgment in complex ethical situations.

## 3.4 Technical Implementation

The technical implementation employs a Model Context Protocol (MCP) architecture to enable systematic integration between ontological knowledge and LLM reasoning processes. This section details the technical mechanisms that realize the conceptual framework described above.

### MCP-Enabled Ontology Access

The Model Context Protocol server exposes specialized tools organized into four categories. Knowledge Query Tools retrieve entities, relationships, and facts from professional ethics ontologies. Relationship Analysis Tools analyze ontological relationships and find connections between ethical concepts. Case Analysis Tools extract and match ethical concepts from case content. Ethics-Specific Tools provide domain-specific tools for professional ethics analysis.

This tool ecosystem enables systematic ontology access without requiring the LLM to directly manage complex knowledge graph traversal or relationship reasoning.

### Orchestrated Reasoning Workflow

The system implements a deterministic workflow where application logic determines ontology tool usage patterns rather than delegating tool selection to the LLM. This orchestrated approach provides reliability through predictable behavior patterns and graceful degradation when ontology services are unavailable, falling back to direct LLM processing with pre-fetched context.

All relevant ontological knowledge is provided upfront, ensuring that LLM reasoning operates with complete contextual awareness of applicable professional ethics constraints. The deterministic workflow enables systematic tracking of which ontological knowledge influenced specific reasoning steps, supporting transparency requirements for professional ethics applications.

### Constraint Enforcement Mechanisms

ProEthica enforces ontological constraints through complementary mechanisms. Professional ethics principles, role-based obligations, and relevant precedent cases are systematically integrated into LLM prompts using structured formats that guide reasoning toward ontologically consistent conclusions.

Generated reasoning undergoes validation against ontological constraints, where claims are checked for consistency with established professional ethics frameworks and precedent patterns. The system provides analogical context from similar cases, enabling case-based reasoning patterns that align with established professional ethics practices.

### Multi-Dimensional Vector Integration

The system implements sophisticated vector similarity capabilities that support both exact and approximate nearest neighbor search across multiple embedding spaces. Document sections are embedded using MiniLM-L6-v2 to generate 384-dimensional representations that capture semantic content while remaining computationally efficient for similarity search.

Ontological concepts are embedded using the same model to ensure compatibility with section embeddings, enabling direct similarity computation between case content and professional ethics concepts. The pgvector database employs HNSW (Hierarchical Navigable Small World) indices that provide logarithmic search complexity while maintaining high recall for similarity queries.

### Implementation Characteristics

This MCP-enabled architecture provides several characteristics that distinguish it from traditional LLM approaches to ethical reasoning. Reasoning is systematically anchored in established professional ethics frameworks rather than general moral intuitions. Complex ontological relationships are made accessible to LLM reasoning without requiring the model to navigate knowledge graph complexities directly.

The systematic integration of ontological knowledge provides clear traceability for how professional ethics principles influence reasoning outcomes. The tool-based architecture enables extension to new professional domains by developing domain-specific ontology tools while maintaining consistent reasoning patterns.