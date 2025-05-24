# 2. Background and Related Work

## 2.1 Computational Ethics and Role Theory

### Computational Ethics Framework
Computational ethics represents an interdisciplinary effort to translate ethical theory into machine-operable representations, addressing the computational complexity of moral reasoning and decision-making (Stenseke, 2024). This field has evolved from early attempts at formalizing ethical principles to sophisticated approaches that recognize the inherent complexity and context-dependency of moral judgments. Contemporary computational ethics emphasizes the integration of multiple approaches, from rule-based systems to case-based reasoning, acknowledging that different ethical challenges may require different computational strategies.

### Role-Based Ethics: Foundations and Applications
Role-based ethics, with historical roots traceable to ancient philosophy including Epictetus, emphasizes duty tied to social and professional roles rather than universal moral principles (Peterson, 2017). This approach recognizes that individuals occupy multiple roles simultaneously as professionals, community members, and private individuals, each carrying distinct moral obligations that may sometimes conflict.

Contemporary research has demonstrated the practical importance of role-based ethics in professional contexts. Cooper and Marder (2023) examine role morality discrepancy in professional purchasing decisions, showing how individuals experience tension between personal moral standards and professional role expectations. Their work reveals that felt responsibility in professional contexts is significantly influenced by how individuals interpret their role-based obligations, supporting the theoretical foundation that professional ethics requires domain-specific approaches rather than universal moral frameworks.

### Case-Based Reasoning in Practical Ethics
A foundational approach to computational ethics involves case-based reasoning (CBR), which draws on the principle of treating like cases alike, a concept traceable to Aristotelian ethics (Ashley & McLaren, 1995). Ashley and McLaren's seminal work on CBR knowledge representation for practical ethics established that practical ethical reasoning often involves comparative evaluation of problems rather than deductive application of abstract principles. This approach recognizes that ethical principles can be inconsistent or poorly defined in their antecedents, making pure deductive reasoning insufficient for complex moral decisions.

The CBR approach to ethics is particularly relevant in professional domains where abstract principles must be applied to concrete factual scenarios. As Ashley and McLaren (1995) demonstrate, practical ethical reasoning supplements weak analytic models with comparative evaluation, allowing decision-makers to construct arguments by comparing current problems to past paradigmatic cases. This approach implements a form of bottom-up ethical decision-making that complements top-down principle-based approaches.

### Professional Ethics and Contextual Evaluation
Role-based ethics operates not as a universal standard but through localized professional obligations that vary by domain, role responsibilities, and situational context (Wallach & Allen, 2009). This contextual variation makes role-based ethics particularly suitable for ontological modeling, where domain-specific ethical frameworks can capture the nuanced obligations that characterize different professional roles.

The integration of role-based ethics with computational approaches requires structured modeling of professional roles, duties, and contextual evaluation mechanisms. This includes the development of ontological representations that can capture both the explicit rules of professional codes and the implicit knowledge embedded in precedent cases and expert decision-making patterns.

## 2.2 Prior Systems

### Case-Based Ethical Reasoning Systems

Early computational ethics systems established foundational approaches for automated ethical analysis across diverse domains. **MedEthEx** implemented ILP-based ethical modeling for medical decision support, incorporating Beauchamp and Childress' principles of biomedical ethics (Anderson, 2005). **GenEth** provided general ethical dilemma analysis using inductive logic programming to codify ethical principles across domains (Anderson & Anderson, 2018). **SIROCCO** represents a particularly relevant precedent, as McLaren's (2003) computational model for extensionally defining principles and cases in ethics was specifically designed for case-based evaluative reasoning using NSPE engineering ethics cases.

Additional systems include medical ethics AI frameworks that incorporate case-based reasoning and domain-specific ethical principles (Waser, 2014), and contemporary machine ethics surveys showing diverse approaches from rule-based to learning-based systems (Tolmeijer et al., 2021). SIROCCO demonstrated the viability of computational approaches to professional ethical reasoning within established frameworks using the same NSPE engineering ethics cases that we employ in our evaluation.

