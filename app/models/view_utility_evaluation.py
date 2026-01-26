"""
Database models for Chapter 4 validation: View Utility Assessment.

These models implement the validation methodology from Chapter 4, which evaluates
whether structured synthesis views help evaluators understand professional ethics cases.

Unlike the comparative RTI/PBRQ/CA/DRA evaluation (ExperimentEvaluation), these models
assess the utility of individual synthesis VIEWS:
- Provisions View: Code provision mappings
- Questions View: Ethical questions structure
- Decisions View: Decision points and alternatives
- Narrative View: Timeline, profiles, relationships
"""

from datetime import datetime
from app.models import db
from sqlalchemy.dialects.postgresql import JSON


class ValidationSession(db.Model):
    """A validation session groups multiple case evaluations for one evaluator.

    Chapter 4 specifies 23 cases evaluated per participant over 2-3 hours.
    This model tracks session-level metadata and progress.
    """

    __tablename__ = 'validation_sessions'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    evaluator_id = db.Column(db.String(255), nullable=False)  # Anonymous participant ID
    evaluator_domain = db.Column(db.String(50))  # 'engineering' or 'education'

    # Session configuration
    assigned_cases = db.Column(JSON)  # List of case_ids assigned to this evaluator
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
    """Chapter 4 Component Utility Assessment.

    Evaluators rate how well each synthesis VIEW helps them understand cases.
    All utility items use 1-7 Likert scale:
        1 = Strongly Disagree
        4 = Neutral
        7 = Strongly Agree

    This replaces the comparative RTI/PBRQ/CA/DRA approach which compared
    two prediction outputs. Here we evaluate view utility independently.
    """

    __tablename__ = 'view_utility_evaluations'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('validation_sessions.id'), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    evaluator_id = db.Column(db.String(255), nullable=False)

    # =========================================================================
    # PART 1: PROVISIONS VIEW UTILITY (3 items, 1-7 Likert)
    # Chapter 4, Section 4.4.1
    # =========================================================================

    # "The code provision mapping helped me identify which professional standards apply to this case"
    prov_standards_identified = db.Column(db.Integer)

    # "The connections between provisions and case facts were clear"
    prov_connections_clear = db.Column(db.Integer)

    # "This view helped me understand the normative foundation for evaluating the case"
    prov_normative_foundation = db.Column(db.Integer)

    # =========================================================================
    # PART 1: QUESTIONS VIEW UTILITY (3 items, 1-7 Likert)
    # =========================================================================

    # "The extracted questions helped me see the ethical issues at stake"
    ques_issues_visible = db.Column(db.Integer)

    # "The structure of questions aided my understanding"
    ques_structure_aided = db.Column(db.Integer)

    # "This view helped me identify what a committee would need to deliberate"
    ques_deliberation_needs = db.Column(db.Integer)

    # =========================================================================
    # PART 1: DECISIONS VIEW UTILITY (3 items, 1-7 Likert)
    # =========================================================================

    # "The decision points helped me understand the choices the professional faced"
    decs_choices_understood = db.Column(db.Integer)

    # "The alternatives presented gave useful context for evaluation"
    decs_alternatives_context = db.Column(db.Integer)

    # "This view helped me trace how the professional's actions related to their obligations"
    decs_actions_obligations = db.Column(db.Integer)

    # =========================================================================
    # PART 1: NARRATIVE VIEW UTILITY (3 items, 1-7 Likert)
    # =========================================================================

    # "The character profiles and timeline helped me understand the situation"
    narr_situation_understood = db.Column(db.Integer)

    # "The relationship information clarified who was involved and how"
    narr_relationships_clear = db.Column(db.Integer)

    # "The sequence of events and decisions was clear"
    narr_sequence_clear = db.Column(db.Integer)

    # =========================================================================
    # PART 1: OVERALL UTILITY (3 items, 1-7 Likert)
    # =========================================================================

    # "The structured presentation helped me understand this case"
    overall_helped_understand = db.Column(db.Integer)

    # "The presentation surfaced considerations I might have missed reading only the facts"
    overall_surfaced_considerations = db.Column(db.Integer)

    # "This type of structured synthesis would be useful for professional ethics deliberation"
    overall_useful_deliberation = db.Column(db.Integer)

    # =========================================================================
    # PART 2: COMPREHENSION QUESTIONS (free text)
    # Chapter 4, Section 4.4.2 - Ground Truth Alignment
    # Collected BEFORE revealing board conclusions
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

    # Self-rating: How well did your comprehension answers align with the board's reasoning?
    # 1-7 Likert: 1 = Not at all aligned, 7 = Fully aligned
    alignment_self_rating = db.Column(db.Integer)

    # Open reflection on alignment
    alignment_reflection = db.Column(db.Text)

    # =========================================================================
    # METADATA
    # =========================================================================

    # Timestamps
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    # Time spent on each section (milliseconds)
    time_facts_review = db.Column(db.Integer)
    time_views_review = db.Column(db.Integer)
    time_utility_rating = db.Column(db.Integer)
    time_comprehension = db.Column(db.Integer)
    time_alignment = db.Column(db.Integer)

    # Store which views were actually displayed (for debugging)
    views_displayed = db.Column(JSON)  # {'provisions': True, 'questions': True, ...}

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
    def questions_view_mean(self):
        """Compute mean Questions View utility score."""
        scores = [self.ques_issues_visible, self.ques_structure_aided,
                  self.ques_deliberation_needs]
        valid = [s for s in scores if s is not None]
        return round(sum(valid) / len(valid), 2) if valid else None

    @property
    def decisions_view_mean(self):
        """Compute mean Decisions View utility score."""
        scores = [self.decs_choices_understood, self.decs_alternatives_context,
                  self.decs_actions_obligations]
        valid = [s for s in scores if s is not None]
        return round(sum(valid) / len(valid), 2) if valid else None

    @property
    def narrative_view_mean(self):
        """Compute mean Narrative View utility score."""
        scores = [self.narr_situation_understood, self.narr_relationships_clear,
                  self.narr_sequence_clear]
        valid = [s for s in scores if s is not None]
        return round(sum(valid) / len(valid), 2) if valid else None

    @property
    def overall_utility_mean(self):
        """Compute mean Overall Utility score."""
        scores = [self.overall_helped_understand, self.overall_surfaced_considerations,
                  self.overall_useful_deliberation]
        valid = [s for s in scores if s is not None]
        return round(sum(valid) / len(valid), 2) if valid else None

    @property
    def all_utility_items_complete(self):
        """Check if all 15 utility items have been rated."""
        utility_items = [
            self.prov_standards_identified, self.prov_connections_clear, self.prov_normative_foundation,
            self.ques_issues_visible, self.ques_structure_aided, self.ques_deliberation_needs,
            self.decs_choices_understood, self.decs_alternatives_context, self.decs_actions_obligations,
            self.narr_situation_understood, self.narr_relationships_clear, self.narr_sequence_clear,
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
    def is_complete(self):
        """Check if evaluation is fully complete including alignment."""
        return (self.all_utility_items_complete and
                self.comprehension_complete and
                self.alignment_self_rating is not None)

    def __repr__(self):
        return f"<ViewUtilityEvaluation {self.id}: case {self.case_id} by {self.evaluator_id}>"


class RetrospectiveReflection(db.Model):
    """Post-study reflection on view utility across all evaluated cases.

    Chapter 4, Section 4.3.2 Part 3: Retrospective Reflection
    Completed after evaluating all assigned cases.
    """

    __tablename__ = 'retrospective_reflections'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('validation_sessions.id'),
                           nullable=False, unique=True)
    evaluator_id = db.Column(db.String(255), nullable=False)
    evaluator_domain = db.Column(db.String(50))

    # =========================================================================
    # VIEW RANKING (1=most valuable, 4=least valuable)
    # Chapter 4, Section 4.4.3
    # =========================================================================

    rank_provisions_view = db.Column(db.Integer)  # Rank 1-4
    rank_questions_view = db.Column(db.Integer)   # Rank 1-4
    rank_decisions_view = db.Column(db.Integer)   # Rank 1-4
    rank_narrative_view = db.Column(db.Integer)   # Rank 1-4

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
        """Check if rankings are valid (each rank 1-4 used exactly once)."""
        ranks = [self.rank_provisions_view, self.rank_questions_view,
                 self.rank_decisions_view, self.rank_narrative_view]
        if any(r is None for r in ranks):
            return False
        return sorted(ranks) == [1, 2, 3, 4]

    @property
    def is_complete(self):
        """Check if retrospective is fully complete."""
        return (self.rankings_valid and
                self.surfaced_missed_considerations is not None)

    def __repr__(self):
        return f"<RetrospectiveReflection {self.id}: {self.evaluator_id}>"
