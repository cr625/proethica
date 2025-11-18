# Chapter 2: Literature Review and Related Work

## Introduction

This literature review examines the foundations for professional role ethics in AI systems, establishing how ProEthica's formal knowledge representation D = (R, P, O, S, Rs, A, E, Ca, Cs) emerges from synthesis of computational ethics literature. Tolmeijer et al.'s three-dimensional taxonomy provides valuable analytical structure by examining ethical theories, implementation approaches, and technical aspects simultaneously. This multi-dimensional analysis reveals persistent patterns in machine ethics implementations. Systems tend to favor single ethical theories over hybrid approaches that combine multiple theoretical frameworks. They also favor general-purpose designs over domain-specific implementations tailored to particular professional contexts. The taxonomy highlights the scarcity of frameworks that integrate multiple ethical theories while incorporating domain-specific requirements through stakeholder participation. This gap remains relevant despite subsequent technological advances. The review builds from three seminal works that provide complementary perspectives on professional ethical reasoning. McLaren's (2003) extensional principles for case-based ethical reasoning demonstrates that professional ethics achieves meaning through accumulated precedents rather than abstract theory. Berreby et al.'s (2017) modular architecture for ethical reasoning systems provides systematic framework for organizing ethical components. Through examining these foundational works alongside broader computational ethics literature, this review identifies how current approaches address individual components while revealing critical gaps in their integration.

## 2.1 Foundational Frameworks

### 2.1.1 McLaren's Extensional Principles Approach

McLaren (2003) provides the fundamental insight that professional ethics operates through extensional definition rather than intensional specification of principles. His analysis of National Society of Professional Engineers Board of Ethical Review cases reveals that abstract principles like "hold paramount the safety, health, and welfare of the public" cannot be understood through logical definition alone but require accumulated precedents to achieve concrete meaning. This extensional approach directly challenges computational approaches that attempt to encode ethics as abstract rules, showing instead that professional ethical reasoning operates through analogical comparison to paradigmatic cases.

McLaren identifies nine operationalization techniques that bridge abstract principles to concrete application, addressing the methodological gap identified in Chapter 1. Principle instantiation links abstract principles to clusters of critical facts, showing which situational elements activate ethical considerations. Fact hypotheses specify conditions that modify principle application, recognizing contextual factors that alter standard interpretations. When principles conflict, precedent patterns show resolution strategies. Case instantiation and case grouping demonstrate how professionals use accumulated precedents to guide current decisions. These techniques provide the methodological foundation for transforming abstract principles (P) into concrete obligations (O) through resources (Rs) in ProEthica's formal model.

The extensional definition process McLaren describes explains why current AI tools fail at professional ethics. Large language models can reference professional codes in prompts but cannot enforce them during analysis because they lack the precedent-based reasoning that gives principles meaning (Liu, 2024; Carrell, 2023). Without access to extensional definitions through precedents, systems cannot bridge the gap between abstract principles and concrete application that McLaren identifies as fundamental to professional ethical reasoning.

McLaren's SIROCCO system demonstrates computational implementation of extensional principles through comprehensive ontological representation of engineering ethics concepts and systematic encoding of Board cases. The system's ability to retrieve relevant precedents and predict applicable principles validates that extensional definition can be computationally implemented. However, SIROCCO's limitation to engineering ethics and lack of learning capabilities reveals the need for more general frameworks that can adapt to multiple professional domains while maintaining extensional grounding.

### 2.1.2 Berreby et al.'s Modular Architecture

Berreby et al. (2017) provide architectural framework showing how ethical reasoning components can be systematically organized and integrated. Their ACE (Action-Causality-Ethics) framework demonstrates that complex ethical reasoning emerges from interaction between separable but interconnected modules. This modular approach directly informs ProEthica's nine-component structure by showing how ethical reasoning can be decomposed into manageable components while preserving necessary interactions.

The ACE framework's four modules map directly to ProEthica components. The Action Model, representing agent capabilities and action effects, corresponds to ProEthica's actions (A) and capabilities (Ca). The Causal Model, tracking relationships between events and outcomes, informs the events (E) component and their role in state transitions. The Ethical Model, encoding normative rules and principles, parallels the principles (P) and obligations (O) distinction. The Event Motor, managing temporal evolution, demonstrates how states (S) evolve through event-driven transitions.

