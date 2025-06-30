# Enhanced Association Schema Design - Phase 2

**Date**: June 9, 2025  
**Status**: In Progress  
**Dependencies**: Phase 1 Analysis Complete

## Overview

This document defines the enhanced database schema for outcome-aware guideline associations that will enable case outcome prediction based on ethical guideline patterns.

## Core Schema Design

### **1. Case-Guideline Associations Table**

```sql
CREATE TABLE case_guideline_associations (
    id SERIAL PRIMARY KEY,
    case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
    guideline_concept_id INTEGER REFERENCES entity_triples(id) ON DELETE CASCADE,
    section_type VARCHAR(50) NOT NULL, -- facts, discussion, conclusion, etc.
    
    -- Association Strength
    semantic_similarity DECIMAL(5,3), -- 0.000-1.000 embedding similarity
    keyword_overlap DECIMAL(5,3),    -- 0.000-1.000 term overlap score
    contextual_relevance DECIMAL(5,3), -- 0.000-1.000 context matching
    overall_confidence DECIMAL(5,3) NOT NULL, -- 0.000-1.000 combined score
    
    -- Prediction Enhancement Fields
    outcome_correlation JSONB, -- historical outcome correlation data
    pattern_indicators JSONB,  -- specific pattern matches
    prediction_weight DECIMAL(5,3), -- weight for outcome prediction
    
    -- Reasoning and Metadata
    association_reasoning TEXT,
    association_method VARCHAR(50), -- 'embedding', 'keyword', 'llm', 'hybrid'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes for performance
    UNIQUE(case_id, guideline_concept_id, section_type)
);

-- Performance indexes
CREATE INDEX idx_case_guideline_case_id ON case_guideline_associations(case_id);
CREATE INDEX idx_case_guideline_concept_id ON case_guideline_associations(guideline_concept_id);
CREATE INDEX idx_case_guideline_confidence ON case_guideline_associations(overall_confidence DESC);
CREATE INDEX idx_case_guideline_section ON case_guideline_associations(section_type);
```

### **2. Outcome Pattern Analysis Table**

```sql
CREATE TABLE outcome_patterns (
    id SERIAL PRIMARY KEY,
    pattern_name VARCHAR(100) NOT NULL UNIQUE,
    pattern_type VARCHAR(50) NOT NULL, -- 'guideline_strength', 'section_pattern', 'decision_factor'
    
    -- Pattern Definition
    pattern_criteria JSONB NOT NULL, -- conditions that define this pattern
    guideline_concepts TEXT[], -- array of guideline concept URIs involved
    section_types TEXT[], -- array of section types involved
    
    -- Outcome Correlation Data
    ethical_correlation DECIMAL(5,3), -- correlation with ethical outcomes
    unethical_correlation DECIMAL(5,3), -- correlation with unethical outcomes
    confidence_level DECIMAL(5,3), -- statistical confidence in correlation
    sample_size INTEGER, -- number of cases supporting this pattern
    
    -- Pattern Metadata
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_validated TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- Example patterns
INSERT INTO outcome_patterns (pattern_name, pattern_type, pattern_criteria, ethical_correlation, unethical_correlation, confidence_level, description) VALUES
('public_safety_prioritized', 'decision_factor', '{"public_safety_association": ">0.8", "action_taken": true}', 0.92, 0.08, 0.85, 'Cases where public safety guidelines are strongly associated and protective action is taken'),
('competence_boundary_exceeded', 'guideline_strength', '{"professional_competence_association": ">0.7", "competence_exceeded": true}', 0.15, 0.85, 0.78, 'Cases where work is performed outside competence area despite strong competence guidelines'),
('honest_communication_maintained', 'section_pattern', '{"honesty_association": ">0.6", "transparent_communication": true}', 0.88, 0.12, 0.81, 'Cases with strong honesty associations and transparent communication patterns');
```

### **3. Case Prediction Results Table**

