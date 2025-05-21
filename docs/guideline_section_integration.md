# Guideline Section Integration

This document describes the integration of ethical guidelines with document sections in the ProEthica application. This feature connects document sections with relevant ethical principles and guidelines, enabling more advanced semantic analysis and reasoning.

## Overview

The Guideline Section integration extends the document structure enhancements by associating ethical guidelines, principles, and rules with specific document sections. This capability enables:

1. **Contextual ethical analysis**: Identifying which ethical guidelines apply to specific parts of a case
2. **Cross-document ethical pattern detection**: Finding cases that share ethical concerns across sections
3. **Improved teaching and learning**: Highlighting specific ethical considerations in different case components
4. **Semantic reasoning**: Supporting advanced queries like "Find cases discussing competence issues in their conclusions"

## Technical Implementation

### Core Components

1. **GuidelineSectionService**: Service class that manages the association of guidelines with document sections. Located in `app/services/guideline_section_service.py`.

2. **Document Structure UI**: Enhanced to display guideline associations and allow generating them. Located in `app/templates/document_structure.html`.

3. **Document Structure Routes**: Extended to include routes for guideline association operations. Located in `app/routes/document_structure.py`.

### Data Model

The guideline associations are stored in two locations:

1. **DocumentSection.section_metadata**: JSON field that stores the guideline information directly with the section record, including:
   - guideline URI
   - relationship type (applies_to, references, contradicts, etc.)
   - confidence score
   - extraction timestamp

2. **Document.doc_metadata**: Contains summary information about guideline associations in the document_structure.guideline_associations object:
   - count (total number of associations)
   - sections_processed (number of sections with associations)
   - updated_at (timestamp of the last update)

### API Endpoints

The integration adds the following route:

- **POST /structure/associate_guidelines/<int:id>**: Generates guideline associations for a document's sections

### Process Flow

1. User navigates to the document structure view for a case
2. If the case doesn't have guideline associations, a "Generate Guideline Associations" button is displayed
3. When clicked, the system:
   - Retrieves all document sections from the DocumentSection table
   - For each section, extracts relevant guidelines using the GuidelineExtractionClient
   - Stores the guideline associations in the section metadata
   - Updates the document metadata with summary information
   - Displays the results on the document structure page

### Guideline Association Algorithm

The guideline association process uses the following algorithm:

1. Retrieve the document section text
2. Extract guidelines from the text using the GuidelineExtractionClient
3. For each guideline:
   - Determine the relationship type based on the section content and guideline text
   - Calculate a confidence score for the association
   - Store the association in the section metadata

## User Interface

The document structure view has been enhanced with a new "Ethical Guideline Associations" card that displays:

1. Status indicator (available/not available)
2. For each section with guidelines:
   - Section ID
   - Table of associated guidelines with relationship type and confidence score
3. Button to generate associations if none exist

## Future Enhancements

1. **Advanced Search**: Add ability to search for cases based on guideline associations
2. **Visualization**: Create visual representation of guideline relationships across case sections
3. **Guideline Network**: Build network view of how guidelines relate across multiple cases
4. **API Extensions**: Add REST endpoints for programmatic access to guideline associations
5. **Batch Processing**: Create tools to update guideline associations for all cases in the system

## Testing

The test script `test_guideline_section_service.py` demonstrates how to use the GuidelineSectionService to:

1. Associate guidelines with document sections
2. Retrieve guidelines for a specific section
3. Get all guideline associations for a document

## Implementation Example

Here's an example of how to use the GuidelineSectionService in code:

```python
# Create the service
guideline_service = GuidelineSectionService()

# Associate guidelines with sections
result = guideline_service.associate_guidelines_with_sections(document_id)

# Get guidelines for all sections in a document
document_result = guideline_service.get_document_section_guidelines(document_id)

# Search for sections by guideline
search_result = guideline_service.search_guideline_associations(
    guideline_uri="http://example.org/guidelines/competence",
    confidence_threshold=0.7
)
