"""Shared constants, participant-code helpers, session-creation helpers, and the retrospective ranking-views metadata used across study route groups."""
import hashlib
import logging
import os
import random
import secrets
import uuid
from datetime import datetime
from flask import Blueprint, request, render_template, redirect, url_for, flash, session, jsonify
from flask_wtf.csrf import CSRFError
from app import db
from app.models import Document
from app.models.view_utility_evaluation import (
    ValidationSession, ViewUtilityEvaluation, RetrospectiveReflection
)
from app.services.validation.synthesis_view_builder import SynthesisViewBuilder
from app.services.validation.case_assignment_service import assign_cases
from app.services.validation.likert_items import (
    NARR_ITEMS, TIMELINE_ITEMS, QC_ITEMS, DECS_ITEMS, PROV_ITEMS, OVERALL_ITEMS,
)

logger = logging.getLogger(__name__)


INFO_SHEET_VERSION = 'v2.2'                  # Drexel-student senior-design channel (HRP-506)
INFO_SHEET_VERSION_PROLIFIC = 'v3-prolific'  # Prolific adult-population channel (HRP-506b)

# Ambiguity-stripped alphabet for participant codes (no 0/O, 1/I, L).
CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
CODE_LENGTH = 8

# Prolific URL parameter names. Prolific's External Study integration injects
# these via {{%PROLIFIC_PID%}}, {{%STUDY_ID%}}, {{%SESSION_ID%}} substitution.
PROLIFIC_PARAMS = ('prolific_pid', 'study_id', 'session_id')

# Prolific submission-completion URL pattern. Participants are redirected here
# after they finish; the `cc` param is the fixed completion code registered in
# the Prolific study config (env: PROLIFIC_COMPLETION_CODE_SUCCESS).
PROLIFIC_COMPLETION_URL_BASE = 'https://app.prolific.com/submissions/complete'


def generate_participant_code() -> str:
    """Random 8-character alphanumeric code. No crosswalk to identity."""
    return ''.join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def generate_completion_code() -> str:
    """Random 8-character completion code, distinct from the participant code.

    Crowdsourcing platforms reject a study that prints the participant code
    as the completion proof. The completion code is generated only at the
    moment the participant finishes (on retrospective submission) and is
    what they paste into Prolific.
    """
    return ''.join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def hash_prolific_pid(pid: str) -> str:
    """SHA-256 hex of a Prolific PID, for duplicate-enrollment detection.

    The plain PID is never persisted. Only the hash is stored, and only on
    the validation_sessions row.
    """
    return hashlib.sha256(pid.encode('utf-8')).hexdigest()


def get_participant_code() -> str | None:
    """Read code from query string or session. Returns None if unknown."""
    code = request.args.get('code', '').strip().upper()
    if code:
        session['participant_code'] = code
        return code
    return session.get('participant_code')


def load_session(code: str) -> ValidationSession | None:
    """Fetch a session by participant code, or None if the code is bogus."""
    if not code:
        return None
    return ValidationSession.query.filter_by(participant_code=code).first()


def capture_prolific_params() -> dict | None:
    """Read Prolific URL parameters from the request and stash them in the
    Flask session so they survive the consent submit.

    Returns the captured dict, or None if no Prolific PID is present. Once
    captured, subsequent requests can read them out of `session` without
    relying on the URL.
    """
    pid = request.args.get('prolific_pid', '').strip()
    if not pid:
        return None
    payload = {
        'prolific_pid': pid,
        'study_id': request.args.get('study_id', '').strip(),
        'session_id': request.args.get('session_id', '').strip(),
    }
    session['prolific'] = payload
    return payload


def get_stashed_prolific() -> dict | None:
    """Return the stashed Prolific params dict, or None."""
    return session.get('prolific')


