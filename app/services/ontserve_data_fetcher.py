"""
OntServe Data Fetcher Service

Fetches live entity data from OntServe for synchronization with ProEthica.
"""

import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import json

logger = logging.getLogger(__name__)


class OntServeDataFetcher:
    """Service for fetching live entity data from OntServe."""

    def __init__(self, ontserve_url: str = "http://localhost:8082",
                 db_host: str = "localhost",
                 db_name: str = "ontserve",
                 db_user: str = "postgres",
                 db_password: str = "PASS"):
        """Initialize the OntServe data fetcher.

        Args:
            ontserve_url: Base URL for OntServe MCP server
            db_host: PostgreSQL host for direct database access
            db_name: OntServe database name
            db_user: Database user
            db_password: Database password
        """
        self.ontserve_url = ontserve_url
        self.db_config = {
            'host': db_host,
            'database': db_name,
            'user': db_user,
            'password': db_password
        }

    def fetch_case_entities_from_db(self, case_id: int) -> Dict[str, List[Dict]]:
        """Fetch all entities for a case directly from OntServe database.

        Args:
            case_id: The case ID to fetch entities for

        Returns:
            Dictionary with 'classes' and 'individuals' lists
        """
        try:
            conn = psycopg2.connect(**self.db_config, cursor_factory=RealDictCursor)
            cursor = conn.cursor()

            result = {
                'classes': [],
                'individuals': [],
                'sync_timestamp': datetime.utcnow().isoformat()
            }

            # Fetch classes from proethica-engineering-extracted
            cursor.execute("""
                SELECT
                    oe.uri,
                    oe.label,
                    oe.entity_type,
                    oe.parent_uri,
                    oe.comment,
                    oe.properties,
                    o.name as ontology_name
                FROM ontology_entities oe
                JOIN ontologies o ON oe.ontology_id = o.id
                WHERE o.name = 'proethica-engineering-extracted'
                ORDER BY oe.label
            """)

            classes = cursor.fetchall()
            result['classes'] = [dict(row) for row in classes]

            # Fetch individuals from proethica-case-N
            case_ontology_name = f'proethica-case-{case_id}'
            cursor.execute("""
                SELECT
                    oe.uri,
                    oe.label,
                    oe.entity_type,
                    oe.parent_uri,
                    oe.comment,
                    oe.properties,
                    o.name as ontology_name
                FROM ontology_entities oe
                JOIN ontologies o ON oe.ontology_id = o.id
                WHERE o.name = %s
                ORDER BY oe.label
            """, (case_ontology_name,))

            individuals = cursor.fetchall()
            result['individuals'] = [dict(row) for row in individuals]

            cursor.close()
            conn.close()

            logger.info(f"Fetched {len(result['classes'])} classes and {len(result['individuals'])} individuals for case {case_id}")
            return result

        except Exception as e:
            logger.error(f"Error fetching entities from OntServe database: {e}")
            return {'classes': [], 'individuals': [], 'error': str(e)}

    def fetch_entity_by_uri(self, entity_uri: str) -> Optional[Dict]:
        """Fetch a single entity by URI from OntServe.

        Args:
            entity_uri: The URI of the entity to fetch

        Returns:
            Entity data or None if not found
        """
        try:
            conn = psycopg2.connect(**self.db_config, cursor_factory=RealDictCursor)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    oe.*,
                    o.name as ontology_name
                FROM ontology_entities oe
                JOIN ontologies o ON oe.ontology_id = o.id
                WHERE oe.uri = %s
            """, (entity_uri,))

            result = cursor.fetchone()
            cursor.close()
            conn.close()

            return dict(result) if result else None

        except Exception as e:
            logger.error(f"Error fetching entity {entity_uri}: {e}")
            return None

    def compare_with_proethica(self, ontserve_entity: Dict, proethica_entity: Dict) -> Dict:
        """Compare OntServe entity with ProEthica version to detect changes.

        Args:
            ontserve_entity: Live entity data from OntServe
            proethica_entity: Cached entity data from ProEthica

        Returns:
            Comparison result with change details
        """
        changes = []

        # Compare label (main field to check)
        ontserve_label = ontserve_entity.get('label', '')
        proethica_label = proethica_entity.get('entity_label', '')

        if ontserve_label != proethica_label:
            changes.append({
                'field': 'label',
                'ontserve_value': ontserve_label,
                'proethica_value': proethica_label
            })

        # Compare parent_uri
        ontserve_parent = ontserve_entity.get('parent_uri')
        proethica_parent = proethica_entity.get('parent_uri')

        if ontserve_parent != proethica_parent:
            changes.append({
                'field': 'parent_uri',
                'ontserve_value': ontserve_parent,
                'proethica_value': proethica_parent
            })

        # Compare comment/description
        ontserve_comment = ontserve_entity.get('comment', '')
        proethica_description = proethica_entity.get('description', '')

        # Only compare if both have values
        if ontserve_comment and proethica_description and ontserve_comment != proethica_description:
            changes.append({
                'field': 'description',
                'ontserve_value': ontserve_comment,
                'proethica_value': proethica_description
            })

        return {
            'has_changes': len(changes) > 0,
            'changes': changes,
            'change_count': len(changes),
            'comparison_timestamp': datetime.utcnow().isoformat()
        }

    def refresh_committed_entities(self, case_id: int, proethica_entities: List[Dict]) -> Dict:
        """Refresh ProEthica's committed entities with live OntServe data.

        Args:
            case_id: The case ID
            proethica_entities: List of ProEthica entities to refresh

        Returns:
            Refresh result with statistics and change details
        """
        result = {
            'refreshed': 0,
            'unchanged': 0,
            'modified': 0,
            'not_found': 0,
            'errors': 0,
            'details': [],
            'timestamp': datetime.utcnow().isoformat()
        }

        # Fetch all OntServe entities for this case
        ontserve_data = self.fetch_case_entities_from_db(case_id)

        # Create lookup dictionary for OntServe entities by URI
        ontserve_by_uri = {}
        for entity in ontserve_data['classes'] + ontserve_data['individuals']:
            ontserve_by_uri[entity['uri']] = entity

        # Compare each ProEthica entity with OntServe version
        for pe_entity in proethica_entities:
            entity_uri = pe_entity.get('entity_uri')

            if not entity_uri:
                result['errors'] += 1
                result['details'].append({
                    'entity_label': pe_entity.get('entity_label'),
                    'status': 'error',
                    'message': 'No URI found'
                })
                continue

            ontserve_entity = ontserve_by_uri.get(entity_uri)

            if not ontserve_entity:
                result['not_found'] += 1
                result['details'].append({
                    'entity_uri': entity_uri,
                    'entity_label': pe_entity.get('entity_label'),
                    'status': 'not_found',
                    'message': 'Entity not found in OntServe'
                })
                continue

            # Compare entities
            comparison = self.compare_with_proethica(ontserve_entity, pe_entity)

            if comparison['has_changes']:
                result['modified'] += 1
                result['details'].append({
                    'entity_uri': entity_uri,
                    'entity_label': pe_entity.get('entity_label'),
                    'status': 'modified',
                    'changes': comparison['changes'],
                    'ontserve_data': ontserve_entity
                })
            else:
                result['unchanged'] += 1
                result['details'].append({
                    'entity_uri': entity_uri,
                    'entity_label': pe_entity.get('entity_label'),
                    'status': 'unchanged'
                })

            result['refreshed'] += 1

        logger.info(f"Refreshed {result['refreshed']} entities for case {case_id}: "
                   f"{result['modified']} modified, {result['unchanged']} unchanged, "
                   f"{result['not_found']} not found")

        return result