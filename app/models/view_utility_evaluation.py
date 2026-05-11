"""
Database models for the ProEthica user-study (IRB Protocol 2603011709).

Implements the study design described in
`docs-internal/study/EvaluationStudyPlan.md` (Appendix A utility rating items,
Appendix B comprehension questions). Evaluates perceived utility of five
synthesis views produced by the ProEthica pipeline:

- Provisions View: Code provision mappings
- Q&C View: Ethical questions linked to conclusions with emergence/resolution overlays
- Decisions View: Decision points with Toulmin argumentative structure
- Timeline View: Actions/Events in temporal sequence with nested decision points
- Narrative View: Characters with ethical tensions and opening states

Per Appendix A, each view is rated with 3 seven-point Likert items; 3 overall
items complete the 18-item utility instrument. Retrospective Reflection
collects a 5-view ranking and open-ended feedback.

Schema level: v6 (2026-04-16).
"""

from datetime import datetime
from app.models import db
from sqlalchemy.dialects.postgresql import JSON


class ValidationSession(db.Model):
    """A study session groups 3-4 case evaluations for one participant.

    Between-subjects design: each participant reviews 3-4 cases drawn from the
    23-case pool (`app.config.study_case_pool.STUDY_CASE_POOL_IDS`). Tracks
    consent acknowledgement, random participant code, and completion progress.
    """

    __tablename__ = 'validation_sessions'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    evaluator_id = db.Column(db.String(255), nullable=False)  # Anonymous participant ID (kept for compatibility; mirrors participant_code)
    evaluator_domain = db.Column(db.String(50))  # 'engineering' only in IRB scope; column kept for schema stability

    # Participant code: displayed to the participant, re-enterable on return.
    # Random alphanumeric; no crosswalk to identity.
    participant_code = db.Column(db.String(16), unique=True, index=True)

    # Completion code: distinct from participant_code. Generated at completed_at
    # and shown on the Thank You page for the participant to paste into the
    # crowdsourcing platform's completion field. Crowd platforms reject a study
    # that prints the participant code as the completion proof.
    completion_code = db.Column(db.String(16), unique=True, index=True)

    # Recruitment channel tag. 'drexel_student' is the original senior-design
    # channel under Protocol 2603011709; 'prolific_engineering_trained' is the
    # paid Prolific panel pre-screened for engineering background, added by
    # IRB amendment (validation pivot, week of 2026-04-28).
    recruitment_source = db.Column(db.String(50), nullable=False, default='drexel_student')

    # SHA-256 hex of the Prolific PID, stored only for duplicate-enrollment
    # detection. Plain PID is never persisted. NULL for the Drexel-student
    # channel.
    prolific_pid_hash = db.Column(db.String(64), unique=True, index=True)

    # Layout cohort marker (see .claude/plans/inline-utility-ratings.md).
    # 'inline_v1'     = post-2026-05 layout (Likert footer per view tab).
    # 'sequential_v1' = pre-2026-05 layout (consolidated post-views block).
    # Defaults to inline_v1 for new sessions; pre-deploy completed sessions
    # are backfilled to sequential_v1 by migrate_study_schema_v8.sql.
    layout_version = db.Column(
        db.String(20), nullable=False, default='inline_v1', server_default='inline_v1'
    )

    # Consent gate (HRP-506 Information Sheet acknowledgement)
    consent_acknowledged_at = db.Column(db.DateTime)
    info_sheet_version = db.Column(db.String(20))

    # Orientation gate (post-consent onboarding screen). NULL means the
    # participant has not yet completed orientation and should be redirected
    # to /validation/orientation. Set to NOW() on form submission. Legacy
    # rows are backfilled by migrate_study_schema_v10.sql so returning
    # participants skip the new screen. See
    # .claude/plans/participant-onboarding-redesign.md.
    orientation_completed_at = db.Column(db.DateTime)

    # Post-task demographics (4-6 closed-form items captured between alignment
    # and complete). All categorical or ordinal; no free text. Lets Chapter 4
    # describe the realised sample and run Prolific-only / Drexel-only subsets.
    highest_engineering_degree = db.Column(db.String(50))
    years_engineering_experience = db.Column(db.String(20))
    role_category = db.Column(db.String(50))
    nspe_pe_familiarity = db.Column(db.Integer)  # 1-5 Likert
    prior_ethics_course = db.Column(db.Boolean)
    demographics_completed_at = db.Column(db.DateTime)

    # Session configuration
    assigned_cases = db.Column(JSON)  # List of case_ids assigned to this participant
    completed_cases = db.Column(JSON, default=list)  # List of completed case_ids

    # Timestamps
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    evaluations = db.relationship('ViewUtilityEvaluation', back_populates='session',
                                  cascade='all, delete-orphan')
    retrospective = db.relationship('RetrospectiveReflection', back_populates='session',
                                    uselist=False, cascade='all, delete-orphan')

    @property
    def progress_percent(self):
        """Calculate completion percentage."""
        if not self.assigned_cases:
            return 0
        completed = len(self.completed_cases) if self.completed_cases else 0
        return round((completed / len(self.assigned_cases)) * 100)

    @property
    def is_complete(self):
        """Check if all assigned cases have been evaluated."""
        if not self.assigned_cases:
            return False
        completed = self.completed_cases or []
        return len(completed) >= len(self.assigned_cases)

    def __repr__(self):
        return f"<ValidationSession {self.session_id}: {self.evaluator_id}>"


