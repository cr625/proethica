# Section 5: Related Work

This section examines existing approaches to computational ethics and LLM-based moral reasoning, positioning ProEthica's contributions within the broader landscape of AI systems designed to support ethical decision-making. We organize our analysis around three key themes: case-based and ontological approaches to professional ethics, LLM-based moral reasoning systems, and recent comparative evaluations of different methodologies for ethical decision support.

## 5.1 Case-Based and Ontological Approaches to Professional Ethics

Professional ethics has long relied on precedent-based reasoning, making case-based approaches particularly suitable for computational implementation. Early systems like MedEthEx employed inductive logic programming to model medical ethics using Beauchamp and Childress' biomedical principles (Anderson, 2005), while GenEthEx provided general ethical dilemma analysis across domains (Anderson & Anderson, 2018). Most directly relevant to our work, SIROCCO (McLaren, 2003) implemented case-based evaluative reasoning specifically for NSPE engineering ethics cases, demonstrating the viability of computational approaches to professional ethical reasoning.

Recent advances in ontological modeling for professional ethics have moved beyond abstract ethical principles toward domain-specific frameworks. The IEEE 7007-2021 Ontological Standard exemplifies this approach, providing structured representations of ethical considerations for cyber-physical systems (Houghtaling et al., n.d.; Prestes et al., n.d.). Similarly, the Ontology of Professional Judicial Knowledge (OPJK) demonstrates how complex legal knowledge can be organized ontologically for practical application (Casellas, 2011; Vallbé et al., 2010).

Contemporary work has developed sophisticated case-oriented models like the Case-Oriented Ontological Model (COOM) and Hyper-Knowledge Graph System (HKGS), which capture event, relational, and positional attributes in AI ethics cases, enabling exploration of correlations between cases and dynamic visual analysis (Chen et al., 2024). These systems demonstrate the potential for ontological structures to organize professional ethics precedents systematically.

**ProEthica's Advancement**: While these systems provide important foundations, ProEthica advances the field through bidirectional LLM-ontology integration that combines the interpretability of structured ontologies with the flexibility of neural language models. Our multi-metric relevance scoring goes beyond simple case matching to include vector similarity, ontological relationships, and structured document analysis, enabling more nuanced analogical reasoning than previous case-based systems.

## 5.2 LLM-Based Moral Reasoning Systems

The integration of large language models into moral reasoning represents a significant shift from rule-based to data-driven approaches. Early systems like Delphi (Jiang et al., 2022) demonstrated that language models could learn to present descriptive views of ethical judgments from human text data, while Kaleidoscope (Sorensen et al., 2023) addressed value pluralism in AI ethics evaluation.

Recent research has moved toward more sophisticated approaches that address contextual dependencies and alignment challenges. Rao et al. (2023) developed iterative self-distillation methods for understanding when moral rule-breaking becomes acceptable, addressing the fundamental challenge of context-dependent moral evaluation. This work demonstrates the potential for language models to learn nuanced ethical reasoning beyond simple rule application.

### Contemporary Comparative Evaluations

Recent comparative studies provide important insights into different approaches for LLM-based ethical reasoning. A systematic comparison of prompt engineering, RAG, and fine-tuning using LLaMA 3 8B for mental health text analysis revealed significant trade-offs: fine-tuning achieved highest accuracy (91% for emotion classification, 80% for condition detection) but required substantial computational resources, while RAG offered more flexible deployment with moderate performance (40-68% accuracy) but showed high dependency on retrieval quality (arXiv:2503.24307, 2025).

For moral judgment alignment, a 2025 study using AITA subreddit data compared RAG-enhanced GPT-4o against direct prompting for replicating community moral judgments. The RAG approach achieved superior performance (83% accuracy, 0.469 MCC) compared to direct prompting (77% accuracy, 0.357 MCC) by providing relevant precedent cases as context. This demonstrates the value of precedent-based reasoning for aligning LLM moral judgments with human consensus.

