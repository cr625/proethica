-- scripts/migrate_study_schema_v6.sql
-- Align study schema with IRB-approved five-view design (18 items, 5 ranks).
-- IRB Protocol 2603011709 — see docs-internal/study/EvaluationStudyPlan.md.
--
-- Run: PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm \
--        -f scripts/migrate_study_schema_v6.sql
--
-- Rollback: scripts/migrate_study_schema_v6_rollback.sql

BEGIN;

-- ---------------------------------------------------------------------
-- view_utility_evaluations: Questions -> Q&C
-- ---------------------------------------------------------------------
ALTER TABLE view_utility_evaluations
  RENAME COLUMN ques_issues_visible TO qc_issues_visible;
ALTER TABLE view_utility_evaluations
  RENAME COLUMN ques_deliberation_needs TO qc_deliberation_needs;
ALTER TABLE view_utility_evaluations
  DROP COLUMN ques_structure_aided;
ALTER TABLE view_utility_evaluations
  ADD COLUMN qc_emergence_resolution INTEGER;

-- ---------------------------------------------------------------------
-- view_utility_evaluations: Decisions item 2 rewording
-- ---------------------------------------------------------------------
ALTER TABLE view_utility_evaluations
  DROP COLUMN decs_alternatives_context;
ALTER TABLE view_utility_evaluations
  ADD COLUMN decs_argumentative_structure INTEGER;

-- ---------------------------------------------------------------------
-- view_utility_evaluations: Timeline view (new, 3 items + 1 timing)
-- ---------------------------------------------------------------------
ALTER TABLE view_utility_evaluations
  ADD COLUMN timeline_temporal_sequence INTEGER,
  ADD COLUMN timeline_causal_links INTEGER,
  ADD COLUMN timeline_obligation_activation INTEGER,
  ADD COLUMN time_timeline_review INTEGER;

-- ---------------------------------------------------------------------
-- view_utility_evaluations: Narrative rewording
-- ---------------------------------------------------------------------
ALTER TABLE view_utility_evaluations
  RENAME COLUMN narr_situation_understood TO narr_characters_tensions;
ALTER TABLE view_utility_evaluations
  DROP COLUMN narr_sequence_clear;
ALTER TABLE view_utility_evaluations
  ADD COLUMN narr_ethical_significance INTEGER;

-- ---------------------------------------------------------------------
-- retrospective_reflections: add Timeline rank, rename Questions rank
-- ---------------------------------------------------------------------
ALTER TABLE retrospective_reflections
  RENAME COLUMN rank_questions_view TO rank_qc_view;
ALTER TABLE retrospective_reflections
  ADD COLUMN rank_timeline_view INTEGER;

-- ---------------------------------------------------------------------
-- validation_sessions: consent gate + random-code support
-- ---------------------------------------------------------------------
ALTER TABLE validation_sessions
  ADD COLUMN consent_acknowledged_at TIMESTAMP,
  ADD COLUMN info_sheet_version VARCHAR(20),
  ADD COLUMN participant_code VARCHAR(16);

CREATE UNIQUE INDEX validation_sessions_participant_code_key
  ON validation_sessions (participant_code)
  WHERE participant_code IS NOT NULL;

COMMIT;
