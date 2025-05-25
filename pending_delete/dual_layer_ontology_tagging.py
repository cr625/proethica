#!/usr/bin/env python3
"""
Dual-Layer Ontology Tagging Example
-----------------------------------
Demonstrates the proposed dual-layer ontology tagging approach for engineering ethics cases:
1. Case level (McLaren extensional elements aligned with BFO)
2. Scenario level (intermediate ontology elements)

Using NSPE Case 21-3: "Offer of Free or Reduced Fee Services" as an example
"""

import psycopg2
import json
import uuid
from datetime import datetime

# Database connection parameters
DB_PARAMS = {
    "dbname": "ai_ethical_dm",
    "user": "postgres",
    "password": "PASS",
    "host": "localhost",
    "port": "5433"
}

# Case details from NSPE Case 21-3
CASE_ID = 168  # Assuming this is the ID in our system
CASE_TITLE = "Offer of Free or Reduced Fee Services"
CASE_NUMBER = "21-3"

# ---------------------------------------------------------------
# PART 1: McLaren Extensional Definition Approach (Case Level)
# Mapped to BFO-aligned classes
# ---------------------------------------------------------------

def create_mclaren_triples(conn, case_id):
    """Create entity triples based on McLaren's extensional definition approach"""
    print("Creating McLaren extensional definition triples...")
    
    cur = conn.cursor()
    triples = []
    
    # 1. Principle Instantiations
    # Each principle is mapped as a BFO:GenericallyDependentContinuant
    # The instantiation is a BFO:Process
    
    # Principle: Professional Integrity (II.5.B)
    triples.append({
        "subject": f"Engineer A's offer of free services",
        "predicate": "http://proethica.org/ontology/engineering-ethics#instantiatesPrinciple",
        "object_uri": "http://proethica.org/ontology/engineering-ethics#ProfessionalIntegrity",
        "is_literal": False,
        "entity_type": "document",
        "entity_id": case_id,
        "triple_metadata": {
            "bfo_classification": "http://purl.obolibrary.org/obo/BFO_0000015",  # Process
            "principle_code": "II.5.B",
            "principle_text": "Engineers shall not offer any gift or valuable consideration in order to secure work"
        }
    })
    
    # Principle: Fairness (III.1.F)
    triples.append({
        "subject": f"Engineer A's competitive advantage",
        "predicate": "http://proethica.org/ontology/engineering-ethics#instantiatesPrinciple",
        "object_uri": "http://proethica.org/ontology/engineering-ethics#Fairness",
        "is_literal": False,
        "entity_type": "document",
        "entity_id": case_id,
        "triple_metadata": {
            "bfo_classification": "http://purl.obolibrary.org/obo/BFO_0000015",  # Process
            "principle_code": "III.1.F",
            "principle_text": "Engineers shall treat all persons with fairness"
        }
    })
    
    # 2. Principle Conflicts
    triples.append({
        "subject": f"Competitive advantage",
        "predicate": "http://proethica.org/ontology/engineering-ethics#conflictsWith",
        "object_literal": "Fair competition",
        "is_literal": True,
        "entity_type": "document",
        "entity_id": case_id,
        "triple_metadata": {
            "bfo_classification": "http://purl.obolibrary.org/obo/BFO_0000015",  # Process
            "conflict_description": "Engineer A's attempt to gain competitive advantage conflicts with fair treatment of competitors"
        }
    })
    
    # 3. Operationalization Techniques
    # McLaren's operationalization techniques as BFO:Process
    triples.append({
        "subject": f"Free Preliminary Engineering",
        "predicate": "http://proethica.org/ontology/mclaren-extensional#usesOperationalizationTechnique",
        "object_uri": "http://proethica.org/ontology/mclaren-extensional#FactualApplication",
        "is_literal": False,
        "entity_type": "document",
        "entity_id": case_id,
        "triple_metadata": {
            "bfo_classification": "http://purl.obolibrary.org/obo/BFO_0000015",  # Process
            "technique_description": "Applying ethics principles to concrete facts of the case"
        }
    })
    
    # Insert all triples into the database
    for triple in triples:
        # Add common fields - don't set ID, let the database auto-generate it
        triple["graph"] = "http://proethica.org/ontology/case-analysis"
        triple["created_at"] = datetime.now().isoformat()
        triple["updated_at"] = datetime.now().isoformat()
        
        # Convert metadata to JSON string or object
        if isinstance(triple["triple_metadata"], dict):
            triple["triple_metadata"] = json.dumps(triple["triple_metadata"])
        
        # Create SQL placeholders for the keys
        keys = triple.keys()
        placeholders = ', '.join([f"%({key})s" for key in keys])
        columns = ', '.join(keys)
        
        # Insert query
        query = f"INSERT INTO entity_triples ({columns}) VALUES ({placeholders})"
        cur.execute(query, triple)
    
    conn.commit()
    cur.close()
    print(f"Added {len(triples)} McLaren extensional definition triples for case {case_id}")
    return triples


