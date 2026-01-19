<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

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

### MCP chrome-devtools (Codex CLI) — браузер стартует сам

В WSL `chrome-devtools-mcp` может ошибочно выбрать Windows `chrome.exe` под `/mnt/c/...` и падать с `Target closed` / `Target.setDiscoverTargets`.
Чтобы запуск был стабильным, всегда пинни Linux Chromium через `--executablePath` и используй изолированный профиль.

Рекомендуемый конфиг для Codex: `~/.codex/config.toml`

```toml
[mcp_servers.chrome-devtools]
command = "npx"
args = [
  "-y",
  "chrome-devtools-mcp@latest",
  "--executablePath=/usr/lib/chromium/chromium",
  "--isolated",
  "--logFile=/tmp/chrome-devtools-mcp.log",
  "--chromeArg=--no-sandbox",
  "--chromeArg=--disable-setuid-sandbox",
  "--chromeArg=--no-first-run",
  "--chromeArg=--no-default-browser-check",
  "--chromeArg=--disable-dev-shm-usage",
]
startup_timeout_sec = 30
```

Заметки:
- После правки `~/.codex/config.toml` нужно перезапустить Codex (или через `/mcp` перезапустить MCP сервер), иначе настройки не подхватятся.
- При ошибках смотри `/tmp/chrome-devtools-mcp.log`.

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

**Version:** 4.2
**Updated:** 2026-01-14

**Changes v4.2:**
- Синхронизированы критичные данные (порты, лимиты, покрытие) с `.claude/rules/*`
- Добавлен раздел по contract-first и отладке frontend через `chrome-debug.py`
- Уточнён стабильный запуск Chromium для `chrome-devtools` MCP в WSL (через `--executablePath`, `--isolated`, лог).

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
