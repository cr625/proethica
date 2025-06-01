# Ontology Visualization

This document describes the ontology visualization feature implementation in the ProEthica system.

## Overview

The ontology visualization feature provides a graphical view of ontology hierarchies, making it easier to understand the structure and relationships between ontology classes. The visualization is implemented using D3.js to create an interactive tree diagram that displays the taxonomy and hierarchy of BFO-aligned ontologies.

## Architecture

The visualization feature consists of several components:

1. **Backend API**: Server-side code that extracts a hierarchical structure from the TTL content of an ontology
2. **Visualization Template**: HTML template for the visualization page  
3. **JavaScript Code**: Client-side code that renders the hierarchy using D3.js
4. **CSS Styling**: Styling for the visualization elements

## Implementation Details

### Backend Components

The backend implementation includes:

- A Flask route in `ontology_editor/__init__.py` to handle the `/visualize/<ontology_id>` endpoint
- An API endpoint in `ontology_editor/api/routes.py` at `/api/hierarchy/<int:ontology_id>` that parses TTL content into a hierarchical structure
- RDFLib integration for parsing TTL and extracting class hierarchies from proethica-intermediate.ttl and engineering-ethics.ttl

### Frontend Components

The frontend implementation includes:

- The `hierarchy.js` file that handles the visualization using D3.js
- The `hierarchy.css` file that styles the visualization elements
- The `visualize.html` template that displays the visualization

### Key Features

1. **Hierarchy Visualization**: Display classes in a hierarchical tree structure based on rdfs:subClassOf relationships
2. **Interactive Navigation**: Expand/collapse nodes to explore the hierarchy
3. **Entity Details**: View details of selected entities including URI, description, and properties
4. **Filtering**: Filter the visualization by GuidelineConceptType (Role, Principle, Obligation, State, Resource, Action, Event, Capability)
5. **BFO Integration**: Special handling for BFO classes and ProEthica intermediate ontology classes
6. **Color Coding**: Different entity types are color-coded for easy identification
7. **Dual View Modes**: Hierarchical view (inheritance structure) and Categorized view (by GuidelineConceptType)

## Usage

To visualize an ontology:

1. Open an ontology in the editor
2. Click the "Visualize" button
3. Interact with the visualization using:
   - Expand/collapse buttons for individual nodes
   - Expand All/Collapse All buttons for the entire hierarchy
   - Filters to show/hide specific parts of the hierarchy
   - Click on nodes to view entity details

## Technical Notes

- The visualization uses the `rdfs:subClassOf` relationship to determine the class hierarchy
- BFO classes are identified by the URI prefix "http://purl.obolibrary.org/obo/BFO_"
- BFO-aligned classes are identified by their relationship to BFO classes
- The D3.js library is used for rendering the tree visualization

## Testing

A test script is provided in `scripts/test_ontology_visualization.py` to verify the functionality of the hierarchy API endpoint. The script can be run with:

```bash
./scripts/test_ontology_visualization.py <ontology_id>
```

## Future Enhancements

Possible improvements to the visualization feature:

1. **Radial/Force Layout**: Alternative visualization layouts beyond the tree view
2. **Property Visualization**: Visualize properties and their relationships
3. **Export Options**: Export the visualization as SVG, PNG, etc.
4. **Interactive Editing**: Allow editing the ontology directly from the visualization
5. **Advanced Filtering**: More advanced filtering options for complex ontologies
6. **Performance Optimization**: Improve performance for large ontologies
