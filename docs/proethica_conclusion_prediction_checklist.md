# ProEthica Enhanced Conclusion Prediction Implementation Checklist

## 1. Database Schema Updates
- [x] 1.1. Add `target` field to `Prediction` model in `app/models/experiment.py`
- [x] 1.2. Create `PredictionTarget` model in `app/models/experiment.py`
- [x] 1.3. Create SQL migration script for schema updates in `migrations/sql/add_prediction_target.sql`
- [x] 1.4. Run migration script and verify database changes
- [x] 1.5. Update model relationships to support new schema

## 2. Prediction Service Enhancements
- [x] 2.1. Implement `generate_conclusion_prediction` method in `PredictionService`
- [x] 2.2. Create `_construct_conclusion_prediction_prompt` function
- [x] 2.3. Implement `_extract_conclusion` method for parsing responses
- [x] 2.4. Develop `_validate_conclusion` method for quality checks
- [x] 2.5. Fix AIMessage handling in prediction methods
- [ ] 2.6. Test ontology entity integration in prompts
- [ ] 2.7. Optimize context window usage in prompts

## 3. Experiment Interface Extensions
- [x] 3.1. Add `conclusion_prediction_setup` route to `app/routes/experiment.py`
- [x] 3.2. Create `predict_conclusions` endpoint in `app/routes/experiment.py`
- [x] 3.3. Implement `conclusion_results` route for viewing predictions
- [x] 3.4. Add `conclusion_comparison` route for side-by-side comparison
- [x] 3.5. Create template `templates/experiment/conclusion_setup.html`
- [x] 3.6. Create template `templates/experiment/conclusion_results.html`
- [x] 3.7. Create template `templates/experiment/conclusion_comparison.html`
- [x] 3.8. Create template `templates/experiment/conclusion_run.html`
- [x] 3.9. Create streamlined experiment index template with quick prediction workflow
- [x] 3.10. Add `quick_predict` endpoint for single case predictions
- [x] 3.11. Add `case_comparison` route for streamlined comparison view

## 4. Standalone Script Development
- [ ] 4.1. Create `run_conclusion_predictions.py` script
- [ ] 4.2. Implement environment setup function
- [ ] 4.3. Develop batch processing logic for multiple cases
- [ ] 4.4. Add command-line argument parsing
- [ ] 4.5. Implement results storage and reporting
- [ ] 4.6. Test script functionality with sample cases

## 5. Testing and Refinement
- [ ] 5.1. Test with a small set of cases (3-5) for initial validation
- [ ] 5.2. Refine prompts based on initial results
- [ ] 5.3. Optimize conclusion extraction from LLM responses
- [ ] 5.4. Enhance validation metrics for better quality assessment
- [ ] 5.5. Test with a larger set of cases (10+)
- [ ] 5.6. Analyze and document patterns in prediction quality

## 6. Visualization and Analysis
- [x] 6.1. Implement side-by-side comparison display
- [ ] 6.2. Add highlighting for ontology concepts in predictions
- [x] 6.3. Create metrics display for prediction quality
- [ ] 6.4. Develop aggregated statistics view across cases
- [x] 6.5. Add export functionality for results and comparisons

## 7. Documentation
- [ ] 7.1. Update project documentation with new features
- [ ] 7.2. Create user guide for running conclusion predictions
- [ ] 7.3. Document API changes and new endpoints
- [ ] 7.4. Add code comments for maintainability

## Current Progress

- Total tasks: 20/39 complete (51%)
- Current focus: Streamlined Workflow Implementation (Phase 3+)

## NEW: Streamlined End-to-End Workflow ✓

### Implemented Features:
1. **Quick Prediction Interface**: Users can now select any case from the experiment dashboard and immediately generate a conclusion prediction
2. **Streamlined Case Selection**: Simple UI showing all available cases with prediction status
3. **Direct Comparison View**: Side-by-side display of original vs predicted conclusions
4. **Real-time Processing**: AJAX-based prediction generation with loading indicators
5. **Integrated Validation Metrics**: Display of ontology entity usage and prediction quality metrics

### Workflow:
```
/experiment/ → View all cases → Click "Predict Conclusion" → 
→ Loading modal → Redirect to comparison view → 
→ See original vs predicted conclusion side-by-side
```

### Key Routes Added:
- `GET /experiment/` - Enhanced dashboard with case list and statistics
- `POST /experiment/quick_predict/<case_id>` - Generate prediction for single case
- `GET /experiment/case_comparison/<case_id>` - View side-by-side comparison

## Implementation Timeline Estimate

1. **Database Schema Updates**: Days 1-2 ✓
2. **Prediction Service Enhancements**: Days 2-5 ✓ (Mostly complete)
3. **Experiment Interface Extensions**: Days 5-8 ✓ (Complete with streamlined workflow)
4. **Standalone Script Development**: Days 8-10
5. **Testing and Refinement**: Days 10-13
6. **Visualization and Analysis**: Days 13-15 (Partially complete)
7. **Documentation**: Throughout (completed by day 15)

Total estimated time: 15 days

## Next Steps for End-to-End Testing

1. **Test the streamlined workflow** by visiting `http://localhost:3333/experiment/`
2. **Select a case** and generate a conclusion prediction
3. **Review the comparison** between original and predicted conclusions
4. **Refine prompts** based on prediction quality
5. **Run batch experiments** for comprehensive evaluation
