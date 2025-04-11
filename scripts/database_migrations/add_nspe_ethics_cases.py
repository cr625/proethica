#!/usr/bin/env python3
"""
Script to add new NSPE engineering ethics cases to the Engineering world.
This script creates case documents and adds corresponding entity triples.
"""

import json
import sys
import os
import datetime

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Import the application and database
from app import create_app, db

# Constants
ENGINEERING_WORLD_ID = 1  # Engineering Ethics world ID

# Define the new NSPE cases to add
NEW_CASES = [
    {
        "title": "Post-Public Employment: City Engineer Transitioning to Consultant",
        "description": """
A city engineer has decided to retire from his position and establish his own consulting engineering practice. While serving as city engineer, the engineer was involved in the planning of numerous public works projects in the city, including a major bridge replacement project. The engineer now wishes to provide consulting services to contractors that may be involved in the bridge replacement project.

**Facts:**
- The engineer served as city engineer for 20 years.
- The engineer was significantly involved in the planning of a major bridge replacement project.
- The engineer has retired and wants to establish a consulting practice.
- The engineer wants to provide consulting services to contractors involved in the bridge project.
- The project is in the bidding stage, but construction has not yet begun.

**Question:**
Would it be ethical for the engineer to provide consulting services to contractors bidding on the bridge replacement project?

**Discussion:**
The NSPE Code of Ethics states that engineers shall act in professional matters for each employer or client as faithful agents or trustees, and shall avoid conflicts of interest. Additionally, engineers in public service as members, advisors, or employees of a governmental body or department shall not participate in decisions with respect to services solicited or provided by them or their organizations in private or public engineering practice.

The engineer's prior involvement in planning the bridge replacement project creates a conflict of interest situation. The engineer would have access to inside information about the project that other consultants would not have, creating an unfair advantage and potential bias.

**Conclusion:**
It would be unethical for the engineer to provide consulting services to contractors bidding on the bridge replacement project that he was involved with as city engineer. This would constitute a conflict of interest and violate the NSPE Code of Ethics.
        """,
        "source": "https://www.nspe.org/career-resources/ethics/post-public-employment-city-engineer-transitioning-consultant",
        "metadata": {
            "case_number": "BER 22-1",
            "year": 2022,
            "principles": ["conflict of interest", "fair competition", "professional integrity", "public service"],
            "outcome": "unethical",
            "decision": "It would be unethical for the engineer to provide consulting services to contractors bidding on the bridge replacement project that he was involved with as city engineer."
        },
        "entity_triples": [
            {
                "subject": ":CityEngineerRole",
                "predicate": "rdf:type",
                "object": "proeth:Role",
                "is_literal": False
            },
            {
                "subject": "case:engineer",
                "predicate": "proeth:hasRole",
                "object": ":CityEngineerRole",
                "is_literal": False
            },
            {
                "subject": "case:engineer",
                "predicate": "proeth:hasRole",
                "object": ":ConsultingEngineerRole",
                "is_literal": False
            },
            {
                "subject": "case:situation",
                "predicate": "rdf:type",
                "object": ":ConflictOfInterestDilemma",
                "is_literal": False
            },
            {
                "subject": "case:decision",
                "predicate": "proeth:violates",
                "object": ":NSPEPublicSafetyPrinciple",
                "is_literal": False
            }
        ]
    },
    {
        "title": "Public Health, Safety & Welfare: Climate Change-Induced Conditions",
        "description": """
An engineer is reviewing design plans for a coastal residential development. The engineer is aware of recent climate change studies indicating that sea levels in this area are projected to rise significantly over the next 50 years, which would place portions of the development at risk of flooding. The current design meets all existing building codes and regulations, which have not yet been updated to account for projected climate change impacts.

**Facts:**
- The engineer is reviewing design plans for a coastal residential development.
- Climate change studies indicate significant sea level rise in the area over the next 50 years.
- Current building codes do not account for projected climate change impacts.
- The developer is pressuring for approval, stating they only need to meet current regulations.
- The development is expected to have a lifespan of at least 75 years.

**Question:**
What are the engineer's ethical obligations regarding the projected climate change impacts?

**Discussion:**
The NSPE Code of Ethics states that engineers shall hold paramount the safety, health, and welfare of the public in the performance of their professional duties. This creates an obligation to consider reasonably foreseeable long-term impacts, even if current regulations do not explicitly require it.

While the design meets current regulations, engineers have an ethical responsibility to advise clients about foreseeable risks beyond code compliance. The projected sea level rise presents a significant risk to future residents' safety and property.

**Conclusion:**
The engineer has an ethical obligation to inform the client and relevant stakeholders about the projected climate change impacts and associated risks. The engineer should recommend design modifications to account for sea level rise, even if not required by current regulations, to protect public safety and welfare.
        """,
        "source": "https://www.nspe.org/career-resources/ethics/public-health-safety-welfare-climate-change-induced-conditions",
        "metadata": {
            "case_number": "BER 22-8",
            "year": 2022,
            "principles": ["public safety", "professional judgment", "disclosure", "future impacts"],
            "outcome": "ethical obligation to disclose",
            "decision": "The engineer has an ethical obligation to inform the client and stakeholders about projected climate change impacts and recommend design modifications."
        },
        "entity_triples": [
            {
                "subject": "case:situation",
                "predicate": "rdf:type",
                "object": ":ClimateChangeCondition",
                "is_literal": False
            },
            {
                "subject": "case:engineer",
                "predicate": "proeth:hasRole",
                "object": ":ConsultingEngineerRole",
                "is_literal": False
            },
            {
                "subject": "case:situation",
                "predicate": "proeth:involves",
                "object": ":PublicSafetyVsResourceConstraintsDilemma",
                "is_literal": False
            },
            {
                "subject": "case:decision",
                "predicate": "proeth:upholdsEthicalPrinciple",
                "object": ":DisclosurePrinciple",
                "is_literal": False
            },
            {
                "subject": "case:decision",
                "predicate": "proeth:upholdsEthicalPrinciple",
                "object": ":NSPEPublicSafetyPrinciple",
                "is_literal": False
            }
        ]
    },
    {
        "title": "Public Health, Safety & Welfare: Drinking Water Quality",
        "description": """
An engineer employed by a water authority discovers that the public water supply in a specific neighborhood has lead levels that exceed EPA guidelines. The engineer reports this to management, but the authority decides to postpone public notification and remediation until the next budget cycle, citing limited resources and the need for additional testing to confirm the extent of the problem.

**Facts:**
- The engineer has reliable test results showing elevated lead levels in a neighborhood's water supply.
- The levels exceed EPA safety guidelines, though not by a large margin.
- Management has decided to postpone public notification for several months.
- The engineer has attempted to express concerns through internal channels.
- The affected neighborhood has many families with young children, who are particularly vulnerable to lead exposure.

**Question:**
What are the engineer's ethical obligations in this situation?

**Discussion:**
The NSPE Code of Ethics makes clear that engineers shall hold paramount the safety, health, and welfare of the public. While engineers also have obligations to their employers, these are subordinate to public safety concerns.

The presence of elevated lead levels in drinking water presents a significant health risk, particularly to children and pregnant women. Delaying notification denies affected residents the opportunity to take precautionary measures to protect their health.

**Conclusion:**
The engineer has an ethical obligation to take further action to ensure timely notification of the affected public. This may include escalating concerns to higher management, relevant regulatory agencies, or public health officials if the water authority continues to delay notification and remediation efforts.
        """,
        "source": "https://www.nspe.org/career-resources/ethics/public-health-safety-welfare-drinking-water-quality",
        "metadata": {
            "case_number": "BER 23-2",
            "year": 2023,
            "principles": ["public safety", "whistleblowing", "disclosure", "professional responsibility"],
            "outcome": "ethical obligation to act",
            "decision": "The engineer has an ethical obligation to take further action to ensure timely notification of the affected public."
        },
        "entity_triples": [
            {
                "subject": "case:situation",
                "predicate": "rdf:type",
                "object": ":WaterQualityCondition",
                "is_literal": False
            },
            {
                "subject": "case:engineer",
                "predicate": "proeth:hasRole",
                "object": ":EngineeringRole",
                "is_literal": False
            },
            {
                "subject": "case:situation",
                "predicate": "rdf:type",
                "object": ":SafetyHazard",
                "is_literal": False
            },
            {
                "subject": "case:decision",
                "predicate": "rdf:type",
                "object": ":WhistleblowingDecision",
                "is_literal": False
            },
            {
                "subject": "case:decision",
                "predicate": "proeth:upholdsEthicalPrinciple",
                "object": ":ProfessionalResponsibilityPrinciple",
                "is_literal": False
            }
        ]
    },
    {
        "title": "Sharing As-Built Drawings",
        "description": """
An engineer received a request from a contractor to provide as-built drawings for a completed project. The engineer had prepared these drawings for the original client, a property owner, as part of an earlier renovation project. The contractor is now working on a new project for the same property but with a different owner, and believes the as-built drawings would be helpful for the current work.

**Facts:**
- The engineer prepared as-built drawings for a previous owner of the property.
- A contractor working for the new owner has requested these drawings.
- The engineer does not have explicit permission from the original client to share the drawings.
- The drawings could be helpful for the new project and potentially identify existing conditions that might affect safety.
- The original contract did not specifically address future use of the drawings.

**Question:**
Would it be ethical for the engineer to provide the as-built drawings to the contractor without the original client's permission?

**Discussion:**
The NSPE Code of Ethics states that engineers shall not reveal facts, data, or information without the prior consent of the client or employer except as authorized or required by law or this Code. As-built drawings contain specific information about a project commissioned by a specific client.

However, engineers also have an obligation to protect public safety. If the drawings contain information that would help identify potential safety issues in subsequent work, there may be competing ethical principles at play.

**Conclusion:**
It would be unethical for the engineer to provide the as-built drawings without attempting to obtain permission from the original client. The engineer should first try to contact the original client for consent. If the original client cannot be reached or refuses permission, the engineer should advise the contractor to commission new as-built drawings or surveys. If there are specific safety concerns, the engineer may have a duty to disclose only the safety-critical information rather than the complete drawings.
        """,
        "source": "https://www.nspe.org/career-resources/ethics/sharing-built-drawings",
        "metadata": {
            "case_number": "BER 22-5",
            "year": 2022,
            "principles": ["confidentiality", "ownership of documents", "professional responsibility", "client consent"],
            "outcome": "unethical without consent",
            "decision": "It would be unethical for the engineer to provide the as-built drawings without attempting to obtain permission from the original client."
        },
        "entity_triples": [
            {
                "subject": "case:request",
                "predicate": "proeth:involves",
                "object": ":AsBuiltDrawings",
                "is_literal": False
            },
            {
                "subject": "case:engineer",
                "predicate": "proeth:hasRole",
                "object": ":ConsultingEngineerRole",
                "is_literal": False
            },
            {
                "subject": "case:situation",
                "predicate": "rdf:type",
                "object": ":ConfidentialityVsSafetyDilemma",
                "is_literal": False
            },
            {
                "subject": "case:decision",
                "predicate": "proeth:upholdsEthicalPrinciple",
                "object": ":ConfidentialityPrinciple",
                "is_literal": False
            },
            {
                "subject": "case:decision",
                "predicate": "proeth:involves",
                "object": ":EngineeringDocument",
                "is_literal": False
            }
        ]
    },
    {
        "title": "Excess Stormwater Runoff",
        "description": """
An engineer is designing a commercial development that will replace a wooded area with buildings and paved surfaces. The local stormwater regulations require managing a 10-year storm event, but the engineer knows from experience that a nearby residential neighborhood has experienced flooding during larger storm events. Recent climate data suggests that these larger storms are becoming more frequent.

**Facts:**
- The engineer is designing a commercial development that will significantly increase impervious surface area.
- Local regulations only require managing a 10-year storm event.
- A downstream residential neighborhood has a history of flooding during larger storms.
- Climate data indicates larger storms are occurring more frequently than in the past.
- Additional stormwater management features would increase project costs for the client.

**Question:**
What are the engineer's ethical obligations regarding stormwater management design?

**Discussion:**
The NSPE Code of Ethics requires engineers to hold paramount the safety, health, and welfare of the public in the performance of their professional duties. While the design meets current regulations, the engineer has knowledge that suggests the minimum standards may be insufficient to prevent harm to the downstream neighborhood.

Engineers must balance their obligations to their client with their responsibility to protect public welfare, even when that means exceeding minimum regulatory requirements.

**Conclusion:**
The engineer has an ethical obligation to inform the client about the potential downstream flooding impacts and recommend stormwater management features that would address larger storm events, even though they exceed the minimum regulatory requirements. If the client refuses to implement additional measures, the engineer should at minimum document the recommendations and the client's decision.
        """,
        "source": "https://www.nspe.org/career-resources/ethics/excess-stormwater-runoff",
        "metadata": {
            "case_number": "BER 21-4",
            "year": 2021,
            "principles": ["public safety", "client service", "disclosure", "professional judgment"],
            "outcome": "ethical obligation to recommend",
            "decision": "The engineer has an ethical obligation to inform the client and recommend stormwater management features for larger storm events."
        },
        "entity_triples": [
            {
                "subject": "case:situation",
                "predicate": "rdf:type",
                "object": ":StormwaterRunoffCondition",
                "is_literal": False
            },
            {
                "subject": "case:engineer",
                "predicate": "proeth:hasRole",
                "object": ":ConsultingEngineerRole",
                "is_literal": False
            },
            {
                "subject": "case:situation",
                "predicate": "proeth:involves",
                "object": ":ClimateChangeCondition",
                "is_literal": False
            },
            {
                "subject": "case:decision",
                "predicate": "proeth:upholdsEthicalPrinciple",
                "object": ":NSPEPublicSafetyPrinciple",
                "is_literal": False
            },
            {
                "subject": "case:decision",
                "predicate": "proeth:upholdsEthicalPrinciple",
                "object": ":DisclosurePrinciple",
                "is_literal": False
            }
        ]
    }
]