Berreby et al.'s emphasis on modularity addresses the integration challenge by showing that ethical reasoning components can be developed independently while maintaining clear interfaces for interaction. This architectural insight enables ProEthica to integrate diverse computational approaches—ontologies for knowledge representation, large language models for natural language understanding, case-based reasoning for precedent application—within a unified framework. The modular architecture also facilitates domain adaptation, as individual modules can be customized for specific professions while maintaining the overall architectural structure.

The framework's sophisticated causal reasoning using Wright's NESS test demonstrates how professional responsibility attribution requires understanding complex causal chains. This causal analysis capability proves essential for professional domains where accountability depends on establishing relationships between actions and outcomes. The separation of causal analysis from ethical evaluation ensures objective assessment before applying normative judgments, a critical requirement for professional ethics where liability and responsibility must be clearly established.

### 2.1.3 Tolmeijer et al.'s Requirements for Ethical Agents

Tolmeijer et al. (2021) establish comprehensive requirements for ethical decision-making agents that directly inform ProEthica's component identification. Their systematic analysis of implemented ethical agents reveals essential capabilities that map to ProEthica's formal components. They identify that ethical agents must possess norm competence (principles P), situational awareness (states S), action repertoires (actions A), and explanation capabilities that draw on authoritative sources (resources Rs).

Their requirement for "norm competence" elaborates how agents must not only store ethical rules but also recognize when they apply, how they conflict, and how to resolve contradictions. This requirement directly motivates ProEthica's distinction between abstract principles (P) that provide high-level guidance and concrete obligations (O) that specify exact requirements. Their analysis shows that successful ethical agents must transform abstract norms into actionable requirements based on context, supporting McLaren's extensional approach.

Tolmeijer et al.'s emphasis on explanation and justification establishes the need for traceable connections to authoritative sources, addressing the third critical gap identified in Chapter 1. They demonstrate that ethical agents operating in professional contexts must justify decisions by referencing established authorities, precedents, and professional standards. This requirement motivates ProEthica's resources (Rs) component as essential for grounding ethical reasoning in professional knowledge rather than abstract philosophical speculation.

Their analysis of learning capabilities in ethical agents reveals that static rule-based systems cannot handle the evolving nature of professional ethics. They show that agents must adapt to new cases, changing standards, and novel situations while maintaining consistency with established principles. This finding supports the need for case-based learning and precedent accumulation that McLaren identifies as fundamental to professional ethical reasoning.

## 2.2 The Nine Components in Literature

### 2.2.1 Roles (R) - Professional Identity in Computational Ethics

The literature extensively documents how professional roles create distinctive ethical obligations that computational systems must recognize and implement. Building on the foundational frameworks, the broader literature provides detailed analysis of role-based ethics in professional contexts.

Oakley and Cocking (2001) establish theoretical foundation showing that professional roles generate specific duties tied to professional goals and practices. Their analysis demonstrates that role morality justifies behaviors within professional contexts that might be unacceptable otherwise, though not without limits. Wendel (2024) extends this analysis, showing how professionals navigate between personal moral standards and institutional obligations, creating what he terms "moral complexity" that computational systems must handle.

Computational approaches to role representation appear throughout the literature. Dennis et al. (2016) formalize roles as filters determining which obligations apply in specific contexts, demonstrating through model checking that role-based filtering ensures ethical compliance. Cointe et al. (2016) develop multi-agent frameworks where roles modify principle interpretation and application. Their work shows that computational role representation requires both static elements (formal position, authorization) and dynamic elements (context-dependent interpretation, temporal validity).

Kong et al. (2020) provide empirical analysis of professional codes across engineering, law, and accounting, identifying common patterns of "identity roles" (provider-client, professional peer, employer relationships) and "identity virtues" (integrity, responsibility, competence). This systematic analysis reveals that roles are not merely job descriptions but complex normative constructs that shape ethical obligations. Their findings directly inform how ProEthica's R component must capture both formal role definitions and their associated ethical implications.

