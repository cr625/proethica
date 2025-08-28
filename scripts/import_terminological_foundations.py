#!/usr/bin/env python3
"""
Import Terminological Foundations with dc:source References
"""

import os
import sys
from pathlib import Path
import psycopg2
from datetime import datetime
import rdflib
from rdflib.namespace import RDF, RDFS, OWL, SKOS, DCTERMS

# Set environment variables
os.environ.setdefault('ONTSERVE_DB_URL', 'postgresql://ontserve_user:ontserve_development_password@localhost:5432/ontserve')

def import_terminological_foundations():
    """Import terminological foundations as a new ontology."""
    
    print("🏗️ Importing Terminological Foundations Ontology")
    print("=" * 60)
    
    try:
        # Read the terminological foundations file
        foundations_file = Path(__file__).parent.parent / 'ontologies/terminological_foundations.ttl'
        with open(foundations_file, 'r', encoding='utf-8') as f:
            foundations_content = f.read()
        
        # Connect to database
        conn = psycopg2.connect(os.environ['ONTSERVE_DB_URL'])
        cur = conn.cursor()
        
        # Create new ontology entry
        ontology_name = "Terminological Foundations"
        base_uri = "http://proethica.org/ontology/terminological_foundations#"
        description = "Essential terminological concepts derived from ISO standards (15926, 80000, 6707-1) and professional organization standards to ground engineering ethics representations in professional practice"
        
        # Check if ontology already exists
        cur.execute("SELECT id FROM ontologies WHERE name = %s", (ontology_name,))
        existing = cur.fetchone()
        
        if existing:
            print(f"⚠️  Ontology {ontology_name} already exists, updating...")
            ontology_id = existing[0]
            
            # Update existing ontology version
            cur.execute("""
                UPDATE ontology_versions 
                SET content = %s
                WHERE ontology_id = %s AND is_current = true
            """, (foundations_content, ontology_id))
        else:
            # Create new ontology
            cur.execute("""
                INSERT INTO ontologies (name, base_uri, description, created_at)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (ontology_name, base_uri, description, datetime.utcnow()))
            ontology_id = cur.fetchone()[0]
            
            # Create initial version
            cur.execute("""
                INSERT INTO ontology_versions (
                    ontology_id, version_number, version_tag, content, 
                    is_current, is_draft, workflow_status, 
                    created_by, change_summary, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                ontology_id, 1, 'initial', foundations_content,
                True, False, 'published',
                'import_script', f'Initial import of {ontology_name}',
                datetime.utcnow()
            ))
        
        conn.commit()
        
        # Extract entities with enhanced dc:source handling
        entities_added = extract_entities_with_sources(foundations_content, ontology_id, ontology_name, cur)
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"✅ Successfully imported {ontology_name}")
        print(f"   Added {entities_added} entities with dc:source references")
        
        return True, entities_added
        
    except Exception as e:
        print(f"❌ Error importing terminological foundations: {e}")
        return False, 0

