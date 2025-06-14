"""Domain Registry service for managing multiple domains in ProEthica."""

import os
import yaml
import logging
from typing import Dict, List, Optional, Type
from pathlib import Path

from app.models.domain_config import DomainConfig
from app.services.case_deconstruction.base_adapter import BaseCaseDeconstructionAdapter
from app.services.case_deconstruction.engineering_ethics_adapter import EngineeringEthicsAdapter


logger = logging.getLogger(__name__)


class DomainRegistry:
    """Central registry for managing available domains in ProEthica.
    
    This singleton service:
    - Loads domain configurations from YAML files
    - Provides access to domain configs and adapters
    - Manages domain validation and registration
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._domains: Dict[str, DomainConfig] = {}
            self._adapter_classes: Dict[str, Type[BaseCaseDeconstructionAdapter]] = {}
            self._config_dir = Path("config/domains")
            self._register_builtin_adapters()
            self._load_domain_configs()
            self.__class__._initialized = True
    
    def _register_builtin_adapters(self):
        """Register built-in adapter classes."""
        # Register existing adapters
        self._adapter_classes["EngineeringEthicsAdapter"] = EngineeringEthicsAdapter
        
        # Future adapters will be registered here:
        # self._adapter_classes["MedicalEthicsAdapter"] = MedicalEthicsAdapter
        # self._adapter_classes["LegalEthicsAdapter"] = LegalEthicsAdapter
    
    def _load_domain_configs(self):
        """Load all domain configurations from the config directory."""
        # Create config directory if it doesn't exist
        self._config_dir.mkdir(parents=True, exist_ok=True)
        
        # If no configs exist, create a default engineering config
        if not any(self._config_dir.glob("*.yaml")):
            self._create_default_engineering_config()
        
        # Load all YAML files in the config directory
        for config_file in self._config_dir.glob("*.yaml"):
            try:
                with open(config_file, 'r') as f:
                    data = yaml.safe_load(f)
                    
                domain_config = DomainConfig.from_dict(data)
                
                # Validate the configuration
                errors = domain_config.validate()
                if errors:
                    logger.error(f"Invalid domain config {config_file}: {errors}")
                    continue
                
                # Register the domain
                self._domains[domain_config.name] = domain_config
                logger.info(f"Loaded domain configuration: {domain_config.name}")
                
            except Exception as e:
                logger.error(f"Failed to load domain config {config_file}: {e}")
    
    def _create_default_engineering_config(self):
        """Create a default engineering domain configuration."""
        engineering_config = {
            "name": "engineering",
            "display_name": "Engineering Ethics",
            "description": "NSPE-based engineering ethics analysis",
            "adapter_class_name": "EngineeringEthicsAdapter",
            
            "guideline_sections": [
                "facts",
                "question",
                "discussion", 
                "conclusion",
                "dissenting_opinion"
            ],
            
            "case_sections": [
                "scenario_description",
                "ethical_considerations", 
                "stakeholder_analysis",
                "decision_points",
                "recommendations"
            ],
            
            "extraction_patterns": {
                "stakeholder_keywords": [
                    "engineer", "client", "public", "employer",
                    "employee", "contractor", "government", "company"
                ],
                "decision_indicators": [
                    "should", "must", "shall", "shall not",
                    "obligation", "duty", "responsibility", "required"
                ],
                "ethical_principles": [
                    "safety", "integrity", "competence", "honesty",
                    "fairness", "transparency", "accountability"
                ]
            },
            
            "section_mappings": {
                "facts": "case_facts",
                "question": "ethical_question",
                "discussion": "ethical_analysis",
                "conclusion": "ethical_conclusion",
                "dissenting_opinion": "minority_view"
            },
            
            "ontology_namespace": "http://proethica.org/ontology/engineering#",
            
            "ontology_concepts": {
                "competence": "eng:Competence",
                "safety": "eng:PublicSafety",
                "integrity": "eng:ProfessionalIntegrity",
                "honesty": "eng:Honesty",
                "judgment": "eng:ProfessionalJudgment"
            },
            
            "mcp_modules": [
                "guideline_analysis_module",
                "ontology_query_module"
            ],
            
            "ui_templates": {
                "guideline_display": "domain/engineering_guidelines.html",
                "case_analysis": "domain/engineering_case_analysis.html"
            },
            
            "metadata": {
                "source": "NSPE Code of Ethics",
                "version": "2019",
                "professional_body": "National Society of Professional Engineers"
            }
        }
        
        # Save to file
        config_path = self._config_dir / "engineering.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(engineering_config, f, default_flow_style=False, sort_keys=False)
        
        logger.info("Created default engineering domain configuration")
    
    def register_domain(self, config: DomainConfig) -> None:
        """Register a new domain configuration.
        
        Args:
            config: The domain configuration to register
            
        Raises:
            ValueError: If the configuration is invalid
        """
        errors = config.validate()
        if errors:
            raise ValueError(f"Invalid domain configuration: {errors}")
        
        self._domains[config.name] = config
        logger.info(f"Registered domain: {config.name}")
    
    def get_domain(self, name: str) -> Optional[DomainConfig]:
        """Get a domain configuration by name.
        
        Args:
            name: The domain name
            
        Returns:
            The domain configuration or None if not found
        """
        return self._domains.get(name)
    
    def list_domains(self) -> List[str]:
        """List all registered domain names.
        
        Returns:
            List of domain names
        """
        return list(self._domains.keys())
    
    def get_all_domains(self) -> Dict[str, DomainConfig]:
        """Get all registered domains.
        
        Returns:
            Dictionary mapping domain names to configurations
        """
        return self._domains.copy()
    
    def create_adapter(self, domain_name: str) -> BaseCaseDeconstructionAdapter:
        """Create an adapter instance for the specified domain.
        
        Args:
            domain_name: The name of the domain
            
        Returns:
            An instance of the domain's adapter
            
        Raises:
            ValueError: If domain not found or adapter class not registered
        """
        domain_config = self.get_domain(domain_name)
        if not domain_config:
            raise ValueError(f"Domain not found: {domain_name}")
        
        adapter_class_name = domain_config.adapter_class_name
        adapter_class = self._adapter_classes.get(adapter_class_name)
        
        if not adapter_class:
            raise ValueError(f"Adapter class not registered: {adapter_class_name}")
        
        # Create and return the adapter instance
        return adapter_class()
    
    def register_adapter_class(self, name: str, adapter_class: Type[BaseCaseDeconstructionAdapter]):
        """Register a new adapter class.
        
        Args:
            name: The adapter class name
            adapter_class: The adapter class
        """
        self._adapter_classes[name] = adapter_class
        logger.info(f"Registered adapter class: {name}")
    
    def reload_configs(self):
        """Reload all domain configurations from disk."""
        self._domains.clear()
        self._load_domain_configs()
        logger.info("Reloaded domain configurations")


# Create singleton instance
domain_registry = DomainRegistry()