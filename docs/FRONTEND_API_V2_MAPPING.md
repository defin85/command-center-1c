# Frontend API v1 → v2 Endpoint Mapping

## Authentication

| v1 Endpoint | v2 Endpoint | Method | Gateway Route | Notes |
|-------------|-------------|--------|---------------|-------|
| `POST /api/token/` | `POST /api/v2/auth/login` | POST | → Django Orchestrator | Returns JWT access + refresh tokens |
| `POST /api/token/refresh/` | `POST /api/v2/auth/refresh` | POST | → Django Orchestrator | Refresh access token |
| `POST /api/token/verify/` | `POST /api/v2/auth/verify` | POST | → Django Orchestrator | Verify token validity |

**Breaking Changes:** None
**Migration Priority:** 🔴 CRITICAL (fixes direct 8000 calls)

---

## Databases

| v1 Endpoint | v2 Endpoint | Method | Gateway Route | Breaking Changes |
|-------------|-------------|--------|---------------|------------------|
| `GET /api/v1/databases/` | `GET /api/v2/databases/list-databases` | GET | → Django | Query params: `?cluster_id=&name_filter=&page=&page_size=` |
| `GET /api/v1/databases/{id}` | `GET /api/v2/databases/get-database?db_id={id}` | GET | → Django | Path param → Query param |
| `POST /api/v1/databases/` | `POST /api/v2/databases/create-database` | POST | → Django | Body unchanged |
| `PUT /api/v1/databases/{id}` | `PUT /api/v2/databases/update-database?db_id={id}` | PUT | → Django | Path param → Query param |
| `DELETE /api/v1/databases/{id}` | `DELETE /api/v2/databases/delete-database?db_id={id}` | DELETE | → Django | Path param → Query param |
| `POST /api/v1/databases/health-check` | `POST /api/v2/databases/check-health` | POST | → Django | Body: `{"database_ids": [...]}` |
| `GET /api/v1/databases/{id}/odata-metadata` | `GET /api/v2/databases/get-odata-metadata?db_id={id}` | GET | → Django | Path → Query |
| `POST /api/v1/databases/batch-operation` | `POST /api/v2/databases/execute-batch-operation` | POST | → Django | Body unchanged |

**Breaking Changes:**
- ⚠️ All ID parameters moved from path to query params
- ⚠️ List endpoint renamed: `/databases/` → `/databases/list-databases`

**Migration Priority:** 🔴 CRITICAL

---

## Clusters (RAS Adapter Integration)

| v1 Endpoint | v2 Endpoint | Method | Gateway Route | Breaking Changes |
|-------------|-------------|--------|---------------|------------------|
| `POST /api/v1/clusters/{id}/sync` | `POST /api/v2/clusters/sync-cluster?cluster_id={id}` | POST | → Django | Path → Query param |
| `POST /api/v1/clusters/{id}/lock` | `POST /api/v2/ras/lock-infobase` | POST | → RAS Adapter | ⚠️ Now requires `infobase_name` (see notes) |
| `POST /api/v1/clusters/{id}/unlock` | `POST /api/v2/ras/unlock-infobase` | POST | → RAS Adapter | ⚠️ Now requires `infobase_name` |
| N/A (new) | `GET /api/v2/ras/list-infobases?cluster_id={id}` | GET | → RAS Adapter | NEW: list all infobases in cluster |
| N/A (new) | `GET /api/v2/ras/infobase-info?cluster_id={id}&infobase_name={name}` | GET | → RAS Adapter | NEW: get infobase details |
| N/A (new) | `GET /api/v2/ras/list-sessions?cluster_id={id}&infobase_name={name}` | GET | → RAS Adapter | NEW: list active sessions |
| N/A (new) | `DELETE /api/v2/ras/terminate-session?cluster_id={id}&session_id={sid}` | DELETE | → RAS Adapter | NEW: kill session |

**Lock/Unlock Body Format:**
```json
{
  "cluster_id": "uuid",
  "infobase_name": "accounting_db",
  "permission_code": "1234",
  "message": "Maintenance in progress"
}
```

**Breaking Changes:**
- ⚠️ **MAJOR:** Lock/Unlock now use `infobase_name` instead of `database_id`
- **Migration Strategy:** Frontend must fetch database details first to resolve `infobase_name`

**Migration Priority:** 🟡 HIGH

---

## Operations (Workflows)

