# Archived v1 API Tests

These tests were archived during the V1 → V2 Event-Driven Migration (P3-11).

## Why Archived

All tests in this directory were written for the **v1 REST-style API** which has been removed.
The **v2 API uses action-based routing** with completely different request/response patterns:

| v1 REST Style | v2 Action Style |
|---------------|-----------------|
| `GET /api/v1/databases/` | `GET /api/v2/databases/list-databases/` |
| `GET /api/v1/databases/{id}/` | `POST /api/v2/databases/get-database/` + body |
| `POST /api/v1/databases/{id}/credentials/` | `Redis Streams: commands:orchestrator:get-database-credentials` |

These tests cannot be simply "URL-updated" - they require rewriting to match v2 API style.

## Archived Files

| File | Original Location | Description |
|------|-------------------|-------------|
| `test_databases_api.py` | `apps/databases/` | Database CRUD REST API tests |
| `test_service_mesh_views.py` | `apps/operations/tests/` | Service Mesh monitoring API tests |
| `test_templates_views.py` | `apps/templates/tests/` | Template validation endpoint tests |
| `test_workflow_api.py` | `apps/templates/workflow/tests/` | Workflow CRUD REST API tests |
| `test_workflow_integration.py` | `apps/templates/workflow/tests/` | Workflow integration tests |
| `test_jwt_service_auth.py` | `apps/databases/tests/` | JWT service-to-service auth tests |
| `workflow_load_test.py` | `tests/load/` | Locust load testing script |
| `test_celery_tasks.py` | `apps/templates/tests/` | Celery tasks tests (tasks removed) |

## TODO: v2 API Tests

New tests should be written for v2 API at:
- `orchestrator/apps/api_v2/tests/`

Key areas needing coverage:
- [ ] Workflow execution via `/api/v2/workflows/execute-workflow/`
- [ ] Database credentials via `commands:orchestrator:get-database-credentials`
- [ ] Service mesh monitoring via `/api/v2/service-mesh/get-metrics/`
- [ ] JWT authentication for internal API
- [ ] Load testing with v2 endpoints

## Date Archived

2025-12-15 (V1_TO_V2_EVENT_DRIVEN_MIGRATION P3-11)
