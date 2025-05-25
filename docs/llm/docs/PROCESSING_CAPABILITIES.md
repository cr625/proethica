# LLM-Enhanced Processing Capabilities

## Triple Generation Enhancement

### Current Implementation (Phase 1)
- Basic RDF triple creation from guideline concepts
- Standard properties (labels, descriptions, IDs)
- Domain-specific relationships
- Multiple output formats (JSON, Turtle)
- Deterministic, predictable output

### Phase 2: LLM Enhancement Plan
1. **Design Specialized Prompts**
   - Include ontology structure information
   - Provide triple format examples
   - Guide relationship detection

2. **Implementation Approach**
   - Create `_generate_llm_enhanced_triples` method
   - Configuration for enable/disable LLM enhancement
   - Error handling with fallback to basic generation

3. **Triple Merging Strategy**
   - Start with basic generation as foundation
   - Add LLM-generated semantic triples
   - Remove duplicates/contradictions
   - Ensure consistent formatting

4. **Quality Control**
   - Validation checks for LLM output
   - Confidence scoring (0.0-1.0)
   - Filtering rules for low-confidence triples
   - User configuration for quality thresholds

### LLM Prompt Template
```
You are an expert in RDF triple generation. Given concepts below, generate meaningful semantic triples capturing relationships in engineering ethics.

Consider relationship types:
- Hierarchical (isA, partOf, subClassOf)
- Process (causes, enables, prevents)
- Responsibility (responsibleFor, accountableTo)
- Ethical (conflictsWith, supportsValue)
- Normative (obligated, permitted, prohibited)

Format:
{
  "subject": "URI",
  "predicate": "URI",
  "object": "URI or literal",
  "confidence": 0.0-1.0,
  "explanation": "relationship rationale"
}
```

## Section-Triple Association

### Current Limitations
- Embedding-based approach finds too few associations
- Vector space mismatch between narratives and concepts
- Granularity issues with full section embeddings

### LLM-Based Solution
1. **Multi-Metric Approach**
   - Vector similarity (when available)
   - Term overlap analysis
   - Structural relevance
   - LLM semantic assessment

2. **Implementation Components**
   - `LLMSectionTripleAssociator` class
   - Integration with existing storage format
   - UI enhancements for reasoning display

3. **Success Metrics**
   - 3-5 concepts per section (vs. current 1)
   - Meaningful explanations for associations
   - Consistent database format
   - Clear reasoning display in UI

## Temporal Extensions

### RDF Triple Enhancement
- Temporal fields: `valid_from`, `valid_to`, `temporal_confidence`
- Timeline organization: `timeline_order`, `timeline_group`
- Causal relationships: `causedBy`, `enabledBy`, `preventedBy`
- Decision structures: `DecisionSequence`, `DecisionOption`, `DecisionConsequence`

### Causal Trace Construction
- Sequential recording of events and decisions
- Temporal coherence maintenance
- External reasoning enablement for LLMs
- Consequence mapping from decisions to outcomes