Recent work has also explored hybrid architectures combining LLMs with symbolic reasoning frameworks. A 2025 review of CBR-LLM integration (arXiv:2504.06943) proposes theoretical advantages for moral reasoning, including enhanced transparency through precedent-based justification and improved domain adaptation. The review cites evidence from medical triage and legal question answering showing that providing relevant case context improves both accuracy and user trust in LLM analysis.

### Evaluation of LLM Moral Reasoning Quality

Comprehensive evaluation of frontier LLMs on real-world ethical dilemmas reveals both capabilities and limitations. Du et al. (2025) evaluated multiple LLMs (GPT-4o-mini, Claude-3.5-Sonnet, Deepseek-V3, Gemini-1.5-Flash) on 196 academic research ethics cases using structured components (Key Factors, Historical Perspectives, Resolution Strategies). Their findings show that while LLMs effectively capture high-level ethical concepts, they struggle with in-depth analysis requiring historically grounded reasoning and strategic recommendations. GPT-4o-mini demonstrated the most consistent performance across metrics.

Bias evaluation studies reveal systematic issues in LLM ethical decision-making. Yan et al. (2025) compared GPT-3.5 Turbo and Claude 3.5 Sonnet on ethical dilemmas involving protected attributes, finding significant biases in both models through 11,200 experimental trials. GPT-3.5 Turbo showed preferences aligned with traditional power structures, while Claude 3.5 Sonnet demonstrated more diverse choices but reduced ethical sensitivity in complex intersectional scenarios.

Multilingual evaluation using the Multilingual Moral Reasoning Benchmark (MMRB) revealed significant inconsistencies in LLM moral reasoning across languages, with particular challenges in low-resource languages (arXiv:2504.19759). This highlights the context-dependent nature of current LLM moral reasoning capabilities.

**ProEthica's Distinction**: Unlike general moral reasoning systems, ProEthica specifically targets professional ethics through domain-specific ontological grounding. Our approach addresses the limitations identified in recent evaluations—lack of historical grounding, insufficient precedent integration, and inconsistent reasoning quality—through structured professional frameworks and bidirectional validation mechanisms.

## 5.3 Hybrid Systems and Integration Approaches

The limitations of purely statistical or purely symbolic approaches have driven recent interest in hybrid systems that combine multiple reasoning modalities. Integration of case-based reasoning with neural language models represents a promising direction for improving transparency and reliability in ethical reasoning systems.

Molineaux et al. (2024) demonstrate successful alignment of AI systems with human decision-makers in military medical triage scenarios, showing how case-based reasoning can be integrated with AI systems to support ethical decision-making in high-stakes professional contexts. Their work provides evidence that hybrid approaches can achieve better human-AI collaboration in ethically sensitive domains.

The theoretical framework for CBR-augmented LLM agents suggests advantages over Chain-of-Thought prompting and standard RAG approaches, particularly for tasks requiring transparent justification of moral decisions (arXiv:2504.06943). CBR integration promises precedent-based explanations that can be traced to specific historical cases, addressing the "black box" problem in neural ethical reasoning.

**ProEthica's Contribution**: Our system advances hybrid integration through novel bidirectional mechanisms where ontological frameworks both constrain LLM input and validate LLM output. This two-way integration ensures that professional ethical reasoning remains grounded in established frameworks while leveraging LLM capabilities for contextual analysis and natural language generation.

## 5.4 Evaluation Methodologies and Benchmarks

Recent work has developed sophisticated evaluation approaches for LLM moral reasoning. The Priced Survey Methodology (PSM) adapts economic choice theory to analyze LLM responses to ethical questions as choices under constraints, enabling assessment of reasoning consistency and quantification of "moral stances" across 39 LLMs (arXiv:2412.04476). This methodology revealed a "shared core" in LLM moral reasoning but also meaningful variations in consistency and ethical profiles.

Specialized benchmarks have emerged for different aspects of ethical evaluation. The ETHICS dataset suite provides multilingual evaluation across moral dimensions, while protected attribute dilemma scenarios assess bias in ethical decision-making (arXiv:2501.10484). Real-world ethical dilemma benchmarks use expert-segmented analysis to evaluate LLM performance on complex cases requiring nuanced resolution strategies (arXiv:2505.08106).

