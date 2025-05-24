# Section 1: Introduction

## 1.1 Problem Context

Large language models (LLMs) are now being applied in ethically sensitive domains such as healthcare and engineering, wherein failure may result in substantial material or ethical harm \cite{abbott_reasonable_2020, haltaufderheide_ethics_2024, kampelopoulos_review_2025, waser_implementation_2014}. In medicine and mental health, LLMs are proposed for tasks such as clinical decision support, diagnostic reasoning, and therapeutic dialogue \cite{lawrence_opportunities_2024}. In engineering and construction, they have been used for hazard recognition, energy modeling, and robotic sequencing \cite{kampelopoulos_review_2025}. Applications in these contexts raise concerns about the reliability, accountability, and regulatory adequacy of LLM use in professional environments within established normative constraints \cite{taddeo_ai_2024}. Despite promising performance, documented errors and misuse cases, such as false medical facts and unsafe engineering suggestions, highlight unresolved risks to safety, equity, and trust \cite{haltaufderheide_ethics_2024}.

These models are also increasingly embedded in workflows that interact with legal and institutional frameworks, raising the need for explicit alignment with professional standards \cite{dubber_oxford_2020, zhang_mm-llms_2024, osman_computational_2024}. The introduction of AI-based systems into these domains without corresponding mechanisms for normative validation and explanation has prompted concerns about accountability, transparency, and value alignment \cite{prem_ethical_2023, vishwanath_towards_2023}. A critical failure mode involves treating LLMs as autonomous ethical decision-makers rather than tools that support human judgment within established professional frameworks.

Current LLMs incorporate tool use, response shaping, and reinforcement learning strategies beyond basic transformer architectures \cite{schick_toolformer_2023, yao_react_2023, hadji-kyriacou_would_2024, li_representation_2024}. These enhancements enable high performance across many domains, but they do not provide sufficient transparency or structured control mechanisms for high-stakes ethical applications where professional obligations, legal precedents, and domain-specific constraints must guide reasoning processes.

## 1.2 Gap Analysis

Current systems do not meet the reasoning requirements of professional ethical practice. These limitations fall into three main areas.

**Formal Constraint Mechanisms**: Most systems do not support formal constraint mechanisms. LLMs cannot enforce domain-specific standards without structured knowledge integration. General purpose prompts may reference codes or rules, but there is no mechanism to verify consistency with those standards \cite{puri_moral_2020, dennis_formal_2016}. The absence of formal representation, whether in legal, medical or engineering contexts, undermines trust and limits usability in regulated environments \cite{dubber_oxford_2020, bruckert_next_2020}. Current systems lack formal constraint mechanisms for incorporating domain-specific professional obligations into AI reasoning processes.

**Analogical Reasoning from Precedent**: LLMs lack analogical reasoning grounded in precedent. Although some systems retrieve example cases, few compare cases structurally or apply lessons from precedent in a verifiable way \cite{chiarello_future_2024}. Even advanced retrieval systems do not trace or align reasoning paths across cases \cite{fraser_does_2022}. This deficiency is significant in professional domains that rely on analogy, such as law and engineering, where ethical analysis routinely involves comparison to prior decisions and articulated justifications. Professional ethical reasoning relies heavily on analogical reasoning from precedent cases, where practitioners evaluate current situations by comparing them to established cases and applying lessons learned from previous ethical decisions.

**Bidirectional Validation**: Most systems do not support bidirectional validation. Although some apply rules to input or postprocess output for compliance, few systems do both. This asymmetry prevents feedback loops and weakens the alignment between system output and professional expectations \cite{chhabra_evaluating_2024}. Without structured interaction between input constraint and output admissibility, the reasoning process remains opaque and unaccountable. Existing approaches lack bidirectional validation mechanisms where ethical frameworks can both constrain LLM input and validate LLM outputs against established professional standards.

Although recent systems increasingly incorporate mechanisms beyond transformer-based text generation, including tool use, reinforcement learning, and structured scaffolding \cite{schick_toolformer_2023, yao_react_2023, hadji-kyriacou_would_2024, li_representation_2024}, these remaining gaps reflect a deeper symbolic-structural disconnect. Professional duties are compositional, contextual, and often involve weighing conflicting obligations. LLMs, in contrast, rely on pattern completion, shortcut learning, and statistically grounded approximations. Bridging this gap requires systems that integrate symbolic knowledge structures, support analogical precedent matching, and allow for constraint-based validation during both generation and interpretation.

