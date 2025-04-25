# Ontology Visualization System

This document provides an overview of the newly implemented ontology visualization system.

## Features

- **Interactive Hierarchy Visualization**: View the ontology structure as an interactive D3.js tree
- **Dual View Modes**: 
  - Hierarchical View: Shows the traditional inheritance structure
  - Entity Type View: Organizes entities by their type (Role, Condition, etc.)
- **Filtering Capabilities**: Filter by entity type to focus on specific aspects
- **Interactive Controls**:
  - Zoom level adjustment
  - Tree depth control
  - Expand/collapse functionality

## How to Access

The visualization is available at:
```
http://localhost:3333/ontology-editor/visualize/{ontology_id}
```

For example, to view ontology ID 1:
```
http://localhost:3333/ontology-editor/visualize/1
```

## Implementation Details

### Database Support
- Added `is_base` and `is_editable` flags to ontologies table
- Created `ontology_imports` table to track relationships between ontologies
- Added user admin roles to manage access permissions

### Visualization Components
- D3.js visualization library for interactive tree rendering
- Color coding for different entity types
- Tooltips with entity details
- Legends for easy identification

### API Endpoints
- `/ontology-editor/api/ontology/{ontology_id}/hierarchy` - Get hierarchy data for visualization
- `/ontology-editor/api/ontologies` - List all available ontologies
- `/ontology-editor/api/ontology/{ontology_id}` - Get specific ontology details

## Known Issues & Solutions

If you have trouble accessing the visualization:

1. Ensure the ProEthica server is running (`./start_proethica.sh`)
2. Verify the ontology exists in the database (check with `scripts/check_ontologies_in_db.py`)
3. Try accessing via direct URL in your browser
4. If browser integration fails, use curl to verify the endpoint is responding:
   ```
   curl http://localhost:3333/ontology-editor/visualize/1
   ```

## Next Steps for Enhancement

1. **API Route Standardization**: Align singular/plural routes in API endpoints
2. **Advanced RDF Parsing**: Enhance hierarchy extraction with full RDF parsing
3. **Interactive Editing**: Add drag-and-drop functionality for ontology modification
4. **Performance Optimization**: Add pagination and lazy-loading for large ontologies
5. **Search Functionality**: Add the ability to search for specific entities

## Technical References

- D3.js Documentation: https://d3js.org/
- Flask Blueprint Documentation: https://flask.palletsprojects.com/en/2.0.x/blueprints/
- RDFLib Documentation: https://rdflib.readthedocs.io/
