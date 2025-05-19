# Case Processing Pipeline Implementation Plan

## Overview

This document outlines the plan for implementing a step-by-step case processing pipeline for the AI Ethical DM project. The pipeline will start with simple URL-based case retrieval and progressively enhance capability with more sophisticated processing steps in future iterations.

## Goals

1. Build a modular case processing pipeline that starts with URL content retrieval
2. Implement each processing step independently to allow incremental development
3. Create a system that can be extended with advanced ontology-based analysis
4. Minimize changes to the main Flask application files

## Architecture

The pipeline will follow a modular architecture with these components:

```
app/services/case_processing/
├── __init__.py
├── pipeline_steps/
│   ├── __init__.py
│   ├── base_step.py           # Base class for all pipeline steps
│   ├── url_retrieval_step.py  # Step 1: Basic URL content retrieval
│   └── [future_steps].py      # Additional steps to be added later
├── pipeline_manager.py        # Orchestrates the execution of pipeline steps
└── pipeline_result.py         # Standardized result format
```

## Implementation Phases

### Phase 1: Foundation & URL Retrieval (Current Task)

#### Components to Implement:

1. **BaseStep Interface**
   - Define common interface for all pipeline steps
   - Include step metadata (name, description, version)
   - Standardize input/output formats
   - Implement error handling and logging

2. **URLRetrievalStep Implementation**
   - Create step for fetching content from URLs
   - Implement proper validation and error handling
   - Return raw content without processing
   - Support various content types (HTML, PDF, etc.)

3. **PipelineManager**
   - Create class to manage pipeline execution
   - Support running individual steps or complete pipeline
   - Handle state management between steps
   - Implement proper error handling and recovery

4. **Pipeline Integration**
   - Create new route at `/cases/process/url` for pipeline access
   - Integrate with existing URL processing route
   - Allow specifying which steps to run
   - Return results in a standardized format

#### Technical Requirements:

- Proper input validation for URLs
- Security considerations (URL sanitization, request limits)
- Error handling for network issues and invalid responses
- Support for various content types
- Logging for debugging and analysis
- Unit tests for each component

### Phase 2: Content Extraction & Cleaning (Future)

Building on Phase 1, add steps for:
- HTML parsing and cleaning
- Main content extraction
- Noise removal (ads, navigation, etc.)
- Basic document structure identification

### Phase 3: Metadata & Structure Analysis (Future)

Extending the pipeline with:
- Metadata extraction (title, author, date)
- Document type classification
- Section identification
- Reference extraction

### Phase 4: Semantic Analysis Integration (Future)

Incorporating ontology-based analysis:
- Entity extraction using engineering ethics ontology
- McLaren's extensional definition approach
- Ethical concept mapping
- Principle instantiation identification

### Phase 5: Knowledge Integration (Future)

Final phase focusing on:
- Triple generation from extracted entities
- Integration with existing ontology
- Case similarity analysis
- Cross-case learning

## Phase 1 Implementation Details

### BaseStep Interface

```python
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
```

### URLRetrievalStep Implementation

```python
import requests
from urllib.parse import urlparse
from .base_step import BaseStep

class URLRetrievalStep(BaseStep):
    """Step for retrieving content from a URL."""
    
    def __init__(self):
        super().__init__()
        self.description = "Retrieves raw content from a URL"
        self.timeout = 30  # seconds
        
    def validate_input(self, input_data):
        """Validate URL input."""
        if not input_data or 'url' not in input_data:
            return False
            
        url = input_data['url']
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
        
    def process(self, input_data):
        """
        Retrieve content from the specified URL.
        
        Args:
            input_data: Dict containing 'url' key
            
        Returns:
            dict: Results containing status, content, and metadata
        """
        if not self.validate_input(input_data):
            return {
                'status': 'error',
                'message': 'Invalid URL input',
                'url': input_data.get('url', '')
            }
            
        url = input_data['url']
        
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            return {
                'status': 'success',
                'url': url,
                'content': response.text,
                'content_type': response.headers.get('Content-Type', ''),
                'status_code': response.status_code,
                'headers': dict(response.headers),
                'encoding': response.encoding
            }
            
        except requests.RequestException as e:
            return {
                'status': 'error',
                'url': url,
                'message': str(e),
                'error_type': e.__class__.__name__
            }
```

### PipelineManager Implementation

```python
class PipelineManager:
    """Manager for executing pipeline steps."""
    
    def __init__(self):
        self.steps = {}
        self.results = {}
        
    def register_step(self, step_id, step_instance):
        """Register a step with the pipeline."""
        self.steps[step_id] = step_instance
        
    def run_step(self, step_id, input_data):
        """Run a single step by ID."""
        if step_id not in self.steps:
            return {
                'status': 'error',
                'message': f'Step {step_id} not found'
            }
            
        step = self.steps[step_id]
        result = step.process(input_data)
        self.results[step_id] = result
        return result
        
    def run_pipeline(self, input_data, step_ids=None):
        """
        Run multiple steps in sequence.
        
        Args:
            input_data: Initial input data
            step_ids: List of step IDs to run (or None for all)
            
        Returns:
            dict: Results from all steps
        """
        self.results = {}
        
        # Determine which steps to run
        steps_to_run = step_ids or self.steps.keys()
        
        # Initialize with input data
        current_input = input_data
        
        for step_id in steps_to_run:
            if step_id not in self.steps:
                self.results[step_id] = {
                    'status': 'error',
                    'message': f'Step {step_id} not found'
                }
                continue
                
            # Run step with current input
            result = self.run_step(step_id, current_input)
            
            # Stop pipeline if step failed
            if result.get('status') == 'error':
                break
                
            # Use this step's output as input to next step
            current_input = result
            
        return {
            'status': 'complete',
            'results': self.results,
            'final_result': current_input
        }
```

### Integration with Routes

We'll integrate this with a new route in `app/routes/cases.py` (without modifying the main structure):

```python
@cases_bp.route('/process/url', methods=['POST'])
@login_required
def process_url_pipeline():
    """Process a URL through the case processing pipeline."""
    url = request.form.get('url')
    steps = request.form.get('steps', 'url_retrieval').split(',')
    
    if not url:
        return jsonify({
            'status': 'error',
            'message': 'URL is required'
        })
    
    # Initialize pipeline
    from app.services.case_processing.pipeline_manager import PipelineManager
    from app.services.case_processing.pipeline_steps.url_retrieval_step import URLRetrievalStep
    
    pipeline = PipelineManager()
    pipeline.register_step('url_retrieval', URLRetrievalStep())
    
    # Run pipeline
    result = pipeline.run_pipeline({'url': url}, steps)
    
    return jsonify(result)
```

## Testing Plan

1. **Unit Tests**
   - Test BaseStep interface validation
   - Test URLRetrievalStep with various URLs
   - Test PipelineManager with mock steps

2. **Integration Tests**
   - Test pipeline integration with Flask routes
   - Verify proper error handling
   - Test with various URL types

3. **Manual Testing**
   - Test with valid URLs from different sources
   - Test with invalid URLs and verify error handling
   - Verify content retrieval matches expected output

## Next Steps After Phase 1

1. Create comprehensive documentation
2. Design and implement content cleaning step
3. Add metadata extraction capabilities
4. Begin integration with ontology-based analysis

## Conclusion

This implementation plan provides a solid foundation for building our case processing pipeline. Starting with the URL retrieval step establishes the architecture while delivering immediate value. The modular design ensures we can extend the pipeline with more advanced capabilities in future phases.
