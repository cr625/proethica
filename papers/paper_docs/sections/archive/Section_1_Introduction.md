# 1. Introduction

Large language models (LLMs) are increasingly deployed in ethically sensitive domains, from healthcare decision support to legal analysis and engineering safety assessments. However, current systems lack structured mechanisms for incorporating domain-specific ethical obligations into their reasoning processes. A critical failure mode involves treating LLMs as autonomous ethical decision-makers rather than tools that support human judgment within established professional frameworks.

Current LLMs incorporate tool use, response shaping, and reinforcement learning strategies beyond basic transformer architectures (Schick et al., 2023; Yao et al., 2023; Hadji-Kyriacou & Arandjelović, 2024). These enhancements enable high performance across many domains, but they do not provide sufficient transparency or structured control mechanisms for high-stakes ethical applications where professional obligations, legal precedents, and domain-specific constraints must guide reasoning processes.

## 1.2 Gap Analysis

Existing approaches to AI-assisted ethical reasoning exhibit several critical limitations that limit their effectiveness in professional contexts. Current systems lack formal constraint mechanisms for incorporating domain-specific professional obligations into AI reasoning processes. Professional ethics requires specialized knowledge of codes, precedents, and institutional contexts that general-purpose moral reasoning approaches cannot adequately address.

Most LLM-based moral reasoning approaches treat ethical evaluation as general text generation rather than specialized professional decision support. This approach fails to account for the structured, precedent-based reasoning that characterizes professional ethics in domains such as engineering, medicine, and law. Professional ethical reasoning relies heavily on analogical reasoning from precedent cases, where practitioners evaluate current situations by comparing them to established cases and applying lessons learned from previous ethical decisions.

Current systems demonstrate limited integration of ontological knowledge structures with LLM reasoning capabilities, particularly for professional domains that require systematic precedent-based analysis. The temporal dimension of ethical reasoning—how professional standards evolve through case precedents and changing social contexts—remains poorly addressed in existing approaches. Professional ethics codes develop through accumulated case decisions over time, creating complex relationships between historical precedents and current applications.

Existing approaches lack bidirectional validation mechanisms where ethical frameworks can both constrain LLM input and validate LLM outputs against established professional standards. Current systems typically operate in one direction: either using ontologies to structure input or applying post-hoc validation, but not both systematically. This limitation prevents the kind of iterative refinement that characterizes professional ethical reasoning, where practitioners move between abstract principles and concrete case analysis.

## 1.3 Proposed Solution Overview

This paper presents ProEthica, a system that combines LLMs with role-based ontologies for structured ethical reasoning in professional contexts. The approach integrates three key components that address the identified gaps: analogical reasoning from precedent cases, temporal reasoning through historical case progression, and evaluative AI frameworks for evidence-based decision support.

**Analogical Reasoning from Precedent Cases**: Professional ethics relies fundamentally on case-based reasoning where practitioners evaluate current situations by reference to established precedents following the principle of "treat like cases alike" (Aristotle, *Nicomachean Ethics*). ProEthica implements sophisticated analogical reasoning through multi-metric relevance scoring that combines vector similarity, ontological relationships, and structural case analysis to identify relevant precedents and extract applicable principles.

**Temporal Reasoning and Case Progression**: Professional ethical standards evolve through accumulated case decisions and changing social contexts. ProEthica incorporates temporal reasoning by analyzing how professional standards develop over time through case precedents, enabling the system to understand how ethical principles adapt to new situations while maintaining consistency with established frameworks.

**Evaluative AI Framework Integration**: ProEthica's ontological modeling aligns with the evaluative AI paradigm that emphasizes evidence-based decision support rather than autonomous recommendations (Miller, 2023). This approach preserves human agency while providing structured evidence for ethical reasoning. The system's concept-based explanations and multi-metric relevance scoring parallel Visual Evaluative AI's weight of evidence methodology (Le et al., 2024), while the ontology-constrained reasoning reflects cognitive psychology principles for explainable complex systems (Hoffman et al., 2022). ProEthica implements evaluative AI by providing professional ethics evidence and precedent analysis to support human ethical decision-making rather than replacing professional judgment.

The system architecture employs role-grounded ethical obligations encoded as RDF triples that model scenarios in terms of agents, actions, and outcomes. Ontological constraints guide LLM reasoning throughout the process while preserving the natural language capabilities needed for complex ethical analysis. Evaluation and decision-making occur through structured context and professional framework validation rather than autonomous AI judgment.

## 1.4 Key Contributions

This work makes four primary contributions to AI-assisted professional ethical reasoning:

**Professional Ontology Grounding**: ProEthica grounds reasoning in domain-specific professional ontologies and ethical guidelines rather than general moral frameworks, enabling systematic incorporation of professional codes, precedents, and domain-specific obligations into AI reasoning processes.

**Multi-Metric Analogical Reasoning**: The system implements sophisticated analogical reasoning through multi-metric relevance scoring that combines vector similarity, ontological relationship matching, and structural case analysis to identify relevant precedents and extract applicable principles for current ethical dilemmas.

**Bidirectional LLM-Ontology Integration**: ProEthica combines the interpretability and structure of professional ontologies with the flexibility and natural language capabilities of LLMs through bidirectional integration where ontologies both constrain input and validate output.

**Evaluative AI Framework for Professional Ethics**: The approach provides a concrete framework for normative alignment of LLM-assisted systems without granting ethical agency to the model, implementing evaluative AI principles to support rather than replace human professional judgment.