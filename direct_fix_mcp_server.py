#!/usr/bin/env python3
"""
Script to directly fix the MCP server entity extraction logic by patching
the http_ontology_mcp_server.py file.
"""
import os
import sys
import shutil

def fix_mcp_server():
    """
    Directly edit the http_ontology_mcp_server.py file to fix the entity extraction method.
    """
    mcp_server_path = os.path.join(os.getcwd(), "mcp", "http_ontology_mcp_server.py")
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
    
    # Look for the _extract_entities method
    extract_entities_def = "    def _extract_entities(self, graph, entity_type):"
    if extract_entities_def not in content:
        print(f"Error: Could not find _extract_entities method in {mcp_server_path}")
        return False
    
    # Find the start position of the method
    start_pos = content.find(extract_entities_def)
    if start_pos == -1:
        print(f"Error: Could not find _extract_entities method in {mcp_server_path}")
        return False
    
    # Find the end of the method (next method or end of class)
    next_def = content.find("\n    def ", start_pos + len(extract_entities_def))
    if next_def == -1:
        # Look for end of class
        next_def = content.find("\n\n", start_pos)
        if next_def == -1:
            print("Error: Could not find the end of _extract_entities method")
            return False
    
    # Replace the method with our fixed version
    # First extract the current method for debugging
    current_method = content[start_pos:next_def]
    print(f"\nReplacing current method of {len(current_method)} characters")
    
    # Create the fixed method
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

        out = {}
        if entity_type in ("all", "roles"):
            # Look for both namespace.Role and proeth:Role
            role_subjects = set()
            
            # Look for instances linked via rdf:type to Role
            role_subjects.update(graph.subjects(RDF.type, namespace.Role))
            role_subjects.update(graph.subjects(RDF.type, proeth_namespace.Role))
            
            # ADDITIONAL: Look for instances that have both EntityType and Role types
            entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
            for s in entity_type_subjects:
                if (s, RDF.type, proeth_namespace.Role) in graph:
                    role_subjects.add(s)
            
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
            
            # ADDITIONAL: Look for instances that have both EntityType and ConditionType types
            entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
            for s in entity_type_subjects:
                if (s, RDF.type, proeth_namespace.ConditionType) in graph:
                    condition_subjects.add(s)
            
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
            
            # ADDITIONAL: Look for instances that have both EntityType and ResourceType types
            entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
            for s in entity_type_subjects:
                if (s, RDF.type, proeth_namespace.ResourceType) in graph:
                    resource_subjects.add(s)
            
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
            
            # ADDITIONAL: Look for instances that have both EntityType and EventType types
            entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
            for s in entity_type_subjects:
                if (s, RDF.type, proeth_namespace.EventType) in graph:
                    event_subjects.add(s)
            
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
            
            # ADDITIONAL: Look for instances that have both EntityType and ActionType types
            entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
            for s in entity_type_subjects:
                if (s, RDF.type, proeth_namespace.ActionType) in graph:
                    action_subjects.add(s)
            
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
            
            # ADDITIONAL: Look for instances that have both EntityType and Capability types
            entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
            for s in entity_type_subjects:
                if (s, RDF.type, proeth_namespace.Capability) in graph:
                    capability_subjects.add(s)
            
            # Also get capabilities that are associated with roles
            for role in graph.subjects(RDF.type, namespace.Role):
                capability_subjects.update(graph.objects(role, proeth_namespace.hasCapability))
            for role in graph.subjects(RDF.type, proeth_namespace.Role):
                capability_subjects.update(graph.objects(role, proeth_namespace.hasCapability))
                
            out["capabilities"] = [
                {
                    "id": str(s), 
                    "label": label_or_id(s),
                    "description": get_description(s)
                }
                for s in capability_subjects
            ]
            
        return out"""
    
    # Update the file with the fixed method
    updated_content = content[:start_pos] + fixed_method + content[next_def:]
    with open(mcp_server_path, 'w') as f:
        f.write(updated_content)
    
    print(f"Successfully updated {mcp_server_path}")
    return True

if __name__ == "__main__":
    if fix_mcp_server():
        print("\nSuccess! The MCP server entity extraction method has been fixed.")
        print("You should now restart the server to apply the changes: ./restart_server.sh")
    else:
        print("\nFailed to fix the MCP server entity extraction method.")
        print("Please check the error messages above for details.")
