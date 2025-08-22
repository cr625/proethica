"""
Neo4j Graph Service for ProEthica
Provides graph data queries for web visualization.
"""

import os
import logging
from typing import Dict, List, Any, Optional
from neo4j import GraphDatabase
from flask import current_app

logger = logging.getLogger(__name__)

class Neo4jGraphService:
    """Service for querying Neo4j graph data for visualization."""
    
    def __init__(self):
        self.driver = None
        self.connected = False
        
    def connect(self):
        """Initialize connection to Neo4j."""
        if self.connected:
            return True
            
        try:
            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            user = os.getenv("NEO4J_USER", "neo4j")
            password = os.getenv("NEO4J_PASSWORD", "proethica123")
            
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            
            self.connected = True
            logger.info("Connected to Neo4j successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            return False
    
    def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()
            self.connected = False
    
    def get_ontology_graph(self, ontology: str = None, limit: int = 100) -> Dict[str, Any]:
        """
        Get graph data for a specific ontology or all ontologies.
        
        Args:
            ontology: Specific ontology to query ('engineering-ethics', 'proethica-intermediate', 'bfo')
            limit: Maximum number of nodes to return
            
        Returns:
            Dictionary with nodes and edges for visualization
        """
        if not self.connect():
            return {"nodes": [], "edges": [], "error": "Failed to connect to Neo4j"}
        
        try:
            with self.driver.session() as session:
                # Build query based on ontology filter
                if ontology == "engineering-ethics":
                    query = """
                    MATCH (n:EngineeringEthics)
                    OPTIONAL MATCH (n)-[r]-(m)
                    RETURN n, r, m
                    LIMIT $limit
                    """
                elif ontology == "proethica-intermediate":
                    query = """
                    MATCH (n:ProEthicaIntermediate)
                    OPTIONAL MATCH (n)-[r]-(m)
                    RETURN n, r, m
                    LIMIT $limit
                    """
                elif ontology == "bfo":
                    query = """
                    MATCH (n:BFO)
                    OPTIONAL MATCH (n)-[r]-(m)
                    RETURN n, r, m
                    LIMIT $limit
                    """
                elif ontology == "relationships":
                    query = """
                    MATCH (pi:ProEthicaIntermediate)-[r]-(ee:EngineeringEthics)
                    RETURN pi as n, r, ee as m
                    UNION
                    MATCH (pi:ProEthicaIntermediate)-[r:SUBCLASSOF]-(parent)
                    RETURN pi as n, r, parent as m
                    UNION
                    MATCH (ee:EngineeringEthics)-[r:SUBCLASSOF]-(parent)
                    RETURN ee as n, r, parent as m
                    LIMIT $limit
                    """
                else:
                    # Default: show all with relationships
                    query = """
                    MATCH (n)-[r]-(m)
                    WHERE n:ProEthicaIntermediate OR n:EngineeringEthics
                    RETURN n, r, m
                    LIMIT $limit
                    """
                
                result = session.run(query, limit=limit)
                
                nodes = {}
                edges = []
                
                for record in result:
                    # Process source node
                    n = record.get("n")
                    if n:
                        node_id = n.get("uri", str(n.id))
                        if node_id not in nodes:
                            nodes[node_id] = self._format_node(n)
                    
                    # Process relationship and target node
                    r = record.get("r")
                    m = record.get("m")
                    
                    if r and m and n:
                        target_id = m.get("uri", str(m.id))
                        if target_id not in nodes:
                            nodes[target_id] = self._format_node(m)
                        
                        # Add edge
                        edges.append({
                            "id": f"{node_id}-{target_id}",
                            "source": node_id,
                            "target": target_id,
                            "label": type(r).__name__ if hasattr(r, '__name__') else str(r.type),
                            "type": str(r.type) if hasattr(r, 'type') else "RELATED"
                        })
                
                return {
                    "nodes": list(nodes.values()),
                    "edges": edges,
                    "stats": {
                        "nodeCount": len(nodes),
                        "edgeCount": len(edges),
                        "ontology": ontology or "all"
                    }
                }
                
        except Exception as e:
            logger.error(f"Error querying Neo4j: {e}")
            return {"nodes": [], "edges": [], "error": str(e)}
    
    def _format_node(self, node) -> Dict[str, Any]:
        """Format a Neo4j node for visualization."""
        labels = list(node.labels)
        properties = dict(node)
        
        # Determine node type and color
        node_type = "unknown"
        color = "#gray"
        
        if "ProEthicaIntermediate" in labels:
            node_type = "intermediate"
            color = "#3498db"  # Blue
        elif "EngineeringEthics" in labels:
            node_type = "engineering"
            color = "#e74c3c"  # Red
        elif "BFO" in labels:
            node_type = "bfo"
            color = "#2ecc71"  # Green
        
        return {
            "id": properties.get("uri", str(node.id)),
            "label": properties.get("localName", properties.get("uri", "Unknown")),
            "type": node_type,
            "color": color,
            "ontology": properties.get("ontology", "unknown"),
            "properties": properties,
            "labels": labels
        }
    
    def get_ontology_stats(self) -> Dict[str, Any]:
        """Get statistics about loaded ontologies."""
        if not self.connect():
            return {"error": "Failed to connect to Neo4j"}
        
        try:
            with self.driver.session() as session:
                # Count nodes by type
                node_stats = session.run("""
                    MATCH (n)
                    RETURN labels(n) as labels, count(n) as count
                    ORDER BY count DESC
                """).data()
                
                # Count relationships
                rel_stats = session.run("""
                    MATCH ()-[r]->()
                    RETURN type(r) as type, count(r) as count
                    ORDER BY count DESC
                    LIMIT 10
                """).data()
                
                return {
                    "nodes": node_stats,
                    "relationships": rel_stats
                }
                
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"error": str(e)}

# Global instance
_neo4j_service = None

def get_neo4j_service() -> Neo4jGraphService:
    """Get singleton instance of Neo4j service."""
    global _neo4j_service
    if _neo4j_service is None:
        _neo4j_service = Neo4jGraphService()
    return _neo4j_service