# ---------------------------------------------------------------
# PART 2: Intermediate Ontology Tagging (Scenario Level)
# Using the ProEthica intermediate ontology roles, resources, etc.
# ---------------------------------------------------------------

def create_scenario_triples(conn, case_id):
    """Create entity triples based on the intermediate ontology for scenario conversion"""
    print("Creating intermediate ontology triples for scenario conversion...")
    
    cur = conn.cursor()
    triples = []
    
    # 1. Roles (mapped to BFO:Role) - Using specific role types instead of generic Role
    triples.append({
        "subject": f"Case {case_id}",
        "predicate": "http://proethica.org/ontology/engineering-ethics#hasRole",
        "object_uri": "http://proethica.org/ontology/engineering-ethics#EngineeringConsultantRole",
        "is_literal": False,
        "entity_type": "document",
        "entity_id": case_id,
        "triple_metadata": {
            "bfo_classification": "http://purl.obolibrary.org/obo/BFO_0000023",  # Role
            "role_description": "Engineering firm principal offering services",
            "role_bearer": "Engineer A"
        }
    })
    
    triples.append({
        "subject": f"Case {case_id}",
        "predicate": "http://proethica.org/ontology/engineering-ethics#hasRole",
        "object_uri": "http://proethica.org/ontology/engineering-ethics#ClientRole",
        "is_literal": False,
        "entity_type": "document",
        "entity_id": case_id,
        "triple_metadata": {
            "bfo_classification": "http://purl.obolibrary.org/obo/BFO_0000023",  # Role
            "role_description": "Municipality seeking engineering services",
            "role_bearer": "City"
        }
    })
    
    triples.append({
        "subject": f"Case {case_id}",
        "predicate": "http://proethica.org/ontology/engineering-ethics#hasRole",
        "object_uri": "http://proethica.org/ontology/engineering-ethics#RegulatoryAuthorityRole",
        "is_literal": False,
        "entity_type": "document",
        "entity_id": case_id,
        "triple_metadata": {
            "bfo_classification": "http://purl.obolibrary.org/obo/BFO_0000023",  # Role
            "role_description": "Regulatory agency enforcing water standards",
            "role_bearer": "State Environmental Agency"
        }
    })
    
    # 2. Resources (mapped to BFO:IndependentContinuant) - Using more specific predicates and resources
    triples.append({
        "subject": f"Case {case_id}",
        "predicate": "http://proethica.org/ontology/engineering-ethics#involvesResource",
        "object_uri": "http://proethica.org/ontology/engineering-ethics#MunicipalWaterSystem",
        "is_literal": False,
        "entity_type": "document",
        "entity_id": case_id,
        "triple_metadata": {
            "bfo_classification": "http://purl.obolibrary.org/obo/BFO_0000004",  # IndependentContinuant
            "resource_description": "Municipal water system requiring remediation",
            "resource_owner": "City"
        }
    })
    
    triples.append({
        "subject": f"Case {case_id}",
        "predicate": "http://proethica.org/ontology/engineering-ethics#involvesProcurementDocument",
        "object_uri": "http://proethica.org/ontology/engineering-ethics#RequestForQualifications",
        "is_literal": False,
        "entity_type": "document",
        "entity_id": case_id,
        "triple_metadata": {
            "bfo_classification": "http://purl.obolibrary.org/obo/BFO_0000031",  # Document
            "resource_description": "RFQ issued by city for engineering services",
            "issuer": "City"
        }
    })
    
    # 3. Events (mapped to BFO:Process) - Using specific event types instead of generic EventType
    triples.append({
        "subject": f"Case {case_id}",
        "predicate": "http://proethica.org/ontology/engineering-ethics#involvesEvent",
        "object_uri": "http://proethica.org/ontology/engineering-ethics#RegulatoryNotification",
        "is_literal": False,
        "entity_type": "document",
        "entity_id": case_id,
        "triple_metadata": {
            "bfo_classification": "http://purl.obolibrary.org/obo/BFO_0000015",  # Process
            "event_description": "State agency notifying city of water system non-compliance",
            "event_initiator": "State Environmental Agency",
            "event_recipient": "City"
        }
    })
    
    triples.append({
        "subject": f"Case {case_id}",
        "predicate": "http://proethica.org/ontology/engineering-ethics#involvesEvent",
        "object_uri": "http://proethica.org/ontology/engineering-ethics#ProcurementProcess",
        "is_literal": False,
        "entity_type": "document",
        "entity_id": case_id,
        "triple_metadata": {
            "bfo_classification": "http://purl.obolibrary.org/obo/BFO_0000015",  # Process
            "event_description": "City's process for selecting engineering services",
            "event_initiator": "City"
        }
    })
    
    # 4. Actions (mapped to BFO:Process with agent causality) - Using specific action types
    triples.append({
        "subject": f"Case {case_id}",
        "predicate": "http://proethica.org/ontology/engineering-ethics#involvesAction",
        "object_uri": "http://proethica.org/ontology/engineering-ethics#OfferingFreeServices",
        "is_literal": False,
        "entity_type": "document",
        "entity_id": case_id,
        "triple_metadata": {
            "bfo_classification": "http://purl.obolibrary.org/obo/BFO_0000015",  # Process
            "action_description": "Engineer A's decision to offer free preliminary engineering",
            "action_agent": "Engineer A",
            "action_target": "City"
        }
    })
    
    triples.append({
        "subject": f"Case {case_id}",
        "predicate": "http://proethica.org/ontology/engineering-ethics#involvesAction",
        "object_uri": "http://proethica.org/ontology/engineering-ethics#IssuingProcurementDocument",
        "is_literal": False,
        "entity_type": "document",
        "entity_id": case_id,
        "triple_metadata": {
            "bfo_classification": "http://purl.obolibrary.org/obo/BFO_0000015",  # Process
            "action_description": "City's action of soliciting engineering services",
            "action_agent": "City",
            "action_result": "Request for Qualifications"
        }
    })
    
    # 5. Conditions (mapped to BFO:Quality or RealizableEntity) - Using specific condition types
    triples.append({
        "subject": f"Case {case_id}",
        "predicate": "http://proethica.org/ontology/engineering-ethics#involvesCondition",
        "object_uri": "http://proethica.org/ontology/engineering-ethics#RegulatoryNonCompliance",
        "is_literal": False,
        "entity_type": "document",
        "entity_id": case_id,
        "triple_metadata": {
            "bfo_classification": "http://purl.obolibrary.org/obo/BFO_0000019",  # Quality
            "condition_description": "Water system's non-compliant regulatory status",
            "condition_bearer": "Municipal Water System",
            "condition_authority": "State Environmental Agency"
        }
    })
    
    triples.append({
        "subject": f"Case {case_id}",
        "predicate": "http://proethica.org/ontology/engineering-ethics#involvesRequirement",
        "object_uri": "http://proethica.org/ontology/engineering-ethics#FairCompetitiveSelectionRequirement",
        "is_literal": False,
        "entity_type": "document",
        "entity_id": case_id,
        "triple_metadata": {
            "bfo_classification": "http://purl.obolibrary.org/obo/BFO_0000016",  # Disposition
            "condition_description": "Requirement for fair and competitive selection process",
            "authority": "Engineering Profession Ethics"
        }
    })
    
    # 6. Relationships between entities (using specific entity relationship types)
    triples.append({
        "subject": f"Case {case_id}",
        "predicate": "http://proethica.org/ontology/engineering-ethics#involvesEthicalIssue",
        "object_uri": "http://proethica.org/ontology/engineering-ethics#UnfairCompetitiveAdvantage",
        "is_literal": False,
        "entity_type": "document",
        "entity_id": case_id,
        "triple_metadata": {
            "bfo_classification": "http://purl.obolibrary.org/obo/BFO_0000015",  # Process
            "issue_description": "Engineer A's free services creating unfair advantage",
            "related_principle": "Professional Integrity",
            "principle_code": "II.5.B"
        }
    })
    
    triples.append({
        "subject": f"Case {case_id}",
        "predicate": "http://proethica.org/ontology/engineering-ethics#hasEthicalVerdict",
        "object_uri": "http://proethica.org/ontology/engineering-ethics#UnethicalAction",
        "is_literal": False,
        "entity_type": "document",
        "entity_id": case_id,
        "triple_metadata": {
            "bfo_classification": "http://purl.obolibrary.org/obo/BFO_0000031",  # Generically Dependent Continuant
            "verdict_description": "The offer of free Preliminary Engineering was unethical",
            "verdict_authority": "Board of Ethical Review",
            "verdict_rationale": "Offering free services constitutes valuable consideration to secure work"
        }
    })
    
    # Insert all triples into the database
    for triple in triples:
        # Add common fields - don't set ID, let the database auto-generate it
        triple["graph"] = "http://proethica.org/ontology/scenario-entities"
        triple["created_at"] = datetime.now().isoformat()
        triple["updated_at"] = datetime.now().isoformat()
        
        # Convert metadata to JSON string or object
        if isinstance(triple["triple_metadata"], dict):
            triple["triple_metadata"] = json.dumps(triple["triple_metadata"])
        
        # Create SQL placeholders for the keys
        keys = triple.keys()
        placeholders = ', '.join([f"%({key})s" for key in keys])
        columns = ', '.join(keys)
        
        # Insert query
        query = f"INSERT INTO entity_triples ({columns}) VALUES ({placeholders})"
        cur.execute(query, triple)
    
    conn.commit()
    cur.close()
    print(f"Added {len(triples)} intermediate ontology triples for case {case_id}")
    return triples


def main():
    """Main function to demonstrate the dual-layer ontology tagging approach"""
    try:
        # Connect to the database
        print(f"Connecting to database: {DB_PARAMS['dbname']} on {DB_PARAMS['host']}:{DB_PARAMS['port']}")
        conn = psycopg2.connect(**DB_PARAMS)
        
        # Execute both tagging approaches
        mclaren_triples = create_mclaren_triples(conn, CASE_ID)
        scenario_triples = create_scenario_triples(conn, CASE_ID)
        
        # Summary
        print("\n=== Dual-Layer Ontology Tagging Complete ===")
        print(f"Case: {CASE_TITLE} (#{CASE_NUMBER})")
        print(f"McLaren Extensional Triples: {len(mclaren_triples)}")
        print(f"Intermediate Ontology Triples: {len(scenario_triples)}")
        print(f"Total Triples: {len(mclaren_triples) + len(scenario_triples)}")
        print("\nYou can now view the case with its triples at: http://127.0.0.1:3333/cases/{CASE_ID}")
        
        # Close connection
        conn.close()
        print("Database connection closed")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    main()
