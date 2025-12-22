"""
Base Classes for Synthesis Pipeline

Provides common infrastructure for all synthesis phases.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SynthesisEvent:
    """A progress event for SSE streaming."""
    stage: str
    progress: int
    messages: List[str]
    result: Optional[Dict[str, Any]] = None
    error: bool = False
    prompt: Optional[str] = None
    raw_llm_response: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        data = {
            'stage': self.stage,
            'progress': self.progress,
            'messages': self.messages
        }
        if self.result:
            data['result'] = self.result
        if self.error:
            data['error'] = True
        if self.prompt:
            data['prompt'] = self.prompt
        if self.raw_llm_response:
            data['raw_llm_response'] = self.raw_llm_response
        return data


@dataclass
class SynthesisResult:
    """Base result class for synthesis phases."""
    case_id: int
    success: bool = True
    error_message: Optional[str] = None
    extraction_session_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    llm_traces: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            'case_id': self.case_id,
            'success': self.success,
            'error_message': self.error_message,
            'extraction_session_id': self.extraction_session_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'llm_traces_count': len(self.llm_traces)
        }


class BaseSynthesizer:
    """
    Base class for synthesis phases.

    Subclasses implement:
    - extract_streaming(): Generator that yields SynthesisEvents
    - extract(): Non-streaming extraction (calls streaming and consumes events)
    """

    def __init__(self, case_id: int, llm_client=None):
        self.case_id = case_id
        self.llm_client = llm_client
        self._result = None

    def extract_streaming(self) -> Generator[SynthesisEvent, None, None]:
        """
        Execute extraction with streaming progress events.

        Yields:
            SynthesisEvent objects for each stage of extraction
        """
        raise NotImplementedError("Subclasses must implement extract_streaming()")

    def extract(self) -> SynthesisResult:
        """
        Execute extraction and return final result.

        Consumes all streaming events to get final result.
        """
        for event in self.extract_streaming():
            pass  # Consume all events
        return self._result

    def _emit(
        self,
        stage: str,
        progress: int,
        messages: List[str],
        result: Optional[Dict[str, Any]] = None,
        error: bool = False,
        prompt: Optional[str] = None,
        raw_llm_response: Optional[str] = None
    ) -> SynthesisEvent:
        """Helper to create and log a synthesis event."""
        event = SynthesisEvent(
            stage=stage,
            progress=progress,
            messages=messages,
            result=result,
            error=error,
            prompt=prompt,
            raw_llm_response=raw_llm_response
        )
        if error:
            logger.error(f"[{stage}] {messages}")
        else:
            logger.info(f"[{stage}] {messages[0] if messages else 'Progress'}")
        return event
