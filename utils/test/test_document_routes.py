"""
Tests for the document management routes.
"""

import json
import pytest
from unittest.mock import patch
from io import BytesIO
from datetime import datetime
from app.models.document import Document, PROCESSING_STATUS


def test_get_documents(client, create_test_world, create_test_scenario):
    """Test listing all documents."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Create a test document
    document = Document(
        title="Test Document",
        document_type="guideline",
        world_id=world.id,
        file_path="uploads/test.pdf",
        file_type="application/pdf",
        content="A test document content",
        processing_status=PROCESSING_STATUS['PENDING'],
        doc_metadata={"author": "Test Author"}
    )
    
    from app import db
    db.session.add(document)
    db.session.commit()
    
    # Send request
    response = client.get('/documents/')
    
    # Verify response
    assert response.status_code == 200
    assert b'Test Document' in response.data


def test_get_document(client, create_test_world, create_test_scenario):
    """Test getting a specific document."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Create a test document
    document = Document(
        title="Test Document",
        document_type="guideline",
        world_id=world.id,
        file_path="uploads/test.pdf",
        file_type="application/pdf",
        content="A test document content",
        processing_status=PROCESSING_STATUS['PENDING'],
        doc_metadata={"author": "Test Author"}
    )
    
    from app import db
    db.session.add(document)
    db.session.commit()
    
    # Send request
    response = client.get(f'/documents/{document.id}')
    
    # Verify response
    assert response.status_code == 200
    assert b'Test Document' in response.data
    assert b'A test document content' in response.data


def test_create_document(client, auth_client, create_test_world, create_test_scenario):
    """Test creating a new document."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Create a mock file
    file_data = BytesIO(b"Test file content")
    file_data.name = "test.pdf"
    
    # Set up a mock for saving the file
    with patch('app.routes.documents.secure_filename', return_value='test.pdf'):
        with patch('app.routes.documents.os.path.join', return_value='/tmp/test.pdf'):
            with patch('app.routes.documents.os.makedirs'):
                with patch('werkzeug.datastructures.FileStorage.save') as mock_save:
                    # Send request (using auth_client as document uploads require authentication)
                    response = auth_client.post(
                        '/documents/',
                        data={
                            'title': 'New Document',
                            'document_type': 'guideline',
                            'world_id': world.id,
                            'file': (file_data, 'test.pdf')
                        },
                        content_type='multipart/form-data',
                        follow_redirects=True
                    )
                    
                    # Verify the file was saved
                    mock_save.assert_called_once()
    
    # Verify response
    assert response.status_code == 200
    assert b'Document created successfully' in response.data
    
    # Verify document was created in the database
    from app.models.document import Document
    document = Document.query.filter_by(title='New Document').first()
    assert document is not None
    assert document.document_type == 'guideline'
    assert document.world_id == world.id
    assert document.processing_status == PROCESSING_STATUS['PENDING']


def test_update_document(client, auth_client, create_test_world, create_test_scenario):
    """Test updating a document."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Create a test document
    document = Document(
        title="Test Document",
        document_type="guideline",
        world_id=world.id,
        file_path="uploads/test.pdf",
        file_type="application/pdf",
        content="A test document content",
        processing_status=PROCESSING_STATUS['PENDING'],
        doc_metadata={"author": "Test Author"}
    )
    
    from app import db
    db.session.add(document)
    db.session.commit()
    
    # Send request
    response = auth_client.post(
        f'/documents/{document.id}/update',
        data={
            'title': 'Updated Document',
            'content': 'An updated test document content',
            'processing_status': PROCESSING_STATUS['COMPLETED']
        },
        follow_redirects=True
    )
    
    # Verify response
    assert response.status_code == 200
    assert b'Document updated successfully' in response.data
    
    # Verify document was updated in the database
    document = Document.query.get(document.id)
    assert document.title == 'Updated Document'
    assert document.content == 'An updated test document content'
    assert document.processing_status == PROCESSING_STATUS['COMPLETED']