### Ontological Approaches to Professional Ethics

Research on using domain ontologies and knowledge graphs to structure professional ethics content for AI systems represents a practical alternative to encoding universal ethical principles directly in ontologies. This approach focuses on organizing professional codes, case precedents, and domain-specific ethical frameworks rather than abstract moral reasoning.

**Professional Domain Standards**: The IEEE 7007-2021 Ontological Standard provides a pioneering framework for ethically driven robotics and automation systems, emphasizing domain-specific ontologies that include ethical considerations such as data privacy, transparency, responsibility, and accountability tailored to cyber-physical systems (Houghtaling et al., 2021; Prestes et al., 2021). This standard exemplifies how ontological structures can support ethically aligned design in specific professional domains.

**Legal Knowledge Ontologies**: The development of the Ontology of Professional Judicial Knowledge (OPJK) demonstrates how ontologies can represent complex legal knowledge, facilitating management and application of legal information in e-government and e-democracy contexts (Casellas, 2011; Vallbé et al., 2010). This approach shows how domain-specific ontological structures can organize professional knowledge for practical application.

**Case-Oriented Ontological Models**: The Case-Oriented Ontological Model (COOM) and Hyper-Knowledge Graph System (HKGS) are designed to model AI ethics cases by capturing event, relational, and positional attributes, allowing exploration of correlations between cases and providing dynamic visual analysis of ethical issues across domains (Chen et al., 2024). These models demonstrate how ontological structures can organize case precedents for professional ethics applications.

**Requirements Engineering Approaches**: Ontology-based Requirements Engineering (ObRE) applies ontological analysis to unpack ethicality requirements in AI systems, focusing on specific ethical principles like Beneficence, Non-maleficence, Explicability, and Autonomy, providing guidelines for requirements elicitation and analysis in software development (Guizzardi et al., 2023).

**Professional Ethics by Design**: The concept of "Professional Ethics by Design" advocates for co-creation of codes of conduct for computational practice across various fields, emphasizing development of professional ethics frameworks specific to computational practices rather than relying on abstract ethical principles (Danzon-Chambaud & Foissac, 2023).

## 2.3 LLM-Based Moral Reasoning

This section focuses on systems that use LLMs and language models to assist with ethical reasoning and moral decision-making, rather than approaches for making AI systems themselves more ethical (such as Constitutional AI or alignment research).

### Early Language Model-Based Moral Reasoning Systems
Early systems established foundational approaches for encoding moral knowledge in language models. **Delphi** (Jiang et al., 2022) represented commonsense moral reasoning trained to present a descriptive view of ethical judgments, representing early attempts to encode moral knowledge in language models trained on human text data. **Kaleidoscope** (Sorensen et al., 2023) addressed value pluralism evaluation framework for AI ethics, tackling the challenge of multiple competing ethical frameworks. **DIT and DailyDilemmas** provided datasets and benchmarks for testing ethical reasoning maturity in language models, establishing standardized evaluation approaches.

### Contemporary Language Model Approaches to Moral Reasoning
Recent research has expanded beyond standalone moral reasoning models toward more sophisticated approaches that address contextual disambiguation and value alignment. Rao et al. (2023) present iterative self-distillation methods for understanding when moral rule-breaking becomes acceptable, demonstrating how language models can learn to distinguish between contexts where identical actions may have different moral evaluations. This work addresses a fundamental challenge in computational ethics, namely the context-dependency of moral judgments.

The measurement and evaluation of value alignment in AI systems has become a critical research area. Peterson and Gärdenfors (2024) provide frameworks for measuring value alignment in AI systems, offering methodological approaches for assessing how well AI reasoning aligns with human moral judgments. Their work establishes important foundations for evaluating the effectiveness of language model-based moral reasoning systems.

