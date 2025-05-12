"""
Configuration settings for the NSPE case processing pipeline
"""

import os
import json
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Ontology paths
ONTOLOGY_DIR = os.path.join(os.path.dirname(BASE_DIR), "ontologies")
ENGINEERING_ETHICS_ONTOLOGY = os.path.join(ONTOLOGY_DIR, "engineering-ethics.ttl")
PROETHICA_ONTOLOGY = os.path.join(ONTOLOGY_DIR, "proethica-intermediate.ttl")
BFO_ONTOLOGY = os.path.join(ONTOLOGY_DIR, "bfo.ttl")
MCLAREN_ONTOLOGY = os.path.join(ONTOLOGY_DIR, "mclaren-extensional-definitions.ttl")

# Database connection parameters
DB_PARAMS = {
    "dbname": "ai_ethical_dm",
    "user": "postgres",
    "password": "PASS",
    "host": "localhost",
    "port": "5433"
}

# RDF namespace URIs
NAMESPACE_URIS = {
    "proethica": "http://proethica.org/ontology/",
    "engineering-ethics": "http://proethica.org/ontology/engineering-ethics#",
    "intermediate": "http://proethica.org/ontology/intermediate#",
    "mclaren": "http://proethica.org/ontology/mclaren-extensional#",
    "bfo": "http://purl.obolibrary.org/obo/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#"
}

# RDF type predicate URI
RDF_TYPE_PREDICATE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

# Case detail properties
CASE_SECTION_MARKERS = [
    "Facts:",
    "Question:",
    "References:",
    "Discussion:",
    "Conclusion:"
]

# NSPE website settings
NSPE_BASE_URL = "https://www.nspe.org"
NSPE_CASE_PATTERN = r"BER Case ([0-9\-]+)"
NSPE_CASE_TIMEOUT = 30  # Seconds

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Load custom config if it exists
CUSTOM_CONFIG_PATH = os.path.join(BASE_DIR, "custom_config.json")
if os.path.exists(CUSTOM_CONFIG_PATH):
    with open(CUSTOM_CONFIG_PATH, "r") as f:
        custom_config = json.load(f)
        # Update globals with custom config
        globals().update(custom_config)
