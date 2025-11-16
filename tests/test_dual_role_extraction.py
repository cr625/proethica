#!/usr/bin/env python3
"""
Test script for dual role extraction system
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

# Initialize Flask app context
from app import create_app
app = create_app()

from app.services.extraction.dual_role_extractor import DualRoleExtractor

# Sample case text for testing
CASE_8_SAMPLE_TEXT = """
The stormwater management project involves several key professionals. Dr. Sarah Jones, a geotechnical risk assessor with PE License #12345, conducted the comprehensive site investigation focusing on seismic hazards and soil stability. She has 15 years of experience in geotechnical engineering and works for GeoTech Consulting LLC.

John Smith, the licensed professional engineer and project lead, oversees the entire infrastructure design. He holds PE certification and reports directly to the client representative at Acme Engineering Corp.

The project also involves Maria Rodriguez, who serves as the community liaison engineer, a relatively new role that bridges technical engineering decisions with community stakeholder concerns. She facilitates public meetings and ensures community feedback is integrated into design decisions.

Additionally, the project requires coordination with the City's stormwater compliance officer, Robert Chen, who ensures all designs meet current environmental regulations and drainage standards.
"""

def test_dual_role_extraction():
    """Test the dual role extraction on sample case text"""
    print("=== Testing Dual Role Extraction ===\n")

    with app.app_context():
        try:
            # Initialize extractor
            extractor = DualRoleExtractor()
            print("✓ DualRoleExtractor initialized")

            # Test extraction
            print("\nExtracting roles from case text...")
            candidate_classes, role_individuals = extractor.extract_dual_roles(
                case_text=CASE_8_SAMPLE_TEXT,
                case_id=8,
                section_type="facts"
            )

            # Display results
            print(f"\n=== EXTRACTION RESULTS ===")
            print(f"Candidate Role Classes Found: {len(candidate_classes)}")
            print(f"Role Individuals Found: {len(role_individuals)}")

            print(f"\n=== CANDIDATE ROLE CLASSES ===")
            for i, candidate in enumerate(candidate_classes, 1):
                print(f"\n{i}. {candidate.label}")
                print(f"   Definition: {candidate.definition}")
                print(f"   Distinguishing Features: {candidate.distinguishing_features}")
                print(f"   Professional Scope: {candidate.professional_scope}")
                print(f"   Qualifications: {candidate.typical_qualifications}")
                print(f"   Similarity to Existing: {candidate.similarity_to_existing:.2f}")
                print(f"   Similar Classes: {candidate.existing_similar_classes}")

            print(f"\n=== ROLE INDIVIDUALS ===")
            for i, individual in enumerate(role_individuals, 1):
                print(f"\n{i}. {individual.name}")
                print(f"   Role: {individual.role_class}")
                print(f"   Is New Role Class: {individual.is_new_role_class}")
                print(f"   Attributes: {individual.attributes}")
                print(f"   Relationships: {individual.relationships}")

            # Generate summary
            summary = extractor.get_extraction_summary(candidate_classes, role_individuals)
            print(f"\n=== SUMMARY ===")
            for key, value in summary.items():
                print(f"{key}: {value}")

            print("\n✓ Test completed successfully!")

        except Exception as e:
            print(f"✗ Test failed with error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_dual_role_extraction()