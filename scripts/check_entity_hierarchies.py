#!/usr/bin/env python
"""
Script to check entity hierarchies in the database-stored ontologies.
This verifies that our action and event hierarchies are correctly structured.
"""
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.services.ontology_entity_service import OntologyEntityService
import pprint

def check_hierarchies(ontology_id=1):
    """
    Check the hierarchies for actions and events in the specified ontology.
    
    Args:
        ontology_id (int): The ID of the ontology to check.
    """
    print(f"Checking entity hierarchies for ontology ID {ontology_id}...\n")
    
    app = create_app()
    with app.app_context():
        service = OntologyEntityService()
        
        # Get ontology entities from database
        from app.models.ontology import Ontology
        ontology = Ontology.query.get(ontology_id)
        if not ontology:
            print(f"Error: Ontology with ID {ontology_id} not found")
            return

        print(f"Analyzing ontology: {ontology.name} ({ontology.domain_id})")
        print("=" * 80)
        
        # Create a temporary world object with the ontology ID
        class TempWorld:
            def __init__(self, ontology_id):
                self.ontology_id = ontology_id
        
        # Get entities using the world-based method
        temp_world = TempWorld(ontology_id)
        entities = service.get_entities_for_world(temp_world)
        
        # Debug the structure of entities
        print("\nEntities structure:")
        print(f"Keys in entities: {entities.keys()}")
        print(f"Type of entities: {type(entities)}")
        
        # Check if is_mock flag is present
        if 'is_mock' in entities:
            print(f"is_mock: {entities['is_mock']}")
            
        # Check what's in 'entities' key if it exists
        if 'entities' in entities:
            print("\nInner entities structure:")
            inner_entities = entities['entities']
            print(f"Keys in inner entities: {inner_entities.keys() if isinstance(inner_entities, dict) else 'Not a dict'}")
        
        # Check Actions and their hierarchy
        print("\n\033[1;34mACTION HIERARCHY\033[0m")
        print("-" * 80)
        
        # Get actions from the nested structure
        actions = entities.get('entities', {}).get('actions', [])
        
        # Debug information
        print(f"Found {len(actions)} actions in the ontology")
        if actions:
            print("\nSample action details:")
            if len(actions) > 0:
                sample = actions[0]
                for key, value in sample.items():
                    print(f"  {key}: {value}")
            
            # Show all action parent classes
            print("\nAll action parent classes:")
            for action in actions:
                print(f"  {action.get('label', 'Unknown')}: {action.get('parent_class', 'No parent')}")
        
        # Create a mapping of action URI to its details
        action_map = {action['id']: action for action in actions}
        
        # Track parent-child relationships
        child_to_parent = {}
        for action in actions:
            if 'parent_class' in action and action['parent_class']:
                child_to_parent[action['id']] = action['parent_class']
        
        # Print hierarchy
        print("\nAction Class Hierarchy:")
        base_classes = set(['http://proethica.org/ontology/intermediate#ActionType'])
        
        # Build specialized classes set from actual parent classes in the ontology
        specialized_classes = set()
        for action in actions:
            if 'parent_class' in action and action['parent_class']:
                if action['parent_class'] != 'http://proethica.org/ontology/intermediate#ActionType':
                    specialized_classes.add(action['parent_class'])
        
        # Add known specialized classes that might not be used yet
        additional_specialized_classes = set([
            'http://proethica.org/ontology/engineering-ethics#EngineeringAction',
            'http://proethica.org/ontology/engineering-ethics#ReportAction',
            'http://proethica.org/ontology/engineering-ethics#DesignAction', 
            'http://proethica.org/ontology/engineering-ethics#ReviewAction',
            'http://proethica.org/ontology/engineering-ethics#DecisionAction',
            'http://proethica.org/ontology/engineering-ethics#SafetyAction', 
            'http://proethica.org/ontology/engineering-ethics#ConsultationAction'
        ])
        specialized_classes.update(additional_specialized_classes)
        
        print(f"\nDetected specialized action classes: {', '.join(cls.split('#')[-1] for cls in specialized_classes)}")
        
        def print_action_tree(uri, indent=0, is_last=False):
            if uri in action_map:
                action = action_map[uri]
                label = action.get('label', uri.split('#')[-1])
                prefix = "└── " if is_last else "├── "
                print(f"{' ' * indent}{prefix}{label}")
                
                # Find children
                children = [child_uri for child_uri, parent_uri in child_to_parent.items() if parent_uri == uri]
                for i, child in enumerate(children):
                    is_last_child = (i == len(children) - 1)
                    print_action_tree(child, indent + 4, is_last_child)
        
        # Start with base classes
        for base in base_classes:
            base_label = base.split('#')[-1]
            print(f"\n{base_label}")
            
            # First, find specialized categories (second-level classes)
            specialized = specialized_classes
            for i, spec_class in enumerate(sorted(specialized)):
                # Get only the class name from the URI
                class_name = spec_class.split('#')[-1]
                is_last_spec = (i == len(specialized) - 1)
                
                # Print the specialized class
                prefix = "└── " if is_last_spec else "├── "
                print(f"{prefix}{class_name}")
                
                # Find immediate children of this specialized class
                children = [child_uri for child_uri, parent_uri in child_to_parent.items() if parent_uri == spec_class]
                for j, child in enumerate(children):
                    is_last_child = (j == len(children) - 1)
                    child_indent = 4
                    print_action_tree(child, child_indent, is_last_child)
        
        # Check for actions with Resource parents (incorrect)
        resource_parents = [action for action in actions if 
                           'parent_class' in action and 
                           action['parent_class'] and 
                           ('ResourceType' in action['parent_class'] or 'Document' in action['parent_class'])]
        
        if resource_parents:
            print("\n\033[1;31mWARNING: Actions with Resource parents detected!\033[0m")
            for action in resource_parents:
                print(f"  - {action.get('label', 'Unknown')}: Parent={action.get('parent_class', 'Unknown')}")
        else:
            print("\n\033[1;32mSuccess: No actions with Resource parents detected.\033[0m")
        
        # Check Events and their hierarchy
        print("\n\n\033[1;34mEVENT HIERARCHY\033[0m")
        print("-" * 80)
        
        # Get events from the nested structure
        events = entities.get('entities', {}).get('events', [])
        
        # Debug information
        print(f"Found {len(events)} events in the ontology")
        if events:
            print("\nSample event details:")
            if len(events) > 0:
                sample = events[0]
                for key, value in sample.items():
                    print(f"  {key}: {value}")
                    
            # Show all event parent classes
            print("\nAll event parent classes:")
            for event in events:
                print(f"  {event.get('label', 'Unknown')}: {event.get('parent_class', 'No parent')}")
        
        # Create a mapping of event URI to its details
        event_map = {event['id']: event for event in events}
        
        # Track parent-child relationships
        child_to_parent = {}
        for event in events:
            if 'parent_class' in event and event['parent_class']:
                child_to_parent[event['id']] = event['parent_class']
        
        # Print hierarchy
        print("\nEvent Class Hierarchy:")
        base_classes = set(['http://proethica.org/ontology/intermediate#EventType'])
        
        # Build specialized classes set from actual parent classes in the ontology
        specialized_classes = set()
        for event in events:
            if 'parent_class' in event and event['parent_class']:
                if event['parent_class'] != 'http://proethica.org/ontology/intermediate#EventType':
                    specialized_classes.add(event['parent_class'])
        
        # Add known specialized classes that might not be used yet
        additional_specialized_classes = set([
            'http://proethica.org/ontology/engineering-ethics#EngineeringEvent',
            'http://proethica.org/ontology/engineering-ethics#MeetingEvent',
            'http://proethica.org/ontology/engineering-ethics#ReportingEvent',
            'http://proethica.org/ontology/engineering-ethics#DisclosureEvent', 
            'http://proethica.org/ontology/engineering-ethics#SafetyEvent',
            'http://proethica.org/ontology/engineering-ethics#DiscoveryEvent',
            'http://proethica.org/ontology/engineering-ethics#InspectionEvent',
            'http://proethica.org/ontology/engineering-ethics#DeliveryEvent',
            'http://proethica.org/ontology/engineering-ethics#HazardDiscoveryEvent'
        ])
        specialized_classes.update(additional_specialized_classes)
        
        print(f"\nDetected specialized event classes: {', '.join(cls.split('#')[-1] for cls in specialized_classes)}")
        
        def print_event_tree(uri, indent=0, is_last=False):
            if uri in event_map:
                event = event_map[uri]
                label = event.get('label', uri.split('#')[-1])
                prefix = "└── " if is_last else "├── "
                print(f"{' ' * indent}{prefix}{label}")
                
                # Find children
                children = [child_uri for child_uri, parent_uri in child_to_parent.items() if parent_uri == uri]
                for i, child in enumerate(children):
                    is_last_child = (i == len(children) - 1)
                    print_event_tree(child, indent + 4, is_last_child)
        
        # Start with base classes
        for base in base_classes:
            base_label = base.split('#')[-1]
            print(f"\n{base_label}")
            
            # First, find specialized categories (second-level classes)
            specialized = specialized_classes
            for i, spec_class in enumerate(sorted(specialized)):
                # Get only the class name from the URI
                class_name = spec_class.split('#')[-1]
                is_last_spec = (i == len(specialized) - 1)
                
                # Print the specialized class
                prefix = "└── " if is_last_spec else "├── "
                print(f"{prefix}{class_name}")
                
                # Find immediate children of this specialized class
                children = [child_uri for child_uri, parent_uri in child_to_parent.items() if parent_uri == spec_class]
                for j, child in enumerate(children):
                    is_last_child = (j == len(children) - 1)
                    child_indent = 4
                    print_event_tree(child, child_indent, is_last_child)
        
        # Check for events with Resource parents (incorrect)
        resource_parents = [event for event in events if 
                           'parent_class' in event and 
                           event['parent_class'] and 
                           ('ResourceType' in event['parent_class'] or 'Document' in event['parent_class'])]
        
        if resource_parents:
            print("\n\033[1;31mWARNING: Events with Resource parents detected!\033[0m")
            for event in resource_parents:
                print(f"  - {event.get('label', 'Unknown')}: Parent={event.get('parent_class', 'Unknown')}")
        else:
            print("\n\033[1;32mSuccess: No events with Resource parents detected.\033[0m")
        
        # Check Capabilities and their hierarchy
        print("\n\n\033[1;34mCAPABILITY HIERARCHY\033[0m")
        print("-" * 80)
        
        # Get capabilities from the nested structure
        capabilities = entities.get('entities', {}).get('capabilities', [])
        
        # Debug information
        print(f"Found {len(capabilities)} capabilities in the ontology")
        if capabilities:
            print("\nSample capability details:")
            if len(capabilities) > 0:
                sample = capabilities[0]
                for key, value in sample.items():
                    print(f"  {key}: {value}")
                    
            # Show all capability parent classes
            print("\nAll capability parent classes:")
            for capability in capabilities:
                print(f"  {capability.get('label', 'Unknown')}: {capability.get('parent_class', 'No parent')}")
        
        # Create a mapping of capability URI to its details
        capability_map = {capability['id']: capability for capability in capabilities}
        
        # Track parent-child relationships
        child_to_parent = {}
        for capability in capabilities:
            if 'parent_class' in capability and capability['parent_class']:
                child_to_parent[capability['id']] = capability['parent_class']
        
        # Print hierarchy
        print("\nCapability Class Hierarchy:")
        base_classes = set(['http://proethica.org/ontology/intermediate#Capability'])
        
        # Build specialized classes set from actual parent classes in the ontology
        specialized_classes = set()
        for capability in capabilities:
            if 'parent_class' in capability and capability['parent_class']:
                if capability['parent_class'] != 'http://proethica.org/ontology/intermediate#Capability':
                    specialized_classes.add(capability['parent_class'])
        
        # Add known specialized classes that might not be used yet
        additional_specialized_classes = set([
            'http://proethica.org/ontology/engineering-ethics#EngineeringCapability',
            'http://proethica.org/ontology/engineering-ethics#StructuralAnalysisCapability', 
            'http://proethica.org/ontology/engineering-ethics#StructuralDesignCapability',
            'http://proethica.org/ontology/engineering-ethics#ProjectManagementCapability',
            'http://proethica.org/ontology/engineering-ethics#TechnicalReportingCapability',
            'http://proethica.org/ontology/engineering-ethics#RegulatoryComplianceCapability', 
            'http://proethica.org/ontology/engineering-ethics#SafetyAssessmentCapability',
            'http://proethica.org/ontology/engineering-ethics#EngineeringConsultationCapability'
        ])
        specialized_classes.update(additional_specialized_classes)
        
        print(f"\nDetected specialized capability classes: {', '.join(cls.split('#')[-1] for cls in specialized_classes)}")
        
        def print_capability_tree(uri, indent=0, is_last=False):
            if uri in capability_map:
                capability = capability_map[uri]
                label = capability.get('label', uri.split('#')[-1])
                prefix = "└── " if is_last else "├── "
                print(f"{' ' * indent}{prefix}{label}")
                
                # Find children
                children = [child_uri for child_uri, parent_uri in child_to_parent.items() if parent_uri == uri]
                for i, child in enumerate(children):
                    is_last_child = (i == len(children) - 1)
                    print_capability_tree(child, indent + 4, is_last_child)
        
        # Start with base classes
        for base in base_classes:
            base_label = base.split('#')[-1]
            print(f"\n{base_label}")
            
            # First, find specialized categories (second-level classes)
            specialized = specialized_classes
            for i, spec_class in enumerate(sorted(specialized)):
                # Get only the class name from the URI
                class_name = spec_class.split('#')[-1]
                is_last_spec = (i == len(specialized) - 1)
                
                # Print the specialized class
                prefix = "└── " if is_last_spec else "├── "
                print(f"{prefix}{class_name}")
                
                # Find immediate children of this specialized class
                children = [child_uri for child_uri, parent_uri in child_to_parent.items() if parent_uri == spec_class]
                for j, child in enumerate(children):
                    is_last_child = (j == len(children) - 1)
                    child_indent = 4
                    print_capability_tree(child, child_indent, is_last_child)
        
        # Check for capabilities with inappropriate parents (incorrect)
        resource_capability_parents = [capability for capability in capabilities if 
                           'parent_class' in capability and 
                           capability['parent_class'] and 
                           ('ResourceType' in capability['parent_class'] or 'Document' in capability['parent_class'])]
        
        if resource_capability_parents:
            print("\n\033[1;31mWARNING: Capabilities with inappropriate parents detected!\033[0m")
            for capability in resource_capability_parents:
                print(f"  - {capability.get('label', 'Unknown')}: Parent={capability.get('parent_class', 'Unknown')}")
        else:
            print("\n\033[1;32mSuccess: No capabilities with inappropriate parents detected.\033[0m")

        # Check specialized class usage
        specialized_action_count = sum(1 for action in actions if 
                                     'parent_class' in action and 
                                     action['parent_class'] and
                                     action['parent_class'] != 'http://proethica.org/ontology/intermediate#ActionType')
        
        specialized_event_count = sum(1 for event in events if 
                                     'parent_class' in event and 
                                     event['parent_class'] and
                                     event['parent_class'] != 'http://proethica.org/ontology/intermediate#EventType')
        
        specialized_capability_count = sum(1 for capability in capabilities if 
                                     'parent_class' in capability and 
                                     capability['parent_class'] and
                                     capability['parent_class'] != 'http://proethica.org/ontology/intermediate#Capability')
        
        print(f"\n\n\033[1;34mSPECIALIZED CLASS USAGE\033[0m")
        print("-" * 80)
        print(f"Actions using specialized parent classes: {specialized_action_count}/{len(actions)}")
        print(f"Events using specialized parent classes: {specialized_event_count}/{len(events)}")
        print(f"Capabilities using specialized parent classes: {specialized_capability_count}/{len(capabilities)}")
        
        overall_status = "PASS" if not (resource_parents or resource_capability_parents) else "FAIL"
        print(f"\nOverall hierarchy check: \033[1;{'32' if overall_status == 'PASS' else '31'}m{overall_status}\033[0m")

if __name__ == "__main__":
    # Parse command line arguments
    if len(sys.argv) > 1:
        try:
            ontology_id = int(sys.argv[1])
            check_hierarchies(ontology_id)
        except ValueError:
            print(f"Invalid ontology ID: {sys.argv[1]}")
            print("Usage: python check_entity_hierarchies.py [ontology_id]")
            sys.exit(1)
    else:
        # Default to ontology ID 1
        check_hierarchies()
