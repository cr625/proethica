# NSPE Engineering Ethics Case Import

This directory contains scripts for importing cases from the NSPE Board of Ethical Review into the ProEthica system. These scripts allow you to fetch, process, and store engineering ethics cases from NSPE as semantic triples in the ProEthica database.

## Overview

The implementation follows a multi-step pipeline:

1. **Case Collection**: Fetches engineering ethics cases from the NSPE Board of Ethical Review.
2. **Ontology Extension**: Extends the engineering ethics ontology with additional concepts needed for NSPE cases.
3. **Triple Generation**: Converts case data into RDF triples that represent the ethical principles, decisions, and relationships.
4. **Database Storage**: Imports the generated triples as documents associated with worlds, not scenarios.

## Correctly Associating Cases with Worlds

This implementation properly associates cases with worlds, not with scenarios. NSPE cases are stored as Document objects with `document_type='case_study'` and are added to the world's `cases` array.

## Scripts

### 1. `create_nspe_ethics_cases.py`

This script fetches and processes NSPE cases, converting them into RDF triples and storing them as JSON files.

```bash
# Export cases to JSON files
python create_nspe_ethics_cases.py --export-only

# Export cases with a custom limit
python create_nspe_ethics_cases.py --export-only --max-cases 10

# Export to a custom directory
python create_nspe_ethics_cases.py --export-only --export-dir data/custom_directory
```

### 2. `extend_engineering_ethics_ontology.py`

This script extends the engineering ethics ontology with additional concepts found in NSPE cases.

```bash
# Default usage
python extend_engineering_ethics_ontology.py

# Custom file paths
python extend_engineering_ethics_ontology.py path/to/base/ontology.ttl path/to/cases.json path/to/output/ontology.ttl
```

### 3. `cleanup_nspe_scenarios.py`

This script removes any incorrectly created NSPE scenarios from a previous implementation.

```bash
# Remove the incorrectly created scenarios
python cleanup_nspe_scenarios.py
```

### 4. `import_nspe_cases_to_world.py`

This script imports NSPE cases as document-based cases associated with worlds.

```bash
# Default usage (runs cleanup first, then imports cases)
python import_nspe_cases_to_world.py

# Skip running the cleanup script
python import_nspe_cases_to_world.py --skip-cleanup

# Custom directory
python import_nspe_cases_to_world.py --dir data/custom_case_triples

# Custom world ID
python import_nspe_cases_to_world.py --world-id 2
```

### 5. `list_nspe_world_cases.py`

This script lists all NSPE ethics cases that have been correctly imported as world cases.

```bash
# List all NSPE cases associated with worlds
python list_nspe_world_cases.py
```

## Case Structure

Each imported case includes:

- **Basic Information**: Title, description, case number, and source URL
- **Ethical Principles**: Key ethical principles involved in the case
- **BER Decision**: The NSPE Board of Ethical Review's decision and reasoning
- **Related Cases**: Links to related cases for cross-referencing
- **Semantic Triples**: RDF triples representing the case's ethical relationships

## Implementation Details

### Document & World Association

Cases are stored with the following structure:
- NSPE cases are stored as `Document` objects with `document_type='case_study'`
- Cases are associated with worlds by adding their document IDs to the world's `cases` array
- Entity triples are associated with documents, not scenarios

### Triple Structure

Cases are stored as RDF triples in the following structure:

- **Subject**: The case, principle, or entity (e.g., engineer, client)
- **Predicate**: The relationship (e.g., involves, hasDecision, references)
- **Object**: The target of the relationship, which can be another entity or a literal value
- **Graph**: Named graph format `world:{world_id}/document:{document_id}`

### Ontology Integration

The imported cases use concepts from:

- **BFO (Basic Formal Ontology)**: The foundational upper-level ontology
- **ProEthica Intermediate Ontology**: The middle-level ontology for ethical reasoning
- **Engineering Ethics Ontology**: Domain-specific ethical concepts for engineering

## Adding More Cases

To add more cases:

1. Add case data to `data/modern_nspe_cases.json`
2. Run `extend_engineering_ethics_ontology.py` to update the ontology if needed
3. Run `create_nspe_ethics_cases.py --export-only` to export case triples to JSON
4. Run `import_nspe_cases_to_world.py` to import the cases as world-associated documents

## Current Status

After running the import scripts, the system should contain the following NSPE cases as world cases:

- **Case 22-5**: "Duty to Report Unsafe Conditions"
- **Case 23-4**: "Acknowledging Errors in Design"
- **Case 22-10**: "Serving as Both Engineer and Building Official"

Each case includes all relevant ethical principles, cited codes, and the board's analysis of the ethical dilemma.
