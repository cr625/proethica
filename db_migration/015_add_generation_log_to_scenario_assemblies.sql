-- Migration: Add generation_log to scenario_assemblies table
-- Purpose: Persist SSE event log for scenario generation so users can review analysis steps after page reload
-- Date: 2025-11-03

-- Add generation_log column to store all SSE events
ALTER TABLE scenario_assemblies
ADD COLUMN generation_log JSONB;

-- Add comment for documentation
COMMENT ON COLUMN scenario_assemblies.generation_log IS 'Array of SSE events from scenario generation process (stage, message, progress, timestamp, data)';