### 2.2.2 Principles (P) - Abstract Ethical Foundations

Following McLaren's extensional approach, the literature reveals consistent challenges in computationally representing abstract ethical principles. The inherent vagueness of principles emerges as a critical issue across multiple studies.

Hallamaa and Kalliokoski (2022) characterize principles by their context-sensitivity and resistance to formal specification, arguing this vagueness enables broad applicability. Taddeo et al. (2024) compare AI ethics principles to constitutional principles requiring interpretation and balancing in specific contexts. They identify three steps in principle operationalization: identifying abstraction levels, interpreting principles to extract requirements, and defining balancing criteria. This analysis directly supports ProEthica's approach of using precedents and cases to provide extensional definitions.

Anderson and Anderson (2018) demonstrate through GenEth that principles can be learned from expert examples rather than explicitly programmed. Their system discovers principles as generalizations from cases where experts agree on correct actions, validating McLaren's thesis about extensional definition. The learned principles maintain traceability to originating cases, providing justification through analogy rather than deduction. This learning approach addresses the limitation of purely ontological approaches that cannot capture the full complexity of professional ethical principles.

Multiple extraction and formalization approaches appear in the literature. Abel et al. (2016) use inductive logic programming to discover principles from expert-labeled cases, generating principles that are complete and consistent. Benzmüller et al. (2020) employ higher-order logic in their LogiKEy framework to formalize principles, enabling formal verification of consistency and entailment relationships. These diverse approaches demonstrate that principle representation requires multiple complementary methods, supporting ProEthica's integration of ontologies, learning, and case-based reasoning.

### 2.2.3 Obligations (O) - Concrete Professional Requirements

The transformation from abstract principles to concrete obligations represents a critical challenge consistently identified in the literature, directly supporting the gap McLaren identifies between abstract and concrete ethical guidance.

Dennis et al. (2016) distinguish between principles as general guidance and obligations as specific requirements, showing that computational systems require explicit transformation mechanisms. They demonstrate that obligations must specify not just what should be done but when, by whom, and under what conditions. This specificity requirement explains why large language models struggle with professional ethics despite being able to reference ethical principles.

Scheutz and Malle (2014) describe obligations as the "moral core" dictating permissible, obligatory, or forbidden actions. Their analysis reveals that professional obligations often conflict, requiring sophisticated resolution mechanisms. Anderson (2006, 2007) and Anderson and Anderson (2011) extensively study the prima facie duty framework, showing how abstract duties transform into specific obligations through contextual weighing of duty intensities. Their -2 to +2 scale for duty satisfaction/violation provides quantitative framework for obligation management.

Ganascia (2007) employs answer set programming to handle conflicting obligations, demonstrating that professional obligations operate as default rules admitting exceptions. Dennis and del Olmo (2021) develop defeasible deontic logic specifically for professional obligations with exceptions, distinguishing strict obligations from defeasible ones. Almpani et al. (2023) show that obligation activation depends on environmental context, with their Event Calculus formalization tracking obligation lifecycles. These approaches collectively demonstrate that obligation management requires sophisticated formal methods beyond simple rule encoding.

### 2.2.4 States (S) - Environmental Context

The literature consistently emphasizes context-dependence in professional ethical evaluation, supporting Berreby et al.'s architectural insight about state representation.

Rao et al. (2023) demonstrate empirically that identical actions receive different moral evaluations depending on situational context. Their findings show that contextual factors can completely reverse ethical valence, challenging context-free approaches to ethics. Almpani et al. (2023) formalize context as environmental states determining which principles activate and how they apply. Their framework shows that states must capture current conditions, historical information, and future projections affecting ethical evaluation.

The Event Calculus emerges as dominant formalism for state representation. Berreby et al. (2017) demonstrate that Event Calculus tracks both persistent properties (inertial fluents) and momentary conditions (non-inertial fluents), capturing full complexity of professional scenarios. Sarmiento et al. (2023) extend this by integrating causal reasoning with state representation, showing that understanding state transitions requires tracking causal relationships between events and effects.

