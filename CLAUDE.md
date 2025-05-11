# AI Ethical Decision Making System Enhancement Log

## May 11, 2025 - Case Detail View & Ontology RDF Property Enhancements

### Fixed Show More/Less Toggle for Case Descriptions

* Created standalone `app/static/js/case_detail.js` file for improved code organization
* Fixed JavaScript error: `Uncaught TypeError: Cannot read properties of null (reading 'addEventListener')`
* Added robust null checks for all DOM element interactions
* Implemented better show more/less toggle functionality for case descriptions:
  * Properly measures content height vs container height 
  * Uses CSS transitions for smooth animation
  * Handles edge cases like empty containers

### Improved RDF Properties Display

* Created and ran `cleanup_rdf_type_triples.py` to remove generic RDF type triples (11 triples removed)
* Improved triple display by removing redundant generic type information:
  * Removed triples with: `22-rdf-syntax-ns#type: intermediate#Role`
  * These were replaced with more semantic domain-specific predicates like:
    `engineering-ethics#hasRole: engineering-ethics#EngineeringConsultantRole`
* The case detail view now shows fewer but more meaningful RDF properties

### Ontology Tagging Improvements

* Enhanced the `dual_layer_ontology_tagging.py` script to use more semantic predicates
* Made all entities reference the case directly with `Case {case_id}` as the subject
* Added domain-specific predicates that better represent ethical relationships:
  * `hasRole`, `involvesResource`, `involvesEvent`, `involvesAction`
  * `involvesEthicalIssue`, `hasEthicalVerdict`

## April 28, 2025 - Enhanced Ontology Processing

...rest of document continues...
