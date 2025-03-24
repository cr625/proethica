import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from app.services.zotero_client import ZoteroClient
from app.services.mcp_client import MCPClient

class TestZoteroClient(unittest.TestCase):
    """Test the ZoteroClient class."""
    
    def setUp(self):
        """Set up test environment."""
        # Clear singleton instances
        ZoteroClient._instance = None
        MCPClient._instance = None
        
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'ZOTERO_API_KEY': 'test_api_key',
            'ZOTERO_USER_ID': 'test_user_id'
        })
        self.env_patcher.start()
    
    def tearDown(self):
        """Clean up test environment."""
        self.env_patcher.stop()
    
    @patch('app.services.zotero_client.zotero.Zotero')
    def test_singleton_pattern(self, mock_zotero):
        """Test that ZoteroClient follows the singleton pattern."""
        # Create a mock Zotero instance
        mock_zotero_instance = MagicMock()
        mock_zotero.return_value = mock_zotero_instance
        
        # Get two instances of ZoteroClient
        client1 = ZoteroClient.get_instance()
        client2 = ZoteroClient.get_instance()
        
        # Verify they are the same instance
        self.assertIs(client1, client2)
        
        # Verify the Zotero client was initialized correctly
        mock_zotero.assert_called_once_with('test_user_id', 'user', 'test_api_key')
    
    @patch('app.services.zotero_client.zotero.Zotero')
    def test_direct_instantiation(self, mock_zotero):
        """Test that direct instantiation also returns the singleton instance."""
        # Create a mock Zotero instance
        mock_zotero_instance = MagicMock()
        mock_zotero.return_value = mock_zotero_instance
        
        # Get an instance via get_instance
        client1 = ZoteroClient.get_instance()
        
        # Get an instance via direct instantiation
        client2 = ZoteroClient()
        
        # Verify they are the same instance
        self.assertIs(client1, client2)
    
    @patch('app.services.zotero_client.zotero.Zotero')
    def test_search_items(self, mock_zotero):
        """Test the search_items method."""
        # Create a mock Zotero instance
        mock_zotero_instance = MagicMock()
        mock_zotero.return_value = mock_zotero_instance
        
        # Set up the mock to return a list of items
        mock_items = [{'data': {'title': 'Reference 1', 'creators': [{'firstName': 'John', 'lastName': 'Doe'}]}, 'key': 'ref1'}]
        mock_zotero_instance.items.return_value = mock_items
        
        # Get an instance of ZoteroClient
        client = ZoteroClient.get_instance()
        
        # Call the search_items method
        result = client.search_items('test query')
        
        # Verify the result
        self.assertEqual(result, mock_items)
        
        # Verify the Zotero client was called correctly
        mock_zotero_instance.items.assert_called_once_with(q='test query', limit=20)
    
    @patch('app.services.zotero_client.zotero.Zotero')
    @patch.dict('os.environ', {'TESTING': 'true'})
    def test_get_citation(self, mock_zotero):
        """Test the get_citation method."""
        # Create a mock Zotero instance
        mock_zotero_instance = MagicMock()
        mock_zotero.return_value = mock_zotero_instance
        
        # Set up the mock to return item data
        mock_item = {
            'data': {
                'title': 'Test Title',
                'creators': [
                    {
                        'creatorType': 'author',
                        'firstName': 'John',
                        'lastName': 'Doe'
                    }
                ],
                'date': '2023',
                'publicationTitle': 'Test Journal',
                'volume': '1',
                'issue': '1',
                'pages': '1-10'
            }
        }
        mock_zotero_instance.item.return_value = mock_item
        
        # Get an instance of ZoteroClient
        client = ZoteroClient.get_instance()
        
        # Call the get_citation method
        result = client.get_citation('ref1', 'apa')
        
        # Verify the result
        self.assertEqual(result, 'Doe J. (2023). Reference Title. Journal Name 1(1), 1-10.')
        
        # Verify the Zotero client was called correctly
        mock_zotero_instance.item.assert_called_once_with('ref1')

