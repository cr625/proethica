# ProEthica Experiment Interface

This README provides information on the ProEthica experiment interface, which allows for the evaluation of engineering ethics case predictions with and without ontology support.

## Overview

The ProEthica experiment interface enables:
1. Creation and configuration of experiments
2. Selection of engineering ethics cases for analysis
3. Generation of predictions using baseline and ontology-enhanced approaches
4. Evaluation of prediction quality across multiple metrics
5. Analysis and comparison of results

## Setup Instructions

### Database Setup

The experiment interface requires database tables to be created:

```bash
# Run database migrations to create experiment tables
./direct_experiment_tables_migration.py
```

### Create Sample Experiment

You can create a sample experiment for testing:

```bash
./run_experiment_test.py --create-sample
```

### Run Test Server

Start a local test server to access the experiment interface:

```bash
./run_experiment_test.py
```

Then navigate to http://127.0.0.1:5050/experiment/ in your web browser.

## Interface Components

### Experiment Dashboard

The experiment dashboard displays all experiments and allows creation of new ones.

**URL:** `/experiment/`

### Experiment Setup

Configure the parameters for a new or existing experiment.

**URL:** `/experiment/setup?id={experiment_id}`

Parameters:
- Leave-out-conclusion: Whether to exclude conclusion sections when generating predictions
- Use ontology: Enable ontology-constrained analysis
- Evaluation metrics: Select metrics to use for evaluation

### Case Selection

Select engineering ethics cases to include in the experiment.

**URL:** `/experiment/cases?id={experiment_id}`

### Run Experiment

Execute the experiment to generate predictions for the selected cases.

**URL:** `/experiment/run?id={experiment_id}`

### Results Overview

View aggregated results across all cases in the experiment.

**URL:** `/experiment/results?id={experiment_id}`

### Case Results

View and evaluate predictions for a specific case.

**URL:** `/experiment/case_results?id={experiment_id}&case_id={case_id}`

## Evaluation Metrics

The experiment interface includes the following evaluation metrics:

1. **Reasoning Quality** (0-10 scale)
   - Are the steps in the discussion analysis reasonable and logical?

2. **Persuasiveness** (0-10 scale)
   - Subjective assessment of which approach is more persuasive

3. **Coherence** (0-10 scale)
   - Does the reasoning follow a clear, logical progression?

4. **Accuracy**
   - Does the predicted conclusion match the original NSPE conclusion?

5. **Support Quality** (0-10 scale)
   - Quality of justification and evidence provided

6. **Overall Preference Score** (0-10 scale)
   - Participant preference for one approach over another

## API Reference

The experiment interface provides the following API endpoints:

- `GET /experiment/api/experiments` - List all experiments
- `GET /experiment/api/experiments/{id}` - Get experiment details
- `POST /experiment/api/experiments` - Create a new experiment
- `PUT /experiment/api/experiments/{id}` - Update an experiment
- `GET /experiment/api/predictions/{id}` - Get prediction details
- `POST /experiment/api/evaluations` - Submit evaluation for a prediction

## Implementation Details

For more detailed information about the implementation, refer to [proethica_experiment_implementation_plan.md](docs/proethica_experiment_implementation_plan.md).
