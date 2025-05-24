# 4. Study

## 4.1 Research Hypothesis

ProEthica's ontology-constrained approach to ethical reasoning represents a systematic method for grounding LLM outputs in professional ethical frameworks. The research hypothesis centers on whether structured ontological constraints improve the quality and alignment of ethical reasoning compared to standard retrieval-augmented approaches.

### Primary Hypothesis

**Ontology-constrained prompts that integrate role-based ethical obligations with structured case precedents will produce more reasonable, persuasive, and aligned ethical reasoning compared to standard retrieval-augmented baseline approaches.**

This hypothesis addresses the fundamental question of whether systematic integration of professional ethics knowledge through ontological structures enhances LLM reasoning capabilities beyond general similarity-based retrieval methods.

### Specific Predictions

The research framework tests four key dimensions of ethical reasoning improvement.

**Reasoning Quality Enhancement**: ProEthica outputs will demonstrate superior logical coherence, systematic principle application, and structured argumentation compared to baseline approaches. The ontological constraints are expected to guide reasoning toward more systematic consideration of relevant ethical factors.

**Persuasiveness Improvement**: Participants will find ProEthica-generated reasoning more convincing and well-supported than baseline outputs. The structured integration of precedent cases and professional principles should enhance the persuasive quality of ethical arguments.

**Conclusion Accuracy**: ProEthica predictions will show higher alignment with original NSPE Board determinations. The systematic application of professional ethical principles should improve prediction accuracy for expert ethical reasoning.

**Professional Alignment**: ProEthica outputs will demonstrate better adherence to professional ethical reasoning patterns and standards. The ontological grounding should produce reasoning that more closely matches established professional ethics practices.

### Evaluation Framework

The evaluation approach employs comparative assessment where participants evaluate paired outputs across multiple dimensions. Participants do not know which system generated each output (ProEthica vs. baseline). This double-blind comparative approach enables direct assessment of reasoning quality differences.

The research design implements a leave-one-out cross-validation approach on NSPE Board of Ethical Review cases, enabling systematic assessment of prediction accuracy while maintaining independence between training and evaluation data. Each of the 20 NSPE cases serves as a test case with conclusion and discussion sections redacted, requiring the system to predict these elements based on facts and applicable ethical principles.

## 4.2 Corpus and Data

The evaluation corpus consists of professional ethics cases from the National Society of Professional Engineers (NSPE) Board of Ethical Review, representing a well-established dataset of expert ethical reasoning in engineering practice. This corpus provides the foundation for systematic evaluation of ontology-constrained reasoning approaches.

Existing general moral reasoning benchmarks (ETHICS dataset, AITA scenarios, PSM questions) are not suitable for evaluating professional decision-support systems due to domain specificity requirements, the precedent-based nature of professional ethics, and evaluation target mismatches between autonomous moral judgment and professional decision support.

### NSPE Board of Ethical Review Case Dataset

Twenty recent NSPE Board of Ethical Review cases form the complete evaluation dataset. These cases represent diverse ethical scenarios encountered in professional engineering practice, including conflicts of interest, safety concerns, confidentiality issues, and professional competence questions.

Each case follows a standardized format that facilitates systematic analysis. Case Facts provide detailed description of the ethical scenario, professional relationships, and contextual factors. Ethical Questions pose specific questions to the Board regarding professional obligations and appropriate actions. Discussion sections contain expert analysis incorporating relevant NSPE Code provisions, precedent cases, and ethical reasoning. Conclusion sections present Board determination of appropriate action and ethical obligations. Code References specify NSPE Code of Ethics provisions applicable to the case.

The selected cases cover the full spectrum of professional engineering ethics, ensuring evaluation across diverse ethical principles, professional roles, and contextual factors commonly encountered in engineering practice. Cases span recent years to ensure contemporary relevance while providing sufficient precedent depth for analogical reasoning evaluation. The dataset includes cases ranging from straightforward ethical applications to complex scenarios involving multiple competing obligations and nuanced contextual factors.

### NSPE Code of Ethics as Canonical Framework

