# Структура репозитория (коротко)

- `frontend/` — React+TS.
- `go-services/api-gateway/` — Gateway (Gin), единственная точка входа для frontend.
- `go-services/worker/` — Go Worker (execution engine), Celery удалён.
- `go-services/shared/`, `go-services/ras-client/` — общий код/интеграция RAS.
- `orchestrator/` — Django/DRF.
- `contracts/` — OpenAPI (contract-first) + генерация.
- `docs/`, `scripts/dev/`, `generated/`.

Правило: frontend ходит только в Gateway (`/api/v2/*` на 8180).
