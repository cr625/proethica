# LLM Use Cases in ProEthica

## 1. Case Analysis and Information Extraction

### Purpose
Extract structured information from unstructured engineering ethics cases.

### Implementation
- **Service**: `app/services/case_url_processor/llm_extractor.py`
- **Method**: `extract_case_sections()`

### Process
1. Fetch case content from URL
2. Clean HTML and extract text
3. Use LLM to identify sections:
   - Facts
   - Questions
   - Discussion
   - Conclusion
   - References

### Example Prompt
```
Extract the following sections from this engineering ethics case:
1. FACTS - The factual situation
2. QUESTIONS - Ethical questions posed
3. DISCUSSION - Analysis of the issues
4. CONCLUSION - Final determination
5. REFERENCES - Codes and standards cited

Case text: [CASE_CONTENT]

Return in JSON format.
```

### Success Metrics
- 95%+ accuracy in section identification
- Handles varied case formats
- Preserves important formatting

## 2. Guideline Concept Extraction

### Purpose
Extract ontology-aligned concepts from ethical guidelines and codes.

### Implementation
- **Service**: `app/services/guideline_analysis_service.py`
- **MCP Module**: `mcp/modules/guideline_analysis_module.py`

### Process
1. Parse guideline text
2. Identify key ethical concepts
3. Map to ontology entities
4. Generate RDF triples
5. Store associations

### Example Usage
```python
{
  "guideline_text": "Engineers shall hold paramount the safety, health, and welfare of the public.",
  "extracted_concepts": [
    {
      "concept": "Public Safety",
      "ontology_uri": "http://proethica.org/ontology#PublicSafety",
      "confidence": 0.95
    },
    {
      "concept": "Professional Duty",
      "ontology_uri": "http://proethica.org/ontology#ProfessionalDuty",
      "confidence": 0.88
    }
  ]
}
```

## 3. Case Conclusion Prediction

### Purpose
Predict ethical conclusions for cases with and without ontology enhancement.

### Implementation
- **Service**: `app/services/experiment/prediction_service.py`
- **Modes**: Ontology-augmented vs. Prompt-only

### Experimental Setup
```python
# With ontology
prediction = predict_with_ontology(
    case_data={
        "facts": "...",
        "questions": ["..."],
        "discussion": "..."
    },
    ontology_concepts=["concept1", "concept2"],
    similar_cases=[case1, case2]
)

# Without ontology (baseline)
baseline = predict_prompt_only(case_data)
```

### Evaluation Metrics
- Accuracy vs. expert conclusions
- Reasoning quality scores
- Consistency across similar cases

## 4. Section-Triple Association

### Purpose
Link document sections to relevant ontology concepts using semantic analysis.

### Implementation
- **Service**: `ttl_triple_association/llm_section_triple_associator.py`
- **Storage**: `section_triple_associations` table

### Process
1. Analyze section content
2. Identify relevant ontology concepts
3. Generate association explanation
4. Calculate confidence scores
5. Store with metadata

### Association Format
```json
{
  "section_uri": "http://proethica.org/document/case_21_11/discussion",
  "concept_uri": "http://proethica.org/ontology#ConflictOfInterest",
  "confidence": 0.82,
  "explanation": "Discussion addresses competing obligations between employer loyalty and public safety.",
  "method": "llm_semantic"
}
```

## 5. Ethical Decision Support

### Purpose
Provide reasoning support for ethical decisions in engineering scenarios.

### Implementation
- **Service**: `app/services/decision_engine.py`
- **Enhanced**: `app/services/enhanced_decision_engine.py`

### Decision Process
1. **Context Gathering**
   - Identify stakeholders
   - Extract constraints
   - Determine applicable principles

2. **Analysis**
   - Evaluate options
   - Consider consequences
   - Apply ethical frameworks

3. **Recommendation**
   - Propose action
   - Provide justification
   - Cite relevant standards

### Example Decision
```json
{
  "scenario": "Pressure to approve unsafe design",
  "recommendation": "Refuse approval and document concerns",
  "justification": {
    "principles": ["public_safety", "professional_integrity"],
    "standards": ["NSPE Code I.1", "State regulations"],
    "reasoning": "Public safety overrides employer pressure"
  }
}
```

## 6. Simulation and Agent Interactions

### Purpose
Simulate ethical scenarios with multiple agents representing different perspectives.

### Implementation
- **Controller**: `app/services/simulation_controller.py`
- **Orchestrator**: `app/services/agent_orchestrator.py`
- **Agents**: `app/services/agents/`

### Agent Types
1. **Guidelines Agent**: Interprets ethical codes
2. **Stakeholder Agents**: Represent different interests
3. **Decision Agent**: Makes final determinations

### Simulation Flow
```
Initialize Scenario → Spawn Agents → Exchange Views → 
Negotiate → Reach Decision → Document Reasoning
```

## 7. Temporal and Causal Reasoning

### Purpose
Track decision sequences and causal relationships in ethical scenarios.

### Implementation
- **Module**: `mcp/modules/temporal_module.py`
- **Enhancement**: Timeline and causality tracking

### Capabilities
- Track event sequences
- Identify causal chains
- Predict consequences
- Build decision trees

### Temporal Triple Example
```turtle
:Decision1 :causedBy :Event1 ;
          :enabledBy :Condition1 ;
          :resultsIn :Consequence1 ;
          :occursAt "2024-01-15T10:00:00"^^xsd:dateTime .
```

## 8. Ontology Enhancement

### Purpose
Use LLM to enhance ontology with new concepts and relationships.

### Implementation
- **Scripts**: Various in `/scripts/`
- **MCP Tools**: Concept analysis tools

### Enhancement Types
1. **Concept Discovery**: Find new ethical concepts in cases
2. **Relationship Inference**: Discover implicit relationships
3. **Definition Refinement**: Improve concept descriptions
4. **Hierarchy Extension**: Suggest new classifications

## 9. Quality Assurance

### Purpose
Validate and improve data quality using LLM analysis.

### Use Cases
1. **Triple Validation**: Check RDF triple correctness
2. **Consistency Checking**: Identify contradictions
3. **Completeness Analysis**: Find missing information
4. **Format Standardization**: Ensure uniform structure

## 10. Research and Experimentation

### Purpose
Support research on LLM-ontology integration effectiveness.

### Current Experiments
1. **Extensional Definition Study**: Testing McLaren's approach
2. **Prompt Engineering**: Optimizing for ethical reasoning
3. **Hybrid Reasoning**: Combining symbolic and neural approaches
4. **Evaluation Metrics**: Developing assessment methods

### Future Research
- Multi-modal analysis (text + diagrams)
- Real-time decision support
- Explainable AI for ethics
- Cross-domain transfer learning

## Performance Optimization

### Caching Strategy
```python
# Cache similar queries
cache_key = hash(prompt + str(ontology_concepts))
if cache_key in response_cache:
    return response_cache[cache_key]
```

### Batch Processing
```python
# Process multiple sections together
sections = ["section1", "section2", "section3"]
prompts = [format_prompt(s) for s in sections]
results = llm.batch_complete(prompts)
```

### Context Management
```python
# Limit context to relevant information
relevant_context = filter_by_relevance(
    full_context, 
    query, 
    max_tokens=50000
)
```

## Monitoring and Metrics

### Usage Tracking
- API calls per service
- Token consumption by use case
- Response times
- Error rates

### Quality Metrics
- Extraction accuracy
- Concept mapping precision
- Decision agreement rates
- User satisfaction scores

### Cost Analysis
- Cost per use case
- ROI for different applications
- Optimization opportunities
- Budget allocation