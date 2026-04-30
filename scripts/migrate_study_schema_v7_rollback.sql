-- scripts/migrate_study_schema_v7_rollback.sql
-- Rollback of migrate_study_schema_v7.sql. Use only if forward migration
-- succeeded but the Python-side work failed and we need to revert.

BEGIN;

ALTER TABLE view_utility_evaluations
  DROP COLUMN low_effort_flag,
  DROP COLUMN attention_check_response;

ALTER TABLE validation_sessions
  DROP COLUMN demographics_completed_at,
  DROP COLUMN prior_ethics_course,
  DROP COLUMN nspe_pe_familiarity,
  DROP COLUMN role_category,
  DROP COLUMN years_engineering_experience,
  DROP COLUMN highest_engineering_degree;

ALTER TABLE validation_sessions
  DROP COLUMN recruitment_source;

DROP INDEX IF EXISTS validation_sessions_prolific_pid_hash_key;
ALTER TABLE validation_sessions
  DROP COLUMN prolific_pid_hash;

DROP INDEX IF EXISTS validation_sessions_completion_code_key;
ALTER TABLE validation_sessions
  DROP COLUMN completion_code;

COMMIT;
