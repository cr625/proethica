#!/usr/bin/env python3
"""
Import Technical Standards into Engineering-Ethics Ontology
"""

import os
import sys
from pathlib import Path
import psycopg2
from datetime import datetime
import rdflib
from rdflib.namespace import RDF, RDFS, OWL, SKOS

# Set environment variables
os.environ.setdefault('ONTSERVE_DB_URL', 'postgresql://ontserve_user:ontserve_development_password@localhost:5432/ontserve')

def merge_with_engineering_ethics():
    """Merge technical standards with existing engineering-ethics ontology."""
    
    print("🔄 Merging Technical Standards with Engineering-Ethics Ontology")
    print("=" * 70)
    
    try:
        # Read the technical standards file
        standards_file = Path(__file__).parent.parent / 'ontologies/technical_standards.ttl'
        with open(standards_file, 'r', encoding='utf-8') as f:
            standards_content = f.read()
        
        # Connect to database
        conn = psycopg2.connect(os.environ['ONTSERVE_DB_URL'])
        cur = conn.cursor()
        
        # Get engineering-ethics ontology
        cur.execute("""
            SELECT o.id, o.name, v.content
            FROM ontologies o
            JOIN ontology_versions v ON o.id = v.ontology_id AND v.is_current = true
            WHERE o.name = 'engineering-ethics'
        """)
        
        result = cur.fetchone()
        if not result:
            print("❌ Engineering-ethics ontology not found")
            return False
        
        ontology_id, name, existing_content = result
        
        # Parse both ontologies
        g_existing = rdflib.Graph()
        g_standards = rdflib.Graph()
        
        if existing_content and existing_content.strip():
            try:
                g_existing.parse(data=existing_content, format='turtle')
                print(f"   Parsed existing content: {len(g_existing)} triples")
            except Exception as e:
                print(f"   ⚠️  Existing content parse warning: {e}")
        
        g_standards.parse(data=standards_content, format='turtle')
        print(f"   Parsed technical standards: {len(g_standards)} triples")
        
        # Merge the graphs
        for triple in g_standards:
            g_existing.add(triple)
        
        # Serialize merged content
        merged_content = g_existing.serialize(format='turtle')
        print(f"   Merged ontology: {len(g_existing)} triples")
        
        # Update the ontology version
        cur.execute("""
            UPDATE ontology_versions 
            SET content = %s
            WHERE ontology_id = %s AND is_current = true
        """, (merged_content, ontology_id))
        
        conn.commit()
        
        # Extract entities from the merged content
        entities_added = extract_entities_from_content(g_existing, ontology_id, name, cur)
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"✅ Successfully merged technical standards into engineering-ethics")
        print(f"   Added {entities_added} new entities")
        print(f"   Total ontology size: {len(g_existing)} triples")
        
        return True
        
    except Exception as e:
        print(f"❌ Error merging standards: {e}")
        return False

def extract_entities_from_content(graph, ontology_id, ontology_name, cursor):
    """Extract entities from RDF graph and store in database."""
    
    # Define ProEthica concept types
    proethica_ns = rdflib.Namespace("http://proethica.org/ontology/intermediate#")
    engstd_ns = rdflib.Namespace("http://proethica.org/ontology/engineering_standards#")
    
    # Extract ProEthica concept instances
    concept_types = [
        proethica_ns.Principle, proethica_ns.Obligation, proethica_ns.Role,
        proethica_ns.Action, proethica_ns.Resource, proethica_ns.Constraint,
        proethica_ns.Event, proethica_ns.State, proethica_ns.Capability
    ]
    
    entities = []
    for concept_type in concept_types:
        entities.extend(list(graph.subjects(RDF.type, concept_type)))
    
    # Also extract traditional OWL classes
    entities.extend(list(graph.subjects(RDF.type, OWL.Class)))
    entities.extend(list(graph.subjects(RDF.type, RDFS.Class)))
    
    entities_added = 0
    
    for entity_uri in entities:
        if not isinstance(entity_uri, rdflib.URIRef):
            continue
        
        # Only process engineering standards namespace entities (new ones)
        if not str(entity_uri).startswith(str(engstd_ns)):
            continue
            
        # Get label and comment
        label = graph.value(entity_uri, RDFS.label)
        comment = graph.value(entity_uri, RDFS.comment) or graph.value(entity_uri, SKOS.definition)
        
        # Skip if no label
        if not label:
            continue
        
        try:
            # Check if entity already exists
            cursor.execute("SELECT id FROM ontology_entities WHERE ontology_id = %s AND uri = %s", 
                          (ontology_id, str(entity_uri)))
            if cursor.fetchone():
                continue  # Skip if already exists
            
            cursor.execute("""
                INSERT INTO ontology_entities (
                    ontology_id, entity_type, uri, label, comment, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                ontology_id, 'class', str(entity_uri), str(label), 
                str(comment) if comment else None, datetime.utcnow()
            ))
            entities_added += cursor.rowcount
            
        except Exception as e:
            print(f"   ⚠️  Error inserting {entity_uri}: {e}")
    
    return entities_added

def main():
    """Main function to merge technical standards."""
    
    success = merge_with_engineering_ethics()
    
    if success:
        print("\n" + "=" * 70)
        print("🎉 Technical Standards Integration Complete!")
        print("✅ Engineering-ethics ontology now includes comprehensive technical standards")
        print("✅ ISO, IEC, ANSI, and other major standards integrated")
        print("✅ Standards-based obligations and constraints defined")
        print("\n🔗 View at: http://localhost:5003/ontology/engineering-ethics")
        print("\n📋 Next Steps:")
        print("  1. Web interface visibility fixes")  
        print("  2. Definition integration into TTL content")
        print("  3. Enhanced annotation system testing")
    else:
        print("\n❌ Technical standards integration failed")

if __name__ == "__main__":
    main()