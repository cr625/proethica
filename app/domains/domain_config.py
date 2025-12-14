"""
Domain configuration loader for ProEthica.

Loads domain-specific configuration from YAML files in config/domains/.
Each domain (engineering, education, etc.) has its own configuration file
defining ethical frameworks, founding goods, and principle mappings.
"""

import os
import yaml
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from functools import lru_cache

logger = logging.getLogger(__name__)

# Path to domain configuration files
DOMAINS_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'config', 'domains'
)


@dataclass
class EthicalFramework:
    """Configuration for the domain's ethical analysis framework."""
    name: str
    methodology: str  # e.g., 'line_drawing', 'principlist', 'casuist'
    citation: str = ""
    steps: List[str] = field(default_factory=list)


@dataclass
class ProvisionStructure:
    """Configuration for how code provisions are structured in this domain."""
    code_name: str
    hierarchy: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class DomainConfig:
    """
    Complete configuration for a professional ethics domain.

    Attributes:
        name: Domain identifier (e.g., 'engineering', 'education')
        display_name: Human-readable name
        description: Brief description of the domain
        founding_good: The fundamental good this profession serves
        founding_good_description: Explanation of the founding good
        professional_virtues: List of virtues required in this profession
        ethical_framework: Framework for ethical analysis
        principle_mapping: Maps domain principles to Beauchamp & Childress categories
        provision_structure: How code provisions are organized
        role_vocabulary: Common role types in this domain
        ontology_namespace: RDF namespace for domain ontology
        raw_config: Original YAML configuration dict
    """
    name: str
    display_name: str
    description: str = ""
    founding_good: str = ""
    founding_good_description: str = ""
    professional_virtues: List[str] = field(default_factory=list)
    ethical_framework: EthicalFramework = field(default_factory=lambda: EthicalFramework(
        name="Generic", methodology="generic"
    ))
    principle_mapping: Dict[str, str] = field(default_factory=dict)
    provision_structure: ProvisionStructure = field(default_factory=lambda: ProvisionStructure(
        code_name="Unknown"
    ))
    role_vocabulary: List[str] = field(default_factory=list)
    ontology_namespace: str = ""
    raw_config: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'DomainConfig':
        """
        Load domain configuration from a YAML file.

        Args:
            yaml_path: Path to the YAML configuration file

        Returns:
            DomainConfig instance
        """
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)

        # Parse ethical framework
        ef_config = config.get('ethical_framework', {})
        ethical_framework = EthicalFramework(
            name=ef_config.get('name', 'Unknown'),
            methodology=ef_config.get('methodology', 'generic'),
            citation=ef_config.get('citation', ''),
            steps=ef_config.get('steps', [])
        )

        # Parse provision structure
        ps_config = config.get('provision_structure', {})
        provision_structure = ProvisionStructure(
            code_name=ps_config.get('code_name', 'Unknown'),
            hierarchy=ps_config.get('hierarchy', [])
        )

        # Extract role vocabulary from extraction_patterns if present
        role_vocabulary = config.get('role_vocabulary', [])
        if not role_vocabulary:
            extraction_patterns = config.get('extraction_patterns', {})
            role_vocabulary = extraction_patterns.get('stakeholder_keywords', [])

        return cls(
            name=config.get('name', os.path.basename(yaml_path).replace('.yaml', '')),
            display_name=config.get('display_name', config.get('name', 'Unknown')),
            description=config.get('description', ''),
            founding_good=config.get('founding_good', ''),
            founding_good_description=config.get('founding_good_description', ''),
            professional_virtues=config.get('professional_virtues', []),
            ethical_framework=ethical_framework,
            principle_mapping=config.get('principle_mapping', {}),
            provision_structure=provision_structure,
            role_vocabulary=role_vocabulary,
            ontology_namespace=config.get('ontology_namespace', ''),
            raw_config=config
        )

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the raw config by key."""
        return self.raw_config.get(key, default)


@lru_cache(maxsize=10)
def get_domain_config(domain_code: str = 'engineering') -> DomainConfig:
    """
    Load and cache domain configuration.

    Args:
        domain_code: Domain identifier (e.g., 'engineering', 'education')

    Returns:
        DomainConfig instance for the specified domain

    Raises:
        FileNotFoundError: If domain configuration file doesn't exist
        ValueError: If configuration is invalid
    """
    yaml_path = os.path.join(DOMAINS_CONFIG_DIR, f'{domain_code}.yaml')

    if not os.path.exists(yaml_path):
        available = list_available_domains()
        raise FileNotFoundError(
            f"Domain configuration not found: {domain_code}. "
            f"Available domains: {available}"
        )

    try:
        config = DomainConfig.from_yaml(yaml_path)
        logger.info(f"Loaded domain configuration: {domain_code}")
        return config
    except Exception as e:
        logger.error(f"Failed to load domain config {domain_code}: {e}")
        raise ValueError(f"Invalid domain configuration: {e}")


def list_available_domains() -> List[str]:
    """
    List all available domain configurations.

    Returns:
        List of domain codes that have configuration files
    """
    if not os.path.exists(DOMAINS_CONFIG_DIR):
        return []

    domains = []
    for filename in os.listdir(DOMAINS_CONFIG_DIR):
        if filename.endswith('.yaml'):
            domains.append(filename.replace('.yaml', ''))

    return sorted(domains)


def clear_domain_cache() -> None:
    """Clear the domain configuration cache."""
    get_domain_config.cache_clear()
