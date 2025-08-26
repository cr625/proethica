#!/usr/bin/env python3
"""
Enhanced Roles Integration Patch

This demonstrates how to integrate the generalized concept splitting
into the existing RolesExtractor with minimal changes.

This is a patch file showing the exact integration pattern.
"""

import os
from typing import List

# This is the integration pattern - add these lines to roles.py around line 84

def enhanced_roles_extract_integration():
    """
    Integration pattern for adding enhanced splitting to RolesExtractor.
    
    Add these lines to the roles.py file just before the main return statement:
    """
    
    integration_code = '''
    # Around line 80-84 in roles.py, modify the return section:
    
    # Original code:
    # return candidates
    
    # Enhanced integration:
    # Apply enhanced splitting if enabled
    if os.environ.get('ENABLE_CONCEPT_SPLITTING', 'false').lower() == 'true':
        try:
            from .concept_splitter import split_concepts_for_extractor
            logger.info(f"Applying enhanced splitting to {len(candidates)} role candidates")
            enhanced_candidates = split_concepts_for_extractor(candidates, 'role')
            
            # Log splitting results
            if len(enhanced_candidates) != len(candidates):
                logger.info(f"Enhanced splitting: {len(candidates)} → {len(enhanced_candidates)} concepts")
                compounds_found = sum(1 for c in enhanced_candidates if c.debug.get('atomic_decomposition'))
                if compounds_found > 0:
                    logger.info(f"Split {compounds_found} compound role concepts into atomic parts")
            
            return enhanced_candidates
            
        except Exception as e:
            logger.error(f"Enhanced splitting failed, falling back to original: {e}")
            return candidates
    else:
        return candidates
    '''
    
    return integration_code


def create_enhanced_roles_extractor():
    """Create a complete enhanced roles extractor file."""
    
    # Read the original roles.py file
    original_file = '/home/chris/onto/proethica/app/services/extraction/roles.py'
    
    try:
        with open(original_file, 'r') as f:
            original_content = f.read()
        
        # Find the return statement and add enhanced integration
        if 'return candidates' in original_content and 'split_concepts_for_extractor' not in original_content:
            
            # Insert the enhanced integration before the main return
            enhanced_content = original_content.replace(
                '            return candidates',
                '''            # Apply enhanced splitting if enabled
            if os.environ.get('ENABLE_CONCEPT_SPLITTING', 'false').lower() == 'true':
                try:
                    from .concept_splitter import split_concepts_for_extractor
                    logger.info(f"Applying enhanced splitting to {len(candidates)} role candidates")
                    enhanced_candidates = split_concepts_for_extractor(candidates, 'role')
                    
                    # Log splitting results
                    if len(enhanced_candidates) != len(candidates):
                        logger.info(f"Enhanced splitting: {len(candidates)} → {len(enhanced_candidates)} concepts")
                        compounds_found = sum(1 for c in enhanced_candidates if c.debug.get('atomic_decomposition'))
                        if compounds_found > 0:
                            logger.info(f"Split {compounds_found} compound role concepts into atomic parts")
                    
                    return enhanced_candidates
                    
                except Exception as e:
                    logger.error(f"Enhanced splitting failed, falling back to original: {e}")
                    return candidates
            else:
                return candidates'''
            )
            
            # Also need to add the import at the top
            if 'import os' not in enhanced_content:
                enhanced_content = enhanced_content.replace(
                    'import logging',
                    'import logging\nimport os'
                )
            
            # Write the enhanced version
            enhanced_file = '/home/chris/onto/proethica/app/services/extraction/roles_enhanced.py'
            with open(enhanced_file, 'w') as f:
                f.write(enhanced_content)
            
            print(f"✅ Created enhanced roles extractor at: {enhanced_file}")
            print("📋 Integration preview:")
            print("=" * 50)
            print(enhanced_roles_extract_integration())
            print("=" * 50)
            
            return enhanced_file
            
        else:
            print("❌ Could not find integration point or already integrated")
            return None
            
    except Exception as e:
        print(f"❌ Error creating enhanced extractor: {e}")
        return None


def test_integration_readiness():
    """Test if the integration components are available."""
    print("🔍 Testing integration readiness...")
    
    # Check if concept_splitter exists
    try:
        splitter_file = '/home/chris/onto/proethica/app/services/extraction/concept_splitter.py'
        if os.path.exists(splitter_file):
            print("✅ GeneralizedConceptSplitter available")
        else:
            print("❌ concept_splitter.py not found")
            return False
    except Exception as e:
        print(f"❌ Error checking concept_splitter: {e}")
        return False
    
    # Check if original roles extractor exists
    try:
        roles_file = '/home/chris/onto/proethica/app/services/extraction/roles.py'
        if os.path.exists(roles_file):
            print("✅ Original RolesExtractor available")
        else:
            print("❌ roles.py not found")
            return False
    except Exception as e:
        print(f"❌ Error checking roles.py: {e}")
        return False
    
    print("✅ All components ready for integration")
    return True


def main():
    """Main integration demonstration."""
    print("🔧 Enhanced Roles Integration")
    print("=" * 40)
    
    # Test readiness
    if not test_integration_readiness():
        print("❌ Integration not ready")
        return
    
    # Show integration pattern
    print("\n📋 Integration Pattern:")
    print(enhanced_roles_extract_integration())
    
    # Create enhanced version for testing
    enhanced_file = create_enhanced_roles_extractor()
    
    if enhanced_file:
        print(f"\n🚀 Next Steps:")
        print("1. Review the enhanced extractor file")
        print("2. Run: python test_enhanced_roles.py")
        print("3. If tests pass, apply integration to original roles.py")
        print("4. Set ENABLE_CONCEPT_SPLITTING=true for production")
    else:
        print("\n❌ Integration failed - review errors above")


if __name__ == "__main__":
    main()