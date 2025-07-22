#!/usr/bin/env python3
"""
Script to manually add the sample structural safety case to the case repository.

This creates a complete NSPE-format case based on the agent conversation example
and adds it to the Document model so it appears in the cases listing.
"""

import sys
import os
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app, db
from app.models.document import Document
from app.models.world import World

def create_sample_case():
    """Create and save the sample structural safety case."""
    
    app = create_app()
    
    with app.app_context():
        # Get the first available world (usually Engineering Ethics)
        world = World.query.first()
        if not world:
            print("No worlds found in database. Please create a world first.")
            return
        
        # Define the case content based on our sample conversation
        case_title = "Foundation Design and Professional Responsibility"
        
        case_content = """**FACTS:**
Engineer A, a licensed structural engineer, was retained by Developer B to review foundation plans for a new commercial building. During the review, Engineer A discovered that the approved foundation design specified standard shallow foundations, but the geotechnical report clearly indicated expansive clay soil conditions requiring deeper foundations with special reinforcement. Engineer A estimated that using the inadequate foundation design would likely cause significant structural movement and cracking within 2-3 years, potentially compromising the building's structural integrity. When Engineer A informed Developer B of the necessary design changes, Developer B stated that the timeline and budget could not accommodate changes and threatened to retain another engineer if Engineer A would not approve the existing plans.

**QUESTION:**
Was it ethical for Engineer A to refuse to approve the foundation plans despite pressure from Developer B, and what professional obligations does Engineer A have regarding reporting the safety concerns?

**NSPE CODE OF ETHICS REFERENCES:**
- Section I.1: Engineers must hold paramount the safety, health, and welfare of the public
- Section II.3: Engineers shall issue public statements only in an objective and truthful manner
- Section III.4: Engineers shall act for each employer or client as faithful agents or trustees

**DISCUSSION:**
This case presents a fundamental conflict between business pressures and professional obligations. Engineer A's refusal to approve inadequate foundation plans aligns with the paramount duty under Section I.1 to protect public safety. The expansive clay conditions and predicted structural failure within 2-3 years present a clear risk to building occupants and the public. Section II.3 requires Engineers to provide objective and truthful professional judgment, which would be compromised by approving plans known to be inadequate. While Section III.4 requires engineers to act as faithful agents, this obligation cannot supersede the paramount duty to public safety. The threat from Developer B to find another engineer does not diminish Engineer A's professional responsibilities, as outlined in the NSPE Code of Ethics.

**CONCLUSION:**
Engineer A acted ethically by refusing to approve foundation plans that did not meet site conditions and posed a public safety risk. Professional obligations under the NSPE Code of Ethics require prioritizing public safety over client business pressures. If Developer B proceeds with the inadequate design through another engineer, Engineer A should consider reporting the safety concern to appropriate authorities."""

        # Create comprehensive metadata
        doc_metadata = {
            'source': 'agent_generated_sample',
            'generation_method': 'language_model_assisted',
            'generation_timestamp': datetime.utcnow().isoformat(),
            'selected_concepts_summary': '5 categories, 8 concepts selected',
            
            # NSPE-format sections
            'sections': {
                'facts': """Engineer A, a licensed structural engineer, was retained by Developer B to review foundation plans for a new commercial building. During the review, Engineer A discovered that the approved foundation design specified standard shallow foundations, but the geotechnical report clearly indicated expansive clay soil conditions requiring deeper foundations with special reinforcement. Engineer A estimated that using the inadequate foundation design would likely cause significant structural movement and cracking within 2-3 years, potentially compromising the building's structural integrity. When Engineer A informed Developer B of the necessary design changes, Developer B stated that the timeline and budget could not accommodate changes and threatened to retain another engineer if Engineer A would not approve the existing plans.""",
                
                'questions': """Was it ethical for Engineer A to refuse to approve the foundation plans despite pressure from Developer B, and what professional obligations does Engineer A have regarding reporting the safety concerns?""",
                
                'nspe_references': """- Section I.1: Engineers must hold paramount the safety, health, and welfare of the public
- Section II.3: Engineers shall issue public statements only in an objective and truthful manner
- Section III.4: Engineers shall act for each employer or client as faithful agents or trustees""",
                
                'discussion': """This case presents a fundamental conflict between business pressures and professional obligations. Engineer A's refusal to approve inadequate foundation plans aligns with the paramount duty under Section I.1 to protect public safety. The expansive clay conditions and predicted structural failure within 2-3 years present a clear risk to building occupants and the public. Section II.3 requires Engineers to provide objective and truthful professional judgment, which would be compromised by approving plans known to be inadequate. While Section III.4 requires engineers to act as faithful agents, this obligation cannot supersede the paramount duty to public safety. The threat from Developer B to find another engineer does not diminish Engineer A's professional responsibilities, as outlined in the NSPE Code of Ethics.""",
                
                'conclusion': """Engineer A acted ethically by refusing to approve foundation plans that did not meet site conditions and posed a public safety risk. Professional obligations under the NSPE Code of Ethics require prioritizing public safety over client business pressures. If Developer B proceeds with the inadequate design through another engineer, Engineer A should consider reporting the safety concern to appropriate authorities."""
            },
            
            # Ontology selections from the sample conversation
            'ontology_selections': {
                'Principle': ['PublicSafetyPrinciple', 'ProfessionalIntegrityPrinciple'],
                'Obligation': ['PublicWelfareObligation', 'HonestServiceObligation'],
                'Role': ['StructuralEngineerRole'],
                'Action': ['SafetyReportingAction', 'EthicalConsultationAction'],
                'State': ['RiskState']
            },
            
            # Generation metadata
            'generation_metadata': {
                'generated_at': datetime.utcnow().isoformat(),
                'conversation_source': 'sample_structural_safety_conversation',
                'llm_service': 'sample_manual_creation',
                'ontology_concepts_used': [
                    'PublicSafetyPrinciple', 'ProfessionalIntegrityPrinciple',
                    'PublicWelfareObligation', 'HonestServiceObligation',
                    'StructuralEngineerRole', 'SafetyReportingAction', 
                    'EthicalConsultationAction', 'RiskState'
                ]
            },
            
            # Sample conversation thread (abbreviated)
            'conversation_thread': [
                {
                    'content': 'I want to create a case about a structural engineer who discovers potential safety issues in a building design but faces pressure from the client to approve it anyway.',
                    'role': 'user',
                    'timestamp': '2025-01-27T10:30:00Z'
                },
                {
                    'content': 'Based on your selected ontological concepts, this presents a classic conflict between PublicSafetyPrinciple and professional relationships...',
                    'role': 'assistant', 
                    'timestamp': '2025-01-27T10:30:45Z'
                },
                {
                    'content': "Let's make it about a commercial building where the structural engineer finds that the foundation design doesn't meet local soil conditions.",
                    'role': 'user',
                    'timestamp': '2025-01-27T10:35:00Z'
                }
            ]
        }
        
        # Create the document
        document = Document(
            title=case_title,
            content=case_content,
            document_type='case_study',
            world_id=world.id,
            source='Generated with Language Model assistance',
            doc_metadata=doc_metadata,
            processing_status='COMPLETED',
            processing_progress=100
        )
        
        # Save to database
        db.session.add(document)
        db.session.commit()
        
        print(f"✅ Successfully created sample case:")
        print(f"   ID: {document.id}")
        print(f"   Title: {document.title}")
        print(f"   World: {world.name}")
        print(f"   Source: {document.source}")
        print(f"   URL: /cases/view/{document.id}")
        print(f"   Ontology concepts: {len(doc_metadata['generation_metadata']['ontology_concepts_used'])} concepts across 5 categories")

if __name__ == '__main__':
    create_sample_case()