class TestMCPClientWithZoteroClient(unittest.TestCase):
    """Test the MCPClient class with ZoteroClient integration."""
    
    def setUp(self):
        """Set up test environment."""
        # Clear singleton instances
        ZoteroClient._instance = None
        MCPClient._instance = None
        
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'ZOTERO_API_KEY': 'test_api_key',
            'ZOTERO_USER_ID': 'test_user_id'
        })
        self.env_patcher.start()
        
        # Mock subprocess.Popen
        self.popen_patcher = patch('subprocess.Popen')
        self.mock_popen = self.popen_patcher.start()
        
        # Create a mock process
        self.mock_process = MagicMock()
        self.mock_process.poll.return_value = None
        self.mock_process.stdin = MagicMock()
        self.mock_process.stdout = MagicMock()
        self.mock_process.stderr = MagicMock()
        self.mock_popen.return_value = self.mock_process
    
    def tearDown(self):
        """Clean up test environment."""
        self.env_patcher.stop()
        self.popen_patcher.stop()
    
    @patch('app.services.zotero_client.zotero.Zotero')
    def test_mcp_client_uses_zotero_client(self, mock_zotero):
        """Test that MCPClient uses ZoteroClient for Zotero functionality."""
        # Create a mock Zotero instance
        mock_zotero_instance = MagicMock()
        mock_zotero.return_value = mock_zotero_instance
        
        # Set up the mock to return a list of items
        mock_items = [{'data': {'title': 'Search Result', 'creators': [{'firstName': 'Jane', 'lastName': 'Smith'}]}, 'key': 'ref2'}]
        mock_zotero_instance.items.return_value = mock_items
        
        # Clear singleton instances
        ZoteroClient._instance = None
        MCPClient._instance = None
        
        # Get an instance of MCPClient
        client = MCPClient.get_instance()
        
        # Call the search_zotero_items method
        result = client.search_zotero_items('test query')
        
        # Verify the result
        self.assertEqual(result, mock_items)
        
        # Verify the Zotero client was called correctly
        mock_zotero_instance.items.assert_called_once()
        args, kwargs = mock_zotero_instance.items.call_args
        self.assertEqual(kwargs.get('q'), 'test query')
        self.assertEqual(kwargs.get('limit'), 20)
    
    @patch('app.services.zotero_client.zotero.Zotero')
    def test_mcp_client_get_references_for_world(self, mock_zotero):
        """Test the get_references_for_world method."""
        # Create a mock Zotero instance
        mock_zotero_instance = MagicMock()
        mock_zotero.return_value = mock_zotero_instance
        
        # Set up the mock to return a list of items
        mock_items = [{'data': {'title': 'Reference 1', 'creators': [{'firstName': 'John', 'lastName': 'Doe'}]}, 'key': 'ref1'}]
        mock_zotero_instance.items.return_value = mock_items
        
        # Create a mock world
        mock_world = MagicMock()
        mock_world.name = 'Test World'
        mock_world.description = 'Test Description'
        mock_world.ontology_source = 'test.ttl'
        mock_world.world_metadata = {'key': 'value'}
        
        # Clear singleton instances
        ZoteroClient._instance = None
        MCPClient._instance = None
        
        # Get an instance of MCPClient
        client = MCPClient.get_instance()
        
        # Call the get_references_for_world method
        result = client.get_references_for_world(mock_world)
        
        # Verify the result
        self.assertEqual(result, mock_items)
        
        # Verify the Zotero client was called correctly
        mock_zotero_instance.items.assert_called_once()
        args, kwargs = mock_zotero_instance.items.call_args
        self.assertIn('q', kwargs)
        query = kwargs.get('q')
        self.assertIn('Test World', query)
        self.assertIn('Test Description', query)
        self.assertIn('test.ttl', query)
        self.assertIn('value', query)

if __name__ == '__main__':
    print("Testing ZoteroClient and MCPClient integration...")
    unittest.main()
