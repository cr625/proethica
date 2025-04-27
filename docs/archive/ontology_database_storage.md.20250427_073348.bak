# Unified Ontology System Storage

This document describes the new unified ontology system storage architecture that allows for proper integration between domain-specific ontologies and base ontologies.

## Overview

The unified ontology system solves several key challenges:

1. **Consistent Entity Types**: Ensures all domain ontologies properly reference the same core entity types (Role, Event, etc.)
2. **Hierarchy Visualization**: Properly shows domain-specific classes within their type categories
3. **Single Source of Truth**: Uses the database as the single source of truth for all ontologies
4. **Base Ontology Protection**: Prevents accidental modification of core ontologies (BFO, Intermediate)
5. **Explicit Import Relationships**: Tracks which ontologies import/extend others

## Database Storage Model

The system now uses a more sophisticated database storage model:

### Core Models:

1. **Ontology**:
   - Stores basic ontology information and content
   - Added fields: `is_base`, `is_editable`, and `base_uri`
   - See `app/models/ontology.py`

2. **OntologyVersion**:
   - Tracks version history for ontologies
   - Each version maintains a complete copy of the ontology content at that point in time
   - See `app/models/ontology_version.py`

3. **OntologyImport** (New):
   - Tracks import relationships between ontologies
   - Allows building dependency graphs between ontologies
   - See `app/models/ontology_import.py`

## Base Ontologies

The system now recognizes two types of base ontologies:

1. **BFO (Basic Formal Ontology)**:
   - Provides the foundational classes for all ontologies
   - Imported into the intermediate ontology
   - Marked as non-editable in the database

2. **ProEthica Intermediate Ontology**:
   - Defines core entity types used across all domain ontologies
   - Extends BFO with ethical-specific concepts
   - Defines `Role`, `Condition`, `Resource`, `Event`, and `Action` classes
   - Marked as non-editable in the database

## Import Relationships

Domain ontologies now explicitly import base ontologies in the database:

1. **Direct Imports**:
   - Explicitly defined with `owl:imports` statements in the TTL
   - Stored in the database using the `OntologyImport` model

2. **Implicit Imports**:
   - Detected from prefix declarations and namespace usage
   - Added automatically during import processing
   - Example: Using `proeth:Role` implies importing the intermediate ontology

3. **Default Imports**:
   - When no imports are detected, the intermediate ontology is added by default
   - Ensures all domain ontologies have access to core types

## Hierarchy Visualization

The visualization of ontology hierarchies has been enhanced to:

1. Load and include imported ontologies when building the hierarchy
2. Recognize and categorize entities by their type (Role, Event, etc.)
3. Support two viewing modes:
   - Hierarchical: Shows the inheritance tree based on `rdfs:subClassOf`
   - Categorized: Groups entities by their type category

## Setup and Migration

To set up the unified ontology system:

1. Create necessary database tables:
   ```bash
   python scripts/create_ontology_import_table.py
   ```

2. Import base ontologies:
   ```bash
   python scripts/import_base_ontologies.py
   ```

3. Process domain ontology imports:
   ```bash
   python scripts/process_domain_ontology_imports.py
   ```

Or run the unified setup script:
```bash
scripts/setup_unified_ontology_system.sh
```

## Editing Restrictions

- Base ontologies (`is_base=True`) are marked as non-editable (`is_editable=False`)
- The ontology editor UI shows a warning for non-editable ontologies
- Domain ontologies remain fully editable
