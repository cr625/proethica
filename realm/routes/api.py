"""
REALM API Routes.

This module defines the API routes for the REALM application.
"""

import logging
from flask import Blueprint, jsonify, request, session, current_app

# Import services
from realm.services import material_service

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
api_bp = Blueprint('api', __name__)

@api_bp.route('/materials/search', methods=['GET'])
def search_materials():
    """Search for materials.
    
    Query Parameters:
        q: Search query
        limit: Maximum number of results (default: 20)
    """
    query = request.args.get('q', '')
    limit = int(request.args.get('limit', 20))
    
    if not query:
        return jsonify({
            "error": "Missing query parameter",
            "message": "Please provide a search query"
        }), 400
    
    try:
        materials = material_service.search_materials(query, limit=limit)
        
        # Convert to dict for JSON serialization
        material_dicts = [material.to_dict() for material in materials]
        
        return jsonify({
            "query": query,
            "count": len(material_dicts),
            "materials": material_dicts
        })
    except Exception as e:
        logger.error(f"Error searching materials: {e}")
        return jsonify({
            "error": "Search Error",
            "message": str(e)
        }), 500

@api_bp.route('/materials/<path:uri>', methods=['GET'])
def get_material(uri):
    """Get details for a specific material.
    
    Path Parameters:
        uri: URI of the material
    """
    try:
        material = material_service.get_material(uri)
        
        if not material:
            return jsonify({
                "error": "Not Found",
                "message": f"Material not found: {uri}"
            }), 404
        
        return jsonify(material.to_dict())
    except Exception as e:
        logger.error(f"Error getting material: {e}")
        return jsonify({
            "error": "Material Error",
            "message": str(e)
        }), 500

@api_bp.route('/categories', methods=['GET'])
def get_categories():
    """Get a list of material categories."""
    try:
        categories = material_service.get_categories()
        
        return jsonify({
            "count": len(categories),
            "categories": categories
        })
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        return jsonify({
            "error": "Category Error",
            "message": str(e)
        }), 500

@api_bp.route('/materials/compare', methods=['GET'])
def compare_materials():
    """Compare two materials.
    
    Query Parameters:
        uri1: URI of the first material
        uri2: URI of the second material
    """
    uri1 = request.args.get('uri1', '')
    uri2 = request.args.get('uri2', '')
    
    if not uri1 or not uri2:
        return jsonify({
            "error": "Missing Parameter",
            "message": "Please provide two material URIs (uri1 and uri2)"
        }), 400
    
    try:
        comparison = material_service.compare_materials(uri1, uri2)
        
        return jsonify(comparison)
    except Exception as e:
        logger.error(f"Error comparing materials: {e}")
        return jsonify({
            "error": "Comparison Error",
            "message": str(e)
        }), 500

@api_bp.route('/chat', methods=['POST'])
def chat():
    """Chat with the MSEO-enhanced LLM.
    
    Request Body:
        message: User message
        clear_history: (Optional) Whether to clear the conversation history
    """
    # Parse request
    data = request.get_json()
    
    if not data or 'message' not in data:
        return jsonify({
            "error": "Missing Parameter",
            "message": "Please provide a message"
        }), 400
    
    # Get user message
    user_message = data['message']
    
    # Check if should clear history
    if data.get('clear_history', False):
        session['chat_history'] = []
    
    # Get conversation history
    history = session.get('chat_history', [])
    
    try:
        # Add user message to history
        history.append({"role": "user", "content": user_message})
        
        # Get response from service
        response = material_service.chat_about_materials(user_message, history)
        
        # Add assistant response to history
        history.append({"role": "assistant", "content": response})
        
        # Update session
        session['chat_history'] = history
        
        return jsonify({
            "message": response,
            "history": history
        })
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        return jsonify({
            "error": "Chat Error",
            "message": str(e)
        }), 500

@api_bp.route('/health', methods=['GET'])
def health_check():
    """API health check endpoint."""
    return jsonify({
        "status": "ok",
        "version": "1.0.0"
    })
