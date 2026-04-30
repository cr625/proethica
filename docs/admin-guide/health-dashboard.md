# Service Health Dashboard

The health dashboard at `/health/status` displays the operational status of ProEthica's dependent services. The page is admin-only in production.

## Public Endpoints

The following health endpoints are open to all clients and are intended for monitoring tools:

| Endpoint | Purpose |
|----------|---------|
| `/health` | Liveness check; returns `{status: "ok"}` if the Flask process is running |
| `/health/ready` | Readiness check; verifies database, Redis, MCP connectivity |
| `/health/services` | Per-service status report (cached; suitable for status pages) |

## Admin Endpoints

Admin authentication is required in production for the following:

| Endpoint | Purpose |
|----------|---------|
| `/health/status` | Full service-monitoring dashboard with cached results and history |
| `/health/demo` | Demo case health check (verifies the AAAI demo case still extracts) |
| `/health/clear-cache` | Force-refresh all cached health checks |
| `/health/errors` | Recent error log with breakdown by service |
| `/health/test-alert` | Trigger a test alert to verify notification wiring |

## Service Checks

The dashboard reports on five upstream dependencies:

| Service | Check |
|---------|-------|
| PostgreSQL | Connection succeeds and a trivial `SELECT 1` returns |
| Redis | Connection succeeds and a `PING` round-trips |
| Celery | A worker responds to inspect ping (skipped when Celery is not in use) |
| OntServe MCP | The MCP server at `ONTSERVE_MCP_URL` responds to a tools-list request |
| Demo case | The AAAI-26 demo case (database id 7) retains its extraction results |

Each check is cached separately. Successful checks are cached for several minutes; failed checks are cached for a shorter window so transient failures self-correct quickly.

## Cache Behavior

Health endpoints use `@cached_health_check` decorators that store results in Redis. Two TTLs apply: a longer one for healthy responses and a shorter one for failed responses. Use `/health/clear-cache` to force a refresh after intervention.

## Related Documentation

- [Architecture](architecture.md) - Service dependencies and ports
- [Production Server](production-server.md) - Operational monitoring setup