Dennis et al. (2016) prove through formal verification that ethical policies must be parameterized by context, with different policies applying in different states. Their work demonstrates that context-aware ethical reasoning prevents inappropriate rule application, a critical safety property for professional domains. This state-dependent activation of ethical considerations directly supports ProEthica's design where states S interact with roles R and principles P to generate appropriate obligations O.

### 2.2.5 Resources (Rs) - Professional Knowledge Sources

McLaren's emphasis on precedent-based reasoning is extensively supported by literature on case-based reasoning and professional knowledge representation.

Ashley and McLaren (1995) provide foundational analysis showing that ethical expertise involves recognizing relevant similarities between cases rather than applying universal rules. They establish that professional ethical knowledge is largely encoded in cases rather than explicit rules, requiring systems that can learn from and reason with precedents. This finding directly supports ProEthica's resources component as essential for professional ethical reasoning.

Guarini (2006) demonstrates that case-based reasoning handles moral particularism where ethical relevance varies by context. His neural network implementation shows that systems can learn to classify cases without explicit rules, supporting the view that professional ethics operates through pattern recognition. This pattern-based approach complements rule-based methods, suggesting that resources must include both explicit codes and implicit patterns extracted from cases.

Professional codes as resources receive extensive analysis. Davis (1991) shows that codes serve multiple functions beyond rule specification: establishing professional identity, creating accountability mechanisms, and providing deliberation frameworks. Frankel (1989) identifies hierarchical structure in codes from aspirational principles to detailed procedures. Kong et al. (2020) use computational linguistics to extract patterns from professional codes, revealing implicit structure and relationships. These analyses demonstrate that professional codes are complex resources requiring sophisticated representation beyond simple rule lists.

### 2.2.6 Actions (A) - Professional Decisions

The literature reveals multiple dimensions of professional actions that computational systems must represent, supporting Berreby et al.'s action model component.

Bonnemains et al. (2018) provide formal framework for evaluating actions across deontological, consequentialist, and virtue ethics dimensions simultaneously. Their work shows that professional actions require multi-criteria assessment, not single ethical lens evaluation. This multi-dimensional evaluation directly informs ProEthica's approach to action assessment.

The Doctrine of Double Effect, computationally formalized by Govindarajulu and Bringsjord (2017), demonstrates the importance of intention in professional action evaluation. Their work shows that identical actions with identical outcomes can have different ethical status based on intentions, critical for domains like medicine where harmful actions may be justified by beneficial intent.

Sarmiento et al. (2023) provide rigorous formalization of causal relationships between actions and outcomes using Wright's NESS test. Their work demonstrates that professional responsibility requires understanding complex causal chains including overdetermination, prevention, and enabling relationships. This causal analysis capability, inherited from Berreby et al.'s framework, proves essential for liability assessment and accountability in professional domains.

Dawson (1994) argues that professional actions constitute distinct categories with special moral properties, not merely actions performed by professionals. This distinction emphasizes that ProEthica's action component must capture professional meaning and context, not just physical behaviors.

### 2.2.7 Events (E) - Temporal Dynamics

Events as drivers of ethical consideration receive significant attention in the literature, validating Berreby et al.'s event motor concept and Tolmeijer et al.'s requirement for situational awareness.

Zhang et al. (2023) define moral events as occurrences with potential to harm or help agents with moral standing, distinguishing them from ethically neutral occurrences. Their empirical studies show that event classification requires sophisticated understanding of causal relationships and agent intentions. This classification challenge demonstrates why ProEthica needs dedicated event representation beyond simple temporal markers.

Anderson and Anderson (2018) show that ethical evaluation depends on event sequences rather than individual events. Their work on eldercare robots demonstrates that appropriate responses depend on historical context and anticipated future events, requiring temporal awareness. This temporal dependency supports ProEthica's use of Event Calculus for tracking event relationships and their ethical implications.

Govindarajulu and Bringsjord (2017) formalize temporal aspects using modal logic, showing that obligations and permissions have temporal scope affecting their application. Their work demonstrates that professional ethics requires reasoning about not just what happens but when it happens relative to other events. This temporal reasoning capability proves essential for professional domains where timing affects ethical evaluation.

