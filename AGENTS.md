Отвечай только на русском языке.

# CommandCenter1C - AI Agent Instructions

> Микросервисная платформа для централизованного управления 700+ базами 1С

---

## Для AI-агента (коротко)

- Работай по Balanced roadmap: `docs/ROADMAP.md`.
- Соблюдай структуру монорепы: не создавай файлы в "случайных" местах.
- Frontend обращается только в API Gateway (`/api/v2/*` на `8180`), без прямых вызовов Orchestrator.
- Изменения API делай contract-first: сначала `contracts/**/*.yaml`, затем генерация клиентов/типов.
- Учитывай лимиты 1С: транзакции < 15 секунд, 3-5 соединений на БД, OData batch 100-500.
- Не полагайся на `jq/yq` как на обязательные утилиты: при необходимости делай fallback на Python.

## Статус проекта (критично)

| Field | Value |
|-------|-------|
| **Current Phase** | Phase 2 - Extended Functionality |
| **Celery Status** | REMOVED - Go Worker единственный execution engine |
| **Dev Mode** | Native WSL (USE_DOCKER=false) |
| **API Version** | v2 (action-based) - `/api/v2/*` (v1 deprecated, Sunset: 2026-03-01) |
| **Roadmap** | Balanced Approach (14-16 weeks) - `docs/ROADMAP.md` |

## Сервисы и порты

| Service | Port |
|---------|------|
| Frontend | 5173 |
| API Gateway | 8180 |
| Orchestrator (Django) | 8200 |
| ras-adapter | 8188 |
| batch-service (dev) | 8187 |
| PostgreSQL | 5432 |
| Redis | 6379 |

## Архитектура (high level)

```
User → Frontend (5173) → API Gateway (8180) → Orchestrator (8200) → PostgreSQL
                                           ↓
                                         Redis (6379)
                                           ↓
                              Go Worker (unified) → OData → 1C Bases
                                           ↓
                                   ras-adapter (8188) → RAS (1545)
```

## Критичные ограничения

- 1C Transactions: < 15 seconds (обязательно дробить на короткие операции)
- Connections per DB: 3-5 concurrent
- OData batch: 100-500 records/batch
- Rate limiting: 100 req/min per user (default)

## Команды разработки

```bash
./scripts/dev/start-all.sh        # Smart start with auto-rebuild
./scripts/dev/health-check.sh     # Check health
./scripts/dev/restart-all.sh      # Restart all services
./scripts/dev/restart.sh <svc>    # Restart one service
./scripts/dev/logs.sh <svc>       # Tail logs for service
./scripts/dev/stop-all.sh         # Stop all services
./scripts/dev/lint.sh             # tsc + eslint + ruff + go vet
./scripts/dev/lint.sh --fix       # Auto-fix
```

Список сервисов (актуальный для скриптов): `./scripts/dev/restart.sh --help`.

## OpenAPI (contract-first)

Workflow:
1. Update spec: `contracts/<service>/openapi.yaml`
2. Validate: `./contracts/scripts/validate-specs.sh`
3. Generate: `./contracts/scripts/generate-all.sh`
4. Implement handlers using generated types

Notes:
- Для infobases endpoints использовать `cluster_id` (не `cluster`).
- Параметры и поля: `snake_case`.
- Breaking changes: версия API + депрекейт (v1 → v2).

## Тесты и покрытие

Минимум по покрытию:
- Django: > 70%
- Go: > 70%
- React: > 60%

## Отладка frontend (CDP 9222)

Запуск Chromium для remote debugging:

```bash
nohup setsid chromium --disable-gpu --disable-dev-shm-usage --no-sandbox \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chromium-debug-profile \
  http://localhost:5173/ \
  > /tmp/chromium.log 2>&1 &
```

Приоритетный способ отладки: `./scripts/dev/chrome-debug.py` (console/network/screenshot/eval/reload/pages).
Ограничение: `chrome-debug.py` и MCP-интерактив к браузеру одновременно нельзя (CDP поддерживает одно WebSocket соединение к странице).

## LSP Tool (lspctl)

CLI для LSP JSON-RPC с JSON output: `tools/lspctl/lspctl.py`.

One-shot:

```bash
python tools/lspctl/lspctl.py definition --file path/to/file.go --line 10 --col 5
```

Daemon (recommended):

```bash
python tools/lspctl/lspctl.py serve --socket /tmp/lspctl.sock
python tools/lspctl/lspctl.py call hover --file path/to/file.go --line 10 --col 5 --socket /tmp/lspctl.sock
python tools/lspctl/lspctl.py shutdown --socket /tmp/lspctl.sock
```

Notes:
- All commands return JSON: `{"result": ...}` or `{"error": "..."}`.
- Use `--lang` if file extension is not supported or when using `workspaceSymbol`.

## Полные правила

Все детальные правила и справочники лежат в `.claude/rules/`:

| File | Description |
|------|-------------|
| `critical.md` | Status, constraints, ports |
| `quick-start.md` | Commands, endpoints, monitoring |
| `development.md` | Dev rules, monorepo structure, tech stack |
| `shell-rules.md` | Shell rules (WSL/Arch) |
| `api-contracts.md` | OpenAPI workflow (paths: contracts/**) |
| `testing.md` | Testing & linting |
| `setup.md` | Setup & troubleshooting |
| `documentation.md` | Documentation links |

---

**Version:** 4.1
**Updated:** 2026-01-13

**Changes v4.1:**
- Синхронизированы критичные данные (порты, лимиты, покрытие) с `.claude/rules/*`
- Добавлен раздел по contract-first и отладке frontend через `chrome-debug.py`
