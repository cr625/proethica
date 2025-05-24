# 3.1 Requirements and Conceptual Framework

## 3.1.1 Requirements for Professional Ethics Reasoning

**Table: Mapping Ethical Reasoning Needs to ProEthica Components**

| Ethical Reasoning Need | Why Needed | ProEthica Component |
|------------------------|------------|-------------------|
| **Role-based obligations** | Professional ethics requires domain-specific duties | Role-based ontologies with professional codes extract and formalize duties from canonical ethics documents |
| **Domain specialization** | Different professions have unique ethical frameworks | World-based organization with canonical guidelines for each professional domain |
| **Analogical reasoning** | Legal/ethical precedents inform decisions | Multi-metric relevance scoring combining vector similarity, term overlap, structural relevance, and LLM enhancement |
| **Structured case analysis** | Systematic evaluation prevents oversight | Structured decomposition with document structure annotation |
| **Transparent justification** | Ethical decisions must be explainable | Ontology-constrained prompting with traceable references to specific ethical principles |
| **Bidirectional validation** | LLM outputs must be checked against ethical principles | Ontological admissibility checking validates reasoning against professional frameworks |
| **Constraint enforcement** | LLMs need guidance, not autonomy | Two-way integration: ontology guides LLM input, validates LLM output |
| **Precedent retrieval** | Similar cases inform current decisions | Section-level embedding similarity enables component-specific precedent matching |
| **Professional grounding** | Ethics varies by domain/role | Domain-specific ontology extensions with formalized professional codes |

These requirements derive from identified gaps in current LLM-based ethical reasoning systems and computational ethics literature. Professional ethics requires specialized mechanisms that general moral reasoning approaches cannot adequately address.

## 3.1.2 Evaluative AI Framework Integration

ProEthica's ontological modeling aligns with the evaluative AI paradigm that emphasizes evidence-based decision support rather than autonomous recommendations (Miller, 2023). This approach preserves human agency while providing structured evidence for ethical reasoning, addressing the fundamental challenge of incorporating AI capabilities into professional ethical decision-making without compromising human responsibility.

**Evidence-Based Decision Support Paradigm**: The evaluative AI framework positions AI systems as tools for evidence analysis and presentation rather than autonomous decision-makers (Miller, 2023). ProEthica implements this paradigm by providing comprehensive evidence from professional ethics codes, precedent cases, and ontological relationships to support human ethical reasoning rather than generating autonomous ethical judgments. This approach addresses concerns about delegating moral responsibility to AI systems while leveraging computational capabilities for systematic evidence analysis.

**Concept-Based Explanations and Weight of Evidence**: The system's concept-based explanations and multi-metric relevance scoring parallel Visual Evaluative AI's weight of evidence methodology (Le et al., 2024). ProEthica's multi-metric scoring combines vector similarity, ontological relationships, and structural case analysis to provide weighted evidence from multiple sources. This approach enables systematic evaluation of ethical precedents and principles rather than relying on single similarity measures, providing transparent justification for why specific cases or principles are relevant to current ethical decisions.

**Cognitive Psychology Principles for Explainable Systems**: The ontology-constrained reasoning reflects cognitive psychology principles for explainable complex systems (Hoffman et al., 2022). Professional ethical reasoning involves complex relationships between abstract principles, domain-specific obligations, and concrete case contexts. ProEthica's structured approach mirrors human professional reasoning patterns by organizing evidence according to established cognitive frameworks, enabling professionals to understand and validate AI-generated analysis through familiar reasoning structures.

**Professional Ethics Evidence Integration**: ProEthica implements evaluative AI principles by providing systematic analysis of professional ethics evidence and precedent patterns to support human ethical decision-making rather than replacing professional judgment. The system organizes complex ethical information according to professional frameworks, enabling practitioners to access relevant precedents, applicable principles, and contextual considerations in structured formats that support rather than supplant human ethical reasoning capabilities.

## 3.1.3 Conceptual Architecture Overview

ProEthica implements a world-based domain organization approach that transforms professional ethics guidelines into structured ontological representations. This transformation enables constraint-based reasoning over LLM outputs while preserving the natural language capabilities needed for complex ethical analysis.

**World-Based Domain Organization**: The system organizes professional ethics knowledge through "worlds" - self-contained domains that encapsulate the ontological structures, canonical guidelines, and case precedents specific to a professional field. Each world represents a cohesive ethical framework derived from authoritative sources. For engineering ethics, the NSPE world encompasses the complete NSPE Code of Ethics, Board of Ethical Review cases, and derived ontological relationships. This domain-specific organization enables targeted ethical reasoning within established professional boundaries while maintaining flexibility to extend to additional professional domains.

**Bidirectional LLM-Ontology Integration**: The framework implements bidirectional integration where ontological knowledge both constrains LLM inputs and validates LLM outputs. This two-way relationship ensures that reasoning remains grounded in professional ethical frameworks while leveraging LLM capabilities for flexible analysis. Constraint application integrates relevant ontological concepts, professional obligations, and precedent patterns into LLM prompts, providing structured context that guides reasoning toward ontologically consistent conclusions. Output validation ensures generated reasoning undergoes validation against professional ethics constraints, maintaining consistency with established principles and identifying potential conflicts with professional standards.

**Professional Ethics Formalization Process**: The transformation from canonical guidelines to operational ontologies follows a systematic pipeline. Guideline analysis extracts key entities, relationships, and constraints from professional codes. RDF triple generation formalizes extracted concepts as semantic relationships. Document structure annotation using Basic Formal Ontology (BFO) principles identifies Facts, Issues, Rules, Analysis, and Conclusion (FIRAC) components. Multi-metric association calculation establishes connections between abstract principles and concrete case content through comprehensive scoring approaches.

**Figure 1: System Architecture Overview** *(To be created)*  
*Illustrates the complete ProEthica architecture showing world-based organization, bidirectional LLM-ontology integration, and the flow from canonical guidelines through ontological constraints to supported ethical reasoning.*

This conceptual framework establishes the foundation for systematic professional ethics reasoning by combining the flexibility of LLM capabilities with the structured constraints of professional ethical frameworks, enabling principled ethical analysis within established professional boundaries.
