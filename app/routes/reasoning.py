"""
Reasoning Inspector Routes

Routes for viewing and analyzing reasoning chains captured during
ProEthica processing (scenarios, annotations, guidelines).
"""

from flask import Blueprint, render_template, request, jsonify, abort
from app.models.reasoning_trace import ReasoningTrace, ReasoningStep
from app.models.document import Document
from app.services.reasoning_inspector import get_reasoning_inspector

reasoning_bp = Blueprint('reasoning', __name__, url_prefix='/reasoning')

@reasoning_bp.route('/inspect/<int:trace_id>')
def inspect_trace(trace_id):
    """Main reasoning inspector page"""
    trace = ReasoningTrace.query.get_or_404(trace_id)
    steps = ReasoningStep.query.filter_by(trace_id=trace_id)\
                              .order_by(ReasoningStep.step_number)\
                              .all()
    
    # Convert to dictionaries for template
    steps_data = [step.to_dict() for step in steps]
    trace_data = trace.to_dict()
    
    # Get case information
    case = Document.query.get(trace.case_id) if trace.case_id else None
    
    return render_template('reasoning_inspector.html', 
                         trace=trace_data, 
                         steps=steps_data,
                         case=case)

@reasoning_bp.route('/case/<int:case_id>/traces')
def case_traces(case_id):
    """List all traces for a case"""
    case = Document.query.get_or_404(case_id)
    traces = ReasoningTrace.query.filter_by(case_id=case_id)\
                                .order_by(ReasoningTrace.started_at.desc())\
                                .all()
    
    traces_data = [trace.to_dict() for trace in traces]
    
    return render_template('case_traces.html', 
                         case=case, 
                         traces=traces_data)

@reasoning_bp.route('/api/trace/<int:trace_id>')
def api_get_trace(trace_id):
    """API endpoint for trace data"""
    inspector = get_reasoning_inspector()
    trace_data = inspector.get_trace_for_ui(trace_id)
    
    if not trace_data:
        return jsonify({'error': 'Trace not found'}), 404
    
    return jsonify(trace_data)

@reasoning_bp.route('/api/step/<int:step_id>')
def api_get_step(step_id):
    """API endpoint for individual step data"""
    step = ReasoningStep.query.get_or_404(step_id)
    
    return jsonify(step.to_dict())

@reasoning_bp.route('/api/case/<int:case_id>/traces')
def api_case_traces(case_id):
    """API endpoint for all traces for a case"""
    traces = ReasoningTrace.query.filter_by(case_id=case_id)\
                                .order_by(ReasoningTrace.started_at.desc())\
                                .all()
    
    return jsonify([trace.to_dict() for trace in traces])

@reasoning_bp.route('/test')
def test_inspector():
    """Test page to verify inspector functionality"""
    # Create a sample trace for testing
    inspector = get_reasoning_inspector()
    
    # Start a test trace
    session_id = inspector.start_trace(1, 'test')
    
    # Add some test steps
    inspector.capture_preprocessing_step(
        phase='test_preprocessing',
        original_text='Original case text with <html>tags</html>',
        processed_text='Original case text with tags',
        metadata={'html_removed': True, 'test': True}
    )
    
    inspector.capture_llm_interaction(
        phase='test_llm_call',
        prompt='Test prompt for timeline extraction',
        response='{"timeline_events": [{"id": 1, "title": "Test Event"}]}',
        parsed_result={'timeline_events': [{'id': 1, 'title': 'Test Event'}]},
        model='test-model',
        confidence_score=0.9,
        processing_time=2.5
    )
    
    inspector.capture_algorithm_step(
        phase='test_algorithm',
        input_data={'events': ['event1', 'event2']},
        output_data={'ordered_events': ['event1', 'event2']},
        processing_time=0.5,
        algorithm_name='test_ordering_algorithm'
    )
    
    # Complete trace
    completed_trace = inspector.complete_trace('completed')
    
    return jsonify({
        'message': 'Test trace created successfully',
        'trace_id': completed_trace.id,
        'session_id': completed_trace.session_id,
        'inspector_url': f'/reasoning/inspect/{completed_trace.id}'
    })
