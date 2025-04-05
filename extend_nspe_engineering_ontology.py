import sys
import os
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD, DC
import datetime

def extend_engineering_ethics_ontology(output_path=None):
    """
    Extend the engineering ethics ontology with new concepts from NSPE cases
    """
    print("Extending engineering ethics ontology with new NSPE case concepts...")
    
    # Load the existing ontology
    ontology_path = os.path.join('mcp', 'ontology', 'engineering-ethics-enhanced.ttl')
    g = Graph()
    g.parse(ontology_path, format='turtle')
    
    # Define namespaces
    ENGETH = Namespace("http://proethica.org/ontology/engineering-ethics#")
    PROETH = Namespace("http://proethica.org/ontology/intermediate#")
    BFO = Namespace("http://purl.obolibrary.org/obo/")
    
    # Bind namespaces
    g.bind("", ENGETH)
    g.bind("proeth", PROETH)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)
    g.bind("rdf", RDF)
    g.bind("xsd", XSD)
    g.bind("dc", DC)
    g.bind("bfo", BFO)
    
    # Update ontology date
    ontology_uri = URIRef("http://proethica.org/ontology/engineering-ethics")
    for dc_date in g.objects(ontology_uri, DC.date):
        g.remove((ontology_uri, DC.date, dc_date))
    today = datetime.date.today().isoformat()
    g.add((ontology_uri, DC.date, Literal(today, datatype=XSD.date)))
    
    # Track added entities to avoid duplicates
    added_entities = set()
    
    # Helper function to add new entity if it doesn't already exist
    def add_entity_if_new(entity_uri, entity_type, label, comment, parent_class=None, **properties):
        entity_name = entity_uri.split('#')[1]
        if entity_name in added_entities:
            print(f"  Entity {entity_name} already added, skipping.")
            return
            
        # Check if entity already exists in the ontology
        if (URIRef(entity_uri), RDF.type, OWL.Class) in g:
            print(f"  Entity {entity_name} already exists in ontology, skipping.")
            return
            
        # Add the new entity
        g.add((URIRef(entity_uri), RDF.type, OWL.Class))
        g.add((URIRef(entity_uri), RDF.type, PROETH.EntityType))
        if entity_type:
            g.add((URIRef(entity_uri), RDF.type, entity_type))
        
        if parent_class:
            g.add((URIRef(entity_uri), RDFS.subClassOf, parent_class))
        
        g.add((URIRef(entity_uri), RDFS.label, Literal(label, lang="en")))
        g.add((URIRef(entity_uri), RDFS.comment, Literal(comment, lang="en")))
        
        # Add any additional properties
        for prop, value in properties.items():
            g.add((URIRef(entity_uri), prop, value))
        
        added_entities.add(entity_name)
        print(f"  Added {entity_name} to ontology")
    
    # 1. Add new Engineering Roles
    print("\nAdding new Engineering Roles...")
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#CityEngineerRole",
        PROETH.Role,
        "City Engineer Role",
        "The role of an engineer employed by a city government to oversee public infrastructure",
        ENGETH.EngineeringRole
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#PeerReviewerRole",
        PROETH.Role,
        "Peer Reviewer Role",
        "The role of an engineer who reviews the work of other engineers for quality and compliance",
        ENGETH.EngineeringRole
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#DesignBuildEngineerRole",
        PROETH.Role,
        "Design-Build Engineer Role",
        "The role of an engineer who works on combined design and construction projects",
        ENGETH.EngineeringRole
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#StateEngineerRole",
        PROETH.Role,
        "State Engineer Role",
        "The role of an engineer employed by a state government agency",
        ENGETH.EngineeringRole
    )
    
    # 2. Add new Engineering Conditions
    print("\nAdding new Engineering Conditions...")
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#ClimateChangeCondition",
        PROETH.ConditionType,
        "Climate Change Condition",
        "A condition related to climate change that affects engineering practice and decisions",
        ENGETH.EngineeringCondition
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#WaterQualityCondition",
        PROETH.ConditionType,
        "Water Quality Condition",
        "A condition related to drinking water quality that requires engineering assessment or intervention",
        ENGETH.EngineeringCondition
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#StormwaterRunoffCondition",
        PROETH.ConditionType,
        "Stormwater Runoff Condition",
        "A condition related to excessive stormwater runoff that affects engineering projects or public safety",
        ENGETH.EngineeringCondition
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#ImpairedPracticeCondition",
        PROETH.ConditionType,
        "Impaired Practice Condition",
        "A condition where an engineer's practice is impaired due to health or other factors",
        ENGETH.EngineeringCondition
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#CompetenceDeficiencyCondition",
        PROETH.ConditionType,
        "Competence Deficiency Condition",
        "A condition where an engineer lacks the necessary competence for a specific task",
        ENGETH.EngineeringCondition
    )
    
    # 3. Add new Engineering Dilemmas
    print("\nAdding new Engineering Dilemmas...")
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#ConflictOfInterestDilemma",
        PROETH.ConditionType,
        "Conflict of Interest Dilemma",
        "A dilemma where an engineer must navigate conflicting interests in professional practice",
        ENGETH.EngineeringEthicalDilemma
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#PublicSafetyVsResourceConstraintsDilemma",
        PROETH.ConditionType,
        "Public Safety vs Resource Constraints Dilemma",
        "A dilemma where ensuring public safety conflicts with resource or budget constraints",
        ENGETH.EngineeringEthicalDilemma
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#ProfessionalResponsibilityDilemma",
        PROETH.ConditionType,
        "Professional Responsibility Dilemma",
        "A dilemma where an engineer must determine the extent of their professional responsibility",
        ENGETH.EngineeringEthicalDilemma
    )
    
    # 4. Add new Engineering Resources
    print("\nAdding new Engineering Resources...")
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#AsBuiltDrawings",
        PROETH.ResourceType,
        "As-Built Drawings",
        "Drawings that show how a structure was actually built, which may differ from the original design drawings",
        ENGETH.EngineeringDocument
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#PlanReview",
        PROETH.ResourceType,
        "Plan Review",
        "A formal review of engineering plans for compliance and safety",
        ENGETH.EngineeringDocument
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#BuildingPermit",
        PROETH.ResourceType,
        "Building Permit",
        "An official authorization to proceed with construction or renovation",
        ENGETH.EngineeringDocument
    )
    
    # 5. Add new Engineering Ethical Principles
    print("\nAdding new Engineering Ethical Principles...")
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#DisclosurePrinciple",
        PROETH.ConditionType,
        "Disclosure Principle",
        "The principle that engineers should disclose relevant information to affected parties",
        ENGETH.EngineeringEthicalPrinciple
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#ObjectivityPrinciple",
        PROETH.ConditionType,
        "Objectivity Principle",
        "The principle that engineers should maintain objectivity in their professional judgments",
        ENGETH.EngineeringEthicalPrinciple
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#IndependencePrinciple",
        PROETH.ConditionType,
        "Independence Principle",
        "The principle that engineers should maintain independence in their professional judgments",
        ENGETH.EngineeringEthicalPrinciple
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#GoodSamaritanPrinciple",
        PROETH.ConditionType,
        "Good Samaritan Principle",
        "The principle that engineers should provide voluntary services during emergencies",
        ENGETH.EngineeringEthicalPrinciple
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#ProfessionalResponsibilityPrinciple",
        PROETH.ConditionType,
        "Professional Responsibility Principle",
        "The principle that engineers have a responsibility to take action when public safety is at risk",
        ENGETH.EngineeringEthicalPrinciple
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#DesignResponsibilityPrinciple",
        PROETH.ConditionType,
        "Design Responsibility Principle",
        "The principle that engineers are responsible for the safety of their designs",
        ENGETH.EngineeringEthicalPrinciple
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#ContinuingEducationPrinciple",
        PROETH.ConditionType,
        "Continuing Education Principle",
        "The principle that engineers should maintain and improve their technical competence",
        ENGETH.EngineeringEthicalPrinciple
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#PeerReviewPrinciple",
        PROETH.ConditionType,
        "Peer Review Principle",
        "The principle that engineers should engage in honest and objective peer reviews",
        ENGETH.EngineeringEthicalPrinciple
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#QualificationsPrinciple",
        PROETH.ConditionType,
        "Qualifications Principle",
        "The principle that engineers should not misrepresent their qualifications",
        ENGETH.EngineeringEthicalPrinciple
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#FairCompensationPrinciple",
        PROETH.ConditionType,
        "Fair Compensation Principle",
        "The principle that engineers should receive fair compensation for their services",
        ENGETH.EngineeringEthicalPrinciple
    )
    
    add_entity_if_new(
        "http://proethica.org/ontology/engineering-ethics#GiftsPrinciple",
        PROETH.ConditionType,
        "Gifts Principle",
        "The principle that engineers should avoid accepting gifts that may appear to influence their judgment",
        ENGETH.EngineeringEthicalPrinciple
    )
    
    # Save the extended ontology
    if output_path is None:
        output_path = os.path.join('mcp', 'ontology', 'engineering-ethics-nspe-extended.ttl')
    
    g.serialize(destination=output_path, format='turtle')
    print(f"\nExtended ontology saved to {output_path}")
    print(f"Added {len(added_entities)} new entities to the ontology")
    
    return output_path

if __name__ == "__main__":
    output_path = None
    if len(sys.argv) > 1:
        output_path = sys.argv[1]
    
    extend_engineering_ethics_ontology(output_path)
