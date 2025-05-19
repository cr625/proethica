"""
Pipeline Manager - Orchestrates the execution of pipeline steps.
"""
import logging

# Set up logging
logger = logging.getLogger(__name__)

class PipelineManager:
    """Manager for executing pipeline steps."""
    
    def __init__(self):
        self.steps = {}
        self.results = {}
        
    def register_step(self, step_id, step_instance):
        """Register a step with the pipeline."""
        self.steps[step_id] = step_instance
        logger.info(f"Registered step '{step_id}': {step_instance.description}")
        
    def run_step(self, step_id, input_data):
        """
        Run a single step by ID.
        
        Args:
            step_id: Identifier for the step to run
            input_data: Input data for the step
            
        Returns:
            dict: Results from the step
        """
        if step_id not in self.steps:
            logger.error(f"Step '{step_id}' not found")
            return {
                'status': 'error',
                'message': f'Step {step_id} not found',
                'step': 'PipelineManager'
            }
            
        step = self.steps[step_id]
        logger.info(f"Running step '{step_id}': {step.description}")
        
        try:
            result = step.process(input_data)
            self.results[step_id] = result
            
            # Check for error status
            if result.get('status') == 'error':
                logger.error(f"Step '{step_id}' failed: {result.get('message')}")
            else:
                logger.info(f"Step '{step_id}' completed successfully")
                
            return result
            
        except Exception as e:
            logger.exception(f"Exception running step '{step_id}': {str(e)}")
            error_result = {
                'status': 'error',
                'message': f"Exception running step '{step_id}': {str(e)}",
                'step': step_id,
                'exception': str(e)
            }
            self.results[step_id] = error_result
            return error_result
        
    def run_pipeline(self, input_data, step_ids=None):
        """
        Run multiple steps in sequence.
        
        Args:
            input_data: Initial input data
            step_ids: List of step IDs to run (or None for all)
            
        Returns:
            dict: Results from all steps and final result
        """
        self.results = {}
        logger.info(f"Starting pipeline execution with {len(self.steps)} registered steps")
        
        # Determine which steps to run
        steps_to_run = step_ids or list(self.steps.keys())
        logger.info(f"Pipeline will run {len(steps_to_run)} steps: {', '.join(steps_to_run)}")
        
        # Initialize with input data
        current_input = input_data
        
        for step_id in steps_to_run:
            if step_id not in self.steps:
                logger.error(f"Step '{step_id}' not found")
                self.results[step_id] = {
                    'status': 'error',
                    'message': f'Step {step_id} not found',
                    'step': 'PipelineManager'
                }
                continue
                
            # Run step with current input
            result = self.run_step(step_id, current_input)
            
            # Stop pipeline if step failed
            if result.get('status') == 'error':
                logger.error(f"Pipeline execution stopped due to error in step '{step_id}'")
                break
                
            # Use this step's output as input to next step
            current_input = result
            
        logger.info(f"Pipeline execution completed with {len(self.results)} steps processed")
        
        return {
            'status': 'complete',
            'steps_run': list(self.results.keys()),
            'results': self.results,
            'final_result': current_input
        }
