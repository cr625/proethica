from flask import Blueprint, request, jsonify, Response, render_template_string, current_app
from flask_login import login_required, current_user
from functools import wraps
import os
import re
import traceback
from urllib.parse import urlparse, unquote
from rdflib import Graph, URIRef, Namespace, RDF, RDFS, Literal
from rdflib.namespace import OWL

ontology_iri_bp = Blueprint('ontology_iri', __name__)

# Create a decorator to allow anonymous access
def allow_anonymous(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip login requirement for these routes
        return f(*args, **kwargs)
    return decorated_function

# HTML template for human-readable representation
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ entity_label }} - Ontology Entity</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        h1 {
            border-bottom: 1px solid #ddd;
            padding-bottom: 10px;
        }
        .meta {
            color: #555;
            font-size: 0.9em;
        }
        .description {
            background-color: #f9f9f9;
            padding: 15px;
            border-left: 4px solid #0066cc;
            margin: 20px 0;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
        }
        .format-link {
            display: inline-block;
            margin-right: 10px;
            padding: 5px 10px;
            background-color: #eee;
            text-decoration: none;
            color: #333;
            border-radius: 3px;
        }
        .format-link:hover {
            background-color: #ddd;
        }
        .uri {
            font-family: monospace;
            word-break: break-all;
        }
    </style>
</head>
<body>
    <h1>{{ entity_label }}</h1>
    <p class="uri">URI: {{ entity_uri }}</p>
    
    {% if description %}
    <div class="description">
        <p>{{ description }}</p>
    </div>
    {% endif %}
    
    {% if types %}
    <h2>Types</h2>
    <ul>
        {% for type in types %}
        <li><a href="{{ type.uri }}">{{ type.label }}</a> <span class="meta">({{ type.uri }})</span></li>
        {% endfor %}
    </ul>
    {% endif %}
    
    {% if properties %}
    <h2>Properties</h2>
    <table>
        <thead>
            <tr>
                <th>Property</th>
                <th>Value</th>
            </tr>
        </thead>
        <tbody>
            {% for prop in properties %}
            <tr>
                <td>
                    <a href="{{ prop.predicate.uri }}">{{ prop.predicate.label }}</a>
                    <div class="meta">{{ prop.predicate.uri }}</div>
                </td>
                <td>
                    {% if prop.object.is_literal %}
                        {{ prop.object.value }}
                    {% else %}
                        <a href="{{ prop.object.uri }}">{{ prop.object.label }}</a>
                        <div class="meta">{{ prop.object.uri }}</div>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% endif %}
    
    <div>
        <h3>Available Formats</h3>
        <a class="format-link" href="{{ request.url }}?format=ttl">Turtle</a>
        <a class="format-link" href="{{ request.url }}?format=xml">RDF/XML</a>
        <a class="format-link" href="{{ request.url }}?format=json">JSON-LD</a>
        <a class="format-link" href="{{ request.url }}?format=html">HTML</a>
    </div>
