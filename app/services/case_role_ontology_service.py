"""
Case Role Ontology Service

Manages adding unmatched participant roles from cases to world-specific derived ontologies.
Creates and maintains case-roles-<world> ontologies that import the base world ontology.

This service:
- Creates derived ontologies for each world (e.g., case-roles-engineering)
- Adds unmatched participant roles with descriptions and capabilities
- Checks for duplicates before adding new roles
- Integrates with existing EntityService infrastructure
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import sessionmaker

from app import db
from app.models.ontology import Ontology
from app.models.ontology_import import OntologyImport
from app.models.world import World
from app.models.document import Document
from ontology_editor.services.entity_service import EntityService
from datetime import datetime

logger = logging.getLogger(__name__)

class CaseRoleOntologyService:
    """Service for managing case-derived role ontologies"""
    
    # Role-specific parent class in intermediate ontology
    ROLE_PARENT_CLASS = 'http://proethica.org/ontology/intermediate#Role'
    
    @classmethod
    def add_role_to_ontology(cls, 
                           role_name: str,
                           role_description: str,
                           world_id: int,
                           capabilities: List[str] = None,
                           case_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Add a new participant role to the world's case-roles derived ontology.
        
        Args:
            role_name: Name/label of the role (e.g., "Environmental Engineer")
            role_description: Description of the role and its responsibilities
            world_id: World ID to determine which derived ontology to use
            capabilities: Optional list of capabilities this role has
            case_id: Optional case ID for provenance tracking
            
        Returns:
            Dict with success status, entity_id, and any errors
        """
        try:
            logger.info(f"Adding role '{role_name}' to world {world_id} case-roles ontology")
            
            # Get the world to determine ontology domain
            world = World.query.get(world_id)
            if not world:
                return {
                    'success': False,
                    'error': f'World {world_id} not found',
                    'entity_id': None
                }
            
            # Get or create derived ontology for this world
            derived_ontology = cls._get_or_create_case_roles_ontology(world)
            if not derived_ontology:
                return {
                    'success': False,
                    'error': f'Failed to create case-roles ontology for world {world_id}',
                    'entity_id': None
                }
            
            # Check for existing roles to avoid duplicates
            existing_roles = cls._get_existing_role_labels(derived_ontology.id)
            
            # Check for duplicates (case-insensitive)
            if any(existing.lower() == role_name.lower() for existing in existing_roles):
                logger.info(f"Role '{role_name}' already exists in derived ontology")
                return {
                    'success': False,
                    'error': f'Role "{role_name}" already exists in the ontology',
                    'entity_id': None,
                    'duplicate': True
                }
            
            # Build comprehensive description
            full_description = role_description
            
            # Add capabilities to description if provided
            if capabilities and len(capabilities) > 0:
                full_description += f"\n\nCapabilities: {', '.join(capabilities)}"
            
            # Add provenance information
            if case_id:
                case = Document.query.get(case_id)
                if case:
                    full_description += f"\n\nSource: Added from case '{case.title}' (Case {case_id})"
            
            # Prepare entity data for EntityService
            entity_data = {
                'label': role_name,
                'description': full_description,
                'parent_class': cls.ROLE_PARENT_CLASS,
                'proethica_category': 'role'
            }
            
            # Add capabilities as structured metadata if provided
            if capabilities:
                entity_data['capabilities'] = capabilities
            
            # Create entity in derived ontology using existing EntityService
            success, result = EntityService.create_entity(
                ontology_id=derived_ontology.id,
                entity_data=entity_data,
                commit_message=f"Added case role: {role_name} from case {case_id}" if case_id else f"Added case role: {role_name}"
            )
            
            if success and result:
                logger.info(f"Successfully created role entity: {role_name} -> {result.get('entity_id')}")
                return {
                    'success': True,
                    'entity_id': result.get('entity_id'),
                    'ontology_id': derived_ontology.id,
                    'role_name': role_name
                }
            else:
                error_msg = result.get('error', 'Unknown error from EntityService') if result else 'No result from EntityService'
                logger.error(f"Failed to create role entity '{role_name}': {error_msg}")
                return {
                    'success': False,
                    'error': f'Failed to create role entity: {error_msg}',
                    'entity_id': None
                }
                
        except Exception as e:
            logger.error(f"Error adding role '{role_name}' to ontology: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'Exception while adding role: {str(e)}',
                'entity_id': None
            }
    
    @classmethod
    def _get_or_create_case_roles_ontology(cls, world: World) -> Optional[Ontology]:
        """Get or create the case-roles derived ontology for a world."""
        try:
            # Determine derived ontology domain based on world's main ontology
            base_ontology_domain = world.ontology_id or 'engineering-ethics'
            derived_domain = f"case-roles-{base_ontology_domain}"
            
            # Check if derived ontology already exists
            derived_ontology = Ontology.query.filter_by(domain_id=derived_domain).first()
            
            if derived_ontology:
                logger.info(f"Using existing case-roles ontology: {derived_domain}")
                return derived_ontology
            
            # Create new derived ontology
            logger.info(f"Creating new case-roles ontology: {derived_domain}")
            
            derived_ontology = Ontology(
                domain_id=derived_domain,
                name=f"{world.name} - Case Roles",
                description=f"Case-derived participant roles for {world.name}. "
                           f"Contains roles extracted from cases that were not found in the base ontology.",
                world_id=world.id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.session.add(derived_ontology)
            db.session.flush()  # Get ID
            
            # Create import relationship to base ontology
            base_ontology = Ontology.query.filter_by(domain_id=base_ontology_domain).first()
            if base_ontology:
                ontology_import = OntologyImport(
                    ontology_id=derived_ontology.id,
                    imported_ontology_id=base_ontology.id,
                    import_type='extends',
                    created_at=datetime.utcnow()
                )
                db.session.add(ontology_import)
                logger.info(f"Created import relationship: {derived_domain} imports {base_ontology_domain}")
            else:
                logger.warning(f"Base ontology '{base_ontology_domain}' not found for import")
            
            db.session.commit()
            logger.info(f"Successfully created derived ontology: {derived_domain}")
            return derived_ontology
            
        except Exception as e:
            logger.error(f"Error creating case-roles ontology for world {world.id}: {str(e)}", exc_info=True)
            db.session.rollback()
            return None
    
    @classmethod
    def _get_existing_role_labels(cls, ontology_id: int) -> List[str]:
        """Get all existing role labels from the derived ontology to check for duplicates."""
        try:
            # Use EntityService to get entities from the ontology
            entities_result = EntityService.get_entities(ontology_id, entity_type='role')
            
            if entities_result and entities_result.get('success'):
                entities = entities_result.get('entities', [])
                return [entity.get('label', '') for entity in entities if entity.get('label')]
            else:
                logger.info(f"No existing role entities found in ontology {ontology_id}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting existing role labels from ontology {ontology_id}: {str(e)}", exc_info=True)
            return []
    
    @classmethod
    def check_role_exists(cls, role_name: str, world_id: int) -> bool:
        """Check if a role already exists in the world's case-roles ontology."""
        try:
            world = World.query.get(world_id)
            if not world:
                return False
            
            base_ontology_domain = world.ontology_id or 'engineering-ethics'
            derived_domain = f"case-roles-{base_ontology_domain}"
            
            derived_ontology = Ontology.query.filter_by(domain_id=derived_domain).first()
            if not derived_ontology:
                return False
            
            existing_roles = cls._get_existing_role_labels(derived_ontology.id)
            return any(existing.lower() == role_name.lower() for existing in existing_roles)
            
        except Exception as e:
            logger.error(f"Error checking if role '{role_name}' exists: {str(e)}", exc_info=True)
            return False
    
    @classmethod
    def get_case_roles_ontology_stats(cls, world_id: int) -> Dict[str, Any]:
        """Get statistics about the case-roles ontology for a world."""
        try:
            world = World.query.get(world_id)
            if not world:
                return {'exists': False, 'error': 'World not found'}
            
            base_ontology_domain = world.ontology_id or 'engineering-ethics'
            derived_domain = f"case-roles-{base_ontology_domain}"
            
            derived_ontology = Ontology.query.filter_by(domain_id=derived_domain).first()
            if not derived_ontology:
                return {'exists': False, 'domain': derived_domain}
            
            existing_roles = cls._get_existing_role_labels(derived_ontology.id)
            
            return {
                'exists': True,
                'ontology_id': derived_ontology.id,
                'domain': derived_domain,
                'name': derived_ontology.name,
                'role_count': len(existing_roles),
                'roles': existing_roles[:10],  # First 10 for preview
                'created_at': derived_ontology.created_at.isoformat() if derived_ontology.created_at else None
            }
            
        except Exception as e:
            logger.error(f"Error getting case-roles ontology stats for world {world_id}: {str(e)}", exc_info=True)
            return {'exists': False, 'error': str(e)}