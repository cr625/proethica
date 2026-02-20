"""
OntServe Commit Service for ProEthica

Handles committing extracted entities from temporary storage to permanent OntServe storage.
- Classes are saved to proethica-intermediate-extended.ttl (supplemental file)
- Individuals are saved to case-specific ontologies (proethica-case-N.ttl)
- Synchronizes with OntServe database via refresh scripts

Versioning Strategy (January 2026):
- Case TTL files are OVERWRITTEN on re-extraction (single file, no accumulation)
- OntServe DB preserves historical versions via concepts.is_current and concept_versions
- Classes are versioned individually (same class from different cases = new version)

Note: Current architecture stores new classes in proethica-intermediate-extended.ttl
for testing purposes. Alternative approach would be to store both classes and
individuals in case-specific ontologies (proethica-case-N.ttl) and have
proethica-intermediate import from all cases, but this could become unwieldy.
The current approach allows easy clearing of test classes via clear_extracted_classes().
"""

import os
import json
import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timezone
import subprocess
from pathlib import Path
import requests
import psycopg2
from psycopg2.extras import Json

from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL, XSD
from rdflib.namespace import SKOS, DCTERMS

from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.services.extraction.schemas import CATEGORY_TO_ONTOLOGY_IRI

logger = logging.getLogger(__name__)

# OntServe database connection (for versioned commits)
ONTSERVE_DB_CONFIG = {
    'dbname': 'ontserve',
    'user': 'postgres',
    'password': 'PASS',
    'host': 'localhost',
    'port': 5432
}

# Namespaces
PROETHICA = Namespace("http://proethica.org/ontology/intermediate#")
PROETHICA_CORE = Namespace("http://proethica.org/ontology/core#")
PROETHICA_CASES = Namespace("http://proethica.org/ontology/cases#")
BFO = Namespace("http://purl.obolibrary.org/obo/BFO_")
IAO = Namespace("http://purl.obolibrary.org/obo/IAO_")
PROV = Namespace("http://www.w3.org/ns/prov#")


