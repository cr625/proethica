"""
Base Step - Interface for all pipeline steps.
"""
import logging

# Set up logging
logger = logging.getLogger(__name__)

class BaseStep:
    """Base class for all pipeline steps."""
    
    def __init__(self):
        self.name = self.__class__.__name__
        self.description = "Base pipeline step"
        self.version = "1.0"
        
    def process(self, input_data):
        """
        Process the input data and return results.
        Must be implemented by subclasses.
        
        Args:
            input_data: Data passed from previous step or pipeline input
            
        Returns:
            dict: Processing results
        """
        raise NotImplementedError("Subclasses must implement this method")
        
    def validate_input(self, input_data):
        """
        Validate input data before processing.
        
        Args:
            input_data: Data to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        return True
    
    def get_error_result(self, message, input_data=None):
        """
        Create a standardized error result.
        
        Args:
            message: Error message
            input_data: The input data that caused the error (optional)
            
        Returns:
            dict: Error result with status and message
        """
        result = {
            'status': 'error',
            'message': message,
            'step': self.name
        }
        
        # Include relevant parts of input data if provided
        if input_data:
            # Only include non-sensitive data
            if isinstance(input_data, dict):
                safe_input = {}
                for key, value in input_data.items():
                    # Don't include potential sensitive content
                    if key != 'content' and key != 'raw_content':
                        safe_input[key] = value
                result['input'] = safe_input
                
        return result
