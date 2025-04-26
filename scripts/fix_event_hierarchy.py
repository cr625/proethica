"""
Script to fix the event hierarchy in the ontology system.

This script will:
1. Create proper event type base classes
2. Fix events with incorrect parent classes
3. Ensure a clean, consistent hierarchy
"""
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion
from rdflib import Graph, Namespace, URIRef, RDF, RDFS, Literal
import re

def fix_event_hierarchy(ontology_id=1):
    """
    Fix the event hierarchy in the ontology.
    
    Args:
        ontology_id (int): Ontology ID
    
    Returns:
        bool: True if successful, False otherwise
    """
    print(f"Fixing event hierarchy in ontology ID {ontology_id}...")
    
    app = create_app()
    with app.app_context():
        # Get the ontology
        ontology = Ontology.query.get(ontology_id)
        if not ontology:
            print(f"Ontology ID {ontology_id} not found")
            return False
        
        # Parse the ontology content
        g = Graph()
        g.parse(data=ontology.content, format="turtle")
        
        # Define namespaces
        namespaces = {
            "engineering-ethics": Namespace("http://proethica.org/ontology/engineering-ethics#"),
            "intermediate": Namespace("http://proethica.org/ontology/intermediate#"),
            "proethica-intermediate": Namespace("http://proethica.org/ontology/intermediate#"),
            "nspe": Namespace("http://proethica.org/nspe/"),
            "bfo": Namespace("http://purl.obolibrary.org/obo/"),
            "owl": Namespace("http://www.w3.org/2002/07/owl#")
        }
        eng_ethics = namespaces["engineering-ethics"]
        proeth = namespaces["intermediate"]
        
        # Helper function
        def label_or_id(s):
            label = next(g.objects(s, RDFS.label), None)
            return str(label) if label else str(s).split('#')[-1]
        
        # 1. Create/verify base event classes
        print("\n1. Creating or verifying base event classes...")
        
        # Ensure we have EventType
        event_type_uri = proeth.EventType
        event_type_exists = (event_type_uri, None, None) in g
        if not event_type_exists:
            print(f"  - Creating EventType base class")
            g.add((event_type_uri, RDF.type, namespaces["owl"].Class))
            g.add((event_type_uri, RDFS.label, Literal("Event Type")))
            g.add((event_type_uri, RDFS.comment, Literal("Base class for all event types in the ontology")))
            g.add((event_type_uri, RDFS.subClassOf, URIRef("http://purl.obolibrary.org/obo/BFO_0000002")))
        
        # Ensure we have EngineeringEvent
        engineering_event_uri = eng_ethics.EngineeringEvent
        if (engineering_event_uri, None, None) in g:
            print(f"  - Found EngineeringEvent base class")
            # Ensure it has proper parent
            for parent in list(g.objects(engineering_event_uri, RDFS.subClassOf)):
                g.remove((engineering_event_uri, RDFS.subClassOf, parent))
            g.add((engineering_event_uri, RDFS.subClassOf, event_type_uri))
        else:
            print(f"  - Creating EngineeringEvent base class")
            g.add((engineering_event_uri, RDF.type, namespaces["owl"].Class))
            g.add((engineering_event_uri, RDFS.label, Literal("Engineering Event")))
            g.add((engineering_event_uri, RDFS.comment, Literal("Base class for all engineering events")))
            g.add((engineering_event_uri, RDFS.subClassOf, event_type_uri))
        
        # 2. Create specialized event classes
        print("\n2. Creating specialized event types...")
        
        # Define specialized event types
        specialized_events = {
            "MeetingEvent": {
                "label": "Meeting Event",
                "comment": "Events related to meetings and discussions"
            },
            "ReportingEvent": {
                "label": "Reporting Event",
                "comment": "Events related to report delivery or publication"
            },
            "InspectionEvent": {
                "label": "Inspection Event",
                "comment": "Events related to inspections and assessments"
            },
            "DisclosureEvent": {
                "label": "Disclosure Event",
                "comment": "Events related to disclosure of information"
            },
            "SafetyEvent": {
                "label": "Safety Event",
                "comment": "Events related to safety incidents and discoveries"
            },
            "DeliveryEvent": {
                "label": "Delivery Event",
                "comment": "Events related to delivery of documents or reports"
            },
            "DiscoveryEvent": {
                "label": "Discovery Event",
                "comment": "Events related to discoveries or findings"
            }
        }
        
        event_type_classes = {}
        
        for event_name, details in specialized_events.items():
            event_uri = getattr(eng_ethics, event_name)
            event_type_classes[event_name] = event_uri
            
            # Check if class already exists
            if (event_uri, None, None) in g:
                print(f"  - Found {event_name} class")
                # Ensure it has proper parent
                for parent in list(g.objects(event_uri, RDFS.subClassOf)):
                    g.remove((event_uri, RDFS.subClassOf, parent))
                g.add((event_uri, RDFS.subClassOf, engineering_event_uri))
            else:
                print(f"  - Creating {event_name} class")
                g.add((event_uri, RDF.type, namespaces["owl"].Class))
                g.add((event_uri, RDFS.label, Literal(details["label"])))
                g.add((event_uri, RDFS.comment, Literal(details["comment"])))
                g.add((event_uri, RDFS.subClassOf, engineering_event_uri))
        
        # 3. Find all existing events and fix their parent classes
        print("\n3. Finding and fixing existing events...")
        
        # Get all EventType instances
        event_instances = []
        for s in g.subjects(RDF.type, event_type_uri):
            event_instances.append(s)
        
        # Also look for event-related classes based on name pattern
        for s, p, o in g.triples((None, RDF.type, namespaces["owl"].Class)):
            if "Event" in str(s) or "Delivery" in str(s) or "Meeting" in str(s) or "Discovery" in str(s):
                event_instances.append(s)
        
        # Make list unique
        event_instances = list(set(event_instances))
        
        # Fix each event
        for event in event_instances:
            event_label = label_or_id(event)
            print(f"  - Processing event: {event_label}")
            
            # Remove incorrect parents
            current_parents = list(g.objects(event, RDFS.subClassOf))
            invalid_parents = []
            
            for parent in current_parents:
                parent_label = label_or_id(parent)
                # Check for report as parent - this is incorrect
                if "Report" in parent_label and "Event" not in parent_label and not parent.endswith("EventType"):
                    invalid_parents.append(parent)
                elif parent == event:  # Self-reference check
                    invalid_parents.append(parent)
            
            for invalid_parent in invalid_parents:
                g.remove((event, RDFS.subClassOf, invalid_parent))
                print(f"    - Removed invalid parent: {label_or_id(invalid_parent)}")
            
            # Assign to appropriate parent based on name pattern
            parent_assigned = False
            
            if any(keyword in event_label for keyword in ["Meeting", "Conference"]):
                g.add((event, RDFS.subClassOf, event_type_classes["MeetingEvent"]))
                print(f"    - Assigned to MeetingEvent")
                parent_assigned = True
                
            elif any(keyword in event_label for keyword in ["Reporting", "Report Delivery"]):
                g.add((event, RDFS.subClassOf, event_type_classes["ReportingEvent"]))
                print(f"    - Assigned to ReportingEvent")
                parent_assigned = True
                
            elif any(keyword in event_label for keyword in ["Inspection"]):
                g.add((event, RDFS.subClassOf, event_type_classes["InspectionEvent"]))
                print(f"    - Assigned to InspectionEvent")
                parent_assigned = True
                
            elif any(keyword in event_label for keyword in ["Disclosure", "Non-Disclosure"]):
                g.add((event, RDFS.subClassOf, event_type_classes["DisclosureEvent"]))
                print(f"    - Assigned to DisclosureEvent")
                parent_assigned = True
                
            elif any(keyword in event_label for keyword in ["Safety", "Hazard"]):
                g.add((event, RDFS.subClassOf, event_type_classes["SafetyEvent"]))
                print(f"    - Assigned to SafetyEvent")
                parent_assigned = True
                
            elif any(keyword in event_label for keyword in ["Delivery"]):
                g.add((event, RDFS.subClassOf, event_type_classes["DeliveryEvent"]))
                print(f"    - Assigned to DeliveryEvent")
                parent_assigned = True
                
            elif any(keyword in event_label for keyword in ["Discovery", "Finding"]):
                g.add((event, RDFS.subClassOf, event_type_classes["DiscoveryEvent"]))
                print(f"    - Assigned to DiscoveryEvent")
                parent_assigned = True
            
            # If no pattern matched, assign directly to EngineeringEvent
            if not parent_assigned:
                g.add((event, RDFS.subClassOf, engineering_event_uri))
                print(f"    - Assigned to EngineeringEvent (default)")
        
        # 4. Handle special cases
        print("\n4. Handling special cases...")
        
        # Fix Confidential Report Delivery
        confidential_report_delivery_uri = eng_ethics.ConfidentialReportDelivery
        if (confidential_report_delivery_uri, None, None) in g:
            # Remove all parents
            for parent in list(g.objects(confidential_report_delivery_uri, RDFS.subClassOf)):
                g.remove((confidential_report_delivery_uri, RDFS.subClassOf, parent))
            
            # Add proper parent - this should be both DeliveryEvent and DisclosureEvent
            g.add((confidential_report_delivery_uri, RDFS.subClassOf, event_type_classes["DeliveryEvent"]))
            g.add((confidential_report_delivery_uri, RDFS.subClassOf, event_type_classes["DisclosureEvent"]))
            print(f"  - Fixed Confidential Report Delivery parents")
        
        # Fix Safety Reporting Event
        safety_reporting_event_uri = eng_ethics.SafetyReportingEvent
        if (safety_reporting_event_uri, None, None) in g:
            # Remove all parents
            for parent in list(g.objects(safety_reporting_event_uri, RDFS.subClassOf)):
                g.remove((safety_reporting_event_uri, RDFS.subClassOf, parent))
            
            # Add proper parents
            g.add((safety_reporting_event_uri, RDFS.subClassOf, event_type_classes["ReportingEvent"]))
            g.add((safety_reporting_event_uri, RDFS.subClassOf, event_type_classes["SafetyEvent"]))
            print(f"  - Fixed Safety Reporting Event parents")
        
        # Fix Structural Inspection Event
        structural_inspection_event_uri = eng_ethics.StructuralInspectionEvent
        if (structural_inspection_event_uri, None, None) in g:
            # Only keep InspectionEvent as parent if it already has it
            keep_inspection = False
            for parent in list(g.objects(structural_inspection_event_uri, RDFS.subClassOf)):
                if parent == event_type_classes.get("InspectionEvent", None):
                    keep_inspection = True
                else:
                    g.remove((structural_inspection_event_uri, RDFS.subClassOf, parent))
            
            # If we didn't keep the parent, add it
            if not keep_inspection:
                g.add((structural_inspection_event_uri, RDFS.subClassOf, event_type_classes["InspectionEvent"]))
            
            print(f"  - Fixed Structural Inspection Event parents")
        
        # Fix Hazard Discovery Event
        hazard_discovery_event_uri = eng_ethics.HazardDiscoveryEvent
        if (hazard_discovery_event_uri, None, None) in g:
            # Remove all parents
            for parent in list(g.objects(hazard_discovery_event_uri, RDFS.subClassOf)):
                g.remove((hazard_discovery_event_uri, RDFS.subClassOf, parent))
            
            # Add proper parents
            g.add((hazard_discovery_event_uri, RDFS.subClassOf, event_type_classes["DiscoveryEvent"]))
            g.add((hazard_discovery_event_uri, RDFS.subClassOf, event_type_classes["SafetyEvent"]))
            print(f"  - Fixed Hazard Discovery Event parents")
        
        # Save the updated ontology
        try:
            # Create new version
            next_version = OntologyVersion.query.filter_by(
                ontology_id=ontology_id
            ).order_by(
                OntologyVersion.version_number.desc()
            ).first()
            
            next_version_num = 1
            if next_version:
                next_version_num = next_version.version_number + 1
                
            # Serialize updated graph
            new_content = g.serialize(format="turtle")
            
            # Create version entry
            version = OntologyVersion(
                ontology_id=ontology_id,
                version_number=next_version_num,
                content=new_content,
                commit_message="Fixed event hierarchy"
            )
            
            # Update ontology content
            ontology.content = new_content
            
            # Save to database
            from app import db
            db.session.add(version)
            db.session.commit()
            
            print(f"\nSuccessfully updated ontology (version {next_version_num})")
            print("Fixed event hierarchy")
            
            return True
            
        except Exception as e:
            from app import db
            db.session.rollback()
            print(f"Error saving ontology: {e}")
            return False

if __name__ == "__main__":
    # Default ontology ID is 1, but can be passed as command-line argument
    ontology_id = 1
    if len(sys.argv) > 1:
        try:
            ontology_id = int(sys.argv[1])
        except ValueError:
            print(f"Invalid ontology ID: {sys.argv[1]}")
            sys.exit(1)
    
    success = fix_event_hierarchy(ontology_id)
    sys.exit(0 if success else 1)
