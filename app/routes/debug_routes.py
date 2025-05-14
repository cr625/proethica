"""
Debug routes for development.
"""
from flask import Blueprint, jsonify, render_template, current_app
import sys
import os
import requests
import psycopg2
import json
from datetime import datetime

debug_bp = Blueprint('debug', __name__)

@debug_bp.route('/test-triple-preview', methods=['GET'])
def test_triple_preview():
    """
    Test route to verify the triple preview functionality.
    """
    # Generate sample triples for testing
    sample_triples = [
        {
            "subject": "http://proethica.org/engineering-ethics/concept/safety_critical_design",
            "subject_label": "Safety Critical Design",
            "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
            "predicate_label": "type",
            "object": "http://proethica.org/engineering-ethics/principle",
            "object_label": "Principle",
            "is_literal": False
        },
        {
            "subject": "http://proethica.org/engineering-ethics/concept/safety_critical_design",
            "subject_label": "Safety Critical Design",
            "predicate": "http://www.w3.org/2000/01/rdf-schema#label",
            "predicate_label": "label",
            "object": "Safety Critical Design",
            "is_literal": True
        },
        {
            "subject": "http://proethica.org/engineering-ethics/concept/safety_critical_design",
            "subject_label": "Safety Critical Design",
            "predicate": "http://purl.org/dc/elements/1.1/description",
            "predicate_label": "description",
            "object": "The practice of ensuring safety in systems where failure could cause serious harm",
            "is_literal": True
        }
    ]
    
    # Return platform info and triples
    return jsonify({
        "status": "success",
        "message": "Triple preview test route is functioning",
        "python_version": sys.version,
        "sample_triples": sample_triples,
        "triple_count": len(sample_triples)
    })

