"""
Service to manage per-world dynamic "cases ontology" and upsert new role classes.

This lets users add LLM-suggested roles directly into a world-scoped editable ontology
and mirrors them into the relational Roles table.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional, Tuple

from app import db
from app.models.world import World
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion
from app.models.ontology_import import OntologyImport
from app.models.role import Role


class CasesOntologyService:
    """Utilities for creating and updating a per-world editable ontology."""

    CASES_DOMAIN_PREFIX = "world-cases-"
    BASE_URI_PREFIX = "http://proethica.org/ontology/"

    def get_or_create_world_cases_ontology(self, world: World) -> Ontology:
        """Return the per-world cases ontology, creating it if it doesn't exist.

        - domain_id: f"world-cases-{world.id}"
        - base_uri: f"{BASE_URI_PREFIX}world-{world.id}#"
        - imports the world's primary ontology (if set) and proethica-intermediate
        """
        domain_id = f"{self.CASES_DOMAIN_PREFIX}{world.id}"

        ontology = Ontology.query.filter_by(domain_id=domain_id).first()
        if ontology:
            return ontology

        base_uri = f"{self.BASE_URI_PREFIX}world-{world.id}#"
        # Seed TTL with common prefixes and ontology header
        ttl_header = (
            "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
            "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
            "@prefix proethica: <http://proethica.org/ontology/intermediate#> .\n"
            f"@prefix world: <{base_uri}> .\n\n"
            f"<{base_uri.rstrip('#')}> a owl:Ontology ; rdfs:label \"{world.name} Cases Ontology\" .\n\n"
        )

        ontology = Ontology(
            name=f"{world.name} Cases Ontology",
            description=f"Editable per-world ontology for '{world.name}' to store scenario-specific roles and concepts.",
            domain_id=domain_id,
            content=ttl_header,
            is_base=False,
            is_editable=True,
            base_uri=base_uri,
        )
        db.session.add(ontology)
        db.session.flush()  # get ontology.id

        # Import the world's main ontology, if present
        if world.ontology_id:
            try:
                db.session.add(OntologyImport(importing_ontology_id=ontology.id, imported_ontology_id=world.ontology_id))
            except Exception:
                pass

        # Also try to import proethica-intermediate if present in DB
        try:
            intermediate = Ontology.query.filter_by(domain_id='proethica-intermediate').first()
            if intermediate:
                db.session.add(OntologyImport(importing_ontology_id=ontology.id, imported_ontology_id=intermediate.id))
        except Exception:
            pass

        # Create initial version
        version = OntologyVersion(
            ontology_id=ontology.id,
            version_number=1,
            content=ontology.content,
            commit_message="Initialize cases ontology"
        )
        db.session.add(version)
        db.session.commit()
        return ontology

    def add_role_to_cases_ontology(self, world: World, label: str, description: str = "") -> Tuple[str, Role]:
        """Create a Role class in the world's cases ontology and a corresponding Role row.

        Returns: (ontology_uri, role_db)
        """
        cases_ont = self.get_or_create_world_cases_ontology(world)

        # Generate a stable fragment identifier for the class
        class_fragment = self._to_camel_case(label) + "Role"
        # Ensure uniqueness by checking current content
        content = cases_ont.content or ""
        suffix = 1
        unique_fragment = class_fragment
        while re.search(rf"[:#]{re.escape(unique_fragment)}\b", content):
            suffix += 1
            unique_fragment = f"{class_fragment}{suffix}"

        # Build TTL for the new class
        ttl_snippet = (
            f"world:{unique_fragment} a owl:Class, proethica:Role ;\n"
            f"  rdfs:label \"{self._escape_literal(label)}\" ;\n"
            f"  rdfs:comment \"{self._escape_literal(description or '')}\" ;\n"
            f"  rdfs:subClassOf proethica:Role .\n\n"
        )

        # Append to ontology content and version
        updated_content = (content + ("\n" if not content.endswith("\n") else "") + ttl_snippet)
        cases_ont.content = updated_content
        cases_ont.updated_at = datetime.utcnow()

        # Create a new version entry
        latest = (
            OntologyVersion.query.filter_by(ontology_id=cases_ont.id)
            .order_by(OntologyVersion.version_number.desc())
            .first()
        )
        next_version = (latest.version_number + 1) if latest else 1
        version = OntologyVersion(
            ontology_id=cases_ont.id,
            version_number=next_version,
            content=updated_content,
            commit_message=f"Add Role: {label}"
        )
        db.session.add(version)

        # Mirror into relational Role table (scoped to this world)
        ontology_uri = f"{cases_ont.base_uri}{unique_fragment}"
        role_db = Role(
            name=label,
            description=description,
            world_id=world.id,
            ontology_uri=ontology_uri,
        )
        db.session.add(role_db)

        db.session.commit()
        return ontology_uri, role_db

    # -----------------
    # Helpers
    # -----------------
    def _to_camel_case(self, s: str) -> str:
        # Remove non-alphanumeric and split
        parts = re.split(r"[^A-Za-z0-9]+", s.strip())
        parts = [p for p in parts if p]
        if not parts:
            return "Custom"
        return parts[0].capitalize() + "".join(p.capitalize() for p in parts[1:])

    def _escape_literal(self, s: str) -> str:
        return s.replace("\\", "\\\\").replace("\"", "\\\"")
