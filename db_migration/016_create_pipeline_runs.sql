-- Migration: 016_create_pipeline_runs.sql
-- Purpose: Create table for tracking automated pipeline runs
-- Date: 2025-11-30

-- Pipeline run tracking table
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- Status tracking
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    current_step VARCHAR(50),

    -- Celery integration
    celery_task_id VARCHAR(255),

    -- Progress tracking (JSONB for flexibility)
    steps_completed JSONB DEFAULT '[]'::jsonb,
    step_results JSONB DEFAULT '{}'::jsonb,

    -- Error handling
    error_message TEXT,
    error_step VARCHAR(50),
    retry_count INTEGER DEFAULT 0,

    -- Timing
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Configuration
    config JSONB DEFAULT '{}'::jsonb,

    -- User who initiated (optional)
    initiated_by INTEGER REFERENCES users(id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_case_id ON pipeline_runs(case_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_celery_task_id ON pipeline_runs(celery_task_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_created_at ON pipeline_runs(created_at DESC);

-- Status values:
-- 'pending'        - Queued, not started
-- 'running'        - Currently processing
-- 'step1_facts'    - Running Step 1 facts extraction
-- 'step1_discussion' - Running Step 1 discussion extraction
-- 'step2_facts'    - Running Step 2 facts extraction
-- 'step2_discussion' - Running Step 2 discussion extraction
-- 'step3'          - Running Step 3 (actions/events)
-- 'step4'          - Running Step 4 (synthesis)
-- 'step5'          - Running Step 5 (scenario)
-- 'completed'      - All steps finished successfully
-- 'failed'         - Error occurred
-- 'paused'         - Manually paused by user

-- Pipeline queue table for batch processing
CREATE TABLE IF NOT EXISTS pipeline_queue (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    priority INTEGER DEFAULT 0,  -- Higher = more urgent
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    group_name VARCHAR(100),  -- For grouping cases
    added_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,

    UNIQUE(case_id, status)  -- Prevent duplicate queuing
);

CREATE INDEX IF NOT EXISTS idx_pipeline_queue_status ON pipeline_queue(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_queue_priority ON pipeline_queue(priority DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_queue_group ON pipeline_queue(group_name);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_pipeline_runs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for auto-updating updated_at
DROP TRIGGER IF EXISTS trigger_pipeline_runs_updated_at ON pipeline_runs;
CREATE TRIGGER trigger_pipeline_runs_updated_at
    BEFORE UPDATE ON pipeline_runs
    FOR EACH ROW
    EXECUTE FUNCTION update_pipeline_runs_updated_at();

-- Comments for documentation
COMMENT ON TABLE pipeline_runs IS 'Tracks automated pipeline processing runs for cases';
COMMENT ON TABLE pipeline_queue IS 'Queue for batch processing of cases';
COMMENT ON COLUMN pipeline_runs.steps_completed IS 'JSON array of completed step names';
COMMENT ON COLUMN pipeline_runs.step_results IS 'JSON object with results from each step';
COMMENT ON COLUMN pipeline_runs.config IS 'Configuration options for this run';