def test_delete_document(client, auth_client, create_test_world, create_test_scenario):
    """Test deleting a document."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Create a test document
    document = Document(
        title="Test Document",
        document_type="guideline",
        world_id=world.id,
        file_path="uploads/test.pdf",
        file_type="application/pdf",
        content="A test document content",
        processing_status=PROCESSING_STATUS['PENDING'],
        doc_metadata={"author": "Test Author"}
    )
    
    from app import db
    db.session.add(document)
    db.session.commit()
    
    # Set up a mock for deleting the file
    with patch('app.routes.documents.os.remove'):
        # Send request
        response = auth_client.post(
            f'/documents/{document.id}/delete',
            follow_redirects=True
        )
        
    # Verify response
    assert response.status_code == 200
    assert b'Document deleted successfully' in response.data
    
    # Verify document was deleted from the database
    document = Document.query.get(document.id)
    assert document is None


def test_api_get_documents(client, create_test_world, create_test_scenario):
    """Test the API endpoint to get all documents."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Create a test document
    document = Document(
        title="Test Document",
        document_type="guideline",
        world_id=world.id,
        file_path="uploads/test.pdf",
        file_type="application/pdf",
        content="A test document content",
        processing_status=PROCESSING_STATUS['PENDING'],
        doc_metadata={"author": "Test Author"}
    )
    
    from app import db
    db.session.add(document)
    db.session.commit()
    
    # Send request
    response = client.get('/documents/api')
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert len(data['data']) == 1
    assert data['data'][0]['title'] == 'Test Document'


def test_api_get_document(client, create_test_world, create_test_scenario):
    """Test the API endpoint to get a specific document by ID."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Create a test document
    document = Document(
        title="Test Document",
        document_type="guideline",
        world_id=world.id,
        file_path="uploads/test.pdf",
        file_type="application/pdf",
        content="A test document content",
        processing_status=PROCESSING_STATUS['PENDING'],
        doc_metadata={"author": "Test Author"}
    )
    
    from app import db
    db.session.add(document)
    db.session.commit()
    
    # Send request
    response = client.get(f'/documents/api/{document.id}')
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['data']['title'] == 'Test Document'
    assert data['data']['content'] == 'A test document content'


def test_api_get_document_status(client, create_test_world, create_test_scenario):
    """Test the API endpoint to get a document's status."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Create a test document
    document = Document(
        title="Test Document",
        document_type="guideline",
        world_id=world.id,
        file_path="uploads/test.pdf",
        file_type="application/pdf",
        content="A test document content",
        processing_status=PROCESSING_STATUS['PENDING'],
        doc_metadata={"author": "Test Author"},
        processing_progress=0
    )
    
    from app import db
    db.session.add(document)
    db.session.commit()
    
    # Send request
    response = client.get(f'/documents/api/{document.id}/status')
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['data']['status'] == PROCESSING_STATUS['PENDING']
    assert data['data']['progress'] == 0


def test_api_update_document_status(client, create_test_world, create_test_scenario):
    """Test the API endpoint to update a document's status."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Create a test document
    document = Document(
        title="Test Document",
        document_type="guideline",
        world_id=world.id,
        file_path="uploads/test.pdf",
        file_type="application/pdf",
        content="A test document content",
        processing_status=PROCESSING_STATUS['PENDING'],
        doc_metadata={"author": "Test Author"},
        processing_progress=0
    )
    
    from app import db
    db.session.add(document)
    db.session.commit()
    
    # Send request
    response = client.post(
        f'/documents/api/{document.id}/status',
        json={
            'status': PROCESSING_STATUS['PROCESSING'],
            'progress': 50
        }
    )
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    
    # Verify document status was updated
    document = Document.query.get(document.id)
    assert document.processing_status == PROCESSING_STATUS['PROCESSING']
    assert document.processing_progress == 50
