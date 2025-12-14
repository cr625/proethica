"""
Domain configuration module for ProEthica.

Provides domain-specific configuration for different professional ethics domains
(engineering, education, medical, legal). Each domain has its own ethical framework,
founding good, professional virtues, and principle mappings.
"""

from app.domains.domain_config import DomainConfig, get_domain_config

__all__ = ['DomainConfig', 'get_domain_config']
