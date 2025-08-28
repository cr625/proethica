# Intelligent Multi-Pass Annotation System

## 🎯 Problem Analysis

**Current Issues:**
1. **Simple keyword matching** - Terms matched regardless of context
2. **No semantic understanding** - "Engineering" matches "Engineering System" inappropriately  
3. **Missing ontology definitions** - All 124 entities in proethica-intermediate have empty definitions
4. **No contextual validation** - No verification that concept matches usage

**LLM Advantages:**
- **Contextual understanding** - Exactly how transformers work
- **Semantic matching** - Can understand when "public safety" means safety vs public
- **Multi-step reasoning** - Can validate and refine matches

## 🏗️ Multi-Pass Architecture Design

### **Phase 1: Context-Aware Candidate Detection**
```
Input: Document text + Available ontology concepts
LLM Task: "Identify which concepts from this ontology are meaningfully present in this text"
Output: List of {concept, text_span, confidence, reasoning}
```

### **Phase 2: Contextual Validation** 
```
Input: Candidate matches + surrounding context
LLM Task: "Validate each match - does the concept truly apply in this context?"
Output: Filtered list with contextual confidence scores
```

### **Phase 3: Semantic Refinement**
```
Input: Validated matches + concept definitions
LLM Task: "Refine matches based on full concept meanings and relationships"
Output: Final high-quality annotations with explanations
```

## 🛠️ Implementation Components

### **Component 1: Intelligent Annotation Service**
`app/services/intelligent_annotation_service.py`
- LangChain orchestration with 3-pass pipeline
- Context-aware prompting with ontology concepts
- Confidence scoring and validation
- Batch processing for efficiency

### **Component 2: Enhanced Ontology Definitions**  
`scripts/enrich_ontology_definitions.py`
- LLM-generated definitions for missing concepts
- SKOS-compatible metadata structure
- BFO/IAO alignment for professional ethics concepts

### **Component 3: Multi-Pass Orchestrator**
`app/services/annotation_orchestrator.py`  
- Sequential LangChain processing
- Error handling and fallbacks
- Performance monitoring
- Caching and optimization

## 📊 Expected Improvements

**Quality Metrics:**
- **Precision**: 90%+ (vs ~60% with keyword matching)
- **Contextual Accuracy**: 85%+ proper concept-context alignment
- **Rich Metadata**: Full definitions and relationships

**User Experience:**
- **Meaningful annotations** - Only concepts that truly apply
- **Rich explanations** - Why each annotation was made  
- **Confidence indicators** - Clear quality signals

## 🎯 Implementation Priority

### **Phase A: Ontology Enhancement** (Week 1)
1. **Generate definitions** for all 124 entities using LLM
2. **Populate metadata** with SKOS properties
3. **Create relationships** between concepts

### **Phase B: Multi-Pass Annotation** (Week 2)  
1. **Build LangChain orchestrator** with 3-pass system
2. **Implement context-aware prompting**
3. **Add confidence scoring and validation**

### **Phase C: Integration & Testing** (Week 3)
1. **A/B testing** against keyword system
2. **Performance optimization**  
3. **User interface enhancements**

## 🔧 Technical Architecture

```
┌─────────────────────────────────────────┐
│           Document Text                 │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│  Phase 1: Concept Detection            │
│  - Load ontology concepts               │  
│  - LLM identifies relevant concepts     │
│  - Extract text spans and confidence    │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│  Phase 2: Contextual Validation        │
│  - Analyze surrounding context          │
│  - Validate concept appropriateness     │
│  - Filter low-confidence matches        │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│  Phase 3: Semantic Refinement          │
│  - Apply concept definitions            │
│  - Check for concept relationships      │
│  - Generate final explanations          │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│     High-Quality Annotations           │
│  - Contextually appropriate             │
│  - Confidence-scored                    │ 
│  - Rich metadata & explanations         │
└─────────────────────────────────────────┘
```

## 🎨 Prompt Engineering Strategy

### **Detection Prompt:**
```
You are an expert in professional ethics ontology annotation. 

Given this text about professional engineering ethics:
"{document_text}"

And these available ethical concepts:
{concept_list_with_labels}

Identify which concepts are meaningfully referenced in the text. 
For each match, provide:
- Exact text span
- Concept URI  
- Confidence (0.0-1.0)
- Brief reasoning

Only include concepts that are genuinely relevant to the context.
```

### **Validation Prompt:**
```
Review this potential annotation:
- Text: "{text_span}" 
- Concept: "{concept_label}"
- Context: "{surrounding_text}"

Questions:
1. Does the concept truly apply in this specific context?
2. Is this the most appropriate concept for this usage?
3. What is your confidence level (0.0-1.0)?

Provide validation with reasoning.
```

## 🚀 Success Criteria

**Quantitative:**
- **Precision > 85%** (manually validated sample)
- **User satisfaction > 4.0/5** (vs current system)
- **Processing time < 30 seconds** per document

**Qualitative:**  
- **Contextually meaningful** annotations
- **Rich explanatory content** in popups
- **Professional-grade** accuracy for ethics domain

---

This system will transform annotation from basic keyword matching to intelligent semantic understanding, matching the sophistication users expect from modern LLM-powered tools.