### Virtue Ethics and Learning-Based Approaches
Contemporary research has explored virtue ethics as a promising framework for artificial moral agents due to its emphasis on learning from experience and adapting to complex human norms (Stenseke, 2023). This approach connects directly to the capabilities of language models, which learn patterns of human values and norms from vast amounts of human text data. Stenseke's work on artificial virtuous agents bridges classical virtue ethics theory with modern machine implementation, providing theoretical foundations for language model-based moral agents.

The "bottom-up" approach to machine ethics emphasizes creating environments where agents learn moral values and norms from data or experience rather than being explicitly programmed with rules. Language models, trained on extensive human text corpora, inherently embody this bottom-up learning approach by capturing patterns of human moral reasoning and value expression embedded in natural language.

### Hybrid and Integration Approaches
Current research increasingly favors hybrid systems that combine learned patterns from language models (bottom-up) with explicit rules or principles (top-down). This aligns with the broader trend toward integrating multiple methodological approaches in AI systems for complex domains like moral reasoning (Davis-Stober et al., 2024).

### Recent Advances in AI-Human Alignment for Ethical Decision-Making
Contemporary research has moved beyond standalone LLM moral reasoning toward systems that align with human decision-makers in specific professional contexts. Molineaux et al. (2024) present significant advances in aligning AI systems to human decision-makers in military medical triage scenarios, demonstrating how case-based reasoning can be integrated with AI systems to support ethical decision-making in high-stakes professional contexts.

### Limitations of Current LLM-Based Approaches
Despite these advances, current LLM-based moral reasoning systems face several key limitations. Most systems treat ethical reasoning as general text generation rather than specialized professional decision support grounded in domain-specific obligations and precedents. Existing approaches lack formal mechanisms to ensure that AI reasoning aligns with established professional ethical frameworks and precedent cases. While systems show promise in learning moral patterns from text, they do not systematically integrate the rich precedent-based reasoning that characterizes established professional ethics domains.

Current systems typically generate moral reasoning without systematic post-hoc validation against professional ethical frameworks and established precedent patterns. Although work like Rao et al. (2023) addresses contextual moral reasoning, most systems lack the structured constraint mechanisms needed for professional contexts where decisions must be traceable to specific ethical principles.

## 2.4 Related Work on Validation Methodologies

### Contemporary Comparative Evaluations

Recent comparative studies provide important insights into different approaches for LLM-based ethical reasoning. A systematic comparison of prompt engineering, RAG, and fine-tuning using LLaMA 3 8B for mental health text analysis revealed significant trade-offs. Fine-tuning achieved highest accuracy (91% for emotion classification, 80% for condition detection) but required substantial computational resources, while RAG offered more flexible deployment with moderate performance (40-68% accuracy) but showed high dependency on retrieval quality (arXiv:2503.24307, 2025).

For moral judgment alignment, a 2025 study using AITA subreddit data compared RAG-enhanced GPT-4o against direct prompting for replicating community moral judgments. The RAG approach achieved superior performance (83% accuracy, 0.469 MCC) compared to direct prompting (77% accuracy, 0.357 MCC) by providing relevant precedent cases as context. This demonstrates the value of precedent-based reasoning for aligning LLM moral judgments with human consensus.

Recent work has also explored hybrid architectures combining LLMs with symbolic reasoning frameworks. A 2025 review of CBR-LLM integration (arXiv:2504.06943) proposes theoretical advantages for moral reasoning, including enhanced transparency through precedent-based justification and improved domain adaptation. The review cites evidence from medical triage and legal question answering showing that providing relevant case context improves both accuracy and user trust in LLM analysis.

### Evaluation of LLM Moral Reasoning Quality

Comprehensive evaluation of frontier LLMs on real-world ethical dilemmas reveals both capabilities and limitations. Du et al. (2025) evaluated multiple LLMs (GPT-4o-mini, Claude-3.5-Sonnet, Deepseek-V3, Gemini-1.5-Flash) on 196 academic research ethics cases using structured components (Key Factors, Historical Perspectives, Resolution Strategies). Their findings show that while LLMs effectively capture high-level ethical concepts, they struggle with in-depth analysis requiring historically grounded reasoning and strategic recommendations. GPT-4o-mini demonstrated the most consistent performance across metrics.

