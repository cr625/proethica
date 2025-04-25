#!/usr/bin/env python3
"""
Script to fix the MCP server entity extraction logic.
The issue is that while the ontology content is valid and contains entity instances,
they are not being properly extracted by the MCP server.
"""
import os
import sys
import tempfile
import shutil

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from mcp
from mcp.http_ontology_mcp_server import OntologyMCPServer

def fix_extract_entities_method():
    """
    Fix the _extract_entities method in the MCP server by creating a patched version
    and updating the file.
    """
    mcp_server_path = os.path.join(os.path.dirname(__file__), "mcp", "http_ontology_mcp_server.py")
    if not os.path.exists(mcp_server_path):
        print(f"Error: Could not find MCP server file at {mcp_server_path}")
        return False
    
    # Create a backup
    backup_path = mcp_server_path + ".bak"
    shutil.copy2(mcp_server_path, backup_path)
    print(f"Created backup of MCP server file at {backup_path}")
    
    # Read the file
    with open(mcp_server_path, 'r') as f:
        content = f.read()
    
    # Find the _extract_entities method
    start_marker = "    def _extract_entities(self, graph, entity_type):"
    end_marker = "        return out"
    
    start_pos = content.find(start_marker)
    if start_pos == -1:
        print("Error: Could not find _extract_entities method in the MCP server file.")
        return False
    
    # Find the end of the method
    end_pos = content.find(end_marker, start_pos)
    if end_pos == -1:
        print("Error: Could not find the end of _extract_entities method.")
        return False
    
    # Include the end marker in the extraction
    end_pos = end_pos + len(end_marker)
    
    # Extract the current method implementation
    original_method = content[start_pos:end_pos]
    
    # Create the fixed version of the method
    fixed_method = """    def _extract_entities(self, graph, entity_type):
        # Detect primary namespace
        namespace = self._detect_namespace(graph)
        
        # Always include the intermediate namespace for entity types
        proeth_namespace = self.namespaces["intermediate"]
        
        def label_or_id(s):
            return str(next(graph.objects(s, RDFS.label), s))
        
        def get_description(s):
            return str(next(graph.objects(s, RDFS.comment), ""))
        
        def safe_get_property(s, prop, default=""):
            try:
                return str(next(graph.objects(s, prop), default))
            except:
                return default
        
        # Debug function to print found subjects
        def debug_subjects(subjects, type_name):
            if subjects:
                print(f"Found {len(subjects)} {type_name} entities")
                for s in list(subjects)[:3]:
                    print(f"  {label_or_id(s)} ({s})")
            else:
                print(f"No {type_name} entities found")

        out = {}
        if entity_type in ("all", "roles"):
            # Look for both namespace.Role and proeth:Role
            role_subjects = set()
            
            # Look for instances linked via rdf:type to Role
            role_subjects.update(graph.subjects(RDF.type, namespace.Role))
            role_subjects.update(graph.subjects(RDF.type, proeth_namespace.Role))
            
            # ADDITIONAL: Look for instances that have both types: EntityType and Role
            entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
            for s in entity_type_subjects:
                if (s, RDF.type, proeth_namespace.Role) in graph:
                    role_subjects.add(s)
            
            # Debug
            debug_subjects(role_subjects, "Role")
            
            out["roles"] = [
                {
                    "id": str(s), 
                    "label": label_or_id(s),
                    "description": get_description(s),
                    "tier": safe_get_property(s, namespace.hasTier),
                    "capabilities": [
                        {
                            "id": str(o),
                            "label": label_or_id(o),
                            "description": get_description(o)
                        } 
                        for o in graph.objects(s, proeth_namespace.hasCapability)
                    ]
                }
                for s in role_subjects
            ]
        
        if entity_type in ("all", "conditions"):
            # Look for both namespace.ConditionType and proeth:ConditionType
            condition_subjects = set()
            condition_subjects.update(graph.subjects(RDF.type, namespace.ConditionType))
            condition_subjects.update(graph.subjects(RDF.type, proeth_namespace.ConditionType))
            
            # ADDITIONAL: Look for instances that have both types: EntityType and ConditionType
            entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
            for s in entity_type_subjects:
                if (s, RDF.type, proeth_namespace.ConditionType) in graph:
                    condition_subjects.add(s)
            
            # Debug
            debug_subjects(condition_subjects, "ConditionType")
            
            out["conditions"] = [
                {
                    "id": str(s), 
                    "label": label_or_id(s),
                    "description": get_description(s)
                }
                for s in condition_subjects
            ]
        
        if entity_type in ("all", "resources"):
            # Look for both namespace.ResourceType and proeth:ResourceType
            resource_subjects = set()
            resource_subjects.update(graph.subjects(RDF.type, namespace.ResourceType))
            resource_subjects.update(graph.subjects(RDF.type, proeth_namespace.ResourceType))
            
            # ADDITIONAL: Look for instances that have both types: EntityType and ResourceType
            entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
            for s in entity_type_subjects:
                if (s, RDF.type, proeth_namespace.ResourceType) in graph:
                    resource_subjects.add(s)
            
            # Debug
            debug_subjects(resource_subjects, "ResourceType")
            
            out["resources"] = [
                {
                    "id": str(s), 
                    "label": label_or_id(s),
                    "description": get_description(s)
                }
                for s in resource_subjects
            ]
        
        if entity_type in ("all", "events"):
            # Look for both namespace.EventType and proeth:EventType
            event_subjects = set()
            event_subjects.update(graph.subjects(RDF.type, namespace.EventType))
            event_subjects.update(graph.subjects(RDF.type, proeth_namespace.EventType))
            
            # ADDITIONAL: Look for instances that have both types: EntityType and EventType
            entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
            for s in entity_type_subjects:
                if (s, RDF.type, proeth_namespace.EventType) in graph:
                    event_subjects.add(s)
            
            # Debug
            debug_subjects(event_subjects, "EventType")
            
            out["events"] = [
                {
                    "id": str(s), 
                    "label": label_or_id(s),
                    "description": get_description(s)
                }
                for s in event_subjects
            ]
        
        if entity_type in ("all", "actions"):
            # Look for both namespace.ActionType and proeth:ActionType
            action_subjects = set()
            action_subjects.update(graph.subjects(RDF.type, namespace.ActionType))
            action_subjects.update(graph.subjects(RDF.type, proeth_namespace.ActionType))
            
            # ADDITIONAL: Look for instances that have both types: EntityType and ActionType
            entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
            for s in entity_type_subjects:
                if (s, RDF.type, proeth_namespace.ActionType) in graph:
                    action_subjects.add(s)
            
            # Debug
            debug_subjects(action_subjects, "ActionType")
            
            out["actions"] = [
                {
                    "id": str(s), 
                    "label": label_or_id(s),
                    "description": get_description(s)
                }
                for s in action_subjects
            ]
            
        if entity_type in ("all", "capabilities"):
            # Look for capability types
            capability_subjects = set()
            capability_subjects.update(graph.subjects(RDF.type, namespace.Capability))
            capability_subjects.update(graph.subjects(RDF.type, proeth_namespace.Capability))
            
            # ADDITIONAL: Look for instances that have both types: EntityType and Capability
            entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
            for s in entity_type_subjects:
                if (s, RDF.type, proeth_namespace.Capability) in graph:
                    capability_subjects.add(s)
            
            # Also get capabilities that are associated with roles
            for role in graph.subjects(RDF.type, namespace.Role):
                capability_subjects.update(graph.objects(role, proeth_namespace.hasCapability))
            for role in graph.subjects(RDF.type, proeth_namespace.Role):
                capability_subjects.update(graph.objects(role, proeth_namespace.hasCapability))
            
            # Debug
            debug_subjects(capability_subjects, "Capability")
            
            out["capabilities"] = [
                {
                    "id": str(s), 
                    "label": label_or_id(s),
                    "description": get_description(s)
                }
                for s in capability_subjects
            ]
        
        return out"""
    
    # Replace the method in the content
    patched_content = content[:start_pos] + fixed_method + content[end_pos:]
    
    # Write the updated content to the file
    with open(mcp_server_path, 'w') as f:
        f.write(patched_content)
    
    print(f"Updated MCP server file with fixed _extract_entities method.")
    return True

if __name__ == "__main__":
    if fix_extract_entities_method():
        print("\nSuccess! The MCP server entity extraction method has been fixed.")
        print("You should now restart the server to apply the changes: ./restart_server.sh")
    else:
        print("\nFailed to fix the MCP server entity extraction method.")
        print("You may need to manually edit the file.")
