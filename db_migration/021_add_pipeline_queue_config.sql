-- Migration 021: Add config column to pipeline_queue
-- Date: 2025-12-19
-- Purpose: Store pipeline configuration options (include_step4, etc.) per queue item

-- Add config column to pipeline_queue
ALTER TABLE pipeline_queue
ADD COLUMN IF NOT EXISTS config JSONB DEFAULT '{}'::jsonb;

-- Add comment
COMMENT ON COLUMN pipeline_queue.config IS 'Pipeline configuration (include_step4, etc.)';

-- Update existing rows to have empty config if null
UPDATE pipeline_queue SET config = '{}'::jsonb WHERE config IS NULL;
