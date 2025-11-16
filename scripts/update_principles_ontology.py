#!/usr/bin/env python3
"""
Update Principles in proethica-intermediate ontology based on Chapter 2.2.2 Literature.
Following the pattern established for Roles enhancements.

Based on:
- McLaren (2003): Extensional definition through cases and precedents
- Taddeo et al. (2024): Three-step operationalization process
- Hallamaa & Kalliokoski (2022): Context-sensitive mediation
- Anderson & Anderson (2018): Principles learned from expert examples
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

# Database credentials
DB_HOST = 'localhost'
DB_NAME = 'ontserve'
DB_USER = 'postgres'
DB_PASSWORD = 'PASS'

# Principle definitions to add based on Chapter 2.2.2
PRINCIPLE_UPDATES = """
# ====================================================================
# PRINCIPLE SUBCLASSES BASED ON CHAPTER 2.2.2 LITERATURE
# ====================================================================

# Core Principle Categories from Chapter 2.2.2 Analysis
:FundamentalEthicalPrinciple rdf:type owl:Class ;
    rdf:type :EntityType ;
    rdfs:subClassOf :Principle ;
    rdfs:label "Fundamental Ethical Principle"@en ;
    iao:0000115 "A universal moral foundation that serves as the highest-level abstraction in professional ethics, requiring extensive interpretation through concrete cases (BFO: generically dependent continuant)"@en ;
    skos:definition "According to McLaren (2003), fundamental principles like public welfare and respect for persons cannot be applied through formal deduction alone but require extensional definition through landmark ethics cases and professional code applications. These principles function as constitutional-like foundations (Taddeo et al. 2024) that mediate moral ideals into professional practice (Hallamaa & Kalliokoski 2022)."@en ;
    dcterms:source <https://doi.org/10.1023/A:1024195425598> , # McLaren 2003
                   <https://doi.org/10.1007/s00146-024-01870-x> , # Taddeo et al. 2024
                   <https://doi.org/10.1080/08989621.2022.2054267> ; # Hallamaa & Kalliokoski 2022
    rdfs:comment "Examples: Public Welfare Paramount, Respect for Persons, Justice, Beneficence. These require extensive interpretation and balancing in specific contexts."@en .

:ProfessionalVirtuePrinciple rdf:type owl:Class ;
    rdf:type :EntityType ;
    rdfs:subClassOf :Principle ;
    rdfs:label "Professional Virtue Principle"@en ;
    iao:0000115 "A character-based principle defining professional excellence and ethical sensitivities specific to professional identity (BFO: generically dependent continuant)"@en ;
    skos:definition "Professional virtue principles guide professional identity formation and ethical sensitivities (Oakley & Cocking 2001). These principles are learned through expert examples (Anderson & Anderson 2018) and exemplified through model professional behavior cases, creating role-generated moral demands that shape professional character."@en ;
    dcterms:source <https://doi.org/10.1017/CBO9780511489471> , # Oakley & Cocking 2001
                   <https://doi.org/10.1007/s10994-018-5753-x> ; # Anderson & Anderson 2018
    rdfs:comment "Examples: Integrity, Competence, Honesty, Professional Courage, Accountability. These shape professional character and decision-making."@en .

:RelationalPrinciple rdf:type owl:Class ;
    rdf:type :EntityType ;
    rdfs:subClassOf :Principle ;
    rdfs:label "Relational Principle"@en ;
    iao:0000115 "A principle governing professional relationships and establishing frameworks for trust and stakeholder interactions (BFO: generically dependent continuant)"@en ;
    skos:definition "Relational principles establish frameworks for managing professional relationships and stakeholder trust. Following McLaren's extensional approach, these principles gain meaning through precedents from client-professional disputes and resolutions, defining how professionals navigate competing interests and maintain trustworthy relationships."@en ;
    dcterms:source <https://doi.org/10.1023/A:1024195425598> , # McLaren 2003
                   <https://doi.org/10.1080/10508422.2016.1155099> ; # Dennis et al. 2016
    rdfs:comment "Examples: Confidentiality, Loyalty, Fairness, Transparency, Respect for Autonomy. These govern interpersonal professional dynamics."@en .

:DomainSpecificPrinciple rdf:type owl:Class ;
    rdf:type :EntityType ;
    rdfs:subClassOf :Principle ;
    rdfs:label "Domain-Specific Principle"@en ;
    iao:0000115 "A principle particular to professional domain contexts that bridges general ethics to specific technical practices (BFO: generically dependent continuant)"@en ;
    skos:definition "Domain-specific principles bridge general ethical guidance to particular professional contexts. As identified by Prem (2023), these principles face inherent challenges in operationalization but remain essential for contextual guidance. They are grounded through industry-specific cases and technical standards applications."@en ;
    dcterms:source <https://doi.org/10.1007/s00146-023-01687-0> , # Prem 2023
                   <https://doi.org/10.1007/s10676-021-09586-y> ; # Segun 2021
    rdfs:comment "Examples: Environmental Stewardship (engineering), Patient Autonomy (medicine), Academic Freedom (education). These address domain-specific ethical challenges."@en .