</body>
</html>
"""

def extract_ontology_info(iri):
    """
    Extract domain and entity identifiers from an ontology IRI.
    
    Args:
        iri: The IRI to parse
        
    Returns:
        Tuple of (domain, entity_id)
    """
    try:
        # Parse the IRI
        parsed = urlparse(iri)
        path = parsed.path
        fragment = parsed.fragment
        
        # Extract domain from path (e.g., /ontology/engineering-ethics)
        domain_match = re.search(r'/ontology/([^/]+)$', path)
        if domain_match:
            domain = domain_match.group(1)
        else:
            domain = path.strip('/').split('/')[-1]
        
        return domain, fragment
    except Exception as e:
        print(f"Error extracting ontology info: {str(e)}")
        return None, None

def get_ontology_graph(domain):
    """
    Load ontology graph from database or file.
    
    Args:
        domain: The domain identifier
        
    Returns:
        RDFLib Graph object
    """
    try:
        # Import models here to avoid circular imports
        from app.models.ontology import Ontology
        from app import db
        
        # Convert domain format (replace hyphens with underscores for database lookup)
        db_domain = domain.replace('-', '_')
        
        # Query the database for the ontology
        ontology = Ontology.query.filter_by(domain_id=db_domain).first()
        
        if ontology:
            # Create graph from ontology content
            g = Graph()
            g.parse(data=ontology.content, format="turtle")
            return g
        else:
            print(f"Ontology not found in database: {domain}")
            
            # Fall back to file-based ontology
            ontology_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "mcp/ontology")
            file_name = f"{db_domain}.ttl"
            ontology_path = os.path.join(ontology_dir, file_name)
            
            if os.path.exists(ontology_path):
                g = Graph()
                g.parse(ontology_path, format="turtle")
                return g
            
            print(f"Ontology file not found: {ontology_path}")
            return None
    except Exception as e:
        print(f"Error loading ontology graph: {str(e)}")
        traceback.print_exc()
        return None

def get_entity_details(graph, entity_uri):
    """
    Get detailed information about an entity from the graph.
    
    Args:
        graph: The RDFLib graph
        entity_uri: The URI of the entity
        
    Returns:
        Dictionary of entity details
    """
    if not graph:
        return None
    
    entity = URIRef(entity_uri)
    
    # Check if entity exists in graph
    if not any(graph.triples((entity, None, None))):
        return None
    
    # Get basic information
    label = graph.value(entity, RDFS.label)
    comment = graph.value(entity, RDFS.comment)
    
    # Get types
    types = []
    for t in graph.objects(entity, RDF.type):
        if isinstance(t, URIRef):
            t_label = graph.value(t, RDFS.label)
            types.append({
                "uri": str(t),
                "label": str(t_label) if t_label else str(t).split("/")[-1].replace("_", " ")
            })
    
    # Get all properties and values
    properties = []
    for p, o in graph.predicate_objects(entity):
        # Skip standard RDF/RDFS properties
        if p in [RDF.type, RDFS.label, RDFS.comment, RDFS.subClassOf]:
            continue
            
        # Get predicate label
        p_label = graph.value(p, RDFS.label)
        p_label = str(p_label) if p_label else str(p).split("/")[-1].replace("_", " ")
        
        # Format object based on type
        if isinstance(o, URIRef):
            o_label = graph.value(o, RDFS.label)
            o_formatted = {
                "uri": str(o),
                "label": str(o_label) if o_label else str(o).split("/")[-1].replace("_", " "),
                "is_literal": False
            }
        else:
            o_formatted = {
                "value": str(o),
                "datatype": str(o.datatype) if hasattr(o, 'datatype') else None,
                "is_literal": True
            }
        
        properties.append({
            "predicate": {
                "uri": str(p),
                "label": p_label
            },
            "object": o_formatted
        })
    
    return {
        "uri": entity_uri,
        "label": str(label) if label else entity_uri.split("/")[-1].split("#")[-1].replace("_", " "),
        "description": str(comment) if comment else None,
        "types": types,
        "properties": properties
    }

def get_entity_triples(graph, entity_uri):
    """
    Get all triples where the entity is either the subject or object.
    
    Args:
        graph: The RDFLib graph
        entity_uri: The URI of the entity
        
    Returns:
        A new graph containing relevant triples
    """
    if not graph:
        return None
    
    entity = URIRef(entity_uri)
    
    # Create a new graph to store the entity's triples
    entity_graph = Graph()
    
    # Add namespace bindings from the original graph
    for prefix, namespace in graph.namespaces():
        entity_graph.bind(prefix, namespace)
    
    # Add triples where entity is the subject
    for s, p, o in graph.triples((entity, None, None)):
        entity_graph.add((s, p, o))
    
    # Add triples where entity is the object
    for s, p, o in graph.triples((None, None, entity)):
        entity_graph.add((s, p, o))
    
    # For object triples, add context about the connected entity
    for s, p, o in graph.triples((None, None, entity)):
        # Add type info for the subject
        for s_type in graph.objects(s, RDF.type):
            entity_graph.add((s, RDF.type, s_type))
        
        # Add label for the subject if available
        s_label = graph.value(s, RDFS.label)
        if s_label:
            entity_graph.add((s, RDFS.label, s_label))
    
    return entity_graph

@ontology_iri_bp.route('/ontology/<path:iri_path>', methods=['GET'])
@allow_anonymous
def resolve_ontology_iri(iri_path):
    """
    Resolve an ontology IRI to return RDF data.
    
    Args:
        iri_path: Path part of the IRI
        
    Returns:
        Response with RDF data in the requested format
    """
    try:
        # Decode URL-encoded characters
        iri_path = unquote(iri_path)
        
        # Handle fragment identifier if present in URL
        fragment = request.args.get('fragment', '')
        if '#' in iri_path:
            iri_path, fragment = iri_path.split('#', 1)
        
        # Reconstruct the full IRI
        base_url = request.host_url.rstrip('/')
        full_iri = f"{base_url}/ontology/{iri_path}"
        if fragment:
            full_iri += f"#{fragment}"
        
        # Extract domain and entity ID from IRI
        domain, entity_id = extract_ontology_info(full_iri)
        
        if not domain or not entity_id:
            return jsonify({
                "error": "Invalid ontology IRI format",
                "iri": full_iri
            }), 400
        
        # Load the ontology graph
        graph = get_ontology_graph(domain)
        
        if not graph:
            return jsonify({
                "error": f"Ontology not found: {domain}",
                "iri": full_iri
            }), 404
        
        # Determine the format based on Accept header or format parameter
        format_param = request.args.get('format', '').lower()
        if format_param:
            if format_param in ['ttl', 'turtle']:
                requested_format = 'text/turtle'
            elif format_param in ['xml', 'rdfxml']:
                requested_format = 'application/rdf+xml'
            elif format_param in ['json', 'jsonld']:
                requested_format = 'application/ld+json'
            elif format_param in ['html']:
                requested_format = 'text/html'
            else:
                requested_format = 'text/turtle'  # Default to Turtle
        else:
            # Check Accept header
            accept_header = request.headers.get('Accept', '')
            if 'text/turtle' in accept_header:
                requested_format = 'text/turtle'
            elif 'application/rdf+xml' in accept_header:
                requested_format = 'application/rdf+xml'
            elif 'application/ld+json' in accept_header:
                requested_format = 'application/ld+json'
            elif 'text/html' in accept_header or 'application/xhtml+xml' in accept_header:
                requested_format = 'text/html'
            else:
                requested_format = 'text/turtle'  # Default to Turtle
        
        # Create entity URI
        entity_uri = f"http://proethica.org/ontology/{domain}#{entity_id}"
        
        # Get entity triples
        entity_graph = get_entity_triples(graph, entity_uri)
        
        if not entity_graph or len(entity_graph) == 0:
            return jsonify({
                "error": f"Entity not found: {entity_id}",
                "iri": entity_uri
            }), 404
        
        # Return the data in the requested format
        if requested_format == 'text/html':
            # Get detailed entity information
            entity_details = get_entity_details(graph, entity_uri)
            
            if not entity_details:
                return jsonify({
                    "error": f"Entity not found: {entity_id}",
                    "iri": entity_uri
                }), 404
            
            # Render HTML template
            html = render_template_string(
                HTML_TEMPLATE,
                entity_uri=entity_uri,
                entity_label=entity_details.get('label', entity_id),
                description=entity_details.get('description', ''),
                types=entity_details.get('types', []),
                properties=entity_details.get('properties', [])
            )
            return Response(html, content_type='text/html')
        
        elif requested_format == 'application/ld+json':
            jsonld = entity_graph.serialize(format='json-ld')
            return Response(jsonld, content_type='application/ld+json')
        
        elif requested_format == 'application/rdf+xml':
            rdfxml = entity_graph.serialize(format='xml')
            return Response(rdfxml, content_type='application/rdf+xml')
        
        else:  # text/turtle (default)
            turtle = entity_graph.serialize(format='turtle')
            return Response(turtle, content_type='text/turtle')
    
    except Exception as e:
        print(f"Error resolving ontology IRI: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "error": f"Failed to resolve ontology IRI: {str(e)}",
            "iri_path": iri_path
        }), 500

@ontology_iri_bp.route('/ontology/<path:domain>/<entity_id>', methods=['GET'])
@allow_anonymous
def resolve_ontology_entity(domain, entity_id):
    """
    Alternative route for ontology entities without using hash notation.
    Redirects to the hash-based IRI.
    """
    # Reconstruct the hash-based IRI and redirect
    return resolve_ontology_iri(f"{domain}#{entity_id}")