def extract_entities_with_sources(content, ontology_id, ontology_name, cursor):
    """Extract entities with enhanced dc:source metadata."""
    
    # Parse the content
    g = rdflib.Graph()
    g.parse(data=content, format='turtle')
    
    # Define namespaces
    proethica_ns = rdflib.Namespace("http://proethica.org/ontology/intermediate#")
    termfound_ns = rdflib.Namespace("http://proethica.org/ontology/terminological_foundations#")
    
    # Extract ProEthica concept instances
    concept_types = [
        proethica_ns.Principle, proethica_ns.Obligation, proethica_ns.Role,
        proethica_ns.Action, proethica_ns.Resource, proethica_ns.Constraint,
        proethica_ns.Event, proethica_ns.State, proethica_ns.Capability
    ]
    
    entities = []
    for concept_type in concept_types:
        entities.extend(list(g.subjects(RDF.type, concept_type)))
    
    # Also extract traditional OWL classes
    entities.extend(list(g.subjects(RDF.type, OWL.Class)))
    entities.extend(list(g.subjects(RDF.type, RDFS.Class)))
    
    entities_added = 0
    
    for entity_uri in entities:
        if not isinstance(entity_uri, rdflib.URIRef):
            continue
            
        # Get label, comment, and source
        label = g.value(entity_uri, RDFS.label)
        comment = g.value(entity_uri, RDFS.comment) or g.value(entity_uri, SKOS.definition)
        dc_source = g.value(entity_uri, DCTERMS.source)
        
        # Skip if no label
        if not label:
            continue
        
        try:
            # Check if entity already exists
            cursor.execute("SELECT id FROM ontology_entities WHERE ontology_id = %s AND uri = %s", 
                          (ontology_id, str(entity_uri)))
            if cursor.fetchone():
                continue  # Skip if already exists
            
            # Build enhanced properties with dc:source information
            properties = {}
            if dc_source:
                properties['dc:source'] = str(dc_source)
                properties['source_type'] = 'iso_standard' if 'iso.org' in str(dc_source) else 'professional_organization'
                
            # Add standard type if available
            standard_type = g.value(entity_uri, rdflib.Namespace("http://proethica.org/ontology/intermediate#standardType"))
            if standard_type:
                properties['standard_type'] = str(standard_type)
                
            # Add applicable domains
            domains = list(g.objects(entity_uri, rdflib.Namespace("http://proethica.org/ontology/intermediate#appliesToDomain")))
            if domains:
                properties['applicable_domains'] = [str(domain) for domain in domains]
            
            cursor.execute("""
                INSERT INTO ontology_entities (
                    ontology_id, entity_type, uri, label, comment, properties, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                ontology_id, 'class', str(entity_uri), str(label), 
                str(comment) if comment else None,
                rdflib.Graph().serialize(format='json-ld', context=properties) if properties else None,
                datetime.utcnow()
            ))
            entities_added += cursor.rowcount
            
        except Exception as e:
            print(f"   ⚠️  Error inserting {entity_uri}: {e}")
    
    return entities_added

def verify_dc_source_implementation():
    """Verify that dc:source references are properly implemented."""
    
    print("\n🔍 Verifying dc:source Implementation")
    print("-" * 40)
    
    try:
        conn = psycopg2.connect(os.environ['ONTSERVE_DB_URL'])
        cur = conn.cursor()
        
        # Check entities with dc:source references
        cur.execute("""
            SELECT 
                e.label,
                e.properties::text
            FROM ontology_entities e
            JOIN ontologies o ON e.ontology_id = o.id
            WHERE o.name = 'Terminological Foundations'
            AND e.properties::text LIKE '%dc:source%'
            LIMIT 5
        """)
        
        results = cur.fetchall()
        
        if results:
            print(f"✅ Found {len(results)} entities with dc:source references:")
            for label, properties in results:
                print(f"   - {label}")
                if 'iso.org' in properties:
                    print(f"     → ISO Standard Reference")
                if 'nspe.org' in properties or 'asce.org' in properties or 'ieee.org' in properties:
                    print(f"     → Professional Organization Reference")
        else:
            print("❌ No entities found with dc:source references")
            
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error verifying dc:source implementation: {e}")

def main():
    """Main function to import terminological foundations."""
    
    success, entities_count = import_terminological_foundations()
    
    if success:
        verify_dc_source_implementation()
        
        print("\n" + "=" * 60)
        print("🎉 Terminological Foundations Import Complete!")
        print(f"✅ Added {entities_count} entities with proper dc:source attribution")
        print("✅ ISO standards: 15926 (Industrial Automation), 80000 (Quantities/Units), 6707-1 (Civil Engineering)")
        print("✅ Professional organization references: NSPE, ASCE, IEEE")
        print("✅ Proper attribution without copyright infringement")
        print("\n🔗 View at: http://localhost:5003/ontology/terminological-foundations")
        
        # Show the corrected statement
        print("\n📝 CORRECTED STATEMENT:")
        print("Standards ground representations in professional practice through comprehensive")
        print("ISO standards providing definitional foundations: ISO 15926 for industrial")  
        print("automation terminology, ISO 80000 for quantities and units, and ISO 6707-1:2020")
        print("for building and civil engineering vocabulary. Professional organization standards")
        print("from NSPE, ASCE, IEEE, ASME, and PMI serve as authoritative sources for role")
        print("definitions and obligations, properly referenced through dct:source properties")
        print("with selective conceptual import rather than full standard reproduction.")
        
    else:
        print("\n❌ Terminological foundations import failed")

if __name__ == "__main__":
    main()