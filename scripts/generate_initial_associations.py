#!/usr/bin/env python3
"""
Generate Initial Guideline Associations

This script generates enhanced guideline associations for existing cases
using the new EnhancedGuidelineAssociationService.

Usage:
    python scripts/generate_initial_associations.py [--case-id CASE_ID] [--limit N]

Author: Claude Code
Date: June 9, 2025
"""

import sys
import os
import argparse
import logging
from datetime import datetime

# Add project root to path  
sys.path.insert(0, '/home/chris/proethica')
os.chdir('/home/chris/proethica')

from app import create_app, db
from app.models.scenario import Scenario as Case  # Use Scenario model which contains cases
from app.services.enhanced_guideline_association_service import EnhancedGuidelineAssociationService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Generate initial guideline associations')
    parser.add_argument('--case-id', type=int, help='Generate associations for specific case ID')
    parser.add_argument('--limit', type=int, default=10, help='Limit number of cases to process')
    parser.add_argument('--test', action='store_true', help='Test mode - analyze without saving')
    
    args = parser.parse_args()
    
    # Create Flask app context
    app = create_app()
    with app.app_context():
        
        logger.info("Starting guideline association generation")
        
        # Initialize service
        service = EnhancedGuidelineAssociationService()
        
        if args.case_id:
            # Process specific case
            logger.info(f"Processing case {args.case_id}")
            
            try:
                if args.test:
                    associations = service.generate_associations_for_case(args.case_id)
                    print_association_summary(args.case_id, associations)
                else:
                    count = service.generate_and_save_associations_for_case(args.case_id)
                    logger.info(f"Generated {count} associations for case {args.case_id}")
                    
            except Exception as e:
                logger.error(f"Error processing case {args.case_id}: {e}")
                return 1
                
        else:
            # Process multiple cases
            logger.info(f"Processing up to {args.limit} cases")
            
            # Get cases with document structure  
            cases = Case.query.filter(
                Case.scenario_metadata.isnot(None)
            ).limit(args.limit).all()
            
            logger.info(f"Found {len(cases)} cases to process")
            
            if args.test:
                # Test mode - analyze first case only
                if cases:
                    test_case = cases[0]
                    logger.info(f"Testing with case {test_case.id}: {test_case.name}")
                    associations = service.generate_associations_for_case(test_case.id)
                    print_association_summary(test_case.id, associations)
            else:
                # Production mode - process all cases
                case_ids = [case.id for case in cases]
                stats = service.batch_generate_associations(case_ids)
                
                logger.info("Batch processing complete:")
                logger.info(f"  Total associations: {stats['total_associations']}")
                logger.info(f"  Successful cases: {stats['successful_cases']}")
                logger.info(f"  Failed cases: {stats['failed_cases']}")
                logger.info(f"  Total cases: {stats['total_cases']}")
                
        logger.info("Association generation complete")
        return 0

def print_association_summary(case_id: int, associations):
    """Print detailed summary of generated associations"""
    
    print(f"\n=== Association Summary for Case {case_id} ===")
    print(f"Total associations: {len(associations)}")
    
    if not associations:
        print("No associations generated")
        return
        
    # Group by section type
    by_section = {}
    for assoc in associations:
        section = assoc.section_type
        if section not in by_section:
            by_section[section] = []
        by_section[section].append(assoc)
        
    for section_type, section_assocs in by_section.items():
        print(f"\n--- {section_type.upper()} Section ({len(section_assocs)} associations) ---")
        
        # Sort by confidence
        section_assocs.sort(key=lambda a: a.score.overall_confidence, reverse=True)
        
        for i, assoc in enumerate(section_assocs[:5]):  # Show top 5
            score = assoc.score
            print(f"  {i+1}. Confidence: {score.overall_confidence:.3f}")
            print(f"     Semantic: {score.semantic_similarity:.3f}, "
                  f"Keyword: {score.keyword_overlap:.3f}, "
                  f"Contextual: {score.contextual_relevance:.3f}")
            print(f"     Concept ID: {assoc.guideline_concept_id}")
            print(f"     Pattern indicators: {len(assoc.pattern_indicators)} keys")
            print(f"     Reasoning: {score.reasoning[:100]}...")
            print()
            
        if len(section_assocs) > 5:
            print(f"     ... and {len(section_assocs) - 5} more")
            
    # Overall statistics
    confidences = [a.score.overall_confidence for a in associations]
    avg_confidence = sum(confidences) / len(confidences)
    max_confidence = max(confidences)
    min_confidence = min(confidences)
    
    print(f"\n--- Overall Statistics ---")
    print(f"Average confidence: {avg_confidence:.3f}")
    print(f"Max confidence: {max_confidence:.3f}")
    print(f"Min confidence: {min_confidence:.3f}")
    print(f"High confidence (>0.7): {sum(1 for c in confidences if c > 0.7)}")
    print(f"Medium confidence (0.4-0.7): {sum(1 for c in confidences if 0.4 <= c <= 0.7)}")
    print(f"Low confidence (<0.4): {sum(1 for c in confidences if c < 0.4)}")

if __name__ == '__main__':
    exit(main())