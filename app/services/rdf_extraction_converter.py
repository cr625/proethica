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