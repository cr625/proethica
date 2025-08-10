"""
Concept Hierarchy Service

This service resolves and displays hierarchical relationships between concepts,
showing the path from BFO through intermediate types to specific domain concepts.
"""

import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ConceptHierarchy:
    """Represents a concept's hierarchical path."""
    
    def __init__(self, concept_uri: str, concept_label: str):
        self.concept_uri = concept_uri
        self.concept_label = concept_label
        self.hierarchy_path: List[Tuple[str, str]] = []  # [(level_name, level_label), ...]
        self.primary_type: Optional[str] = None
        self.semantic_label: Optional[str] = None
        
    def add_level(self, level_name: str, level_label: str):
        """Add a level to the hierarchy path."""
        self.hierarchy_path.append((level_name, level_label))
    
    def get_display_path(self) -> List[str]:
        """Get the hierarchy path for display."""
        return [label for _, label in self.hierarchy_path]
    
    def get_full_path_string(self) -> str:
        """Get the full hierarchy as a string."""
        path = self.get_display_path()
        if path:
            return " → ".join(path) + f" → {self.concept_label}"
        return self.concept_label


class ConceptHierarchyService:
    """Service for resolving concept hierarchies."""
    
    def __init__(self):
        # Mapping from 8 intermediate types to their display names and BFO parents
        self.intermediate_types = {
            'role': {
                'display': 'Role',
                'bfo_parent': 'Independent Continuant',
                'description': 'Professional positions and stakeholders'
            },
            'principle': {
                'display': 'Principle', 
                'bfo_parent': 'Specifically Dependent Continuant',
                'description': 'Ethical values and standards'
            },
            'obligation': {
                'display': 'Obligation',
                'bfo_parent': 'Realizable Entity', 
                'description': 'Professional duties and responsibilities'
            },
            'state': {
                'display': 'State',
                'bfo_parent': 'Quality',
                'description': 'Conditions and situations'
            },
            'resource': {
                'display': 'Resource',
                'bfo_parent': 'Material Entity',
                'description': 'Physical and informational entities'
            },
            'action': {
                'display': 'Action',
                'bfo_parent': 'Process',
                'description': 'Intentional activities'
            },
            'event': {
                'display': 'Event', 
                'bfo_parent': 'Process',
                'description': 'Occurrences and happenings'
            },
            'capability': {
                'display': 'Capability',
                'bfo_parent': 'Disposition',
                'description': 'Skills and competencies'
            }
        }
        
        # Common domain-level concepts that act as intermediate classes
        self.domain_intermediates = {
            'stakeholder': 'Professional Role',
            'ethical_principle': 'Ethics Framework',
            'professional_duty': 'Professional Obligation',
            'safety_principle': 'Safety Framework',
            'competence': 'Professional Capability',
            'engineering_document': 'Technical Resource',
            'safety_incident': 'Safety Event',
            'design_action': 'Engineering Process'
        }
    
    def get_concept_hierarchy(self, concept: Dict) -> ConceptHierarchy:
        """
        Resolve the full hierarchy for a concept.
        
        Args:
            concept: Dictionary with concept information including:
                   - label: concept name
                   - primary_type: one of the 8 intermediate types
                   - semantic_label: LLM-suggested semantic description
                   - original_llm_type: original type from LLM
                   
        Returns:
            ConceptHierarchy object with full path
        """
        concept_label = concept.get('label', 'Unknown Concept')
        concept_uri = f"http://proethica.org/ontology/{concept_label.lower().replace(' ', '_')}"
        
        hierarchy = ConceptHierarchy(concept_uri, concept_label)
        hierarchy.primary_type = concept.get('primary_type') or concept.get('type', '').lower()
        hierarchy.semantic_label = concept.get('semantic_label')
        
        # 1. Add BFO level (top of hierarchy)
        if hierarchy.primary_type in self.intermediate_types:
            bfo_parent = self.intermediate_types[hierarchy.primary_type]['bfo_parent']
            hierarchy.add_level('bfo', bfo_parent)
        
        # 2. Add Intermediate level (8 core types)
        if hierarchy.primary_type in self.intermediate_types:
            intermediate_info = self.intermediate_types[hierarchy.primary_type]
            hierarchy.add_level('intermediate', intermediate_info['display'])
        
        # 3. Add Domain level (if identifiable)
        domain_level = self._infer_domain_level(concept)
        if domain_level:
            hierarchy.add_level('domain', domain_level)
        
        # 4. The specific concept is the final level (added by get_full_path_string)
        
        return hierarchy
    
    def _infer_domain_level(self, concept: Dict) -> Optional[str]:
        """
        Infer domain-level classification from semantic labels.
        
        This creates an intermediate layer between the 8 core types and specific concepts.
        """
        semantic_label = (concept.get('semantic_label') or 
                         concept.get('original_llm_type') or 
                         concept.get('category', '')).lower()
        
        primary_type = concept.get('primary_type') or concept.get('type', '').lower()
        
        # Role domain classifications
        if primary_type == 'role':
            if 'stakeholder' in semantic_label or 'public' in semantic_label:
                return 'Stakeholder Role'
            elif 'professional' in semantic_label or 'engineer' in semantic_label:
                return 'Professional Role'
            elif 'client' in semantic_label or 'customer' in semantic_label:
                return 'Client Role'
            else:
                return 'Professional Role'  # Default for roles
        
        # Principle domain classifications  
        elif primary_type == 'principle':
            if 'safety' in semantic_label:
                return 'Safety Principle'
            elif 'ethical' in semantic_label or 'ethics' in semantic_label:
                return 'Ethics Framework'
            elif 'professional' in semantic_label:
                return 'Professional Standard'
            elif 'public' in semantic_label:
                return 'Public Interest Principle'
            else:
                return 'Ethics Framework'  # Default for principles
        
        # Obligation domain classifications
        elif primary_type == 'obligation':
            if 'professional' in semantic_label:
                return 'Professional Obligation'
            elif 'safety' in semantic_label:
                return 'Safety Obligation'
            elif 'public' in semantic_label:
                return 'Public Service Obligation'
            else:
                return 'Professional Obligation'  # Default for obligations
                
        # Capability domain classifications
        elif primary_type == 'capability':
            if 'technical' in semantic_label or 'engineering' in semantic_label:
                return 'Technical Capability'
            elif 'professional' in semantic_label:
                return 'Professional Capability' 
            elif 'ethical' in semantic_label:
                return 'Ethical Capability'
            else:
                return 'Professional Capability'  # Default for capabilities
        
        # Action domain classifications
        elif primary_type == 'action':
            if 'design' in semantic_label or 'engineering' in semantic_label:
                return 'Engineering Process'
            elif 'safety' in semantic_label:
                return 'Safety Process'
            elif 'communication' in semantic_label or 'report' in semantic_label:
                return 'Communication Process'
            else:
                return 'Professional Process'  # Default for actions
        
        # State domain classifications
        elif primary_type == 'state':
            if 'conflict' in semantic_label:
                return 'Conflict State'
            elif 'safety' in semantic_label or 'hazard' in semantic_label:
                return 'Safety State'
            elif 'professional' in semantic_label:
                return 'Professional State'
            else:
                return 'Environmental State'  # Default for states
                
        # Resource domain classifications
        elif primary_type == 'resource':
            if 'document' in semantic_label or 'specification' in semantic_label:
                return 'Technical Resource'
            elif 'standard' in semantic_label or 'code' in semantic_label:
                return 'Standard Resource'
            else:
                return 'Information Resource'  # Default for resources
                
        # Event domain classifications  
        elif primary_type == 'event':
            if 'safety' in semantic_label or 'incident' in semantic_label:
                return 'Safety Event'
            elif 'project' in semantic_label or 'milestone' in semantic_label:
                return 'Project Event'
            elif 'review' in semantic_label or 'audit' in semantic_label:
                return 'Assessment Event'
            else:
                return 'Professional Event'  # Default for events
        
        return None
    
    def get_hierarchy_summary(self, concepts: List[Dict]) -> Dict[str, int]:
        """
        Get summary statistics of concept hierarchies.
        
        Returns:
            Dictionary with counts by hierarchy level
        """
        summary = {
            'total_concepts': len(concepts),
            'by_primary_type': {},
            'by_domain_level': {},
            'with_hierarchy': 0
        }
        
        for concept in concepts:
            hierarchy = self.get_concept_hierarchy(concept)
            
            # Count by primary type
            if hierarchy.primary_type:
                summary['by_primary_type'][hierarchy.primary_type] = \
                    summary['by_primary_type'].get(hierarchy.primary_type, 0) + 1
            
            # Count by domain level
            if len(hierarchy.hierarchy_path) >= 3:  # BFO + Intermediate + Domain
                domain_level = hierarchy.hierarchy_path[2][1]  # Get domain level label
                summary['by_domain_level'][domain_level] = \
                    summary['by_domain_level'].get(domain_level, 0) + 1
                summary['with_hierarchy'] += 1
        
        return summary
    
    def format_hierarchy_for_display(self, hierarchy: ConceptHierarchy, 
                                   format_type: str = 'breadcrumb') -> str:
        """
        Format hierarchy for different display contexts.
        
        Args:
            hierarchy: ConceptHierarchy object
            format_type: 'breadcrumb', 'tree', 'compact'
            
        Returns:
            Formatted string for display
        """
        if format_type == 'breadcrumb':
            path = hierarchy.get_display_path()
            if path:
                return ' → '.join(path) + f' → <strong>{hierarchy.concept_label}</strong>'
            return f'<strong>{hierarchy.concept_label}</strong>'
            
        elif format_type == 'tree':
            lines = []
            indent = ""
            for i, (_, label) in enumerate(hierarchy.hierarchy_path):
                lines.append(f"{indent}├─ {label}")
                indent += "  "
            lines.append(f"{indent}└─ <strong>{hierarchy.concept_label}</strong>")
            return '<br>'.join(lines)
            
        elif format_type == 'compact':
            if hierarchy.hierarchy_path:
                # Show only the most specific levels
                if len(hierarchy.hierarchy_path) >= 2:
                    domain = hierarchy.hierarchy_path[-1][1]  # Most specific
                    intermediate = hierarchy.hierarchy_path[-2][1] if len(hierarchy.hierarchy_path) >= 2 else ""
                    return f"{intermediate} → {domain} → <strong>{hierarchy.concept_label}</strong>"
                else:
                    return f"{hierarchy.hierarchy_path[0][1]} → <strong>{hierarchy.concept_label}</strong>"
            return f'<strong>{hierarchy.concept_label}</strong>'
        
        return hierarchy.get_full_path_string()