def create_nspe_case(case_data, world_id=ENGINEERING_WORLD_ID):
    """
    Create a NSPE case as a Document object with document_type='case_study'.
    """
    from app.models.document import Document
    from app.services.entity_triple_service import EntityTripleService
    from app.services.embedding_service import EmbeddingService
    
    # Extract case information
    title = case_data.get('title', '')
    description = case_data.get('description', '')
    source = case_data.get('source', '')
    metadata = case_data.get('metadata', {})
    
    # Check if the case already exists with the same title
    existing_case = Document.query.filter_by(
        title=title,
        document_type='case_study',
        world_id=world_id
    ).first()
    
    if existing_case:
        print(f"Case '{title}' already exists (ID: {existing_case.id}). Skipping.")
        return existing_case.id
    
    # Create the document
    document = Document(
        title=title,
        content=description,
        document_type='case_study',
        world_id=world_id,
        source=source,
        doc_metadata=metadata,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow()
    )
    
    # Add to database
    db.session.add(document)
    db.session.commit()
    
    print(f"Created case document: {title} (ID: {document.id})")
    
    # Update the world's cases array
    update_world_cases(world_id, document.id)
    
    # Process document for embeddings
    try:
        embedding_service = EmbeddingService()
        embedding_service.process_document(document.id)
        print(f"Generated embeddings for document ID {document.id}")
    except Exception as e:
        print(f"Error processing embeddings: {str(e)}")
    
    # Process entity triples if available
    entity_triples = case_data.get('entity_triples', [])
    if entity_triples:
        try:
            triple_service = EntityTripleService()
            
            # Define common namespaces
            namespaces = {
                '': 'http://proethica.org/ontology/engineering-ethics#',
                'proeth': 'http://proethica.org/ontology/intermediate#',
                'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
                'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
                'case': f'http://proethica.org/case/{document.id}#'
            }
            
            # Import each triple
            for triple in entity_triples:
                subject = triple.get('subject', '')
                predicate = triple.get('predicate', '')
                object_value = triple.get('object', '')
                is_literal = triple.get('is_literal', False)
                
                # Expand namespaces if needed
                if ':' in subject:
                    prefix, name = subject.split(':', 1)
                    if prefix in namespaces:
                        subject = namespaces[prefix] + name
                
                if ':' in predicate:
                    prefix, name = predicate.split(':', 1)
                    if prefix in namespaces:
                        predicate = namespaces[prefix] + name
                
                if not is_literal and ':' in object_value:
                    prefix, name = object_value.split(':', 1)
                    if prefix in namespaces:
                        object_value = namespaces[prefix] + name
                
                # Create the triple
                triple_service.create_triple(
                    entity_type='document',
                    entity_id=document.id,
                    subject=subject,
                    predicate=predicate,
                    object_value=object_value,
                    is_literal=is_literal,
                    graph=f"world:{world_id}/document:{document.id}"
                )
            
            print(f"Imported {len(entity_triples)} triples for document ID {document.id}")
        except Exception as e:
            print(f"Error importing triples: {str(e)}")
    
    return document.id

