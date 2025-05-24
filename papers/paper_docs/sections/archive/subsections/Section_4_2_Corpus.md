# 4.2 Corpus and Data

The evaluation corpus consists of professional ethics cases from the National Society of Professional Engineers (NSPE) Board of Ethical Review, representing a well-established dataset of expert ethical reasoning in engineering practice. This corpus provides the foundation for systematic evaluation of ontology-constrained reasoning approaches.

**Evaluation Approach Rationale**: As detailed in Section 5.4.1, existing general moral reasoning benchmarks (ETHICS dataset, AITA scenarios, PSM questions) are not suitable for evaluating professional decision-support systems due to domain specificity requirements, the precedent-based nature of professional ethics, and evaluation target mismatches between autonomous moral judgment and professional decision support.

## NSPE Board of Ethical Review Case Dataset

**Case Selection**: Twenty recent NSPE Board of Ethical Review cases form the complete evaluation dataset. These cases represent diverse ethical scenarios encountered in professional engineering practice, including conflicts of interest, safety concerns, confidentiality issues, and professional competence questions.

**Case Structure and Content**: Each case follows a standardized format that facilitates systematic analysis:
- **Case Facts**: Detailed description of the ethical scenario, professional relationships, and contextual factors
- **Ethical Questions**: Specific questions posed to the Board regarding professional obligations and appropriate actions
- **Discussion**: Expert analysis incorporating relevant NSPE Code provisions, precedent cases, and ethical reasoning
- **Conclusion**: Board determination of appropriate action and ethical obligations
- **Code References**: Specific NSPE Code of Ethics provisions applicable to the case

**Professional Relevance**: The selected cases cover the full spectrum of professional engineering ethics, ensuring evaluation across diverse ethical principles, professional roles, and contextual factors commonly encountered in engineering practice.

## NSPE Code of Ethics as Canonical Framework

**Authoritative Foundation**: The NSPE Code of Ethics serves as the canonical ethical framework for engineering professional practice, providing structured principles, obligations, and guidelines that inform ethical reasoning.

**Hierarchical Organization**: The Code organizes ethical obligations through fundamental principles (public safety, competence, honesty), specific duties to stakeholders (public, employers, clients, colleagues), and professional conduct standards.

**Precedent Integration**: The Code works in conjunction with Board of Ethical Review precedents to provide comprehensive guidance for professional ethical reasoning across diverse scenarios.

## Data Characteristics and Representativeness

**Temporal Distribution**: Cases span recent years to ensure contemporary relevance while providing sufficient precedent depth for analogical reasoning evaluation.

**Complexity Variation**: The dataset includes cases ranging from straightforward ethical applications to complex scenarios involving multiple competing obligations and nuanced contextual factors.

**Professional Domain Coverage**: Cases represent diverse engineering disciplines and practice contexts, ensuring evaluation across the breadth of professional engineering ethics rather than narrow specialization.

**Reasoning Depth**: Each case includes substantial expert analysis that demonstrates systematic application of ethical principles, providing robust targets for reasoning quality assessment.

## Dataset Preparation for Evaluation

**Content Standardization**: All cases undergo formatting standardization to ensure consistent presentation while preserving semantic content and reasoning structure.

**Section Identification**: Case components (facts, questions, discussion, conclusion) are clearly identified to enable precise redaction and comparison during evaluation.

**Metadata Documentation**: Each case includes comprehensive metadata regarding applicable ethical principles, stakeholder relationships, and contextual factors to support systematic analysis.

The corpus provides a representative and authoritative foundation for evaluating ontology-constrained reasoning approaches within established professional ethics practice, ensuring evaluation results have practical relevance for professional ethics applications.
