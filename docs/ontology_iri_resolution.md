# Ontology IRI Resolution

This document explains the implementation of dereferenceable IRIs for ProEthica ontologies, allowing direct access to RDF entities via HTTP.

## Overview

The system now supports resolution of ontology IRIs in the format `http://proethica.org/ontology/{domain}#{entity_id}` to retrieve the RDF triples associated with a specific entity. This implementation follows linked data principles, allowing semantic web clients to directly navigate the ontology structure.

## Features

- **Content Negotiation**: The endpoint supports different RDF serialization formats based on the HTTP Accept header or format parameter:
  - Turtle (text/turtle) - Default format
  - RDF/XML (application/rdf+xml)
  - JSON-LD (application/ld+json)
  - HTML (text/html) - Human-readable representation

- **Entity Context**: When retrieving an entity, the system returns not only the triples where the entity is the subject but also triples where it's the object, providing a more complete context.

- **Database Priority**: The system first attempts to load ontologies from the database, falling back to file-based ontologies if necessary.

- **Human-readable HTML**: For browser access, a formatted HTML view displays entity details in a user-friendly format with property tables and navigation links.

## Usage Examples

### Direct IRI Access

Accessing an IRI directly:

```
http://proethica.org/ontology/engineering-ethics#ProjectEngineerRole
```

This will return RDF data in Turtle format by default.

### Format Selection via URL Parameter

To request a specific format, append the `format` parameter:

```
http://proethica.org/ontology/engineering-ethics#ProjectEngineerRole?format=json
http://proethica.org/ontology/engineering-ethics#ProjectEngineerRole?format=xml
http://proethica.org/ontology/engineering-ethics#ProjectEngineerRole?format=ttl
http://proethica.org/ontology/engineering-ethics#ProjectEngineerRole?format=html
```

### Format Selection via Accept Header

Clients can also specify the preferred format using the HTTP Accept header:

```
Accept: text/turtle
Accept: application/rdf+xml
Accept: application/ld+json
Accept: text/html
```

## Implementation Details

### Routes

Two main routes handle IRI resolution:

1. `/ontology/<path:iri_path>` - Handles IRI paths, extracting domain and fragment identifiers.
2. `/ontology/<path:domain>/<entity_id>` - Alternative route without hash notation, for more URL-friendly access.

### Data Extraction Process

When an IRI is requested:

1. The system extracts the domain and entity ID from the IRI.
2. It loads the ontology graph from the database (or falls back to file).
3. It extracts relevant triples for the entity.
4. Based on the requested format, it serializes the data appropriately.
5. For HTML format, it also extracts detailed entity information and renders a human-friendly template.

### Production Deployment

For this feature to work in production:

1. **Nginx Configuration**: The web server should be configured to proxy requests for `http://proethica.org/ontology/*` to the Flask application.

Example Nginx configuration snippet:

```nginx
server {
    server_name proethica.org;
    
    # Regular application routes
    location / {
        proxy_pass http://localhost:5000;
        # other proxy settings...
    }
    
    # Ensure ontology path is handled by the application
    location /ontology/ {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        # other proxy settings...
    }
}
```

2. **DNS Configuration**: Ensure the domain `proethica.org` resolves to your server.

## Benefits

- **Semantic Web Integration**: Ontologies are now fully accessible via standard semantic web protocols.
- **Machine Readability**: Other systems can automatically consume and navigate the ontology structure.
- **Human Exploration**: Researchers can explore the ontology through a browser with the HTML representation.
- **Standards Compliance**: Implementation follows linked data best practices for IRI dereferencing.