Arkin (2008) emphasizes event documentation for accountability, arguing that autonomous systems must maintain detailed logs for review. His "ethical black box" concept shows that events must be recorded with associated reasoning, not just as raw occurrences. This documentation requirement directly informs ProEthica's event component design.

### 2.2.8 Capabilities (Ca) - Professional Competence

The literature extensively addresses capability requirements for ethical agents, supporting Tolmeijer et al.'s capability requirements and Berreby et al.'s action model.

Epstein (2002) provides influential definition of professional competence as "habitual and judicious use of communication, knowledge, technical skills, clinical reasoning, emotions, values, and reflection in daily practice." This multidimensional view appears throughout professional ethics literature, showing that competence transcends technical skill.

Cervantes et al. (2020) distinguish between capacities (fundamental prerequisites), capabilities (operational abilities), and competencies (professional skills) in artificial moral agents. Their taxonomy provides framework for understanding different ability levels required for professional ethical reasoning. This hierarchical view directly informs ProEthica's capability component structure.

Stenseke (2022) argues that moral agency requires phenomenal consciousness, autonomy, and free will—capabilities current AI lacks. However, he acknowledges "functional competence" enabling appropriate professional behavior without full moral agency. This distinction proves important for implementing ProEthica's capability component within current technological constraints.

Assessment approaches vary across studies. Dennis et al. (2016) employ formal verification to prove capability sufficiency before authorizing actions. Anderson and Anderson (2018) use Ethical Turing Tests assessing whether systems achieve expert-level performance. Abel et al. (2016) demonstrate that capability assessment must consider not just current abilities but learning potential. These diverse assessment methods show that capability validation requires multiple complementary approaches.

### 2.2.9 Constraints (Cs) - Professional Boundaries

The literature identifies multiple constraint types bounding professional behavior, complementing the obligation component by establishing inviolable limits.

Ganascia (2007) distinguishes hard constraints that cannot be violated from soft constraints admitting exceptions. His analysis shows that most professional constraints are defeasible, requiring systems handling exceptions while maintaining compliance. This defeasibility parallels the obligation component but operates at a different level—constraints establish boundaries while obligations specify requirements.

Furbach et al. (2014) analyze deontic constraints specifying obligations, permissions, and prohibitions. They demonstrate that professional constraints often conflict, requiring prioritization mechanisms. Their work shows that constraint conflicts are inherent features of professional ethics requiring systematic management, not errors to eliminate.

Taddeo et al. (2024) examine how legal and regulatory constraints interact with professional ethical requirements. Their analysis reveals that legal compliance may be necessary but insufficient for professional standards, requiring systems navigating multiple constraint systems simultaneously. This multi-system navigation demonstrates why ProEthica needs dedicated constraint component beyond obligation management.

Validation and enforcement approaches include model checking for formal verification (Almpani et al., 2023), architectural "ethical governors" filtering actions (Arkin, 2008), and explanation generation for constraint violations (Dennis and del Olmo, 2021). These approaches show that constraint management requires both preventive and detective controls with explanation capabilities.

## 2.3 Critical Gaps and Integration Challenges

### 2.3.1 The Methodological Gap

The literature reveals the methodological gap that McLaren identifies between abstract principles and concrete application. Despite various approaches to principle representation, systems consistently struggle to bridge from high-level ethical guidance to specific professional decisions.

Current systems demonstrate partial solutions. SIROCCO implements extensional definition through precedents but lacks learning capabilities and domain generality. GenEth learns principles from examples but doesn't integrate with professional codes and precedents. LogiKEy provides formal verification but doesn't handle the case-based reasoning fundamental to professional ethics. These limitations validate the need for integrated approaches combining multiple methods.

The inability of large language models to enforce professional codes during analysis (Liu, 2024; Carrell, 2023) despite referencing them in prompts demonstrates this gap's persistence. Without mechanisms for extensional definition through precedents, systems cannot operationalize abstract principles into concrete guidance. Webb (2023) and Gao (2024) show that even retrieval-augmented generation fails to achieve genuine analogical reasoning, further confirming the methodological gap.