The NSPE Code of Ethics serves as the canonical ethical framework for engineering professional practice, providing structured principles, obligations, and guidelines that inform ethical reasoning. The Code organizes ethical obligations through fundamental principles (public safety, competence, honesty), specific duties to stakeholders (public, employers, clients, colleagues), and professional conduct standards. The Code works in conjunction with Board of Ethical Review precedents to provide comprehensive guidance for professional ethical reasoning across diverse scenarios.

## 4.3 Processing Pipeline

The preprocessing pipeline transforms raw NSPE cases and ethical guidelines into structured representations suitable for both ontology-constrained reasoning and comparative evaluation. The pipeline emphasizes automated processing with validation checkpoints to ensure consistency and accuracy.

### World Creation and Ontology Development

The NSPE Code of Ethics undergoes systematic analysis to extract professional roles, ethical principles, obligations, and constraints. This process creates the foundational ontology that constrains subsequent reasoning processes. Professional ethics concepts are identified through automated analysis combined with domain expertise validation. Extracted concepts include roles (Engineer, Client, Public), principles (Safety, Competence, Honesty), and contextual factors (Conflicts of Interest, Confidentiality Requirements).

Professional obligations and ethical relationships are encoded as RDF triples that specify permissible and required actions under various circumstances, providing structured constraints for reasoning processes.

### Document Processing and Annotation

Cases undergo automatic analysis to identify semantic sections according to professional ethics reasoning patterns. The system identifies Facts, Questions, Discussion, and Conclusion sections using pattern recognition and content analysis. Professional entities mentioned in case content (roles, actions, principles, outcomes) are identified and linked to corresponding ontological representations, enabling systematic analysis of ethical relationships and obligations.

Case sections receive semantic tags that specify their evidential role within ethical reasoning, enabling targeted retrieval and analysis during system operation. Each case section is processed using MiniLM-L6-v2 to generate 384-dimensional semantic embeddings that capture content meaning while maintaining computational efficiency.

### Cross-Validation Preparation

The 20-case dataset is prepared for leave-one-out cross-validation with systematic redaction procedures that remove target sections (conclusion, discussion, or both) while preserving contextual information needed for reasoning. Standard retrieval-augmented prompts are prepared using the same case database and NSPE Code access but without ontological constraints, ensuring fair comparison between approaches.

## 4.4 Study Design

The study employs a within-subjects comparative design that evaluates ProEthica's ontology-constrained reasoning against a standard retrieval-augmented baseline across 20 NSPE Board of Ethical Review cases. The design prioritizes practical evaluation while maintaining scientific rigor through systematic comparison and randomization.

### Leave-One-Out Cross-Validation Procedure

The evaluation implements leave-one-out cross-validation to ensure independence between training and testing data while maximizing the use of available cases. For each test case, specific sections are systematically removed depending on the evaluation condition. Conclusion sections are completely redacted for conclusion prediction tasks, discussion sections for discussion prediction tasks, and both sections for combined evaluation tasks.

The remaining 19 cases retain their complete content, including conclusions and discussions, providing the system with precedent patterns and reasoning examples for analogical reasoning and constraint application. Both ProEthica and baseline systems receive identical redacted cases and generate predictions for the missing sections. Systems have access to facts, questions, and applicable NSPE Code references but not the expert reasoning or conclusions.

### Three-Condition Comparison Framework

The study evaluates three distinct aspects of ethical reasoning through separate comparison conditions. Condition 1 (Conclusion Comparison) has participants compare original NSPE conclusions with system-predicted conclusions (subset of 7 cases). This condition focuses on outcome accuracy and ethical judgment alignment. Condition 2 (Discussion Comparison) compares original NSPE discussion analysis with system-predicted discussion analysis (subset of 7 cases). This condition evaluates reasoning process quality and argumentation coherence. Condition 3 (Combined Comparison) compares original complete analysis (discussion + conclusion) with system-predicted complete analysis (subset of 6 cases). This condition assesses integrated reasoning quality and overall coherence.

Each condition uses different case subsets to enable comprehensive evaluation while maintaining manageable participant workload.

### Baseline and System Comparison

The baseline system implements standard embedding-based retrieval with basic precedent matching. The baseline uses the same case database and NSPE Code access but without ontological constraints or multi-metric relevance scoring. Prompts include retrieved similar cases and relevant code sections but lack structured ontological context.

