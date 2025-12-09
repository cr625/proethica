# Pipeline Automation

This guide covers batch case processing through the automated extraction pipeline.

## Overview

Pipeline automation enables:

- Batch extraction across multiple cases
- Background processing via Celery tasks
- Real-time progress monitoring
- Queue management for bulk operations

## Prerequisites

Pipeline automation requires:

| Service | Port | Purpose |
|---------|------|---------|
| Redis | 6379 | Message broker |
| Celery Worker | - | Background tasks |
| ProEthica | 5000 | Web interface |
| OntServe MCP | 8082 | Ontology validation |

## Starting Services

### Option 1: Single Command (Recommended)

```bash
./scripts/start_all.sh start
```

This starts all required services in correct order.

### Option 2: Manual Start

**Terminal 1 - Redis**:
```bash
redis-server
```

**Terminal 2 - Celery Worker**:
```bash
cd /path/to/proethica
source venv-proethica/bin/activate
PYTHONPATH=/path/to/parent:$PYTHONPATH celery -A celery_config worker --loglevel=info
```

**Terminal 3 - Flask**:
```bash
cd /path/to/proethica
source venv-proethica/bin/activate
PYTHONPATH=/path/to/parent:$PYTHONPATH python run.py
```

### Service Management

```bash
./scripts/start_all.sh status   # Check status
./scripts/start_all.sh stop     # Stop services
./scripts/start_all.sh restart  # Restart all
```

## Pipeline Dashboard

### Accessing Dashboard

Navigate to: **Pipeline Dashboard** (`/pipeline/dashboard`)

Or via Cases page: Click **Automation** button

### Dashboard Layout

| Section | Description |
|---------|-------------|
| **Service Status** | Health of Redis, Celery, Workers |
| **Active Runs** | Currently processing pipelines |
| **Queue** | Pending and completed jobs |
| **Controls** | Start, cancel, reprocess buttons |

## Service Status

### Status Widget

The header widget shows real-time status:

| Indicator | Meaning |
|-----------|---------|
| **Redis** | Message broker connection |
| **Celery** | Worker process status |
| **Workers** | Active worker count |
| **Tasks** | Queue depth |

### Overall Health

| Status | Description |
|--------|-------------|
| **Healthy** | All services operational |
| **Degraded** | Some services unavailable |
| **Critical** | Core services offline |

### Status API

Programmatic access:

```bash
curl http://localhost:5000/pipeline/api/service-status
```

## Queue Management

### Queue Tab

The Queue tab shows:

| Column | Description |
|--------|-------------|
| **Case** | Case being processed |
| **Status** | Queued, running, completed, failed |
| **Progress** | Completion percentage |
| **Started** | Start timestamp |
| **Completed** | End timestamp |

### Queue Statuses

| Status | Meaning |
|--------|---------|
| **queued** | Waiting in queue |
| **running** | Currently processing |
| **completed** | Successfully finished |
| **failed** | Error occurred |
| **cancelled** | User cancelled |
| **superseded** | Replaced by reprocess |

## Running Pipelines

### Single Case

To process a single case:

1. Go to case detail page
2. Click **Queue for Processing**
3. Monitor in Pipeline Dashboard

### Batch Processing

To process multiple cases:

1. Go to Pipeline Dashboard
2. Select cases from list
3. Click **Add to Queue**
4. Monitor progress

### Priority Processing

Cases processed in queue order. For priority:

1. Use direct extraction (non-automated)
2. Or reorder queue manually

## Monitoring Progress

### Real-Time Updates

Active runs show:

- Current step (1, 1b, 2, 2b, 3)
- Entity count extracted
- Progress percentage
- Estimated time remaining

### Refresh

Dashboard auto-refreshes every 5 seconds. Manual refresh also available.

### Logs

View detailed logs:

1. Click run in Active Runs
2. Expand log section
3. View extraction output

## Pipeline Controls

### Cancel Running

To cancel a running pipeline:

1. Click **Cancel** on active run
2. Confirms cancellation
3. Celery task revoked
4. Run marked cancelled

### Reprocess Case

To reprocess a completed case:

1. Click **Reprocess** button
2. Clears existing entities
3. Marks old run as superseded
4. Starts fresh extraction

### Clear Case

To clear without reprocessing:

```bash
python scripts/clear_case_extractions.py <case_id>
```

Options:
- `--include-runs`: Also clear pipeline_run records

## Pipeline Architecture

### Extraction Flow

```
Queue Request
    ↓
Celery Task Created
    ↓
Step 1: Facts (Roles, States, Resources)
    ↓
Step 1b: Discussion (Roles, States, Resources)
    ↓
Step 2: Facts (Principles, Obligations, Constraints, Capabilities)
    ↓
Step 2b: Discussion (Principles, Obligations, Constraints, Capabilities)
    ↓
Step 3: Temporal (Events, Actions, Relations)
    ↓
Complete
```

### Entity Storage

During pipeline:

- Entities stored in `temporary_rdf_storage`
- Linked by `extraction_session_id`
- Prompts stored in `extraction_prompts`

### Pipeline Run Record

Each run creates `pipeline_run` record:

| Field | Description |
|-------|-------------|
| `id` | Run identifier |
| `case_id` | Case being processed |
| `status` | Current status |
| `current_step` | Active step |
| `entity_count` | Entities extracted |
| `started_at` | Start timestamp |
| `completed_at` | End timestamp |
| `error_message` | Error if failed |

## Celery Configuration

### Task Settings

From `celery_config.py`:

```python
task_time_limit = 7200      # 2 hour hard limit
task_soft_time_limit = 6000 # 100 minute soft limit
worker_prefetch_multiplier = 1  # One task at a time
```

### Queue Name

Default queue: `celery`

### Result Backend

Results stored in Redis DB 1.

## Error Handling

### Task Failures

If task fails:

1. Error captured in pipeline_run
2. Partial entities preserved
3. Can retry or reprocess

### Timeout

If task times out:

1. Soft limit triggers graceful stop
2. Hard limit forces termination
3. Partial progress saved

### Recovery

After failure:

1. Review error message
2. Fix underlying issue
3. Reprocess case

## Utility Scripts

### Clear Case Extractions

```bash
python scripts/clear_case_extractions.py <case_id> [--include-runs]
```

### Cleanup Orphaned Entities

```bash
python scripts/cleanup_orphaned_entities.py [--delete]
```

### Check Queue

```bash
celery -A celery_config inspect active
celery -A celery_config inspect reserved
```

## Troubleshooting

### Services Not Starting

Check each service:

```bash
redis-cli ping  # Should return PONG
celery -A celery_config status  # Should show workers
curl http://localhost:5000/  # Should return page
```

### Tasks Not Processing

1. Check Celery worker running
2. Verify Redis connection
3. Check worker logs for errors

### Memory Issues

Long-running tasks may use memory:

1. Monitor worker memory
2. Restart workers periodically
3. Process fewer cases at once

### Orphaned Entities

If entities without sessions:

```bash
python scripts/cleanup_orphaned_entities.py --delete
```

## Related Guides

- [Phase 1 Extraction](phase1-extraction.md) - Manual extraction
- [Entity Review](entity-review.md) - Reviewing results
- [Settings](settings.md) - Configuration options