**ProEthica's Evaluation Innovation**: Our evaluation approach differs from existing benchmarks by focusing on professional context alignment rather than general moral reasoning. We employ leave-one-out validation on authentic professional ethics cases with participant assessment of reasoning quality, persuasiveness, and alignment with expert professional judgments. This evaluation strategy directly measures the system's effectiveness for its intended professional decision-support role.

### 5.4.1 Rationale for Domain-Specific Evaluation vs. General Moral Reasoning Benchmarks

While the benchmarks described above provide valuable insights into general LLM moral reasoning capabilities, they are not suitable for evaluating ProEthica's specific contributions for several methodological and theoretical reasons:

**Domain Specificity Requirements**: Existing benchmarks like the ETHICS dataset suite, AITA scenarios, and PSM questions focus on general moral reasoning or interpersonal conflicts rather than professional ethical decision-making. Professional ethics operates under domain-specific frameworks with specialized obligations, precedent structures, and accountability mechanisms that differ fundamentally from general moral reasoning. Evaluating ProEthica on general moral benchmarks would not capture its core innovation: structured integration of professional ethical frameworks with LLM reasoning capabilities.

**Precedent-Based vs. Principle-Based Reasoning**: General moral reasoning benchmarks typically evaluate principle-based ethical reasoning (deontological, consequentialist, virtue-based), while professional ethics relies heavily on precedent-based reasoning where similar cases inform current decisions. ProEthica's multi-metric relevance scoring and ontology-constrained reasoning are specifically designed for professional precedent matching, making evaluation on principle-based benchmarks methodologically inappropriate.

**Evaluation Target Mismatch**: Existing benchmarks evaluate LLM autonomous moral judgment capabilities, while ProEthica is designed as a professional decision-support tool that preserves human agency in ethical decision-making. The system's effectiveness must be measured by how well it supports professional decision-makers through structured evidence and precedent analysis, not by its ability to make autonomous moral choices.

**Professional Context Requirements**: Professional ethical reasoning involves specialized knowledge of domain-specific codes, regulatory frameworks, and institutional contexts that are absent from general moral reasoning benchmarks. The NSPE engineering ethics cases we use contain technical, legal, and professional context that cannot be captured in general-purpose moral dilemma scenarios.

**Authentic Stakeholder Evaluation**: Professional decision-support systems require evaluation by relevant professional communities or those who understand professional contexts. General moral reasoning benchmarks often use crowd-sourced judgments or expert philosophers' assessments, which may not align with professional ethical decision-making standards in engineering, medicine, law, or other specialized domains.

**System Architecture Evaluation**: ProEthica's bidirectional LLM-ontology integration, multi-metric relevance scoring, and structured document analysis represent novel technical contributions that require specialized evaluation. General moral reasoning benchmarks cannot assess these architectural innovations or their effectiveness in professional contexts.

Therefore, our domain-specific evaluation using authentic NSPE cases with professional context assessment provides the most appropriate methodology for measuring ProEthica's intended contributions to AI-assisted professional ethical decision-making.

## 5.6 Limitations in Precedent-Based Professional Ethics Integration

Despite advances in AI applications across professional domains, current systems demonstrate significant limitations in leveraging the precedent-based reasoning that characterizes professional ethics in legal, medical, and engineering contexts. This gap represents a fundamental challenge for AI-assisted ethical decision-making in professional settings.

### Legal Domain Challenges

Recent research reveals substantial difficulties in AI systems' ability to engage with legal precedent effectively. A 2024 study on precedent search in Chinese law found practitioners expressing dissatisfaction with current AI legal tools, citing their "end-to-end" nature that lacks intermediate control and raises concerns about trustworthiness and ethics in high-stakes legal domains. The study specifically chose "precedent search" as a use case requiring better human-AI collaboration, indicating current systems' inadequacy for this fundamental legal reasoning task.

Legal AI systems face additional challenges in their interaction with precedent-based reasoning. Analysis of AI systems' integration with traditional legal frameworks reveals that AI technology applies computational models rather than legal reasoning as understood in jurisprudence, with AI systems not "reasoning" or "interpreting" in the human sense. This fundamental disconnect challenges "the foundation of precedent" in legal decision-making, highlighting the gap between statistical pattern matching and genuine precedent-based reasoning.

