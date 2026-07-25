"""
Case-TTL-building mixin for AutoCommitService.

Extracted verbatim from auto_commit_service.py (god-file split PHASE 2 Step
2.5): case TTL generation (fresh graph or legacy merge) and the per-entity
property-merge / entity-type-mapping helpers it uses. AutoCommitService
gains CaseTtlBuilderMixin as a base class so every self._method(...) call
site is unaffected.

Namespace constants (PROETHICA, PROETHICA_CORE, PROV) are redeclared locally
rather than imported back from auto_commit_service.py (which imports this
module for the mixin), to avoid a circular import; rdflib Namespace equality
is string-based, so this has no behavioral effect.

DEVIATION (recorded): the two ``EntityCommitResult`` type-hint references
(``_generate_case_ttl``'s ``results`` param, ``_merge_entity_properties``'s
``result`` param) are quoted as forward-reference strings rather than
imported from auto_commit_service.py, again to avoid a circular import back
to the module that imports this one for the mixin. Python never evaluates a
quoted annotation at runtime, so this is behaviorally inert.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from rdflib import Graph, Literal, Namespace, URIRef, RDF, RDFS, OWL, XSD
from rdflib.namespace import SKOS, DCTERMS

from app.models.temporary_rdf_storage import TemporaryRDFStorage

logger = logging.getLogger(__name__)

# Namespaces (see auto_commit_service.py module docstring for the shared definitions).
PROETHICA = Namespace("http://proethica.org/ontology/intermediate#")
PROETHICA_CORE = Namespace("http://proethica.org/ontology/core#")
PROV = Namespace("http://www.w3.org/ns/prov#")


class CaseTtlBuilderMixin:
    """Case TTL generation: fresh/legacy graph building, entity-property
    merging, and the section-type / core-type / safe-URI helpers it uses."""

    def _case_title(self, case_id: int) -> Optional[str]:
        """Human case title for the case id, or None if the document is absent.
        Emitted as dcterms:title in the TTL header so OntServe can read it into
        display_name on sync (see OntServeCommitService._case_title)."""
        from app.models.document import Document
        from app.models import db
        doc = db.session.get(Document, case_id)
        title = (doc.title or '').strip() if doc else ''
        return title or None

    def _generate_case_ttl(
        self,
        case_id: int,
        entities: List[TemporaryRDFStorage],
        results: List["EntityCommitResult"]
    ) -> Optional[str]:
        """
        Generate case-specific .ttl file with individuals typed to OntServe classes.

        Implements property merging: when the same individual is extracted from
        multiple sections (facts, discussion), properties are merged rather than
        the second extraction being skipped.

        Args:
            case_id: The case ID
            entities: List of entities to include
            results: Commit results with linked URIs

        Returns:
            Path to generated .ttl file, or None if error
        """
        try:
            case_file = self.ontologies_dir / f"proethica-case-{case_id}.ttl"

            # Check if using versioned commits (overwrites TTL) or legacy (merges)
            versioned = getattr(self, '_versioned_commit', True)

            # Create graph - for versioned commits, always start fresh
            g = Graph()
            if not versioned and case_file.exists():
                # Legacy: load existing and merge
                g.parse(case_file, format='turtle')
                logger.info(f"Legacy mode: merging with existing TTL for case {case_id}")
            else:
                # Versioned: always create fresh ontology declaration
                if versioned and case_file.exists():
                    logger.info(f"Versioned mode: overwriting TTL for case {case_id}")
                case_ontology_uri = URIRef(f"http://proethica.org/ontology/case/{case_id}")
                g.add((case_ontology_uri, RDF.type, OWL.Ontology))
                g.add((case_ontology_uri, RDFS.label, Literal(f"ProEthica Case {case_id} Ontology")))
                _title = self._case_title(case_id)
                if _title:
                    g.add((case_ontology_uri, DCTERMS.title, Literal(_title)))
                g.add((case_ontology_uri, OWL.imports, URIRef("http://proethica.org/ontology/intermediate")))
                g.add((case_ontology_uri, DCTERMS.created, Literal(datetime.utcnow())))

            # Bind namespaces
            case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")
            g.bind(f"case{case_id}", case_ns)
            g.bind("proeth", PROETHICA)
            g.bind("proeth-core", PROETHICA_CORE)
            g.bind("prov", PROV)
            g.bind("skos", SKOS)

            # Create a map of entity_id to result for quick lookup
            result_map = {r.entity_id: r for r in results}

            # Group entities by URI for merging
            entities_by_uri: Dict[str, List[Tuple[TemporaryRDFStorage, EntityCommitResult]]] = {}
            for entity in entities:
                result = result_map.get(entity.id)
                if not result or result.action in ('error', 'skipped'):
                    continue

                safe_label = self._make_safe_uri(entity.entity_label)
                uri_key = str(case_ns[safe_label])

                if uri_key not in entities_by_uri:
                    entities_by_uri[uri_key] = []
                entities_by_uri[uri_key].append((entity, result))

            individuals_added = 0
            individuals_merged = 0

            for uri_key, entity_list in entities_by_uri.items():
                individual_uri = URIRef(uri_key)
                already_exists = (individual_uri, RDF.type, OWL.NamedIndividual) in g

                if already_exists:
                    # Merge properties from all new entities into existing individual
                    for entity, result in entity_list:
                        self._merge_entity_properties(g, individual_uri, entity, result, case_id)
                    individuals_merged += len(entity_list)
                    logger.debug(f"Merged {len(entity_list)} extractions into existing {entity_list[0][0].entity_label}")
                else:
                    # Create new individual and merge all extractions
                    first_entity, first_result = entity_list[0]

                    # Add as NamedIndividual
                    g.add((individual_uri, RDF.type, OWL.NamedIndividual))
                    g.add((individual_uri, RDFS.label, Literal(first_entity.entity_label)))

                    # Add type reference to OntServe class
                    if first_result.linked_uri:
                        class_uri = URIRef(first_result.linked_uri)
                        g.add((individual_uri, RDF.type, class_uri))
                    elif first_result.action == 'new_class':
                        core_type = self._get_core_type(first_entity.entity_type)
                        if core_type:
                            g.add((individual_uri, RDF.type, core_type))

                    # Add provenance
                    g.add((individual_uri, PROV.generatedAtTime, Literal(datetime.utcnow())))
                    g.add((individual_uri, PROV.wasGeneratedBy, Literal(f"ProEthica Case {case_id} Auto-Commit")))

                    # Add match metadata from first result
                    if first_result.confidence:
                        g.add((individual_uri, URIRef(str(PROETHICA) + "matchConfidence"),
                               Literal(first_result.confidence, datatype=XSD.float)))

                    # Merge properties from ALL extractions (facts + discussion)
                    for entity, result in entity_list:
                        self._merge_entity_properties(g, individual_uri, entity, result, case_id)

                    individuals_added += 1

                    if len(entity_list) > 1:
                        logger.info(f"Created {first_entity.entity_label} with merged properties from {len(entity_list)} sections")

            # Save the graph
            g.serialize(destination=case_file, format='turtle')
            logger.info(f"Generated case TTL: {individuals_added} new, {individuals_merged} merged: {case_file}")

            # NOTE: edge materialization (defeasibility + R->P->O + cites-provision)
            # is NOT run here. In the default versioned path this TTL is rewritten
            # by commit_case_versioned -> _write_case_ttl_fresh (which overwrites),
            # so edges added here would be clobbered. Materialization runs on the
            # FINAL persisted TTL: in commit_case_versioned (versioned) or in
            # _sync_to_ontserve (non-versioned). See edge_materialization.py.
            return str(case_file)

        except Exception as e:
            logger.error(f"Error generating case TTL for case {case_id}: {e}")
            return None

    def _merge_entity_properties(
        self,
        g: Graph,
        individual_uri: URIRef,
        entity: TemporaryRDFStorage,
        result: "EntityCommitResult",
        case_id: int
    ):
        """
        Merge properties from an entity extraction into an existing individual.

        Handles multi-value properties by adding new values without duplicating.
        Tracks source texts per section for provenance.

        Args:
            g: The RDF graph
            individual_uri: URI of the individual to merge into
            entity: The entity with properties to merge
            result: The commit result for this entity
            case_id: The case ID
        """
        # Get section type from linked extraction prompt
        section_type = self._get_entity_section_type(entity)

        # Parse JSON-LD properties
        if not entity.rdf_json_ld:
            return

        try:
            json_data = json.loads(entity.rdf_json_ld) if isinstance(entity.rdf_json_ld, str) else entity.rdf_json_ld
        except (json.JSONDecodeError, TypeError):
            return

        properties = json_data.get('properties', {})

        # Define property mappings to RDF predicates
        property_mappings = {
            'hasTitle': URIRef(str(PROETHICA) + "hasTitle"),
            'hasLicense': URIRef(str(PROETHICA) + "hasLicense"),
            'hasSpecialization': URIRef(str(PROETHICA) + "hasSpecialization"),
            'hasExperience': URIRef(str(PROETHICA) + "hasExperience"),
            'hasExpertise': URIRef(str(PROETHICA) + "hasExpertise"),
            'caseInvolvement': URIRef(str(PROETHICA) + "caseInvolvement"),
            'hasActiveObligation': URIRef(str(PROETHICA) + "hasActiveObligation"),
            'hasEthicalTension': URIRef(str(PROETHICA) + "hasEthicalTension"),
        }

        # Add properties, avoiding duplicates
        for prop_name, values in properties.items():
            if prop_name in property_mappings:
                predicate = property_mappings[prop_name]
                if not isinstance(values, list):
                    values = [values]

                for value in values:
                    if value and value != "None":
                        literal = Literal(value)
                        # Check if this exact triple already exists
                        if (individual_uri, predicate, literal) not in g:
                            g.add((individual_uri, predicate, literal))

        # Add source text with section annotation
        source_text = json_data.get('source_text') or properties.get('sourceText', [None])[0]
        if source_text:
            # Use section-specific predicate to preserve both sources
            section_predicate = URIRef(str(PROETHICA) + f"sourceText_{section_type}")
            g.add((individual_uri, section_predicate, Literal(source_text)))

            # Also add to generic sourceText for backward compatibility
            generic_predicate = URIRef(str(PROETHICA) + "sourceText")
            source_with_section = f"[{section_type}] {source_text}"
            if (individual_uri, generic_predicate, Literal(source_with_section)) not in g:
                g.add((individual_uri, generic_predicate, Literal(source_with_section)))

        # Add definition if available
        if entity.entity_definition:
            definition_literal = Literal(entity.entity_definition)
            if (individual_uri, SKOS.definition, definition_literal) not in g:
                g.add((individual_uri, SKOS.definition, definition_literal))

        # Handle relationships
        relationships = json_data.get('relationships', [])
        for rel in relationships:
            rel_type = rel.get('type')
            target = rel.get('target')
            target_uri_str = rel.get('target_uri')

            if rel_type and target_uri_str:
                rel_predicate = URIRef(str(PROETHICA) + rel_type)
                target_uri = URIRef(target_uri_str)
                if (individual_uri, rel_predicate, target_uri) not in g:
                    g.add((individual_uri, rel_predicate, target_uri))

    def _get_entity_section_type(self, entity: TemporaryRDFStorage) -> str:
        """Get the section type (facts/discussion) for an entity."""
        try:
            from app.models.extraction_prompt import ExtractionPrompt
            prompt = ExtractionPrompt.query.filter_by(
                extraction_session_id=entity.extraction_session_id
            ).first()
            if prompt and prompt.section_type:
                return prompt.section_type
        except Exception:
            pass
        return "unknown"

    def _get_core_type(self, entity_type: str) -> Optional[URIRef]:
        """Get the core ontology type URI for an entity type."""
        if not entity_type:
            return None

        type_map = {
            'role': PROETHICA_CORE.Role,
            'roles': PROETHICA_CORE.Role,
            'state': PROETHICA_CORE.State,
            'states': PROETHICA_CORE.State,
            'resource': PROETHICA_CORE.Resource,
            'resources': PROETHICA_CORE.Resource,
            'principle': PROETHICA_CORE.Principle,
            'principles': PROETHICA_CORE.Principle,
            'obligation': PROETHICA_CORE.Obligation,
            'obligations': PROETHICA_CORE.Obligation,
            'action': PROETHICA_CORE.Action,
            'actions': PROETHICA_CORE.Action,
            'actions_events': PROETHICA_CORE.Action,  # Default to Action for combined
            'event': PROETHICA_CORE.Event,
            'events': PROETHICA_CORE.Event,
            'capability': PROETHICA_CORE.Capability,
            'capabilities': PROETHICA_CORE.Capability,
            'constraint': PROETHICA_CORE.Constraint,
            'constraints': PROETHICA_CORE.Constraint,
        }

        return type_map.get(entity_type.lower())

    def _make_safe_uri(self, label: str) -> str:
        """Convert a label to a safe URI component."""
        if not label:
            return "Unknown"

        # Replace spaces and special characters
        safe = label.replace(" ", "_")
        safe = safe.replace("(", "").replace(")", "")
        safe = safe.replace("'", "").replace('"', "")
        safe = safe.replace("/", "_").replace("\\", "_")
        safe = safe.replace(",", "").replace(".", "")

        return safe
