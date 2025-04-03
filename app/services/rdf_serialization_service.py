import os
import tempfile
from rdflib import Graph, Namespace, Literal, URIRef, RDF, RDFS, BNode
from rdflib.namespace import XSD
from app import db
from app.models.entity_triple import EntityTriple
from app.services.entity_triple_service import EntityTripleService
from typing import List, Dict, Tuple, Optional, Union, Any, Set
import json
from datetime import datetime

class RDFSerializationService:
    """
    Service for serializing entity triples to various RDF formats and importing RDF data.
    This service provides methods for:
    1. Exporting entity triples as RDF/Turtle, RDF/XML, and JSON-LD formats
    2. Importing RDF data into the entity_triples table
    3. Utilities for working with RDF formats
    """
    
    def __init__(self):
        # Get an EntityTripleService instance to work with
        self.entity_triple_service = EntityTripleService()
        # Get namespaces from entity triple service
        self.namespaces = self.entity_triple_service.get_namespaces()
        
        # Additional namespaces for serialization
        self.namespaces['xsd'] = XSD
        self.namespaces['time'] = Namespace("http://www.w3.org/2006/time#")
    
    def export_triples_to_graph(self, **filters) -> Graph:
        """
        Export entity triples to an RDFLib Graph.
        
        Args:
            **filters: Filters to apply when querying triples (e.g., entity_type, entity_id)
            
        Returns:
            RDFLib Graph containing the triples
        """
        # Create a new RDF graph
        g = Graph()
        
        # Bind all namespaces
        for prefix, namespace in self.namespaces.items():
            g.bind(prefix, namespace)
        
        # Get triples based on filters
        triples = self.entity_triple_service.find_triples(**filters)
        
        # Add each triple to the graph
        for triple in triples:
            # Convert subject to URIRef
            subject = URIRef(triple.subject)
            
            # Convert predicate to URIRef
            predicate = URIRef(triple.predicate)
            
            # Convert object based on whether it's a literal or URI
            if triple.is_literal:
                # Try to type the literal appropriately
                value = triple.object_literal
                
                # Check if the value is a boolean
                if value.lower() in ('true', 'false'):
                    obj = Literal(value.lower() == 'true', datatype=XSD.boolean)
                
                # Check if the value is an integer
                elif value.isdigit():
                    obj = Literal(int(value), datatype=XSD.integer)
                
                # Check if the value is a float
                elif self._is_float(value):
                    obj = Literal(float(value), datatype=XSD.float)
                
                # Default to string
                else:
                    obj = Literal(value)
            else:
                # Object is a URI
                obj = URIRef(triple.object_uri)
            
            # Add the triple to the graph
            g.add((subject, predicate, obj))
            
            # Add temporal information if available
            if hasattr(triple, 'valid_from') and triple.valid_from:
                # Create a blank node for the time interval
                interval = BNode()
                
                # Add the interval information
                g.add((subject, self.namespaces['time']['hasTime'], interval))
                g.add((interval, RDF.type, self.namespaces['time']['Interval']))
                g.add((interval, self.namespaces['time']['hasBeginning'], 
                      Literal(triple.valid_from.isoformat(), datatype=XSD.dateTime)))
                
                if triple.valid_to:
                    g.add((interval, self.namespaces['time']['hasEnd'], 
                          Literal(triple.valid_to.isoformat(), datatype=XSD.dateTime)))
        
        return g
    
    def export_to_turtle(self, output_path=None, **filters) -> str:
        """
        Export entity triples to Turtle format.
        
        Args:
            output_path: Optional path to save the Turtle file
            **filters: Filters to apply when querying triples
            
        Returns:
            Turtle string representation of the triples
        """
        # Get the graph
        g = self.export_triples_to_graph(**filters)
        
        # Serialize to Turtle
        turtle_data = g.serialize(format='turtle')
        
        # Save to file if output_path is provided
        if output_path:
            with open(output_path, 'w') as f:
                f.write(turtle_data)
        
        return turtle_data
    
    def export_to_rdfxml(self, output_path=None, **filters) -> str:
        """
        Export entity triples to RDF/XML format.
        
        Args:
            output_path: Optional path to save the RDF/XML file
            **filters: Filters to apply when querying triples
            
        Returns:
            RDF/XML string representation of the triples
        """
        # Get the graph
        g = self.export_triples_to_graph(**filters)
        
        # Serialize to RDF/XML
        rdfxml_data = g.serialize(format='xml')
        
        # Save to file if output_path is provided
        if output_path:
            with open(output_path, 'w') as f:
                f.write(rdfxml_data)
        
        return rdfxml_data
    
    def export_to_jsonld(self, output_path=None, **filters) -> str:
        """
        Export entity triples to JSON-LD format.
        
        Args:
            output_path: Optional path to save the JSON-LD file
            **filters: Filters to apply when querying triples
            
        Returns:
            JSON-LD string representation of the triples
        """
        # Get the graph
        g = self.export_triples_to_graph(**filters)
        
        # Create a context for JSON-LD
        context = {prefix: str(namespace) for prefix, namespace in self.namespaces.items()}
        
        # Serialize to JSON-LD
        jsonld_data = g.serialize(format='json-ld', context=context)
        
        # Save to file if output_path is provided
        if output_path:
            with open(output_path, 'w') as f:
                f.write(jsonld_data)
        
        return jsonld_data
    
    def import_from_rdf(self, input_source, format='turtle', 
                       entity_type=None, entity_id=None, scenario_id=None) -> List[EntityTriple]:
        """
        Import RDF data into the entity_triples table.
        
        Args:
            input_source: Path to an RDF file or RDF string
            format: Format of the RDF data ('turtle', 'xml', 'json-ld', etc.)
            entity_type: Entity type to associate with imported triples
            entity_id: Entity ID to associate with imported triples
            scenario_id: Scenario ID to associate with imported triples
            
        Returns:
            List of created EntityTriple objects
        """
        # Create a new RDF graph
        g = Graph()
        
        # Parse the input source
        if os.path.isfile(input_source):
            # Input is a file path
            g.parse(input_source, format=format)
        else:
            # Input is a string
            # Create a temporary file to hold the RDF data
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp:
                temp.write(input_source)
                temp_path = temp.name
            
            # Parse the temporary file
            g.parse(temp_path, format=format)
            
            # Remove the temporary file
            os.unlink(temp_path)
        
        # Convert graph to entity triples
        triples = []
        
        # Process each triple in the graph
        for s, p, o in g:
            # Convert subject from URIRef to string
            subject = str(s)
            
            # Convert predicate from URIRef to string
            predicate = str(p)
            
            # Process object based on its type
            if isinstance(o, Literal):
                # Object is a literal
                is_literal = True
                object_value = str(o)
                object_uri = None
            else:
                # Object is a URI
                is_literal = False
                object_value = None
                object_uri = str(o)
            
            # Create the triple entity
            triple = EntityTriple(
                subject=subject,
                predicate=predicate,
                object_literal=object_value,
                object_uri=object_uri,
                is_literal=is_literal,
                entity_type=entity_type,
                entity_id=entity_id,
                scenario_id=scenario_id,
                valid_from=datetime.utcnow(),
                valid_to=None
            )
            
            db.session.add(triple)
            triples.append(triple)
        
        # Look for temporal information
        for s, p, interval in g.triples((None, self.namespaces['time']['hasTime'], None)):
            # Get the triples with this subject
            subject_triples = [t for t in triples if t.subject == str(s)]
            
            # Get beginning time
            begin_time = None
            for _, _, begin in g.triples((interval, self.namespaces['time']['hasBeginning'], None)):
                if isinstance(begin, Literal) and begin.datatype == XSD.dateTime:
                    begin_time = datetime.fromisoformat(str(begin))
            
            # Get end time
            end_time = None
            for _, _, end in g.triples((interval, self.namespaces['time']['hasEnd'], None)):
                if isinstance(end, Literal) and end.datatype == XSD.dateTime:
                    end_time = datetime.fromisoformat(str(end))
            
            # Update temporal information for subject triples
            if begin_time:
                for triple in subject_triples:
                    triple.valid_from = begin_time
                    triple.valid_to = end_time
        
        # Commit the changes
        db.session.commit()
        
        return triples
    
    def _is_float(self, value: str) -> bool:
        """Check if a string can be converted to a float."""
        try:
            float(value)
            return True
        except ValueError:
            return False