## 1.3 Proposed Solution Overview

This paper presents ProEthica, a system that combines LLMs with role-based ontologies for structured ethical reasoning in professional contexts. The approach integrates three key components that address the identified gaps: analogical reasoning from precedent cases, temporal reasoning through historical case progression, and evaluative AI frameworks for evidence-based decision support.

**Analogical Reasoning from Precedent Cases**: Professional ethics relies fundamentally on case-based reasoning where practitioners evaluate current situations by reference to established precedents following the principle of "treat like cases alike". ProEthica implements sophisticated analogical reasoning through multi-metric relevance scoring that combines vector similarity, ontological relationships, and structural case analysis to identify relevant precedents and extract applicable principles.

**Temporal Reasoning and Case Progression**: Professional ethical standards evolve through accumulated case decisions and changing social contexts. ProEthica incorporates temporal reasoning by analyzing how professional standards develop over time through case precedents, enabling the system to understand how ethical principles adapt to new situations while maintaining consistency with established frameworks.

**Evaluative AI Framework Integration**: ProEthica's ontological modeling aligns with the evaluative AI paradigm that emphasizes evidence-based decision support rather than autonomous recommendations. This approach preserves human agency while providing structured evidence for ethical reasoning. The system's concept-based explanations and multi-metric relevance scoring parallel Visual Evaluative AI's weight of evidence methodology, while the ontology-constrained reasoning reflects cognitive psychology principles for explainable complex systems. ProEthica implements evaluative AI by providing professional ethics evidence and precedent analysis to support human ethical decision-making rather than replacing professional judgment.

The system architecture employs role-grounded ethical obligations encoded as RDF triples that model scenarios in terms of agents, actions, and outcomes. Ontological constraints guide LLM reasoning throughout the process while preserving the natural language capabilities needed for complex ethical analysis. Evaluation and decision-making occur through structured context and professional framework validation rather than autonomous AI judgment.

## 1.4 Key Contributions

This work makes four primary contributions to AI-assisted professional ethical reasoning:

**Professional Ontology Grounding**: ProEthica grounds reasoning in domain-specific professional ontologies and ethical guidelines rather than general moral frameworks, enabling systematic incorporation of professional codes, precedents, and domain-specific obligations into AI reasoning processes.

**Multi-Metric Analogical Reasoning**: The system implements sophisticated analogical reasoning through multi-metric relevance scoring that combines vector similarity, ontological relationship matching, and structural case analysis to identify relevant precedents and extract applicable principles for current ethical dilemmas.

**Bidirectional LLM-Ontology Integration**: ProEthica combines the interpretability and structure of professional ontologies with the flexibility and natural language capabilities of LLMs through bidirectional integration where ontologies both constrain input and validate output.

**Evaluative AI Framework for Professional Ethics**: The approach provides a concrete framework for normative alignment of LLM-assisted systems without granting ethical agency to the model, implementing evaluative AI principles to support rather than replace human professional judgment.

## 1.5 Paper Organisation

This paper is organized as follows. Section 2 reviews background work in computational ethics, case-based reasoning systems, and LLM-based moral reasoning. Section 3 presents our proposed approach, including requirements analysis, conceptual framework, and technical implementation. Section 4 describes our study methodology, including research hypothesis, corpus preparation, and evaluation metrics. Section 5 presents results from our evaluation on NSPE engineering ethics cases. Section 6 discusses implications and positions our work relative to existing approaches. Section 7 concludes with limitations and future work directions.

---

**Section Status**: Complete with all citations integrated
- ✅ **1.1 Problem Context**: Complete with all LaTeX citations
- ✅ **1.2 Gap Analysis**: Restored to three main areas with all citations  
- ✅ **1.3 Proposed Solution Overview**: Complete
- ✅ **1.4 Key Contributions**: Complete
- ✅ **1.5 Paper Organisation**: Complete

**Citation Updates**: 
- Added all citations from LaTeX source to appropriate locations
- Removed fake Rawte et al. reference
- Maintained three-area gap analysis structure as in original
- Ready for bibliography compilation
