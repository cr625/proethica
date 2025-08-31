#!/usr/bin/env python3
"""
Demo of Enhanced Annotation Concept

This demonstrates the two-stage LLM annotation approach:
1. Term extraction from NSPE text  
2. Semantic matching against ontology definitions

This demo shows the concept and expected improvements without requiring 
full system integration.
"""

import re
import json
from typing import List, Dict, Any

# Sample NSPE Code text
SAMPLE_NSPE_TEXT = """
## Preamble

Engineering is an important and learned profession. As members of this profession, 
engineers are expected to exhibit the highest standards of honesty and integrity. 
Engineering has a direct and vital impact on the quality of life for all people. 
Accordingly, the services provided by engineers require honesty, impartiality, 
fairness, and equity, and must be dedicated to the protection of the public health, 
safety, and welfare. Engineers must perform under a standard of professional 
behavior that requires adherence to the highest principles of ethical conduct.

## Fundamental Principles

Engineers, in the fulfillment of their professional duties, shall:

1. Hold paramount the safety, health, and welfare of the public.
2. Perform services only in areas of their competence.
3. Issue public statements only in an objective and truthful manner.
4. Act for each employer or client as faithful agents or trustees.
5. Avoid deceptive acts.
6. Conduct themselves honorably, responsibly, ethically, and lawfully.
"""

# Sample ontology concepts (from our actual proethica-intermediate ontology)
SAMPLE_ONTOLOGY_CONCEPTS = [
    {
        "label": "Public Safety",
        "uri": "http://proethica.org/ontology/intermediate#PublicSafety",
        "definition": "",  # No definition - this is why it might not match well
        "ontology": "proethica-intermediate"
    },
    {
        "label": "Public Health", 
        "uri": "http://proethica.org/ontology/intermediate#PublicHealth",
        "definition": "",  # No definition
        "ontology": "proethica-intermediate"
    },
    {
        "label": "Competence",
        "uri": "http://proethica.org/ontology/intermediate#Competence", 
        "definition": "The combination of technical knowledge, professional skills, and sound judgment necessary to perform engineering services safely and effectively within one's area of expertise. Competence includes both initial qualification and ongoing maintenance of professional capabilities.",
        "ontology": "proethica-intermediate"
    },
    {
        "label": "Truthfulness",
        "uri": "http://proethica.org/ontology/intermediate#Truthfulness",
        "definition": "",  # No definition
        "ontology": "proethica-intermediate"
    },
    {
        "label": "Professional Obligation",
        "uri": "http://proethica.org/ontology/intermediate#Obligation",
        "definition": "A binding moral or legal duty that arises from an engineer's professional role, requiring specific actions or behaviors to fulfill responsibilities to the public, employers, clients, and the engineering profession. Professional obligations create enforceable expectations that override personal preferences or convenience.",
        "ontology": "proethica-intermediate"
    },
    {
        "label": "Client",
        "uri": "http://proethica.org/ontology/intermediate#Client",
        "definition": "The individual, organization, or entity that engages an engineer's professional services and to whom the engineer owes specific professional duties, including competent service, confidentiality, and loyalty, while maintaining paramount duty to public safety and welfare.",
        "ontology": "proethica-intermediate"
    },
    {
        "label": "Ensure Accessibility Compliance",
        "uri": "http://proethica.org/ontology/engineering-ethics#EnsureAccessibilityCompliance",
        "definition": "Legal and ethical obligation for inclusive design",
        "ontology": "engineering-ethics"
    },
    {
        "label": "Comply with Applicable Safety Standards", 
        "uri": "http://proethica.org/ontology/engineering-ethics#ComplyWithApplicableSafetyStandards",
        "definition": "Fundamental obligation to follow established safety protocols",
        "ontology": "engineering-ethics"
    }
]

def demo_term_extraction(text: str) -> List[Dict[str, Any]]:
    """
    Demo: Extract key terms from NSPE text using rule-based patterns.
    In real implementation, this would use LLM for intelligent extraction.
    """
    print("🔍 STAGE 1: Term Extraction")
    print("-" * 40)
    
    # Professional ethics patterns (simplified version of what LLM would find)
    patterns = [
        (r'\b(public\s+(?:safety|health|welfare))\b', 'stakeholder_concept'),
        (r'\b(professional\s+(?:competence|integrity|behavior|duties))\b', 'professional_concept'),
        (r'\b(honesty|integrity|truthfulness|impartiality|fairness|equity)\b', 'ethical_principle'),
        (r'\b(employer|client)\b', 'stakeholder'),
        (r'\b(competence|competent)\b', 'capability'),
        (r'\b(ethical\s+conduct|ethical\s+principles)\b', 'ethical_concept'),
        (r'\b(deceptive\s+acts)\b', 'prohibited_action'),
        (r'\b(faithful\s+agents|trustees)\b', 'role_concept')
    ]
    
    extracted_terms = []
    text_lower = text.lower()
    
    for pattern, term_type in patterns:
        for match in re.finditer(pattern, text_lower, re.IGNORECASE):
            term = match.group(1)
            start_pos = match.start(1)
            
            # Get context (30 chars before and after)
            context_start = max(0, start_pos - 30)
            context_end = min(len(text), start_pos + len(term) + 30)
            context = text[context_start:context_end].strip().replace('\n', ' ')
            
            extracted_terms.append({
                'term': term,
                'type': term_type,
                'context': context,
                'start_offset': start_pos
            })
    
    # Remove duplicates by term
    seen = set()
    unique_terms = []
    for term in extracted_terms:
        key = term['term'].lower()
        if key not in seen:
            seen.add(key)
            unique_terms.append(term)
    
    print(f"Found {len(unique_terms)} unique terms:")
    for i, term in enumerate(unique_terms, 1):
        print(f"{i:2d}. \"{term['term']}\" ({term['type']})")
        print(f"     Context: ...{term['context'][:60]}...")
    
    print()
    return unique_terms

