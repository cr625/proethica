# Section 2.3 LLM-Based Moral Reasoning - Enhanced with Additional Validated Citations

## Enhanced Section 2.3 

**Note**: This section focuses on systems that use LLMs and language models to assist with ethical reasoning and moral decision-making, rather than approaches for making AI systems themselves more ethical (e.g., Constitutional AI, alignment research). ProEthica belongs to the former category - using AI as a tool for ethical deliberation rather than addressing the ethics of AI use.

### Early Language Model-Based Moral Reasoning Systems
- **Delphi** (Jiang et al., 2022): Commonsense moral model trained to present a descriptive view of ethical judgments, representing early attempts to encode moral knowledge in language models trained on human text data
- **Kaleidoscope** (Sorensen et al., 2023): Value pluralism evaluation framework for AI ethics, addressing the challenge of multiple competing ethical frameworks
- **DIT and DailyDilemmas**: Datasets and benchmarks for testing ethical reasoning maturity in language models, providing standardized evaluation approaches

### Contemporary Language Model Approaches to Moral Reasoning
Recent research has expanded beyond standalone moral reasoning models toward more sophisticated approaches that address contextual disambiguation and value alignment. Rao et al. (2023) present iterative self-distillation methods for understanding when moral rule-breaking becomes acceptable, demonstrating how language models can learn to distinguish between contexts where identical actions may have different moral evaluations. This work addresses a fundamental challenge in computational ethics: the context-dependency of moral judgments.

The measurement and evaluation of value alignment in AI systems has become a critical research area. Peterson and Gärdenfors (2024) provide frameworks for measuring value alignment in AI systems, offering methodological approaches for assessing how well AI reasoning aligns with human moral judgments. Their work establishes important foundations for evaluating the effectiveness of language model-based moral reasoning systems.

### Virtue Ethics and Learning-Based Approaches
Contemporary research has explored virtue ethics as a promising framework for artificial moral agents due to its emphasis on learning from experience and adapting to complex human norms (Stenseke, 2023). This approach connects directly to the capabilities of language models, which learn patterns of human values and norms from vast amounts of human text data. Stenseke's work on artificial virtuous agents bridges classical virtue ethics theory with modern machine implementation, providing theoretical foundations for language model-based moral agents.

The "bottom-up" approach to machine ethics emphasizes creating environments where agents learn moral values and norms from data or experience rather than being explicitly programmed with rules. Language models, trained on extensive human text corpora, inherently embody this bottom-up learning approach by capturing patterns of human moral reasoning and value expression embedded in natural language.

### Hybrid and Integration Approaches
Current research increasingly favors hybrid systems that combine learned patterns from language models (bottom-up) with explicit rules or principles (top-down). This aligns with the broader trend toward integrating multiple methodological approaches in AI systems for complex domains like moral reasoning (Davis-Stober et al., 2024).

### Recent Advances in AI-Human Alignment for Ethical Decision-Making
Contemporary research has moved beyond standalone LLM moral reasoning toward systems that align with human decision-makers in specific professional contexts. Molineaux et al. (2024) present significant advances in aligning AI systems to human decision-makers in military medical triage scenarios, demonstrating how case-based reasoning can be integrated with AI systems to support ethical decision-making in high-stakes professional contexts.

### Limitations of Current LLM-Based Approaches
Despite these advances, current LLM-based moral reasoning systems face several key limitations that ProEthica aims to address:

1. **Lack of Professional Grounding**: Most systems treat ethical reasoning as general text generation rather than specialized professional decision support grounded in domain-specific obligations and precedents.

2. **Insufficient Constraint Mechanisms**: Existing approaches lack formal mechanisms to ensure that AI reasoning aligns with established professional ethical frameworks and precedent cases.

3. **Limited Precedent Integration**: While systems show promise in learning moral patterns from text, they do not systematically integrate the rich precedent-based reasoning that characterizes established professional ethics domains.

4. **Weak Bidirectional Validation**: Current systems typically generate moral reasoning without systematic post-hoc validation against professional ethical frameworks and established precedent patterns.

5. **Context-Dependency Challenges**: Although work like Rao et al. (2023) addresses contextual moral reasoning, most systems lack the structured constraint mechanisms needed for professional contexts where decisions must be traceable to specific ethical principles.

### The Need for Ontology-Constrained Approaches
The integration of ontological knowledge structures with LLM reasoning capabilities, as proposed in ProEthica, addresses these limitations by providing both constraint mechanisms during reasoning and validation frameworks for generated outputs. This approach builds on the foundation established by systems like SIROCCO (McLaren, 2003), contemporary alignment work (Molineaux et al., 2024), and recent advances in value alignment measurement (Peterson & Gärdenfors, 2024) while addressing their limitations through bidirectional LLM-ontology integration.

---

## References Added:

**Davis-Stober, C. P., Erev, I., & Bhatia, S. (2024).** The interface between machine learning, artificial intelligence, and decision research. *Decision*, 11(4), 389–396. https://doi.org/10.1037/dec0000272

**Peterson, M., & Gärdenfors, P. (2024).** How to measure value alignment in AI. *AI and Ethics*, 4, 1493–1506. https://doi.org/10.1007/s43681-023-00357-7

**Rao, A., Ammanabrolu, P., Sap, M., Hajishirzi, H., & Choi, Y. (2023).** What Makes it Ok to Set a Fire? Iterative Self-distillation of Contexts and Rationales for Disambiguation.

**Stenseke, J. (2023).** Artificial virtuous agents: from theory to machine implementation. *AI & Society*, 38, 1301–1320. https://doi.org/10.1007/s00146-021-01325-7

---

## Key Enhancements:

1. **Contemporary Context Work**: Rao et al. (2023) on contextual moral reasoning
2. **Value Alignment Framework**: Peterson & Gärdenfors (2024) on measuring value alignment
3. **Virtue Ethics Implementation**: Stenseke (2023) on artificial virtuous agents
4. **Methodological Integration**: Davis-Stober et al. (2024) on ML/AI/decision research interfaces
5. **Stronger LLM Foundation**: Better grounding in actual language model moral reasoning research
6. **Professional Context Positioning**: Clearer articulation of how ProEthica advances beyond current approaches

This significantly strengthens the theoretical positioning of ProEthica by showing how it builds on contemporary LLM moral reasoning research while addressing specific limitations through ontology-constrained approaches.
