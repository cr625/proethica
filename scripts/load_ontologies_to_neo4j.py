#!/usr/bin/env python3
"""
Load ProEthica ontologies into Neo4j for visualization.
This script loads both the intermediate and engineering ethics ontologies,
preserving the relationships between them.
"""

import os
import sys
from pathlib import Path
from neo4j import GraphDatabase
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Neo4j connection details
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "proethica123")

# Ontology namespaces
PROETHICA = Namespace("http://proethica.org/ontology/")
ENG_ETHICS = Namespace("http://proethica.org/engineering-ethics/")
BFO = Namespace("http://purl.obolibrary.org/obo/")

class OntologyLoader:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        
    def close(self):
        self.driver.close()
        
    def clear_database(self):
        """Clear existing data from Neo4j"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("Cleared existing data from Neo4j")
    
    def create_constraints(self):
        """Create constraints and indexes for better performance"""
        with self.driver.session() as session:
            # Create uniqueness constraint for URIs
            try:
                session.run("""
                    CREATE CONSTRAINT uri_unique IF NOT EXISTS
                    FOR (n:Resource) REQUIRE n.uri IS UNIQUE
                """)
            except:
                # Older Neo4j versions
                session.run("""
                    CREATE CONSTRAINT ON (n:Resource) ASSERT n.uri IS UNIQUE
                """)
            print("Created constraints")
    
    def load_ontology(self, file_path, ontology_name):
        """Load an ontology file into Neo4j"""
        print(f"\nLoading {ontology_name} from {file_path}")
        
        # Parse the ontology
        g = Graph()
        g.parse(file_path, format="turtle")
        
        print(f"Parsed {len(g)} triples")
        
        with self.driver.session() as session:
            # Create nodes for all subjects and objects
            subjects_objects = set()
            for s, p, o in g:
                if isinstance(s, URIRef):
                    subjects_objects.add(str(s))
                if isinstance(o, URIRef):
                    subjects_objects.add(str(o))
            
            # Batch create nodes
            for uri in subjects_objects:
                # Determine node labels based on URI
                labels = ["Resource"]
                
                # Add ontology-specific labels
                if "proethica.org/ontology/" in uri and "engineering-ethics" not in uri:
                    labels.append("ProEthicaIntermediate")
                elif "engineering-ethics" in uri:
                    labels.append("EngineeringEthics")
                elif "obolibrary.org/obo/" in uri:
                    labels.append("BFO")
                
                # Get local name for display
                local_name = uri.split("#")[-1].split("/")[-1]
                
                # Create node with proper label syntax
                labels_str = ":".join(labels)
                session.run(
                    f"""
                    MERGE (n:{labels_str} {{uri: $uri}})
                    SET n.localName = $localName,
                        n.ontology = $ontology
                    """,
                    uri=uri,
                    localName=local_name,
                    ontology=ontology_name
                )
            
            print(f"Created {len(subjects_objects)} nodes")
            
            # Create relationships
            relationship_count = 0
            for s, p, o in g:
                if isinstance(s, URIRef) and isinstance(o, URIRef):
                    # Get relationship type
                    rel_type = str(p).split("#")[-1].split("/")[-1].upper()
                    
                    # Create relationship
                    session.run(
                        f"""
                        MATCH (s:Resource {{uri: $subject}})
                        MATCH (o:Resource {{uri: $object}})
                        CREATE (s)-[r:`{rel_type}`]->(o)
                        SET r.predicate = $predicate
                        """,
                        subject=str(s),
                        object=str(o),
                        predicate=str(p)
                    )
                    relationship_count += 1
                elif isinstance(s, URIRef) and isinstance(o, Literal):
                    # Add literal properties to nodes
                    prop_name = str(p).split("#")[-1].split("/")[-1]
                    session.run(
                        """
                        MATCH (n:Resource {uri: $uri})
                        SET n[$propName] = $value
                        """,
                        uri=str(s),
                        propName=prop_name,
                        value=str(o)
                    )
            
            print(f"Created {relationship_count} relationships")
    
    def create_hierarchy_relationships(self):
        """Create additional relationships to show ontology hierarchy"""
        with self.driver.session() as session:
            # Link intermediate ontology concepts to their engineering ethics implementations
            session.run("""
                MATCH (pi:ProEthicaIntermediate)
                MATCH (ee:EngineeringEthics)
                WHERE ee.localName CONTAINS pi.localName
                   OR pi.localName CONTAINS ee.localName
                CREATE (pi)-[:IMPLEMENTED_BY]->(ee)
            """)
            
            # Create visual grouping for better layout
            session.run("""
                MERGE (pi:OntologyGroup {name: 'ProEthica Intermediate'})
                MERGE (ee:OntologyGroup {name: 'Engineering Ethics'})
                MERGE (bfo:OntologyGroup {name: 'BFO'})
                
                WITH pi, ee, bfo
                MATCH (n:ProEthicaIntermediate)
                CREATE (pi)-[:CONTAINS]->(n)
                
                WITH pi, ee, bfo
                MATCH (n:EngineeringEthics)
                CREATE (ee)-[:CONTAINS]->(n)
                
                WITH pi, ee, bfo
                MATCH (n:BFO)
                CREATE (bfo)-[:CONTAINS]->(n)
            """)
            
            print("Created hierarchy relationships")
    
    def get_statistics(self):
        """Get statistics about loaded ontologies"""
        with self.driver.session() as session:
            stats = {}
            
            # Count nodes by type
            result = session.run("""
                MATCH (n)
                RETURN labels(n) as labels, count(n) as count
                ORDER BY count DESC
            """)
            
            print("\nNode Statistics:")
            for record in result:
                labels = ", ".join(record["labels"])
                print(f"  {labels}: {record['count']}")
            
            # Count relationships
            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(r) as count
                ORDER BY count DESC
                LIMIT 10
            """)
            
            print("\nTop 10 Relationship Types:")
            for record in result:
                print(f"  {record['type']}: {record['count']}")

def main():
    # Initialize loader
    loader = OntologyLoader(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    try:
        # Clear existing data
        loader.clear_database()
        
        # Create constraints
        loader.create_constraints()
        
        # Load ontologies
        ontology_dir = Path("ontologies")
        
        # Load BFO first (base ontology)
        if (ontology_dir / "bfo.ttl").exists():
            loader.load_ontology(ontology_dir / "bfo.ttl", "BFO")
        
        # Load ProEthica intermediate ontology
        loader.load_ontology(
            ontology_dir / "proethica-intermediate.ttl", 
            "ProEthica-Intermediate"
        )
        
        # Load Engineering Ethics ontology
        loader.load_ontology(
            ontology_dir / "engineering-ethics.ttl",
            "Engineering-Ethics"
        )
        
        # Create hierarchy relationships
        loader.create_hierarchy_relationships()
        
        # Show statistics
        loader.get_statistics()
        
        print("\n✅ Ontologies loaded successfully!")
        print(f"\n🌐 View in Neo4j Browser: http://localhost:7474")
        print("   Username: neo4j")
        print("   Password: proethica123")
        print("\n📊 Example queries to visualize:")
        print("   1. Show all: MATCH (n) RETURN n LIMIT 100")
        print("   2. Show hierarchy: MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 100")
        print("   3. Show intermediate to engineering links:")
        print("      MATCH (pi:ProEthicaIntermediate)-[r]-(ee:EngineeringEthics)")
        print("      RETURN pi,r,ee")
        
    finally:
        loader.close()

if __name__ == "__main__":
    main()