"""
Shared concept extraction service.

Single entry point for all extraction paths (individual buttons, streaming
full pass, automated pipeline). Wraps UnifiedDualExtractor + store_extraction_result()
into one function that all callers use.
"""
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)

# Retry configuration (consolidated from step1_enhanced.py / step2_enhanced.py)
RETRY_ATTEMPTS = 3
RETRY_MIN_WAIT = 2   # seconds
RETRY_MAX_WAIT = 10  # seconds

EXTRACTION_PASS_LABELS = {
    1: 'contextual_framework',
    2: 'normative_requirements',
    3: 'temporal_dynamics',
}


class ExtractionTimeoutError(Exception):
    """Raised on LLM timeout/connection errors to trigger retry."""
    pass


@dataclass
class ExtractionResult:
    """Result of a single concept extraction."""
    concept_type: str
    classes: list = field(default_factory=list)
    individuals: list = field(default_factory=list)
    prompt_text: Optional[str] = None
    raw_response: Optional[str] = None
    model_name: str = ''
    session_id: str = ''
    extraction_time: float = 0.0
    success: bool = False
    error: Optional[str] = None
    injection_mode: str = 'full'
    tool_call_log: list = field(default_factory=list)


def extract_concept(
    case_text: str,
    case_id: int,
    concept_type: str,
    section_type: str = 'facts',
    step_number: int = 1,
    session_id: Optional[str] = None,
    injection_mode: str = 'full',
) -> ExtractionResult:
    """
    Extract a single concept from case text and store results.

    This is the single function all extraction paths call.
    Cross-concept context injection (Step 2 dependencies) is handled
    internally by UnifiedDualExtractor.

    Args:
        case_text: The text to extract from.
        case_id: Case database ID.
        concept_type: e.g. roles, states, resources, principles, etc.
        section_type: 'facts' or 'discussion'.
        step_number: Pipeline step (1, 2, or 3).
        session_id: Optional UUID; generated if not provided.

    Returns:
        ExtractionResult with classes, individuals, prompt, response, timing.
    """
    from app.services.extraction.unified_dual_extractor import UnifiedDualExtractor
    from app.services.extraction.extraction_graph import store_extraction_result

    session_id = session_id or str(uuid.uuid4())
    extraction_pass = EXTRACTION_PASS_LABELS.get(step_number, f'step{step_number}')

    start = time.time()

    extractor = UnifiedDualExtractor(concept_type, injection_mode=injection_mode)
    classes, individuals = extractor.extract(
        case_text=case_text,
        case_id=case_id,
        section_type=section_type,
    )

    store_extraction_result(
        case_id=case_id,
        concept_type=concept_type,
        step_number=step_number,
        section_type=section_type,
        session_id=session_id,
        extractor=extractor,
        classes=classes,
        individuals=individuals,
        pass_number=step_number,
        extraction_pass=extraction_pass,
    )

    return ExtractionResult(
        concept_type=concept_type,
        classes=classes,
        individuals=individuals,
        prompt_text=extractor.last_prompt,
        raw_response=extractor.last_raw_response,
        model_name=extractor.model_name,
        session_id=session_id,
        extraction_time=time.time() - start,
        success=True,
        injection_mode=extractor.injection_mode,
        tool_call_log=extractor.tool_call_log,
    )


def get_injection_mode() -> str:
    """Get the current injection mode from Flask config or environment.

    Priority: Flask app.config > environment variable > default ('full').
    The pipeline runner sets this via /pipeline/api/set_injection_mode.
    """
    try:
        from flask import current_app
        mode = current_app.config.get('INJECTION_MODE')
        if mode:
            return mode
    except (ImportError, RuntimeError):
        pass
    import os
    return os.environ.get('PROETHICA_INJECTION_MODE', 'full')


def extract_concept_with_retry(
    case_text: str,
    case_id: int,
    concept_type: str,
    section_type: str = 'facts',
    step_number: int = 1,
    session_id: Optional[str] = None,
    injection_mode: Optional[str] = None,
) -> ExtractionResult:
    """
    Extract with tenacity retry on timeout/connection errors.

    Wraps extract_concept() with exponential backoff for transient LLM
    failures. Non-transient errors propagate immediately.
    """
    mode = injection_mode or get_injection_mode()

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        retry=retry_if_exception_type((ExtractionTimeoutError, ConnectionError)),
    )
    def _inner():
        try:
            return extract_concept(
                case_text=case_text,
                case_id=case_id,
                concept_type=concept_type,
                section_type=section_type,
                step_number=step_number,
                session_id=session_id,
                injection_mode=mode,
            )
        except Exception as e:
            error_str = str(e).lower()
            if 'timeout' in error_str or 'connection' in error_str:
                logger.warning(f"Transient extraction error for {concept_type}, retrying: {e}")
                raise ExtractionTimeoutError(str(e)) from e
            raise

    return _inner()
