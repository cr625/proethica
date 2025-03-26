# Utilities for AI Ethical Decision-Making Simulator

This directory contains utility scripts for managing case studies and other resources in the AI Ethical Decision-Making Simulator.

## Scripts

### 1. `scrape_nspe_cases.py`

This script scrapes engineering ethics case studies from the National Society of Professional Engineers (NSPE) Board of Ethical Review Cases website and saves them to a JSON file.

**Usage:**
```bash
python utilities/scrape_nspe_cases.py [--output OUTPUT_FILE] [--limit MAX_CASES]
```

**Arguments:**
- `--output`, `-o`: Output JSON file (default: `data/nspe_cases.json`)
- `--limit`, `-l`: Maximum number of cases to scrape (default: all)

**Example:**
```bash
# Scrape all cases
python utilities/scrape_nspe_cases.py

# Scrape 5 cases and save to a custom file
python utilities/scrape_nspe_cases.py --limit 5 --output data/sample_cases.json
```

### 2. `add_cases_to_world.py`

This script adds the scraped case studies to a specific world in the database and processes them with the embedding service.

**Usage:**
```bash
python utilities/add_cases_to_world.py --world-id WORLD_ID [--input INPUT_FILE] [--document-type DOC_TYPE] [--no-embeddings] [--url URL] [--title TITLE]
```

**Arguments:**
- `--world-id`, `-w`: ID of the world to add cases to (required)
- `--input`, `-i`: Input JSON file with case studies (default: `data/nspe_cases.json`)
- `--document-type`, `-t`: Type of document to create (default: `case_study`)
- `--no-embeddings`, `-n`: Do not process embeddings for the documents
- `--url`, `-u`: Process a single URL directly instead of loading from file
- `--title`: Title for the document when processing a single URL

**Example:**
```bash
# Add all cases from the default JSON file to world with ID 2
python utilities/add_cases_to_world.py --world-id 2

# Add cases from a custom file without processing embeddings
python utilities/add_cases_to_world.py --world-id 2 --input data/sample_cases.json --no-embeddings

# Process a single URL directly
python utilities/add_cases_to_world.py --world-id 2 --url https://www.nspe.org/resources/ethics/ethics-resources/board-ethical-review-cases/example-case --title "Example Case"
```

### 3. `retrieve_cases.py`

This script provides functions to retrieve case studies from the database based on various criteria, such as world ID, similarity to a query, etc.

**Usage:**
```bash
python utilities/retrieve_cases.py [--world-id WORLD_ID] [--query QUERY] [--document-id DOC_ID] [--year YEAR] [--limit LIMIT] [--output OUTPUT_FILE]
```

**Arguments:**
- `--world-id`, `-w`: ID of the world to get cases for
- `--query`, `-q`: Query string to search for similar cases
- `--document-id`, `-d`: ID of a specific document to retrieve
- `--year`, `-y`: Year to filter cases by
- `--limit`, `-l`: Maximum number of results to return (default: 10)
- `--output`, `-o`: Output file to save results to (JSON format)

**Example:**
```bash
# Get all cases for world with ID 2
python utilities/retrieve_cases.py --world-id 2

# Search for cases similar to a query
python utilities/retrieve_cases.py --query "conflict of interest" --world-id 2

# Get a specific case by ID
python utilities/retrieve_cases.py --document-id 123

# Get cases from a specific year
python utilities/retrieve_cases.py --year 2020 --world-id 2

# Save results to a file
python utilities/retrieve_cases.py --world-id 2 --output results.json
```

### 4. `process_nspe_url.py`

This script combines the functionality of `scrape_nspe_cases.py` and `add_cases_to_world.py` to directly process a specific URL from the NSPE website and add it to the database.

**Usage:**
```bash
python utilities/process_nspe_url.py --url URL --world-id WORLD_ID [--document-type DOC_TYPE] [--no-embeddings]
```

**Arguments:**
- `--url`, `-u`: URL of the NSPE case study (required)
- `--world-id`, `-w`: ID of the world to add the case to (required)
- `--document-type`, `-t`: Type of document to create (default: `case_study`)
- `--no-embeddings`, `-n`: Do not process embeddings for the document

**Example:**
```bash
# Process a specific NSPE case study URL and add it to world with ID 2
python utilities/process_nspe_url.py --url https://www.nspe.org/resources/ethics/ethics-resources/board-ethical-review-cases/example-case --world-id 2
```

