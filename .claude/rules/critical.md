# Critical Information

> Статус: legacy/non-authoritative Claude rule.
> Для текущего agent-facing onboarding используйте [../../docs/agent/INDEX.md](../../docs/agent/INDEX.md).

> Загружается ВСЕГДА. Критичная информация для любой задачи.

## Project Status

| Field | Value |
|-------|-------|
| **Current Phase** | Phase 2 - Extended Functionality |
| **Celery Status** | REMOVED - Go Worker единственный execution engine |
| **Dev Mode** | Native WSL (USE_DOCKER=false) |
| **Roadmap** | Balanced Approach (14-16 weeks) - `docs/ROADMAP.md` |
| **Phase 1** | COMPLETE (Infrastructure, Models, OData, RAS, Celery Removal) |

## API Version

**v2 (action-based)** - см. `docs/roadmaps/API_V2_UNIFICATION_ROADMAP.md`

- Frontend → API Gateway (8180) `/api/v2/*`
- v1 endpoints deprecated (Sunset: 2026-03-01)

## Architecture Flow

```
User → Frontend (React:5173)
  ↓
API Gateway (Go:8180) → Orchestrator (Django:8200) → PostgreSQL:5432
                          ↓
                        Redis:6379 (Queue + Pub/Sub)
                          ↓
                    Go Worker (Unified Engine) → OData → 1C Bases
                          ↓
                    ras-adapter (Go:8188) → RAS (1545)
```

## Critical Constraints

| Constraint | Limit | Notes |
|------------|-------|-------|
| **1C Transactions** | < 15 seconds | CRITICAL! Split into short transactions |
| **Connections per DB** | 3-5 concurrent | Per 1C database |
| **Worker Pool** | Phase 1: 10-20 | Production: auto-scale |
| **OData Batch** | 100-500 records | Per batch operation |
| **Rate Limiting** | 100 req/min | Per user (default) |

## Service Ports

| Service | Port | Status |
|---------|------|--------|
| **Frontend** | 5173 | React |
| **API Gateway** | 8180 | Go/Gin |
| **Orchestrator** | 8200 | Django |
| **ras-adapter** | 8188 | Go |
| **batch-service** | 8187 | Go (in dev) |
| **PostgreSQL** | 5432 | - |
| **Redis** | 6379 | - |

> Ports 8180, 8187, 8188, 8200 chosen outside Windows reserved ranges (7913-8012, 8013-8112)