@debug_bp.route('/status', methods=['GET'])
def debug_status():
    """
    Debug route that displays system status including:
    - MCP server status
    - Database connection
    - Ontology system
    - Guidelines feature status
    """
    status_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "python_version": sys.version,
        "app_name": current_app.name,
        "debug_mode": current_app.debug,
        "system_status": {
            "mcp_server": {"status": "unknown", "detail": {}, "error": None},
            "database": {"status": "unknown", "detail": {}, "error": None},
            "ontology": {"status": "unknown", "detail": {}, "error": None},
            "guidelines": {"status": "unknown", "detail": {}, "error": None}
        }
    }
    
    # Check MCP server status
    try:
        mcp_url = os.environ.get("MCP_SERVER_URL", "http://localhost:5001")
        
        # Better JSON-RPC request for the MCP server
        response = requests.post(
            f"{mcp_url}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "list_tools",
                "params": {},
                "id": 1
            },
            timeout=5
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Debug the response
            print(f"MCP Response: {json.dumps(result, indent=2)}")
            
            if "result" in result and isinstance(result["result"], dict) and "tools" in result["result"]:
                tools = result["result"]["tools"]
                guideline_tools = [t for t in tools if "guideline" in t["name"].lower()]
                
                status_data["system_status"]["mcp_server"] = {
                    "status": "online",
                    "detail": {
                        "url": mcp_url,
                        "tool_count": len(tools),
                        "available_tools": [t["name"] for t in tools],
                        "guideline_tools_available": len(guideline_tools) > 0,
                        "guideline_tools": [t["name"] for t in guideline_tools]
                    },
                    "error": None
                }
                
                # Set ontology status based on available tools and database content
                # Check for entity tools including the specific "get_world_entities" tool
                if any("entity" in t["name"].lower() for t in tools) or any(t["name"] == "get_world_entities" for t in tools):
                    # Also check for ontologies in the database to provide more information
                    try:
                        from app.models.ontology import Ontology
                        ontologies = Ontology.query.all()
                        
                        if ontologies:
                            # For ontology status, display as "available" instead of "unknown"
                            status_data["system_status"]["ontology"] = {
                                "status": "available",
                                "detail": {
                                    "entity_tools_available": True,
                                    "entity_tools": [t["name"] for t in tools if "entity" in t["name"].lower() or t["name"] == "get_world_entities"],
                                    "ontology_count": len(ontologies),
                                    "ontologies": [
                                        {
                                            "id": o.id,
                                            "name": o.name,
                                            "source": o.source,
                                            "triple_count": len(o.content.split('\n')) if o.content else 0
                                        } 
                                        for o in ontologies[:5]  # Limit to 5 to avoid large responses
                                    ]
                                },
                                "error": None
                            }
                        else:
                            status_data["system_status"]["ontology"] = {
                                "status": "available",
                                "detail": {
                                    "entity_tools_available": True,
                                    "entity_tools": [t["name"] for t in tools if "entity" in t["name"].lower() or t["name"] == "get_world_entities"],
                                    "warning": "No ontologies found in database"
                                },
                                "error": None
                            }
                    except Exception as e:
                        # Fall back to basic information if there's an error accessing the database
                        status_data["system_status"]["ontology"] = {
                            "status": "available",
                            "detail": {
                                "entity_tools_available": True,
                                "entity_tools": [t["name"] for t in tools if "entity" in t["name"].lower() or t["name"] == "get_world_entities"],
                                "db_error": str(e)
                            },
                            "error": None
                        }
                
                # Set guidelines status based on available tools
                if guideline_tools:
                    status_data["system_status"]["guidelines"] = {
                        "status": "available",
                        "detail": {
                            "guideline_tools_available": True,
                            "guideline_tools": [t["name"] for t in guideline_tools]
                        },
                        "error": None
                    }
            else:
                status_data["system_status"]["mcp_server"] = {
                    "status": "error",
                    "detail": {"response": result},
                    "error": "Invalid response format from MCP server"
                }
        else:
            status_data["system_status"]["mcp_server"] = {
                "status": "error",
                "detail": {"status_code": response.status_code},
                "error": f"MCP server returned HTTP {response.status_code}"
            }
    except Exception as e:
        status_data["system_status"]["mcp_server"] = {
            "status": "offline",
            "detail": {},
            "error": str(e)
        }
    
    # Check database connection
    try:
        db_url = current_app.config.get("DATABASE_URL", os.environ.get("DATABASE_URL"))
        if db_url:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            
            # Get database info
            cur.execute("SELECT version();")
            db_version = cur.fetchone()[0]
            
            # Get table list
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema='public'
                ORDER BY table_name;
            """)
            tables = [row[0] for row in cur.fetchall()]
            
            # Check if worlds table exists and count worlds
            world_count = 0
            if 'worlds' in tables:
                cur.execute("SELECT COUNT(*) FROM worlds;")
                world_count = cur.fetchone()[0]
            
            # Check if guidelines table exists and count guidelines
            guideline_count = 0
            if 'documents' in tables:
                cur.execute("SELECT COUNT(*) FROM documents WHERE document_type='guideline';")
                guideline_count = cur.fetchone()[0]
            
            # Check if ontologies table exists and get ontology data even if MCP server isn't working
            if 'ontologies' in tables and status_data["system_status"]["ontology"]["status"] == "unknown":
                try:
                    from app.models.ontology import Ontology
                    ontologies = Ontology.query.all()
                    
                    if ontologies:
                        status_data["system_status"]["ontology"] = {
                            "status": "available",
                            "detail": {
                                "source": "database",
                                "ontology_count": len(ontologies),
                                "ontologies": [
                                    {
                                        "id": o.id,
                                        "name": o.name,
                                        "source": o.source,
                                        "triple_count": len(o.content.split('\n')) if o.content else 0
                                    } 
                                    for o in ontologies[:5]  # Limit to 5 to avoid large responses
                                ]
                            },
                            "error": None
                        }
                except Exception as e:
                    print(f"Error getting ontology info from database: {e}")
            
            conn.close()
            
            status_data["system_status"]["database"] = {
                "status": "connected",
                "detail": {
                    "db_version": db_version,
                    "table_count": len(tables),
                    "tables": tables,
                    "world_count": world_count,
                    "guideline_count": guideline_count
                },
                "error": None
            }
        else:
            status_data["system_status"]["database"] = {
                "status": "error",
                "detail": {},
                "error": "DATABASE_URL not configured"
            }
    except Exception as e:
        status_data["system_status"]["database"] = {
            "status": "error",
            "detail": {},
            "error": str(e)
        }
    
    # Return either JSON or HTML based on Accept header
    from flask import request
    if "application/json" in request.headers.get("Accept", ""):
        return jsonify(status_data)
    else:
        return render_template('debug/status.html', status=status_data)
