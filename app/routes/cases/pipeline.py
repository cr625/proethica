"""Pipeline view routes -- per-case extraction pipeline status dashboard."""

from flask import render_template, jsonify
from app.models import Document
from app.services.pipeline_state_manager import PipelineStateManager


def register_pipeline_routes(bp):
    """Register pipeline routes on the cases blueprint."""

    @bp.route('/<int:case_id>/pipeline')
    def case_pipeline(case_id):
        """Per-case pipeline status dashboard (read-only)."""
        case = Document.query.get_or_404(case_id)
        manager = PipelineStateManager()
        state = manager.get_pipeline_state(case_id)
        return render_template(
            'cases/pipeline.html',
            case=case,
            pipeline_state=state.to_dict(),
        )

    @bp.route('/<int:case_id>/pipeline/status')
    def case_pipeline_status(case_id):
        """API endpoint for AJAX status polling."""
        Document.query.get_or_404(case_id)
        manager = PipelineStateManager()
        state = manager.get_pipeline_state(case_id)
        return jsonify(state.to_dict())
