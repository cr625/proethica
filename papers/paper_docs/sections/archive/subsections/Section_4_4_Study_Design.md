# 4.4 Study Design

The study employs a within-subjects comparative design that evaluates ProEthica's ontology-constrained reasoning against a standard retrieval-augmented baseline across 20 NSPE Board of Ethical Review cases. The design prioritizes practical evaluation while maintaining scientific rigor through systematic comparison and randomization.

## Leave-One-Out Cross-Validation Procedure

The evaluation implements leave-one-out cross-validation to ensure independence between training and testing data while maximizing the use of available cases.

**Case Redaction Process**: For each test case, specific sections are systematically removed depending on the evaluation condition. Conclusion sections are completely redacted for conclusion prediction tasks, discussion sections for discussion prediction tasks, and both sections for combined evaluation tasks.

**Training Data Availability**: The remaining 19 cases retain their complete content, including conclusions and discussions, providing the system with precedent patterns and reasoning examples for analogical reasoning and constraint application.

**Prediction Generation**: Both ProEthica and baseline systems receive identical redacted cases and generate predictions for the missing sections. Systems have access to facts, questions, and applicable NSPE Code references but not the expert reasoning or conclusions.

## Online Evaluation Platform

The study utilizes a streamlined online evaluation platform designed for efficiency and participant accessibility.

**Simple Interface Design**: Participants interact with a clean, intuitive interface that presents original NSPE content alongside system-generated predictions without identifying which system produced each output.

**Randomization and Blinding**: System outputs are randomly assigned to presentation positions (left/right) and anonymized to ensure double-blind evaluation. Participants cannot identify which predictions come from ProEthica versus baseline approaches.

**Progressive Evaluation Structure**: The evaluation proceeds through three distinct comparison types with different subsets of cases to minimize participant fatigue while providing comprehensive assessment.

## Three-Condition Comparison Framework

The study evaluates three distinct aspects of ethical reasoning through separate comparison conditions:

**Condition 1: Conclusion Comparison**: Participants compare original NSPE conclusions with system-predicted conclusions (subset of 7 cases). This condition focuses on outcome accuracy and ethical judgment alignment.

**Condition 2: Discussion Comparison**: Participants compare original NSPE discussion analysis with system-predicted discussion analysis (subset of 7 cases). This condition evaluates reasoning process quality and argumentation coherence.

**Condition 3: Combined Comparison**: Participants compare original complete analysis (discussion + conclusion) with system-predicted complete analysis (subset of 6 cases). This condition assesses integrated reasoning quality and overall coherence.

Each condition uses different case subsets to enable comprehensive evaluation while maintaining manageable participant workload.

## Comparison Conditions: ProEthica vs. Baseline

**Baseline System**: Implements standard embedding-based retrieval with basic precedent matching. The baseline uses the same case database and NSPE Code access but without ontological constraints or multi-metric relevance scoring. Prompts include retrieved similar cases and relevant code sections but lack structured ontological context.

**ProEthica System**: Employs full ontology-constrained reasoning including multi-metric relevance calculation, world-based organization, bidirectional LLM-ontology integration, and structured precedent analysis as detailed in Section 3.

**Consistent Inputs**: Both systems receive identical case facts, questions, and NSPE Code access. The key difference lies in how this information is structured and constrained during reasoning generation.

## Participant Evaluation Protocol

**Participant Demographics**: Non-expert participants with diverse professional backgrounds represent the general educated audience for professional ethics communication. This approach avoids potential conflicts of interest while providing practical assessment of reasoning accessibility and persuasiveness.

**Evaluation Questions**: Participants respond to structured questions focusing on clarity, persuasiveness, logical coherence, and overall preference between paired outputs. Questions use Likert scales and direct preference selections to enable quantitative analysis.

**Session Structure**: Each participant evaluates a subset of cases across the three conditions (approximately 6-8 comparisons total) to maintain engagement while providing sufficient data for statistical analysis.

## Data Collection and Analysis Framework

**Quantitative Metrics**: Preference percentages, Likert scale ratings, and accuracy measures (agreement with original NSPE conclusions) provide quantitative assessment of system performance differences.

**Qualitative Feedback**: Optional open-ended responses enable participants to explain reasoning behind preferences and identify specific strengths or weaknesses in system outputs.

**Statistical Analysis**: Chi-square tests for preference distributions, t-tests for scale ratings, and effect size calculations provide robust statistical evaluation of performance differences between systems.

**Randomization Control**: Systematic randomization of presentation order, case selection, and participant assignment ensures unbiased evaluation and enables reliable statistical inference.

The study design balances comprehensive evaluation with practical implementation constraints, providing reliable assessment of ontology-constrained reasoning effectiveness while maintaining participant accessibility and scientific rigor.