def demo_semantic_matching(extracted_terms: List[Dict], concepts: List[Dict]) -> List[Dict]:
    """
    Demo: Show how LLM would semantically match terms to ontology concepts.
    This simulates the LLM reasoning process.
    """
    print("🤖 STAGE 2: Semantic Matching")
    print("-" * 40)
    
    matches = []
    no_matches = []
    
    # Simulate LLM semantic matching
    semantic_mappings = {
        'public safety': ('Public Safety', 0.95, 'exact', 'Direct match with concept label'),
        'public health': ('Public Health', 0.95, 'exact', 'Direct match with concept label'),
        'public welfare': ('Public Health', 0.75, 'semantic', 'Welfare encompasses health concerns'),
        'competence': ('Competence', 0.90, 'exact', 'Direct match with detailed definition'),
        'competent': ('Competence', 0.85, 'semantic', 'Adjectival form of competence concept'),
        'honesty': ('Truthfulness', 0.85, 'semantic', 'Honesty and truthfulness are synonymous in professional context'),
        'integrity': ('Professional Obligation', 0.70, 'contextual', 'Integrity relates to fulfilling professional obligations'),
        'truthfulness': ('Truthfulness', 0.95, 'exact', 'Direct match with concept label'),
        'impartiality': ('Professional Obligation', 0.75, 'contextual', 'Impartiality is a key professional obligation'),
        'fairness': ('Professional Obligation', 0.70, 'contextual', 'Fairness is inherent in professional obligations'),
        'equity': ('Professional Obligation', 0.70, 'contextual', 'Equity relates to fair professional conduct'),
        'employer': ('Client', 0.80, 'semantic', 'Employer is a type of client relationship'),
        'client': ('Client', 0.95, 'exact', 'Direct match with detailed definition'),
        'faithful agents': ('Client', 0.85, 'contextual', 'Faithful agents relates to client relationship duties'),
        'professional duties': ('Professional Obligation', 0.90, 'semantic', 'Direct conceptual match'),
        'professional behavior': ('Professional Obligation', 0.85, 'semantic', 'Behavior governed by professional obligations')
    }
    
    for term in extracted_terms:
        term_key = term['term'].lower()
        
        if term_key in semantic_mappings:
            concept_label, similarity, match_type, reasoning = semantic_mappings[term_key]
            
            # Find the matching concept
            matching_concept = next((c for c in concepts if c['label'] == concept_label), None)
            if matching_concept:
                matches.append({
                    'extracted_term': term,
                    'concept': matching_concept,
                    'similarity_score': similarity,
                    'match_type': match_type,
                    'reasoning': reasoning,
                    'confidence': 'high' if similarity > 0.8 else 'medium' if similarity > 0.6 else 'low'
                })
            else:
                no_matches.append(term['term'])
        else:
            no_matches.append(term['term'])
    
    # Display matches
    print(f"✅ Found {len(matches)} semantic matches:")
    for i, match in enumerate(matches, 1):
        term = match['extracted_term']['term']
        concept = match['concept']['label'] 
        score = match['similarity_score']
        confidence = match['confidence']
        ontology = match['concept']['ontology']
        definition = match['concept']['definition'][:60] + '...' if match['concept']['definition'] else 'No definition'
        
        print(f"{i:2d}. \"{term}\" → **{concept}** ({ontology})")
        print(f"     Similarity: {score:.2f} ({confidence} confidence)")
        print(f"     Reasoning: {match['reasoning']}")
        print(f"     Definition: {definition}")
        print()
    
    if no_matches:
        print(f"❌ Ontology gaps - {len(no_matches)} terms not matched:")
        for i, term in enumerate(no_matches, 1):
            print(f"{i:2d}. \"{term}\"")
    
    return matches

def demo_analysis():
    """Run the complete demo analysis."""
    print("🚀 Enhanced Annotation Demo")
    print("=" * 60)
    print("Demonstrating LLM-powered semantic annotation")
    print("on NSPE Code of Ethics text")
    print()
    
    # Stage 1: Term extraction
    extracted_terms = demo_term_extraction(SAMPLE_NSPE_TEXT)
    
    # Stage 2: Semantic matching 
    matches = demo_semantic_matching(extracted_terms, SAMPLE_ONTOLOGY_CONCEPTS)
    
    # Summary
    print("=" * 60)
    print("📊 DEMO RESULTS SUMMARY")
    print("=" * 60)
    print(f"Terms extracted: {len(extracted_terms)}")
    print(f"Successful matches: {len(matches)}")
    print(f"Success rate: {len(matches)/len(extracted_terms)*100:.1f}%")
    print()
    
    print(f"🔥 **Expected Improvement**: From 3 matches → {len(matches)} matches")
    print(f"📈 That's a {len(matches)/3:.1f}x improvement!")
    print()
    
    print("💡 **Key Insights:**")
    print("1. LLM can extract domain-specific terms intelligently")
    print("2. Semantic matching finds synonyms (honesty → Truthfulness)")
    print("3. Contextual matching connects related concepts")
    print("4. Concepts with rich definitions match better")
    print("5. Ontology gaps reveal missing concepts to add")
    print()
    
    print("🎯 **Next Steps:**")
    print("1. Add Claude API key to enable full LLM functionality")
    print("2. Add missing concept definitions to improve matching")
    print("3. Consider adding gap terms to ontology")
    print("4. Integrate with existing annotation UI")

if __name__ == "__main__":
    demo_analysis()