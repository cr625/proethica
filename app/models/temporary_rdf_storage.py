"""
Temporary RDF Storage Model

Database model for storing temporary RDF triples from LLM extractions
before they are published to the permanent ontologies.

Draft/Publish Workflow (2025-12-10):
- Entities start as drafts (is_published=False)
- Published to OntServe at end of Step 4 (core entities) or Step 6 (analysis)
- Re-extraction clears unpublished entities of same type
"""

from datetime import datetime
from app.models import db


class TemporaryRDFStorage(db.Model):
    """
    Store temporary RDF triples for review before committing to ontologies.

    This model stores both new classes (for proethica-intermediate) and
    new individuals (for case-specific ontologies) as RDF triples.
    """

    __tablename__ = 'temporary_rdf_storage'

    id = db.Column(db.Integer, primary_key=True)

    # Case and extraction context
    case_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    extraction_session_id = db.Column(db.String(100), nullable=False, index=True)
    extraction_type = db.Column(db.String(50))  # 'roles', 'states', etc.

    # RDF storage type
    storage_type = db.Column(db.String(20), nullable=False)  # 'class' or 'individual'
    ontology_target = db.Column(db.String(100))  # 'proethica-intermediate' or 'proethica-case-N'

    # RDF content
    rdf_turtle = db.Column(db.Text)  # Turtle serialization of the RDF graph
    rdf_json_ld = db.Column(db.JSON)  # JSON-LD representation for easier manipulation

    # Extracted entity information for display
    entity_label = db.Column(db.String(255), index=True)
    entity_uri = db.Column(db.String(500))
    entity_type = db.Column(db.String(100))  # Role, State, etc.
    entity_definition = db.Column(db.Text)

    # Review status
    is_selected = db.Column(db.Boolean, default=True)
    is_reviewed = db.Column(db.Boolean, default=False)
    is_published = db.Column(db.Boolean, default=False)  # Renamed from is_published (2025-12-10)
    review_notes = db.Column(db.Text)

    # Provenance
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100))
    extraction_model = db.Column(db.String(100))  # Which LLM model was used

    # Statistics
    triple_count = db.Column(db.Integer, default=0)
    property_count = db.Column(db.Integer, default=0)
    relationship_count = db.Column(db.Integer, default=0)

    # IAO Document References (Phase 1 - Added 2025-10-07)
    iao_document_uri = db.Column(db.String(500))  # URI of IAO document (iao:0000300 or iao:0000310)
    iao_document_label = db.Column(db.String(500))  # Human-readable label (e.g., "NSPE Code Section II.4.a")
    iao_document_type = db.Column(db.String(50))  # 'document' or 'document_part'
    cited_by_role = db.Column(db.String(200))  # Which role cited this (for References section)
    available_to_role = db.Column(db.String(200))  # Which role has access (for case context)

    # PROV-O Provenance Metadata (Added 2025-10-12)
    provenance_metadata = db.Column(db.JSON)  # Provenance tracking (activity_id, section_type, match_reasoning, etc.)

    # OntServe Class Matching (Added 2025-12-01 for Entity-Ontology Linking)
    matched_ontology_uri = db.Column(db.String(500))  # URI of matched OntServe class
    matched_ontology_label = db.Column(db.String(255))  # Label of matched OntServe class
    match_confidence = db.Column(db.Float)  # Confidence score 0.0-1.0
    match_method = db.Column(db.String(50))  # 'llm', 'embedding', 'exact_label', 'user_override'
    match_reasoning = db.Column(db.Text)  # Explanation of why this match was made

    # Relationships
    case = db.relationship('Document', backref='temporary_rdf_entities', lazy=True)

    def __repr__(self):
        return f'<TemporaryRDFStorage {self.entity_label} ({self.storage_type}) for case {self.case_id}>'

    def to_dict(self):
        """Convert to dictionary for API responses"""
        # Clean the rdf_json_ld data to ensure it's properly serializable
        clean_rdf = self._ensure_serializable(self.rdf_json_ld) if self.rdf_json_ld else None

        return {
            'id': self.id,
            'case_id': self.case_id,
            'extraction_session_id': self.extraction_session_id,
            'extraction_type': self.extraction_type,
            'storage_type': self.storage_type,
            'ontology_target': self.ontology_target,
            'entity_label': self.entity_label,
            'entity_uri': self.entity_uri,
            'entity_type': self.entity_type,
            'entity_definition': self.entity_definition,
            'is_selected': self.is_selected,
            'is_reviewed': self.is_reviewed,
            'is_published': self.is_published,
            'review_notes': self.review_notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'extraction_model': self.extraction_model,
            'triple_count': self.triple_count,
            'property_count': self.property_count,
            'relationship_count': self.relationship_count,
            'rdf_json_ld': clean_rdf,
            # IAO document references
            'iao_document_uri': self.iao_document_uri,
            'iao_document_label': self.iao_document_label,
            'iao_document_type': self.iao_document_type,
            'cited_by_role': self.cited_by_role,
            'available_to_role': self.available_to_role,
            # PROV-O provenance metadata
            'provenance_metadata': self.provenance_metadata,
            # OntServe class matching
            'matched_ontology_uri': self.matched_ontology_uri,
            'matched_ontology_label': self.matched_ontology_label,
            'match_confidence': self.match_confidence,
            'match_method': self.match_method,
            'match_reasoning': self.match_reasoning
        }

    def _ensure_serializable(self, data):
        """Ensure data is JSON serializable, converting dict_values and similar objects."""
        if isinstance(data, dict):
            return {k: self._ensure_serializable(v) for k, v in data.items()}
        elif isinstance(data, (list, tuple)):
            return [self._ensure_serializable(item) for item in data]
        elif hasattr(data, '__iter__') and not isinstance(data, (str, bytes)):
            # This catches dict_values, dict_keys, etc.
            try:
                return list(data)
            except:
                return str(data)
        else:
            return data

    @classmethod
    def clear_case_session(cls, case_id: int, extraction_session_id: str = None):
        """
        Clear temporary RDF storage for a case or specific session.

        Args:
            case_id: The case ID to clear
            extraction_session_id: Optional specific session to clear
        """
        query = cls.query.filter_by(case_id=case_id, is_published=False)

        if extraction_session_id:
            query = query.filter_by(extraction_session_id=extraction_session_id)

        count = query.count()
        query.delete()
        db.session.commit()

        return count

    @classmethod
    def get_case_entities(cls, case_id: int, storage_type: str = None, is_selected: bool = None):
        """
        Get temporary RDF entities for a case.

        Args:
            case_id: The case ID
            storage_type: Optional filter for 'class' or 'individual'
            is_selected: Optional filter for selected entities

        Returns:
            List of TemporaryRDFStorage objects
        """
        query = cls.query.filter_by(case_id=case_id, is_published=False)

        if storage_type:
            query = query.filter_by(storage_type=storage_type)

        if is_selected is not None:
            query = query.filter_by(is_selected=is_selected)

        return query.order_by(cls.created_at.desc()).all()

    @classmethod
    def store_extraction_results(cls, case_id: int, extraction_session_id: str,
                                extraction_type: str, rdf_data: dict,
                                extraction_model: str = None,
                                provenance_data: dict = None):
        """
        Store RDF extraction results from the converter.

        Implements cross-section entity merging: when the same entity (e.g., "Engineer K")
        is extracted from both facts and discussion, properties are merged into a single
        record with provenance tracking from each section.

        Args:
            case_id: The case ID
            extraction_session_id: Unique session identifier
            extraction_type: Type of extraction (roles, states, etc.)
            rdf_data: Dictionary containing classes and individuals from RDF converter
            extraction_model: LLM model used for extraction
            provenance_data: Optional PROV-O provenance metadata (activity_id, section_type, match_reasoning, etc.)

        Returns:
            List of created/updated TemporaryRDFStorage objects
        """
        import logging
        from app.services.entity_merge_service import EntityMergeService

        logger = logging.getLogger(__name__)
        merge_service = EntityMergeService()

        logger.info(f"store_extraction_results called for {extraction_type} case {case_id}")
        logger.info(f"RDF data: {len(rdf_data.get('new_classes', []))} classes, {len(rdf_data.get('new_individuals', []))} individuals")

        created_entities = []
        merged_count = 0

        # Get section type from provenance data
        section_type = provenance_data.get('section_type', 'unknown') if provenance_data else 'unknown'

        # Clear uncommitted entities of this extraction_type for this case AND section
        # IMPORTANT: Only delete entities from the SAME section_type to preserve entities
        # from other sections (e.g., don't delete facts entities when running discussion)
        #
        # We find session_ids for this section_type from extraction_prompts, then
        # delete only entities with those session_ids
        from app.models import ExtractionPrompt
        same_section_sessions = [
            p.extraction_session_id
            for p in ExtractionPrompt.query.filter_by(
                case_id=case_id,
                concept_type=extraction_type,
                section_type=section_type
            ).all()
            if p.extraction_session_id
        ]

        deleted_count = 0
        if same_section_sessions:
            deleted_count = cls.query.filter(
                cls.case_id == case_id,
                cls.extraction_type == extraction_type,
                cls.is_published == False,
                cls.extraction_session_id.in_(same_section_sessions)
            ).delete(synchronize_session='fetch')

        if deleted_count > 0:
            logger.info(f"Cleared {deleted_count} uncommitted {extraction_type} entities for case {case_id} section_type={section_type}")

        # Store new classes with merge detection
        for class_info in rdf_data.get('new_classes', []):
            clean_class_info = cls._clean_json_data(class_info)
            match_decision = class_info.get('match_decision', {})

            # Check for existing entity from another section
            existing = cls._find_existing_entity(
                case_id, class_info['label'], extraction_type.capitalize(), extraction_session_id
            )

            if existing:
                # Merge into existing entity
                cls._merge_into_existing(existing, clean_class_info, section_type)
                created_entities.append(existing)
                merged_count += 1
                logger.info(f"Merged class '{class_info['label']}' from {section_type} into existing entity")
            else:
                # Initialize section tracking in JSON-LD
                clean_class_info['section_sources'] = [section_type]
                if clean_class_info.get('source_text'):
                    clean_class_info['source_texts'] = {section_type: clean_class_info['source_text']}

                entity = cls(
                    case_id=case_id,
                    extraction_session_id=extraction_session_id,
                    extraction_type=extraction_type,
                    storage_type='class',
                    ontology_target='proethica-intermediate',
                    entity_label=class_info['label'],
                    entity_uri=class_info['uri'],
                    entity_type=extraction_type.capitalize(),
                    entity_definition=class_info.get('definition', ''),
                    rdf_json_ld=clean_class_info,
                    extraction_model=extraction_model,
                    triple_count=len(class_info.get('properties', {})) + 4,
                    property_count=len(class_info.get('properties', {})),
                    provenance_metadata=provenance_data or {},
                    matched_ontology_uri=match_decision.get('matched_uri'),
                    matched_ontology_label=match_decision.get('matched_label'),
                    match_confidence=match_decision.get('confidence'),
                    match_method='llm' if match_decision.get('matches_existing') else None,
                    match_reasoning=match_decision.get('reasoning'),
                    is_selected=True
                )
                db.session.add(entity)
                created_entities.append(entity)

        # Store individuals with merge detection
        for indiv_info in rdf_data.get('new_individuals', []):
            clean_indiv_info = cls._clean_json_data(indiv_info)
            match_decision = indiv_info.get('match_decision', {})

            # Check for existing entity from another section
            existing = cls._find_existing_entity(
                case_id, indiv_info['label'], extraction_type.capitalize(), extraction_session_id
            )

            if existing:
                # Merge into existing entity
                cls._merge_into_existing(existing, clean_indiv_info, section_type)
                created_entities.append(existing)
                merged_count += 1
                logger.info(f"Merged individual '{indiv_info['label']}' from {section_type} into existing entity")
            else:
                # Initialize section tracking in JSON-LD
                clean_indiv_info['section_sources'] = [section_type]
                if clean_indiv_info.get('source_text'):
                    clean_indiv_info['source_texts'] = {section_type: clean_indiv_info['source_text']}

                entity = cls(
                    case_id=case_id,
                    extraction_session_id=extraction_session_id,
                    extraction_type=extraction_type,
                    storage_type='individual',
                    ontology_target=f'proethica-case-{case_id}',
                    entity_label=indiv_info['label'],
                    entity_uri=indiv_info['uri'],
                    entity_type=extraction_type.capitalize(),
                    entity_definition=indiv_info.get('definition', ''),
                    rdf_json_ld=clean_indiv_info,
                    extraction_model=extraction_model,
                    triple_count=len(indiv_info.get('properties', {})) + len(indiv_info.get('relationships', [])) + 2,
                    property_count=len(indiv_info.get('properties', {})),
                    relationship_count=len(indiv_info.get('relationships', [])),
                    provenance_metadata=provenance_data or {},
                    matched_ontology_uri=match_decision.get('matched_uri'),
                    matched_ontology_label=match_decision.get('matched_label'),
                    match_confidence=match_decision.get('confidence'),
                    match_method='llm' if match_decision.get('matches_existing') else None,
                    match_reasoning=match_decision.get('reasoning'),
                    is_selected=True
                )
                db.session.add(entity)
                created_entities.append(entity)

        db.session.commit()
        logger.info(f"Stored {len(created_entities)} {extraction_type} entities ({merged_count} merged from other sections)")
        return created_entities

    @classmethod
    def _find_existing_entity(cls, case_id: int, entity_label: str, entity_type: str, current_session_id: str):
        """Find an existing uncommitted entity with same label.

        Note: Since store_extraction_results now clears all uncommitted entities
        of the same extraction_type before storing, this method will typically
        return None. It's kept for potential future use or manual entity creation.
        """
        return cls.query.filter(
            cls.case_id == case_id,
            cls.entity_label == entity_label,
            cls.entity_type == entity_type,
            cls.is_published == False
        ).first()

    @classmethod
    def _merge_into_existing(cls, existing_entity, new_json_ld: dict, new_section_type: str):
        """Merge properties from new extraction into existing entity."""
        existing_json = existing_entity.rdf_json_ld or {}

        # Initialize section_sources if not present
        if 'section_sources' not in existing_json:
            existing_json['section_sources'] = []
            # Try to determine existing section from provenance
            if existing_entity.provenance_metadata and existing_entity.provenance_metadata.get('section_type'):
                existing_json['section_sources'].append(existing_entity.provenance_metadata['section_type'])

        # Add new section to sources
        if new_section_type not in existing_json['section_sources']:
            existing_json['section_sources'].append(new_section_type)

        # Merge properties
        existing_props = existing_json.get('properties', {})
        new_props = new_json_ld.get('properties', {})

        for prop_name, new_values in new_props.items():
            if not isinstance(new_values, list):
                new_values = [new_values]

            if prop_name not in existing_props:
                existing_props[prop_name] = new_values
            else:
                existing_values = existing_props[prop_name]
                if not isinstance(existing_values, list):
                    existing_values = [existing_values]

                for val in new_values:
                    if val and val not in existing_values and val != "None":
                        existing_values.append(val)

                existing_props[prop_name] = existing_values

        existing_json['properties'] = existing_props

        # Merge source texts with section labels
        if 'source_texts' not in existing_json:
            existing_json['source_texts'] = {}
            # Preserve existing source_text under its section
            if existing_json.get('source_text') and existing_json.get('section_sources'):
                first_section = existing_json['section_sources'][0] if existing_json['section_sources'] else 'unknown'
                existing_json['source_texts'][first_section] = existing_json['source_text']

        # Add new source text
        if new_json_ld.get('source_text'):
            existing_json['source_texts'][new_section_type] = new_json_ld['source_text']

        # Update main source_text as combined view
        combined_sources = []
        for section, text in existing_json.get('source_texts', {}).items():
            combined_sources.append(f"[{section}] {text}")
        if combined_sources:
            existing_json['source_text'] = " | ".join(combined_sources)

        # Merge definitions array
        existing_defs = existing_json.get('definitions', [])
        new_defs = new_json_ld.get('definitions', [])

        # Bootstrap existing definitions from scalar 'definition' if array is empty
        if not existing_defs and existing_json.get('definition'):
            existing_defs = [{
                'text': existing_json['definition'],
                'source_type': 'extraction',
                'source_section': existing_json.get('section_sources', ['unknown'])[0],
                'is_primary': True,
            }]

        # Append new definitions, skipping exact text duplicates
        existing_texts = {d.get('text', '') for d in existing_defs}
        for new_def in new_defs:
            new_text = new_def.get('text', '')
            if new_text and new_text not in existing_texts:
                new_def['is_primary'] = False
                existing_defs.append(new_def)
                existing_texts.add(new_text)

        existing_json['definitions'] = existing_defs

        # Merge relationships
        existing_rels = existing_json.get('relationships', [])
        new_rels = new_json_ld.get('relationships', [])

        existing_rel_keys = {(r.get('type'), r.get('target_uri')) for r in existing_rels}
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

    @classmethod
    def _clean_json_data(cls, data):
        """Clean data to ensure it's JSON-serializable.

        Removes any callable methods or non-serializable objects that might
        have accidentally been included in the data.
        """
        import json

        def clean_value(value):
            """Recursively clean a value for JSON serialization."""
            if callable(value):
                # Skip callable objects (methods, functions)
                return None
            elif isinstance(value, dict):
                # Recursively clean dictionary
                return {k: clean_value(v) for k, v in value.items() if clean_value(v) is not None}
            elif isinstance(value, (list, tuple)):
                # Recursively clean list/tuple
                cleaned = [clean_value(v) for v in value]
                return [v for v in cleaned if v is not None]
            elif isinstance(value, (str, int, float, bool, type(None))):
                # These types are JSON-serializable
                return value
            else:
                # Try to convert to string for other types
                try:
                    # Check if it's a built-in method or similar
                    str_val = str(value)
                    if 'built-in method' in str_val or 'method' in str_val:
                        return None
                    return str_val
                except:
                    return None

        return clean_value(data)