Furthermore, AI systems trained on historical legal data can perpetuate and amplify existing biases present in past decisions, leading to problematic applications of precedent. Research on AI ethics in legal decision-making demonstrates how historical patterns of discrimination can create outcomes that perpetuate injustice, representing a flawed interaction with legal precedent that undermines the ethical foundations of precedent-based reasoning.

### Medical and Healthcare Ethics

Medical AI systems face similar challenges in applying ethical precedents effectively. The "black box" nature of many AI models complicates clinical decision-making and accountability, creating barriers to understanding how ethical precedents or established best practices are being applied. Research on AI in healthcare highlights issues including biased training data leading to unfair recommendations and problems with informed consent when patients cannot understand AI's role—all factors that impede trustworthy precedent-based ethical reasoning.

The opacity of AI systems creates particular challenges for medical ethics, where precedent-based reasoning often involves weighing complex contextual factors and competing values. Current AI approaches struggle with the nuanced interpretation, contextual understanding, and value-based judgments inherent in applying medical ethical precedents to novel situations.

### Engineering and Safety-Critical Systems

While engineering ethics literature may not explicitly use the term "precedent-based reasoning," the field relies heavily on learning from past failures, applying codes of ethics informed by historical cases, and adapting established principles to novel situations. Current AI systems demonstrate limitations in this type of reasoning, particularly in safety-critical contexts where ethical decision-making must incorporate lessons from historical engineering failures and established professional precedents.

Research on AI in safety-critical systems, such as autonomous vehicles, reveals difficulties in programming AI to handle novel ethical dilemmas that don't perfectly match training data. This limitation directly relates to the inability to generalize from or appropriately adapt established precedents to new contexts—a fundamental requirement for professional engineering ethics.

### Systemic Limitations in Current Approaches

These domain-specific challenges reflect broader systemic limitations in how current AI systems engage with precedent-based reasoning. Most systems perform pattern matching or statistical analysis rather than engaging in genuine reasoning about the principles underlying precedents. The reduction of ethics to mathematically expressible constraints fundamentally alters the nature of moral reasoning, failing to capture the richness of precedent-based human ethical reasoning that characterizes professional practice.

**ProEthica's Response to These Limitations**: Our approach directly addresses these identified gaps through structured integration of professional ethical frameworks with LLM reasoning capabilities. By combining ontological constraints with case-based precedent matching, ProEthica enables more sophisticated analogical reasoning that preserves the contextual richness of professional ethical precedents while leveraging AI capabilities for analysis and synthesis.

## 5.5 Positioning ProEthica's Contributions

ProEthica addresses gaps identified across multiple research streams in computational ethics and LLM-based reasoning:

**Professional Domain Grounding**: Unlike general moral reasoning systems that treat ethical evaluation as general text generation, ProEthica grounds reasoning in domain-specific professional obligations and precedent patterns derived from canonical ethical frameworks.

**Bidirectional Integration**: Most existing approaches use unidirectional methods—either ontology-guided input or output validation, but not both. ProEthica implements bidirectional integration where professional frameworks constrain LLM reasoning and validate outputs against established ethical principles.

**Structured Precedent Reasoning**: While recent work demonstrates the value of precedent-based reasoning (RAG studies), ProEthica advances beyond simple retrieval through multi-metric relevance scoring that combines vector similarity, term overlap, structural relevance, and ontological relationships for more sophisticated analogical matching.

**Transparent Professional Decision Support**: Rather than autonomous ethical decision-making, ProEthica positions LLMs as tools for evidence-based ethical analysis within established professional frameworks, addressing calls for transparent, accountable AI in high-stakes domains.

**Systematic Evaluation Framework**: Our evaluation methodology directly assesses professional decision-support effectiveness through authentic case analysis and participant evaluation of reasoning quality, providing a more targeted evaluation than general moral reasoning benchmarks.

These contributions position ProEthica as a novel approach that bridges the gap between structured professional ethics frameworks and flexible natural language reasoning capabilities, offering a principled path toward AI-assisted ethical decision support in professional contexts.