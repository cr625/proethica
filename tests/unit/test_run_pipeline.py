"""Tests for scripts/run_pipeline.py -- pipeline orchestration and error handling.

Tests the PipelineError propagation, collect_sse error detection,
and step function behavior without requiring Flask or database.
"""
import json
import io
import pytest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.run_pipeline import (
    PipelineError,
    collect_sse,
    parse_sse_events,
    run_step1,
    run_step2,
    run_step3,
    run_step4,
    run_commit,
    run_reconcile,
    run_qc,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_sse_response(events):
    """Build a fake HTTP response yielding SSE data lines."""
    lines = []
    for evt in events:
        lines.append(f"data: {json.dumps(evt)}\n\n".encode())
    return lines


def make_json_response(data, status=200):
    """Build a fake HTTP response returning JSON."""
    body = json.dumps(data).encode()
    resp = MagicMock()
    resp.read.return_value = body
    resp.status = status
    return resp


def make_http_error(code, body=''):
    """Build a urllib HTTPError."""
    err = HTTPError(
        url='http://localhost:5000/test',
        code=code,
        msg=f'HTTP {code}',
        hdrs={},
        fp=io.BytesIO(body.encode()) if body else None,
    )
    return err


# ===========================================================================
# collect_sse
# ===========================================================================

class TestCollectSSE:
    """Tests for SSE event parsing and error detection."""

    def test_success_step1_complete(self):
        """Step 1/2 SSE stream ending with status='complete' returns no error."""
        events = [
            {'status': 'extracted', 'entity_type': 'roles',
             'result': {'data': {'classes': [1], 'individuals': [1, 2]}}},
            {'status': 'complete', 'summary': {'total': 3}},
        ]
        result, error = collect_sse(make_sse_response(events))
        assert error is None
        assert len(result) == 2

    def test_success_step3_complete(self):
        """Step 3 SSE stream ending with complete=True returns no error."""
        events = [
            {'progress': 50, 'messages': ['Processing...']},
            {'complete': True, 'progress': 100, 'messages': ['Done']},
        ]
        result, error = collect_sse(make_sse_response(events))
        assert error is None

    def test_success_step4_complete(self):
        """Step 4 SSE stream ending with stage='COMPLETE' returns no error."""
        events = [
            {'stage': 'PROVISIONS_DONE', 'message': '2A: 5 provisions'},
            {'stage': 'COMPLETE', 'message': 'Synthesis complete!'},
        ]
        result, error = collect_sse(make_sse_response(events))
        assert error is None

    def test_error_status_error(self):
        """SSE event with status='error' is detected."""
        events = [
            {'status': 'error', 'error': 'LLM call failed'},
        ]
        result, error = collect_sse(make_sse_response(events))
        assert error is not None
        assert 'LLM call failed' in error

    def test_error_stage_ERROR(self):
        """SSE event with stage='ERROR' is detected (Step 4 pattern)."""
        events = [
            {'stage': 'PROVISIONS_DONE', 'message': '2A done'},
            {'stage': 'ERROR', 'error': True, 'message': 'No conclusions found'},
        ]
        result, error = collect_sse(make_sse_response(events))
        assert error is not None
        assert 'No conclusions found' in error

    def test_error_field_true(self):
        """SSE event with error=True but no status/stage field is detected."""
        events = [
            {'error': True, 'message': 'Something broke'},
        ]
        result, error = collect_sse(make_sse_response(events))
        assert error is not None
        assert 'Something broke' in error

    def test_error_field_string(self):
        """SSE event with error=string (Step 3 pattern) is detected."""
        events = [
            {'error': 'Temporal extraction failed', 'progress': 0},
        ]
        result, error = collect_sse(make_sse_response(events))
        assert error is not None
        assert 'Temporal extraction failed' in error

    def test_error_messages_list(self):
        """SSE error with messages as list extracts first message."""
        events = [
            {'stage': 'ERROR', 'error': True,
             'messages': ['First error', 'Second detail']},
        ]
        result, error = collect_sse(make_sse_response(events))
        assert error is not None
        assert 'First error' in error

    def test_empty_stream(self):
        """Empty SSE stream returns no error."""
        result, error = collect_sse(make_sse_response([]))
        assert error is None
        assert len(result) == 0

    def test_malformed_json_skipped(self):
        """Non-JSON SSE lines are silently skipped by parse_sse_events."""
        lines = [
            b"data: not-json\n\n",
            b"data: {\"status\": \"complete\"}\n\n",
        ]
        events = list(parse_sse_events(lines))
        assert len(events) == 1
        assert events[0]['status'] == 'complete'


# ===========================================================================
# Step functions -- error propagation
# ===========================================================================

class TestStepErrorPropagation:
    """Each run_step* function raises PipelineError on SSE error or HTTP failure."""

    @patch('scripts.run_pipeline.http_post')
    def test_step1_raises_on_sse_error(self, mock_post):
        events = [{'status': 'error', 'error': 'extraction failed'}]
        mock_post.return_value = make_sse_response(events)
        with pytest.raises(PipelineError, match='Step 1 facts failed'):
            run_step1(999, 'facts')

    @patch('scripts.run_pipeline.http_post')
    def test_step1_raises_on_http_error(self, mock_post):
        mock_post.side_effect = make_http_error(500, '{"error": "internal"}')
        with pytest.raises(PipelineError, match='Step 1.*HTTP error'):
            run_step1(999, 'facts')

    @patch('scripts.run_pipeline.http_post')
    def test_step1_raises_on_connection_error(self, mock_post):
        mock_post.side_effect = URLError('Connection refused')
        with pytest.raises(PipelineError, match='Step 1.*HTTP error'):
            run_step1(999, 'discussion')

    @patch('scripts.run_pipeline.http_post')
    def test_step1_success(self, mock_post):
        events = [
            {'status': 'extracted', 'entity_type': 'roles',
             'result': {'data': {'classes': [1], 'individuals': [1, 2]}}},
            {'status': 'complete'},
        ]
        mock_post.return_value = make_sse_response(events)
        result = run_step1(999, 'facts')
        assert len(result) == 2

    @patch('scripts.run_pipeline.http_post')
    def test_step2_raises_on_sse_error(self, mock_post):
        events = [{'status': 'error', 'error': 'normative pass failed'}]
        mock_post.return_value = make_sse_response(events)
        with pytest.raises(PipelineError, match='Step 2 discussion failed'):
            run_step2(999, 'discussion')

    @patch('scripts.run_pipeline.http_post')
    def test_step2_raises_on_http_error(self, mock_post):
        mock_post.side_effect = make_http_error(500)
        with pytest.raises(PipelineError, match='Step 2.*HTTP error'):
            run_step2(999, 'facts')

    @patch('scripts.run_pipeline.http_get')
    def test_step3_raises_on_sse_error(self, mock_get):
        events = [{'error': 'LangGraph timeout', 'progress': 0}]
        mock_get.return_value = make_sse_response(events)
        with pytest.raises(PipelineError, match='Step 3 failed'):
            run_step3(999)

    @patch('scripts.run_pipeline.http_get')
    def test_step3_raises_on_http_error(self, mock_get):
        mock_get.side_effect = make_http_error(500)
        with pytest.raises(PipelineError, match='Step 3 HTTP error'):
            run_step3(999)

    @patch('scripts.run_pipeline.http_get')
    def test_step3_success(self, mock_get):
        events = [
            {'progress': 100, 'messages': ['Done']},
            {'complete': True, 'progress': 100},
        ]
        mock_get.return_value = make_sse_response(events)
        result = run_step3(999)
        assert len(result) == 2

    @patch('scripts.run_pipeline.http_post')
    def test_step4_raises_on_sse_error(self, mock_post):
        events = [
            {'stage': 'PROVISIONS_DONE', 'message': '2A done'},
            {'stage': 'ERROR', 'error': True, 'message': 'Phase 3 failed'},
        ]
        mock_post.return_value = make_sse_response(events)
        with pytest.raises(PipelineError, match='Step 4 failed'):
            run_step4(999)

    @patch('scripts.run_pipeline.http_post')
    def test_step4_raises_on_http_error(self, mock_post):
        mock_post.side_effect = make_http_error(500)
        with pytest.raises(PipelineError, match='Step 4 HTTP error'):
            run_step4(999)

    @patch('scripts.run_pipeline.http_post')
    def test_step4_success(self, mock_post):
        events = [
            {'stage': 'PROVISIONS_DONE', 'message': '2A: 5 provisions'},
            {'stage': 'COMPLETE', 'message': 'Synthesis complete!'},
        ]
        mock_post.return_value = make_sse_response(events)
        result = run_step4(999)
        assert len(result) == 2


# ===========================================================================
# Commit / Reconcile / QC -- error propagation
# ===========================================================================

class TestCommitErrorPropagation:
    """run_commit raises PipelineError on HTTP failure."""

    @patch('scripts.run_pipeline.http_post')
    def test_commit_success(self, mock_post):
        mock_post.return_value = make_json_response({
            'result': {'classes_committed': 10, 'individuals_committed': 50}
        })
        data = run_commit(999)
        assert data['result']['classes_committed'] == 10

    @patch('scripts.run_pipeline.http_post')
    def test_commit_raises_on_http_error(self, mock_post):
        mock_post.side_effect = make_http_error(500, '{"error": "OntServe unreachable"}')
        with pytest.raises(PipelineError, match='OntServe commit failed'):
            run_commit(999)

    @patch('scripts.run_pipeline.http_post')
    def test_commit_raises_on_http_error_no_body(self, mock_post):
        mock_post.side_effect = make_http_error(502)
        with pytest.raises(PipelineError, match='HTTP 502'):
            run_commit(999)


class TestReconcileErrorPropagation:
    """run_reconcile raises PipelineError on failure."""

    @patch('scripts.run_pipeline.http_post')
    def test_reconcile_success(self, mock_post):
        mock_post.return_value = make_json_response({
            'success': True, 'candidates': [], 'auto_merged': 0
        })
        data = run_reconcile(999)
        assert data['success'] is True

    @patch('scripts.run_pipeline.http_post')
    def test_reconcile_raises_on_success_false(self, mock_post):
        mock_post.return_value = make_json_response({
            'success': False, 'error': 'No entities to reconcile'
        })
        with pytest.raises(PipelineError, match='Reconciliation failed'):
            run_reconcile(999)

    @patch('scripts.run_pipeline.http_post')
    def test_reconcile_raises_on_http_error(self, mock_post):
        mock_post.side_effect = make_http_error(500)
        with pytest.raises(PipelineError, match='Reconciliation failed.*HTTP 500'):
            run_reconcile(999)


class TestQCErrorPropagation:
    """run_qc raises PipelineError on QC failure or HTTP error."""

    @patch('scripts.run_pipeline.http_post')
    def test_qc_pass(self, mock_post):
        mock_post.return_value = make_json_response({
            'success': True,
            'audit': {
                'overall_status': 'PASS',
                'entity_count_total': 300,
                'extraction_types_count': 16,
                'critical_count': 0, 'warning_count': 0, 'info_count': 1,
                'check_results': [
                    {'check_id': 'V7', 'status': 'INFO', 'severity': 'INFO',
                     'name': 'Count Sanity'},
                ],
            }
        })
        audit = run_qc(999)
        assert audit['overall_status'] == 'PASS'

    @patch('scripts.run_pipeline.http_post')
    def test_qc_raises_on_fail_checks(self, mock_post):
        mock_post.return_value = make_json_response({
            'success': True,
            'audit': {
                'overall_status': 'FAIL',
                'entity_count_total': 200,
                'extraction_types_count': 9,
                'critical_count': 1, 'warning_count': 0, 'info_count': 0,
                'check_results': [
                    {'check_id': 'V6', 'status': 'FAIL', 'severity': 'CRITICAL',
                     'name': 'Completeness', 'message': 'Missing 7 types'},
                ],
            }
        })
        with pytest.raises(PipelineError, match='QC FAIL.*V6'):
            run_qc(999)

    @patch('scripts.run_pipeline.http_post')
    def test_qc_raises_on_http_error(self, mock_post):
        mock_post.side_effect = make_http_error(500)
        with pytest.raises(PipelineError, match='QC audit HTTP error'):
            run_qc(999)

    @patch('scripts.run_pipeline.http_post')
    def test_qc_raises_on_api_error(self, mock_post):
        mock_post.return_value = make_json_response({
            'success': False, 'error': 'Case not found'
        })
        with pytest.raises(PipelineError, match='QC audit error.*Case not found'):
            run_qc(999)

    @patch('scripts.run_pipeline.http_post')
    def test_qc_info_does_not_raise(self, mock_post):
        """INFO-only checks (V7 out of range) do not halt the pipeline."""
        mock_post.return_value = make_json_response({
            'success': True,
            'audit': {
                'overall_status': 'PASS',
                'entity_count_total': 280,
                'extraction_types_count': 16,
                'critical_count': 0, 'warning_count': 0, 'info_count': 2,
                'check_results': [
                    {'check_id': 'V7', 'status': 'INFO', 'severity': 'INFO',
                     'name': 'Count Sanity'},
                    {'check_id': 'V1', 'status': 'INFO', 'severity': 'INFO',
                     'name': 'Duplicate Sessions'},
                ],
            }
        })
        audit = run_qc(999)
        assert audit['overall_status'] == 'PASS'

    @patch('scripts.run_pipeline.http_post')
    def test_qc_warning_does_not_raise(self, mock_post):
        """WARNING-level failures (V9 unpublished) do not halt the pipeline."""
        mock_post.return_value = make_json_response({
            'success': True,
            'audit': {
                'overall_status': 'ISSUES_FOUND',
                'entity_count_total': 280,
                'extraction_types_count': 16,
                'critical_count': 0, 'warning_count': 1, 'info_count': 0,
                'check_results': [
                    {'check_id': 'V9', 'status': 'FAIL', 'severity': 'WARNING',
                     'name': 'Publish Status', 'message': '10 unpublished'},
                ],
            }
        })
        # Should not raise -- V9 is WARNING, not CRITICAL
        audit = run_qc(999)
        assert audit['overall_status'] == 'ISSUES_FOUND'