class ViewUtilityEvaluation(db.Model):
    """Per-case utility ratings and comprehension responses.

    18-item utility instrument (3 per view x 5 views + 3 overall) plus 4
    comprehension free-text responses, 1 alignment self-rating, and 1
    alignment reflection. All Likert items use a 1-7 scale:
        1 = Strongly Disagree
        4 = Neutral
        7 = Strongly Agree

    Item wording is authoritative in `docs-internal/study/EvaluationStudyPlan.md`
    Appendix A.

    Note: `overall_surfaced_considerations` is a REVERSE-CODED item ("I could
    have reached the same understanding from the case facts alone"). The
    `overall_utility_mean` property applies the 8 - x reverse before averaging.
    """

    __tablename__ = 'view_utility_evaluations'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('validation_sessions.id'), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    evaluator_id = db.Column(db.String(255), nullable=False)

    # =========================================================================
    # PART 1: PROVISIONS VIEW UTILITY (3 items, 1-7 Likert)
    # =========================================================================

    # "The code provision mapping helped me identify which professional standards apply to this case."
    prov_standards_identified = db.Column(db.Integer)

    # "The connections between provisions and case facts were clear."
    prov_connections_clear = db.Column(db.Integer)

    # "This view helped me understand the ethical basis for evaluating the case."
    prov_normative_foundation = db.Column(db.Integer)

    # =========================================================================
    # PART 1: Q&C VIEW UTILITY (3 items, 1-7 Likert)
    # =========================================================================

    # "The extracted questions helped me see the ethical issues at stake."
    qc_issues_visible = db.Column(db.Integer)

    # "The connections between questions and conclusions clarified how the board reached its findings."
    qc_emergence_resolution = db.Column(db.Integer)

    # "This view helped me identify what questions an ethics review would need to address."
    qc_deliberation_needs = db.Column(db.Integer)

    # =========================================================================
    # PART 1: DECISIONS VIEW UTILITY (3 items, 1-7 Likert)
    # =========================================================================

    # "The decision points helped me understand the choices the professional faced."
    decs_choices_understood = db.Column(db.Integer)

    # "The arguments for and against each option helped me evaluate the choices that were made."
    decs_argumentative_structure = db.Column(db.Integer)

    # "This view helped me trace how the professional's actions related to their obligations."
    decs_actions_obligations = db.Column(db.Integer)

    # =========================================================================
    # PART 1: TIMELINE VIEW UTILITY (3 items, 1-7 Likert)
    # =========================================================================

    # "The temporal sequence of events helped me understand how the situation developed."
    timeline_temporal_sequence = db.Column(db.Integer)

    # "The causal links between events clarified why certain actions raised ethical concerns."
    timeline_causal_links = db.Column(db.Integer)

    # "This view helped me identify when obligations were activated or violated."
    timeline_obligation_activation = db.Column(db.Integer)

    # =========================================================================
    # PART 1: NARRATIVE VIEW UTILITY (3 items, 1-7 Likert)
    # =========================================================================

    # "The character profiles and ethical tensions helped me understand who was affected and why."
    narr_characters_tensions = db.Column(db.Integer)

    # "The relationship information clarified the professional dynamics in the case."
    narr_relationships_clear = db.Column(db.Integer)

    # "This view provided a useful overview of the ethical significance of the case."
    narr_ethical_significance = db.Column(db.Integer)

    # =========================================================================
    # PART 1: OVERALL UTILITY (3 items, 1-7 Likert)
    # =========================================================================

    # "The structured presentation helped me understand this case."
    overall_helped_understand = db.Column(db.Integer)

    # REVERSE-CODED: "I could have reached the same understanding from the case facts alone."
    # The stored value is the raw response; the mean property applies 8 - x before averaging.
    overall_surfaced_considerations = db.Column(db.Integer)

    # "This type of structured synthesis would be useful for professional ethics deliberation."
    overall_useful_deliberation = db.Column(db.Integer)

    # =========================================================================
    # PART 2: COMPREHENSION QUESTIONS (free text)
    # Appendix B - collected BEFORE revealing board conclusions
    # =========================================================================

    # "What were the main ethical tensions in this case?"
    comp_main_tensions = db.Column(db.Text)

    # "Which code provisions are most relevant?"
    comp_relevant_provisions = db.Column(db.Text)

    # "What decision points did the professional face?"
    comp_decision_points = db.Column(db.Text)

    # "What factors would be most important for a committee deliberating this case?"
    comp_deliberation_factors = db.Column(db.Text)

    # =========================================================================
    # PART 2: ALIGNMENT SELF-ASSESSMENT (after revealing conclusions)
    # =========================================================================
    # NOTE (2026-05-10): Steps 3-5 reorganized. Comprehension questions
    # (the four comp_* columns above) and the alignment_* fields are
    # retained for back-compat with sessions started before the reorg
    # but are no longer collected from new participants. The current
    # post-views flow uses the refl_* columns below: an open Reflection
    # step (Step 3) and a Wrap-up step (Step 4) that shows the BER
    # conclusions and one final reflection prompt. is_complete no longer
    # requires comprehension or alignment.

    # Self-rating: How well did your comprehension answers align with the board's reasoning?
    # 1-7 Likert: 1 = Not at all aligned, 7 = Fully aligned
    alignment_self_rating = db.Column(db.Integer)

    # Open reflection on alignment
    alignment_reflection = db.Column(db.Text)

    # =========================================================================
    # PART 2': REFLECTION (replaces comprehension+alignment under the
    # design-utility framing introduced 2026-05-10). All optional.
    # =========================================================================

    # Step 3 — Reflection
    refl_most_useful_view = db.Column(db.Text)   # which view was most useful, why
    refl_changes = db.Column(db.Text)            # what would you change about any view

    # Step 4 — Wrap-up (after BER conclusions are shown)
    refl_final = db.Column(db.Text)              # any final thoughts after seeing the actual ruling

    # =========================================================================
    # METADATA
    # =========================================================================

    # Timestamps
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    # Time spent on each section (milliseconds)
    time_facts_review = db.Column(db.Integer)
    time_views_review = db.Column(db.Integer)
    time_timeline_review = db.Column(db.Integer)
    time_utility_rating = db.Column(db.Integer)
    time_comprehension = db.Column(db.Integer)
    time_alignment = db.Column(db.Integer)

    # Per-view tab dwell time (milliseconds) under the inline-layout flow.
    # Recorded by case_evaluation.html from Bootstrap shown.bs.tab /
    # hidden.bs.tab events. The existing time_views_review remains the
    # sum-of-tabs aggregate used by the low_effort_flag floor check.
    time_view_narrative = db.Column(db.Integer)
    time_view_timeline = db.Column(db.Integer)
    time_view_qc = db.Column(db.Integer)
    time_view_decisions = db.Column(db.Integer)
    time_view_provisions = db.Column(db.Integer)

    # Attention check (plan §4.4): single instructed-response item embedded
    # among the utility items. 1-7 Likert; pass = 1 ("Strongly Disagree").
    # Stored raw; pass/fail computed at analysis time.
    attention_check_response = db.Column(db.Integer)

    # Time-on-task floor flag (plan §4.5): set by a server-side check after
    # submit if time_facts_review + time_views_review + time_comprehension is
    # below the calibrated floor. NULL until the check has run; True flags a
    # case for analyst review (not auto-rejected, per Prolific policy).
    low_effort_flag = db.Column(db.Boolean)

    # Store which views were actually displayed (for debugging)
    views_displayed = db.Column(JSON)  # {'provisions': True, 'qc': True, 'decisions': True, 'timeline': True, 'narrative': True}

    # Additional metadata
    meta_info = db.Column(JSON)

    # =========================================================================
    # RELATIONSHIPS
    # =========================================================================

    session = db.relationship('ValidationSession', back_populates='evaluations')
    document = db.relationship('Document', backref=db.backref('view_utility_evaluations',
                                                               cascade='all, delete-orphan'))

    # =========================================================================
    # COMPUTED PROPERTIES
    # =========================================================================

    @property
    def provisions_view_mean(self):
        """Compute mean Provisions View utility score."""
        scores = [self.prov_standards_identified, self.prov_connections_clear,
                  self.prov_normative_foundation]
        valid = [s for s in scores if s is not None]
        return round(sum(valid) / len(valid), 2) if valid else None

    @property
    def qc_view_mean(self):
        """Compute mean Q&C View utility score."""
        scores = [self.qc_issues_visible, self.qc_emergence_resolution,
                  self.qc_deliberation_needs]
        valid = [s for s in scores if s is not None]
        return round(sum(valid) / len(valid), 2) if valid else None

    @property
    def decisions_view_mean(self):
        """Compute mean Decisions View utility score."""
        scores = [self.decs_choices_understood, self.decs_argumentative_structure,
                  self.decs_actions_obligations]
        valid = [s for s in scores if s is not None]
        return round(sum(valid) / len(valid), 2) if valid else None

    @property
    def timeline_view_mean(self):
        """Compute mean Timeline View utility score."""
        scores = [self.timeline_temporal_sequence, self.timeline_causal_links,
                  self.timeline_obligation_activation]
        valid = [s for s in scores if s is not None]
        return round(sum(valid) / len(valid), 2) if valid else None

    @property
    def narrative_view_mean(self):
        """Compute mean Narrative View utility score."""
        scores = [self.narr_characters_tensions, self.narr_relationships_clear,
                  self.narr_ethical_significance]
        valid = [s for s in scores if s is not None]
        return round(sum(valid) / len(valid), 2) if valid else None

    @property
    def overall_utility_mean(self):
        """Compute mean Overall Utility score, reverse-coding item 2.

        `overall_surfaced_considerations` is reverse-coded ("I could have
        reached the same understanding from the case facts alone"), so its
        raw score is mapped to 8 - x before inclusion in the mean.
        """
        items = []
        if self.overall_helped_understand is not None:
            items.append(self.overall_helped_understand)
        if self.overall_surfaced_considerations is not None:
            items.append(8 - self.overall_surfaced_considerations)  # reverse-coded
        if self.overall_useful_deliberation is not None:
            items.append(self.overall_useful_deliberation)
        return round(sum(items) / len(items), 2) if items else None

    @property
    def all_utility_items_complete(self):
        """Check if all 18 utility items have been rated."""
        utility_items = [
            self.prov_standards_identified, self.prov_connections_clear, self.prov_normative_foundation,
            self.qc_issues_visible, self.qc_emergence_resolution, self.qc_deliberation_needs,
            self.decs_choices_understood, self.decs_argumentative_structure, self.decs_actions_obligations,
            self.timeline_temporal_sequence, self.timeline_causal_links, self.timeline_obligation_activation,
            self.narr_characters_tensions, self.narr_relationships_clear, self.narr_ethical_significance,
            self.overall_helped_understand, self.overall_surfaced_considerations, self.overall_useful_deliberation
        ]
        return all(item is not None for item in utility_items)

    @property
    def comprehension_complete(self):
        """Check if all comprehension questions have been answered."""
        questions = [
            self.comp_main_tensions, self.comp_relevant_provisions,
            self.comp_decision_points, self.comp_deliberation_factors
        ]
        return all(q is not None and len(q.strip()) > 0 for q in questions if q)

    @property
    def view_ratings_complete(self):
        """The 15 per-view utility items (excludes the 3 Overall items).

        Used as the gate for advancing past Step 2 (Views) into Step 3
        (Reflection). The Overall items live on Step 3 under the
        post-2026-05-10 reorg, so the Step 3 entry condition is "all
        five views rated"; the all-18 condition gates Step 4 (Wrap-up).
        """
        items = [
            self.prov_standards_identified, self.prov_connections_clear, self.prov_normative_foundation,
            self.qc_issues_visible, self.qc_emergence_resolution, self.qc_deliberation_needs,
            self.decs_choices_understood, self.decs_argumentative_structure, self.decs_actions_obligations,
            self.timeline_temporal_sequence, self.timeline_causal_links, self.timeline_obligation_activation,
            self.narr_characters_tensions, self.narr_relationships_clear, self.narr_ethical_significance,
        ]
        return all(item is not None for item in items)

    @property
    def is_complete(self):
        """Check if evaluation is fully complete.

        2026-05-10 reorg: completion now requires only the 18 utility
        items. The Reflection (Step 3) and Wrap-up (Step 4) prompts are
        all optional under the design-utility framing — the participant
        is rating view structure, not demonstrating case mastery, so
        empty reflection text is not a failure mode. The legacy
        comprehension_complete and alignment_self_rating gates are no
        longer enforced (the columns remain on the model for back-compat).
        """
        return self.all_utility_items_complete

    def __repr__(self):
        return f"<ViewUtilityEvaluation {self.id}: case {self.case_id} by {self.evaluator_id}>"


