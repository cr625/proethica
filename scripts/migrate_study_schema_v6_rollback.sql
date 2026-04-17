-- scripts/migrate_study_schema_v6_rollback.sql
-- Rollback of migrate_study_schema_v6.sql. Use only if the forward migration
-- succeeded but the Python-side work failed and we need to revert.

BEGIN;

DROP INDEX IF EXISTS validation_sessions_participant_code_key;

ALTER TABLE validation_sessions
  DROP COLUMN participant_code,
  DROP COLUMN info_sheet_version,
  DROP COLUMN consent_acknowledged_at;

ALTER TABLE retrospective_reflections
  DROP COLUMN rank_timeline_view;
ALTER TABLE retrospective_reflections
  RENAME COLUMN rank_qc_view TO rank_questions_view;

ALTER TABLE view_utility_evaluations
  DROP COLUMN narr_ethical_significance,
  ADD COLUMN narr_sequence_clear INTEGER;
ALTER TABLE view_utility_evaluations
  RENAME COLUMN narr_characters_tensions TO narr_situation_understood;

ALTER TABLE view_utility_evaluations
  DROP COLUMN time_timeline_review,
  DROP COLUMN timeline_obligation_activation,
  DROP COLUMN timeline_causal_links,
  DROP COLUMN timeline_temporal_sequence;

ALTER TABLE view_utility_evaluations
  DROP COLUMN decs_argumentative_structure,
  ADD COLUMN decs_alternatives_context INTEGER;

ALTER TABLE view_utility_evaluations
  DROP COLUMN qc_emergence_resolution,
  ADD COLUMN ques_structure_aided INTEGER;
ALTER TABLE view_utility_evaluations
  RENAME COLUMN qc_deliberation_needs TO ques_deliberation_needs;
ALTER TABLE view_utility_evaluations
  RENAME COLUMN qc_issues_visible TO ques_issues_visible;

COMMIT;
