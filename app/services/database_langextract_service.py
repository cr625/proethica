"""
Database-Driven LangExtract Service for ProEthica

This service extends the ontology-driven LangExtract functionality by using
database-stored examples instead of hardcoded ones, allowing for dynamic
example management through the prompt builder interface.
"""

import os
import logging
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from datetime import datetime

from .ontology_driven_langextract_service import OntologyDrivenLangExtractService
from ..models.prompt_templates import LangExtractExample

if TYPE_CHECKING:
    from langextract import data

logger = logging.getLogger(__name__)


class DatabaseLangExtractService(OntologyDrivenLangExtractService):
    """
    Database-driven LangExtract service that dynamically loads examples
    from the database instead of using hardcoded examples.
    """
    
    def __init__(self):
        """Initialize the database-driven service"""
        super().__init__()
        self.use_database_examples = os.environ.get('USE_DATABASE_LANGEXTRACT_EXAMPLES', 'true').lower() == 'true'
        logger.info(f"DatabaseLangExtractService initialized - Database examples: {self.use_database_examples}")
    
    def _create_section_type_examples(self, section_type_info: Dict[str, Any], 
                                     case_domain: str) -> List['data.ExampleData']:
        """
        Create LangExtract examples using database-stored examples instead of hardcoded ones
        
        Args:
            section_type_info: Section type information from ontology
            case_domain: Professional domain
            
        Returns:
            List of examples for this section type
        """
        
        if not self.use_database_examples:
            # Fall back to parent implementation if database examples disabled
            return super()._create_section_type_examples(section_type_info, case_domain)
        
        section_type = section_type_info['type']
        section_label = section_type_info['label']
        
        logger.debug(f"Loading database examples for section type: {section_type}, domain: {case_domain}")
        
        try:
            # Load examples from database based on section type and domain
            examples = self._load_database_examples(section_type, case_domain)
            
            if examples:
                logger.info(f"Loaded {len(examples)} database examples for {section_type} in {case_domain}")
                return examples
            else:
                # No database examples found, try generic domain
                logger.info(f"No specific examples found for {case_domain}, trying generic domain")
                generic_examples = self._load_database_examples(section_type, 'generic')
                
                if generic_examples:
                    logger.info(f"Loaded {len(generic_examples)} generic examples for {section_type}")
                    return generic_examples
                else:
                    # Fall back to hardcoded examples
                    logger.warning(f"No database examples found for {section_type}, falling back to hardcoded examples")
                    return super()._create_section_type_examples(section_type_info, case_domain)
        
        except Exception as e:
            logger.error(f"Error loading database examples: {e}")
            # Fall back to hardcoded examples on error
            return super()._create_section_type_examples(section_type_info, case_domain)
    
    def _load_database_examples(self, section_type: str, domain: str) -> List['data.ExampleData']:
        """
        Load examples from database for a specific section type and domain
        
        Args:
            section_type: Section type (e.g., 'FactualSection', 'EthicalQuestionSection')
            domain: Professional domain (e.g., 'engineering_ethics', 'generic')
            
        Returns:
            List of LangExtract ExampleData objects
        """
        
        try:
            # Map section types to example types
            section_to_example_type = {
                'FactualSection': 'factual',
                'EthicalQuestionSection': 'question', 
                'AnalysisSection': 'analysis',
                'ConclusionSection': 'conclusion',
                'CodeReferenceSection': 'code_reference',
                'DissentingOpinionSection': 'dissenting'
            }
            
            example_type = section_to_example_type.get(section_type, 'generic')
            
            # Query database for matching examples
            db_examples = LangExtractExample.query.filter_by(
                example_type=example_type,
                domain=domain,
                active=True
            ).order_by(LangExtractExample.priority.desc()).all()
            
            # Convert database examples to LangExtract format
            langextract_examples = []
            for db_example in db_examples:
                try:
                    langextract_data = db_example.to_langextract_data()
                    langextract_examples.append(langextract_data)
                    
                    # Update usage statistics
                    db_example.usage_count += 1
                    # Note: We don't commit here to avoid transaction issues
                    # The service calling this should handle commits
                    
                except Exception as e:
                    logger.error(f"Error converting database example {db_example.id} to LangExtract format: {e}")
                    continue
            
            logger.debug(f"Successfully converted {len(langextract_examples)} database examples for {section_type}/{domain}")
            return langextract_examples
            
        except Exception as e:
            logger.error(f"Database query error for {section_type}/{domain}: {e}")
            return []
    
    def get_example_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about example usage for analytics
        
        Returns:
            Dictionary with usage statistics
        """
        
        try:
            from ..models import db
            from sqlalchemy import func, text
            
            # Get overall statistics
            stats = db.session.execute(text("""
                SELECT 
                    COUNT(*) as total_examples,
                    COUNT(DISTINCT domain) as total_domains,
                    COUNT(DISTINCT example_type) as total_types,
                    SUM(usage_count) as total_usage,
                    AVG(effectiveness_score) as avg_effectiveness
                FROM langextract_examples 
                WHERE active = true
            """)).fetchone()
            
            # Get usage by domain and type
            domain_stats = db.session.execute(text("""
                SELECT 
                    domain,
                    example_type,
                    COUNT(*) as example_count,
                    SUM(usage_count) as domain_usage,
                    AVG(effectiveness_score) as domain_effectiveness
                FROM langextract_examples 
                WHERE active = true 
                GROUP BY domain, example_type
                ORDER BY domain, example_type
            """)).fetchall()
            
            return {
                'overall': {
                    'total_examples': stats.total_examples or 0,
                    'total_domains': stats.total_domains or 0,
                    'total_types': stats.total_types or 0,
                    'total_usage': stats.total_usage or 0,
                    'avg_effectiveness': round(stats.avg_effectiveness, 2) if stats.avg_effectiveness else None
                },
                'by_domain': [
                    {
                        'domain': stat.domain,
                        'example_type': stat.example_type,
                        'example_count': stat.example_count,
                        'usage': stat.domain_usage or 0,
                        'effectiveness': round(stat.domain_effectiveness, 2) if stat.domain_effectiveness else None
                    } for stat in domain_stats
                ],
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting example statistics: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def validate_example_coverage(self) -> Dict[str, Any]:
        """
        Validate that we have adequate example coverage for different domains and section types
        
        Returns:
            Validation report with recommendations
        """
        
        try:
            from ..models import db
            from sqlalchemy import text
            
            # Check coverage by domain and section type
            coverage = db.session.execute(text("""
                SELECT 
                    domain,
                    example_type,
                    COUNT(*) as example_count,
                    MIN(priority) as min_priority,
                    MAX(priority) as max_priority
                FROM langextract_examples 
                WHERE active = true 
                GROUP BY domain, example_type
            """)).fetchall()
            
            # Analyze coverage
            recommendations = []
            coverage_report = []
            
            for stat in coverage:
                coverage_item = {
                    'domain': stat.domain,
                    'example_type': stat.example_type,
                    'example_count': stat.example_count,
                    'priority_range': f"{stat.min_priority}-{stat.max_priority}",
                    'adequacy': 'good' if stat.example_count >= 2 else 'needs_improvement'
                }
                coverage_report.append(coverage_item)
                
                if stat.example_count < 2:
                    recommendations.append({
                        'domain': stat.domain,
                        'example_type': stat.example_type,
                        'recommendation': f'Add more examples (currently only {stat.example_count})',
                        'priority': 'medium'
                    })
            
            # Check for missing combinations
            expected_combinations = [
                ('engineering_ethics', 'factual'),
                ('engineering_ethics', 'question'),
                ('engineering_ethics', 'analysis'),
                ('generic', 'factual'),
                ('generic', 'question'),
                ('generic', 'analysis')
            ]
            
            existing_combinations = {(stat.domain, stat.example_type) for stat in coverage}
            missing_combinations = set(expected_combinations) - existing_combinations
            
            for domain, example_type in missing_combinations:
                recommendations.append({
                    'domain': domain,
                    'example_type': example_type,
                    'recommendation': f'Create examples for {domain}/{example_type} combination',
                    'priority': 'high'
                })
            
            return {
                'coverage_report': coverage_report,
                'recommendations': recommendations,
                'total_domains': len(set(stat.domain for stat in coverage)),
                'total_types': len(set(stat.example_type for stat in coverage)),
                'missing_combinations': len(missing_combinations),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error validating example coverage: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }