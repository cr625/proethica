#!/usr/bin/env python3
"""
Script to add RDF triples to existing cases in the database.
This ensures that when users click "Edit Triples" on case detail pages,
they will have meaningful triples to work with.

Enhanced to:
1. Process cases in batches to avoid context window size issues
2. Create more tailored triples based on specific case content
3. Add more variety in ethical principles and relationships
4. Ensure proper namespace association
"""

import sys
import os
import re
from datetime import datetime
import time

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.document import Document
from app.models.world import World
from app.services.entity_triple_service import EntityTripleService

# Batch size for processing (to avoid context window size issues)
BATCH_SIZE = 5

# Create app context
app = create_app()
with app.app_context():
    # Initialize services
    triple_service = EntityTripleService()
    
    print("Starting to add RDF triples to cases...")
    
    # Get all documents that are case studies
    cases = Document.query.filter_by(document_type='case_study').all()
    print(f"Found {len(cases)} cases to process")
    
    # Define expanded namespace mappings
    nspe_full_namespaces = {
        "Case": "http://proethica.org/case/",
        "ENG_ETHICS": "http://proethica.org/eng_ethics/",
        "involves": "http://proethica.org/relation/",
        "NSPE": "http://proethica.org/code/nspe/",
        "Decision": "http://proethica.org/decision/",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "dc": "http://purl.org/dc/elements/1.1/",
        "bfo": "http://purl.obolibrary.org/obo/",
        "time": "http://www.w3.org/2006/time#",
        "owl": "http://www.w3.org/2002/07/owl#",
        "eth": "http://proethica.org/ethics/"
    }
    
    # Define expanded patterns to detect common ethical issues
    ethical_patterns = [
        (r'\bsafety\b|\bhazard\b|\bdanger\b|\brisk\b|\bhealth\b|\bwelfare\b', 'ENG_ETHICS:PublicSafety'),
        (r'\bconfident\w*\b|\bdisclos\w*\b|\bprivate\b|\bsecret\b|\bnon-disclosure\b', 'ENG_ETHICS:Confidentiality'),
        (r'\bconflict\w*( of)? interest\b|\bcompeting interest\b|\bdual role\b', 'ENG_ETHICS:ConflictOfInterest'),
        (r'\bwhistleblow\w*\b|\breport\w* violation\b|\bdisclose violation\b|\breport\w* wrongdoing\b', 'ENG_ETHICS:Whistleblowing'),
        (r'\benvironment\w*\b|\becologic\w*\b|\bsustainab\w*\b|\bpollution\b|\bclimate\b', 'ENG_ETHICS:EnvironmentalProtection'),
        (r'\bbribe\w*\b|\bcorrupt\w*\b|\bgift\b|\bpayment\b|\bkickback\b|\binfluenc\w* decision\b', 'ENG_ETHICS:Bribery'),
        (r'\bhonest\w*\b|\btruth\w*\b|\bmisrepresent\w*\b|\bfraud\w*\b|\bdeceiv\w*\b|\blie\b|\blying\b', 'ENG_ETHICS:Honesty'),
        (r'\bcompeten\w*\b|\bqualifi\w*\b|\bexpertise\b|\bskill\w*\b|\bknowledge\b|\btraining\b', 'ENG_ETHICS:Competence'),
        (r'\bintellectual property\b|\bpatent\b|\bcopyright\b|\btrademark\b|\btrade secret\b', 'ENG_ETHICS:IntellectualProperty'),
        (r'\bfair\w*\b|\bjust\w*\b|\bequit\w*\b|\bdiscriminat\w*\b|\bequal\w*\b', 'ENG_ETHICS:Fairness'),
        (r'\bpublic interest\b|\bsociety\b|\bcommunity welfare\b|\bcommon good\b', 'ENG_ETHICS:PublicInterest'),
        (r'\brespect\w*\b|\bdignity\b|\bautonomy\b|\bconsent\b', 'ENG_ETHICS:Respect'),
        (r'\bintegrity\b|\bconsisten\w*\b|\bmoral\w*\b|\bprinciple\w*\b', 'ENG_ETHICS:Integrity'),
        (r'\bresponsib\w*\b|\baccountab\w*\b|\bliab\w*\b', 'ENG_ETHICS:Responsibility'),
        (r'\btranspar\w*\b|\bopen\w*\b|\bdisclos\w*\b', 'ENG_ETHICS:Transparency')
    ]
    
    # Define expanded NSPE codes with more specific references
    nspe_codes = [
        ('PublicSafety', 'NSPE:CodeI.1'),       # Hold paramount the safety, health, and welfare of the public
        ('Competence', 'NSPE:CodeII.1'),        # Practice only in areas of competence
        ('Honesty', 'NSPE:CodeII.3'),           # Issue public statements only in an objective and truthful manner
        ('Confidentiality', 'NSPE:CodeIII.4'),  # Protect confidential information
        ('ConflictOfInterest', 'NSPE:CodeIII.1'), # Avoid conflicts of interest
        ('Integrity', 'NSPE:CodeII.4'),         # Act for each employer or client as faithful agents or trustees
        ('Bribery', 'NSPE:CodeII.5'),           # Avoid deceptive acts
        ('Whistleblowing', 'NSPE:CodeII.1.e'),  # Report violations
        ('PublicInterest', 'NSPE:CodeIII.2'),   # Act in professional matters for each employer or client
        ('IntellectualProperty', 'NSPE:CodeIII.8'), # Respect the intellectual property of others
        ('EnvironmentalProtection', 'NSPE:CodeI.1') # Consider environmental impact (interpretation)
    ]
    
    # Define common ethical conflicts that may arise between principles
    ethical_conflicts = [
        ('PublicSafety', 'Confidentiality', 'ENG_ETHICS:ConfidentialityVsSafety'),
        ('Whistleblowing', 'Confidentiality', 'ENG_ETHICS:WhistleblowingVsConfidentiality'),
        ('ConflictOfInterest', 'Integrity', 'ENG_ETHICS:ConflictVsIntegrity'),
        ('PublicInterest', 'ClientInterest', 'ENG_ETHICS:PublicVsClientInterest'),
        ('EnvironmentalProtection', 'ClientInterest', 'ENG_ETHICS:EnvironmentVsClientInterest'),
        ('Honesty', 'ClientInterest', 'ENG_ETHICS:HonestyVsClientInterest')
    ]
    
    # Process each case in batches
    total_processed = 0
    for batch_idx in range(0, len(cases), BATCH_SIZE):
        batch = cases[batch_idx:batch_idx + BATCH_SIZE]
        print(f"\nProcessing batch {batch_idx//BATCH_SIZE + 1}/{(len(cases) + BATCH_SIZE - 1)//BATCH_SIZE}")
        
        # Process each case in the batch
        for idx, case in enumerate(batch, 1):
            print(f"Processing case {batch_idx + idx}/{len(cases)}: {case.title} (ID: {case.id})")
            
            # Skip if the case already has entity triples
            existing_triples = triple_service.find_triples(entity_type='entity', entity_id=case.id)
            if existing_triples:
                print(f"  Case already has {len(existing_triples)} entity triples, skipping")
                continue
            
            # Initialize RDF triples list - customize based on case content
            triples = []
            
            # Create namespaces for this specific case
            # Start with common namespaces
            case_namespaces = nspe_full_namespaces.copy()
            
            # Add specialized namespaces based on case content if needed
            if case.world_id:
                world = World.query.get(case.world_id)
                if world:
                    # Add world-specific namespace if available
                    world_prefix = world.name.replace(" ", "")
                    case_namespaces[world_prefix] = f"http://proethica.org/world/{world.id}/"
            
            # Add basic case information triples
            triples.append({
                "subject": f"Case:{case.id}",
                "predicate": "rdf:type",
                "object": "ENG_ETHICS:EthicsCase",
                "is_literal": False
            })
            
            # Add case title
            triples.append({
                "subject": f"Case:{case.id}",
                "predicate": "dc:title",
                "object": case.title,
                "is_literal": True
            })
            
            # Get world information if available
            if case.world_id:
                world = World.query.get(case.world_id)
                if world:
                    triples.append({
                        "subject": f"Case:{case.id}",
                        "predicate": "belongsTo",
                        "object": f"World:{world.id}",
                        "is_literal": False
                    })
                    
                    # Add world name
                    triples.append({
                        "subject": f"World:{world.id}",
                        "predicate": "dc:title",
                        "object": world.name,
                        "is_literal": True
                    })
                    
                    # Link case to the world's domain
                    triples.append({
                        "subject": f"Case:{case.id}",
                        "predicate": "hasDomain",
                        "object": f"{world_prefix}:Domain",
                        "is_literal": False
                    })
            
            # Extract metadata - ensuring it's a dictionary
            metadata = {}
            if case.doc_metadata:
                if isinstance(case.doc_metadata, dict):
                    metadata = case.doc_metadata
            
            # Add case metadata
            if 'case_number' in metadata and metadata['case_number']:
                triples.append({
                    "subject": f"Case:{case.id}",
                    "predicate": "dc:identifier",
                    "object": metadata['case_number'],
                    "is_literal": True
                })
            
            if 'year' in metadata and metadata['year']:
                triples.append({
                    "subject": f"Case:{case.id}",
                    "predicate": "dc:date",
                    "object": str(metadata['year']),
                    "is_literal": True
                })
            
            # Analyze case content for ethical issues
            if case.content:
                # Convert content to lowercase for pattern matching
                content_lower = case.content.lower()
                
                # Check for ethical principles
                detected_principles = []
                for pattern, principle in ethical_patterns:
                    if re.search(pattern, content_lower):
                        principle_name = principle.split(':')[1]
                        detected_principles.append(principle_name)
                        
                        # Add the principle triple
                        triples.append({
                            "subject": f"Case:{case.id}",
                            "predicate": "involves:EthicalPrinciple",
                            "object": principle,
                            "is_literal": False
                        })
                        
                        # Add a more specific relationship based on the principle
                        if principle_name == "PublicSafety":
                            triples.append({
                                "subject": f"Case:{case.id}",
                                "predicate": "raises:Concern",
                                "object": "ENG_ETHICS:PublicSafetyConcern",
                                "is_literal": False
                            })
                        elif principle_name == "Confidentiality":
                            triples.append({
                                "subject": f"Case:{case.id}",
                                "predicate": "involves:Obligation",
                                "object": "ENG_ETHICS:ConfidentialityObligation",
                                "is_literal": False
                            })
                        elif principle_name == "ConflictOfInterest":
                            triples.append({
                                "subject": f"Case:{case.id}",
                                "predicate": "presents:Challenge",
                                "object": "ENG_ETHICS:ConflictingInterests",
                                "is_literal": False
                            })
                        elif principle_name == "Whistleblowing":
                            triples.append({
                                "subject": f"Case:{case.id}",
                                "predicate": "involves:Action",
                                "object": "ENG_ETHICS:ReportingViolation",
                                "is_literal": False
                            })
                
                # If we found multiple principles, check for conflicts
                if len(detected_principles) >= 2:
                    # Check for known ethical conflicts
                    for principle1, principle2, conflict in ethical_conflicts:
                        if principle1 in detected_principles and principle2 in detected_principles:
                            triples.append({
                                "subject": f"Case:{case.id}",
                                "predicate": "hasConflict",
                                "object": conflict,
                                "is_literal": False
                            })
                            
                            # Add detailed relationship for this conflict
                            conflict_name = conflict.split(':')[1]
                            triples.append({
                                "subject": conflict,
                                "predicate": "involves:Principle",
                                "object": f"ENG_ETHICS:{principle1}",
                                "is_literal": False
                            })
                            triples.append({
                                "subject": conflict,
                                "predicate": "involves:Principle",
                                "object": f"ENG_ETHICS:{principle2}",
                                "is_literal": False
                            })
                
                # Add NSPE code references based on detected principles
                for principle_name, code in nspe_codes:
                    if principle_name in detected_principles:
                        triples.append({
                            "subject": f"Case:{case.id}",
                            "predicate": "references:Code",
                            "object": code,
                            "is_literal": False
                        })
                        
                        # Add code description for context
                        code_descriptions = {
                            'NSPE:CodeI.1': "Engineers shall hold paramount the safety, health, and welfare of the public.",
                            'NSPE:CodeII.1': "Engineers shall undertake assignments only when qualified by education or experience in the specific technical fields involved.",
                            'NSPE:CodeII.3': "Engineers shall issue public statements only in an objective and truthful manner.",
                            'NSPE:CodeIII.1': "Engineers shall avoid all conflicts of interest.",
                            'NSPE:CodeIII.4': "Engineers shall not disclose, without consent, confidential information.",
                            'NSPE:CodeII.4': "Engineers shall act for each employer or client as faithful agents or trustees.",
                            'NSPE:CodeII.5': "Engineers shall avoid deceptive acts.",
                            'NSPE:CodeII.1.e': "Engineers having knowledge of any alleged violation of this Code shall report thereon to appropriate professional bodies and, when relevant, also to public authorities.",
                            'NSPE:CodeIII.2': "Engineers shall not accept compensation, financial or otherwise, from more than one party for services on the same project.",
                            'NSPE:CodeIII.8': "Engineers shall accept personal responsibility for their professional activities."
                        }
                        
                        if code in code_descriptions:
                            triples.append({
                                "subject": code,
                                "predicate": "dc:description",
                                "object": code_descriptions[code],
                                "is_literal": True
                            })
                
                # Try to determine a decision (requires analysis of the content)
                # This is improved with more nuanced pattern matching
                decision_class = None
                decision_words = r'\bunethical\b|\bviolation\b|\bimproper\b|\bwrongful\b|\bfailed\b|\bmisconduct\b'
                ethical_words = r'\bethical\b|\bproper\b|\bappropriate\b|\bcompliant\b|\bcorrect\b|\bfulfilled\b'
                complex_words = r'\bbalance\b|\btradeoff\b|\bdilemma\b|\bconsider\b|\bweigh\b|\bboth sides\b'
                
                if re.search(decision_words, content_lower):
                    decision_class = "Decision:Unethical"
                elif re.search(ethical_words, content_lower):
                    decision_class = "Decision:Ethical"
                elif re.search(complex_words, content_lower):
                    decision_class = "Decision:Complex"
                else:
                    # Look for more context to determine a default
                    if 'ethical_analysis' in metadata and metadata['ethical_analysis']:
                        analysis_lower = metadata['ethical_analysis'].lower()
                        if re.search(decision_words, analysis_lower):
                            decision_class = "Decision:Unethical"
                        elif re.search(ethical_words, analysis_lower):
                            decision_class = "Decision:Ethical"
                        elif re.search(complex_words, analysis_lower):
                            decision_class = "Decision:Complex"
                        else:
                            decision_class = "Decision:Complex"  # Default for cases with analysis
                    else:
                        # If we still can't determine, use Complex as the default
                        decision_class = "Decision:Complex"
                
                triples.append({
                    "subject": f"Case:{case.id}",
                    "predicate": "hasDecision",
                    "object": decision_class,
                    "is_literal": False
                })
                
                # Add decision classifications with descriptions
                decision_descriptions = {
                    "Decision:Ethical": "The actions or decisions described in this case were deemed ethical and in compliance with engineering ethics codes.",
                    "Decision:Unethical": "The actions or decisions described in this case were deemed unethical or in violation of engineering ethics codes.",
                    "Decision:Complex": "This case presents a complex ethical situation with multiple valid perspectives or competing ethical principles."
                }
                
                if decision_class in decision_descriptions:
                    triples.append({
                        "subject": decision_class,
                        "predicate": "dc:description",
                        "object": decision_descriptions[decision_class],
                        "is_literal": True
                    })
            
            # If we have metadata about decision or analysis, add those too
            if 'decision' in metadata and metadata['decision']:
                triples.append({
                    "subject": f"Case:{case.id}",
                    "predicate": "dc:description",
                    "object": metadata['decision'],
                    "is_literal": True
                })
            
            if 'ethical_analysis' in metadata and metadata['ethical_analysis']:
                triples.append({
                    "subject": f"Case:{case.id}",
                    "predicate": "hasAnalysis",
                    "object": metadata['ethical_analysis'],
                    "is_literal": True
                })
                
                # Add analysis date if available, otherwise use current timestamp
                analysis_date = datetime.now().isoformat()
                triples.append({
                    "subject": f"Case:{case.id}",
                    "predicate": "analysisDate",
                    "object": analysis_date,
                    "is_literal": True
                })
            
            # Save triples to document metadata
            if not case.doc_metadata:
                case.doc_metadata = {}
            
            case.doc_metadata['rdf_triples'] = triples
            case.doc_metadata['rdf_namespaces'] = case_namespaces
            
            # Store in database
            db.session.add(case)
            
            # Create entity triples
            try:
                for triple in triples:
                    triple_service.add_triple(
                        subject=triple['subject'],
                        predicate=triple['predicate'],
                        obj=triple['object'],
                        is_literal=triple['is_literal'],
                        graph=f"case:{case.id}",
                        entity_type='entity',
                        entity_id=case.id
                    )
                print(f"  Added {len(triples)} entity triples")
            except Exception as e:
                print(f"  Error creating entity triples: {str(e)}")
                
            # Commit after each case to avoid large transactions
            db.session.commit()
            
            # Add a small delay to prevent database overload
            time.sleep(0.1)
            
            # Increment counter
            total_processed += 1
            
        # Commit batch changes
        print(f"\nBatch completed. Committing changes...")
        db.session.commit()
        
        # Print status
        print(f"Processed {total_processed}/{len(cases)} cases so far")
        
        # Add a small delay between batches
        time.sleep(1)
    
    print("\nCompleted adding RDF triples to cases")
    print(f"Processed {total_processed} cases in total")
#!/usr/bin/env python3
"""
Script to add RDF triples to existing cases in the database.
This ensures that when users click "Edit Triples" on case detail pages,
they will have meaningful triples to work with.
"""

import sys
import os
import re
from datetime import datetime

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.document import Document
from app.models.world import World
from app.services.entity_triple_service import EntityTripleService

# Create app context
app = create_app()
with app.app_context():
    # Initialize services
    triple_service = EntityTripleService()
    
    print("Starting to add RDF triples to cases...")
    
    # Get all documents that are case studies
    cases = Document.query.filter_by(document_type='case_study').all()
    print(f"Found {len(cases)} cases to process")
    
    # Define common namespaces
    common_namespaces = {
        "Case": "http://proethica.org/case/",
        "ENG_ETHICS": "http://proethica.org/eng_ethics/",
        "involves": "http://proethica.org/relation/",
        "NSPE": "http://proethica.org/code/nspe/",
        "Decision": "http://proethica.org/decision/"
    }
    
    # Define patterns to detect common ethical issues
    ethical_patterns = [
        (r'\bsafety\b|\bhazard\b|\bdanger\b|\brisk\b', 'ENG_ETHICS:PublicSafety'),
        (r'\bconfident\w*\b|\bdisclos\w*\b|\bprivate\b|\bsecret\b', 'ENG_ETHICS:Confidentiality'),
        (r'\bconflict\w*( of)? interest\b', 'ENG_ETHICS:ConflictOfInterest'),
        (r'\bwhistleblow\w*\b|\breport\w* violation\b', 'ENG_ETHICS:Whistleblowing'),
        (r'\benvironment\w*\b|\becologic\w*\b|\bsustainab\w*\b', 'ENG_ETHICS:EnvironmentalProtection'),
        (r'\bbribe\w*\b|\bcorrupt\w*\b|\bgift\b', 'ENG_ETHICS:Bribery'),
        (r'\bhonest\w*\b|\btruth\w*\b|\bmisrepresent\w*\b', 'ENG_ETHICS:Honesty'),
        (r'\bcompeten\w*\b|\bqualifi\w*\b|\bexpertise\b', 'ENG_ETHICS:Competence'),
        (r'\bintellectual property\b|\bpatent\b|\bcopyright\b', 'ENG_ETHICS:IntellectualProperty')
    ]
    
    # Define common NSPE codes
    nspe_codes = [
        ('PublicSafety', 'NSPE:CodeI.1'),  # Hold paramount the safety, health, and welfare of the public
        ('Competence', 'NSPE:CodeII.1'),   # Practice only in areas of competence
        ('Honesty', 'NSPE:CodeII.3'),      # Issue public statements only in an objective and truthful manner
        ('Confidentiality', 'NSPE:CodeIII.4')  # Protect confidential information
    ]
    
    # Process each case
    for idx, case in enumerate(cases, 1):
        print(f"Processing case {idx}/{len(cases)}: {case.title} (ID: {case.id})")
        
        # Skip if the case already has entity triples
        existing_triples = triple_service.find_triples(entity_type='entity', entity_id=case.id)
        if existing_triples:
            print(f"  Case already has {len(existing_triples)} entity triples, skipping")
            continue
        
        # Initialize RDF triples list
        triples = []
        
        # Add basic case information triples
        triples.append({
            "subject": f"Case:{case.id}",
            "predicate": "rdf:type",
            "object": "ENG_ETHICS:EthicsCase",
            "is_literal": False
        })
        
        # Add case title
        triples.append({
            "subject": f"Case:{case.id}",
            "predicate": "dc:title",
            "object": case.title,
            "is_literal": True
        })
        
        # Get world information if available
        if case.world_id:
            world = World.query.get(case.world_id)
            if world:
                triples.append({
                    "subject": f"Case:{case.id}",
                    "predicate": "belongsTo",
                    "object": f"World:{world.id}",
                    "is_literal": False
                })
                
                # Add world name
                triples.append({
                    "subject": f"World:{world.id}",
                    "predicate": "dc:title",
                    "object": world.name,
                    "is_literal": True
                })
        
        # Analyze case content for ethical issues
        if case.content:
            # Convert content to lowercase for pattern matching
            content_lower = case.content.lower()
            
            # Check for ethical principles
            detected_principles = []
            for pattern, principle in ethical_patterns:
                if re.search(pattern, content_lower):
                    detected_principles.append(principle)
                    triples.append({
                        "subject": f"Case:{case.id}",
                        "predicate": "involves:EthicalPrinciple",
                        "object": principle,
                        "is_literal": False
                    })
            
            # If we found multiple principles, check for conflicts
            if len(detected_principles) >= 2:
                for i in range(len(detected_principles)):
                    for j in range(i+1, len(detected_principles)):
                        # Check for common conflicts
                        if ('PublicSafety' in detected_principles[i] and 'Confidentiality' in detected_principles[j]) or \
                           ('PublicSafety' in detected_principles[j] and 'Confidentiality' in detected_principles[i]):
                            triples.append({
                                "subject": f"Case:{case.id}",
                                "predicate": "hasConflict",
                                "object": "ENG_ETHICS:ConfidentialityVsSafety",
                                "is_literal": False
                            })
            
            # Add NSPE code references based on detected principles
            for principle_name, code in nspe_codes:
                for principle in detected_principles:
                    if principle_name in principle:
                        triples.append({
                            "subject": f"Case:{case.id}",
                            "predicate": "references:Code",
                            "object": code,
                            "is_literal": False
                        })
            
            # Try to determine a decision (requires analysis of the content)
            # This is simplified and could be improved with NLP
            decision_words = r'\bunethical\b|\bviolation\b|\bimproper\b|\bwrongful\b'
            if re.search(decision_words, content_lower):
                triples.append({
                    "subject": f"Case:{case.id}",
                    "predicate": "hasDecision",
                    "object": "Decision:Unethical",
                    "is_literal": False
                })
            else:
                ethical_words = r'\bethical\b|\bproper\b|\bappropriate\b|\bcompliant\b'
                if re.search(ethical_words, content_lower):
                    triples.append({
                        "subject": f"Case:{case.id}",
                        "predicate": "hasDecision",
                        "object": "Decision:Ethical",
                        "is_literal": False
                    })
                else:
                    # If we can't determine, assume it's a complex case
                    triples.append({
                        "subject": f"Case:{case.id}",
                        "predicate": "hasDecision",
                        "object": "Decision:Complex",
                        "is_literal": False
                    })
        
        # If we have metadata about decision or analysis, add those too
        metadata = case.doc_metadata or {}
        
        if 'decision' in metadata and metadata['decision']:
            triples.append({
                "subject": f"Case:{case.id}",
                "predicate": "dc:description",
                "object": metadata['decision'],
                "is_literal": True
            })
        
        if 'ethical_analysis' in metadata and metadata['ethical_analysis']:
            triples.append({
                "subject": f"Case:{case.id}",
                "predicate": "hasAnalysis",
                "object": metadata['ethical_analysis'],
                "is_literal": True
            })
        
        # Save triples to document metadata
        if not case.doc_metadata:
            case.doc_metadata = {}
        
        case.doc_metadata['rdf_triples'] = triples
        case.doc_metadata['rdf_namespaces'] = common_namespaces
        
        # Store in database
        db.session.add(case)
        
        # Create entity triples
        try:
            for triple in triples:
                triple_service.add_triple(
                    subject=triple['subject'],
                    predicate=triple['predicate'],
                    obj=triple['object'],
                    is_literal=triple['is_literal'],
                    graph=f"case:{case.id}",
                    entity_type='entity',
                    entity_id=case.id
                )
            print(f"  Added {len(triples)} entity triples")
        except Exception as e:
            print(f"  Error creating entity triples: {str(e)}")
    
    # Commit all changes
    db.session.commit()
    print("\nCompleted adding RDF triples to cases")
    print(f"Processed {len(cases)} cases")
