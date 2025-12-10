# Development Rules

> Правила разработки для всего проекта.

## Core Principles

1. **Work ONLY by Balanced roadmap** (`docs/ROADMAP.md`)
2. **Follow monorepo structure** - don't create files in wrong places
3. **Go shared code** → `go-services/shared/` (auth, logger, config)
4. **Django apps are independent** → minimal cross-app imports
5. **Frontend → API Gateway ONLY** → no direct Orchestrator calls
6. **Tests required** → coverage > 70%
7. **Use ./scripts/dev/*.sh** for local development
8. **OpenAPI Contract-First** → API changes start with spec update

## Monorepo Structure

```
command-center-1c/
├── go-services/              # Go microservices
│   ├── api-gateway/          # HTTP router, auth, rate limit
│   ├── worker/               # Parallel processing
│   ├── ras-adapter/          # RAS integration
│   ├── batch-service/        # Batch operations (in dev)
│   └── shared/               # Shared code
├── orchestrator/             # Python/Django
│   ├── apps/
│   │   ├── databases/        # Database CRUD, OData
│   │   ├── operations/       # Operation management
│   │   └── templates/        # Template engine
│   └── config/               # Django settings
├── frontend/                 # React + TypeScript
│   └── src/
│       ├── api/              # API client
│       ├── components/       # UI components
│       ├── pages/            # App pages
│       └── stores/           # Zustand state
├── contracts/                # OpenAPI specs
├── infrastructure/           # Docker, K8s, monitoring
├── docs/                     # Documentation
└── scripts/dev/              # Dev scripts
```

## Tech Stack

| Component | Language | Framework | Port |
|-----------|----------|-----------|------|
| API Gateway | Go 1.21+ | Gin | 8180 |
| Worker | Go 1.21+ | stdlib + goroutines | - |
| ras-adapter | Go 1.21+ | khorevaa/ras-client | 8188 |
| batch-service | Go 1.21+ | stdlib | 8187 |
| Orchestrator | Python 3.11+ | Django 4.2+ DRF | 8200 |
| Frontend | TypeScript | React 18.2 + Ant Design | 5173 |

**Data:** PostgreSQL 15, Redis 7, ClickHouse
**Monitoring:** Prometheus, Grafana, Jaeger

## MCP Servers

- `mcp-dap-server` - Go debugging via Delve (SSE transport)
- `chrome-devtools` - Browser control for web debugging (альтернатива chrome-debug.py)

### Chrome DevTools Setup

**Перед отладкой frontend** нужно запустить Chromium с remote debugging:

```bash
chromium --remote-debugging-port=9222 --no-first-run http://localhost:5173 &
```

> **Важно:** Chromium установлен нативно в WSL (`/usr/sbin/chromium`), НЕ использовать Windows Chrome.

### Отладка Frontend (ПРИОРИТЕТНЫЙ СПОСОБ)

**Использовать `scripts/dev/chrome-debug.py`** — работает напрямую через CDP, не требует MCP:

```bash
# Проверить console ошибки (перезагружает страницу, ждёт 3 сек)
./scripts/dev/chrome-debug.py console -e

# Все console сообщения
./scripts/dev/chrome-debug.py console

# Скриншот
./scripts/dev/chrome-debug.py screenshot

# Выполнить JS
./scripts/dev/chrome-debug.py eval "document.title"

# Перезагрузить страницу
./scripts/dev/chrome-debug.py reload --hard

# Список страниц
./scripts/dev/chrome-debug.py pages

# Network запросы (только API)
./scripts/dev/chrome-debug.py network -a
```

**Преимущества над MCP:**
- Не требует `/mcp` переподключения
- Автоматически перезагружает страницу
- Работает в CI/CD
- Фильтрует ошибки из коробки

### Альтернатива: chrome-devtools MCP

Если нужен интерактивный контроль браузера (клики, ввод текста):

1. Переподключить MCP: `/mcp`
2. Перезагрузить страницу: `navigate_page(type="reload")`
3. Получить ошибки: `list_console_messages(types=["error"])`

> **Ограничение:** MCP и chrome-debug.py не могут работать одновременно (CDP поддерживает только одно WebSocket соединение к странице).

See `docs/DEBUG_WITH_AI.md` for full guide.
