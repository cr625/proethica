# ProEthica Ontology System

This document provides a comprehensive guide to the ProEthica ontology system, including architecture, visualization, and implementation details.

## Overview

ProEthica uses a sophisticated ontology system to model ethical concepts and support decision-making across professional domains. The system is built on the Basic Formal Ontology (BFO) and uses the 8 GuidelineConceptTypes for structured ethical reasoning.

## Architecture

### Core Components

1. **Database Storage**: PostgreSQL-based storage for all ontologies and versions
2. **Ontology Editor**: TTL-based editor with visualization capabilities
3. **Entity Editor**: Card-based interface for managing specific entities
4. **MCP Server Integration**: Makes ontologies accessible to LLMs via Model Context Protocol
5. **Ontology Entity Service**: Extracts entities from ontologies for application use

### Ontology Structure

The ProEthica ontology system consists of three main ontology files:

#### 1. proethica-intermediate.ttl
- **Purpose**: Domain-general ethical modeling concepts
- **Contents**: 8 GuidelineConceptTypes (Role, Principle, Obligation, State, Resource, Action, Event, Capability)
- **Level**: Intermediate layer between BFO and domain-specific ontologies

#### 2. engineering-ethics.ttl  
- **Purpose**: Engineering-specific ethical concepts
- **Contents**: Engineering roles, principles, and scenarios
- **Level**: Domain-specific specializations of intermediate concepts

#### 3. bfo.ttl
- **Purpose**: Basic Formal Ontology foundation
- **Contents**: Upper-level ontological categories
- **Level**: Foundational ontology layer

## GuidelineConceptTypes

The system uses 8 core entity types for guideline concept extraction:

| Type | Description | Examples |
|------|-------------|----------|
| **Role** | Socially recognized statuses with responsibilities | Engineer, Manager, Client |
| **Principle** | Fundamental ethical values | Honesty, Integrity, Safety |
| **Obligation** | Professional duties that must be fulfilled | Public Safety, Confidentiality |
| **State** | Conditions providing ethical context | Safety Hazard, Conflict of Interest |
| **Resource** | Physical or informational entities | Technical Specifications, Reports |
| **Action** | Intentional activities by agents | Report Safety Concern, Review Design |
| **Event** | Occurrences in ethical scenarios | Project Milestone, Safety Incident |
| **Capability** | Skills or competencies | Technical Design, Risk Assessment |

## Visualization System

### Features

The ontology visualization provides:

1. **Hierarchy Visualization**: Tree structure based on rdfs:subClassOf relationships
2. **Interactive Navigation**: Expand/collapse nodes to explore hierarchy
3. **Entity Details**: View URI, description, and properties of selected entities
4. **Filtering**: Filter by GuidelineConceptType or search terms
5. **Dual View Modes**: 
   - Hierarchical view (inheritance structure)
   - Categorized view (by GuidelineConceptType)
6. **Color Coding**: Different colors for each entity type

### Access

To visualize an ontology:
1. Open the ontology editor at `/ontology-editor/`
2. Click the "Visualize" button
3. Use controls to filter and navigate the hierarchy

### Technical Implementation

- **Frontend**: D3.js for interactive tree visualization
- **Backend**: Flask API endpoint at `/api/hierarchy/<ontology_id>`
- **Parsing**: Regex-based TTL parsing for hierarchy extraction
- **Styling**: CSS color coding for entity types

## MCP Server Integration

The system includes an MCP (Model Context Protocol) server that provides:

- **Ontology Access**: Load ontologies from database with file fallback
- **Guideline Analysis**: Extract concepts and generate RDF triples
- **Entity Matching**: Match guideline concepts to ontology entities
- **LLM Integration**: Claude/OpenAI integration with mock fallback

### Production Deployment

- **URL**: https://mcp.proethica.org
- **Port**: 5002 (production), 5001 (development)
- **Branch**: `guidelines-enhancement`

## Database Schema

### Key Tables

1. **Ontology**: Main ontology metadata and TTL content
2. **OntologyVersion**: Version history and audit trail
3. **OntologyImport**: Import relationships between ontologies
4. **World**: Domains that use specific ontologies
5. **Entity**: Extracted entities from ontologies

### Entity Extraction

The `OntologyEntityService` extracts entities from TTL content and provides:
- Hierarchical organization by GuidelineConceptType
- Parent-child relationships
- Capability associations for roles
- Editability metadata

## File Structure

```
docs/ontology/
├── README.md                           # This comprehensive guide
├── ontology_visualization.md           # Visualization system details  
├── engineering_ethics_ontology_audit.md # Engineering ontology audit results
└── unified_ontology_system.md         # System architecture details

ontologies/
├── proethica-intermediate.ttl          # Intermediate ontology
├── engineering-ethics.ttl              # Engineering-specific ontology
└── bfo.ttl                            # Basic Formal Ontology

ontology_editor/
├── templates/visualize.html            # Visualization interface
├── static/js/hierarchy.js              # D3.js visualization logic
├── api/routes.py                       # API endpoints
└── services/                           # Supporting services
```

## Development Guidelines

### Adding New Concepts

1. **Domain-General Concepts**: Add to `proethica-intermediate.ttl`
2. **Engineering-Specific Concepts**: Add to `engineering-ethics.ttl`
3. **Follow Naming Conventions**: Use CamelCase with appropriate suffixes
4. **Include Metadata**: Add rdfs:label, rdfs:comment, and proper inheritance

### Ontology Validation

- Use the built-in validator in the ontology editor
- Ensure proper BFO alignment
- Validate TTL syntax before committing changes
- Test visualization after updates

### MCP Server Updates

- Test changes with local MCP server first
- Deploy to production using provided scripts
- Verify LLM integration works correctly
- Update documentation for new capabilities

## Future Enhancements

### Planned Features

1. **Advanced Visualization**: Radial layouts, property relationships
2. **Interactive Editing**: Direct ontology editing from visualization
3. **Export Options**: SVG, PNG export capabilities
4. **Performance Optimization**: Better handling of large ontologies
5. **Enhanced Filtering**: More sophisticated search and filter options

### Research Directions

1. **Temporal Modeling**: Enhanced temporal relationship handling
2. **Multi-Domain Integration**: Support for additional professional domains
3. **Automated Classification**: ML-based entity type classification
4. **Semantic Similarity**: Advanced concept matching algorithms

## Troubleshooting

### Common Issues

1. **Visualization Not Loading**: Check hierarchy API endpoint
2. **Empty Hierarchy**: Verify TTL syntax and content
3. **Missing Entities**: Check entity extraction service
4. **MCP Connection Issues**: Verify server status and authentication

### Debugging Tips

- Use browser developer tools for JavaScript errors
- Check Flask logs for API issues
- Validate TTL content with external tools
- Test with simple ontologies first

## References

- [Basic Formal Ontology (BFO)](http://basic-formal-ontology.org/)
- [Turtle (TTL) Specification](https://www.w3.org/TR/turtle/)
- [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol)
- [D3.js Documentation](https://d3js.org/)