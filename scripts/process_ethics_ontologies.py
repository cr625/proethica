#!/usr/bin/env python3
"""
Process Ethics Ontologies to Extract Entities
"""

import os
import sys
from pathlib import Path
import psycopg2
from datetime import datetime

# Set environment variables
os.environ.setdefault('ONTSERVE_DB_URL', 'postgresql://ontserve_user:ontserve_development_password@localhost:5432/ontserve')

def extract_entities_from_turtle(content: str, ontology_id: int, ontology_name: str):
    """Extract entities from Turtle content and store in database."""
    
    import rdflib
    from rdflib.namespace import RDF, RDFS, OWL, SKOS
    
    try:
        # Parse the Turtle content
        g = rdflib.Graph()
        g.parse(data=content, format='turtle')
        
        # Connect to database
        conn = psycopg2.connect(os.environ['ONTSERVE_DB_URL'])
        cur = conn.cursor()
        
        # Define ProEthica concept types
        proethica_ns = rdflib.Namespace("http://proethica.org/ontology/intermediate#")
        
        # Extract ProEthica concept instances (not OWL classes)
        concept_types = [
            proethica_ns.Principle, proethica_ns.Obligation, proethica_ns.Role,
            proethica_ns.Action, proethica_ns.Resource, proethica_ns.Constraint,
            proethica_ns.Event, proethica_ns.State, proethica_ns.Capability
        ]
        
        classes = []
        for concept_type in concept_types:
            classes.extend(list(g.subjects(RDF.type, concept_type)))
        
        # Also extract traditional OWL classes and properties
        owl_classes = list(g.subjects(RDF.type, OWL.Class))
        owl_classes.extend(list(g.subjects(RDF.type, RDFS.Class)))
        
        # Extract properties
        properties = list(g.subjects(RDF.type, OWL.ObjectProperty))
        properties.extend(list(g.subjects(RDF.type, OWL.DatatypeProperty)))
        properties.extend(list(g.subjects(RDF.type, RDF.Property)))
        
        # Combine all classes
        classes.extend(owl_classes)
        
        entities_added = 0
        
        # Process classes
        for class_uri in classes:
            if not isinstance(class_uri, rdflib.URIRef):
                continue
                
            # Get label and comment
            label = g.value(class_uri, RDFS.label)
            comment = g.value(class_uri, RDFS.comment) or g.value(class_uri, SKOS.definition)
            
            # Skip if no label
            if not label:
                continue
                
            try:
                # Check if entity already exists
                cur.execute("SELECT id FROM ontology_entities WHERE ontology_id = %s AND uri = %s", 
                           (ontology_id, str(class_uri)))
                if cur.fetchone():
                    continue  # Skip if already exists
                
                cur.execute("""
                    INSERT INTO ontology_entities (
                        ontology_id, entity_type, uri, label, comment, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    ontology_id, 'class', str(class_uri), str(label), 
                    str(comment) if comment else None, datetime.utcnow()
                ))
                entities_added += cur.rowcount
            except Exception as e:
                print(f"   ⚠️  Error inserting class {class_uri}: {e}")
        
        # Process properties  
        for prop_uri in properties:
            if not isinstance(prop_uri, rdflib.URIRef):
                continue
                
            # Get label and comment
            label = g.value(prop_uri, RDFS.label)
            comment = g.value(prop_uri, RDFS.comment) or g.value(prop_uri, SKOS.definition)
            
            # Skip if no label
            if not label:
                continue
                
            try:
                # Check if entity already exists
                cur.execute("SELECT id FROM ontology_entities WHERE ontology_id = %s AND uri = %s", 
                           (ontology_id, str(prop_uri)))
                if cur.fetchone():
                    continue  # Skip if already exists
                
                cur.execute("""
                    INSERT INTO ontology_entities (
                        ontology_id, entity_type, uri, label, comment, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    ontology_id, 'property', str(prop_uri), str(label),
                    str(comment) if comment else None, datetime.utcnow()
                ))
                entities_added += cur.rowcount
            except Exception as e:
                print(f"   ⚠️  Error inserting property {prop_uri}: {e}")
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"   ✅ Extracted {entities_added} entities from {ontology_name}")
        print(f"      Classes: {len(classes)}, Properties: {len(properties)}")
        
        return entities_added
        
    except Exception as e:
        print(f"   ❌ Error processing {ontology_name}: {e}")
        return 0

def process_all_ethics_ontologies():
    """Process all imported ethics ontologies."""
    
    print("🔄 Processing Ethics Ontologies for Entity Extraction")
    print("=" * 60)
    
    try:
        conn = psycopg2.connect(os.environ['ONTSERVE_DB_URL'])
        cur = conn.cursor()
        
        # Get all ethics ontologies
        cur.execute("""
            SELECT o.id, o.name, v.content
            FROM ontologies o
            JOIN ontology_versions v ON o.id = v.ontology_id AND v.is_current = true
            WHERE o.name LIKE '%Ethics%'
            ORDER BY o.name
        """)
        
        ontologies = cur.fetchall()
        cur.close()
        conn.close()
        
        total_entities = 0
        
        for ontology_id, name, content in ontologies:
            print(f"\n📋 Processing {name}...")
            entities = extract_entities_from_turtle(content, ontology_id, name)
            total_entities += entities
        
        print("\n" + "=" * 60)
        print(f"📊 Processing Summary: {total_entities} total entities extracted")
        print(f"🎉 Ethics codes are now ready for use!")
        print("\n🔗 View at: http://localhost:5003/ontologies")
        
        return total_entities
        
    except Exception as e:
        print(f"❌ Error processing ontologies: {e}")
        return 0

if __name__ == "__main__":
    process_all_ethics_ontologies()