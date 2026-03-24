# Quick Start & Commands

> Статус: legacy/non-authoritative quick-start.
> Для текущего agent-facing onboarding используйте [docs/agent/INDEX.md](../../docs/agent/INDEX.md).

> Запуск и управление проектом.

## Project Launch

```bash
# From project root
./scripts/dev/start-all.sh        # Smart start with auto-rebuild
./scripts/dev/health-check.sh     # Check status
```

## Service Management

```bash
./scripts/dev/restart-all.sh        # Restart all services
./scripts/dev/restart.sh <service>  # Single service
./scripts/dev/logs.sh <service>     # View logs
./scripts/dev/stop-all.sh           # Stop all
```

**Available services:** `orchestrator`, `api-gateway`, `worker`, `ras-adapter`, `frontend`

## Code Quality

```bash
./scripts/dev/lint.sh              # Check all (tsc, eslint, ruff, go vet)
./scripts/dev/lint.sh --fix        # Auto-fix
./scripts/dev/lint.sh --ts         # TypeScript only
```

## Django Shell

```bash
cd orchestrator && source venv/bin/activate
python manage.py shell -c "from apps.operations.models import BatchOperation; print(BatchOperation.objects.count())"
# Or interactive:
python manage.py shell
```

## Slash Commands

Use via SlashCommand tool:
- `/dev-start` - start all services
- `/check-health` - check all services status
- `/restart-service <name>` - restart service
- `/run-migrations` - apply Django migrations
- `/test-all` - run all tests
- `/build-docker` - build Docker images

## Health Check URLs

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| API Gateway | http://localhost:8180/health |
| Orchestrator Admin | http://localhost:8200/admin |
| Orchestrator API | http://localhost:8200/api/docs |
| ras-adapter | http://localhost:8188/health |
| batch-service | http://localhost:8187/health |

## Monitoring Ports

| Service | Native (systemd) | Docker |
|---------|------------------|--------|
| Prometheus | http://localhost:9090 | http://localhost:9090 |
| Grafana | http://localhost:3000 | http://localhost:5000 |
| Jaeger | requires install | http://localhost:16686 |

> Mode determined by `USE_DOCKER` in `.env.local`