```sql
CREATE TABLE case_prediction_results (
    id SERIAL PRIMARY KEY,
    case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
    
    -- Prediction Results
    predicted_outcome VARCHAR(50) NOT NULL, -- 'ethical', 'unethical', 'unclear'
    prediction_confidence DECIMAL(5,3) NOT NULL, -- 0.000-1.000
    actual_outcome VARCHAR(50), -- for validation when known
    
    -- Supporting Evidence
    key_patterns JSONB, -- array of pattern matches that led to prediction
    guideline_associations JSONB, -- summary of relevant associations
    section_analysis JSONB, -- section-by-section analysis
    
    -- Prediction Metadata
    prediction_method VARCHAR(50), -- algorithm used for prediction
    model_version VARCHAR(20), -- version of prediction algorithm
    feature_importance JSONB, -- which factors were most important
    similar_cases INTEGER[], -- array of similar case IDs
    
    -- Quality Metrics
    explanation_quality DECIMAL(5,3), -- how well can we explain the prediction
    uncertainty_level DECIMAL(5,3), -- measure of prediction uncertainty
    
    -- Timestamps
    predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    validated_at TIMESTAMP, -- when actual outcome was confirmed
    
    UNIQUE(case_id, model_version)
);

-- Performance indexes  
CREATE INDEX idx_prediction_case_id ON case_prediction_results(case_id);
CREATE INDEX idx_prediction_confidence ON case_prediction_results(prediction_confidence DESC);
CREATE INDEX idx_prediction_outcome ON case_prediction_results(predicted_outcome);
CREATE INDEX idx_prediction_accuracy ON case_prediction_results(predicted_outcome, actual_outcome) WHERE actual_outcome IS NOT NULL;
```

### **4. Pattern Learning History Table**

```sql
CREATE TABLE pattern_learning_history (
    id SERIAL PRIMARY KEY,
    case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
    pattern_id INTEGER REFERENCES outcome_patterns(id) ON DELETE CASCADE,
    
    -- Learning Data
    pattern_strength DECIMAL(5,3), -- how strongly this pattern applies to this case
    outcome_contribution DECIMAL(5,3), -- how much this pattern contributed to outcome
    validation_result BOOLEAN, -- whether pattern correctly predicted outcome
    
    -- Learning Context
    learning_phase VARCHAR(50), -- 'training', 'validation', 'testing'
    feature_values JSONB, -- specific feature values for this case
    
    -- Metadata
    learned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model_version VARCHAR(20)
);
```

## Enhanced Association Data Structure

### **Association Confidence Calculation**

```python
class AssociationConfidence:
    def calculate_overall_confidence(self, semantic_sim, keyword_overlap, contextual_rel):
        """
        Weighted combination of multiple similarity measures
        """
        return (
            0.5 * semantic_sim +      # Primary: embedding similarity
            0.3 * contextual_rel +    # Secondary: context matching  
            0.2 * keyword_overlap     # Tertiary: keyword overlap
        )
    
    def calculate_prediction_weight(self, confidence, outcome_correlation, pattern_strength):
        """
        Weight for use in outcome prediction
        """
        return confidence * outcome_correlation * pattern_strength
```

### **Outcome Correlation Structure**

```json
{
  "outcome_correlation": {
    "ethical": {
      "correlation": 0.78,
      "sample_size": 12,
      "confidence_interval": [0.65, 0.88]
    },
    "unethical": {
      "correlation": 0.22,  
      "sample_size": 12,
      "confidence_interval": [0.12, 0.35]
    },
    "last_updated": "2025-06-09T19:30:00Z"
  }
}
```

### **Pattern Indicators Structure**

```json
{
  "pattern_indicators": {
    "public_safety_involved": true,
    "competence_boundary_clear": false,
    "stakeholder_conflict": true,
    "economic_pressure": false,
    "safety_action_taken": true,
    "pattern_strength": 0.82,
    "matched_patterns": [
      "public_safety_prioritized",
      "stakeholder_conflict_resolved"
    ]
  }
}
```

## Migration Strategy

### **Phase 2A: Create Core Tables**

```sql
-- migration_001_create_associations_table.sql
CREATE TABLE case_guideline_associations (
    -- Core table structure as defined above
);

-- migration_002_create_outcome_patterns.sql  
CREATE TABLE outcome_patterns (
    -- Pattern table structure as defined above
);

-- migration_003_create_prediction_results.sql
CREATE TABLE case_prediction_results (
    -- Prediction results structure as defined above
);
```

### **Phase 2B: Populate Initial Data**

```python
# populate_baseline_associations.py
def create_baseline_associations():
    """
    Create initial associations using semantic similarity between 
    case sections and guideline concepts
    """
    for case in cases:
        for section in case.sections:
            for guideline_concept in guideline_concepts:
                similarity = calculate_semantic_similarity(section, guideline_concept)
                if similarity > 0.3:  # threshold for inclusion
                    create_association(case, guideline_concept, section, similarity)
```

### **Phase 2C: Initialize Pattern Recognition**