### 2.3.2 Machine Moral Reasoning and LLM Limitations in Professional Ethics

The literature reveals fundamental limitations in current approaches to machine moral reasoning, particularly when applied to professional ethical contexts. These limitations span from crowd-sourced moral learning systems to sophisticated large language models, all failing to capture the structured, precedent-based reasoning required for professional ethics.

Jiang et al. (2025) present Delphi, an AI system trained to predict moral judgments based on crowd-sourced data from US participants, grounded in John Rawls's philosophical framework. While Delphi demonstrates improved generalization over standard language models in predicting human moral preferences, its approach exemplifies the fundamental problems with data-driven moral reasoning systems for professional contexts. The system learns from aggregated human judgments rather than professional codes and precedents, essentially reducing ethics to statistical patterns in crowd preferences. This majoritarian approach cannot capture the specialized reasoning required in professional contexts where decisions must be grounded in established codes, precedents, and domain-specific expertise. Furthermore, Delphi's reliance on US-centric training data raises questions about cultural bias and the universality of its moral judgments, particularly problematic for professional ethics that operates within specific jurisdictional and regulatory frameworks.

The Moral Machine experiment and its extensions (Awad et al., 2018; Ahmad et al., 2024) similarly demonstrate the limitations of crowd-sourced approaches to ethical decision-making. Ahmad et al. (2024) conduct large-scale evaluation of 52 LLMs using the Moral Machine framework, revealing that while larger models show closer alignment with human preferences in trolley-problem scenarios, this alignment does not translate to professional ethical reasoning. The study demonstrates that improvements in model size and training do not address the fundamental architectural limitations in handling the structured, precedent-based reasoning required for professional ethics. These experiments reduce complex professional decisions to simplified dilemmas, missing the nuanced application of professional codes, consideration of precedents, and jurisdictional requirements that characterize real professional ethical reasoning.

Zhou et al. (2024) propose steering LLMs to perform moral reasoning through established moral theories, attempting to move beyond the data-driven approaches exemplified by Delphi. However, their work reveals that even when equipped with theoretical frameworks from deontological, consequentialist, and virtue ethics perspectives, LLMs struggle to apply these theories consistently in complex professional scenarios. The gap between theoretical knowledge and practical application mirrors McLaren's identified methodological gap, showing that access to ethical theories alone does not enable proper professional ethical reasoning without the extensional definitions provided by precedents.

Liu (2024) provides comprehensive survey of LLM safeguarding techniques, demonstrating that despite various guardrail mechanisms, LLMs cannot reliably enforce professional codes during analysis. This inability persists even when codes are explicitly referenced in prompts, as the models lack mechanisms for systematic constraint enforcement. The fundamental issue is architectural: LLMs generate responses through pattern matching rather than through the structured reasoning required for professional ethics, where decisions must trace clear paths from principles through precedents to specific obligations.

Carrell (2023) examines medical LLM applications over a one-year timeline, finding that while models show promise in information retrieval, they fail at the structured ethical reasoning required in clinical decision-making. The study highlights that LLMs cannot maintain consistent application of medical ethics principles across varied scenarios, supporting the need for formal frameworks beyond prompt engineering. This inconsistency proves particularly dangerous in professional contexts where ethical violations carry legal and regulatory consequences.

Webb (2023) investigates emergent analogical reasoning in LLMs, finding that while models can perform simple pattern matching, they lack genuine analogical reasoning capabilities essential for precedent-based professional ethics. The study shows that LLMs struggle with structural mapping between source and target domains, a fundamental requirement for case-based ethical reasoning. This limitation directly undermines the extensional approach McLaren identifies as essential for professional ethics, where principles gain meaning through accumulated precedents rather than abstract definitions.

Gao (2024) provides systematic review of retrieval-augmented generation (RAG) approaches, demonstrating that even with external knowledge retrieval, LLMs struggle with multi-step logical reasoning required for professional ethics. The review identifies specific failure modes where RAG systems cannot maintain reasoning chains when applying retrieved precedents to novel situations. This finding is particularly relevant for professional domains where decisions must trace clear logical paths from principles through precedents to specific obligations.

