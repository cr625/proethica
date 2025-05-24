# ProEthica Experiment System Technical Reference

This document serves as a comprehensive technical reference for the ProEthica experiment system implementation, preserving detailed implementation notes, code examples, and architectural decisions.

## Database Schema

### Core Tables

#### ExperimentRun
```sql
CREATE TABLE experiment_runs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    meta_data JSONB
);
```

#### Prediction
```sql
CREATE TABLE predictions (
    id SERIAL PRIMARY KEY,
    experiment_run_id INTEGER REFERENCES experiment_runs(id),
    case_id INTEGER NOT NULL,
    prediction_type VARCHAR(50) NOT NULL,
    baseline_prediction TEXT,
    enhanced_prediction TEXT,
    meta_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### PredictionTarget
```sql
CREATE TABLE prediction_targets (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

-- Insert default targets
INSERT INTO prediction_targets (name, description) VALUES 
('conclusion', 'Predict the conclusion section of engineering ethics cases'),
('full_analysis', 'Generate complete case analysis including facts, issues, and conclusion');
```

#### ExperimentEvaluation
```sql
CREATE TABLE experiment_evaluations (
    id SERIAL PRIMARY KEY,
    prediction_id INTEGER REFERENCES predictions(id),
    evaluator_id VARCHAR(100),
    reasoning_quality INTEGER CHECK (reasoning_quality >= 0 AND reasoning_quality <= 10),
    persuasiveness INTEGER CHECK (persuasiveness >= 0 AND persuasiveness <= 10),
    coherence INTEGER CHECK (coherence >= 0 AND coherence <= 10),
    accuracy BOOLEAN,
    support_quality INTEGER CHECK (support_quality >= 0 AND support_quality <= 10),
    overall_preference INTEGER CHECK (overall_preference >= 0 AND overall_preference <= 10),
    comments TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Critical Constraint Issue
**BLOCKER**: The `experiment_run_id` field in `predictions` table has NOT NULL constraint but quick predictions need to work without formal experiments.

**Solutions**:
1. Create default experiment run for standalone predictions
2. Make `experiment_run_id` nullable
3. Use separate table for standalone vs experiment predictions

## API Endpoints

### Experiment Management
- `GET /experiment/` - Dashboard with case list and statistics
- `GET /experiment/setup?id={experiment_id}` - Experiment configuration
- `POST /experiment/` - Create new experiment
- `PUT /experiment/{id}` - Update experiment

### Prediction Generation
- `POST /experiment/quick_predict/<case_id>` - Generate standalone prediction
- `POST /experiment/predict_conclusions` - Batch prediction generation
- `GET /experiment/case_comparison/<case_id>` - Side-by-side comparison

### Results and Evaluation
- `GET /experiment/results?id={experiment_id}` - Aggregated results
- `GET /experiment/case_results?id={experiment_id}&case_id={case_id}` - Case-specific results
- `POST /experiment/api/evaluations` - Submit evaluation

## Code Implementation

### Ontology Entity Integration

#### Retrieving Section Associations
```python
def get_section_ontology_entities(self, document_id: int, sections: Dict[str, str]) -> Dict[str, List[Dict]]:
    """
    Get ontology entities associated with document sections.
    Updated to use get_section_associations method (not deprecated get_section_triples).
    """
    ontology_entities = {}
    
    for section_type, content in sections.items():
        section_id = self._get_section_id(document_id, section_type)
        if section_id:
            try:
                # Use updated API method
                associations_result = self.triple_association_service.get_section_associations(section_id)
                
                # Extract triples from associations result
                triples = []
                if associations_result and 'associations' in associations_result:
                    triples = associations_result['associations']
                
                if triples:
                    ontology_entities[section_type] = triples
                    
            except Exception as e:
                self.logger.warning(f"Could not retrieve ontology entities for section {section_id}: {e}")
    
    return ontology_entities
```

#### Enhanced Prompt Construction
```python
def _construct_conclusion_prediction_prompt(self, document: Document, sections: Dict[str, str], 
                                          ontology_entities: Dict[str, List[Dict]], 
                                          similar_cases: List[Dict[str, Any]]) -> str:
    """
    Construct ontology-enhanced conclusion prediction prompt using FIRAC framework.
    """
    prompt_parts = [
        "You are an expert in engineering ethics analyzing NSPE cases.",
        "Use the FIRAC framework (Facts, Issues, Rules, Application, Conclusion) for your analysis.",
        "",
        "# CASE INFORMATION",
        f"**Title**: {document.title}",
        ""
    ]
    
    # Add case sections
    for section_type, content in sections.items():
        if section_type.lower() != 'conclusion':  # Exclude conclusion for prediction
            prompt_parts.extend([
                f"## {section_type.upper()}",
                content.strip(),
                ""
            ])
    
    # Add ontology entities if available
    if ontology_entities:
        prompt_parts.extend([
            "# RELEVANT ENGINEERING ETHICS CONCEPTS",
            "Consider these relevant concepts in your analysis:",
            ""
        ])
        
        for section_type, entities in ontology_entities.items():
            if entities:
                prompt_parts.append(f"**{section_type.title()} - Related Concepts:**")
                for entity in entities[:5]:  # Limit to top 5 entities
                    subject = entity.get('subject', 'Unknown')
                    predicate = entity.get('predicate', 'relates to')
                    obj = entity.get('object', 'Unknown')
                    prompt_parts.append(f"- {subject} {predicate} {obj}")
                prompt_parts.append("")
    
    # Add similar cases context
    if similar_cases:
        prompt_parts.extend([
            "# SIMILAR CASES FOR CONTEXT",
            "Consider these similar cases:",
            ""
        ])
        for case in similar_cases[:3]:  # Limit to top 3
            prompt_parts.append(f"- **{case.get('title', 'Unknown')}**: {case.get('summary', 'No summary')}")
        prompt_parts.append("")
    
    # Add task instructions
    prompt_parts.extend([
        "# TASK",
        "Generate a conclusion for this case following NSPE format:",
        "1. Use formal engineering ethics principles",
        "2. Reference relevant NSPE Code provisions when applicable",
        "3. Provide clear ethical reasoning",
        "4. Format as a professional ethics conclusion",
        "",
        "**Generate only the conclusion section:**"
    ])
    
    return "\n".join(prompt_parts)
```

### Mock Testing Framework

#### Creating Test Entities
```python
def create_mock_ontology_entities(document_id, sections):
    """Create mock ontology entities for testing ontology integration."""
    mock_entities = {}
    
    # Facts-related entities
    if any(section_type in ['facts', 'text'] for section_type in sections.keys()):
        mock_entities['facts'] = [
            {
                'subject': 'Engineer',
                'predicate': 'hasRole',
                'object': 'Professional',
                'score': 0.92,
                'source': 'mock'
            },
            {
                'subject': 'Professional',
                'predicate': 'hasObligation',
                'object': 'PublicSafety',
                'score': 0.88,
                'source': 'mock'
            }
        ]
    
    # Discussion-related entities  
    if any(section_type in ['discussion', 'analysis'] for section_type in sections.keys()):
        mock_entities['discussion'] = [
            {
                'subject': 'EthicalDecision',
                'predicate': 'requiresConsideration',
                'object': 'StakeholderInterests',
                'score': 0.85,
                'source': 'mock'
            },
            {
                'subject': 'Engineer',
                'predicate': 'mustUphold',
                'object': 'NSPECode',
                'score': 0.90,
                'source': 'mock'
            }
        ]
    
    return mock_entities
```

### Validation Metrics

#### Ontology Entity Validation
```python
def validate_ontology_integration(prediction: str, ontology_entities: Dict[str, List[Dict]]) -> Dict[str, Any]:
    """
    Validate how well ontology entities are integrated into the prediction.
    """
    if not ontology_entities:
        return {
            'total_entities': 0,
            'mentioned_entities': 0,
            'mention_ratio': 0.0,
            'mentioned_concepts': [],
            'validation_passed': False,
            'message': 'No ontology entities provided'
        }
    
    # Flatten all entities
    all_entities = []
    for entities in ontology_entities.values():
        all_entities.extend(entities)
    
    # Check which entities are mentioned in prediction
    mentioned_entities = []
    prediction_lower = prediction.lower()
    
    for entity in all_entities:
        subject = entity.get('subject', '').lower()
        obj = entity.get('object', '').lower()
        
        # Check if entity concepts appear in prediction
        if (subject and subject in prediction_lower) or (obj and obj in prediction_lower):
            mentioned_entities.append(entity)
    
    total_entities = len(all_entities)
    mentioned_count = len(mentioned_entities)
    mention_ratio = mentioned_count / total_entities if total_entities > 0 else 0.0
    
    return {
        'total_entities': total_entities,
        'mentioned_entities': mentioned_count,
        'mention_ratio': mention_ratio,
        'mentioned_concepts': mentioned_entities,
        'validation_passed': mention_ratio > 0.1,  # 10% threshold
        'message': f"Mentioned {mentioned_count}/{total_entities} ontology entities ({mention_ratio:.1%})"
    }
```

## System Architecture

### Workflow Integration

#### Quick Prediction Workflow
```
/experiment/ → Select Case → Click "Predict Conclusion" → 
→ AJAX Request → PredictionService.generate_conclusion_prediction() →
→ Ontology Entity Retrieval → Enhanced Prompt Construction →
→ LLM API Call → Response Processing → Validation →
→ Database Storage → Redirect to Comparison View
```

#### Formal Experiment Workflow (Currently Blocked)
```
/experiment/conclusion_setup → Create ExperimentRun → 
→ Configure Parameters → Select Cases → Execute Batch →
→ [FAILS: experiment_run_id constraint] → Error Handling
```

### Service Dependencies

#### PredictionService Dependencies
- `SectionTripleAssociationService` - For ontology entity retrieval
- `LLMService` - For Claude API integration  
- `DocumentService` - For case retrieval
- `SimilarCaseService` - For context enhancement

#### API Compatibility Updates
**CRITICAL**: Updated from deprecated `get_section_triples()` to `get_section_associations()` method.

**Before**:
```python
triples = self.triple_association_service.get_section_triples(section_id)
```

**After**:
```python
associations_result = self.triple_association_service.get_section_associations(section_id)
triples = []
if associations_result and 'associations' in associations_result:
    triples = associations_result['associations']
```

## Configuration

### Flask Application Launch
Based on `.vscode/launch.json`, the application starts with:
```json
{
    "name": "Live LLM - Flask App with MCP",
    "type": "python",
    "request": "launch",
    "program": "run.py",
    "console": "integratedTerminal",
    "env": {
        "FLASK_ENV": "development",
        "FLASK_DEBUG": "1"
    }
}
```

### Required Environment Variables
- Database connection parameters
- LLM service API keys
- MCP server configuration

## Performance Metrics

### Current Achievements
- **Ontology Integration**: 15% mention ratio (target: >20%)
- **API Response Time**: Variable based on LLM service
- **Database Operations**: Functional with constraint issues
- **UI Responsiveness**: AJAX-based with loading indicators

### Test Results Summary
```json
{
    "ontology_entity_mentions": 3,
    "mention_ratio": 0.15,
    "validation_status": "passed",
    "total_entities_available": 20,
    "prediction_generation_time": "~30-60 seconds",
    "ui_workflow": "functional"
}
```

## Troubleshooting

### Common Issues

1. **experiment_run_id Constraint Error**
   - **Symptom**: `null value in column "experiment_run_id" violates not-null constraint`
   - **Cause**: Quick predictions don't have formal experiment context
   - **Solutions**: See Database Schema section above

2. **Ontology Entity Retrieval Failures**
   - **Symptom**: No entities found for sections
   - **Cause**: Missing section associations or API compatibility
   - **Fix**: Verify `get_section_associations` method availability

3. **LLM Service Timeouts**
   - **Symptom**: Prediction generation fails after long wait
   - **Cause**: Large prompts or service unavailability
   - **Fix**: Implement retry logic and prompt optimization

### Debug Commands

```bash
# Check database constraint status
./check_database_triples.py

# Test ontology integration
./run_ontology_validation.sh

# Debug prediction service
./debug_flask_app.py
```

## Future Enhancements

### Immediate Priorities
1. Fix experiment_run_id constraint issue
2. Improve ontology entity mention ratio (target: >20%)
3. Optimize prompt engineering for better context utilization

### Medium-term Goals
1. Implement batch processing for multiple cases
2. Add user authentication for evaluators
3. Create data export functionality
4. Develop admin interface for experiment management

### Long-term Vision
1. Integration with additional ontology sources
2. Machine learning-based entity relevance scoring
3. Real-time collaboration features for evaluators
4. Advanced analytics and visualization capabilities

---
**Document Version**: 1.0  
**Last Updated**: 2025-05-23 08:45  
**Status**: Technical Reference - Maintain for Implementation Details