Bias evaluation studies reveal systematic issues in LLM ethical decision-making. Yan et al. (2025) compared GPT-3.5 Turbo and Claude 3.5 Sonnet on ethical dilemmas involving protected attributes, finding significant biases in both models through 11,200 experimental trials. GPT-3.5 Turbo showed preferences aligned with traditional power structures, while Claude 3.5 Sonnet demonstrated more diverse choices but reduced ethical sensitivity in complex intersectional scenarios.

Multilingual evaluation using the Multilingual Moral Reasoning Benchmark (MMRB) revealed significant inconsistencies in LLM moral reasoning across languages, with particular challenges in low-resource languages (arXiv:2504.19759). This highlights the context-dependent nature of current LLM moral reasoning capabilities.

### Specialized Benchmarks and Evaluation Frameworks

Recent work has developed sophisticated evaluation approaches for LLM moral reasoning. The Priced Survey Methodology (PSM) adapts economic choice theory to analyze LLM responses to ethical questions as choices under constraints, enabling assessment of reasoning consistency and quantification of "moral stances" across 39 LLMs (arXiv:2412.04476). This methodology revealed a "shared core" in LLM moral reasoning but also meaningful variations in consistency and ethical profiles.

Specialized benchmarks have emerged for different aspects of ethical evaluation. The ETHICS dataset suite provides multilingual evaluation across moral dimensions, while protected attribute dilemma scenarios assess bias in ethical decision-making (arXiv:2501.10484). Real-world ethical dilemma benchmarks use expert-segmented analysis to evaluate LLM performance on complex cases requiring nuanced resolution strategies (arXiv:2505.08106).

### Limitations in Precedent-Based Professional Ethics Integration

Despite advances in AI applications across professional domains, current systems demonstrate significant limitations in leveraging the precedent-based reasoning that characterizes professional ethics in legal, medical, and engineering contexts.

**Legal Domain Challenges**: Recent research reveals substantial difficulties in AI systems' ability to engage with legal precedent effectively. A 2024 study on precedent search in Chinese law found practitioners expressing dissatisfaction with current AI legal tools, citing their "end-to-end" nature that lacks intermediate control and raises concerns about trustworthiness and ethics in high-stakes legal domains. Legal AI systems face challenges in their interaction with precedent-based reasoning, as AI technology applies computational models rather than legal reasoning as understood in jurisprudence, with AI systems not "reasoning" or "interpreting" in the human sense.

**Medical and Healthcare Ethics**: Medical AI systems face similar challenges in applying ethical precedents effectively. The "black box" nature of many AI models complicates clinical decision-making and accountability, creating barriers to understanding how ethical precedents or established best practices are being applied (Haltaufderheide & Ranisch, 2024; Lawrence et al., 2024). Research on AI in healthcare highlights issues including biased training data leading to unfair recommendations and problems with informed consent when patients cannot understand AI's role. These factors impede trustworthy precedent-based ethical reasoning.

**Engineering and Safety-Critical Systems**: While engineering ethics literature may not explicitly use the term "precedent-based reasoning," the field relies heavily on learning from past failures, applying codes of ethics informed by historical cases, and adapting established principles to novel situations. Current AI systems demonstrate limitations in this type of reasoning, particularly in safety-critical contexts where ethical decision-making must incorporate lessons from historical engineering failures and established professional precedents.

These domain-specific challenges reflect broader systemic limitations in how current AI systems engage with precedent-based reasoning. Most systems perform pattern matching or statistical analysis rather than engaging in genuine reasoning about the principles underlying precedents. The reduction of ethics to mathematically expressible constraints fundamentally alters the nature of moral reasoning, failing to capture the richness of precedent-based human ethical reasoning that characterizes professional practice.