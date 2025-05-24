# 3.4 Concrete Example: NSPE Case Analysis Walkthrough

This section demonstrates ProEthica's complete processing pipeline through NSPE Case 23-4 "Acknowledging Errors in Design," which involves an engineer's obligations regarding design errors that may have contributed to worker injury. This walkthrough illustrates how the system transforms abstract professional ethics frameworks into concrete reasoning support.

## Case Background and Structure

**NSPE Case 23-4 Overview**: Engineer T worked on a project where a worker was subsequently injured. Questions arise about Engineer T's obligations to acknowledge potential design errors that may have contributed to the injury. The case involves complex ethical considerations including professional competence, public safety, honesty, and disclosure obligations.

**FIRAC Structure Identification**: The system automatically identifies the case's structure following the Facts, Issues, Rules, Analysis, and Conclusion (FIRAC) format standard in professional ethics cases. The Facts section describes Engineer T's design approach and subsequent worker injury. The Issues section poses three specific ethical questions about error acknowledgment and professional obligations. The Rules section references relevant NSPE Code provisions. The Analysis section provides detailed examination incorporating precedent cases. The Conclusion section presents the NSPE Board's determination.

## ProEthica Processing Pipeline Demonstration

### Step 1: World Activation and Context Loading

The system activates the NSPE engineering ethics world, loading the complete professional framework including:

- **NSPE Code of Ethics**: All fundamental canons, rules of practice, and professional obligations
- **Historical Precedents**: Previous Board of Ethical Review cases involving similar ethical issues
- **Ontological Relationships**: Formalized relationships between roles, obligations, principles, and contextual factors
- **Professional Standards**: Domain-specific interpretations of ethical principles in engineering contexts

### Step 2: Document Processing and Structure Annotation

**Automatic FIRAC Annotation**: The system processes the case text to identify structural components:

```
Facts: "Engineer T designed X system... worker injury occurred..."
Issues: "Does Engineer T have obligation to acknowledge potential errors?"
Rules: "NSPE Code I.1 (Public Safety), III.1.a (Honesty), III.8 (Disclosure)"
Analysis: "Similar cases include... professional standards require..."
Conclusion: "Engineer T must... based on professional obligations..."
```

**Section Embedding Generation**: Each FIRAC component undergoes embedding generation for similarity matching with precedent cases and ontological concepts. This enables precise alignment between case components and relevant professional framework elements.

### Step 3: Ontological Mapping and Relevance Calculation

**NSPE Code Provision Identification**: The system identifies relevant Code provisions through multi-metric scoring:

- **I.1 Public Safety**: "Engineers must hold paramount the safety, health, and welfare of the public"
- **II.3.a Professional Competence**: "Engineers shall undertake assignments only when qualified"
- **III.1.a Honesty**: "Engineers shall be objective and truthful in professional reports"
- **III.8 Disclosure Obligations**: "Engineers shall disclose all known or potential conflicts"

**Multi-Metric Relevance Scoring**: For each Code provision, the system calculates:
- **Vector Similarity**: Cosine similarity between case text and provision embeddings
- **Term Overlap**: Weighted overlap of key professional terminology
- **Structural Relevance**: Alignment between case components and provision applications
- **Ontological Distance**: Relationship strength in professional ethics ontology

### Step 4: Precedent Retrieval and Analogical Analysis

**Historical Case Identification**: Vector embeddings identify analogous Board of Ethical Review cases:

- **Case 78-3**: Design error disclosure in construction projects
- **Case 91-7**: Professional competence and error acknowledgment
- **Case 03-2**: Public safety obligations in design review

**Analogical Reasoning Pattern Extraction**: The system analyzes how these precedent cases:
- Define professional obligations in error situations
- Balance competing interests (client confidentiality vs. public safety)
- Apply NSPE Code provisions to specific contexts
- Establish patterns for ethical decision-making

### Step 5: Ontology-Constrained Reasoning Generation

**Structured Context Integration**: The LLM receives comprehensive structured context including:

```
Professional Framework: NSPE Code provisions with relevance scores
Precedent Patterns: Similar cases with analogical reasoning connections  
Case Context: FIRAC-structured current case information
Constraints: Professional obligations and ethical boundaries
Evidence Weights: Multi-metric relevance scores for all components
```

**Constrained Reasoning Process**: The LLM generates analysis that:
- Remains consistent with established NSPE standards
- Incorporates relevant precedent patterns
- Addresses specific ethical questions posed in the case
- Provides structured justification for reasoning conclusions
- Maintains professional terminology and argumentation patterns

### Step 6: Validation and Evidence-Based Output

**Ontological Constraint Validation**: Generated reasoning undergoes validation against professional ethics constraints:
- Consistency with NSPE Code provisions
- Alignment with precedent case patterns
- Professional terminology and framework compliance
- Logical coherence of ethical argumentation

**Evidence-Based Decision Support Output**: The system produces structured evidence including:
- **Relevant Principles**: Applicable NSPE Code provisions with justification
- **Precedent Analysis**: Similar cases and their reasoning patterns
- **Professional Obligations**: Specific duties derived from engineering ethics framework
- **Reasoning Support**: Structured evidence to support human ethical decision-making

## Example Output Comparison

**Traditional LLM Response** (unconstrained):
"Engineer T should probably acknowledge the error because honesty is important and people might be hurt."

**ProEthica Evidence-Based Output**:
"Based on NSPE Code I.1 (Public Safety) and III.1.a (Honesty), Engineer T has professional obligations to acknowledge potential design errors. Precedent Case 78-3 establishes that engineers must prioritize public welfare over client preferences when safety concerns arise. The multi-metric analysis indicates high relevance (0.87) between current case facts and established disclosure obligations. Professional framework analysis suggests three specific actions: [detailed evidence-based recommendations with precedent justification]."

## Evaluative AI Implementation Demonstration

This example demonstrates ProEthica's implementation of evaluative AI principles:

**Evidence-Based Decision Support**: Rather than autonomous judgment, the system provides comprehensive evidence analysis to support human ethical decision-making. The structured output preserves human agency while enhancing systematic consideration of relevant ethical factors.

**Hypothesis-Driven Analysis**: The system enables practitioners to test ethical reasoning hypotheses against established professional frameworks and precedent patterns, supporting iterative refinement of ethical analysis.

**Transparent Justification**: All reasoning components trace to specific professional framework elements, enabling practitioners to understand and validate AI-generated analysis through established professional reasoning structures.

This concrete example illustrates how ProEthica transforms abstract professional ethics frameworks into practical decision support tools that enhance rather than replace human professional judgment in complex ethical situations.