```python
# initialize_patterns.py
def create_initial_patterns():
    """
    Create initial outcome patterns based on Phase 1 hypotheses
    """
    patterns = [
        {
            'name': 'public_safety_prioritized',
            'criteria': {'public_safety_association': '>0.8', 'action_taken': True},
            'description': 'Strong public safety association with protective action'
        },
        {
            'name': 'competence_boundary_exceeded', 
            'criteria': {'competence_association': '>0.7', 'boundary_exceeded': True},
            'description': 'Work performed outside competence area'
        }
        # Additional patterns from Phase 1 analysis
    ]
    for pattern in patterns:
        create_outcome_pattern(pattern)
```

## Data Validation Rules

### **Association Quality Checks**

```python
def validate_association(association):
    """Ensure association data quality"""
    assert 0.0 <= association.overall_confidence <= 1.0
    assert association.semantic_similarity is not None
    assert association.section_type in VALID_SECTION_TYPES
    assert association.association_method in VALID_METHODS
    return True
```

### **Pattern Validation Rules**

```python
def validate_pattern(pattern):
    """Ensure pattern definition quality"""
    assert pattern.ethical_correlation + pattern.unethical_correlation <= 1.1  # Allow slight float precision
    assert pattern.sample_size >= MIN_SAMPLE_SIZE
    assert pattern.confidence_level >= MIN_CONFIDENCE
    return True
```

## Performance Considerations

### **Query Optimization**

```sql
-- Efficient case-to-associations lookup
SELECT cga.*, et.subject, et.object_literal
FROM case_guideline_associations cga
JOIN entity_triples et ON cga.guideline_concept_id = et.id  
WHERE cga.case_id = ? AND cga.overall_confidence > 0.5
ORDER BY cga.overall_confidence DESC;

-- Pattern matching for prediction
SELECT op.pattern_name, op.ethical_correlation, cga.overall_confidence
FROM case_guideline_associations cga
JOIN outcome_patterns op ON op.guideline_concepts @> ARRAY[et.subject]
JOIN entity_triples et ON cga.guideline_concept_id = et.id
WHERE cga.case_id = ?;
```

### **Caching Strategy**

```python
class PredictionCache:
    """Cache prediction results for performance"""
    
    def get_case_prediction(self, case_id, model_version):
        """Get cached prediction if available and valid"""
        return cache.get(f"prediction:{case_id}:{model_version}")
    
    def set_case_prediction(self, case_id, model_version, result):
        """Cache prediction with appropriate TTL"""
        cache.set(f"prediction:{case_id}:{model_version}", result, ttl=3600)
```

## Integration Points

### **With Existing Systems**

1. **Document Processing Pipeline**: Automatically generate associations when cases are imported
2. **Guideline Management**: Update associations when guideline concepts change
3. **Case Management**: Display predictions in case detail views
4. **Type Management**: Leverage improved type classifications for better associations

### **API Design**

```python
# Association API endpoints
GET /api/cases/{case_id}/guideline-associations
POST /api/cases/{case_id}/guideline-associations
PUT /api/cases/{case_id}/guideline-associations/{assoc_id}

# Prediction API endpoints  
GET /api/cases/{case_id}/prediction
POST /api/cases/{case_id}/predict
GET /api/patterns/outcome-correlations

# Batch processing endpoints
POST /api/batch/generate-associations
POST /api/batch/update-patterns
```

## Testing Strategy

### **Unit Tests**

```python
def test_association_confidence_calculation():
    """Test confidence calculation logic"""
    
def test_pattern_matching():
    """Test pattern recognition logic"""
    
def test_outcome_prediction():
    """Test prediction algorithm"""
```

### **Integration Tests**

```python
def test_case_import_with_associations():
    """Test full pipeline from case import to associations"""
    
def test_prediction_accuracy():
    """Test prediction accuracy against known outcomes"""
```

### **Performance Tests**

```python
def test_association_generation_performance():
    """Ensure association generation completes in reasonable time"""
    
def test_prediction_response_time():
    """Ensure predictions return within 2 second target"""
```

## Next Steps (Phase 3)

1. **Implement Schema**: Create database migrations and tables
2. **Build Association Generator**: Create service to generate initial associations
3. **Implement Pattern Recognition**: Build pattern matching logic
4. **Create Prediction Service**: Implement outcome prediction algorithm
5. **Validate with Test Data**: Test against known case outcomes

This enhanced schema provides the foundation for intelligent, outcome-aware guideline associations that can support accurate case outcome prediction while maintaining explainability and confidence scoring.