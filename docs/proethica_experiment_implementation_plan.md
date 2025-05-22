# ProEthica Experiment Implementation Plan

This document outlines the implementation plan for the ProEthica experiment interface, which compares baseline LLM analysis with ontology-enhanced ProEthica analysis for engineering ethics cases.

## Implementation Components

### Core Components

1. **Database Models**
   - ExperimentRun: Track experiment configurations and runs
   - Prediction: Store predictions under different experimental conditions
   - Evaluation: Capture reviewer feedback on predictions

2. **Services**
   - PredictionService: Generate baseline and ProEthica predictions
   - Evaluation metrics and analysis utilities

3. **Interface**
   - Experiment creation and configuration
   - Case selection interface
   - Prediction generation workflow
   - Results visualization
   - Evaluation interface

### Implementation Progress

- [x] Created database models for experiments, predictions, and evaluations
- [x] Created SQL migration script for experiment tables
- [x] Created baseline prediction service
- [x] Created experiment controller/routes
- [x] Created experiment UI templates
   - [x] Experiment dashboard
   - [x] Experiment setup
   - [x] Case selection
   - [x] Experiment run interface
   - [x] Results overview
   - [x] Case results and evaluation

### Remaining Tasks

- [x] Register experiment blueprint in app/__init__.py
- [x] Run database migrations to create experiment tables
- [x] Fix database model column naming (metadata -> meta_data)
- [x] Create run script for experiment interface
- [x] Fix class name conflict (Evaluation -> ExperimentEvaluation)
- [x] Implement ProEthica enhanced prediction service
   - [x] Retrieve ontology entities associated with case sections
   - [x] Generate ontology-constrained FIRAC prompts
   - [x] Implement bidirectional validation
- [ ] Add API endpoints for evaluation submission
- [ ] Create data export functionality
- [ ] Implement admin interface for experiment management
- [ ] Add visualization of experiment results
- [ ] Add user authentication for evaluators

## Implementation Details

### System Integration

The experiment interface integrates with the existing ProEthica system by:

1. Using the document structure and section data
2. Leveraging section-triple associations for ontology integration
3. Utilizing the existing LLM service for predictions
4. Working with case sections and metadata

### Experiment Flow

1. Administrator creates a new experiment and configures parameters
2. Administrator selects cases for analysis
3. System generates predictions using both baseline and ProEthica methods
4. Reviewers evaluate predictions based on various metrics
5. Results are aggregated and analyzed

### Evaluation Metrics

- Reasoning Quality (0-10 scale)
- Persuasiveness (0-10 scale)
- Coherence (0-10 scale)
- Accuracy (match with original NSPE conclusion)
- Support Quality (0-10 scale)
- Overall Preference Score

## Usage Instructions

1. Navigate to the experiment dashboard at `/experiment/`
2. Create a new experiment with a name and description
3. Select cases to include in the experiment
4. Run the experiment to generate predictions
5. View results and conduct evaluations
