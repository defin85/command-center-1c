# CommandCenter1C - AI Coding Instructions

## Project Overview
Microservices platform for centralized management of 700+ 1C:Enterprise databases. Hybrid architecture: Python/Django orchestrator + Go workers for parallel processing + React frontend.

## Critical Architecture Patterns

### Service Communication Flow
```
Frontend (React:5173) → API Gateway (Go:8080) → Orchestrator (Django:8000) → Redis Queue → 
Go Workers → OData → 1C Databases
```

**Key Rules:**
- Frontend NEVER calls Orchestrator directly - always through API Gateway
- Workers pull from Redis queue, never called directly
- Shared Go code lives in `go-services/shared/` (models, logger, metrics, auth)
- Django apps are independent - avoid cross-app imports

### Hybrid Development Mode
Infrastructure runs in Docker, applications run on host:
- **Docker:** PostgreSQL (5432), Redis (6379) via `docker-compose.local.yml`
- **Host processes:** All application services (Orchestrator, Workers, Frontend)
- **Why:** Faster iteration, easier debugging, no Windows Firewall issues with compiled binaries

## Essential Development Workflows

### Starting Work
```bash
./scripts/dev/start-all.sh              # Smart start with auto-rebuild detection
./scripts/dev/health-check.sh           # Verify all services running
```

### During Development
```bash
./scripts/dev/restart-all.sh            # Smart restart - only rebuilds changed Go services
./scripts/dev/restart-all.sh --service=api-gateway  # Restart single service
./scripts/dev/logs.sh <service-name>    # View logs (tail -f)
```

**Go Services Auto-Rebuild Logic:**
- Compares `.go` file timestamps vs binary timestamp
- If `go-services/shared/` changed → rebuilds ALL Go services
- Outputs to `bin/cc1c-<service>.exe` (never use `go run` - causes Windows Firewall prompts)
- Flags: `--force-rebuild`, `--no-rebuild`, `--parallel-build`, `--verbose`

### Testing & Migrations
```bash
# Django migrations
cd orchestrator && source venv/Scripts/activate
python manage.py makemigrations && python manage.py migrate

# Go tests
cd go-services/<service> && go test ./...

# Python tests
cd orchestrator && pytest
```

## Project-Specific Conventions

### Go Service Structure
Every Go service follows this pattern:
```
go-services/<service>/
├── cmd/main.go           # Entry point with version flag support
├── internal/             # Private service code
│   ├── handlers/         # HTTP handlers (Gin framework)
│   ├── services/         # Business logic
│   └── config/           # Service config
└── Dockerfile
```

**Shared code** (`go-services/shared/`):
- `models/` - Common structs (Operation, Database, OperationResultV2)
- `logger/` - Structured logging (logrus)
- `metrics/` - Prometheus metrics
- `auth/` - JWT authentication

### Django App Independence
Each Django app (`orchestrator/apps/*`) is self-contained:
- `databases/` - Database CRUD, OData client, health checks
- `operations/` - Operation management, task queue
- `templates/` - Jinja2 template engine for operations

**Critical:** Apps communicate via well-defined interfaces, not direct imports.

### Build System & Naming
Binary naming: `cc1c-<service>.exe` (Windows) / `cc1c-<service>` (Linux)
- Prevents Task Manager showing "main.exe" everywhere
- Reduces Windows Firewall prompts (stable binary path)
- Versioning baked in: `./bin/cc1c-api-gateway.exe --version`

Build commands:
```bash
./scripts/build.sh                      # Build all Go services
./scripts/build.sh --service=worker     # Build single service
./scripts/build.sh --parallel           # Faster parallel build
```

## Critical Constraints

### 1C Transaction Limits
**MUST keep 1C transactions < 15 seconds!** If longer:
- Split into multiple short transactions
- Use OData `$batch` (100-500 records/batch recommended)
- Move heavy computation outside 1C

### Connection Limits
- Max 3-5 concurrent connections per 1C database
- Worker pool auto-scales based on queue depth
- Phase 1: 10-20 workers; Production: 100-500

### Environment Configuration
`.env.local` must have:
```bash
DB_HOST=localhost        # NOT 'postgres' (Docker service name)
REDIS_HOST=localhost     # NOT 'redis' 
EXE_1CV8_PATH="C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe"
```

## Integration Points

### External Dependencies
- **ras-grpc-gw** (separate repo): gRPC gateway for 1C RAS protocol
  - Must start BEFORE cluster-service
  - Ports: 9999 (gRPC), 8081 (HTTP health)
  - Health: `curl http://localhost:8081/health`

### Service Dependencies
```
ras-grpc-gw:9999 ← cluster-service:8088
postgres:5432, redis:6379 ← orchestrator:8000
orchestrator:8000 ← api-gateway:8080
api-gateway:8080 ← frontend:5173
```

## Key Files to Reference

- **Architecture decisions:** `docs/ROADMAP.md` (Balanced Approach, Phases 1-5)
- **Full AI context:** `CLAUDE.md` (comprehensive instructions for AI agents)
- **Script documentation:** `scripts/dev/README.md`
- **OData integration:** `docs/ODATA_INTEGRATION.md`
- **1C RAS setup:** `docs/1C_ADMINISTRATION_GUIDE.md`

## Common Gotchas

1. **Missing Jinja2:** If Django fails with `ModuleNotFoundError: jinja2`, run:
   ```bash
   cd orchestrator && source venv/Scripts/activate && pip install Jinja2==3.1.6
   ```

2. **psycopg2-binary fails on Python 3.13:** Known issue. Either downgrade to Python 3.11/3.12 or use psycopg3.

3. **cluster-service connection refused:** ras-grpc-gw must be running first. Check:
   ```bash
   curl http://localhost:8081/health  # Should return 200 OK
   netstat -ano | findstr :9999       # Should show listening port
   ```

4. **PID files corrupted:** Clean and restart:
   ```bash
   rm -rf pids/*.pid
   ./scripts/dev/start-all.sh
   ```

## Current Development Phase

**Sprint 2.1-2.2** (Task Queue & Template Engine) - ~25% complete
- Focus: Orchestrator ↔ Worker integration, Template Engine implementation
- Completed: Infrastructure (Sprint 1.1-1.4), RAS integration
- Next: Real operation execution, worker scaling

Refer to `docs/ROADMAP.md` for detailed sprint breakdown.
