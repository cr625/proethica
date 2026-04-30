-- scripts/migrate_study_schema_v7.sql
-- Validation pivot: paid Prolific recruitment + dual-channel preservation.
-- IRB Protocol 2603011709 -- see .claude/plans/validation-crowdsource-pivot.md.
--
-- Bundles plan-§4 column additions (4.1, 4.3, 4.4, 4.7, 4.9) into a single
-- schema bump. The senior-design Drexel-student channel remains active under
-- the existing protocol; recruitment_source defaults to 'drexel_student' so
-- existing live sessions are tagged correctly without backfill drift.
--
-- Run: PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm \
--        -f scripts/migrate_study_schema_v7.sql
--
-- Rollback: scripts/migrate_study_schema_v7_rollback.sql

BEGIN;

-- ---------------------------------------------------------------------
-- validation_sessions: completion code (plan §4.1)
--
-- Distinct from participant_code. Generated at completed_at and shown on
-- the Thank You page for the participant to paste into Prolific. Crowd
-- platforms reject a study that prints the participant code as the
-- "completion proof", so we keep the two codes separate.
-- ---------------------------------------------------------------------
ALTER TABLE validation_sessions
  ADD COLUMN completion_code VARCHAR(16);

CREATE UNIQUE INDEX validation_sessions_completion_code_key
  ON validation_sessions (completion_code)
  WHERE completion_code IS NOT NULL;

-- ---------------------------------------------------------------------
-- validation_sessions: Prolific PID hash (plan §4.7)
--
-- SHA-256 hex of the Prolific PID, stored only for duplicate-enrollment
-- detection. Plain PID is never persisted. Drexel-student enrollments
-- have NULL here.
-- ---------------------------------------------------------------------
ALTER TABLE validation_sessions
  ADD COLUMN prolific_pid_hash VARCHAR(64);

CREATE UNIQUE INDEX validation_sessions_prolific_pid_hash_key
  ON validation_sessions (prolific_pid_hash)
  WHERE prolific_pid_hash IS NOT NULL;

-- ---------------------------------------------------------------------
-- validation_sessions: recruitment source (plan §4.9)
--
-- 'drexel_student' (default for the existing senior-design channel) or
-- 'prolific_engineering_trained' (set on enrollment when a Prolific PID
-- query parameter is present).
-- ---------------------------------------------------------------------
ALTER TABLE validation_sessions
  ADD COLUMN recruitment_source VARCHAR(50) NOT NULL DEFAULT 'drexel_student';

-- ---------------------------------------------------------------------
-- validation_sessions: post-task demographics (plan §4.3)
--
-- 4-6 closed-form items captured on a dedicated page between alignment and
-- complete. Free-text not used; all values are categorical or ordinal.
-- ---------------------------------------------------------------------
ALTER TABLE validation_sessions
  ADD COLUMN highest_engineering_degree VARCHAR(50),
  ADD COLUMN years_engineering_experience VARCHAR(20),
  ADD COLUMN role_category VARCHAR(50),
  ADD COLUMN nspe_pe_familiarity INTEGER,
  ADD COLUMN prior_ethics_course BOOLEAN,
  ADD COLUMN demographics_completed_at TIMESTAMP;

-- ---------------------------------------------------------------------
-- view_utility_evaluations: attention check (plan §4.4)
--
-- Stores the participant's response to a single instructed-response item
-- ("To verify careful reading, please select 'Strongly Disagree' for
-- this item."). 1-7 Likert. Pass = response equals 1. Computed at
-- analysis time; column stores the raw response, not the boolean.
--
-- low_effort_flag is set by the time-on-task floor check (plan §4.5)
-- and is null until that check runs.
-- ---------------------------------------------------------------------
ALTER TABLE view_utility_evaluations
  ADD COLUMN attention_check_response INTEGER,
  ADD COLUMN low_effort_flag BOOLEAN;

COMMIT;
