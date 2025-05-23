#!/usr/bin/env python3
"""
Fix the extraction method for optimized prediction service.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up environment
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
os.environ.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', 'false')
os.environ.setdefault('ENVIRONMENT', 'development')

import logging
from typing import Dict, List, Any
from datetime import datetime
from app import create_app, db

logger = logging.getLogger(__name__)

def test_extraction_patterns():
    """Test different extraction patterns with actual response."""
    
    # Actual response content from the debug
    response_content = """# CONCLUSION

## ETHICAL DETERMINATION

Based on the analysis of the case facts and relevant NSPE Code provisions, the Board of Ethical Review concludes:

1. It was **ETHICAL** for Engineer T and Engineer B to conclude an error had not been made in design.
2. It was **ETHICAL** for Engineer T not to acknowledge an error after the accident occurred.
3. It was **ETHICAL** for Engineer T not to acknowledge an error during the deposition.

## DETAILED JUSTIFICATION

### Paramount Duty to Public Safety (Code I.1)
Engineer T did fulfill the basic obligation to hold paramount the safety, health, and welfare of the public by designing a structurally sound modification and clearly noting the constrained access in the construction documents. While Engineer T could have explored alternative designs that might have been safer for construction workers, the standard practice in the industry is that construction safety is primarily the contractor's responsibility. The design itself was structurally sound and met applicable standards. The fact that Engineer T identified the constrained access in the drawings demonstrates awareness of potential difficulties, allowing the contractor to implement appropriate safety measures.

### Professional Competence (Code I.2)
The facts do not indicate any deficiency in Engineer T's structural engineering competence. Engineer T properly performed services within their area of expertise - structural design. As noted in the case analysis, Engineer T was "not trained in construction safety either by education or by specific experience," and therefore could not reasonably be expected to have the expertise to fully assess construction safety risks. This aligns with BER Case 02-5, which established that engineers cannot be ethically faulted for not incorporating techniques outside their standard practice area.

### Truthfulness in Professional Communication (Code II.3.a and III.3.a)
Engineer T responded truthfully and factually to all questions during the deposition and did not distort or alter any facts. The Code requires engineers to be "objective and truthful in professional reports, statements, or testimony" and to "include all relevant and pertinent information." Engineer T fulfilled this obligation by providing complete transparency during the deposition process. Not characterizing the design as an "error" when Engineer T did not believe it constituted an error is consistent with maintaining truthfulness.

### Acknowledging Errors (Code III.1.a)
Code III.1.a requires engineers to "acknowledge their errors and shall not distort or alter the facts." However, this provision presupposes that an actual error has occurred. In this case, the design approach represented professional practice consistent with the standard of care. As established in BER Case 02-5, following standard professional practice, even when a better approach might have been possible in hindsight, does not constitute an ethical error. Engineer T's design met professional standards, and the construction safety aspects were properly delegated to the contractor through standard contractual arrangements.

### Personal Responsibility (Code III.8)
Engineer T did accept personal responsibility by meeting with Engineer B to discuss concerns, revisiting the site after the accident, and reflecting on whether alternative designs might have prevented the injury. This demonstrates Engineer T's commitment to personal responsibility. However, accepting responsibility does not necessarily mean acknowledging an error when professional judgment reasonably concludes no error occurred.

## COMPREHENSIVE ANALYSIS

The central ethical tension in this case involves balancing several competing obligations: the duty to hold paramount public safety, the obligation to acknowledge errors, the duty to be truthful, and the responsibility to act as a faithful agent to one's employer.

Similar to BER Case 97-13, Engineer T identified a potential safety concern (the constrained access) and properly documented it in the design. The fact that Engineer T, in hindsight, recognized that an alternative design might have been safer does not transform the original design into an error. As in BER Case 02-5, engineers cannot be ethically faulted for not implementing every possible safety enhancement when their design meets the standard of care.

The construction industry operates with a clear division of responsibilities, where designers are responsible for the structural integrity of the design, while contractors are responsible for construction methods and worker safety. This division was properly maintained in this case, with Engineer T clearly noting the constrained access in the drawings, thereby providing the contractor with the information needed to implement appropriate safety measures.

While Engineer T "felt some personal responsibility for the accident," this commendable professional reflection does not equate to having made an error. The Board views this more as a missed opportunity for Engineer T to have gone beyond minimum requirements rather than an ethical lapse.

## STRUCTURED REASONING

First, the Board considered whether Engineer T's design constituted an error. Based on the facts presented, Engineer T followed standard professional practice in developing a structurally sound design and properly noted construction constraints."""

    print("🔍 TESTING EXTRACTION PATTERNS")
    print("="*60)
    print(f"Response length: {len(response_content)} characters")
    
    # Test original regex pattern
    import re
    
    print("\n1. ORIGINAL PATTERN:")
    pattern1 = r'(?i)#*\s*CONCLUSION:?\s*(.*?)(?=#|\Z)'
    match1 = re.search(pattern1, response_content, re.DOTALL)
    if match1:
        result1 = match1.group(1).strip()
        print(f"   Match found: {len(result1)} characters")
        print(f"   Preview: {result1[:100]}...")
    else:
        print("   No match found")
    
    # Test improved pattern - capture everything after CONCLUSION
    print("\n2. IMPROVED PATTERN (everything after CONCLUSION):")
    pattern2 = r'(?i)#*\s*CONCLUSION:?\s*(.*)'
    match2 = re.search(pattern2, response_content, re.DOTALL)
    if match2:
        result2 = match2.group(1).strip()
        print(f"   Match found: {len(result2)} characters")
        print(f"   Preview: {result2[:100]}...")
    else:
        print("   No match found")
    
    # Test pattern that looks for conclusion section specifically
    print("\n3. SECTION-AWARE PATTERN:")
    pattern3 = r'(?i)#\s*CONCLUSION\s*\n\s*(.*)'
    match3 = re.search(pattern3, response_content, re.DOTALL)
    if match3:
        result3 = match3.group(1).strip()
        print(f"   Match found: {len(result3)} characters")
        print(f"   Preview: {result3[:100]}...")
    else:
        print("   No match found")
    
    # Test fallback - just return whole response if starts with conclusion
    print("\n4. FALLBACK APPROACH:")
    if response_content.strip().lower().startswith('#') and 'conclusion' in response_content.lower()[:50]:
        result4 = response_content.strip()
        print(f"   Using whole response: {len(result4)} characters")
        print(f"   Preview: {result4[:100]}...")
    else:
        print("   Does not start with conclusion")
        
    print(f"\n✅ RECOMMENDED: Use pattern 2 or 3, both capture the full conclusion content")

if __name__ == "__main__":
    test_extraction_patterns()
