"""
Entity Merge Service

Handles merging of entities extracted from multiple case sections (facts, discussion, etc.)
into unified records in temporary_rdf_storage.

When the same entity (e.g., "Engineer K") is extracted from both facts and discussion,
this service merges their properties into a single record while preserving provenance
from each section.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from app.models import db
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.models.extraction_prompt import ExtractionPrompt

logger = logging.getLogger(__name__)


class EntityMergeService:
    """Service for merging entities extracted from multiple sections."""

    def __init__(self):
        self.merge_stats = {
            'entities_merged': 0,
            'properties_added': 0,
            'sections_combined': []
        }

    def find_existing_entity(
        self,
        case_id: int,
        entity_label: str,
        entity_type: str,
        current_session_id: str
    ) -> Optional[TemporaryRDFStorage]:
        """
        Find an existing entity with the same label from a different section.

        Args:
            case_id: The case ID
            entity_label: Label of the entity to find
            entity_type: Type of entity (Roles, States, etc.)
            current_session_id: Current extraction session (to exclude from search)

        Returns:
            Existing entity if found, None otherwise
        """
        # Find entities with same label from OTHER sessions
        existing = TemporaryRDFStorage.query.filter(
            TemporaryRDFStorage.case_id == case_id,
            TemporaryRDFStorage.entity_label == entity_label,
            TemporaryRDFStorage.entity_type == entity_type,
            TemporaryRDFStorage.extraction_session_id != current_session_id,
            TemporaryRDFStorage.is_published == False
        ).first()

        return existing

    def get_section_type(self, extraction_session_id: str) -> str:
        """Get the section type for an extraction session."""
        prompt = ExtractionPrompt.query.filter_by(
            extraction_session_id=extraction_session_id
        ).first()
        if prompt and prompt.section_type:
            return prompt.section_type
        return "unknown"

    def merge_entity_properties(
        self,
        existing_entity: TemporaryRDFStorage,
        new_json_ld: Dict[str, Any],
        new_session_id: str
    ) -> TemporaryRDFStorage:
        """
        Merge properties from a new extraction into an existing entity.

        Args:
            existing_entity: The existing entity to merge into
            new_json_ld: JSON-LD from the new extraction
            new_session_id: Session ID of the new extraction

        Returns:
            Updated entity with merged properties
        """
        existing_json = existing_entity.rdf_json_ld or {}
        existing_section = self.get_section_type(existing_entity.extraction_session_id)
        new_section = self.get_section_type(new_session_id)

        # Initialize section_sources if not present
        if 'section_sources' not in existing_json:
            existing_json['section_sources'] = [existing_section]

        # Add new section to sources if not already present
        if new_section not in existing_json['section_sources']:
            existing_json['section_sources'].append(new_section)

        # Merge properties
        existing_props = existing_json.get('properties', {})
        new_props = new_json_ld.get('properties', {})

        for prop_name, new_values in new_props.items():
            if not isinstance(new_values, list):
                new_values = [new_values]

            if prop_name not in existing_props:
                existing_props[prop_name] = new_values
            else:
                # Merge values, avoiding duplicates
                existing_values = existing_props[prop_name]
                if not isinstance(existing_values, list):
                    existing_values = [existing_values]

                for val in new_values:
                    if val and val not in existing_values and val != "None":
                        existing_values.append(val)
                        self.merge_stats['properties_added'] += 1

                existing_props[prop_name] = existing_values

        existing_json['properties'] = existing_props

        # Merge source texts with section labels
        if 'source_texts' not in existing_json:
            existing_json['source_texts'] = {}

        # Store existing source_text under its section
        if existing_json.get('source_text') and existing_section not in existing_json['source_texts']:
            existing_json['source_texts'][existing_section] = existing_json['source_text']

        # Store new source_text under its section
        if new_json_ld.get('source_text'):
            existing_json['source_texts'][new_section] = new_json_ld['source_text']

        # Keep main source_text as combined view
        combined_sources = []
        for section, text in existing_json['source_texts'].items():
            combined_sources.append(f"[{section}] {text}")
        existing_json['source_text'] = " | ".join(combined_sources)

        # Merge relationships
        existing_rels = existing_json.get('relationships', [])
        new_rels = new_json_ld.get('relationships', [])

        existing_rel_keys = {
            (r.get('type'), r.get('target_uri'))
            for r in existing_rels
        }

        for rel in new_rels:
            rel_key = (rel.get('type'), rel.get('target_uri'))
            if rel_key not in existing_rel_keys:
                existing_rels.append(rel)

        existing_json['relationships'] = existing_rels

        # Merge types
        existing_types = set(existing_json.get('types', []))
        new_types = set(new_json_ld.get('types', []))
        existing_json['types'] = list(existing_types | new_types)

        # Update the entity
        existing_entity.rdf_json_ld = existing_json
        existing_entity.updated_at = db.func.now()

        # Update counts
        existing_entity.property_count = sum(
            len(v) if isinstance(v, list) else 1
            for v in existing_props.values()
        )
        existing_entity.relationship_count = len(existing_rels)

        self.merge_stats['entities_merged'] += 1
        if new_section not in self.merge_stats['sections_combined']:
            self.merge_stats['sections_combined'].append(new_section)

        logger.info(
            f"Merged entity '{existing_entity.entity_label}' from {new_section} "
            f"into existing from {existing_section}. "
            f"Now has sources: {existing_json['section_sources']}"
        )

        return existing_entity

    def save_or_merge_entity(
        self,
        case_id: int,
        extraction_session_id: str,
        extraction_type: str,
        storage_type: str,
        ontology_target: str,
        entity_label: str,
        entity_type: str,
        entity_definition: str,
        rdf_json_ld: Dict[str, Any],
        extraction_model: str = None,
        provenance_metadata: Dict = None,
        match_decision: Dict = None
    ) -> Tuple[TemporaryRDFStorage, bool]:
        """
        Save a new entity or merge into existing if duplicate found.

        Args:
            Various entity fields...

        Returns:
            Tuple of (entity, was_merged)
        """
        # Check for existing entity from another section
        existing = self.find_existing_entity(
            case_id=case_id,
            entity_label=entity_label,
            entity_type=entity_type,
            current_session_id=extraction_session_id
        )

        if existing:
            # Merge into existing entity
            merged = self.merge_entity_properties(existing, rdf_json_ld, extraction_session_id)
            db.session.commit()
            return merged, True
        else:
            # Create new entity
            # Initialize section_sources in JSON-LD
            section_type = self.get_section_type(extraction_session_id)
            if rdf_json_ld:
                rdf_json_ld['section_sources'] = [section_type]
                if rdf_json_ld.get('source_text'):
                    rdf_json_ld['source_texts'] = {section_type: rdf_json_ld['source_text']}

            entity = TemporaryRDFStorage(
                case_id=case_id,
                extraction_session_id=extraction_session_id,
                extraction_type=extraction_type,
                storage_type=storage_type,
                ontology_target=ontology_target,
                entity_label=entity_label,
                entity_type=entity_type,
                entity_definition=entity_definition,
                rdf_json_ld=rdf_json_ld,
                extraction_model=extraction_model,
                provenance_metadata=provenance_metadata or {},
                matched_ontology_uri=match_decision.get('matched_uri') if match_decision else None,
                matched_ontology_label=match_decision.get('matched_label') if match_decision else None,
                match_confidence=match_decision.get('confidence') if match_decision else None,
                match_method='llm' if match_decision and match_decision.get('matches_existing') else None,
                match_reasoning=match_decision.get('reasoning') if match_decision else None,
                is_selected=True
            )
            db.session.add(entity)
            db.session.commit()
            return entity, False

    def merge_case_entities(self, case_id: int) -> Dict[str, Any]:
        """
        Post-process merge: Find and merge all duplicate entities for a case.

        This can be called after all sections are extracted to ensure
        any duplicates are merged.

        Args:
            case_id: The case ID to process

        Returns:
            Summary of merge operations
        """
        # Get all uncommitted entities for the case
        entities = TemporaryRDFStorage.query.filter(
            TemporaryRDFStorage.case_id == case_id,
            TemporaryRDFStorage.is_published == False
        ).all()

        # Group by (entity_label, entity_type)
        entity_groups: Dict[Tuple[str, str], List[TemporaryRDFStorage]] = {}
        for entity in entities:
            key = (entity.entity_label.lower(), entity.entity_type)
            if key not in entity_groups:
                entity_groups[key] = []
            entity_groups[key].append(entity)

        merged_count = 0
        deleted_count = 0

        for key, group in entity_groups.items():
            if len(group) > 1:
                # Multiple entities with same label - merge them
                # Keep the first one, merge others into it
                primary = group[0]
                for duplicate in group[1:]:
                    self.merge_entity_properties(
                        primary,
                        duplicate.rdf_json_ld or {},
                        duplicate.extraction_session_id
                    )
                    # Delete the duplicate
                    db.session.delete(duplicate)
                    deleted_count += 1
                merged_count += 1

        db.session.commit()

        return {
            'case_id': case_id,
            'entities_processed': len(entities),
            'groups_merged': merged_count,
            'duplicates_deleted': deleted_count,
            'merge_stats': self.merge_stats
        }


# Module-level convenience functions
def save_or_merge_entity(**kwargs) -> Tuple[TemporaryRDFStorage, bool]:
    """Convenience function to save or merge an entity."""
    service = EntityMergeService()
    return service.save_or_merge_entity(**kwargs)


def merge_case_entities(case_id: int) -> Dict[str, Any]:
    """Convenience function to merge all duplicate entities for a case."""
    service = EntityMergeService()
    return service.merge_case_entities(case_id)