def update_world_cases(world_id, document_id):
    """
    Update the world's cases array to include the new document.
    """
    from app.models.world import World
    
    # Get the world
    world = World.query.get(world_id)
    if not world:
        print(f"Error: World with ID {world_id} not found")
        return False
    
    # Check if cases is None and initialize if needed
    if world.cases is None:
        world.cases = []
    
    # Check if the document is already in the world's cases
    if document_id not in world.cases:
        # Add the document to the world's cases
        world.cases.append(document_id)
        
        # Update the world
        db.session.add(world)
        db.session.commit()
        
        print(f"Added document ID {document_id} to world ID {world_id} cases")
        return True
    else:
        print(f"Document ID {document_id} is already in world ID {world_id} cases")
        return False

def add_nspe_cases(world_id=ENGINEERING_WORLD_ID):
    """
    Add NSPE cases to the specified world.
    """
    app = create_app()
    with app.app_context():
        # Create cases
        created_cases = []
        for case_data in NEW_CASES:
            case_id = create_nspe_case(case_data, world_id)
            if case_id:
                created_cases.append(case_id)
        
        print(f"Added {len(created_cases)} new NSPE cases to world {world_id}")
        return created_cases

def main():
    """
    Main function to add NSPE cases.
    """
    print("===== Adding NSPE Engineering Ethics Cases =====")
    
    # Default world ID
    world_id = ENGINEERING_WORLD_ID
    
    # Process command line arguments
    if len(sys.argv) > 1:
        world_id = int(sys.argv[1])
    
    # Add the cases
    add_nspe_cases(world_id)
    
    print("Completed adding NSPE engineering ethics cases.")
    print("You can now view these cases in the Cases tab of the Engineering world.")

if __name__ == "__main__":
    main()