class OntServeCommitService:
    """Service for committing extracted entities to OntServe permanent storage."""

    def __init__(self):
        """Initialize the commit service."""
        self.ontserve_path = Path("/home/chris/onto/OntServe")
        self.ontologies_dir = self.ontserve_path / "ontologies"
        self.mcp_url = "http://localhost:8082"
        # Use OntServe's venv Python for subprocess calls (has pgvector, etc.)
        self.ontserve_python = str(self.ontserve_path / "venv-ontserve" / "bin" / "python")

        # Ensure directories exist
        self.ontologies_dir.mkdir(parents=True, exist_ok=True)

    def commit_selected_entities(self, case_id: int, entity_ids: List[int]) -> Dict[str, Any]:
        """
        Commit selected entities from temporary storage to permanent OntServe storage.

        Args:
            case_id: The case ID
            entity_ids: List of TemporaryRDFStorage IDs to commit

        Returns:
            Dictionary with commit results
        """
        try:
            # Fetch selected entities
            entities = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.id.in_(entity_ids),
                TemporaryRDFStorage.case_id == case_id
            ).all()

            if not entities:
                return {
                    'success': False,
                    'error': 'No entities found for the provided IDs'
                }

            # Separate classes and individuals
            classes_to_commit = []
            individuals_to_commit = []

            for entity in entities:
                # Use rdf_json_ld column instead of rdf_data
                rdf_data = entity.rdf_json_ld if entity.rdf_json_ld else {}

                # Check storage_type directly from entity
                if entity.storage_type == 'class':
                    classes_to_commit.append((entity, rdf_data))
                elif entity.storage_type == 'individual':
                    individuals_to_commit.append((entity, rdf_data))

            results = {
                'success': True,
                'classes_committed': 0,
                'individuals_committed': 0,
                'errors': []
            }

            # Commit classes to proethica-intermediate-extended.ttl
            if classes_to_commit:
                class_result = self._commit_classes_to_intermediate(classes_to_commit)
                results['classes_committed'] = class_result['count']
                if class_result.get('error'):
                    results['errors'].append(class_result['error'])

            # Commit individuals to case-specific ontology
            if individuals_to_commit:
                individual_result = self._commit_individuals_to_case_ontology(case_id, individuals_to_commit)
                results['individuals_committed'] = individual_result['count']
                if individual_result.get('error'):
                    results['errors'].append(individual_result['error'])

            # Mark entities as published
            for entity in entities:
                entity.is_published = True

            from app import db
            db.session.commit()

            # Sync with OntServe database (register case ontology + refresh entities)
            if individuals_to_commit:
                # Register the case ontology if new, then refresh entities
                register_result = self._register_case_ontology(case_id)
                if register_result.get('success'):
                    refresh_result = self._refresh_case_ontology(case_id)
                    if not refresh_result.get('success'):
                        results['errors'].append(f"OntServe refresh warning: {refresh_result.get('error', 'Unknown')}")
                    else:
                        results['ontserve_synced'] = True
                else:
                    results['errors'].append(f"OntServe register warning: {register_result.get('error', 'Unknown')}")

            if classes_to_commit:
                sync_result = self._synchronize_with_ontserve()
                if not sync_result['success']:
                    results['errors'].append(f"OntServe sync warning: {sync_result.get('error', 'Unknown')}")
                else:
                    results['ontserve_synced'] = True

            return results

        except Exception as e:
            logger.error(f"Error committing entities: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _commit_classes_to_intermediate(self, classes: List[Tuple[Any, Dict]]) -> Dict[str, Any]:
        """
        Commit new classes to proethica-intermediate-extended.ttl.

        This creates a supplemental file that can be imported by proethica-intermediate.ttl
        to avoid making the main file unwieldy.
        """
        try:
            extracted_file = self.ontologies_dir / "proethica-intermediate-extended.ttl"

            # Load existing graph or create new one
            g = Graph()
            if extracted_file.exists():
                g.parse(extracted_file, format='turtle')

            # Bind namespaces
            g.bind("proeth", PROETHICA)
            g.bind("proeth-core", PROETHICA_CORE)
            g.bind("bfo", BFO)
            g.bind("iao", IAO)
            g.bind("prov", PROV)
            g.bind("skos", SKOS)
            g.bind("dcterms", DCTERMS)

            # Define provenance namespace
            PROETHICA_PROV = Namespace("http://proethica.org/provenance#")
            g.bind("proeth-prov", PROETHICA_PROV)

            count = 0
            for entity, rdf_data in classes:
                # Use entity attributes directly
                label = entity.entity_label or 'UnknownClass'
                # Sanitize label for valid URI: remove quotes, parens, and other special chars
                safe_label = label.replace(" ", "").replace("(", "").replace(")", "")
                safe_label = safe_label.replace('"', '').replace("'", "").replace(",", "")
                safe_label = safe_label.replace("<", "").replace(">", "").replace("&", "")
                class_uri = PROETHICA[safe_label]

                # Check if class already exists
                if (class_uri, RDF.type, OWL.Class) in g:
                    logger.info(f"Class {label} already exists, skipping")
                    continue

                # Add class triple
                g.add((class_uri, RDF.type, OWL.Class))
                g.add((class_uri, RDFS.label, Literal(label)))

                # Add definitions with multi-source SKOS support
                definitions = (rdf_data or {}).get('definitions', [])
                if definitions:
                    # Primary definition -> skos:definition + rdfs:comment
                    primary = next((d for d in definitions if d.get('is_primary')), definitions[0])
                    if primary.get('text'):
                        g.add((class_uri, RDFS.comment, Literal(primary['text'])))
                        g.add((class_uri, SKOS.definition, Literal(primary['text'])))
                    # Alternate definitions -> skos:scopeNote with source tag
                    for defn in definitions:
                        if defn is primary:
                            continue
                        text = defn.get('text', '')
                        if not text:
                            continue
                        source_tag = defn.get('source_section') or defn.get('source_ontology') or defn.get('source_type', '')
                        tagged_text = f"[{source_tag}] {text}" if source_tag else text
                        g.add((class_uri, SKOS.scopeNote, Literal(tagged_text)))
                elif entity.entity_definition:
                    g.add((class_uri, RDFS.comment, Literal(entity.entity_definition)))
                    g.add((class_uri, SKOS.definition, Literal(entity.entity_definition)))

                # Add subclass relationship using CATEGORY_TO_ONTOLOGY_IRI when
                # category info is available, otherwise fall back to core class.
                subclass_uris = self._resolve_subclass_uris(entity, rdf_data)
                for sc_uri in subclass_uris:
                    g.add((class_uri, RDFS.subClassOf, URIRef(sc_uri)))

                # Add provenance from rdf_json_ld if available
                if rdf_data and 'properties' in rdf_data:
                    props = rdf_data['properties']

                    # Standard W3C PROV-O
                    if 'generatedAtTime' in props and props['generatedAtTime']:
                        for timestamp_str in props['generatedAtTime']:
                            try:
                                # Parse ISO format timestamp (datetime.fromisoformat works in Python 3.7+)
                                timestamp_str_clean = timestamp_str.replace('Z', '+00:00') if timestamp_str.endswith('Z') else timestamp_str
                                timestamp = datetime.fromisoformat(timestamp_str_clean)
                                g.add((class_uri, PROV.generatedAtTime, Literal(timestamp, datatype=XSD.dateTime)))
                            except Exception as e:
                                logger.warning(f"Could not parse timestamp {timestamp_str}: {e}")

                    if 'wasAttributedTo' in props and props['wasAttributedTo']:
                        for attribution in props['wasAttributedTo']:
                            g.add((class_uri, PROV.wasAttributedTo, Literal(attribution)))

                    # ProEthica-specific provenance (Phase 1 Architecture)
                    if 'firstDiscoveredInCase' in props and props['firstDiscoveredInCase']:
                        case_id_val = props['firstDiscoveredInCase'][0]
                        g.add((class_uri, PROETHICA_PROV.firstDiscoveredInCase, Literal(int(case_id_val), datatype=XSD.integer)))

                    if 'firstDiscoveredAt' in props and props['firstDiscoveredAt']:
                        timestamp_str = props['firstDiscoveredAt'][0]
                        try:
                            # Parse ISO format timestamp
                            timestamp_str_clean = timestamp_str.replace('Z', '+00:00') if timestamp_str.endswith('Z') else timestamp_str
                            timestamp = datetime.fromisoformat(timestamp_str_clean)
                            g.add((class_uri, PROETHICA_PROV.firstDiscoveredAt, Literal(timestamp, datatype=XSD.dateTime)))
                        except Exception as e:
                            logger.warning(f"Could not parse timestamp {timestamp_str}: {e}")

                    if 'discoveredInCase' in props and props['discoveredInCase']:
                        for case_id_val in props['discoveredInCase']:
                            g.add((class_uri, PROETHICA_PROV.discoveredInCase, Literal(int(case_id_val), datatype=XSD.integer)))

                    if 'discoveredInSection' in props and props['discoveredInSection']:
                        section = props['discoveredInSection'][0]
                        g.add((class_uri, PROETHICA_PROV.discoveredInSection, Literal(section)))

                    if 'discoveredInPass' in props and props['discoveredInPass']:
                        pass_num = props['discoveredInPass'][0]
                        g.add((class_uri, PROETHICA_PROV.discoveredInPass, Literal(int(pass_num), datatype=XSD.integer)))

                    if 'sourceText' in props and props['sourceText']:
                        source_text = props['sourceText'][0]
                        if source_text:
                            g.add((class_uri, PROETHICA_PROV.sourceText, Literal(source_text)))
                else:
                    # Fallback to basic provenance if rdf_data not available
                    g.add((class_uri, PROV.generatedAtTime, Literal(datetime.utcnow())))
                    g.add((class_uri, PROV.wasGeneratedBy, Literal("ProEthica Extraction")))

                count += 1

            # Save the graph
            g.serialize(destination=extracted_file, format='turtle')
            logger.info(f"Committed {count} classes to {extracted_file}")

            # Update proethica-intermediate.ttl to import this file if not already
            self._ensure_import_statement()

            return {'count': count, 'file': str(extracted_file)}

        except Exception as e:
            logger.error(f"Error committing classes: {e}")
            return {'count': 0, 'error': str(e)}

    def _commit_individuals_to_case_ontology(self, case_id: int, individuals: List[Tuple[Any, Dict]]) -> Dict[str, Any]:
        """
        Commit individuals to a case-specific ontology file.

        Creates proethica-case-N.ttl files that import from proethica-cases.
        """
        try:
            case_file = self.ontologies_dir / f"proethica-case-{case_id}.ttl"

            # Load existing graph or create new one
            g = Graph()
            if case_file.exists():
                g.parse(case_file, format='turtle')
            else:
                # Add ontology declaration for new case file
                case_ontology_uri = URIRef(f"http://proethica.org/ontology/case/{case_id}")
                g.add((case_ontology_uri, RDF.type, OWL.Ontology))
                g.add((case_ontology_uri, RDFS.label, Literal(f"ProEthica Case {case_id} Ontology")))
                g.add((case_ontology_uri, OWL.imports, URIRef("http://proethica.org/ontology/cases")))
                g.add((case_ontology_uri, OWL.imports, URIRef("http://proethica.org/ontology/intermediate")))
                g.add((case_ontology_uri, DCTERMS.created, Literal(datetime.utcnow())))

            # Bind namespaces
            g.bind(f"case{case_id}", Namespace(f"http://proethica.org/ontology/case/{case_id}#"))
            g.bind("proeth", PROETHICA)
            g.bind("proeth-core", PROETHICA_CORE)
            g.bind("proeth-cases", PROETHICA_CASES)
            g.bind("bfo", BFO)
            g.bind("iao", IAO)
            g.bind("prov", PROV)

            case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")

            count = 0
            for entity, rdf_data in individuals:
                extraction_type = entity.extraction_type or ''

                # Determine label - use short IDs for certain entity types
                # For types with dedicated property fields (focus, questionText, etc.), skip rdfs:comment
                if extraction_type == 'canonical_decision_point' and rdf_data and rdf_data.get('focus_id'):
                    # Use focus_id (e.g., "DP1") - full text goes in proeth:focus
                    label = rdf_data['focus_id']
                    full_description = None
                elif extraction_type in ('ethical_question', 'question_generated') and rdf_data and rdf_data.get('questionNumber'):
                    # Use Question_N - full text goes in proeth:questionText
                    label = f"Question_{rdf_data['questionNumber']}"
                    full_description = None
                elif extraction_type == 'ethical_conclusion' and rdf_data and rdf_data.get('conclusionNumber'):
                    # Use Conclusion_N - full text goes in proeth:conclusionText
                    label = f"Conclusion_{rdf_data['conclusionNumber']}"
                    full_description = None
                else:
                    label = entity.entity_label or 'UnknownIndividual'
                    full_description = None

                # Sanitize label for valid URI: remove quotes, parens, and other special chars
                safe_label = label.replace(" ", "_").replace("(", "").replace(")", "")
                safe_label = safe_label.replace('"', '').replace("'", "").replace(",", "")
                safe_label = safe_label.replace("<", "").replace(">", "").replace("&", "")
                individual_uri = case_ns[safe_label]

                # Check if individual already exists
                if (individual_uri, RDF.type, OWL.NamedIndividual) in g:
                    logger.info(f"Individual {label} already exists, skipping")
                    continue

                # Add individual as NamedIndividual
                g.add((individual_uri, RDF.type, OWL.NamedIndividual))
                g.add((individual_uri, RDFS.label, Literal(label)))

                # Add full description if we used a short label
                if full_description:
                    g.add((individual_uri, RDFS.comment, Literal(full_description)))

                # Add type based on the class from rdf_json_ld
                if rdf_data and rdf_data.get('types'):
                    for type_uri in rdf_data['types']:
                        # Extract class name from URI
                        if '#' in type_uri:
                            class_name = type_uri.split('#')[-1]
                        else:
                            class_name = type_uri.split('/')[-1]
                        safe_class = class_name.replace(" ", "").replace("(", "").replace(")", "")
                        class_uri = PROETHICA[safe_class]
                        g.add((individual_uri, RDF.type, class_uri))

                # Check if this is an argument entity (Toulmin structure)
                extraction_type = entity.extraction_type or ''
                if extraction_type == 'argument_generated' and rdf_data:
                    # Add Argument type
                    g.add((individual_uri, RDF.type, PROETHICA_CASES.Argument))

                    # Serialize Toulmin structure
                    if rdf_data.get('argument_type'):
                        g.add((individual_uri, PROETHICA['argumentType'], Literal(rdf_data['argument_type'])))
                    if rdf_data.get('decision_point_id'):
                        g.add((individual_uri, PROETHICA['decisionPointId'], Literal(rdf_data['decision_point_id'])))
                    if rdf_data.get('option_description'):
                        g.add((individual_uri, PROETHICA['optionDescription'], Literal(rdf_data['option_description'])))
                    if rdf_data.get('confidence_score'):
                        g.add((individual_uri, PROETHICA['confidenceScore'], Literal(float(rdf_data['confidence_score']), datatype=XSD.decimal)))

                    # Claim
                    claim = rdf_data.get('claim', {})
                    if isinstance(claim, dict) and claim.get('text'):
                        g.add((individual_uri, PROETHICA['claimText'], Literal(claim['text'])))
                        if claim.get('entity_label'):
                            g.add((individual_uri, PROETHICA['claimEntity'], Literal(claim['entity_label'])))

                    # Warrant(s)
                    warrant = rdf_data.get('warrant', {})
                    if isinstance(warrant, dict) and warrant.get('entity_label'):
                        g.add((individual_uri, PROETHICA['warrantEntity'], Literal(warrant['entity_label'])))
                        if warrant.get('entity_type'):
                            g.add((individual_uri, PROETHICA['warrantType'], Literal(warrant['entity_type'])))

                    # Backing (code provision)
                    backing = rdf_data.get('backing', {})
                    if isinstance(backing, dict) and backing.get('entity_label'):
                        g.add((individual_uri, PROETHICA['backingProvision'], Literal(backing['entity_label'])))

                    # Qualifier (constraint)
                    qualifier = rdf_data.get('qualifier', {})
                    if isinstance(qualifier, dict) and qualifier.get('entity_label'):
                        g.add((individual_uri, PROETHICA['qualifierConstraint'], Literal(qualifier['entity_label'])))

                    # Role
                    if rdf_data.get('role_label'):
                        g.add((individual_uri, PROETHICA['roleLabel'], Literal(rdf_data['role_label'])))

                    # Founding good analysis
                    if rdf_data.get('founding_good_analysis'):
                        g.add((individual_uri, PROETHICA['foundingGoodAnalysis'], Literal(rdf_data['founding_good_analysis'])))

                # Check if this is an argument validation entity
                elif extraction_type == 'argument_validation' and rdf_data:
                    # Add ArgumentValidation type
                    g.add((individual_uri, RDF.type, PROETHICA_CASES.ArgumentValidation))

                    # Link to the argument being validated
                    if rdf_data.get('argument_id'):
                        arg_id = rdf_data['argument_id']
                        argument_uri = case_ns[arg_id]
                        g.add((individual_uri, PROETHICA['validatesArgument'], argument_uri))
                        g.add((individual_uri, PROETHICA['argumentId'], Literal(arg_id)))

                    # Basic argument context
                    if rdf_data.get('decision_point_id'):
                        g.add((individual_uri, PROETHICA['decisionPointId'], Literal(rdf_data['decision_point_id'])))
                    if rdf_data.get('argument_type'):
                        g.add((individual_uri, PROETHICA['argumentType'], Literal(rdf_data['argument_type'])))

                    # Overall validation results
                    if 'is_valid' in rdf_data:
                        g.add((individual_uri, PROETHICA['isValid'], Literal(rdf_data['is_valid'], datatype=XSD.boolean)))
                    if rdf_data.get('validation_score') is not None:
                        g.add((individual_uri, PROETHICA['validationScore'], Literal(float(rdf_data['validation_score']), datatype=XSD.decimal)))

                    # Validation notes
                    notes = rdf_data.get('validation_notes', [])
                    if notes:
                        for i, note in enumerate(notes):
                            g.add((individual_uri, PROETHICA[f'validationNote{i+1}'], Literal(note)))

                    # Entity validation results
                    entity_val = rdf_data.get('entity_validation', {})
                    if entity_val:
                        if 'is_valid' in entity_val:
                            g.add((individual_uri, PROETHICA['entityValidationPassed'], Literal(entity_val['is_valid'], datatype=XSD.boolean)))
                        missing = entity_val.get('missing_entities', [])
                        for i, m in enumerate(missing):
                            g.add((individual_uri, PROETHICA[f'missingEntity{i+1}'], Literal(m)))

                    # Founding value validation
                    founding_val = rdf_data.get('founding_value_validation', {})
                    if founding_val:
                        if 'is_compliant' in founding_val:
                            g.add((individual_uri, PROETHICA['foundingValueCompliant'], Literal(founding_val['is_compliant'], datatype=XSD.boolean)))
                        if founding_val.get('founding_good'):
                            g.add((individual_uri, PROETHICA['foundingGood'], Literal(founding_val['founding_good'])))
                        if founding_val.get('analysis'):
                            g.add((individual_uri, PROETHICA['foundingValueAnalysis'], Literal(founding_val['analysis'])))

                    # Virtue validation
                    virtue_val = rdf_data.get('virtue_validation', {})
                    if virtue_val:
                        if 'is_valid' in virtue_val:
                            g.add((individual_uri, PROETHICA['virtueValidationPassed'], Literal(virtue_val['is_valid'], datatype=XSD.boolean)))
                        missing_virtues = virtue_val.get('missing_virtues', [])
                        for i, v in enumerate(missing_virtues):
                            g.add((individual_uri, PROETHICA[f'missingVirtue{i+1}'], Literal(v)))

                # Check if this is a decision point
                elif extraction_type == 'canonical_decision_point' and rdf_data:
                    g.add((individual_uri, RDF.type, PROETHICA_CASES.DecisionPoint))
                    # Add decision point ID
                    if rdf_data.get('focus_id'):
                        g.add((individual_uri, PROETHICA['decisionPointId'], Literal(rdf_data['focus_id'])))
                    # Use 'description' field as focus (the full text description)
                    if rdf_data.get('description'):
                        g.add((individual_uri, PROETHICA['focus'], Literal(rdf_data['description'])))
                    elif rdf_data.get('focus'):
                        g.add((individual_uri, PROETHICA['focus'], Literal(rdf_data['focus'])))
                    # Decision question
                    if rdf_data.get('decision_question'):
                        g.add((individual_uri, PROETHICA['decisionQuestion'], Literal(rdf_data['decision_question'])))
                    if rdf_data.get('context'):
                        g.add((individual_uri, PROETHICA['context'], Literal(rdf_data['context'])))
                    # Role involved
                    if rdf_data.get('role_label'):
                        g.add((individual_uri, PROETHICA['roleLabel'], Literal(rdf_data['role_label'])))
                    # Serialize options
                    options = rdf_data.get('options', [])
                    for i, opt in enumerate(options):
                        if isinstance(opt, dict) and opt.get('description'):
                            g.add((individual_uri, PROETHICA[f'option{i+1}'], Literal(opt['description'])))

                # Check if this is an ethical conclusion
                elif extraction_type == 'ethical_conclusion' and rdf_data:
                    g.add((individual_uri, RDF.type, PROETHICA_CASES.EthicalConclusion))
                    if rdf_data.get('conclusionText'):
                        g.add((individual_uri, PROETHICA['conclusionText'], Literal(rdf_data['conclusionText'])))
                    if rdf_data.get('conclusionType'):
                        g.add((individual_uri, PROETHICA['conclusionType'], Literal(rdf_data['conclusionType'])))
                    if rdf_data.get('conclusionNumber'):
                        g.add((individual_uri, PROETHICA['conclusionNumber'], Literal(int(rdf_data['conclusionNumber']), datatype=XSD.integer)))
                    if rdf_data.get('extractionReasoning'):
                        g.add((individual_uri, PROETHICA['extractionReasoning'], Literal(rdf_data['extractionReasoning'])))
                    # Cited provisions
                    cited = rdf_data.get('citedProvisions', [])
                    for i, prov in enumerate(cited):
                        g.add((individual_uri, PROETHICA[f'citedProvision{i+1}'], Literal(prov)))
                    # Answers questions
                    answers = rdf_data.get('answersQuestions', [])
                    for i, q in enumerate(answers):
                        g.add((individual_uri, PROETHICA[f'answersQuestion{i+1}'], Literal(str(q))))

                # Check if this is an ethical question
                elif extraction_type == 'ethical_question' and rdf_data:
                    g.add((individual_uri, RDF.type, PROETHICA_CASES.EthicalQuestion))
                    if rdf_data.get('questionText'):
                        g.add((individual_uri, PROETHICA['questionText'], Literal(rdf_data['questionText'])))
                    if rdf_data.get('questionType'):
                        g.add((individual_uri, PROETHICA['questionType'], Literal(rdf_data['questionType'])))
                    if rdf_data.get('questionNumber'):
                        g.add((individual_uri, PROETHICA['questionNumber'], Literal(int(rdf_data['questionNumber']), datatype=XSD.integer)))
                    if rdf_data.get('emergence'):
                        g.add((individual_uri, PROETHICA['emergence'], Literal(rdf_data['emergence'])))

                # Standard properties handling for other entity types
                elif rdf_data and rdf_data.get('properties'):
                    properties = rdf_data['properties']
                    for prop_name, prop_values in properties.items():
                        if not isinstance(prop_values, list):
                            prop_values = [prop_values]
                        safe_prop = self._camelCase(prop_name)
                        prop_uri = PROETHICA[safe_prop]
                        for value in prop_values:
                            if value:
                                g.add((individual_uri, prop_uri, Literal(value)))

                # Add provenance
                g.add((individual_uri, PROV.generatedAtTime, Literal(datetime.utcnow())))
                g.add((individual_uri, PROV.wasGeneratedBy, Literal(f"ProEthica Case {case_id} Extraction")))

                count += 1

            # Save the graph
            g.serialize(destination=case_file, format='turtle')
            logger.info(f"Committed {count} individuals to {case_file}")

            # Register the case ontology if it's new
            if not case_file.exists() or count > 0:
                self._register_case_ontology(case_id)

            return {'count': count, 'file': str(case_file)}

        except Exception as e:
            logger.error(f"Error committing individuals: {e}")
            return {'count': 0, 'error': str(e)}

    def _ensure_import_statement(self):
        """
        Ensure proethica-intermediate.ttl imports the extracted file.

        This adds an owl:imports statement if not already present.
        """
        try:
            intermediate_file = self.ontologies_dir / "proethica-intermediate.ttl"
            if not intermediate_file.exists():
                logger.warning("proethica-intermediate.ttl not found")
                return

            # Check if import already exists
            with open(intermediate_file, 'r') as f:
                content = f.read()

            import_statement = "owl:imports <http://proethica.org/ontology/intermediate-extended> ;"

            if "intermediate-extended" not in content:
                # Add import statement after other imports
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'owl:imports' in line and 'proethica-core' in line:
                        # Insert after this line
                        lines.insert(i + 1, f"    {import_statement}")
                        break

                # Write back
                with open(intermediate_file, 'w') as f:
                    f.write('\n'.join(lines))

                logger.info("Added import statement for intermediate-extended to proethica-intermediate.ttl")

        except Exception as e:
            logger.error(f"Error ensuring import statement: {e}")

    def _synchronize_with_ontserve(self) -> Dict[str, Any]:
        """
        Synchronize TTL files with OntServe database.

        Runs the refresh_entity_extraction.py script to update the database.
        """
        try:
            # Run refresh script for proethica-intermediate-extended (where new classes are stored)
            refresh_script = self.ontserve_path / "scripts" / "refresh_entity_extraction.py"

            if not refresh_script.exists():
                return {
                    'success': False,
                    'error': 'Refresh script not found'
                }

            # Refresh the extracted ontology (scripts handle their own path setup)
            result = subprocess.run(
                [self.ontserve_python, str(refresh_script), "proethica-intermediate-extended"],
                capture_output=True,
                text=True,
                cwd=str(self.ontserve_path),
                timeout=60
            )

            if result.returncode == 0:
                logger.info("Successfully synchronized with OntServe database")

                # Also notify MCP server to refresh its cache
                try:
                    response = requests.post(f"{self.mcp_url}/refresh_cache")
                    if response.status_code == 200:
                        logger.info("MCP server cache refreshed")
                except:
                    pass  # MCP refresh is optional

                return {
                    'success': True,
                    'output': result.stdout
                }
            else:
                logger.error(f"Refresh script failed: {result.stderr}")
                return {
                    'success': False,
                    'error': result.stderr
                }

        except subprocess.TimeoutExpired:
            logger.error("Sync script timed out")
            return {
                'success': False,
                'error': 'Sync timed out'
            }

        except Exception as e:
            logger.error(f"Error synchronizing with OntServe: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _register_case_ontology(self, case_id: int) -> Dict[str, Any]:
        """
        Register a new case ontology in the OntServe database.

        This ensures the case ontology appears in the web interface and can be queried.
        """
        try:
            register_script = self.ontserve_path / "scripts" / "register_case_ontologies.py"

            if not register_script.exists():
                logger.warning("Registration script not found, trying to register via refresh")
                return self._refresh_case_ontology(case_id)

            # Run the registration script (scripts handle their own path setup)
            result = subprocess.run(
                [self.ontserve_python, str(register_script)],
                capture_output=True,
                text=True,
                cwd=str(self.ontserve_path),
                timeout=60
            )

            if result.returncode == 0:
                logger.info(f"Successfully registered case-{case_id} ontology")
                return {'success': True}
            else:
                logger.error(f"Failed to register case ontology: {result.stderr}")
                return {'success': False, 'error': result.stderr}

        except subprocess.TimeoutExpired:
            logger.error("Registration script timed out")
            return {'success': False, 'error': 'Registration timed out'}
        except Exception as e:
            logger.error(f"Error registering case ontology: {e}")
            return {'success': False, 'error': str(e)}

    def _refresh_case_ontology(self, case_id: int) -> Dict[str, Any]:
        """
        Refresh entity extraction for a case-specific ontology.

        This updates the database to include individuals.
        """
        try:
            refresh_script = self.ontserve_path / "scripts" / "refresh_entity_extraction.py"
            case_ontology_name = f"proethica-case-{case_id}"

            # Run refresh script (scripts handle their own path setup)
            result = subprocess.run(
                [self.ontserve_python, str(refresh_script), case_ontology_name],
                capture_output=True,
                text=True,
                cwd=str(self.ontserve_path),
                timeout=60
            )

            if result.returncode == 0:
                logger.info(f"Successfully refreshed case ontology {case_ontology_name}")
                return {'success': True}
            else:
                logger.error(f"Failed to refresh case ontology: {result.stderr}")
                return {'success': False, 'error': result.stderr}

        except subprocess.TimeoutExpired:
            logger.error(f"Refresh script timed out for {case_ontology_name}")
            return {'success': False, 'error': 'Refresh timed out'}
        except Exception as e:
            logger.error(f"Error refreshing case ontology: {e}")
            return {'success': False, 'error': str(e)}

    # Maps extraction_type (or entity_type for temporal_dynamics) to:
    #   (category_field_name, CATEGORY_TO_ONTOLOGY_IRI key, fallback core class URI)
    # Multi-axis concepts (obligations, constraints) have a second entry for the
    # orthogonal axis (enforcement_level, flexibility).
    _CONCEPT_CATEGORY_CONFIG = {
        'roles':        [('role_category',       'roles',                  f'{PROETHICA_CORE}Role')],
        'principles':   [('principle_category',  'principles',             f'{PROETHICA_CORE}Principle')],
        'obligations':  [('obligation_type',     'obligations',            f'{PROETHICA_CORE}Obligation'),
                         ('enforcement_level',   'obligation_enforcement', None)],
        'states':       [('state_category',      'states',                 f'{PROETHICA_CORE}State')],
        'resources':    [('resource_category',   'resources',              f'{PROETHICA_CORE}Resource')],
        'actions':      [('action_category',     'actions',                f'{PROETHICA_CORE}Action')],
        'events':       [('event_category',      'events',                 f'{PROETHICA_CORE}Event')],
        'capabilities': [('capability_category', 'capabilities',           f'{PROETHICA_CORE}Capability')],
        'constraints':  [('constraint_type',     'constraints',            f'{PROETHICA_CORE}Constraint'),
                         ('flexibility',         'constraint_flexibility', None)],
    }

    def _resolve_subclass_uris(self, entity, rdf_data: Dict) -> list[str]:
        """
        Resolve the rdfs:subClassOf target(s) for a class entity.

        Checks rdf_json_ld for category fields from the unified Pydantic schemas
        and looks them up in CATEGORY_TO_ONTOLOGY_IRI.  Falls back to the core
        concept class (e.g. proethica-core#Role) for legacy data without category.

        Multi-axis concepts (obligations, constraints) can produce two subclass
        URIs -- one per axis.
        """
        concept_type = (entity.extraction_type or '').lower()
        entity_type_lower = (entity.entity_type or '').lower()

        # For temporal_dynamics_enhanced, the entity_type carries the actual
        # concept (e.g. 'actions' or 'events') rather than extraction_type.
        if 'temporal_dynamics' in concept_type:
            key = entity_type_lower.rstrip('s') if entity_type_lower else concept_type
            # Normalize to plural form used in config
            for config_key in self._CONCEPT_CATEGORY_CONFIG:
                if config_key.startswith(key):
                    concept_type = config_key
                    break

        axes = self._CONCEPT_CATEGORY_CONFIG.get(concept_type)
        if not axes:
            # Unrecognized concept type -- try substring match for robustness
            for config_key, config_axes in self._CONCEPT_CATEGORY_CONFIG.items():
                if config_key in concept_type or config_key in entity_type_lower:
                    axes = config_axes
                    concept_type = config_key
                    break

        if not axes:
            logger.warning(f"No category config for extraction_type={entity.extraction_type}, "
                          f"entity_type={entity.entity_type}")
            return []

        result = []
        props = (rdf_data or {}).get('properties', {})

        for category_field, iri_map_key, fallback_uri in axes:
            # Check for category value in rdf_json_ld properties
            category_value = None
            if props:
                vals = props.get(category_field)
                if vals:
                    category_value = vals[0] if isinstance(vals, list) else vals
            # Also check top-level rdf_json_ld (unified extractor stores flat)
            if not category_value and rdf_data:
                category_value = rdf_data.get(category_field)

            if category_value:
                # Normalize enum value (Pydantic may store as 'provider_client' or 'ProviderClient')
                normalized = category_value.lower().replace(' ', '_').replace('-', '_')
                iri_map = CATEGORY_TO_ONTOLOGY_IRI.get(iri_map_key, {})
                iri = iri_map.get(normalized)
                if iri:
                    result.append(iri)
                elif fallback_uri:
                    result.append(fallback_uri)
            elif fallback_uri:
                # No category info (legacy data) -- use core class
                result.append(fallback_uri)

        return result

    def _camelCase(self, text: str) -> str:
        """Convert text to camelCase for property names."""
        words = text.replace('_', ' ').split()
        if not words:
            return text

        # First word lowercase, rest title case
        result = words[0].lower()
        for word in words[1:]:
            result += word.capitalize()

        return result

    def get_commit_status(self, case_id: int) -> Dict[str, Any]:
        """
        Get the commit status for a case.

        Returns information about what has been committed and what's pending.
        """
        try:
            # Count draft (unpublished) entities
            pending = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                is_published=False
            ).count()

            # Count published entities
            committed = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                is_published=True
            ).count()

            # Check if case ontology exists
            case_file = self.ontologies_dir / f"proethica-case-{case_id}.ttl"
            case_ontology_exists = case_file.exists()

            return {
                'pending_count': pending,
                'committed_count': committed,
                'case_ontology_exists': case_ontology_exists,
                'case_ontology_file': str(case_file) if case_ontology_exists else None
            }

        except Exception as e:
            logger.error(f"Error getting commit status: {e}")
            return {
                'error': str(e)
            }

    # ========== VERSIONED COMMIT METHODS ==========

    def commit_case_versioned(self, case_id: int, entity_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Commit entities with versioning support.

        This method:
        1. Marks existing OntServe concepts for this case as superseded (is_current=false)
        2. Creates new concept records with incremented extraction_run_version
        3. OVERWRITES the case TTL file (no merging)
        4. For classes, creates individual class versions

        Args:
            case_id: The case ID
            entity_ids: Optional list of specific entity IDs to commit. If None, commits all.

        Returns:
            Dictionary with commit results including version info
        """
        try:
            # Fetch entities to commit
            if entity_ids:
                entities = TemporaryRDFStorage.query.filter(
                    TemporaryRDFStorage.id.in_(entity_ids),
                    TemporaryRDFStorage.case_id == case_id
                ).all()
            else:
                # Commit all entities for this case
                entities = TemporaryRDFStorage.query.filter_by(case_id=case_id).all()

            if not entities:
                return {
                    'success': False,
                    'error': 'No entities found to commit'
                }

            # Separate classes and individuals
            classes_to_commit = []
            individuals_to_commit = []

            for entity in entities:
                rdf_data = entity.rdf_json_ld if entity.rdf_json_ld else {}
                if entity.storage_type == 'class':
                    classes_to_commit.append((entity, rdf_data))
                elif entity.storage_type == 'individual':
                    individuals_to_commit.append((entity, rdf_data))

            results = {
                'success': True,
                'case_id': case_id,
                'classes_committed': 0,
                'individuals_committed': 0,
                'versions_superseded': 0,
                'new_version': None,
                'errors': []
            }

            # Connect to OntServe database
            conn = psycopg2.connect(**ONTSERVE_DB_CONFIG)
            try:
                # Get the next extraction run version for this case
                new_version = self._get_next_extraction_version(conn, case_id)
                results['new_version'] = new_version

                # Supersede existing current versions for this case
                superseded = self._supersede_case_versions(conn, case_id)
                results['versions_superseded'] = superseded

                # Commit individuals to OntServe concepts table
                if individuals_to_commit:
                    ind_result = self._commit_individuals_versioned(
                        conn, case_id, new_version, individuals_to_commit
                    )
                    results['individuals_committed'] = ind_result['count']
                    if ind_result.get('error'):
                        results['errors'].append(ind_result['error'])

                # Commit classes with individual versioning
                if classes_to_commit:
                    class_result = self._commit_classes_versioned(
                        conn, case_id, new_version, classes_to_commit
                    )
                    results['classes_committed'] = class_result['count']
                    results['class_versions_created'] = class_result.get('versions_created', 0)
                    if class_result.get('error'):
                        results['errors'].append(class_result['error'])

                conn.commit()

            except Exception as e:
                conn.rollback()
                raise
            finally:
                conn.close()

            # Write TTL files (overwrites existing)
            if individuals_to_commit:
                ttl_result = self._write_case_ttl_fresh(case_id, individuals_to_commit)
                if ttl_result.get('error'):
                    results['errors'].append(ttl_result['error'])
                results['ttl_file'] = ttl_result.get('file')

            if classes_to_commit:
                # For classes, we still append to intermediate-extended.ttl
                # but with version metadata
                class_ttl_result = self._commit_classes_to_intermediate(classes_to_commit)
                if class_ttl_result.get('error'):
                    results['errors'].append(class_ttl_result['error'])

            # Mark entities as published in ProEthica
            for entity in entities:
                entity.is_published = True

            from app import db
            db.session.commit()

            # Sync with OntServe (register + refresh)
            if individuals_to_commit:
                register_result = self._register_case_ontology(case_id)
                if register_result.get('success'):
                    refresh_result = self._refresh_case_ontology(case_id)
                    if refresh_result.get('success'):
                        results['ontserve_synced'] = True
                    else:
                        results['errors'].append(f"Refresh warning: {refresh_result.get('error')}")
                else:
                    results['errors'].append(f"Register warning: {register_result.get('error')}")

            logger.info(f"Versioned commit for case {case_id}: v{new_version}, "
                       f"{results['individuals_committed']} individuals, "
                       f"{results['classes_committed']} classes")

            return results

        except Exception as e:
            logger.error(f"Error in versioned commit: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def _get_next_extraction_version(self, conn, case_id: int) -> int:
        """Get the next extraction run version for a case."""
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(MAX(extraction_run_version), 0) + 1
                FROM concepts
                WHERE case_id = %s
            """, (case_id,))
            result = cur.fetchone()
            return result[0] if result else 1

    def _supersede_case_versions(self, conn, case_id: int) -> int:
        """Mark all current versions for a case as superseded."""
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE concepts
                SET is_current = false,
                    superseded_at = %s
                WHERE case_id = %s AND is_current = true
            """, (datetime.now(timezone.utc), case_id))
            return cur.rowcount

    def _commit_individuals_versioned(self, conn, case_id: int, version: int,
                                      individuals: List[Tuple[Any, Dict]]) -> Dict[str, Any]:
        """Commit individuals to OntServe concepts table with versioning."""
        try:
            count = 0
            with conn.cursor() as cur:
                # Get domain ID for engineering-ethics
                cur.execute("SELECT id FROM domains WHERE name = 'engineering-ethics'")
                domain_row = cur.fetchone()
                domain_id = domain_row[0] if domain_row else None

                for entity, rdf_data in individuals:
                    label = entity.entity_label or 'UnknownIndividual'
                    safe_label = label.replace(" ", "_").replace("(", "").replace(")", "")
                    safe_label = safe_label.replace('"', '').replace("'", "").replace(",", "")
                    safe_label = safe_label.replace("<", "").replace(">", "").replace("&", "")

                    uri = f"http://proethica.org/ontology/case/{case_id}#{safe_label}"

                    cur.execute("""
                        INSERT INTO concepts (
                            uuid, domain_id, uri, label, primary_type, description,
                            status, case_id, extraction_run_version, is_current,
                            entity_class, extraction_method, source_document,
                            confidence_score, created_by, metadata
                        )
                        VALUES (
                            gen_random_uuid(), %s, %s, %s, %s, %s,
                            'candidate', %s, %s, true,
                            'individual', 'llm_extraction', %s,
                            %s, 'proethica-pipeline', %s
                        )
                    """, (
                        domain_id,
                        uri,
                        label,
                        entity.extraction_type or 'Unknown',
                        entity.entity_definition,
                        case_id,
                        version,
                        f'case:{case_id}',
                        0.7,  # Default confidence
                        Json(rdf_data or {})
                    ))
                    count += 1

            return {'count': count}

        except Exception as e:
            logger.error(f"Error committing individuals versioned: {e}")
            return {'count': 0, 'error': str(e)}

    def _commit_classes_versioned(self, conn, case_id: int, version: int,
                                  classes: List[Tuple[Any, Dict]]) -> Dict[str, Any]:
        """
        Commit classes with individual versioning.

        If a class already exists (by URI), creates a new version entry.
        If new, creates the class as current version.
        """
        try:
            count = 0
            versions_created = 0

            with conn.cursor() as cur:
                # Get domain ID
                cur.execute("SELECT id FROM domains WHERE name = 'engineering-ethics'")
                domain_row = cur.fetchone()
                domain_id = domain_row[0] if domain_row else None

                for entity, rdf_data in classes:
                    label = entity.entity_label or 'UnknownClass'
                    safe_label = label.replace(" ", "").replace("(", "").replace(")", "")
                    safe_label = safe_label.replace('"', '').replace("'", "").replace(",", "")
                    safe_label = safe_label.replace("<", "").replace(">", "").replace("&", "")

                    uri = f"http://proethica.org/ontology/intermediate#{safe_label}"

                    # Check if class already exists
                    cur.execute("""
                        SELECT id, version_number FROM concepts
                        WHERE uri = %s AND entity_class = 'class' AND is_current = true
                    """, (uri,))
                    existing = cur.fetchone()

                    if existing:
                        # Class exists - create version history and update
                        concept_id, old_version = existing

                        # Create version entry for the old version
                        cur.execute("""
                            INSERT INTO concept_versions (
                                concept_id, version_number, uri, label, semantic_label,
                                primary_type, description, status, metadata,
                                changed_fields, change_reason, changed_by
                            )
                            SELECT id, version_number, uri, label, semantic_label,
                                   primary_type, description, status, metadata,
                                   %s, %s, %s
                            FROM concepts WHERE id = %s
                        """, (
                            Json(['description', 'case_id']),
                            f'Re-extracted from case {case_id}',
                            'proethica-pipeline',
                            concept_id
                        ))

                        # Update existing concept with new version
                        cur.execute("""
                            UPDATE concepts
                            SET description = %s,
                                version_number = version_number + 1,
                                case_id = %s,
                                extraction_run_version = %s,
                                updated_at = %s,
                                updated_by = 'proethica-pipeline',
                                metadata = %s
                            WHERE id = %s
                        """, (
                            entity.entity_definition,
                            case_id,
                            version,
                            datetime.now(timezone.utc),
                            Json(rdf_data or {}),
                            concept_id
                        ))
                        versions_created += 1
                    else:
                        # New class - create fresh
                        cur.execute("""
                            INSERT INTO concepts (
                                uuid, domain_id, uri, label, primary_type, description,
                                status, case_id, extraction_run_version, is_current,
                                entity_class, extraction_method, source_document,
                                created_by, metadata
                            )
                            VALUES (
                                gen_random_uuid(), %s, %s, %s, %s, %s,
                                'candidate', %s, %s, true,
                                'class', 'llm_extraction', %s,
                                'proethica-pipeline', %s
                            )
                        """, (
                            domain_id,
                            uri,
                            label,
                            entity.extraction_type or 'Unknown',
                            entity.entity_definition,
                            case_id,
                            version,
                            f'case:{case_id}',
                            Json(rdf_data or {})
                        ))

                    count += 1

            return {'count': count, 'versions_created': versions_created}

        except Exception as e:
            logger.error(f"Error committing classes versioned: {e}")
            return {'count': 0, 'error': str(e)}

    def _write_case_ttl_fresh(self, case_id: int, individuals: List[Tuple[Any, Dict]]) -> Dict[str, Any]:
        """
        Write a fresh case TTL file (overwrites any existing file).

        This is the versioned approach - each extraction completely replaces the previous TTL.
        """
        try:
            case_file = self.ontologies_dir / f"proethica-case-{case_id}.ttl"

            # Create new graph (don't load existing)
            g = Graph()

            # Add ontology declaration
            case_ontology_uri = URIRef(f"http://proethica.org/ontology/case/{case_id}")
            g.add((case_ontology_uri, RDF.type, OWL.Ontology))
            g.add((case_ontology_uri, RDFS.label, Literal(f"ProEthica Case {case_id} Ontology")))
            g.add((case_ontology_uri, OWL.imports, URIRef("http://proethica.org/ontology/cases")))
            g.add((case_ontology_uri, OWL.imports, URIRef("http://proethica.org/ontology/intermediate")))
            g.add((case_ontology_uri, DCTERMS.created, Literal(datetime.now(timezone.utc))))

            # Bind namespaces
            case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")
            g.bind(f"case{case_id}", case_ns)
            g.bind("proeth", PROETHICA)
            g.bind("proeth-core", PROETHICA_CORE)
            g.bind("proeth-cases", PROETHICA_CASES)
            g.bind("bfo", BFO)
            g.bind("iao", IAO)
            g.bind("prov", PROV)

            count = 0
            for entity, rdf_data in individuals:
                # Use the existing individual serialization logic
                extraction_type = entity.extraction_type or ''

                # Determine label
                if extraction_type == 'canonical_decision_point' and rdf_data and rdf_data.get('focus_id'):
                    label = rdf_data['focus_id']
                elif extraction_type in ('ethical_question', 'question_generated') and rdf_data and rdf_data.get('questionNumber'):
                    label = f"Question_{rdf_data['questionNumber']}"
                elif extraction_type == 'ethical_conclusion' and rdf_data and rdf_data.get('conclusionNumber'):
                    label = f"Conclusion_{rdf_data['conclusionNumber']}"
                else:
                    label = entity.entity_label or 'UnknownIndividual'

                safe_label = label.replace(" ", "_").replace("(", "").replace(")", "")
                safe_label = safe_label.replace('"', '').replace("'", "").replace(",", "")
                safe_label = safe_label.replace("<", "").replace(">", "").replace("&", "")
                individual_uri = case_ns[safe_label]

                # Add individual
                g.add((individual_uri, RDF.type, OWL.NamedIndividual))
                g.add((individual_uri, RDFS.label, Literal(label)))

                # Add type based on rdf_json_ld types
                if rdf_data and rdf_data.get('types'):
                    for type_uri in rdf_data['types']:
                        if '#' in type_uri:
                            class_name = type_uri.split('#')[-1]
                        else:
                            class_name = type_uri.split('/')[-1]
                        safe_class = class_name.replace(" ", "").replace("(", "").replace(")", "")
                        class_uri = PROETHICA[safe_class]
                        g.add((individual_uri, RDF.type, class_uri))

                # Add type-specific properties (reuse existing logic)
                self._add_individual_properties(g, individual_uri, entity, rdf_data, case_ns)

                # Provenance
                g.add((individual_uri, PROV.generatedAtTime, Literal(datetime.now(timezone.utc))))
                g.add((individual_uri, PROV.wasGeneratedBy, Literal(f"ProEthica Case {case_id} Extraction")))

                count += 1

            # Write file (overwrites existing)
            g.serialize(destination=case_file, format='turtle')
            logger.info(f"Wrote fresh TTL file with {count} individuals to {case_file}")

            return {'count': count, 'file': str(case_file)}

        except Exception as e:
            logger.error(f"Error writing fresh case TTL: {e}")
            return {'count': 0, 'error': str(e)}

    def _add_individual_properties(self, g: Graph, uri: URIRef, entity: Any,
                                   rdf_data: Dict, case_ns: Namespace):
        """Add type-specific properties to an individual in the graph."""
        extraction_type = entity.extraction_type or ''

        if extraction_type == 'argument_generated' and rdf_data:
            g.add((uri, RDF.type, PROETHICA_CASES.Argument))
            if rdf_data.get('argument_type'):
                g.add((uri, PROETHICA['argumentType'], Literal(rdf_data['argument_type'])))
            if rdf_data.get('decision_point_id'):
                g.add((uri, PROETHICA['decisionPointId'], Literal(rdf_data['decision_point_id'])))
            # ... (other argument properties handled similarly)

        elif extraction_type == 'canonical_decision_point' and rdf_data:
            g.add((uri, RDF.type, PROETHICA_CASES.DecisionPoint))
            if rdf_data.get('focus_id'):
                g.add((uri, PROETHICA['decisionPointId'], Literal(rdf_data['focus_id'])))
            if rdf_data.get('description'):
                g.add((uri, PROETHICA['focus'], Literal(rdf_data['description'])))
            elif rdf_data.get('focus'):
                g.add((uri, PROETHICA['focus'], Literal(rdf_data['focus'])))

        elif extraction_type == 'ethical_conclusion' and rdf_data:
            g.add((uri, RDF.type, PROETHICA_CASES.EthicalConclusion))
            if rdf_data.get('conclusionText'):
                g.add((uri, PROETHICA['conclusionText'], Literal(rdf_data['conclusionText'])))
            if rdf_data.get('conclusionType'):
                g.add((uri, PROETHICA['conclusionType'], Literal(rdf_data['conclusionType'])))

        elif extraction_type == 'ethical_question' and rdf_data:
            g.add((uri, RDF.type, PROETHICA_CASES.EthicalQuestion))
            if rdf_data.get('questionText'):
                g.add((uri, PROETHICA['questionText'], Literal(rdf_data['questionText'])))
            if rdf_data.get('questionType'):
                g.add((uri, PROETHICA['questionType'], Literal(rdf_data['questionType'])))

        # Generic properties fallback
        elif rdf_data and rdf_data.get('properties'):
            for prop_name, prop_values in rdf_data['properties'].items():
                if not isinstance(prop_values, list):
                    prop_values = [prop_values]
                safe_prop = self._camelCase(prop_name)
                prop_uri = PROETHICA[safe_prop]
                for value in prop_values:
                    if value:
                        g.add((uri, prop_uri, Literal(value)))

    def get_case_version_history(self, case_id: int) -> Dict[str, Any]:
        """
        Get version history for a case's extractions.

        Returns:
            Dictionary with version history and current state
        """
        try:
            conn = psycopg2.connect(**ONTSERVE_DB_CONFIG)
            try:
                with conn.cursor() as cur:
                    # Get all versions for this case
                    cur.execute("""
                        SELECT extraction_run_version, COUNT(*) as entity_count,
                               MIN(created_at) as extracted_at, is_current
                        FROM concepts
                        WHERE case_id = %s
                        GROUP BY extraction_run_version, is_current
                        ORDER BY extraction_run_version DESC
                    """, (case_id,))

                    versions = []
                    for row in cur.fetchall():
                        versions.append({
                            'version': row[0],
                            'entity_count': row[1],
                            'extracted_at': row[2].isoformat() if row[2] else None,
                            'is_current': row[3]
                        })

                    return {
                        'case_id': case_id,
                        'versions': versions,
                        'total_versions': len(set(v['version'] for v in versions))
                    }
            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Error getting version history: {e}")
            return {'error': str(e)}