| v1 Endpoint | v2 Endpoint | Method | Gateway Route | Breaking Changes |
|-------------|-------------|--------|---------------|------------------|
| `POST /api/v1/operations/` | `POST /api/v2/operations/create-operation` | POST | → Django | Body unchanged |
| `GET /api/v1/operations/` | `GET /api/v2/operations/list-operations` | GET | → Django | Query params: `?status=&type=&page=` |
| `GET /api/v1/operations/{id}` | `GET /api/v2/operations/get-operation?operation_id={id}` | GET | → Django | Path → Query |
| `GET /api/v1/operations/{id}/status` | `GET /api/v2/operations/get-status?operation_id={id}` | GET | → Django | Path → Query |
| `POST /api/v1/operations/{id}/execute` | `POST /api/v2/operations/execute-operation?operation_id={id}` | POST | → Django | Path → Query |
| `POST /api/v1/operations/{id}/cancel` | `POST /api/v2/operations/cancel-operation?operation_id={id}` | POST | → Django | Path → Query |
| `GET /api/v1/operations/{id}/logs` | `GET /api/v2/operations/get-logs?operation_id={id}` | GET | → Django | Path → Query |
| `POST /api/v1/operations/{id}/retry` | `POST /api/v2/operations/retry-operation?operation_id={id}` | POST | → Django | Path → Query |

**Breaking Changes:**
- ⚠️ All operation ID parameters moved from path to query params
- ⚠️ List endpoint base path unchanged but now requires explicit `/list-operations`

**Migration Priority:** 🔴 CRITICAL (14+ endpoints in workflows.ts)

---

## Templates

| v1 Endpoint | v2 Endpoint | Method | Gateway Route | Breaking Changes |
|-------------|-------------|--------|---------------|------------------|
| `GET /api/v1/templates/` | `GET /api/v2/templates/list-templates` | GET | → Django | Query params: `?category=&page=` |
| `GET /api/v1/templates/{id}` | `GET /api/v2/templates/get-template?template_id={id}` | GET | → Django | Path → Query |
| `POST /api/v1/templates/` | `POST /api/v2/templates/create-template` | POST | → Django | Body unchanged |
| `PUT /api/v1/templates/{id}` | `POST /api/v2/templates/update-template?template_id={id}` | POST | → Django | Method: PUT → POST, Path → Query |
| `DELETE /api/v1/templates/{id}` | `DELETE /api/v2/templates/delete-template?template_id={id}` | DELETE | → Django | Path → Query |
| `POST /api/v1/templates/{id}/validate` | `POST /api/v2/templates/validate-template?template_id={id}` | POST | → Django | Path → Query |
| `POST /api/v1/templates/render` | `POST /api/v2/templates/render-template` | POST | → Django | Body: `{"template_id": "...", "variables": {...}}` |

**Breaking Changes:**
- ⚠️ Update method changed from PUT → POST (Django convention)
- ⚠️ All ID parameters: path → query

**Migration Priority:** 🟢 MEDIUM

---

## WebSocket

| v1 Endpoint | v2 Endpoint | Protocol | Gateway Route | Notes |
|-------------|-------------|----------|---------------|-------|
| `ws://localhost:8000/ws/service-mesh/` | `ws://localhost:8080/api/v2/ws/service-mesh` | WebSocket | → Django Channels | Real-time metrics |
| `ws://localhost:8000/ws/operations/{id}/` | `ws://localhost:8080/api/v2/ws/operation?operation_id={id}` | WebSocket | → Django Channels | Operation progress |

**Breaking Changes:**
- ⚠️ **HIGH RISK:** WebSocket через Gateway не протестирован
- ⚠️ Path param → Query param для operation streams
- **Mitigation:** Fallback to polling if WebSocket fails

**Migration Priority:** 🔴 CRITICAL (но требует предварительного тестирования)

---

## Monitoring (Jaeger)

| Direct Jaeger | v2 Endpoint | Method | Gateway Route | Notes |
|---------------|-------------|--------|---------------|-------|
| `GET /api/traces?service=X` | `GET /api/v2/jaeger/traces?service=X` | GET | → Jaeger:16686 | Proxy unchanged |
| `GET /api/traces/{trace_id}` | `GET /api/v2/jaeger/trace/{trace_id}` | GET | → Jaeger:16686 | Proxy unchanged |
| `GET /api/services` | `GET /api/v2/jaeger/services` | GET | → Jaeger:16686 | Proxy unchanged |

**UI Links:**
```typescript
// BEFORE: hardcoded
href="http://localhost:16686/trace/abc123"

// AFTER: use config
import { JAEGER_UI_URL } from '@/api/config/endpoints';
href={`${JAEGER_UI_URL}/trace/${traceId}`}
```

**Breaking Changes:** None (pure proxy)
**Migration Priority:** 🟢 LOW

---

## Summary

**Total Endpoints to Migrate:** 38
**High Priority (Week 1):** 22 endpoints
**Medium Priority (Week 2):** 12 endpoints
**Low Priority (Week 3):** 4 endpoints

**Key Breaking Changes:**
1. All resource IDs: Path params → Query params
2. Lock/Unlock: `database_id` → `infobase_name`
3. Template Update: PUT → POST method
4. WebSocket: Path params → Query params

**Migration Risks:**
- 🔴 HIGH: WebSocket through Gateway (untested)
- 🟡 MEDIUM: Lock/Unlock infobase_name resolution
- 🟢 LOW: Query param format changes (mechanical refactor)
