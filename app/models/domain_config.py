"""Domain configuration model for multi-domain support in ProEthica."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class DomainConfig:
    """Configuration for a specific domain in ProEthica.
    
    This class defines all the settings and patterns needed to process
    documents and cases for a particular professional domain (e.g., engineering,
    medical, legal ethics).
    """
    
    # Basic domain information
    name: str                              # "engineering", "medical", etc.
    display_name: str                      # "Engineering Ethics"
    description: str                       # Human-readable description
    adapter_class_name: str                # "EngineeringEthicsAdapter"
    
    # Document processing configuration
    guideline_sections: List[str] = field(default_factory=list)  # ["facts", "discussion", etc.]
    case_sections: List[str] = field(default_factory=list)       # ["scenario", "analysis", etc.]
    
    # Extraction patterns for domain-specific content
    extraction_patterns: Dict[str, Any] = field(default_factory=dict)
    # Example:
    # {
    #     "stakeholder_keywords": ["engineer", "client", "public"],
    #     "decision_indicators": ["should", "must", "shall not"],
    #     "ethical_principles": ["safety", "integrity", "competence"]
    # }
    
    # Section mappings for document structure
    section_mappings: Dict[str, str] = field(default_factory=dict)
    # Maps generic section names to domain-specific ones
    # Example: {"facts": "case_facts", "conclusion": "ethical_conclusion"}
    
    # Ontology configuration
    ontology_namespace: str = ""           # "http://proethica.org/ontology/engineering#"
    ontology_concepts: Dict[str, str] = field(default_factory=dict)
    # Maps domain concepts to ontology URIs
    # Example: {"competence": "eng:Competence", "safety": "eng:PublicSafety"}
    
    # MCP modules required for this domain
    mcp_modules: List[str] = field(default_factory=list)
    # Example: ["guideline_analysis_module", "ontology_query_module"]
    
    # UI configuration
    ui_templates: Dict[str, str] = field(default_factory=dict)
    # Custom templates for domain-specific display
    # Example: {"guideline_display": "engineering_guidelines.html"}
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Any domain-specific configuration not covered above
    
    def get_adapter_class(self):
        """Dynamically import and return the adapter class for this domain."""
        # This will be implemented when we have the adapter factory
        # For now, return the class name
        return self.adapter_class_name
    
    def validate(self) -> List[str]:
        """Validate the domain configuration.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not self.name:
            errors.append("Domain name is required")
        elif not self.name.replace("_", "").isalnum():
            errors.append("Domain name must be alphanumeric (underscores allowed)")
            
        if not self.display_name:
            errors.append("Display name is required")
            
        if not self.adapter_class_name:
            errors.append("Adapter class name is required")
            
        if not self.ontology_namespace:
            errors.append("Ontology namespace is required")
            
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the configuration to a dictionary for serialization."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "adapter_class_name": self.adapter_class_name,
            "guideline_sections": self.guideline_sections,
            "case_sections": self.case_sections,
            "extraction_patterns": self.extraction_patterns,
            "section_mappings": self.section_mappings,
            "ontology_namespace": self.ontology_namespace,
            "ontology_concepts": self.ontology_concepts,
            "mcp_modules": self.mcp_modules,
            "ui_templates": self.ui_templates,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DomainConfig":
        """Create a DomainConfig from a dictionary (e.g., from YAML)."""
        return cls(
            name=data.get("name", ""),
            display_name=data.get("display_name", ""),
            description=data.get("description", ""),
            adapter_class_name=data.get("adapter_class_name", ""),
            guideline_sections=data.get("guideline_sections", []),
            case_sections=data.get("case_sections", []),
            extraction_patterns=data.get("extraction_patterns", {}),
            section_mappings=data.get("section_mappings", {}),
            ontology_namespace=data.get("ontology_namespace", ""),
            ontology_concepts=data.get("ontology_concepts", {}),
            mcp_modules=data.get("mcp_modules", []),
            ui_templates=data.get("ui_templates", {}),
            metadata=data.get("metadata", {})
        )