class RetrospectiveReflection(db.Model):
    """Post-study reflection on view utility across all evaluated cases.

    EvaluationStudyPlan.md Part 3 - completed after evaluating all assigned
    cases. Rankings are over the five IRB-approved views.
    """

    __tablename__ = 'retrospective_reflections'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('validation_sessions.id'),
                           nullable=False, unique=True)
    evaluator_id = db.Column(db.String(255), nullable=False)
    evaluator_domain = db.Column(db.String(50))

    # =========================================================================
    # VIEW RANKING (1=most valuable, 5=least valuable)
    # =========================================================================

    rank_provisions_view = db.Column(db.Integer)  # Rank 1-5
    rank_qc_view = db.Column(db.Integer)          # Rank 1-5
    rank_decisions_view = db.Column(db.Integer)   # Rank 1-5
    rank_timeline_view = db.Column(db.Integer)    # Rank 1-5
    rank_narrative_view = db.Column(db.Integer)   # Rank 1-5

    # =========================================================================
    # SURFACED CONSIDERATIONS
    # "Did the structured presentation surface considerations you might have missed?"
    # =========================================================================

    surfaced_missed_considerations = db.Column(db.Boolean)
    surfaced_considerations_text = db.Column(db.Text)  # If yes, describe what

    # =========================================================================
    # OPEN-ENDED FEEDBACK
    # =========================================================================

    # "What information or structure was missing that would have helped your analysis?"
    missing_elements = db.Column(db.Text)

    # "What changes would make this type of synthesis more useful?"
    improvement_suggestions = db.Column(db.Text)

    # General comments
    general_comments = db.Column(db.Text)

    # =========================================================================
    # TIMESTAMPS
    # =========================================================================

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # =========================================================================
    # RELATIONSHIPS
    # =========================================================================

    session = db.relationship('ValidationSession', back_populates='retrospective')

    # =========================================================================
    # COMPUTED PROPERTIES
    # =========================================================================

    @property
    def rankings_valid(self):
        """Check if rankings are valid (each rank 1-5 used exactly once)."""
        ranks = [self.rank_provisions_view, self.rank_qc_view,
                 self.rank_decisions_view, self.rank_timeline_view,
                 self.rank_narrative_view]
        if any(r is None for r in ranks):
            return False
        return sorted(ranks) == [1, 2, 3, 4, 5]

    @property
    def is_complete(self):
        """Check if retrospective is fully complete.

        Completion is defined by a valid 1-5 ranking permutation only.
        Predecessor commit 1da9d93 made surfaced_missed_considerations
        truly optional at submit time (matching the consent language
        "you may select Prefer not to say on any item"); requiring it
        here would mark legitimate optional-skip submissions incomplete
        and re-surface the "Continue to view ranking" dashboard CTA
        after the participant had already finished the page.
        """
        return self.rankings_valid

    def __repr__(self):
        return f"<RetrospectiveReflection {self.id}: {self.evaluator_id}>"
