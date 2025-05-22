# Triple Toolkit

A collection of command-line utilities for querying, analyzing, and managing RDF triples in the ProEthica database.

## Overview

The Triple Toolkit provides a set of utilities for working with the RDF triples that form the semantic knowledge base of the ProEthica system. These tools help with:

- Listing and browsing worlds, guidelines, and concepts
- Finding orphaned or invalid triples
- Analyzing relationships between triples and document sections
- Exploring the semantic structure of guidelines and cases

## Components

### Core Utilities

- **Common Libraries**
  - `db_utils.py`: Database connection and context management
  - `formatting.py`: Text formatting for consistent display
  - `pagination.py`: Interactive paging for large result sets

### Command-Line Tools

- **Browsing Tools**
  - `list_worlds.py`: List all worlds in the system
  - `list_guidelines.py`: List guidelines for a specific world
  - `list_guideline_concepts.py`: List concepts associated with guidelines
  - `find_orphaned_triples.py`: Find triples without proper associations

### Runner Scripts

Each tool has a corresponding shell script that sets up the proper environment variables before running:

- `run_list_worlds.sh`: Run the list_worlds.py script
- `run_list_guidelines.sh`: Run the list_guidelines.py script
- `run_list_guideline_concepts.sh`: Run the list_guideline_concepts.py script
- `run_find_orphaned_triples.sh`: Run the find_orphaned_triples.py script

## Installation

No installation is needed. The toolkit is designed to work directly with the ProEthica codebase.

## Usage

### Setting Environment Variables

The runner scripts will automatically:
1. Look for a `.env` file in the project root
2. Use the `DATABASE_URL` environment variable if available
3. Fall back to a default database URL if needed

### Basic Usage Examples

#### List all worlds

```bash
# Simple listing
./scripts/triple_toolkit/run_list_worlds.sh

# Detailed view
./scripts/triple_toolkit/run_list_worlds.sh --detail
```

#### List guidelines in a world

```bash
# List guidelines for world ID 1
./scripts/triple_toolkit/run_list_guidelines.sh --world-id 1

# Interactive mode with details
./scripts/triple_toolkit/run_list_guidelines.sh --world-id 1 --detail --interactive
```

#### List concepts for a guideline

```bash
# List concepts for guideline ID 5
./scripts/triple_toolkit/run_list_guideline_concepts.sh --guideline-id 5

# Show detailed view with triples
./scripts/triple_toolkit/run_list_guideline_concepts.sh --guideline-id 5 --format triples
```

#### Find orphaned triples

```bash
# Find orphaned triples with basic display
./scripts/triple_toolkit/run_find_orphaned_triples.sh

# Interactive view with all entity types
./scripts/triple_toolkit/run_find_orphaned_triples.sh --interactive --check-all
```

## Advanced Usage

### Direct Module Execution

You can also run the modules directly using Python's module syntax:

```bash
# First set DATABASE_URL environment variable
export DATABASE_URL="postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"

# Then run the module
python -m scripts.triple_toolkit.list_worlds --detail
```

### Command-line Help

Each tool provides help documentation through the standard `--help` flag:

```bash
./scripts/triple_toolkit/run_list_worlds.sh --help
```

## Development

### Adding New Tools

To add a new tool to the toolkit:

1. Create a new Python file in the `scripts/triple_toolkit` directory
2. Import the common utilities as needed
3. Create a shell script wrapper following the same pattern as existing ones

### Code Style

The code follows these conventions:
- PEP 8 for Python style
- Docstrings for all functions and modules
- Command-line arguments using argparse
- Error handling with appropriate messages

## Troubleshooting

### Database Connection Issues

If you encounter database connection issues:
- Verify the DATABASE_URL is correct in your .env file
- Ensure the database server is running
- Check that you have the required permissions

### Missing Dependencies

The toolkit relies on the core ProEthica dependencies. If you encounter import errors:
- Ensure you're running from the project root directory
- Verify that all ProEthica dependencies are installed
