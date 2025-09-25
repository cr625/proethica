"""
RDF Extraction Converter Service

Converts LLM extraction results (role classes and individuals) into RDF triples
for storage in proethica-intermediate (classes) and proethica-case-N (individuals).

Handles generic conversion of all LLM-extracted data including relationships,
attributes, and case involvement metadata.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL, XSD
from rdflib.namespace import DCTERMS, PROV, SKOS

logger = logging.getLogger(__name__)


class RDFExtractionConverter:
    """
    Converts LLM extraction results to RDF triples for ontology storage.

    Handles:
    - New role classes for proethica-intermediate
    - Individual instances for case-specific ontologies
    - Generic attribute and relationship capture
    - Provenance tracking
    """

    def __init__(self):
        # Define namespaces
        self.PROETHICA = Namespace("http://proethica.org/ontology/core#")
        self.PROETHICA_INT = Namespace("http://proethica.org/ontology/intermediate#")
        self.PROETHICA_CASES = Namespace("http://proethica.org/ontology/cases#")
        self.PROETHICA_PROV = Namespace("http://proethica.org/provenance#")

        # Initialize graphs for temporary storage
        self.class_graph = Graph()  # For new classes (proethica-intermediate)
        self.individual_graph = Graph()  # For individuals (case-specific)

        # Bind common prefixes
        self._bind_prefixes()

    def _bind_prefixes(self):
        """Bind common namespace prefixes to graphs"""
        for graph in [self.class_graph, self.individual_graph]:
            graph.bind("proethica", self.PROETHICA)
            graph.bind("proethica-int", self.PROETHICA_INT)
            graph.bind("proethica-cases", self.PROETHICA_CASES)
            graph.bind("proethica-prov", self.PROETHICA_PROV)
            graph.bind("rdf", RDF)
            graph.bind("rdfs", RDFS)
            graph.bind("owl", OWL)
            graph.bind("dcterms", DCTERMS)
            graph.bind("prov", PROV)
            graph.bind("skos", SKOS)
            graph.bind("xsd", XSD)

    def convert_extraction_to_rdf(self,
                                 extraction_result: Dict[str, Any],
                                 case_id: int,
                                 extraction_timestamp: Optional[datetime] = None) -> Tuple[Graph, Graph]:
        """
        Convert complete LLM extraction result to RDF triples.

        Args:
            extraction_result: Raw LLM extraction result containing new_role_classes and role_individuals
            case_id: ID of the case this extraction is from
            extraction_timestamp: When the extraction occurred

        Returns:
            Tuple of (class_graph, individual_graph) containing RDF triples
        """
        if not extraction_timestamp:
            extraction_timestamp = datetime.utcnow()

        # Clear previous temporary triples
        self.class_graph = Graph()
        self.individual_graph = Graph()
        self._bind_prefixes()

        # Create case-specific namespace
        case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")
        self.individual_graph.bind(f"case{case_id}", case_ns)

        # Process new role classes
        if "new_role_classes" in extraction_result:
            self._convert_role_classes(extraction_result["new_role_classes"], case_id, extraction_timestamp)

        # Process role individuals
        if "role_individuals" in extraction_result:
            self._convert_role_individuals(extraction_result["role_individuals"], case_id, case_ns, extraction_timestamp)

        return self.class_graph, self.individual_graph

    def _convert_role_classes(self, role_classes: List[Dict], case_id: int, timestamp: datetime):
        """Convert new role classes to RDF triples for proethica-intermediate"""

        for role_class in role_classes:
            # Create URI for the new class
            class_label = role_class.get("label", "UnknownRole")
            safe_label = class_label.replace(" ", "")
            class_uri = self.PROETHICA_INT[safe_label]

            # Basic class definition
            self.class_graph.add((class_uri, RDF.type, OWL.Class))
            self.class_graph.add((class_uri, RDFS.subClassOf, self.PROETHICA.Role))
            self.class_graph.add((class_uri, RDFS.label, Literal(class_label)))

            # Add definition
            if "definition" in role_class:
                self.class_graph.add((class_uri, RDFS.comment, Literal(role_class["definition"])))
                self.class_graph.add((class_uri, SKOS.definition, Literal(role_class["definition"])))

            # Add professional scope
            if "professional_scope" in role_class:
                self.class_graph.add((class_uri, self.PROETHICA_INT.professionalScope,
                                    Literal(role_class["professional_scope"])))

            # Add distinguishing features
            if "distinguishing_features" in role_class:
                for feature in role_class["distinguishing_features"]:
                    self.class_graph.add((class_uri, self.PROETHICA_INT.distinguishingFeature,
                                        Literal(feature)))

            # Add typical qualifications
            if "typical_qualifications" in role_class:
                for qual in role_class["typical_qualifications"]:
                    self.class_graph.add((class_uri, self.PROETHICA_INT.typicalQualification,
                                        Literal(qual)))

            # Add generated obligations (NEW)
            if "generated_obligations" in role_class:
                for obligation in role_class["generated_obligations"]:
                    self.class_graph.add((class_uri, self.PROETHICA.generatesObligation,
                                        Literal(obligation)))

            # Add associated virtues (NEW)
            if "associated_virtues" in role_class:
                for virtue in role_class["associated_virtues"]:
                    self.class_graph.add((class_uri, self.PROETHICA.hasAssociatedVirtue,
                                        Literal(virtue)))

            # Add relationship type (NEW)
            if "relationship_type" in role_class:
                self.class_graph.add((class_uri, self.PROETHICA.hasRelationshipType,
                                    Literal(role_class["relationship_type"])))

            # Add domain context (NEW)
            if "domain_context" in role_class:
                self.class_graph.add((class_uri, self.PROETHICA.hasDomainContext,
                                    Literal(role_class["domain_context"])))

            # Add provenance
            self.class_graph.add((class_uri, PROV.generatedAtTime, Literal(timestamp, datatype=XSD.dateTime)))
            self.class_graph.add((class_uri, PROV.wasAttributedTo, Literal(f"Case {case_id} Extraction")))
            self.class_graph.add((class_uri, self.PROETHICA_PROV.discoveredInCase, Literal(case_id, datatype=XSD.integer)))

            # Add case examples
            if "examples_from_case" in role_class:
                for example in role_class["examples_from_case"]:
                    self.class_graph.add((class_uri, self.PROETHICA_INT.caseExample, Literal(example)))

    def _convert_role_individuals(self, individuals: List[Dict], case_id: int,
                                 case_ns: Namespace, timestamp: datetime):
        """Convert role individuals to RDF triples for case-specific ontology"""

        for individual in individuals:
            # Create URI for the individual
            name = individual.get("name", "UnknownIndividual")
            safe_name = name.replace(" ", "_").replace("'", "")
            individual_uri = case_ns[safe_name]

            # Basic individual definition
            self.individual_graph.add((individual_uri, RDF.type, OWL.NamedIndividual))
            self.individual_graph.add((individual_uri, RDFS.label, Literal(name)))

            # Link to role class
            if "role_classification" in individual:
                role_class = individual["role_classification"]
                # Check if it's a new class or existing one
                safe_role = role_class.replace(" ", "")
                if any("new_role_classes" in k for k in [role_class]):
                    role_uri = self.PROETHICA_INT[safe_role]
                else:
                    # Assume it's an existing class in proethica-intermediate
                    role_uri = self.PROETHICA_INT[safe_role]
                self.individual_graph.add((individual_uri, RDF.type, role_uri))

            # Add attributes as properties
            if "attributes" in individual:
                for attr_key, attr_value in individual["attributes"].items():
                    # Create property URI
                    prop_uri = case_ns[f"has{attr_key.title().replace('_', '')}"]
                    self.individual_graph.add((individual_uri, prop_uri, Literal(attr_value)))

                    # Also add as annotation for searchability
                    self.individual_graph.add((prop_uri, RDF.type, OWL.AnnotationProperty))
                    self.individual_graph.add((prop_uri, RDFS.label, Literal(attr_key.replace("_", " ").title())))

            # Add relationships
            if "relationships" in individual:
                for rel in individual["relationships"]:
                    rel_type = rel.get("type", "relatedTo")
                    target = rel.get("target", "Unknown")

                    # Create relationship property
                    rel_prop = case_ns[rel_type]
                    self.individual_graph.add((rel_prop, RDF.type, OWL.ObjectProperty))
                    self.individual_graph.add((rel_prop, RDFS.label, Literal(rel_type.replace("_", " ").title())))

                    # Create target individual if not exists
                    target_safe = target.replace(" ", "_").replace("'", "")
                    target_uri = case_ns[target_safe]
                    self.individual_graph.add((target_uri, RDF.type, OWL.NamedIndividual))
                    self.individual_graph.add((target_uri, RDFS.label, Literal(target)))

                    # Add the relationship
                    self.individual_graph.add((individual_uri, rel_prop, target_uri))

            # Add case involvement
            if "case_involvement" in individual:
                self.individual_graph.add((individual_uri, self.PROETHICA_INT.caseInvolvement,
                                         Literal(individual["case_involvement"])))

            # Add active obligations (NEW)
            if "active_obligations" in individual:
                for obligation in individual["active_obligations"]:
                    self.individual_graph.add((individual_uri, self.PROETHICA.hasActiveObligation,
                                             Literal(obligation)))

            # Add ethical tensions (NEW)
            if "ethical_tensions" in individual:
                for tension in individual["ethical_tensions"]:
                    self.individual_graph.add((individual_uri, self.PROETHICA.hasEthicalTension,
                                             Literal(tension)))

            # Add provenance
            self.individual_graph.add((individual_uri, PROV.generatedAtTime,
                                     Literal(timestamp, datatype=XSD.dateTime)))
            self.individual_graph.add((individual_uri, PROV.wasAttributedTo,
                                     Literal(f"Case {case_id} Extraction")))

    def serialize_graphs(self, format: str = "turtle") -> Tuple[str, str]:
        """
        Serialize the RDF graphs to strings.

        Args:
            format: RDF serialization format (turtle, xml, n3, etc.)

        Returns:
            Tuple of (class_graph_str, individual_graph_str)
        """
        class_str = self.class_graph.serialize(format=format)
        individual_str = self.individual_graph.serialize(format=format)
        return class_str, individual_str

    def convert_states_extraction_to_rdf(self,
                                        extraction_result: Dict[str, Any],
                                        case_id: int,
                                        extraction_timestamp: Optional[datetime] = None) -> Tuple[Graph, Graph]:
        """
        Convert states extraction result to RDF triples.

        Args:
            extraction_result: Raw LLM extraction result containing new_state_classes and state_individuals
            case_id: ID of the case this extraction is from
            extraction_timestamp: When the extraction occurred

        Returns:
            Tuple of (class_graph, individual_graph)
        """
        timestamp = extraction_timestamp or datetime.utcnow()

        # Clear graphs for new conversion
        self.class_graph = Graph()
        self.individual_graph = Graph()
        self._bind_prefixes()

        # Process new state classes
        for state_class in extraction_result.get('new_state_classes', []):
            self._add_state_class_to_graph(state_class, case_id, timestamp)

        # Process state individuals
        for individual in extraction_result.get('state_individuals', []):
            self._add_state_individual_to_graph(individual, case_id, timestamp)

        return self.class_graph, self.individual_graph

    def _add_state_class_to_graph(self, state_class: Dict[str, Any], case_id: int, timestamp: datetime):
        """Add a new state class to the RDF graph with enhanced temporal properties"""
        # Create URI for the state class
        class_label = state_class.get('label', 'UnknownState')
        safe_label = class_label.replace(" ", "")
        class_uri = URIRef(f"{self.PROETHICA_INT}{safe_label}")

        # Add class definition
        self.class_graph.add((class_uri, RDF.type, OWL.Class))
        self.class_graph.add((class_uri, RDFS.subClassOf, self.PROETHICA.State))
        self.class_graph.add((class_uri, RDFS.label, Literal(state_class.get('label', ''))))

        # Add description
        if state_class.get('definition'):
            self.class_graph.add((class_uri, RDFS.comment, Literal(state_class['definition'])))

        # Add activation conditions
        for condition in state_class.get('activation_conditions', []):
            self.class_graph.add((
                class_uri,
                self.PROETHICA.hasActivationCondition,
                Literal(condition)
            ))

        # Add termination conditions (NEW)
        for condition in state_class.get('termination_conditions', []):
            self.class_graph.add((
                class_uri,
                self.PROETHICA.hasTerminationCondition,
                Literal(condition)
            ))

        # Add persistence type (inertial vs non-inertial)
        if state_class.get('persistence_type'):
            self.class_graph.add((
                class_uri,
                self.PROETHICA.hasPersistenceType,
                Literal(state_class['persistence_type'])
            ))

        # Add temporal properties (NEW)
        if state_class.get('temporal_properties'):
            self.class_graph.add((
                class_uri,
                self.PROETHICA.hasTemporalProperties,
                Literal(state_class['temporal_properties'])
            ))

        # Add domain context (NEW)
        if state_class.get('domain_context'):
            self.class_graph.add((
                class_uri,
                self.PROETHICA.hasDomainContext,
                Literal(state_class['domain_context'])
            ))

        # Add affected obligations
        for obligation in state_class.get('affected_obligations', []):
            self.class_graph.add((
                class_uri,
                self.PROETHICA.affectsObligation,
                Literal(obligation)
            ))

        # Add examples from case
        for example in state_class.get('examples_from_case', []):
            self.class_graph.add((
                class_uri,
                self.PROETHICA.hasExample,
                Literal(example)
            ))

        # Add provenance
        self.class_graph.add((class_uri, PROV.generatedAtTime, Literal(timestamp, datatype=XSD.dateTime)))
        self.class_graph.add((class_uri, self.PROETHICA_PROV.discoveredInCase, Literal(case_id, datatype=XSD.integer)))

        # Add confidence score
        if state_class.get('confidence'):
            self.class_graph.add((
                class_uri,
                self.PROETHICA_PROV.confidenceScore,
                Literal(state_class['confidence'], datatype=XSD.float)
            ))

    def _add_state_individual_to_graph(self, individual: Dict[str, Any], case_id: int, timestamp: datetime):
        """Add a state individual to the RDF graph with enhanced temporal and relational properties"""
        # Create URI for the individual
        identifier = individual.get('identifier', 'UnknownStateInstance')
        safe_identifier = identifier.replace(" ", "")
        case_namespace = Namespace(f"http://proethica.org/ontology/case/{case_id}#")
        individual_uri = URIRef(f"{case_namespace}{safe_identifier}")

        # Get the state class URI
        state_class_label = individual.get('state_class', 'State')
        safe_state_class = state_class_label.replace(" ", "")

        # Check if it's a new class or existing
        if individual.get('is_existing_class', True):
            state_class_uri = URIRef(f"{self.PROETHICA_INT}{safe_state_class}")
        else:
            state_class_uri = URIRef(f"{self.PROETHICA_INT}{safe_state_class}")

        # Add individual type assertion
        self.individual_graph.add((individual_uri, RDF.type, state_class_uri))
        self.individual_graph.add((individual_uri, RDFS.label, Literal(individual.get('identifier', ''))))

        # Add subject (WHO is in this state) - NEW
        if individual.get('subject'):
            self.individual_graph.add((
                individual_uri,
                self.PROETHICA.hasSubject,
                Literal(individual['subject'])
            ))

        # Add temporal properties - ENHANCED
        if individual.get('initiated_by'):
            self.individual_graph.add((
                individual_uri,
                self.PROETHICA.initiatedBy,
                Literal(individual['initiated_by'])
            ))

        if individual.get('initiated_at'):
            self.individual_graph.add((
                individual_uri,
                self.PROETHICA.initiatedAt,
                Literal(individual['initiated_at'])
            ))

        if individual.get('terminated_by'):
            self.individual_graph.add((
                individual_uri,
                self.PROETHICA.terminatedBy,
                Literal(individual['terminated_by'])
            ))

        if individual.get('terminated_at'):
            self.individual_graph.add((
                individual_uri,
                self.PROETHICA.terminatedAt,
                Literal(individual['terminated_at'])
            ))

        # Add active period for backwards compatibility
        if individual.get('active_period'):
            self.individual_graph.add((
                individual_uri,
                self.PROETHICA.hasActivePeriod,
                Literal(individual['active_period'])
            ))

        # Add urgency level - NEW
        if individual.get('urgency_level'):
            self.individual_graph.add((
                individual_uri,
                self.PROETHICA.hasUrgencyLevel,
                Literal(individual['urgency_level'])
            ))

        # Add affected obligations - NEW
        for obligation in individual.get('affects_obligations', []):
            self.individual_graph.add((
                individual_uri,
                self.PROETHICA.affectsObligation,
                Literal(obligation)
            ))

        # Add related parties
        related_parties = individual.get('related_parties', individual.get('affected_parties', []))
        if isinstance(related_parties, str):
            related_parties = [related_parties]
        elif not isinstance(related_parties, (list, tuple)):
            related_parties = [str(related_parties)] if related_parties else []

        for party in related_parties:
            self.individual_graph.add((
                individual_uri,
                self.PROETHICA.hasRelatedParty,
                Literal(party)
            ))

        # Add case involvement - NEW
        if individual.get('case_involvement'):
            self.individual_graph.add((
                individual_uri,
                self.PROETHICA.caseInvolvement,
                Literal(individual['case_involvement'])
            ))

        # Add case involvement
        if individual.get('case_involvement'):
            self.individual_graph.add((
                individual_uri,
                self.PROETHICA_PROV.caseInvolvement,
                Literal(individual['case_involvement'])
            ))

        # Add confidence
        if individual.get('confidence'):
            self.individual_graph.add((
                individual_uri,
                self.PROETHICA_PROV.confidenceScore,
                Literal(individual['confidence'], datatype=XSD.float)
            ))

        # Add provenance
        self.individual_graph.add((individual_uri, PROV.generatedAtTime, Literal(timestamp, datatype=XSD.dateTime)))

    def get_temporary_triples(self) -> Dict[str, Any]:
        """
        Get temporary triples organized for review.

        Returns:
            Dictionary with classes and individuals organized for review UI
        """
        result = {
            "new_classes": [],
            "new_individuals": [],
            "statistics": {
                "total_class_triples": len(self.class_graph),
                "total_individual_triples": len(self.individual_graph)
            }
        }

        # Extract classes
        for subj in self.class_graph.subjects(RDF.type, OWL.Class):
            class_info = {
                "uri": str(subj),
                "label": str(self.class_graph.value(subj, RDFS.label, default="")),
                "definition": str(self.class_graph.value(subj, RDFS.comment, default="")),
                "parent": str(self.class_graph.value(subj, RDFS.subClassOf, default="")),
                "properties": {}
            }

            # Collect all properties for this class
            for pred, obj in self.class_graph.predicate_objects(subj):
                if pred not in [RDF.type, RDFS.label, RDFS.comment, RDFS.subClassOf]:
                    pred_label = str(pred).split("#")[-1] if "#" in str(pred) else str(pred).split("/")[-1]
                    if pred_label not in class_info["properties"]:
                        class_info["properties"][pred_label] = []
                    class_info["properties"][pred_label].append(str(obj))

            result["new_classes"].append(class_info)

        # Extract individuals
        for subj in self.individual_graph.subjects(RDF.type, OWL.NamedIndividual):
            indiv_info = {
                "uri": str(subj),
                "label": str(self.individual_graph.value(subj, RDFS.label, default="")),
                "types": [],
                "properties": {},
                "relationships": []
            }

            # Get all types (excluding NamedIndividual)
            for type_uri in self.individual_graph.objects(subj, RDF.type):
                if type_uri != OWL.NamedIndividual:
                    indiv_info["types"].append(str(type_uri))

            # Collect all properties and relationships
            for pred, obj in self.individual_graph.predicate_objects(subj):
                if pred not in [RDF.type, RDFS.label]:
                    pred_label = str(pred).split("#")[-1] if "#" in str(pred) else str(pred).split("/")[-1]

                    # Check if it's a relationship (object property) or attribute (data property)
                    if isinstance(obj, URIRef) and (obj, RDF.type, OWL.NamedIndividual) in self.individual_graph:
                        # It's a relationship to another individual
                        target_label = str(self.individual_graph.value(obj, RDFS.label, default=str(obj)))
                        indiv_info["relationships"].append({
                            "type": pred_label,
                            "target": target_label,
                            "target_uri": str(obj)
                        })
                    else:
                        # It's a data property
                        if pred_label not in indiv_info["properties"]:
                            indiv_info["properties"][pred_label] = []
                        indiv_info["properties"][pred_label].append(str(obj))

            result["new_individuals"].append(indiv_info)

        return result