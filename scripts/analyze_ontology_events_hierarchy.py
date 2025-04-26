"""
Script to analyze and display the hierarchy of events in the ontology to identify
issues with parent class assignments.
"""
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology import Ontology
from rdflib import Graph, Namespace, RDF, RDFS

def analyze_event_hierarchy(ontology_id=1):
    """
    Analyze the event hierarchy in the given ontology to identify any issues.
    """
    print(f"Analyzing event hierarchy in ontology ID {ontology_id}...")
    
    app = create_app()
    with app.app_context():
        # Get the ontology
        ontology = Ontology.query.get(ontology_id)
        if not ontology:
            print(f"Ontology ID {ontology_id} not found.")
            return
        
        # Parse the ontology
        g = Graph()
        g.parse(data=ontology.content, format="turtle")
        
        # Define namespaces
        namespaces = {
            "engineering-ethics": Namespace("http://proethica.org/ontology/engineering-ethics#"),
            "intermediate": Namespace("http://proethica.org/ontology/intermediate#"),
            "proethica-intermediate": Namespace("http://proethica.org/ontology/intermediate#"),
            "nspe": Namespace("http://proethica.org/nspe/"),
            "bfo": Namespace("http://purl.obolibrary.org/obo/")
        }
        
        # Helper function
        def label_or_id(s):
            return str(next(g.objects(s, RDFS.label), s))
        
        # Find all EventType instances
        print("\n1. Finding all event instances...")
        
        event_subjects = set()
        for ns_name, ns in namespaces.items():
            event_class = ns.EventType
            for s in g.subjects(RDF.type, event_class):
                event_subjects.add(s)
                print(f"  - Found event: {label_or_id(s)}")
        
        # Also look for instances that might be events but not explicitly typed
        print("\n2. Looking for additional event-related classes...")
        keyword_events = set()
        keywords = ["Event", "Meeting", "Conference", "Incident", "Occurrence", "Delivery", "Notification"]
        
        # Find subjects that contain these keywords in their URI or label
        for s, p, o in g.triples((None, RDF.type, None)):
            if any(keyword in str(s) for keyword in keywords):
                keyword_events.add(s)
                print(f"  - Found potential event by keyword: {s} (type: {o})")
        
        for s, p, o in g.triples((None, RDFS.label, None)):
            if any(keyword in str(o) for keyword in keywords):
                keyword_events.add(s)
                print(f"  - Found potential event by label: {s} (label: {o})")
        
        # Merge the sets
        all_events = event_subjects.union(keyword_events)
        print(f"\nTotal event-related entities found: {len(all_events)}")
        
        # Analyze subClassOf relationships
        print("\n3. Analyzing subClassOf relationships for events...")
        
        event_hierarchy = {}
        orphaned_events = []
        
        for event in all_events:
            parent_classes = list(g.objects(event, RDFS.subClassOf))
            
            if not parent_classes:
                orphaned_events.append(event)
                event_hierarchy[event] = []
                print(f"  ! Event has no parent: {label_or_id(event)}")
                continue
            
            event_hierarchy[event] = parent_classes
            
            # Display parents
            parents_str = ", ".join([label_or_id(p) for p in parent_classes])
            print(f"  - {label_or_id(event)} → {parents_str}")
        
        # Check for event self-references
        print("\n4. Checking for events that reference themselves as parents...")
        
        self_referencing_events = []
        for event, parents in event_hierarchy.items():
            if event in parents:
                self_referencing_events.append(event)
                print(f"  ! Self-reference detected: {label_or_id(event)}")
        
        # Group events by common patterns
        print("\n5. Grouping events by parent type...")
        
        # Group by parent class
        grouped_by_parent = {}
        
        for event, parents in event_hierarchy.items():
            event_label = label_or_id(event)
            
            for parent in parents:
                parent_label = label_or_id(parent)
                if parent_label not in grouped_by_parent:
                    grouped_by_parent[parent_label] = []
                grouped_by_parent[parent_label].append(event)
        
        # Print groups
        for parent_name, events in grouped_by_parent.items():
            print(f"\nEvents with parent '{parent_name}':")
            for event in events:
                print(f"  - {label_or_id(event)}")
        
        # Check for event base classes
        print("\n6. Looking for event base classes...")
        
        base_classes = {
            "EventType": None,
            "EngineeringEvent": None,
            "MeetingEvent": None,
            "DisclosureEvent": None,
            "SafetyEvent": None,
            "ReportingEvent": None
        }
        
        for base_class in base_classes.keys():
            for ns_name, ns in namespaces.items():
                try:
                    class_uri = getattr(ns, base_class)
                    if (class_uri, None, None) in g:
                        base_classes[base_class] = class_uri
                        print(f"  - Found base class: {base_class} as {class_uri}")
                        # Check its type
                        types = list(g.objects(class_uri, RDF.type))
                        print(f"    Types: {[str(t) for t in types]}")
                        # Check its parents
                        parents = list(g.objects(class_uri, RDFS.subClassOf))
                        print(f"    Parents: {[label_or_id(p) for p in parents]}")
                except:
                    pass
        
        # Analyze event categorization
        print("\n7. Categorizing events by purpose:")
        
        # Define common event categories
        event_categories = {
            "meeting": [],
            "reporting": [],
            "safety": [],
            "disclosure": [],
            "communication": [],
            "other": []
        }
        
        for event in all_events:
            label = label_or_id(event)
            added = False
            
            if any(keyword in label for keyword in ["Meeting", "Conference", "Discussion"]):
                event_categories["meeting"].append(event)
                added = True
            
            if any(keyword in label for keyword in ["Report", "Reporting"]):
                event_categories["reporting"].append(event)
                added = True
            
            if any(keyword in label for keyword in ["Safety", "Hazard", "Risk", "Incident"]):
                event_categories["safety"].append(event)
                added = True
            
            if any(keyword in label for keyword in ["Disclosure", "Reveal", "Publication"]):
                event_categories["disclosure"].append(event)
                added = True
            
            if any(keyword in label for keyword in ["Notification", "Communication", "Delivery"]):
                event_categories["communication"].append(event)
                added = True
            
            if not added:
                event_categories["other"].append(event)
        
        # Print categorized events
        for category, events in event_categories.items():
            if not events:
                continue
                
            print(f"\n{category.capitalize()} Events:")
            for event in events:
                parents = event_hierarchy.get(event, [])
                parent_str = ", ".join([label_or_id(p) for p in parents]) if parents else "NO PARENT"
                print(f"  - {label_or_id(event)} → {parent_str}")
        
        # Check for common patterns in parent assignment
        print("\n8. Analyzing event parent assignment patterns:")
        
        parent_patterns = {}
        for event, parents in event_hierarchy.items():
            event_label = label_or_id(event)
            
            for parent in parents:
                parent_label = label_or_id(parent)
                if parent_label not in parent_patterns:
                    parent_patterns[parent_label] = {"count": 0, "example": None}
                
                parent_patterns[parent_label]["count"] += 1
                
                if not parent_patterns[parent_label]["example"]:
                    parent_patterns[parent_label]["example"] = event_label
        
        # Print parent patterns
        for parent_label, data in sorted(parent_patterns.items(), key=lambda x: x[1]["count"], reverse=True):
            print(f"  - {parent_label}: {data['count']} events (e.g., {data['example']})")
        
        # Check for inconsistencies in parent assignments
        print("\n9. Checking for event parent assignment inconsistencies:")
        
        # Group by event name pattern and check parent consistency
        name_patterns = {}
        for event in all_events:
            label = label_or_id(event)
            name_part = label.split(' ')[0] if ' ' in label else label
            
            if name_part not in name_patterns:
                name_patterns[name_part] = {"events": [], "parents": set()}
            
            name_patterns[name_part]["events"].append(event)
            for parent in event_hierarchy.get(event, []):
                name_patterns[name_part]["parents"].add(label_or_id(parent))
        
        # Check for inconsistent parent assignments
        for name_part, data in name_patterns.items():
            if len(data["events"]) > 1 and len(data["parents"]) > 1:
                print(f"  ! Inconsistent parents for events starting with '{name_part}':")
                for event in data["events"]:
                    parents = event_hierarchy.get(event, [])
                    parent_str = ", ".join([label_or_id(p) for p in parents]) if parents else "NO PARENT"
                    print(f"    - {label_or_id(event)} → {parent_str}")
        
        # Analyze relationship with ActionType
        print("\n10. Analyzing relationship between Events and Actions:")
        
        # Look for events that should be related to specific actions
        related_actions = {}
        for event in all_events:
            event_label = label_or_id(event)
            
            # Look for common patterns that suggest action-event relationships
            if "Report" in event_label:
                related_actions[event_label] = "Reporting Action"
            elif "Meeting" in event_label:
                related_actions[event_label] = "Meeting Action"
            elif "Disclosure" in event_label:
                related_actions[event_label] = "Disclosure Action"
            
        # Print potential related actions
        if related_actions:
            print("\nEvents that should be related to specific actions:")
            for event_label, action_type in related_actions.items():
                print(f"  - {event_label} → {action_type}")
        
        # Propose improvements
        print("\n11. Suggested improvements for event hierarchy:")
        
        # Check if we have a proper hierarchy
        if not base_classes["EngineeringEvent"]:
            print("  - Create EngineeringEvent as a base class for engineering events")
        
        # Check for missing event category classes
        for category in ["MeetingEvent", "ReportingEvent", "SafetyEvent"]:
            if not base_classes[category]:
                print(f"  - Create {category} as a specialized event category")
        
        # Check for events with inappropriate parents
        engineering_condition_parent = None
        
        for parent_label, data in parent_patterns.items():
            if "Condition" in parent_label and not "EventType" in parent_label:
                engineering_condition_parent = parent_label
                
        # Print summary of problematic assignments
        if engineering_condition_parent:
            print(f"  - Reconsider events with '{engineering_condition_parent}' parent:")
            for event in all_events:
                parents = event_hierarchy.get(event, [])
                for parent in parents:
                    if engineering_condition_parent in label_or_id(parent):
                        print(f"    * {label_or_id(event)}")
        
        # Summary
        print("\n=== SUMMARY ===")
        print(f"Total event-related entities found: {len(all_events)}")
        print(f"Events without parents: {len(orphaned_events)}")
        print(f"Self-referencing events: {len(self_referencing_events)}")
        print(f"Different parent patterns: {len(parent_patterns)}")
        
        if engineering_condition_parent:
            print("\nRECOMMENDATION:")
            print("  Consider reorganizing event hierarchy to use proper event types as parents")
            print("  instead of condition-based parents")
        
        # Return the data for further use
        return {
            "all_events": list(all_events),
            "event_hierarchy": event_hierarchy,
            "base_classes": base_classes,
            "event_categories": event_categories
        }

if __name__ == '__main__':
    # Default ontology ID is 1, but can be passed as command-line argument
    ontology_id = 1
    if len(sys.argv) > 1:
        try:
            ontology_id = int(sys.argv[1])
        except ValueError:
            print(f"Invalid ontology ID: {sys.argv[1]}")
            sys.exit(1)
    
    analyze_event_hierarchy(ontology_id)