## Workflow Example

Here's an example workflow for adding NSPE case studies to the database:

1. **Scrape cases from the NSPE website:**
   ```bash
   python utilities/scrape_nspe_cases.py --limit 10
   ```

2. **Add the scraped cases to a world:**
   ```bash
   python utilities/add_cases_to_world.py --world-id 2
   ```

3. **Retrieve cases for verification:**
   ```bash
   python utilities/retrieve_cases.py --world-id 2
   ```

4. **Process a specific case directly:**
   ```bash
   python utilities/process_nspe_url.py --url https://www.nspe.org/resources/ethics/ethics-resources/board-ethical-review-cases/example-case --world-id 2
   ```

### 5. `test_process_case.py`

This script demonstrates how to process a specific NSPE case study URL and add it to the Engineering Ethics (US) world (world_id=2). It includes a few example cases to choose from.

**Usage:**
```bash
python utilities/test_process_case.py [--world-id WORLD_ID] [--case-index CASE_INDEX] [--no-embeddings]
```

**Arguments:**
- `--world-id`, `-w`: ID of the world to add the case to (default: 2 for Engineering Ethics (US) world)
- `--case-index`, `-c`: Index of the case to process (0-2, default: 0)
- `--no-embeddings`, `-n`: Do not process embeddings for the document

**Example:**
```bash
# Process the first example case
python utilities/test_process_case.py

# Process the second example case
python utilities/test_process_case.py --case-index 1

# Process a case for a different world
python utilities/test_process_case.py --world-id 3 --case-index 2
```

### 6. `cases_agent_demo.py`

This script demonstrates how the CasesAgent would work in the agent-based system. It retrieves relevant case studies based on a decision context and analyzes them to provide insights for decision-making.

**Usage:**
```bash
python utilities/cases_agent_demo.py [--world-id WORLD_ID] [--decision DECISION_TEXT] [--output OUTPUT_FILE]
```

**Arguments:**
- `--world-id`, `-w`: ID of the world to get cases for (default: 2 for Engineering Ethics (US) world)
- `--decision`, `-d`: Decision text (default: example decision)
- `--output`, `-o`: Output file to save results to (JSON format)

**Example:**
```bash
# Run with the default example decision
python utilities/cases_agent_demo.py

# Run with a custom decision
python utilities/cases_agent_demo.py --decision "Should the engineer accept a gift from a vendor?"

# Save the results to a file
python utilities/cases_agent_demo.py --output analysis_results.json
```

### 7. `demo_workflow.sh`

This script demonstrates the complete workflow of adding case studies to the database and using them in the agent-based system. It runs through the following steps:

1. Process three example case studies from the NSPE website
2. Retrieve the cases to verify they were added
3. Use the CasesAgent demo to analyze two different decisions

**Usage:**
```bash
./utilities/demo_workflow.sh
```

**Example:**
```bash
# Run the complete demo workflow
./utilities/demo_workflow.sh
```

## Integration with Agent-Based System

These utilities provide the foundation for the agent-based system to access relevant case studies when evaluating decisions in simulations. The `retrieve_cases.py` script, in particular, can be used by the CasesAgent to retrieve relevant cases based on the decision context.

The `cases_agent_demo.py` script demonstrates how the CasesAgent would work in the agent-based system. It shows how to:

1. Retrieve relevant case studies based on a decision context
2. Analyze the cases to provide insights for decision-making
3. Generate recommendations for each decision option based on similar cases

This demo serves as a starting point for implementing the full CasesAgent in the agent-based architecture outlined in the `prompts/agent_based_simulation_plan.md` file.

## Getting Started

To get started with these utilities, follow these steps:

1. Make sure you have all the required dependencies installed:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the demo workflow to see the complete process in action:
   ```bash
   ./utilities/demo_workflow.sh
   ```

3. Explore the individual scripts to understand how they work:
   ```bash
   python utilities/scrape_nspe_cases.py --limit 5
   python utilities/add_cases_to_world.py --world-id 2 --input data/nspe_cases.json
   python utilities/retrieve_cases.py --world-id 2
   python utilities/cases_agent_demo.py
   ```

4. Use these utilities as a foundation for implementing the full agent-based architecture outlined in the `prompts/agent_based_simulation_plan.md` file.
