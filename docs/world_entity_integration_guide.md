# World Entity Integration Guide

This guide explains how to use the new world entity integration feature that connects cases with world ontologies.

## Overview

The world entity integration feature automatically:

1. Extracts entities (roles, conditions, resources, actions, events, capabilities) from case semantic triples
2. Checks if these entities already exist in the associated world
3. Adds new entities to the world's ontology if they don't exist
4. Creates semantic links between cases and the world entities

This creates a bi-directional relationship between cases and worlds, making both more semantically rich.

## Implementation Components

The implementation consists of:

- `nspe-pipeline/utils/world_entity_integration.py`: Core integration module
- `nspe-pipeline/process_nspe_case.py`: Updated processing pipeline with integration support
- `process_example_case.sh`: Demo script to showcase the functionality

## How to Test the Integration

### Prerequisites

1. Make sure the application is running
2. Ensure you have at least one world created in the system (note its ID)

### Testing Process

#### Step 1: Observe the world before integration

1. Visit `http://localhost:5000/worlds/{world_id}` (replace `{world_id}` with an actual world ID)
2. Note the current entities in each tab (roles, conditions, resources, etc.)
3. Take a screenshot or make notes of the existing entities for comparison

#### Step 2: Process a case with world integration

Run the provided demo script:

```bash
# Make the script executable
chmod +x process_example_case.sh

# Run with a specific world ID (replace 1 with your world ID)
./process_example_case.sh 1
```

This will:
- Process the "Acknowledging Errors in Design" case from NSPE
- Extract entities from the case
- Add new entities to the specified world
- Create semantic links between the case and the world

#### Step 3: Observe the integration results

1. Check the terminal output to see:
   - Which entities were extracted from the case
   - Which entities were added to the world
   - The total count of integrated entities

2. Visit `http://localhost:5000/worlds/{world_id}` again to see:
   - New entities added to the world in their respective tabs
   - Compare with your notes/screenshot from Step 1

3. Visit the case page (URL will be shown in terminal output) to see:
   - Case detail with the "Show More" button now working correctly
   - RDF Properties section showing relationships with world entities

## Integration In Depth

### Entity Types Extracted

The integration process extracts and processes these entity types:

| Entity Type | Predicate Pattern | World Tab |
|-------------|------------------|-----------|
| Roles | `hasRole` | Roles |
| Conditions | `involvesCondition` | Conditions |
| Resources | `involvesResource` | Resources |
| Actions | `involvesAction` | Actions |
| Events | `involvesEvent` | Events |
| Capabilities | `hasCapability` | Capabilities |

### Example Entities from "Acknowledging Errors in Design" Case

The case likely contains entities such as:

- **Roles**: Engineer, Design Professional, Client
- **Resources**: Design Documents, Building Plans
- **Actions**: Acknowledging Errors, Design Review
- **Conditions**: Professional Responsibility, Legal Liability

### Command-line Options

The processing pipeline now supports these options:

```bash
python process_nspe_case.py <case_url> [options]

Options:
  --integrate-with-world    Enable world entity integration
  --world-id=ID             Specify world ID to integrate with
  --keep-existing           Keep existing triples instead of clearing them
```

## Troubleshooting

If integration doesn't seem to work:

1. Check if the case was correctly processed (terminal output should confirm)
2. Verify that the world ID exists and is correct
3. Look for error messages in the terminal output
4. Check if the case generates any semantic triples (if none, there's nothing to integrate)

## Next Steps

The world entity integration system can be extended to:

1. Update existing world entities with additional metadata from cases
2. Create more advanced semantic relationships between entities
3. Implement a user interface for manual entity mapping and confirmation
4. Develop visualization tools to show the connections between cases and world entities
