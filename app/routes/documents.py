"""
Routes for document management, including upload, search, and retrieval.
"""

import os
from flask import Blueprint, request, jsonify, current_app, send_file
from werkzeug.utils import secure_filename
import logging

from app import db
from app.models import Document, DocumentChunk, PROCESSING_STATUS
from app.models.world import World
from app.services.embedding_service import EmbeddingService

# Set up logging
logger = logging.getLogger(__name__)

# Create blueprints
documents_bp = Blueprint('api_documents', __name__, url_prefix='/api/documents')
documents_web_bp = Blueprint('documents', __name__, url_prefix='/documents')

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Configure allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt', 'html', 'htm'}

def allowed_file(filename):
    """Check if a file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@documents_bp.route('', methods=['POST'])
def upload_document():
    """Upload a document and process it for embeddings."""
    try:
        # Check if file is provided
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        
        if not file or not allowed_file(file.filename):
            return jsonify({"error": f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"}), 400
        
        # Get form data
        title = request.form.get('title')
        document_type = request.form.get('document_type')
        world_id = request.form.get('world_id')
        source = request.form.get('source')
        
        # Validate required fields
        if not title:
            return jsonify({"error": "Title is required"}), 400
        
        if not document_type:
            return jsonify({"error": "Document type is required"}), 400
        
        # Validate world_id if provided
        if world_id:
            world = World.query.get(world_id)
            if not world:
                return jsonify({"error": f"World with ID {world_id} not found"}), 404
        
        # Save file
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        
        # Get file type
        file_type = filename.rsplit('.', 1)[1].lower()
        
        # Create document record
        document = Document(
            title=title,
            document_type=document_type,
            world_id=world_id,
            source=source,
            file_path=file_path,
            file_type=file_type,
            doc_metadata={}  # Initialize with empty metadata
        )
        
        db.session.add(document)
        db.session.commit()
        
        # Process document in background (in a real application, this would be a Celery task)
        # For now, we'll process it synchronously
        embedding_service = EmbeddingService()
        embedding_service.process_document(document.id)
        
        return jsonify({
            "message": "Document uploaded and processed successfully",
            "document_id": document.id,
            "title": document.title
        }), 201
    
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        return jsonify({"error": str(e)}), 500

@documents_bp.route('', methods=['GET'])
def get_documents():
    """Get all documents, optionally filtered by world_id or document_type."""
    try:
        world_id = request.args.get('world_id')
        document_type = request.args.get('document_type')
        
        query = Document.query
        
        if world_id:
            query = query.filter_by(world_id=world_id)
        
        if document_type:
            query = query.filter_by(document_type=document_type)
        
        documents = query.all()
        
        result = []
        for doc in documents:
            result.append({
                "id": doc.id,
                "title": doc.title,
                "document_type": doc.document_type,
                "source": doc.source,
                "world_id": doc.world_id,
                "file_type": doc.file_type,
                "created_at": doc.created_at.isoformat() if doc.created_at else None
            })
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error getting documents: {str(e)}")
        return jsonify({"error": str(e)}), 500

@documents_bp.route('/<int:document_id>', methods=['GET'])
def get_document(document_id):
    """Get a specific document by ID."""
    try:
        document = Document.query.get_or_404(document_id)
        
        return jsonify({
            "id": document.id,
            "title": document.title,
            "document_type": document.document_type,
            "source": document.source,
            "world_id": document.world_id,
            "file_type": document.file_type,
            "file_path": document.file_path,
            "content": document.content,
            "metadata": document.doc_metadata,
            "created_at": document.created_at.isoformat() if document.created_at else None,
            "updated_at": document.updated_at.isoformat() if document.updated_at else None
        })
    
    except Exception as e:
        logger.error(f"Error getting document {document_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@documents_bp.route('/<int:document_id>/download', methods=['GET'])
def download_document(document_id):
    """Download the original document file."""
    try:
        document = Document.query.get_or_404(document_id)
        
        if not document.file_path or not os.path.exists(document.file_path):
            return jsonify({"error": "Document file not found"}), 404
        
        return send_file(document.file_path, as_attachment=True, download_name=os.path.basename(document.file_path))
    
    except Exception as e:
        logger.error(f"Error downloading document {document_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@documents_bp.route('/<int:document_id>', methods=['DELETE'])
def delete_document(document_id):
    """Delete a document by ID."""
    try:
        document = Document.query.get_or_404(document_id)
        
        # Delete the file if it exists
        if document.file_path and os.path.exists(document.file_path):
            os.remove(document.file_path)
        
        db.session.delete(document)
        db.session.commit()
        
        return jsonify({"message": f"Document {document_id} deleted successfully"})
    
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@documents_bp.route('/search', methods=['POST'])
def search_documents():
    """Search for documents using vector similarity."""
    try:
        data = request.json
        
        if not data or 'query' not in data:
            return jsonify({"error": "Query is required"}), 400
        
        query = data['query']
        world_id = data.get('world_id')
        document_type = data.get('document_type')
        limit = data.get('limit', 5)
        
        # Create filter criteria
        filter_criteria = {}
        if world_id:
            filter_criteria['world_id'] = world_id
        if document_type:
            filter_criteria['document_type'] = document_type
        
        # Get embedding service
        embedding_service = EmbeddingService()
        
        # Search for similar chunks
        results = embedding_service.search_similar_chunks(query, k=limit, world_id=world_id, document_type=document_type)
        
        return jsonify(results)
    
    except Exception as e:
        logger.error(f"Error searching documents: {str(e)}")
        return jsonify({"error": str(e)}), 500

@documents_bp.route('/process-url', methods=['POST'])
def process_url():
    """Process a URL for embeddings."""
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        url = data.get('url')
        title = data.get('title')
        document_type = data.get('document_type')
        world_id = data.get('world_id')
        
        if not url:
            return jsonify({"error": "URL is required"}), 400
        
        if not title:
            return jsonify({"error": "Title is required"}), 400
        
        if not document_type:
            return jsonify({"error": "Document type is required"}), 400
        
        # Validate world_id if provided
        if world_id:
            world = World.query.get(world_id)
            if not world:
                return jsonify({"error": f"World with ID {world_id} not found"}), 404
        
        # Process URL
        embedding_service = EmbeddingService()
        document_id = embedding_service.process_url(url, title, document_type, world_id)
        
        return jsonify({
            "message": "URL processed successfully",
            "document_id": document_id,
            "title": title
        }), 201
    
    except Exception as e:
        logger.error(f"Error processing URL: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Web routes for documents
@documents_web_bp.route('/download/<int:document_id>', methods=['GET'])
def download_document_web(document_id):
    """Web route to download a document."""
    try:
        document = Document.query.get_or_404(document_id)
        
        if not document.file_path or not os.path.exists(document.file_path):
            return jsonify({"error": "Document file not found"}), 404
        
        return send_file(document.file_path, as_attachment=True, download_name=os.path.basename(document.file_path))
    
    except Exception as e:
        logger.error(f"Error downloading document {document_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@documents_web_bp.route('/status/<int:document_id>', methods=['GET'])
def document_status(document_id):
    """Get the processing status of a document."""
    try:
        document = Document.query.get_or_404(document_id)
        
        # Check if document has content but status is still processing
        if document.content and document.processing_status == PROCESSING_STATUS['PROCESSING']:
            # Update status to completed if content exists but status is still processing
            document.processing_status = PROCESSING_STATUS['COMPLETED']
            document.processing_progress = 100
            document.processing_phase = 'completed'
            db.session.commit()
            logger.info(f"Auto-corrected document {document_id} status to completed based on content presence")
        
        # Calculate estimated time remaining based on progress
        estimated_time = None
        if document.processing_status == PROCESSING_STATUS['PROCESSING']:
            # Rough estimate: 2 minutes for a full process, scaled by remaining progress
            remaining_progress = 100 - (document.processing_progress or 0)
            estimated_time = int((remaining_progress / 100) * 120)  # seconds
        
        return jsonify({
            "id": document.id,
            "status": document.processing_status,
            "phase": document.processing_phase,
            "progress": document.processing_progress or 0,
            "estimated_time": estimated_time,  # in seconds
            "error": document.processing_error,
            "has_content": bool(document.content)
        })
    
    except Exception as e:
        logger.error(f"Error getting document status {document_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500