# Specific Principle Instances commonly found in Professional Codes
:PublicWelfarePrinciple rdf:type owl:Class ;
    rdf:type :EntityType ;
    rdfs:subClassOf :FundamentalEthicalPrinciple ;
    rdfs:label "Public Welfare Principle"@en ;
    iao:0000115 "The fundamental principle that public safety, health, and welfare must be held paramount in professional practice (BFO: generically dependent continuant)"@en ;
    skos:definition "The public welfare principle, as articulated in NSPE Fundamental Canon 1, requires professionals to hold paramount the safety, health, and welfare of the public. This principle exemplifies McLaren's challenge of operationalizing abstract guidance - 'hold paramount' gains meaning only through NSPE case applications and precedents like the Challenger disaster."@en ;
    dcterms:source <https://doi.org/10.1023/A:1024195425598> , # McLaren 2003
                   "NSPE Code of Ethics Fundamental Canon 1" ;
    proeth:nspeReference "Fundamental Canon 1" ;
    proeth:extensionalCases "NSPE BER Case 92-6", "Challenger Disaster", "Hyatt Regency Walkway Collapse" ;
    rdfs:comment "Requires contextual interpretation to balance against client confidentiality and employer loyalty when public safety is at risk."@en .

:IntegrityPrinciple rdf:type owl:Class ;
    rdf:type :EntityType ;
    rdfs:subClassOf :ProfessionalVirtuePrinciple ;
    rdfs:label "Integrity Principle"@en ;
    iao:0000115 "The professional virtue principle of maintaining honesty, truthfulness, and ethical consistency in professional practice (BFO: generically dependent continuant)"@en ;
    skos:definition "Professional integrity requires contextual interpretation through cases (Kong et al. 2020) and manifests differently across professional contexts. It encompasses honesty in professional communications, truthfulness in representations, and consistency between professional values and actions."@en ;
    dcterms:source <https://doi.org/10.1007/s10676-020-09538-y> , # Kong et al. 2020
                   "NSPE Code of Ethics II.3" ;
    proeth:nspeReference "Rule of Practice II.3" ;
    rdfs:comment "Central to professional identity formation and trust maintenance in professional relationships."@en .

:CompetencePrinciple rdf:type owl:Class ;
    rdf:type :EntityType ;
    rdfs:subClassOf :ProfessionalVirtuePrinciple ;
    rdfs:label "Competence Principle"@en ;
    iao:0000115 "The professional virtue principle requiring maintenance and application of professional knowledge and skill within areas of competence (BFO: generically dependent continuant)"@en ;
    skos:definition "The competence principle requires professionals to perform services only in areas of their competence and to maintain professional knowledge through continuous learning. This principle generates obligations for professional development and honest self-assessment of capabilities."@en ;
    dcterms:source "NSPE Code of Ethics II.2" ,
                   <https://doi.org/10.1017/CBO9780511489471> ; # Oakley & Cocking 2001
    proeth:nspeReference "Rule of Practice II.2" ;
    rdfs:comment "Balances professional autonomy with recognition of limitations and need for collaboration."@en .

:ConfidentialityPrinciple rdf:type owl:Class ;
    rdf:type :EntityType ;
    rdfs:subClassOf :RelationalPrinciple ;
    rdfs:label "Confidentiality Principle"@en ;
    iao:0000115 "The relational principle protecting client information and maintaining trust in professional relationships (BFO: generically dependent continuant)"@en ;
    skos:definition "Confidentiality establishes trust frameworks in professional relationships by protecting client information from unauthorized disclosure. This principle requires balancing through precedents when it conflicts with public welfare or legal obligations."@en ;
    dcterms:source "NSPE Code of Ethics II.1.c" ,
                   <https://doi.org/10.1023/A:1024195425598> ; # McLaren 2003
    proeth:nspeReference "Rule of Practice II.1.c" ;
    rdfs:comment "Must be balanced against public safety obligations and legal disclosure requirements."@en .

