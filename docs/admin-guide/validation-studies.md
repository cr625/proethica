# Validation Studies

Validation studies measure inter-rater reliability for ProEthica extraction quality.

!!! warning "Documentation In Progress"
    This page documents the validation studies feature for measuring extraction quality through inter-rater reliability analysis.

## Overview

The validation studies module supports empirical assessment of extraction quality by comparing ProEthica outputs against baseline conditions and human evaluator judgments.

## Accessing Validation Studies

Navigate to **Tools** > **Validation Studies** or direct URL: `/admin/validation`

## Features

### Experiment Management

- Create validation experiments with case selections
- Configure baseline vs ProEthica conditions
- Track experiment status and completion

### Prediction Generation

- Generate predictions for selected cases
- Compare conditions (baseline, ProEthica-assisted)
- Store predictions for evaluation

### Evaluation Collection

- Collect evaluator ratings on predictions
- Support multiple evaluators per prediction
- Track evaluator progress

### Export for Analysis

- Export data for Krippendorff's alpha calculation
- CSV and JSON formats available
- Summary statistics and comparison reports

## Database Tables

| Table | Purpose |
|-------|---------|
| `experiment_runs` | Experiment metadata and status |
| `predictions` | Generated predictions by condition |
| `experiment_evaluations` | Evaluator ratings on predictions |

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/admin/validation` | GET | Dashboard view |
| `/admin/validation/export` | GET | Export evaluation data |
| `/admin/validation/summary` | GET | Comparison statistics |

## Related Pages

- [Administration Guide](index.md) - Admin overview
- [Pipeline Management](pipeline-management.md) - Batch processing
