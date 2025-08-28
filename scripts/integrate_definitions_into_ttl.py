#!/usr/bin/env python3
"""
Integrate Entity Definitions into TTL Content

This script takes definitions stored in the database and integrates them 
directly into the TTL content of ontology versions, making them accessible
to external systems that read the ontology files.
"""

import os
import sys
import json
import psycopg2
from datetime import datetime
import rdflib
from rdflib.namespace import RDF, RDFS, OWL, SKOS, DCTERMS

# Set environment variables
os.environ.setdefault('ONTSERVE_DB_URL', 'postgresql://ontserve_user:ontserve_development_password@localhost:5432/ontserve')

def integrate_definitions_into_ttl():
    """Integrate entity definitions from database into TTL content."""
    
    print("🔧 Integrating Entity Definitions into TTL Content")
    print("=" * 60)
    
    try:
        conn = psycopg2.connect(os.environ['ONTSERVE_DB_URL'])
        cur = conn.cursor()
        
        # Get all ontologies that have entities with definitions
        cur.execute("""
            SELECT DISTINCT o.id, o.name, o.base_uri, v.id as version_id, v.content
            FROM ontologies o
            JOIN ontology_versions v ON o.id = v.ontology_id AND v.is_current = true
            JOIN ontology_entities e ON o.id = e.ontology_id
            WHERE e.comment IS NOT NULL AND e.comment != ''
            ORDER BY o.name
        """)
        
        ontologies_to_process = cur.fetchall()
        print(f"Found {len(ontologies_to_process)} ontologies with definitions to integrate")
        
        total_updated = 0
        
        for ont_id, ont_name, base_uri, version_id, current_content in ontologies_to_process:
            print(f"\n🔄 Processing {ont_name}...")
            
            # Get all entities with definitions for this ontology
            cur.execute("""
                SELECT uri, label, comment, properties
                FROM ontology_entities
                WHERE ontology_id = %s 
                AND comment IS NOT NULL 
                AND comment != ''
                ORDER BY uri
            """, (ont_id,))
            
            entities_with_definitions = cur.fetchall()
            print(f"   Found {len(entities_with_definitions)} entities with definitions")
            
            if not entities_with_definitions:
                continue
            
            # Parse existing TTL content
            graph = rdflib.Graph()
            if current_content and current_content.strip():
                try:
                    graph.parse(data=current_content, format='turtle')
                    print(f"   Parsed existing TTL: {len(graph)} triples")
                except Exception as e:
                    print(f"   ⚠️  Could not parse existing TTL: {e}")
                    # Create new graph with basic structure
                    graph = create_basic_ontology_structure(base_uri, ont_name)
            else:
                # Create new graph with basic structure
                graph = create_basic_ontology_structure(base_uri, ont_name)
            
            # Add definitions to the graph
            definitions_added = 0
            for entity_uri, label, comment, properties_json in entities_with_definitions:
                entity_ref = rdflib.URIRef(entity_uri)
                
                # Add rdfs:comment (primary definition)
                graph.set((entity_ref, RDFS.comment, rdflib.Literal(comment)))
                
                # Add skos:definition (semantic web best practice)
                graph.add((entity_ref, SKOS.definition, rdflib.Literal(comment)))
                
                # Add label if not present
                if label and not list(graph.objects(entity_ref, RDFS.label)):
                    graph.add((entity_ref, RDFS.label, rdflib.Literal(label)))
                
                # Parse and add metadata from properties JSON
                if properties_json:
                    try:
                        props = json.loads(properties_json) if isinstance(properties_json, str) else properties_json
                        
                        # Add confidence as custom property
                        if props.get('confidence'):
                            confidence_prop = rdflib.URIRef(f"{base_uri}#definitionConfidence")
                            graph.add((entity_ref, confidence_prop, rdflib.Literal(props['confidence'])))
                        
                        # Add definition type
                        if props.get('definition_type'):
                            def_type_prop = rdflib.URIRef(f"{base_uri}#definitionType") 
                            graph.add((entity_ref, def_type_prop, rdflib.Literal(props['definition_type'])))
                        
                        # Add dc:source if present
                        if props.get('dc:source'):
                            graph.add((entity_ref, DCTERMS.source, rdflib.URIRef(props['dc:source'])))
                    
                    except Exception as e:
                        print(f"   ⚠️  Error parsing properties for {entity_uri}: {e}")
                
                definitions_added += 1
            
            # Serialize enhanced graph
            enhanced_ttl = graph.serialize(format='turtle')
            
            # Create new version with integrated definitions
            new_version_number = get_next_version_number(cur, ont_id)
            cur.execute("""
                INSERT INTO ontology_versions (
                    ontology_id, version_number, version_tag, content, 
                    is_current, is_draft, workflow_status,
                    created_by, change_summary, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                ont_id, new_version_number, 'definitions-integrated', enhanced_ttl,
                False, True, 'draft',
                'ttl_integration_script', 
                f'Integrated {definitions_added} entity definitions from database into TTL content with rdfs:comment, skos:definition, and metadata properties',
                datetime.utcnow()
            ))
            
            print(f"   ✅ Created version {new_version_number} with {definitions_added} integrated definitions")
            total_updated += definitions_added
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"\n✅ Successfully integrated {total_updated} definitions into TTL content")
        print("📋 Next Steps:")
        print("  1. Review draft versions at http://localhost:5003")
        print("  2. Make draft versions current if satisfied")
        print("  3. Test external system access to definitions")
        
        return True
        
    except Exception as e:
        print(f"❌ Error integrating definitions: {e}")
        return False

def create_basic_ontology_structure(base_uri: str, ont_name: str) -> rdflib.Graph:
    """Create a basic ontology structure."""
    graph = rdflib.Graph()
    
    # Add namespace bindings
    graph.bind("rdf", RDF)
    graph.bind("rdfs", RDFS) 
    graph.bind("owl", OWL)
    graph.bind("skos", SKOS)
    graph.bind("dct", DCTERMS)
    
    # Add ontology declaration
    ontology_ref = rdflib.URIRef(base_uri)
    graph.add((ontology_ref, RDF.type, OWL.Ontology))
    graph.add((ontology_ref, RDFS.label, rdflib.Literal(ont_name)))
    graph.add((ontology_ref, RDFS.comment, rdflib.Literal(f"Ontology with integrated definitions from OntServe database")))
    
    return graph

def get_next_version_number(cursor, ontology_id: int) -> int:
    """Get the next version number for an ontology."""
    cursor.execute("""
        SELECT MAX(version_number) FROM ontology_versions 
        WHERE ontology_id = %s
    """, (ontology_id,))
    
    result = cursor.fetchone()
    max_version = result[0] if result and result[0] else 0
    return max_version + 1

def promote_integrated_versions():
    """Helper function to promote integrated versions to current."""
    
    print("\n🚀 Promoting Integrated Versions to Current")
    print("=" * 50)
    
    try:
        conn = psycopg2.connect(os.environ['ONTSERVE_DB_URL'])
        cur = conn.cursor()
        
        # Find all draft versions with definitions-integrated tag
        cur.execute("""
            SELECT v.id, v.ontology_id, o.name, v.version_number
            FROM ontology_versions v
            JOIN ontologies o ON v.ontology_id = o.id
            WHERE v.version_tag = 'definitions-integrated' 
            AND v.is_draft = true
            ORDER BY o.name
        """)
        
        integrated_versions = cur.fetchall()
        
        if not integrated_versions:
            print("No integrated versions found to promote")
            return
        
        for version_id, ont_id, ont_name, version_number in integrated_versions:
            print(f"  Promoting {ont_name} v{version_number} to current...")
            
            # Set all versions for this ontology to non-current
            cur.execute("""
                UPDATE ontology_versions 
                SET is_current = false 
                WHERE ontology_id = %s
            """, (ont_id,))
            
            # Make the integrated version current
            cur.execute("""
                UPDATE ontology_versions 
                SET is_current = true, is_draft = false, workflow_status = 'published'
                WHERE id = %s
            """, (version_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"✅ Promoted {len(integrated_versions)} integrated versions to current")
        
    except Exception as e:
        print(f"❌ Error promoting versions: {e}")

def main():
    """Main execution function."""
    success = integrate_definitions_into_ttl()
    
    if success:
        print("\n" + "=" * 60)
        print("🎉 TTL Definition Integration Complete!")
        print("✅ Entity definitions now embedded in TTL content")
        print("✅ External systems can access rdfs:comment and skos:definition")
        print("✅ Confidence scores and metadata preserved as custom properties")
        
        # Ask user if they want to promote versions
        response = input("\n🤔 Promote integrated versions to current? (y/n): ").lower().strip()
        if response in ['y', 'yes']:
            promote_integrated_versions()
        else:
            print("💡 Integrated versions remain as drafts - you can review and promote them manually at http://localhost:5003")
    else:
        print("\n❌ TTL integration failed")

if __name__ == "__main__":
    main()