ProEthica employs full ontology-constrained reasoning including multi-metric relevance calculation, world-based organization, bidirectional LLM-ontology integration, and structured precedent analysis as detailed in Section 3. Both systems receive identical case facts, questions, and NSPE Code access. The key difference lies in how this information is structured and constrained during reasoning generation.

## 4.5 Evaluation Metrics

The evaluation framework employs multiple complementary metrics to assess the effectiveness of ontology-constrained ethical reasoning across different dimensions of quality and accuracy. The metrics balance objective measures with subjective assessments to provide comprehensive evaluation of system performance.

### Participant-Based Assessment Metrics

Participants evaluate the logical coherence and systematic nature of ethical reasoning using a 7-point Likert scale. This metric captures whether arguments follow clear logical progression, appropriately apply ethical principles, and address relevant considerations systematically. Subjective assessment of argument convincingness on a 7-point scale provides insight into practical effectiveness of different approaches for ethical communication.

Evaluation of reasoning comprehensibility for non-expert audiences assesses whether ethical arguments are presented in accessible language with clear explanations of principle application and reasoning steps. Direct comparative preference between paired system outputs provides a comprehensive quality assessment that integrates multiple factors.

### Accuracy and Alignment Metrics

Binary assessment determines whether system predictions match or contradict original NSPE Board conclusions. This provides objective measurement of professional alignment and prediction accuracy. Assessment of whether system reasoning follows similar patterns and considerations as original NSPE analysis captures qualitative aspects of professional reasoning beyond simple conclusion agreement.

Evaluation of whether systems correctly identify and apply relevant NSPE Code provisions assesses the accuracy of ethical principle selection and application within specific case contexts.

### Statistical Analysis Framework

Chi-square tests for preference distributions, t-tests for Likert scale differences, and Mann-Whitney U tests for non-parametric comparisons ensure robust statistical evaluation. Confidence intervals (95%) for all effect estimates provide reliable bounds for performance differences and enable meaningful interpretation of results. Bonferroni correction addresses multiple testing concerns when evaluating across different conditions and metrics simultaneously.

## 4.6 Participant Review Protocol

The participant review protocol implements a streamlined online evaluation system designed to collect reliable comparative assessments while minimizing participant burden and maximizing data quality. The protocol emphasizes simplicity and clarity to ensure consistent evaluation across diverse participant backgrounds.

### Online Platform Design

The evaluation platform presents clean, side-by-side comparisons of original NSPE content with system predictions. Participants view cases in a standardized format with clear section labels and consistent presentation structure across all evaluations. Information is presented incrementally to avoid cognitive overload. Participants first read case facts and questions, then view paired reasoning outputs, and finally complete evaluation questions before proceeding to the next comparison.

### Participant Demographics and Protocol

Adult participants with post-secondary education representing diverse professional backgrounds provide educated assessment capability without specialized ethics expertise that might create evaluation bias. Target enrollment of 60-80 participants ensures adequate statistical power for detecting meaningful differences while accounting for potential dropout and incomplete responses.

Individual evaluation sessions require approximately 20-25 minutes, balancing comprehensive assessment with participant engagement and completion rates. Participants are randomly assigned to evaluate different case subsets across the three comparison conditions, ensuring balanced coverage while preventing individual participant fatigue.

### Evaluation Questions and Randomization

Participants respond to structured questions focusing on clarity, persuasiveness, logical coherence, and overall preference between paired outputs. Questions use Likert scales and direct preference selections to enable quantitative analysis. System outputs (ProEthica vs. baseline) are randomly assigned to left/right presentation positions for each comparison, preventing systematic position bias in preference ratings.

The sequence of case presentations is randomized for each participant to control for order effects and ensure balanced evaluation across all cases. All system outputs are presented without identifying labels or system names. Participants evaluate reasoning content quality without knowledge of which system generated each output, ensuring double-blind evaluation.

The study design balances comprehensive evaluation with practical implementation constraints, providing reliable assessment of ontology-constrained reasoning effectiveness while maintaining participant accessibility and scientific rigor.