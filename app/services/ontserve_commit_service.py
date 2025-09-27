"""
OntServe Commit Service for ProEthica

Handles committing extracted entities from temporary storage to permanent OntServe storage.
- Classes are saved to proethica-intermediate-extracted.ttl (supplemental file)
- Individuals are saved to case-specific ontologies (proethica-case-N.ttl)
- Synchronizes with OntServe database via refresh scripts
"""

import os
import json
import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import subprocess
from pathlib import Path
import requests

from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL
from rdflib.namespace import SKOS, DCTERMS

from app.models.temporary_rdf_storage import TemporaryRDFStorage

logger = logging.getLogger(__name__)

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

            # Commit classes to proethica-intermediate-extracted.ttl
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
                else:
                    # Also refresh the case ontology to extract individuals
                    self._refresh_case_ontology(case_id)

            # Mark entities as committed
            for entity in entities:
                entity.is_committed = True
                entity.committed_at = datetime.utcnow()

            from app import db
            db.session.commit()

            # Synchronize with OntServe database
            sync_result = self._synchronize_with_ontserve()
            if not sync_result['success']:
                results['errors'].append(f"Sync warning: {sync_result.get('error', 'Unknown error')}")

            results['sync_status'] = sync_result

            return results

        except Exception as e:
            logger.error(f"Error committing entities: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _commit_classes_to_intermediate(self, classes: List[Tuple[Any, Dict]]) -> Dict[str, Any]:
        """
        Commit new classes to proethica-intermediate-extracted.ttl.

        This creates a supplemental file that can be imported by proethica-intermediate.ttl
        to avoid making the main file unwieldy.
        """
        try:
            extracted_file = self.ontologies_dir / "proethica-intermediate-extracted.ttl"

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

            count = 0
            for entity, rdf_data in classes:
                # Use entity attributes directly
                label = entity.entity_label or 'UnknownClass'
                safe_label = label.replace(" ", "").replace("(", "").replace(")", "")
                class_uri = PROETHICA[safe_label]

                # Check if class already exists
                if (class_uri, RDF.type, OWL.Class) in g:
                    logger.info(f"Class {label} already exists, skipping")
                    continue

                # Add class triple
                g.add((class_uri, RDF.type, OWL.Class))
                g.add((class_uri, RDFS.label, Literal(label)))

                # Add description
                if entity.entity_definition:
                    g.add((class_uri, RDFS.comment, Literal(entity.entity_definition)))
                    g.add((class_uri, SKOS.definition, Literal(entity.entity_definition)))

                # Add subclass relationship based on extraction_type
                concept_type = (entity.extraction_type or '').lower()
                if 'role' in concept_type:
                    g.add((class_uri, RDFS.subClassOf, PROETHICA_CORE.Role))
                elif 'state' in concept_type:
                    g.add((class_uri, RDFS.subClassOf, PROETHICA_CORE.State))
                elif 'resource' in concept_type:
                    g.add((class_uri, RDFS.subClassOf, PROETHICA_CORE.Resource))
                elif 'principle' in concept_type:
                    g.add((class_uri, RDFS.subClassOf, PROETHICA_CORE.Principle))
                elif 'obligation' in concept_type:
                    g.add((class_uri, RDFS.subClassOf, PROETHICA_CORE.Obligation))
                elif 'action' in concept_type:
                    g.add((class_uri, RDFS.subClassOf, PROETHICA_CORE.Action))
                elif 'event' in concept_type:
                    g.add((class_uri, RDFS.subClassOf, PROETHICA_CORE.Event))
                elif 'capability' in concept_type:
                    g.add((class_uri, RDFS.subClassOf, PROETHICA_CORE.Capability))
                elif 'constraint' in concept_type:
                    g.add((class_uri, RDFS.subClassOf, PROETHICA_CORE.Constraint))

                # Add provenance
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
                # Use entity attributes directly
                label = entity.entity_label or 'UnknownIndividual'
                safe_label = label.replace(" ", "_").replace("(", "").replace(")", "")
                individual_uri = case_ns[safe_label]

                # Check if individual already exists
                if (individual_uri, RDF.type, OWL.NamedIndividual) in g:
                    logger.info(f"Individual {label} already exists, skipping")
                    continue

                # Add individual as NamedIndividual
                g.add((individual_uri, RDF.type, OWL.NamedIndividual))
                g.add((individual_uri, RDFS.label, Literal(label)))

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

                # Add properties from rdf_json_ld
                if rdf_data and rdf_data.get('properties'):
                    properties = rdf_data['properties']
                else:
                    properties = {}

                for prop_name, prop_values in properties.items():
                    if not isinstance(prop_values, list):
                        prop_values = [prop_values]

                    # Convert property name to URI
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

            import_statement = "owl:imports <http://proethica.org/ontology/intermediate-extracted> ;"

            if "intermediate-extracted" not in content:
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

                logger.info("Added import statement for intermediate-extracted to proethica-intermediate.ttl")

        except Exception as e:
            logger.error(f"Error ensuring import statement: {e}")

    def _synchronize_with_ontserve(self) -> Dict[str, Any]:
        """
        Synchronize TTL files with OntServe database.

        Runs the refresh_entity_extraction.py script to update the database.
        """
        try:
            # Run refresh script for proethica-intermediate-extracted (where new classes are stored)
            refresh_script = self.ontserve_path / "scripts" / "refresh_entity_extraction.py"

            if not refresh_script.exists():
                return {
                    'success': False,
                    'error': 'Refresh script not found'
                }

            # Refresh the extracted ontology to pick up new classes
            result = subprocess.run(
                ["python", str(refresh_script), "proethica-intermediate-extracted"],
                capture_output=True,
                text=True,
                cwd=str(self.ontserve_path)
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
                # Fallback to just trying refresh
                return self._refresh_case_ontology(case_id)

            # Run the registration script
            result = subprocess.run(
                ["python", str(register_script)],
                capture_output=True,
                text=True,
                cwd=str(self.ontserve_path)
            )

            if result.returncode == 0:
                logger.info(f"Successfully registered case-{case_id} ontology")
                return {'success': True}
            else:
                logger.error(f"Failed to register case ontology: {result.stderr}")
                # Try refresh as fallback
                return self._refresh_case_ontology(case_id)

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

            result = subprocess.run(
                ["python", str(refresh_script), case_ontology_name],
                capture_output=True,
                text=True,
                cwd=str(self.ontserve_path)
            )

            if result.returncode == 0:
                logger.info(f"Successfully refreshed case ontology {case_ontology_name}")
                return {'success': True}
            else:
                logger.error(f"Failed to refresh case ontology: {result.stderr}")
                return {'success': False, 'error': result.stderr}

        except Exception as e:
            logger.error(f"Error refreshing case ontology: {e}")
            return {'success': False, 'error': str(e)}

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
            # Count pending entities
            pending = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                is_committed=False
            ).count()

            # Count committed entities
            committed = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                is_committed=True
            ).count()

            # Check if case ontology exists
            case_file = self.ontologies_dir / f"proethica-case-{case_id}.ttl"
            case_ontology_exists = case_file.exists()

            # Check if extracted file exists
            extracted_file = self.ontologies_dir / "proethica-intermediate-extracted.ttl"
            extracted_ontology_exists = extracted_file.exists()

            return {
                'pending_count': pending,
                'committed_count': committed,
                'case_ontology_exists': case_ontology_exists,
                'case_ontology_file': str(case_file) if case_ontology_exists else None,
                'extracted_ontology_exists': extracted_ontology_exists,
                'extracted_ontology_file': str(extracted_file) if extracted_ontology_exists else None
            }

        except Exception as e:
            logger.error(f"Error getting commit status: {e}")
            return {
                'error': str(e)
            }