def create_session(
    domain: str = 'engineering',
    recruitment_source: str = 'drexel_student',
    prolific_pid_hash: str | None = None,
    info_sheet_version: str = INFO_SHEET_VERSION,
) -> ValidationSession:
    """Create a new study session with a fresh random code.

    Consent must have been acknowledged before this is called; the caller is
    responsible for setting `consent_acknowledged_at` and `info_sheet_version`.
    """
    code = generate_participant_code()
    # Vanishingly small collision probability, but belt-and-suspenders:
    while ValidationSession.query.filter_by(participant_code=code).first() is not None:
        code = generate_participant_code()

    assigned = assign_cases(code)

    new_session = ValidationSession(
        session_id=str(uuid.uuid4())[:8],
        evaluator_id=code,
        participant_code=code,
        evaluator_domain=domain,
        recruitment_source=recruitment_source,
        prolific_pid_hash=prolific_pid_hash,
        assigned_cases=assigned,
        completed_cases=[],
        consent_acknowledged_at=datetime.utcnow(),
        info_sheet_version=info_sheet_version,
    )
    db.session.add(new_session)
    db.session.commit()
    session['participant_code'] = code
    return new_session


def create_preview_consent_session(
    domain: str = 'engineering',
    prolific_pid_hash: str | None = None,
) -> ValidationSession:
    """Create a session for an advisor walking consent -> case -> completion.

    Companion to create_session for the /preview/start?show=consent path.
    Each call produces a fresh session tagged recruitment_source='preview'
    (excluded from study analysis) with exactly one case assigned (case 7
    by default), so multiple advisors can share the same URL without
    picking up each other's state. The Prolific PID stashed upstream by
    the consent-mode preview route is unique per visit, so no two preview
    enrollments collide on prolific_pid_hash even though the duplicate-
    enrollment check is skipped here.
    """
    code = generate_participant_code()
    while ValidationSession.query.filter_by(participant_code=code).first() is not None:
        code = generate_participant_code()

    from app.services.validation.synthesis_view_builder import SynthesisViewBuilder
    view_builder = SynthesisViewBuilder()
    evaluable_cases = view_builder.get_evaluable_cases()
    preferred_case_id = 7
    if any(c['id'] == preferred_case_id for c in evaluable_cases):
        case_id = preferred_case_id
    elif evaluable_cases:
        case_id = evaluable_cases[0]['id']
    else:
        case_id = preferred_case_id  # last-resort fallback

    new_session = ValidationSession(
        session_id=str(uuid.uuid4())[:8],
        evaluator_id=code,
        participant_code=code,
        evaluator_domain=domain,
        recruitment_source='preview',
        prolific_pid_hash=prolific_pid_hash,
        assigned_cases=[case_id],
        completed_cases=[],
        consent_acknowledged_at=datetime.utcnow(),
        info_sheet_version=INFO_SHEET_VERSION_PROLIFIC,
    )
    db.session.add(new_session)
    db.session.commit()
    session['participant_code'] = code
    return new_session


def _require_session():
    """Resolve and return the current session, or a redirect response."""
    code = get_participant_code()
    if not code:
        flash('Please enroll or enter your participant code to continue.', 'warning')
        return None, redirect(url_for('study.index'))
    val_session = load_session(code)
    if not val_session:
        flash(f'No study session found for code {code}.', 'warning')
        session.pop('participant_code', None)
        return None, redirect(url_for('study.index'))
    return val_session, None


_RANKING_VIEWS = [
    {
        'slug': 'narrative',
        'name': 'Narrative View',
        'icon_class': 'bi bi-journal-text',
        'icon_color_class': 'text-success',
        'icon_style': '',
        'description': 'Characters with ethical tensions and opening states',
    },
    {
        'slug': 'timeline',
        'name': 'Timeline View',
        'icon_class': 'bi bi-clock-history',
        'icon_color_class': '',
        'icon_style': 'color: #20c997;',
        'description': 'Actions and events in temporal sequence with nested decision points',
    },
    {
        'slug': 'qc',
        'name': 'Conclusions View',
        'icon_class': 'bi bi-question-circle',
        'icon_color_class': '',
        'icon_style': 'color: #6f42c1;',
        'description': "Each board question paired with the Board’s ruling, plus analytical questions for additional perspective.",
    },
    {
        'slug': 'decisions',
        'name': 'Decisions View',
        'icon_class': 'bi bi-signpost-split',
        'icon_color_class': '',
        'icon_style': 'color: #fd7e14;',
        'description': 'Decision points with arguments for and against each option',
    },
    {
        'slug': 'provisions',
        'name': 'Provisions View',
        'icon_class': 'bi bi-book',
        'icon_color_class': 'text-primary',
        'icon_style': '',
        'description': 'Code provisions mapped to case elements',
    },
]