Batarseh (2021) presents comprehensive taxonomy of AI validation methods, revealing absence of bidirectional integration between constraint mechanisms and validation in current systems. This gap proves critical for professional domains where decisions must be both generated according to constraints and validated against professional standards. The lack of integrated validation mechanisms means that even if LLMs could generate appropriate professional decisions, they cannot verify compliance with professional requirements.

Busuioc (2021) analyzes accountability challenges in algorithmic systems, showing that current AI approaches lack the dual-layer validation required for professional contexts. The work demonstrates that systems need both internal consistency checking and external professional validation, neither of which current LLMs or crowd-sourced moral reasoning systems adequately provide. This accountability gap becomes critical in professional domains where practitioners bear legal and ethical responsibility for AI-assisted decisions.

These limitations collectively demonstrate that neither crowd-sourced moral learning approaches like Delphi nor sophisticated LLMs can address the requirements of professional ethical reasoning. The fundamental issue is not model size, training data volume, or even theoretical grounding, but rather the absence of mechanisms for extensional definition through precedents, systematic constraint enforcement, and traceable reasoning paths that professional ethics demands.

### 2.3.3 Integration Challenges

While individual components receive extensive treatment, the literature reveals limited integration across all nine components. Systems typically address subsets: SIROCCO focuses on principles, obligations, and resources; GenEth emphasizes principles and obligations; ACE framework addresses actions, events, and states. No existing system provides comprehensive integration of all components identified as necessary for professional ethical reasoning.

Tolmeijer et al. (2021) identify this integration challenge, noting that ethical agent requirements span multiple components that must operate coordinately. They show that failures in any component can compromise overall ethical performance. This finding emphasizes that ProEthica's value lies not just in identifying components but in their systematic integration.

The literature also reveals challenges in maintaining consistency across components. When principles generate obligations that conflict with constraints, or when role requirements contradict capability limitations, systems must manage these tensions systematically. Current approaches handle these conflicts locally within components rather than through integrated resolution mechanisms.

### 2.3.4 Domain Adaptation Challenges

The literature reveals tension between domain-specific requirements and general frameworks. Professional ethics varies significantly across domains—medical ethics emphasizes patient autonomy, engineering ethics prioritizes public safety, legal ethics balances advocacy and justice. Yet computational approaches need some generality for practical implementation.

GenEth's domain-independent learning and LogiKEy's meta-logical framework demonstrate potential for general approaches that can be specialized. However, McLaren's work shows that professional ethics is deeply embedded in domain-specific precedents and practices. This tension between generality and specificity remains unresolved in current literature, motivating ProEthica's approach of maintaining general architecture while enabling domain-specific configuration.

## Conclusion

This literature review establishes that ProEthica's formal knowledge representation D = (R, P, O, S, Rs, A, E, Ca, Cs) emerges directly from synthesis of computational ethics literature, with three seminal works providing foundational insights. McLaren's (2003) extensional principles approach demonstrates that professional ethics achieves meaning through accumulated precedents rather than abstract rules, addressing the methodological gap between principles and application. Berreby et al.'s (2017) modular architecture shows how complex ethical reasoning can be decomposed into manageable components while preserving necessary interactions. Tolmeijer et al.'s (2021) requirements establish essential capabilities for ethical agents in professional contexts.

The broader literature validates and elaborates each of the nine components, showing that professional ethical reasoning requires: roles that create distinctive obligations, principles that require extensional definition, obligations that emerge from contextual interpretation, states that capture environmental context, resources that provide precedential knowledge, actions that carry professional meaning, events that drive temporal dynamics, capabilities that ensure competent performance, and constraints that bound acceptable behavior.

Critical gaps identified in the literature—the inability to bridge abstract principles to concrete application, lack of genuine analogical reasoning, and absence of integrated frameworks—motivate ProEthica's synthesis approach. While existing systems address component subsets, none provide comprehensive integration necessary for professional ethical reasoning. This gap between current capabilities and professional requirements establishes the foundation for ProEthica's contribution: a formal framework that integrates all nine components while maintaining the extensional grounding, modular architecture, and systematic requirements that the seminal works identify as essential.