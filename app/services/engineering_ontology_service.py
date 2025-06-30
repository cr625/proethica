"""
Engineering Ontology Service for ProEthica.

Provides specialized access to engineering-specific ontology concepts
to enhance FIRAC analysis and case understanding.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from app.models import db
from app.models.entity_triple import EntityTriple
from app.models.ontology import Ontology


@dataclass
class EngineeringRole:
    """Represents an engineering role from the ontology with source attribution."""
    uri: str
    label: str
    description: str
    capabilities: List[str]
    responsibilities: List[str]
    source: str = ""  # Authority/standard source (NSPE, ISO, etc.)
    external_ref: str = ""  # External reference URL


@dataclass
class EngineeringArtifact:
    """Represents an engineering artifact/document type with source attribution."""
    uri: str
    label: str
    description: str
    related_roles: List[str]
    typical_content: List[str]
    source: str = ""  # Authority/standard source (ISO, IEEE, etc.)
    external_ref: str = ""  # External reference URL


@dataclass
class EngineeringProcess:
    """Represents an engineering process or methodology."""
    uri: str
    label: str
    description: str
    involved_roles: List[str]
    required_artifacts: List[str]


@dataclass
class EngineeringStandard:
    """Represents an engineering standard or code with source attribution."""
    uri: str
    label: str
    description: str
    applicable_domains: List[str]
    enforcement_roles: List[str]
    source: str = ""  # Authority/standard organization (ISO, IEEE, NSPE, etc.)
    external_ref: str = ""  # Official reference URL


class EngineeringOntologyService:
    """
    Service for accessing and utilizing engineering-specific ontology concepts.
    
    Enhances case analysis by providing structured knowledge about:
    - Engineering roles and their capabilities
    - Engineering artifacts and documents
    - Engineering processes and methodologies
    - Professional standards and codes
    """
    
    def __init__(self):
        """Initialize the engineering ontology service."""
        self.logger = logging.getLogger(f"{__name__}.EngineeringOntologyService")
        
        # Predefined mappings of engineering concepts with authoritative sources
        # All concepts below are properly cited with ISO standards, NSPE codes, and other authorities
        self.engineering_roles = {
            'structural_engineer': EngineeringRole(
                uri='http://proethica.org/ontology/engineering-ethics#StructuralEngineerRole',
                label='Structural Engineer',
                description='Engineer specializing in structural analysis and design per NSPE categories',
                capabilities=['structural_analysis', 'structural_design', 'safety_assessment'],
                responsibilities=['public_safety', 'structural_integrity', 'code_compliance'],
                source='NSPE Professional Categories; IFC/ISO 16739-1:2018',
                external_ref='https://www.nspe.org/resources/ethics/code-ethics'
            ),
            'electrical_engineer': EngineeringRole(
                uri='http://proethica.org/ontology/engineering-ethics#ElectricalEngineerRole',
                label='Electrical Engineer',
                description='Engineer specializing in electrical power systems per IEC standards',
                capabilities=['electrical_design', 'power_systems', 'safety_analysis'],
                responsibilities=['electrical_safety', 'system_reliability', 'code_compliance'],
                source='NSPE Professional Categories; IEC 61508 Functional Safety',
                external_ref='https://www.nspe.org/resources/ethics/code-ethics'
            ),
            'mechanical_engineer': EngineeringRole(
                uri='http://proethica.org/ontology/engineering-ethics#MechanicalEngineerRole',
                label='Mechanical Engineer',
                description='Engineer specializing in mechanical systems per ASME standards',
                capabilities=['mechanical_design', 'hvac_systems', 'thermal_analysis'],
                responsibilities=['system_efficiency', 'safety', 'environmental_compliance'],
                source='NSPE Professional Categories; ASME Standards',
                external_ref='https://www.asme.org/codes-standards'
            ),
            'consulting_engineer': EngineeringRole(
                uri='http://proethica.org/ontology/engineering-ethics#ConsultingEngineerRole',
                label='Consulting Engineer',
                description='Independent engineering consultant per NSPE Code Section II.3',
                capabilities=['expert_consultation', 'technical_review', 'forensic_analysis'],
                responsibilities=['objective_analysis', 'professional_independence', 'client_service'],
                source='NSPE Code of Ethics Section II.3',
                external_ref='https://www.nspe.org/resources/ethics/code-ethics'
            ),
            'project_engineer': EngineeringRole(
                uri='http://proethica.org/ontology/engineering-ethics#ProjectEngineerRole',
                label='Project Engineer',
                description='Engineer responsible for project management per PMI and ISO standards',
                capabilities=['project_management', 'coordination', 'technical_oversight'],
                responsibilities=['project_delivery', 'team_coordination', 'quality_assurance'],
                source='PMI PMBOK; ISO 21500:2012 Project Management',
                external_ref='https://www.iso.org/standard/50003.html'
            )
        }
        
        self.engineering_artifacts = {
            'engineering_report': EngineeringArtifact(
                uri='http://proethica.org/ontology/engineering-ethics#EngineeringReport',
                label='Engineering Report',
                description='Formal technical report per ISO/IEC/IEEE standards',
                related_roles=['structural_engineer', 'consulting_engineer'],
                typical_content=['analysis_results', 'recommendations', 'technical_data'],
                source='ISO/IEC/IEEE 15289:2019 - Content of systems and software life cycle information items',
                external_ref='https://www.iso.org/standard/74909.html'
            ),
            'engineering_drawing': EngineeringArtifact(
                uri='http://proethica.org/ontology/engineering-ethics#EngineeringDrawing',
                label='Engineering Drawing',
                description='Technical drawings conforming to ISO standards',
                related_roles=['structural_engineer', 'mechanical_engineer', 'electrical_engineer'],
                typical_content=['dimensions', 'specifications', 'materials', 'tolerances'],
                source='ISO 128 - Technical drawings; ISO 5455 - Technical drawings - Scales',
                external_ref='https://www.iso.org/standard/3098.html'
            ),
            'engineering_specification': EngineeringArtifact(
                uri='http://proethica.org/ontology/engineering-ethics#EngineeringSpecification',
                label='Engineering Specification',
                description='Requirements document per ISO/IEC/IEEE standards',
                related_roles=['project_engineer', 'consulting_engineer'],
                typical_content=['requirements', 'standards', 'performance_criteria'],
                source='ISO/IEC/IEEE 29148:2018 - Requirements engineering',
                external_ref='https://www.iso.org/standard/72089.html'
            ),
            'inspection_report': EngineeringArtifact(
                uri='http://proethica.org/ontology/engineering-ethics#InspectionReport',
                label='Inspection Report',
                description='Inspection documentation per ISO conformity assessment',
                related_roles=['consulting_engineer', 'structural_engineer'],
                typical_content=['observations', 'deficiencies', 'recommendations', 'photos'],
                source='ISO/IEC 17020:2012 - Requirements for inspection bodies',
                external_ref='https://www.iso.org/standard/52994.html'
            ),
            'as_built_drawings': EngineeringArtifact(
                uri='http://proethica.org/ontology/engineering-ethics#AsBuiltDrawings',
                label='As-Built Drawings',
                description='Construction documentation per ISO vocabulary standards',
                related_roles=['project_engineer', 'structural_engineer'],
                typical_content=['actual_dimensions', 'field_changes', 'final_configuration'],
                source='ISO 6707-1:2020 - Buildings and civil engineering works vocabulary',
                external_ref='https://www.iso.org/standard/69524.html'
            )
        }
        
        self.engineering_standards = {
            'building_code': EngineeringStandard(
                uri='http://proethica.org/ontology/engineering-ethics#BuildingCode',
                label='Building Code',
                description='Legal requirements for construction safety per international standards',
                applicable_domains=['structural', 'electrical', 'mechanical'],
                enforcement_roles=['building_official', 'regulatory_engineer'],
                source='IBC - International Building Code; ISO 6707-1:2020',
                external_ref='https://www.iccsafe.org/'
            ),
            'nspe_code': EngineeringStandard(
                uri='http://proethica.org/ontology/engineering-ethics#NSPECode',
                label='NSPE Code of Ethics',
                description='Professional ethics code for engineers in the United States',
                applicable_domains=['all_engineering'],
                enforcement_roles=['professional_engineer', 'engineering_board'],
                source='National Society of Professional Engineers, 2019 Edition',
                external_ref='https://www.nspe.org/resources/ethics/code-ethics'
            )
        }
    
    def identify_engineering_roles_in_case(self, case_content: str) -> List[EngineeringRole]:
        """
        Identify engineering roles mentioned in case content.
        
        Args:
            case_content: Text content of the case
            
        Returns:
            List of identified engineering roles
        """
        identified_roles = []
        content_lower = case_content.lower()
        
        # Check for role keywords
        role_keywords = {
            'structural_engineer': ['structural engineer', 'structural', 'building structure'],
            'electrical_engineer': ['electrical engineer', 'electrical', 'power system'],
            'mechanical_engineer': ['mechanical engineer', 'mechanical', 'hvac', 'heating'],
            'consulting_engineer': ['consulting engineer', 'consultant', 'consulting'],
            'project_engineer': ['project engineer', 'project manager', 'project']
        }
        
        for role_key, keywords in role_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                identified_roles.append(self.engineering_roles[role_key])
        
        return identified_roles
    
    def identify_engineering_artifacts_in_case(self, case_content: str) -> List[EngineeringArtifact]:
        """
        Identify engineering artifacts mentioned in case content.
        
        Args:
            case_content: Text content of the case
            
        Returns:
            List of identified engineering artifacts
        """
        identified_artifacts = []
        content_lower = case_content.lower()
        
        # Check for artifact keywords
        artifact_keywords = {
            'engineering_report': ['engineering report', 'technical report', 'structural report'],
            'engineering_drawing': ['engineering drawing', 'drawings', 'blueprints', 'plans'],
            'engineering_specification': ['specification', 'specs', 'requirements'],
            'inspection_report': ['inspection report', 'inspection', 'survey report'],
            'as_built_drawings': ['as-built', 'as built', 'record drawings']
        }
        
        for artifact_key, keywords in artifact_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                identified_artifacts.append(self.engineering_artifacts[artifact_key])
        
        return identified_artifacts
    
    def identify_engineering_standards_in_case(self, case_content: str) -> List[EngineeringStandard]:
        """
        Identify engineering standards referenced in case content.
        
        Args:
            case_content: Text content of the case
            
        Returns:
            List of identified engineering standards
        """
        identified_standards = []
        content_lower = case_content.lower()
        
        # Check for standard keywords
        standard_keywords = {
            'building_code': ['building code', 'code', 'building standard', 'safety code'],
            'nspe_code': ['nspe', 'code of ethics', 'professional ethics', 'engineering ethics']
        }
        
        for standard_key, keywords in standard_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                identified_standards.append(self.engineering_standards[standard_key])
        
        return identified_standards
    
    def get_role_capabilities_for_analysis(self, roles: List[EngineeringRole]) -> Dict[str, List[str]]:
        """
        Get capabilities required for the identified roles.
        
        Args:
            roles: List of engineering roles
            
        Returns:
            Dictionary mapping role labels to their capabilities
        """
        return {role.label: role.capabilities for role in roles}
    
    def get_ethical_considerations_for_roles(self, roles: List[EngineeringRole]) -> List[str]:
        """
        Get ethical considerations relevant to the identified roles.
        
        Args:
            roles: List of engineering roles
            
        Returns:
            List of ethical considerations
        """
        all_responsibilities = []
        for role in roles:
            all_responsibilities.extend(role.responsibilities)
        
        # Remove duplicates and add role-specific ethical considerations
        unique_responsibilities = list(set(all_responsibilities))
        
        ethical_considerations = []
        for responsibility in unique_responsibilities:
            if responsibility == 'public_safety':
                ethical_considerations.append('Engineers must prioritize public safety above all other considerations')
            elif responsibility == 'professional_independence':
                ethical_considerations.append('Engineers must maintain professional independence and objectivity')
            elif responsibility == 'code_compliance':
                ethical_considerations.append('Engineers must ensure compliance with applicable codes and standards')
            elif responsibility == 'client_service':
                ethical_considerations.append('Engineers must serve clients faithfully while maintaining professional integrity')
        
        return ethical_considerations
    
    def analyze_competence_boundaries(self, case_content: str, identified_roles: List[EngineeringRole]) -> Dict[str, Any]:
        """
        Analyze competence boundaries based on identified roles and case requirements.
        
        Args:
            case_content: Text content of the case
            identified_roles: List of identified engineering roles
            
        Returns:
            Dictionary with competence analysis
        """
        content_lower = case_content.lower()
        
        # Identify technical domains mentioned
        technical_domains = []
        domain_keywords = {
            'structural': ['structural', 'foundation', 'beam', 'column', 'load'],
            'electrical': ['electrical', 'wiring', 'power', 'circuit'],
            'mechanical': ['mechanical', 'hvac', 'heating', 'cooling', 'ventilation'],
            'civil': ['civil', 'site', 'grading', 'drainage'],
            'software': ['software', 'programming', 'algorithm', 'code']
        }
        
        for domain, keywords in domain_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                technical_domains.append(domain)
        
        # Analyze competence match
        role_domains = {
            'Structural Engineer': ['structural', 'civil'],
            'Electrical Engineer': ['electrical'],
            'Mechanical Engineer': ['mechanical'],
            'Consulting Engineer': ['structural', 'electrical', 'mechanical', 'civil'],  # Broad expertise
            'Project Engineer': ['structural', 'electrical', 'mechanical', 'civil']  # Coordination role
        }
        
        competence_analysis = {
            'required_domains': technical_domains,
            'available_expertise': {},
            'competence_gaps': [],
            'boundary_issues': []
        }
        
        # Check each identified role against required domains
        for role in identified_roles:
            role_label = role.label
            if role_label in role_domains:
                available_domains = role_domains[role_label]
                competence_analysis['available_expertise'][role_label] = available_domains
                
                # Check for gaps
                missing_domains = set(technical_domains) - set(available_domains)
                if missing_domains:
                    competence_analysis['competence_gaps'].extend([
                        f"{role_label} may lack expertise in {domain}" 
                        for domain in missing_domains
                    ])
        
        # Check for boundary issues
        if len(technical_domains) > 1 and len(identified_roles) == 1:
            competence_analysis['boundary_issues'].append(
                "Case involves multiple technical domains but only one engineering role identified"
            )
        
        return competence_analysis
    
    def get_ontology_concepts_for_case(self, case_id: int) -> List[Dict[str, Any]]:
        """
        Get engineering ontology concepts already associated with a case.
        
        Args:
            case_id: ID of the case
            
        Returns:
            List of ontology concepts with engineering context
        """
        try:
            # Get entity triples for this case
            entity_triples = EntityTriple.query.filter_by(
                entity_id=case_id,
                entity_type='case'
            ).all()
            
            concepts = []
            for triple in entity_triples:
                if 'engineering-ethics' in triple.object_uri:
                    concept_info = {
                        'uri': triple.object_uri,
                        'predicate': triple.predicate,
                        'confidence': triple.metadata.get('confidence', 0.8),
                        'engineering_context': self._get_engineering_context_for_uri(triple.object_uri)
                    }
                    concepts.append(concept_info)
            
            return concepts
            
        except Exception as e:
            self.logger.warning(f"Could not retrieve ontology concepts for case {case_id}: {e}")
            return []
    
    def _get_engineering_context_for_uri(self, uri: str) -> Dict[str, Any]:
        """Get engineering-specific context for an ontology URI."""
        
        # Check if URI matches known engineering concepts
        for role_key, role in self.engineering_roles.items():
            if role.uri == uri:
                return {
                    'type': 'engineering_role',
                    'label': role.label,
                    'capabilities': role.capabilities,
                    'responsibilities': role.responsibilities
                }
        
        for artifact_key, artifact in self.engineering_artifacts.items():
            if artifact.uri == uri:
                return {
                    'type': 'engineering_artifact',
                    'label': artifact.label,
                    'related_roles': artifact.related_roles,
                    'typical_content': artifact.typical_content
                }
        
        for standard_key, standard in self.engineering_standards.items():
            if standard.uri == uri:
                return {
                    'type': 'engineering_standard',
                    'label': standard.label,
                    'applicable_domains': standard.applicable_domains,
                    'enforcement_roles': standard.enforcement_roles
                }
        
        return {
            'type': 'unknown_engineering_concept',
            'label': uri.split('#')[-1].replace('_', ' ').title()
        }


# Create singleton instance
engineering_ontology_service = EngineeringOntologyService()