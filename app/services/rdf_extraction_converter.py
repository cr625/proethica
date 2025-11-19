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
                                 extraction_timestamp: Optional[datetime] = None,
                                 section_type: str = None,
                                 pass_number: int = None) -> Tuple[Graph, Graph]:
        """
        Convert complete LLM extraction result to RDF triples.

        Args:
            extraction_result: Raw LLM extraction result containing new_role_classes and role_individuals
            case_id: ID of the case this extraction is from
            extraction_timestamp: When the extraction occurred
            section_type: Section where entities were discovered (facts, discussion, questions, conclusions)
            pass_number: Extraction pass number (1, 2, or 3)

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
            self._convert_role_classes(extraction_result["new_role_classes"], case_id, extraction_timestamp,
                                     section_type, pass_number)

        # Process role individuals
        if "role_individuals" in extraction_result:
            self._convert_role_individuals(extraction_result["role_individuals"], case_id, case_ns, extraction_timestamp)

        return self.class_graph, self.individual_graph

    def _convert_role_classes(self, role_classes: List[Dict], case_id: int, timestamp: datetime,
                             section_type: str = None, pass_number: int = None):
        """Convert new role classes to RDF triples for proethica-intermediate with full provenance"""

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

            # Add comprehensive provenance (Phase 1 Architecture)
            # Standard W3C PROV-O properties
            self.class_graph.add((class_uri, PROV.generatedAtTime, Literal(timestamp, datatype=XSD.dateTime)))
            self.class_graph.add((class_uri, PROV.wasAttributedTo, Literal(f"Case {case_id} Extraction")))

            # ProEthica-specific provenance
            self.class_graph.add((class_uri, self.PROETHICA_PROV.firstDiscoveredInCase, Literal(case_id, datatype=XSD.integer)))
            self.class_graph.add((class_uri, self.PROETHICA_PROV.firstDiscoveredAt, Literal(timestamp, datatype=XSD.dateTime)))
            self.class_graph.add((class_uri, self.PROETHICA_PROV.discoveredInCase, Literal(case_id, datatype=XSD.integer)))

            if section_type:
                self.class_graph.add((class_uri, self.PROETHICA_PROV.discoveredInSection, Literal(section_type)))

            if pass_number:
                self.class_graph.add((class_uri, self.PROETHICA_PROV.discoveredInPass, Literal(pass_number, datatype=XSD.integer)))

            # Add source text (exact quote from case)
            if "source_text" in role_class and role_class["source_text"]:
                self.class_graph.add((class_uri, self.PROETHICA_PROV.sourceText, Literal(role_class["source_text"])))

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

            # Add source text (provenance)
            if "source_text" in individual and individual["source_text"]:
                self.individual_graph.add((individual_uri, self.PROETHICA_PROV.sourceText,
                                         Literal(individual["source_text"])))

            # Add active obligations (NEW)
            if "active_obligations" in individual and individual["active_obligations"] is not None:
                # Ensure it's a list, not a string
                obligations = individual["active_obligations"]
                if isinstance(obligations, str):
                    obligations = [obligations]
                for obligation in obligations:
                    self.individual_graph.add((individual_uri, self.PROETHICA.hasActiveObligation,
                                             Literal(obligation)))

            # Add ethical tensions (NEW)
            if "ethical_tensions" in individual and individual["ethical_tensions"] is not None:
                # Ensure it's a list, not a string
                tensions = individual["ethical_tensions"]
                if isinstance(tensions, str):
                    tensions = [tensions]
                for tension in tensions:
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
                                        extraction_timestamp: Optional[datetime] = None,
                                        section_type: str = None,
                                        pass_number: int = None) -> Tuple[Graph, Graph]:
        """
        Convert states extraction result to RDF triples with provenance.

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
            self._add_state_class_to_graph(state_class, case_id, timestamp, section_type, pass_number)

        # Process state individuals
        for individual in extraction_result.get('state_individuals', []):
            self._add_state_individual_to_graph(individual, case_id, timestamp)

        return self.class_graph, self.individual_graph

    def _add_state_class_to_graph(self, state_class: Dict[str, Any], case_id: int, timestamp: datetime,
                                  section_type: str = None, pass_number: int = None):
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

        # Add comprehensive provenance (Phase 1 Architecture)
        # Standard W3C PROV-O properties
        self.class_graph.add((class_uri, PROV.generatedAtTime, Literal(timestamp, datatype=XSD.dateTime)))
        self.class_graph.add((class_uri, PROV.wasAttributedTo, Literal(f"Case {case_id} Extraction")))

        # ProEthica-specific provenance
        self.class_graph.add((class_uri, self.PROETHICA_PROV.firstDiscoveredInCase, Literal(case_id, datatype=XSD.integer)))
        self.class_graph.add((class_uri, self.PROETHICA_PROV.firstDiscoveredAt, Literal(timestamp, datatype=XSD.dateTime)))
        self.class_graph.add((class_uri, self.PROETHICA_PROV.discoveredInCase, Literal(case_id, datatype=XSD.integer)))

        if section_type:
            self.class_graph.add((class_uri, self.PROETHICA_PROV.discoveredInSection, Literal(section_type)))

        if pass_number:
            self.class_graph.add((class_uri, self.PROETHICA_PROV.discoveredInPass, Literal(pass_number, datatype=XSD.integer)))

        # Add source text (exact quote from case)
        if state_class.get('source_text') and state_class['source_text']:
            self.class_graph.add((class_uri, self.PROETHICA_PROV.sourceText, Literal(state_class['source_text'])))

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

        # Add individual type assertions - MUST include NamedIndividual for extraction
        self.individual_graph.add((individual_uri, RDF.type, OWL.NamedIndividual))
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

        # Add source text (provenance)
        if individual.get('source_text') and individual['source_text']:
            self.individual_graph.add((individual_uri, self.PROETHICA_PROV.sourceText, Literal(individual['source_text'])))

        # Add provenance
        self.individual_graph.add((individual_uri, PROV.generatedAtTime, Literal(timestamp, datatype=XSD.dateTime)))

    def convert_resources_extraction_to_rdf(self,
                                           extraction_result: Dict[str, Any],
                                           case_id: int,
                                           extraction_timestamp: Optional[datetime] = None,
                                           section_type: str = None,
                                           pass_number: int = None) -> Tuple[Graph, Graph]:
        """
        Convert resources extraction result to RDF triples with provenance.

        Args:
            extraction_result: Raw LLM extraction result containing new_resource_classes and resource_individuals
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

        # Process new resource classes
        for resource_class in extraction_result.get('new_resource_classes', []):
            self._add_resource_class_to_graph(resource_class, case_id, timestamp, section_type, pass_number)

        # Process resource individuals
        for individual in extraction_result.get('resource_individuals', []):
            self._add_resource_individual_to_graph(individual, case_id, timestamp)

        return self.class_graph, self.individual_graph

    def _add_resource_class_to_graph(self, resource_class: Dict[str, Any], case_id: int, timestamp: datetime,
                                     section_type: str = None, pass_number: int = None):
        """Add a new resource class to the RDF graph with full provenance"""
        # Create URI for the resource class
        class_label = resource_class.get('label', 'UnknownResource')
        safe_label = class_label.replace(" ", "")
        class_uri = URIRef(f"{self.PROETHICA_INT}{safe_label}")

        # Add class type and label
        self.class_graph.add((class_uri, RDF.type, OWL.Class))
        self.class_graph.add((class_uri, RDFS.label, Literal(class_label)))

        # Add parent class (subClassOf Resource)
        self.class_graph.add((class_uri, RDFS.subClassOf, self.PROETHICA.Resource))

        # Add definition
        if resource_class.get('definition'):
            self.class_graph.add((class_uri, RDFS.comment, Literal(resource_class['definition'])))

        # Add resource-specific properties in OWL-compliant format
        if resource_class.get('resource_type'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA}hasResourceType"),
                Literal(resource_class['resource_type'])
            ))

        if resource_class.get('accessibility'):
            for access_level in resource_class.get('accessibility', []):
                self.class_graph.add((
                    class_uri,
                    URIRef(f"{self.PROETHICA}hasAccessibility"),
                    Literal(access_level)
                ))

        if resource_class.get('authority_source'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA}hasAuthoritySource"),
                Literal(resource_class['authority_source'])
            ))

        if resource_class.get('typical_usage'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA}hasTypicalUsage"),
                Literal(resource_class['typical_usage'])
            ))

        if resource_class.get('domain_context'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA}hasDomainContext"),
                Literal(resource_class['domain_context'])
            ))

        # Add comprehensive provenance (Phase 1 Architecture)
        # Standard W3C PROV-O properties
        self.class_graph.add((class_uri, PROV.generatedAtTime, Literal(timestamp, datatype=XSD.dateTime)))
        self.class_graph.add((class_uri, PROV.wasAttributedTo, Literal(f"Case {case_id} Extraction")))

        # ProEthica-specific provenance
        self.class_graph.add((class_uri, self.PROETHICA_PROV.firstDiscoveredInCase, Literal(case_id, datatype=XSD.integer)))
        self.class_graph.add((class_uri, self.PROETHICA_PROV.firstDiscoveredAt, Literal(timestamp, datatype=XSD.dateTime)))
        self.class_graph.add((class_uri, self.PROETHICA_PROV.discoveredInCase, Literal(case_id, datatype=XSD.integer)))

        if section_type:
            self.class_graph.add((class_uri, self.PROETHICA_PROV.discoveredInSection, Literal(section_type)))

        if pass_number:
            self.class_graph.add((class_uri, self.PROETHICA_PROV.discoveredInPass, Literal(pass_number, datatype=XSD.integer)))

        # Add source text (exact quote from case)
        if resource_class.get('source_text') and resource_class['source_text']:
            self.class_graph.add((class_uri, self.PROETHICA_PROV.sourceText, Literal(resource_class['source_text'])))

        # Add confidence score if available
        if resource_class.get('confidence'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA_PROV}confidenceScore"),
                Literal(resource_class['confidence'], datatype=XSD.float)
            ))

    def _add_resource_individual_to_graph(self, individual: Dict[str, Any], case_id: int, timestamp: datetime):
        """Add a resource individual to the RDF graph"""
        # Create URI for the individual
        identifier = individual.get('identifier', 'UnknownResourceInstance')
        safe_identifier = identifier.replace(" ", "")
        case_namespace = Namespace(f"http://proethica.org/ontology/case/{case_id}#")
        individual_uri = URIRef(f"{case_namespace}{safe_identifier}")

        # Get the resource class URI
        resource_class_label = individual.get('resource_class', 'Resource')
        safe_resource_class = resource_class_label.replace(" ", "")

        # Check if it's a new class or existing
        if individual.get('is_existing_class', True):
            resource_class_uri = URIRef(f"{self.PROETHICA_INT}{safe_resource_class}")
        else:
            resource_class_uri = URIRef(f"{self.PROETHICA_INT}{safe_resource_class}")

        # Add individual type assertions - MUST include NamedIndividual for extraction
        self.individual_graph.add((individual_uri, RDF.type, OWL.NamedIndividual))
        self.individual_graph.add((individual_uri, RDF.type, resource_class_uri))
        self.individual_graph.add((individual_uri, RDFS.label, Literal(individual.get('identifier', ''))))

        # Add document metadata
        if individual.get('document_title'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA}hasDocumentTitle"),
                Literal(individual['document_title'])
            ))

        if individual.get('created_by'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA}createdBy"),
                Literal(individual['created_by'])
            ))

        if individual.get('created_at'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA}createdAt"),
                Literal(individual['created_at'])
            ))

        if individual.get('version'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA}hasVersion"),
                Literal(individual['version'])
            ))

        if individual.get('url_or_location'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA}hasLocation"),
                Literal(individual['url_or_location'])
            ))

        # Add usage context
        if individual.get('used_by'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA}usedBy"),
                Literal(individual['used_by'])
            ))

        if individual.get('used_in_context'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA}usedInContext"),
                Literal(individual['used_in_context'])
            ))

        # Add case section
        if individual.get('case_section'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA}inCaseSection"),
                Literal(individual['case_section'])
            ))

        # Add confidence
        if individual.get('confidence'):
            self.individual_graph.add((
                individual_uri,
                self.PROETHICA_PROV.confidenceScore,
                Literal(individual['confidence'], datatype=XSD.float)
            ))

        # Add source text (provenance)
        if individual.get('source_text') and individual['source_text']:
            self.individual_graph.add((individual_uri, self.PROETHICA_PROV.sourceText, Literal(individual['source_text'])))

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

            # Extract source text for top-level access (provenance)
            source_text_value = self.class_graph.value(subj, self.PROETHICA_PROV.sourceText)
            if source_text_value:
                class_info["source_text"] = str(source_text_value)

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

            # Extract source text for top-level access (provenance)
            source_text_value = self.individual_graph.value(subj, self.PROETHICA_PROV.sourceText)
            if source_text_value:
                indiv_info["source_text"] = str(source_text_value)

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

    def convert_principles_extraction_to_rdf(self,
                                            extraction_result: Dict[str, Any],
                                            case_id: int,
                                            extraction_timestamp: Optional[datetime] = None) -> Tuple[Graph, Graph]:
        """
        Convert principles extraction result to RDF triples.

        Based on Chapter 2.2.2 literature:
        - Principles are abstract ethical foundations requiring extensional definition
        - They function like constitutional principles requiring interpretation
        - They mediate moral ideals into concrete reality

        Args:
            extraction_result: Raw LLM extraction with new_principle_classes and principle_individuals
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

        # Process new principle classes
        for principle_class in extraction_result.get('new_principle_classes', []):
            self._add_principle_class_to_graph(principle_class, case_id, timestamp)

        # Process principle individuals
        for individual in extraction_result.get('principle_individuals', []):
            self._add_principle_individual_to_graph(individual, case_id, timestamp)

        return self.class_graph, self.individual_graph

    def _add_principle_class_to_graph(self, principle_class: Dict[str, Any], case_id: int, timestamp: datetime):
        """Add a new principle class to the RDF graph"""
        # Create URI for the principle class
        class_label = principle_class.get('label', 'UnknownPrinciple')
        safe_label = class_label.replace(" ", "")
        class_uri = URIRef(f"{self.PROETHICA_INT}{safe_label}")

        # Add class type and label
        self.class_graph.add((class_uri, RDF.type, OWL.Class))
        self.class_graph.add((class_uri, RDFS.label, Literal(class_label)))

        # Add parent class (subClassOf Principle)
        self.class_graph.add((class_uri, RDFS.subClassOf, self.PROETHICA.Principle))

        # Add definition
        if principle_class.get('definition'):
            self.class_graph.add((class_uri, RDFS.comment, Literal(principle_class['definition'])))

        # Add principle-specific properties
        if principle_class.get('abstract_nature'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA}hasAbstractNature"),
                Literal(principle_class['abstract_nature'])
            ))

        if principle_class.get('value_basis'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA}hasValueBasis"),
                Literal(principle_class['value_basis'])
            ))

        if principle_class.get('operationalization'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA}hasOperationalization"),
                Literal(principle_class['operationalization'])
            ))

        # Add extensional examples (key for principles per McLaren)
        for example in principle_class.get('extensional_examples', []):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA}hasExtensionalExample"),
                Literal(example)
            ))

        # Add application contexts
        for context in principle_class.get('application_context', []):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA}hasApplicationContext"),
                Literal(context)
            ))

        # Add balancing requirements (principles often conflict)
        for req in principle_class.get('balancing_requirements', []):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA}requiresBalancingWith"),
                Literal(req)
            ))

        # Add extraction metadata
        self.class_graph.add((
            class_uri,
            URIRef(f"{self.PROETHICA_PROV}discoveredInCase"),
            Literal(case_id, datatype=XSD.integer)
        ))

        if principle_class.get('confidence'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA_PROV}confidenceScore"),
                Literal(principle_class['confidence'], datatype=XSD.float)
            ))

        # Add source text (provenance)
        if principle_class.get('source_text') and principle_class['source_text']:
            self.class_graph.add((class_uri, self.PROETHICA_PROV.sourceText, Literal(principle_class['source_text'])))

        # Add provenance
        self.class_graph.add((class_uri, PROV.wasGeneratedBy, Literal("ProEthica Dual Principles Extraction")))
        self.class_graph.add((class_uri, PROV.generatedAtTime, Literal(timestamp, datatype=XSD.dateTime)))

    def _add_principle_individual_to_graph(self, individual: Dict[str, Any], case_id: int, timestamp: datetime):
        """Add a principle individual (specific instance) to the RDF graph"""
        # Create URI for the individual
        identifier = individual.get('identifier', f'Principle_{case_id}_{uuid.uuid4().hex[:8]}')
        safe_identifier = identifier.replace(" ", "")
        individual_uri = URIRef(f"http://proethica.org/ontology/case/{case_id}#{safe_identifier}")

        # Add individual type
        self.individual_graph.add((individual_uri, RDF.type, OWL.NamedIndividual))

        # Link to principle class
        principle_class = individual.get('principle_class', 'Principle')
        # Always use the proethica-intermediate namespace for principle classes
        safe_class = principle_class.replace(" ", "")
        class_uri = URIRef(f"{self.PROETHICA_INT}{safe_class}")

        self.individual_graph.add((individual_uri, RDF.type, class_uri))
        self.individual_graph.add((individual_uri, RDFS.label, Literal(identifier)))

        # Add concrete expression (how principle is stated in case)
        if individual.get('concrete_expression'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA}hasConcreteExpression"),
                Literal(individual['concrete_expression'])
            ))

        # Add who invokes the principle
        for invoker in individual.get('invoked_by', []):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA}invokedBy"),
                Literal(invoker)
            ))

        # Add what the principle applies to
        for application in individual.get('applied_to', []):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA}appliedTo"),
                Literal(application)
            ))

        # Add interpretation (context-specific)
        if individual.get('interpretation'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA}hasInterpretation"),
                Literal(individual['interpretation'])
            ))

        # Add principles it must be balanced with
        for other_principle in individual.get('balancing_with', []):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA}balancedWith"),
                Literal(other_principle)
            ))

        # Add tension resolution
        if individual.get('tension_resolution'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA}hasTensionResolution"),
                Literal(individual['tension_resolution'])
            ))

        # Add case relevance
        if individual.get('case_relevance'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA}hasCaseRelevance"),
                Literal(individual['case_relevance'])
            ))

        # Add case section
        if individual.get('case_section'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA_CASES}inSection"),
                Literal(individual['case_section'])
            ))

        # Add confidence
        if individual.get('confidence'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA_PROV}confidenceScore"),
                Literal(individual['confidence'], datatype=XSD.float)
            ))

        # Add source text (provenance)
        if individual.get('source_text') and individual['source_text']:
            self.individual_graph.add((individual_uri, self.PROETHICA_PROV.sourceText, Literal(individual['source_text'])))

        # Add provenance
        self.individual_graph.add((individual_uri, PROV.wasGeneratedBy, Literal("ProEthica Dual Principles Extraction")))
        self.individual_graph.add((individual_uri, PROV.generatedAtTime, Literal(timestamp, datatype=XSD.dateTime)))

    def convert_obligations_extraction_to_rdf(self,
                                             extraction_result: Dict[str, Any],
                                             case_id: int,
                                             extraction_timestamp: Optional[datetime] = None) -> Tuple[Graph, Graph]:
        """
        Convert obligations extraction result to RDF triples.

        Based on Chapter 2.2.3 literature:
        - Obligations are concrete professional duties derived from principles
        - They specify what professionals MUST, SHOULD, or MUST NOT do
        - They have deontic force and are enforceable

        Args:
            extraction_result: Raw LLM extraction with new_obligation_classes and obligation_individuals
            case_id: ID of the case this extraction is from
            extraction_timestamp: When the extraction occurred

        Returns:
            Tuple of (class_graph, individual_graph)
        """
        timestamp = extraction_timestamp or datetime.utcnow()

        # Clear and initialize graphs
        self.class_graph = Graph()
        self.individual_graph = Graph()
        self._bind_prefixes()

        # Clear temporary triples storage
        self.new_classes = []
        self.new_individuals = []

        # Process new obligation classes
        for obligation_class in extraction_result.get('new_obligation_classes', []):
            self._add_obligation_class_to_graph(obligation_class, case_id, timestamp)

        # Process obligation individuals
        for individual in extraction_result.get('obligation_individuals', []):
            self._add_obligation_individual_to_graph(individual, case_id, timestamp)

        return self.class_graph, self.individual_graph

    def _add_obligation_class_to_graph(self, obligation_class: Dict[str, Any], case_id: int, timestamp: datetime):
        """Add a new obligation class to the RDF graph"""
        # Create URI for the new class
        safe_label = obligation_class['label'].replace(" ", "")
        class_uri = URIRef(f"{self.PROETHICA_INT}{safe_label}")

        # Add class definition
        self.class_graph.add((class_uri, RDF.type, OWL.Class))

        # Make it a subclass of Obligation
        base_obligation_uri = URIRef(f"{self.PROETHICA}Obligation")
        self.class_graph.add((class_uri, RDFS.subClassOf, base_obligation_uri))

        # Add label and definition
        self.class_graph.add((class_uri, RDFS.label, Literal(obligation_class['label'])))
        if obligation_class.get('definition'):
            self.class_graph.add((class_uri, RDFS.comment, Literal(obligation_class['definition'])))

        # Add obligation-specific properties
        if obligation_class.get('derived_from_principle'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA_INT}derivedFromPrinciple"),
                Literal(obligation_class['derived_from_principle'])
            ))

        if obligation_class.get('duty_type'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA_INT}dutyType"),
                Literal(obligation_class['duty_type'])
            ))

        if obligation_class.get('enforcement_mechanism'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA_INT}enforcementMechanism"),
                Literal(obligation_class['enforcement_mechanism'])
            ))

        if obligation_class.get('violation_consequences'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA_INT}violationConsequences"),
                Literal(obligation_class['violation_consequences'])
            ))

        # Add examples from case
        for example in obligation_class.get('examples_from_case', []):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA_INT}exampleFromCase"),
                Literal(example)
            ))

        # Add confidence and reasoning
        if obligation_class.get('confidence'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA_PROV}confidenceScore"),
                Literal(obligation_class['confidence'], datatype=XSD.float)
            ))

        if obligation_class.get('reasoning'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA_INT}extractionReasoning"),
                Literal(obligation_class['reasoning'])
            ))

        # Add source text (provenance)
        if obligation_class.get('source_text') and obligation_class['source_text']:
            self.class_graph.add((class_uri, self.PROETHICA_PROV.sourceText, Literal(obligation_class['source_text'])))

        # Add provenance
        self.class_graph.add((class_uri, PROV.wasGeneratedBy, Literal("ProEthica Dual Obligations Extraction")))
        self.class_graph.add((class_uri, PROV.generatedAtTime, Literal(timestamp, datatype=XSD.dateTime)))

        # Store for temporary storage
        self.new_classes.append({
            'uri': str(class_uri),
            'label': obligation_class['label'],
            'definition': obligation_class.get('definition', ''),
            'properties': {
                'derived_from_principle': obligation_class.get('derived_from_principle'),
                'duty_type': obligation_class.get('duty_type'),
                'enforcement_mechanism': obligation_class.get('enforcement_mechanism'),
                'violation_consequences': obligation_class.get('violation_consequences'),
                'examples': obligation_class.get('examples_from_case', [])
            }
        })

    def _add_obligation_individual_to_graph(self, individual: Dict[str, Any], case_id: int, timestamp: datetime):
        """Add an obligation individual to the RDF graph"""
        # Create URI for the individual
        safe_identifier = individual.get('identifier', 'UnknownObligation').replace(" ", "_")
        section_type = individual.get('case_context', 'discussion').split()[0].lower()
        individual_uri = URIRef(f"http://proethica.org/ontology/case/{case_id}#{safe_identifier}_{section_type.title()}")

        # Add individual type assertions
        self.individual_graph.add((individual_uri, RDF.type, OWL.NamedIndividual))

        # Link to obligation class (existing or new)
        obligation_class = individual.get('obligation_class', 'Obligation')
        safe_class = obligation_class.replace(" ", "")

        if individual.get('is_existing_class', False):
            # Link to existing class
            class_uri = URIRef(f"{self.PROETHICA_INT}{safe_class}")
        else:
            # Link to new class
            class_uri = URIRef(f"{self.PROETHICA_INT}{safe_class}")

        self.individual_graph.add((individual_uri, RDF.type, class_uri))

        # Add label
        self.individual_graph.add((individual_uri, RDFS.label, Literal(individual.get('identifier', 'Unknown Obligation'))))

        # Add obligation-specific properties
        if individual.get('obligated_party'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA_CASES}obligatedParty"),
                Literal(individual['obligated_party'])
            ))

        if individual.get('obligation_statement'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA_CASES}obligationStatement"),
                Literal(individual['obligation_statement'])
            ))

        if individual.get('derived_from'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA_CASES}derivedFrom"),
                Literal(individual['derived_from'])
            ))

        if individual.get('enforcement_context'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA_CASES}enforcementContext"),
                Literal(individual['enforcement_context'])
            ))

        if individual.get('temporal_scope'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA_CASES}temporalScope"),
                Literal(individual['temporal_scope'])
            ))

        if individual.get('compliance_status'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA_CASES}complianceStatus"),
                Literal(individual['compliance_status'])
            ))

        if individual.get('case_context'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA_CASES}caseContext"),
                Literal(individual['case_context'])
            ))

        # Add confidence
        if individual.get('confidence'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA_PROV}confidenceScore"),
                Literal(individual['confidence'], datatype=XSD.float)
            ))

        # Add source text (provenance)
        if individual.get('source_text') and individual['source_text']:
            self.individual_graph.add((individual_uri, self.PROETHICA_PROV.sourceText, Literal(individual['source_text'])))

        # Add provenance
        self.individual_graph.add((individual_uri, PROV.wasGeneratedBy, Literal("ProEthica Dual Obligations Extraction")))
        self.individual_graph.add((individual_uri, PROV.generatedAtTime, Literal(timestamp, datatype=XSD.dateTime)))

        # Store for temporary storage
        self.new_individuals.append({
            'uri': str(individual_uri),
            'label': individual.get('identifier', 'Unknown Obligation'),
            'type': obligation_class,
            'properties': {
                'obligated_party': individual.get('obligated_party'),
                'obligation_statement': individual.get('obligation_statement'),
                'derived_from': individual.get('derived_from'),
                'enforcement_context': individual.get('enforcement_context'),
                'temporal_scope': individual.get('temporal_scope'),
                'compliance_status': individual.get('compliance_status'),
                'case_context': individual.get('case_context')
            },
            'relationships': []
        })

    def convert_constraints_extraction_to_rdf(self,
                                             extraction_result: Dict[str, Any],
                                             case_id: int,
                                             extraction_timestamp: Optional[datetime] = None) -> Tuple[Graph, Graph]:
        """
        Convert constraints extraction result to RDF triples.

        Based on literature:
        - Constraints are inviolable boundaries that limit acceptable actions
        - They differ from obligations by being restrictions rather than requirements
        - They define the space within which ethical decisions must be made

        Args:
            extraction_result: Raw LLM extraction with new_constraint_classes and constraint_individuals
            case_id: ID of the case this extraction is from
            extraction_timestamp: When the extraction occurred

        Returns:
            Tuple of (class_graph, individual_graph)
        """
        timestamp = extraction_timestamp or datetime.utcnow()

        # Clear and initialize graphs
        self.class_graph = Graph()
        self.individual_graph = Graph()
        self._bind_prefixes()

        # Clear temporary triples storage
        self.new_classes = []
        self.new_individuals = []

        # Process new constraint classes
        for constraint_class in extraction_result.get('new_constraint_classes', []):
            self._add_constraint_class_to_graph(constraint_class, case_id, timestamp)

        # Process constraint individuals
        for individual in extraction_result.get('constraint_individuals', []):
            self._add_constraint_individual_to_graph(individual, case_id, timestamp)

        return self.class_graph, self.individual_graph

    def _add_constraint_class_to_graph(self, constraint_class: Dict[str, Any], case_id: int, timestamp: datetime):
        """Add a new constraint class to the RDF graph"""
        # Create URI for the new class
        safe_label = constraint_class['label'].replace(" ", "")
        class_uri = URIRef(f"{self.PROETHICA_INT}{safe_label}")

        # Add class definition
        self.class_graph.add((class_uri, RDF.type, OWL.Class))

        # Make it a subclass of Constraint
        base_constraint_uri = URIRef(f"{self.PROETHICA}Constraint")
        self.class_graph.add((class_uri, RDFS.subClassOf, base_constraint_uri))

        # Add label and definition
        self.class_graph.add((class_uri, RDFS.label, Literal(constraint_class['label'])))
        if constraint_class.get('definition'):
            self.class_graph.add((class_uri, RDFS.comment, Literal(constraint_class['definition'])))

        # Add constraint-specific properties
        if constraint_class.get('constraint_type'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA_INT}constraintType"),
                Literal(constraint_class['constraint_type'])
            ))

        if constraint_class.get('flexibility'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA_INT}flexibility"),
                Literal(constraint_class['flexibility'])
            ))

        if constraint_class.get('violation_impact'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA_INT}violationImpact"),
                Literal(constraint_class['violation_impact'])
            ))

        if constraint_class.get('mitigation_possible'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA_INT}mitigationPossible"),
                Literal(constraint_class['mitigation_possible'])
            ))

        # Add examples from case
        for example in constraint_class.get('examples_from_case', []):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA_INT}exampleFromCase"),
                Literal(example)
            ))

        # Add confidence and reasoning
        if constraint_class.get('confidence'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA_PROV}confidenceScore"),
                Literal(constraint_class['confidence'], datatype=XSD.float)
            ))

        if constraint_class.get('reasoning'):
            self.class_graph.add((
                class_uri,
                URIRef(f"{self.PROETHICA_INT}extractionReasoning"),
                Literal(constraint_class['reasoning'])
            ))

        # Add source text (provenance)
        if constraint_class.get('source_text') and constraint_class['source_text']:
            self.class_graph.add((class_uri, self.PROETHICA_PROV.sourceText, Literal(constraint_class['source_text'])))

        # Add provenance
        self.class_graph.add((class_uri, PROV.wasGeneratedBy, Literal("ProEthica Dual Constraints Extraction")))
        self.class_graph.add((class_uri, PROV.generatedAtTime, Literal(timestamp, datatype=XSD.dateTime)))

        # Store for temporary storage
        self.new_classes.append({
            'uri': str(class_uri),
            'label': constraint_class['label'],
            'definition': constraint_class.get('definition', ''),
            'properties': {
                'constraint_type': constraint_class.get('constraint_type'),
                'flexibility': constraint_class.get('flexibility'),
                'violation_impact': constraint_class.get('violation_impact'),
                'mitigation_possible': constraint_class.get('mitigation_possible'),
                'examples': constraint_class.get('examples_from_case', [])
            }
        })

    def _add_constraint_individual_to_graph(self, individual: Dict[str, Any], case_id: int, timestamp: datetime):
        """Add a constraint individual to the RDF graph"""
        # Create URI for the individual
        safe_identifier = individual.get('identifier', 'UnknownConstraint').replace(" ", "_")
        section_type = individual.get('case_context', 'discussion').split()[0].lower()
        individual_uri = URIRef(f"http://proethica.org/ontology/case/{case_id}#{safe_identifier}_{section_type.title()}")

        # Add individual type assertions
        self.individual_graph.add((individual_uri, RDF.type, OWL.NamedIndividual))

        # Link to constraint class (existing or new)
        constraint_class = individual.get('constraint_class', 'Constraint')
        safe_class = constraint_class.replace(" ", "")

        if individual.get('is_existing_class', False):
            # Link to existing class
            class_uri = URIRef(f"{self.PROETHICA_INT}{safe_class}")
        else:
            # Link to new class
            class_uri = URIRef(f"{self.PROETHICA_INT}{safe_class}")

        self.individual_graph.add((individual_uri, RDF.type, class_uri))

        # Add label
        self.individual_graph.add((individual_uri, RDFS.label, Literal(individual.get('identifier', 'Unknown Constraint'))))

        # Add constraint-specific properties
        if individual.get('constrained_entity'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA_CASES}constrainedEntity"),
                Literal(individual['constrained_entity'])
            ))

        if individual.get('constraint_statement'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA_CASES}constraintStatement"),
                Literal(individual['constraint_statement'])
            ))

        if individual.get('source'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA_CASES}constraintSource"),
                Literal(individual['source'])
            ))

        if individual.get('enforcement_mechanism'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA_CASES}enforcementMechanism"),
                Literal(individual['enforcement_mechanism'])
            ))

        if individual.get('temporal_scope'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA_CASES}temporalScope"),
                Literal(individual['temporal_scope'])
            ))

        if individual.get('severity'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA_CASES}severity"),
                Literal(individual['severity'])
            ))

        if individual.get('case_context'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA_CASES}caseContext"),
                Literal(individual['case_context'])
            ))

        # Add confidence
        if individual.get('confidence'):
            self.individual_graph.add((
                individual_uri,
                URIRef(f"{self.PROETHICA_PROV}confidenceScore"),
                Literal(individual['confidence'], datatype=XSD.float)
            ))

        # Add source text (provenance)
        if individual.get('source_text') and individual['source_text']:
            self.individual_graph.add((individual_uri, self.PROETHICA_PROV.sourceText, Literal(individual['source_text'])))

        # Add provenance
        self.individual_graph.add((individual_uri, PROV.wasGeneratedBy, Literal("ProEthica Dual Constraints Extraction")))
        self.individual_graph.add((individual_uri, PROV.generatedAtTime, Literal(timestamp, datatype=XSD.dateTime)))

        # Store for temporary storage
        self.new_individuals.append({
            'uri': str(individual_uri),
            'label': individual.get('identifier', 'Unknown Constraint'),
            'type': constraint_class,
            'properties': {
                'constrained_entity': individual.get('constrained_entity'),
                'constraint_statement': individual.get('constraint_statement'),
                'source': individual.get('source'),
                'enforcement_mechanism': individual.get('enforcement_mechanism'),
                'temporal_scope': individual.get('temporal_scope'),
                'severity': individual.get('severity'),
                'case_context': individual.get('case_context')
            },
            'relationships': []
        })

    def convert_capabilities_extraction_to_rdf(self,
                                              extraction_result: Dict[str, Any],
                                              case_id: int,
                                              extraction_timestamp: Optional[datetime] = None) -> Tuple[Graph, Graph]:
        """
        Convert dual capabilities extraction to RDF format.

        Args:
            extraction_result: Dictionary containing 'new_capability_classes' and 'capability_individuals'
            case_id: The case identifier
            extraction_timestamp: Optional timestamp for extraction

        Returns:
            Tuple of (class_graph, individual_graph) for capabilities
        """
        logger.info(f"Converting capabilities extraction to RDF for case {case_id}")

        # Clear the graphs for new conversion
        self.class_graph = Graph()
        self.individual_graph = Graph()
        self._bind_prefixes()

        # Initialize temporary structure for storage
        self.temporary_triples = {'classes': [], 'individuals': []}

        timestamp = extraction_timestamp or datetime.utcnow()

        # Process new capability classes
        for capability_class in extraction_result.get('new_capability_classes', []):
            self._add_capability_class_to_graph(capability_class, case_id, timestamp)

        # Process capability individuals
        for individual in extraction_result.get('capability_individuals', []):
            self._add_capability_individual_to_graph(individual, case_id, timestamp)

        # Store in temporary structure for display
        for capability_class in extraction_result.get('new_capability_classes', []):
            self.temporary_triples['classes'].append({
                'uri': f"{self.PROETHICA}{capability_class.get('label', '').replace(' ', '')}",
                'type': 'capability_class',
                'label': capability_class.get('label'),
                'properties': {
                    'definition': capability_class.get('definition'),
                    'capability_type': capability_class.get('capability_type'),
                    'norm_competence_related': capability_class.get('norm_competence_related'),
                    'skill_level': capability_class.get('skill_level'),
                    'acquisition_method': capability_class.get('acquisition_method'),
                    'examples_from_case': capability_class.get('examples_from_case', []),
                    'confidence': capability_class.get('confidence'),
                    'reasoning': capability_class.get('reasoning')
                },
                'relationships': []
            })

        for individual in extraction_result.get('capability_individuals', []):
            self.temporary_triples['individuals'].append({
                'uri': f"http://proethica.org/ontology/case/{case_id}#{individual.get('identifier', '').replace(' ', '')}",
                'type': 'capability_individual',
                'label': individual.get('identifier'),
                'properties': {
                    'capability_class': individual.get('capability_class'),
                    'possessed_by': individual.get('possessed_by'),
                    'capability_statement': individual.get('capability_statement'),
                    'demonstrated_through': individual.get('demonstrated_through'),
                    'proficiency_level': individual.get('proficiency_level'),
                    'enables_obligations': individual.get('enables_obligations'),
                    'temporal_aspect': individual.get('temporal_aspect'),
                    'case_context': individual.get('case_context')
                },
                'relationships': []
            })

        # Return both graphs for dual processing
        return self.class_graph, self.individual_graph

    def _add_capability_class_to_graph(self, capability_class: Dict[str, Any], case_id: int, timestamp: datetime):
        """Add a capability class to the RDF graph"""
        # Create URI for the capability class
        label = capability_class.get('label', 'UnknownCapability')
        safe_label = label.replace(" ", "")
        class_uri = URIRef(f"{self.PROETHICA}{safe_label}")

        # Add class definition
        self.class_graph.add((class_uri, RDF.type, OWL.Class))
        self.class_graph.add((class_uri, RDFS.subClassOf, URIRef(f"{self.PROETHICA}Capability")))
        self.class_graph.add((class_uri, RDFS.label, Literal(label)))

        # Add definition
        if capability_class.get('definition'):
            self.class_graph.add((class_uri, RDFS.comment, Literal(capability_class['definition'])))

        # Add capability-specific properties
        if capability_class.get('capability_type'):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}capabilityType"), Literal(capability_class['capability_type'])))

        if capability_class.get('norm_competence_related'):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}normCompetenceRelated"), Literal(capability_class['norm_competence_related'])))

        if capability_class.get('skill_level'):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}skillLevel"), Literal(capability_class['skill_level'])))

        if capability_class.get('acquisition_method'):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}acquisitionMethod"), Literal(capability_class['acquisition_method'])))

        # Add examples from case
        for example in capability_class.get('examples_from_case', []):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}exampleFromCase"), Literal(example)))

        # Add source text (provenance)
        if capability_class.get('source_text') and capability_class['source_text']:
            self.class_graph.add((class_uri, self.PROETHICA_PROV.sourceText, Literal(capability_class['source_text'])))

        # Add extraction metadata
        self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}confidence"), Literal(capability_class.get('confidence', 0.8))))
        self.class_graph.add((class_uri, PROV.generatedAtTime, Literal(timestamp, datatype=XSD.dateTime)))

    def _add_capability_individual_to_graph(self, individual: Dict[str, Any], case_id: int, timestamp: datetime):
        """Add a capability individual to the RDF graph"""
        # Create URI for the individual
        identifier = individual.get('identifier', 'UnknownCapability')
        safe_identifier = identifier.replace(" ", "")
        individual_uri = URIRef(f"http://proethica.org/ontology/case/{case_id}#{safe_identifier}")

        # Determine the class URI
        capability_class = individual.get('capability_class', 'Capability')
        if individual.get('is_existing_class'):
            # Use existing class from ontology
            class_uri = URIRef(f"{self.PROETHICA}{capability_class.replace(' ', '')}")
        else:
            # Use newly discovered class
            class_uri = URIRef(f"{self.PROETHICA}{capability_class.replace(' ', '')}")

        # Add individual assertion
        self.individual_graph.add((individual_uri, RDF.type, OWL.NamedIndividual))
        self.individual_graph.add((individual_uri, RDF.type, class_uri))
        self.individual_graph.add((individual_uri, RDFS.label, Literal(identifier)))

        # Add capability properties
        if individual.get('possessed_by'):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}possessedBy"), Literal(individual['possessed_by'])))

        if individual.get('capability_statement'):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}capabilityStatement"), Literal(individual['capability_statement'])))

        if individual.get('demonstrated_through'):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}demonstratedThrough"), Literal(individual['demonstrated_through'])))

        if individual.get('proficiency_level'):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}proficiencyLevel"), Literal(individual['proficiency_level'])))

        if individual.get('enables_obligations'):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}enablesObligations"), Literal(individual['enables_obligations'])))

        if individual.get('temporal_aspect'):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}temporalAspect"), Literal(individual['temporal_aspect'])))

        if individual.get('case_context'):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}caseContext"), Literal(individual['case_context'])))

        # Add source text (provenance)
        if individual.get('source_text') and individual['source_text']:
            self.individual_graph.add((individual_uri, self.PROETHICA_PROV.sourceText, Literal(individual['source_text'])))

        # Add extraction metadata
        self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}confidence"), Literal(individual.get('confidence', 0.85))))
        self.individual_graph.add((individual_uri, PROV.generatedAtTime, Literal(timestamp, datatype=XSD.dateTime)))

    def convert_actions_extraction_to_rdf(self,
                                         extraction_result: Dict[str, Any],
                                         case_id: int,
                                         extraction_timestamp: Optional[datetime] = None) -> Tuple[Graph, Graph]:
        """
        Convert actions dual extraction results to RDF format.

        Args:
            extraction_result: Dictionary containing new_action_classes and action_individuals
            case_id: Case identifier for individual URIs
            extraction_timestamp: When the extraction occurred

        Returns:
            Tuple of (class_graph, individual_graph)
        """
        if extraction_timestamp is None:
            extraction_timestamp = datetime.now()

        # Clear graphs
        self.class_graph = Graph()
        self.individual_graph = Graph()
        self._bind_prefixes()

        timestamp = extraction_timestamp

        # Process new action classes for proethica-intermediate
        for action_class in extraction_result.get('new_action_classes', []):
            self._add_action_class_to_graph(action_class, case_id, timestamp)

        # Process action individuals for case-specific ontology
        for individual in extraction_result.get('action_individuals', []):
            self._add_action_individual_to_graph(individual, case_id, timestamp)

        logger.info(f"Actions RDF conversion complete: {len(self.class_graph)} class triples, {len(self.individual_graph)} individual triples")

        return self.class_graph, self.individual_graph

    def _add_action_class_to_graph(self, action_class: Dict[str, Any], case_id: int, timestamp: datetime):
        """Add an action class to the class graph"""
        label = action_class.get('label', 'Unknown Action')
        safe_label = label.replace(" ", "")
        class_uri = URIRef(f"{self.PROETHICA_INT}{safe_label}")

        # Basic class definition
        self.class_graph.add((class_uri, RDF.type, OWL.Class))
        self.class_graph.add((class_uri, RDFS.subClassOf, URIRef(f"{self.PROETHICA}Action")))
        self.class_graph.add((class_uri, RDFS.label, Literal(label)))

        if action_class.get('definition'):
            self.class_graph.add((class_uri, RDFS.comment, Literal(action_class['definition'])))

        # Action-specific properties
        if action_class.get('action_category'):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}actionCategory"), Literal(action_class['action_category'])))

        if action_class.get('volitional_requirement'):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}volitionalRequirement"), Literal(action_class['volitional_requirement'])))

        if action_class.get('professional_context'):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}professionalContext"), Literal(action_class['professional_context'])))

        if action_class.get('intention_requirement'):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}intentionRequirement"), Literal(action_class['intention_requirement'])))

        # List properties (obligations fulfilled, temporal constraints, etc.)
        for obligation in action_class.get('obligations_fulfilled', []):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}fulfillsObligation"), Literal(obligation)))

        for constraint in action_class.get('temporal_constraints', []):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}temporalConstraint"), Literal(constraint)))

        for implication in action_class.get('causal_implications', []):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}causalImplication"), Literal(implication)))

        for example in action_class.get('examples_from_case', []):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}exampleFromCase"), Literal(example)))

        # Add source text (provenance)
        if action_class.get('source_text') and action_class['source_text']:
            self.class_graph.add((class_uri, self.PROETHICA_PROV.sourceText, Literal(action_class['source_text'])))

        # Metadata
        self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}discoveredInCase"), Literal(case_id)))
        self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}confidence"), Literal(action_class.get('confidence', 0.85))))
        self.class_graph.add((class_uri, PROV.generatedAtTime, Literal(timestamp, datatype=XSD.dateTime)))

    def _add_action_individual_to_graph(self, individual: Dict[str, Any], case_id: int, timestamp: datetime):
        """Add an action individual to the individual graph"""
        identifier = individual.get('identifier', 'UnknownAction')
        safe_identifier = identifier.replace(" ", "")
        individual_uri = URIRef(f"http://proethica.org/ontology/case/{case_id}#{safe_identifier}")

        # Find action class URI
        action_class = individual.get('action_class', 'Action')
        safe_action_class = action_class.replace(" ", "")
        if individual.get('is_new_action_class', False):
            action_class_uri = URIRef(f"{self.PROETHICA_INT}{safe_action_class}")
        else:
            action_class_uri = URIRef(f"{self.PROETHICA}{safe_action_class}")

        # Basic individual definition
        self.individual_graph.add((individual_uri, RDF.type, OWL.NamedIndividual))
        self.individual_graph.add((individual_uri, RDF.type, action_class_uri))
        self.individual_graph.add((individual_uri, RDFS.label, Literal(identifier)))

        # Action-specific properties
        if individual.get('performed_by'):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}performedBy"), Literal(individual['performed_by'])))

        if individual.get('performed_on'):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}performedOn"), Literal(individual['performed_on'])))

        if individual.get('temporal_interval'):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}temporalInterval"), Literal(individual['temporal_interval'])))

        if individual.get('duration'):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}duration"), Literal(individual['duration'])))

        if individual.get('sequence_order'):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}sequenceOrder"), Literal(individual['sequence_order'])))

        # Causal relationships
        for trigger in individual.get('causal_triggers', []):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}causalTrigger"), Literal(trigger)))

        for result in individual.get('causal_results', []):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}causalResult"), Literal(result)))

        # Allen's interval relations
        for relation in individual.get('allen_relations', []):
            if isinstance(relation, dict) and 'relation' in relation and 'target' in relation:
                self.individual_graph.add((individual_uri,
                    URIRef(f"{self.PROETHICA}allenRelation_{relation['relation']}"),
                    Literal(relation['target'])))

        # Professional integration
        for obligation in individual.get('obligations_fulfilled', []):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}fulfillsObligation"), Literal(obligation)))

        for constraint in individual.get('constraints_respected', []):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}respectsConstraint"), Literal(constraint)))

        for capability in individual.get('capabilities_required', []):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}requiresCapability"), Literal(capability)))

        if individual.get('case_context'):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}caseContext"), Literal(individual['case_context'])))

        # Add source text (provenance)
        if individual.get('source_text') and individual['source_text']:
            self.individual_graph.add((individual_uri, self.PROETHICA_PROV.sourceText, Literal(individual['source_text'])))

        # Metadata
        self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}confidence"), Literal(individual.get('confidence', 0.85))))
        self.individual_graph.add((individual_uri, PROV.generatedAtTime, Literal(timestamp, datatype=XSD.dateTime)))

    def convert_events_extraction_to_rdf(self,
                                        extraction_result: Dict[str, Any],
                                        case_id: int,
                                        extraction_timestamp: Optional[datetime] = None) -> Tuple[Graph, Graph]:
        """
        Convert events dual extraction results to RDF format.

        Args:
            extraction_result: Dictionary containing new_event_classes and event_individuals
            case_id: Case identifier for individual URIs
            extraction_timestamp: When the extraction occurred

        Returns:
            Tuple of (class_graph, individual_graph)
        """
        if extraction_timestamp is None:
            extraction_timestamp = datetime.now()

        # Clear graphs
        self.class_graph = Graph()
        self.individual_graph = Graph()
        self._bind_prefixes()

        timestamp = extraction_timestamp

        # Process new event classes for proethica-intermediate
        for event_class in extraction_result.get('new_event_classes', []):
            self._add_event_class_to_graph(event_class, case_id, timestamp)

        # Process event individuals for case-specific ontology
        for individual in extraction_result.get('event_individuals', []):
            self._add_event_individual_to_graph(individual, case_id, timestamp)

        logger.info(f"Events RDF conversion complete: {len(self.class_graph)} class triples, {len(self.individual_graph)} individual triples")

        return self.class_graph, self.individual_graph

    def _add_event_class_to_graph(self, event_class: Dict[str, Any], case_id: int, timestamp: datetime):
        """Add an event class to the class graph"""
        label = event_class.get('label', 'Unknown Event')
        safe_label = label.replace(" ", "")
        class_uri = URIRef(f"{self.PROETHICA_INT}{safe_label}")

        # Basic class definition
        self.class_graph.add((class_uri, RDF.type, OWL.Class))
        self.class_graph.add((class_uri, RDFS.subClassOf, URIRef(f"{self.PROETHICA}Event")))
        self.class_graph.add((class_uri, RDFS.label, Literal(label)))

        if event_class.get('definition'):
            self.class_graph.add((class_uri, RDFS.comment, Literal(event_class['definition'])))

        # Event-specific properties
        if event_class.get('event_category'):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}eventCategory"), Literal(event_class['event_category'])))

        if event_class.get('temporal_marker'):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}temporalMarker"), Literal(event_class['temporal_marker'])))

        if event_class.get('automatic_nature'):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}automaticNature"), Literal(event_class['automatic_nature'])))

        if event_class.get('obligation_transformation'):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}obligationTransformation"), Literal(event_class['obligation_transformation'])))

        if event_class.get('causal_position'):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}causalPosition"), Literal(event_class['causal_position'])))

        if event_class.get('ethical_salience'):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}ethicalSalience"), Literal(event_class['ethical_salience'])))

        # List properties (constraint activation, state transitions, etc.)
        for constraint in event_class.get('constraint_activation', []):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}activatesConstraint"), Literal(constraint)))

        for transition in event_class.get('state_transitions', []):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}stateTransition"), Literal(transition)))

        for example in event_class.get('examples_from_case', []):
            self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}exampleFromCase"), Literal(example)))

        # Add source text (provenance)
        if event_class.get('source_text') and event_class['source_text']:
            self.class_graph.add((class_uri, self.PROETHICA_PROV.sourceText, Literal(event_class['source_text'])))

        # Metadata
        self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}discoveredInCase"), Literal(case_id)))
        self.class_graph.add((class_uri, URIRef(f"{self.PROETHICA}confidence"), Literal(event_class.get('confidence', 0.85))))
        self.class_graph.add((class_uri, PROV.generatedAtTime, Literal(timestamp, datatype=XSD.dateTime)))

    def _add_event_individual_to_graph(self, individual: Dict[str, Any], case_id: int, timestamp: datetime):
        """Add an event individual to the individual graph"""
        identifier = individual.get('identifier', 'UnknownEvent')
        safe_identifier = identifier.replace(" ", "")
        individual_uri = URIRef(f"http://proethica.org/ontology/case/{case_id}#{safe_identifier}")

        # Find event class URI
        event_class = individual.get('event_class', 'Event')
        safe_event_class = event_class.replace(" ", "")
        if individual.get('is_new_event_class', False):
            event_class_uri = URIRef(f"{self.PROETHICA_INT}{safe_event_class}")
        else:
            event_class_uri = URIRef(f"{self.PROETHICA}{safe_event_class}")

        # Basic individual definition
        self.individual_graph.add((individual_uri, RDF.type, OWL.NamedIndividual))
        self.individual_graph.add((individual_uri, RDF.type, event_class_uri))
        self.individual_graph.add((individual_uri, RDFS.label, Literal(identifier)))

        # Event-specific properties
        if individual.get('occurred_to'):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}occurredTo"), Literal(individual['occurred_to'])))

        if individual.get('discovered_by'):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}discoveredBy"), Literal(individual['discovered_by'])))

        if individual.get('temporal_interval'):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}temporalInterval"), Literal(individual['temporal_interval'])))

        if individual.get('duration'):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}duration"), Literal(individual['duration'])))

        if individual.get('sequence_order'):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}sequenceOrder"), Literal(individual['sequence_order'])))

        # Causal relationships
        for trigger in individual.get('causal_triggers', []):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}causalTrigger"), Literal(trigger)))

        for result in individual.get('causal_results', []):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}causalResult"), Literal(result)))

        # Allen's interval relations
        for relation in individual.get('allen_relations', []):
            if isinstance(relation, dict) and 'relation' in relation and 'target' in relation:
                self.individual_graph.add((individual_uri,
                    URIRef(f"{self.PROETHICA}allenRelation_{relation['relation']}"),
                    Literal(relation['target'])))

        # Professional integration
        for constraint in individual.get('constraints_activated', []):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}activatesConstraint"), Literal(constraint)))

        for obligation in individual.get('obligations_triggered', []):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}triggersObligation"), Literal(obligation)))

        for state in individual.get('states_changed', []):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}changesState"), Literal(state)))

        if individual.get('case_context'):
            self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}caseContext"), Literal(individual['case_context'])))

        # Add source text (provenance)
        if individual.get('source_text') and individual['source_text']:
            self.individual_graph.add((individual_uri, self.PROETHICA_PROV.sourceText, Literal(individual['source_text'])))

        # Metadata
        self.individual_graph.add((individual_uri, URIRef(f"{self.PROETHICA}confidence"), Literal(individual.get('confidence', 0.85))))
        self.individual_graph.add((individual_uri, PROV.generatedAtTime, Literal(timestamp, datatype=XSD.dateTime)))

    def convert_actions_events_extraction_to_rdf(self,
                                               extraction_result: Dict[str, Any],
                                               case_id: int,
                                               extraction_timestamp: Optional[datetime] = None) -> Tuple[Graph, Graph]:
        """
        Convert combined actions & events dual extraction results to RDF format.

        Args:
            extraction_result: Dictionary containing all four arrays (new_action_classes, action_individuals, new_event_classes, event_individuals)
            case_id: Case identifier for individual URIs
            extraction_timestamp: When the extraction occurred

        Returns:
            Tuple of (class_graph, individual_graph)
        """
        if extraction_timestamp is None:
            extraction_timestamp = datetime.now()

        # Clear graphs
        self.class_graph = Graph()
        self.individual_graph = Graph()
        self._bind_prefixes()

        timestamp = extraction_timestamp

        # Process all four types of entities
        for action_class in extraction_result.get('new_action_classes', []):
            self._add_action_class_to_graph(action_class, case_id, timestamp)

        for individual in extraction_result.get('action_individuals', []):
            self._add_action_individual_to_graph(individual, case_id, timestamp)

        for event_class in extraction_result.get('new_event_classes', []):
            self._add_event_class_to_graph(event_class, case_id, timestamp)

        for individual in extraction_result.get('event_individuals', []):
            self._add_event_individual_to_graph(individual, case_id, timestamp)

        logger.info(f"Combined Actions & Events RDF conversion complete: {len(self.class_graph)} class triples, {len(self.individual_graph)} individual triples")

        return self.class_graph, self.individual_graph