:TransparencyPrinciple rdf:type owl:Class ;
    rdf:type :EntityType ;
    rdfs:subClassOf :RelationalPrinciple ;
    rdfs:label "Transparency Principle"@en ;
    iao:0000115 "The relational principle requiring openness and disclosure in professional communications and decision-making (BFO: generically dependent continuant)"@en ;
    skos:definition "Transparency requires professionals to be open about conflicts of interest, limitations, and decision-making processes. This principle supports accountability and enables informed consent from stakeholders."@en ;
    dcterms:source "NSPE Code of Ethics II.4" ,
                   <https://doi.org/10.1080/10508422.2016.1155099> ; # Dennis et al. 2016
    proeth:nspeReference "Rule of Practice II.4" ;
    rdfs:comment "Essential for maintaining trust and enabling stakeholder participation in professional decisions."@en .

:EnvironmentalStewardshipPrinciple rdf:type owl:Class ;
    rdf:type :EntityType ;
    rdfs:subClassOf :DomainSpecificPrinciple ;
    rdfs:label "Environmental Stewardship Principle"@en ;
    iao:0000115 "The domain-specific principle in engineering requiring consideration of environmental impact and sustainability (BFO: generically dependent continuant)"@en ;
    skos:definition "Environmental stewardship in engineering requires balancing technical solutions with environmental protection and sustainable development. This principle has evolved through cases addressing pollution, resource depletion, and climate change impacts."@en ;
    dcterms:source "NSPE Code of Ethics III.2.d" ,
                   <https://doi.org/10.1007/s00146-023-01687-0> ; # Prem 2023
    proeth:nspeReference "Professional Obligation III.2.d" ;
    rdfs:comment "Bridges engineering practice with broader environmental and societal responsibilities."@en .
"""

def update_ontology():
    """Update the ontology with enhanced Principle definitions."""
    
    print("Starting Principle ontology updates based on Chapter 2.2.2...")
    
    # Read current ontology
    ontology_path = '/home/chris/onto/proethica/ontologies/proethica-intermediate.ttl'
    backup_path = '/home/chris/onto/proethica/ontologies/proethica-intermediate-backup-principles.ttl'
    
    with open(ontology_path, 'r') as f:
        content = f.read()
    
    # Create backup
    with open(backup_path, 'w') as f:
        f.write(content)
    print(f"Created backup at {backup_path}")
    
    # Check if updates already exist
    if ':FundamentalEthicalPrinciple' in content:
        print("Principle subclasses already exist in ontology")
        return
    
    # Find insertion point (after Principle definition)
    insertion_point = content.find(':Obligation rdf:type owl:Class')
    if insertion_point == -1:
        print("Could not find insertion point")
        return
    
    # Insert new definitions
    updated_content = (
        content[:insertion_point] + 
        PRINCIPLE_UPDATES + '\n\n' +
        content[insertion_point:]
    )
    
    # Write updated ontology
    with open(ontology_path, 'w') as f:
        f.write(updated_content)
    
    print("Successfully added Principle subclasses to ontology")
    
    # Update database
    print("\nUpdating database...")
    import subprocess
    
    # Run the refresh script
    result = subprocess.run([
        'python', 
        '/home/chris/onto/proethica/scripts/refresh_entity_extraction.py',
        'proethica-intermediate'
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("Database update successful")
        print(result.stdout)
    else:
        print("Database update failed:")
        print(result.stderr)
    
    # Update DatabaseConceptManager if needed
    print("\nUpdating DatabaseConceptManager subclass mappings...")
    
    manager_path = '/home/chris/onto/OntServe/storage/concept_manager_database.py'
    with open(manager_path, 'r') as f:
        manager_content = f.read()
    
    # Check if Principle mappings need updating
    if "'Principle': [" in manager_content:
        # Find and update the Principle line
        import re
        pattern = r"'Principle': \[[^\]]*\]"
        replacement = "'Principle': ['FundamentalEthicalPrinciple', 'ProfessionalVirtuePrinciple', 'RelationalPrinciple', 'DomainSpecificPrinciple', 'PublicWelfarePrinciple', 'IntegrityPrinciple', 'CompetencePrinciple', 'ConfidentialityPrinciple', 'TransparencyPrinciple', 'EnvironmentalStewardshipPrinciple']"
        
        updated_manager = re.sub(pattern, replacement, manager_content)
        
        if updated_manager != manager_content:
            with open(manager_path, 'w') as f:
                f.write(updated_manager)
            print("Updated DatabaseConceptManager with new Principle subclasses")
        else:
            print("DatabaseConceptManager already up to date")
    
    print("\nPrinciple ontology updates complete!")
    print("\nNext steps:")
    print("1. Verify entities extracted: curl http://localhost:5003/api/ontologies | jq")
    print("2. Check new principles: PGPASSWORD=PASS psql -h localhost -U postgres -d ontserve -c \"SELECT label FROM ontology_entities WHERE label LIKE '%Principle' ORDER BY label;\"")

if __name__ == "__main__":
    update_ontology()