# CommandCenter1C - AI Agent Instructions

> Микросервисная платформа для централизованного управления 700+ базами 1С

---

## 🚨 КРИТИЧНО

**Дата обновления:** 2025-12-05
**Текущая фаза:** Phase 1, Week 2.5-3 (Core Functionality)
**Статус:** 🔄 Sprint 2.1-2.2 В ПРОЦЕССЕ (~25% готово) - Task Queue & Worker Integration
**Режим разработки:** Native WSL (USE_DOCKER=false в .env.local)
**Roadmap:** Balanced Approach (14-16 недель) - [docs/ROADMAP.md](docs/ROADMAP.md)

**API Version:** v2 (action-based) - см. [API_V2_UNIFICATION_ROADMAP.md](docs/roadmaps/API_V2_UNIFICATION_ROADMAP.md)
- Frontend → API Gateway (8180) `/api/v2/*`
- v1 endpoints deprecated (Sunset: 2026-03-01)

**Завершено:** Sprint 1.1-1.4 (Infrastructure, Models, OData, RAS Integration) ✅
**В работе:** Sprint 2.1 (Celery ↔ Worker) 🟡 30%, Sprint 2.2 (Template Engine) 🟡 20%
**Критичные GAPs:** Orchestrator → Worker integration, Template Engine, Real Operation Execution

---

## 🚀 БЫСТРЫЙ СТАРТ

**Запуск проекта:**
```bash
# из корня проекта
./scripts/dev/start-all.sh        # Умный запуск с автопересборкой
./scripts/dev/health-check.sh     # Проверить статус
```

**Управление сервисами:**
```bash
./scripts/dev/restart-all.sh        # Перезапуск всех сервисов
./scripts/dev/restart.sh <service>  # Один сервис
./scripts/dev/logs.sh <service>     # Просмотр логов
./scripts/dev/stop-all.sh           # Остановить всё
```

**Качество кода:**
```bash
./scripts/dev/lint.sh              # Проверить всё (tsc, eslint, ruff, go vet)
./scripts/dev/lint.sh --fix        # Авто-исправление
./scripts/dev/lint.sh --ts         # Только TypeScript
```

**Django shell (для проверки данных):**
```bash
cd orchestrator && source venv/bin/activate
python manage.py shell -c "from apps.operations.models import BatchOperation; print(BatchOperation.objects.count())"
# Или интерактивно:
python manage.py shell
```

**Доступные сервисы:**
- `orchestrator`, `celery-worker`, `celery-beat` (Python/Django)
- `api-gateway`, `worker`, `ras-adapter` (Go)
- `frontend` (React)

---

## 🛠️ ДОСТУПНЫЕ ИНСТРУМЕНТЫ

**Skills (используй через Skill tool):**
- `cc1c-devops` - управление сервисами, логи, health checks
- `cc1c-navigator` - навигация по monorepo
- `cc1c-odata-integration` - работа с OData batch операциями
- `cc1c-service-builder` - создание Go/Django/React компонентов
- `cc1c-sprint-guide` - отслеживание прогресса в roadmap
- `cc1c-test-runner` - запуск и отладка тестов

**Slash Commands (используй через SlashCommand tool):**
- `/dev-start` - запустить все сервисы
- `/check-health` - проверить статус всех сервисов
- `/restart-service <name>` - перезапустить сервис
- `/run-migrations` - применить миграции Django
- `/test-all` - запустить все тесты
- `/build-docker` - собрать Docker образы

**MCP Servers для AI-powered debugging:**
- `mcp-dap-server` - отладка Go сервисов через Delve (SSE transport)
  - Autonomous bug finding and fixing
  - Live state inspection (threads, stack traces, variables)
  - Expression evaluation in debug context
  - Breakpoint management
  - См. [DEBUG_WITH_AI.md](docs/DEBUG_WITH_AI.md) для полного руководства

**Endpoints для проверки:**
- Frontend: http://localhost:5173
- API Gateway: http://localhost:8180/health
- Orchestrator: http://localhost:8200/admin (Admin Panel)
- Orchestrator API: http://localhost:8200/api/docs (Swagger)
- ras-adapter: http://localhost:8188/health
- batch-service: http://localhost:8187/health
- Flower (Celery UI): http://localhost:5555

**Мониторинг (порты зависят от режима):**

| Сервис | Native (systemd) | Docker |
|--------|------------------|--------|
| Prometheus | http://localhost:9090 | http://localhost:9090 |
| Grafana | http://localhost:3000 | http://localhost:5000 |
| Jaeger | требует установки | http://localhost:16686 |

> **Note:** Режим определяется переменной `USE_DOCKER` в `.env.local`

---

## ⚠️ КЛЮЧЕВЫЕ ОГРАНИЧЕНИЯ

1. **Транзакции 1С < 15 секунд** - КРИТИЧНО! Разбивай на короткие транзакции
2. **Connection limits:** max 3-5 concurrent connections per база 1С
3. **Worker pool size:** Phase 1: 10-20, Production: auto-scale по queue depth
4. **OData batch:** 100-500 records/batch для групповых операций
5. **Rate limiting:** 100 req/min per user (default)

---

## 📐 ПРАВИЛА РАЗРАБОТКИ

1. **Работаем ТОЛЬКО по Balanced roadmap** (docs/ROADMAP.md)
2. **Следуй monorepo структуре** - не создавай файлы в неправильных местах
3. **Go shared code** → go-services/shared/ (auth, logger, config)
4. **Django apps независимы** → минимум cross-app imports
5. **Frontend → API Gateway ТОЛЬКО** → без прямых вызовов Orchestrator
6. **Тесты обязательны** → coverage > 70%
7. **Используй ./scripts/dev/*.sh** для локальной разработки
8. **OpenAPI Contract-First** → изменения API начинаются с обновления спецификации

---

## 🔖 OPENAPI CONTRACTS (Contract-First Development)

**Единый источник правды для REST API контрактов.**

### Структура

```
contracts/
├── ras-adapter/openapi.yaml         # Спецификация ras-adapter API
├── api-gateway/openapi.yaml         # (будущее)
└── scripts/
    ├── generate-all.sh              # Генерация всех клиентов
    ├── validate-specs.sh            # Валидация спецификаций
    └── check-breaking-changes.sh    # Проверка breaking changes
```

### Workflow изменения API

1. **Обновить OpenAPI спецификацию** (`contracts/<service>/openapi.yaml`)
2. **Валидировать:** `./contracts/scripts/validate-specs.sh`
3. **Сгенерировать клиенты:** `./contracts/scripts/generate-all.sh`
4. **Реализовать handlers** используя сгенерированные типы
5. **Закоммитить** (pre-commit hook автоматически проверит)

### Генерация

**Автоматическая (при запуске):**
```bash
./scripts/dev/start-all.sh  # Phase 1.5: Генерация API клиентов
```

**Ручная:**
```bash
./contracts/scripts/generate-all.sh         # Все сервисы
./contracts/scripts/generate-all.sh --force # Принудительно
```

**Результаты:**
- **Go server types:** `go-services/<service>/internal/api/generated/server.go`
- **Python client:** `orchestrator/apps/databases/clients/generated/<service>_api_client/`

### Git Hooks

Активируй pre-commit hook для автоматической валидации:

```bash
git config core.hooksPath .githooks
```

При коммите изменений в `contracts/**/*.yaml` автоматически:
1. Валидация OpenAPI спецификации
2. Проверка breaking changes
3. Регенерация клиентов

### Best Practices

- **ВСЕГДА** используй параметр `cluster_id` (не `cluster`) для infobases endpoints
- **Все параметры:** `snake_case` (соответствие Go/Python конвенциям)
- **Breaking changes:** требуют версионирования API (v1 → v2) и deprecation notice
- **Переиспользование:** используй `$ref` для общих схем

**Подробности:** См. [contracts/README.md](contracts/README.md)

---

## 📋 АРХИТЕКТУРА

### Краткая схема

```
User → Frontend (React:5173)
  ↓
API Gateway (Go:8180) → Orchestrator (Django:8200) → PostgreSQL:5432
                          ↓
                        Redis:6379 → Celery
                          ↓
                    Go Worker Pool (x2) → OData → 1C Bases
                          ↓
                    ras-adapter (Go:8188) → RAS (1545)
```

**Поток данных:**
```
User → Frontend → API Gateway → Orchestrator → Celery → Redis
→ Worker → Redis Pub/Sub → RAS Adapter → RAS → 1C
→ Results → WebSocket → User
```

### Структура monorepo

```
command-center-1c/
├── go-services/              # Go микросервисы
│   ├── api-gateway/          # HTTP router, auth, rate limit
│   ├── worker/               # Parallel processing (x2 replicas)
│   ├── ras-adapter/          # RAS integration (Week 4: replaces cluster-service + ras-grpc-gw)
│   ├── batch-service/        # Batch operations (в разработке)
│   └── shared/               # Общий код (auth, logger, metrics, models)
├── orchestrator/             # Python/Django
│   ├── apps/
│   │   ├── databases/        # Database CRUD, OData, health checks
│   │   ├── operations/       # Operation management
│   │   └── templates/        # Template engine
│   └── config/               # Django settings
├── frontend/                 # React + TypeScript
│   └── src/
│       ├── api/              # API client
│       ├── components/       # UI components
│       ├── pages/            # App pages
│       └── stores/           # State management (Zustand)
├── infrastructure/
│   ├── docker/               # Dockerfiles
│   ├── k8s/                  # Kubernetes manifests
│   └── monitoring/           # Prometheus + Grafana configs
├── docs/                     # Документация
├── scripts/dev/              # Dev scripts
└── docker-compose.yml        # Dev environment
```

### Технологический стек

| Компонент | Язык | Фреймворк | Порт |
|-----------|------|-----------|------|
| **API Gateway** | Go 1.21+ | Gin | 8180 |
| **Workers** | Go 1.21+ | stdlib + goroutines | - |
| **ras-adapter** | Go 1.21+ | khorevaa/ras-client | 8188 |
| **batch-service** | Go 1.21+ | stdlib | 8187 |
| **Orchestrator** | Python 3.11+ | Django 4.2+ DRF | 8200 |
| **Task Queue** | Python 3.11+ | Celery 5.3+ | - |
| **Frontend** | TypeScript | React 18.2 + Ant Design | 5173 |

**Data:** PostgreSQL 15 (5432), Redis 7 (6379), ClickHouse (8123, 9000)
**Monitoring:** Prometheus (9090), Grafana (3000 native / 5000 docker), Jaeger (16686 docker only)

---

## 🔌 КРИТИЧНЫЕ СЕРВИСЫ

### Сервисы и их назначение

| Сервис | Назначение | Порт | Status |
|--------|------------|------|--------|
| **ras-adapter** | Управление кластерами + Lock/Unlock через RAS | 8188 | ✅ ACTIVE |
| **batch-service** | Установка расширений (.cfe) через 1cv8.exe | 8187 | ⚠️ In Dev |
| ~~cluster-service~~ | ~~Мониторинг кластеров~~ | 8088 | ❌ DEPRECATED |
| ~~ras-grpc-gw~~ | ~~Gateway для RAS~~ | 8081/9999 | ❌ DEPRECATED |

> **Note:** Порты 8180, 8187, 8188, 8200 выбраны вне Windows reserved ranges (7913-8012, 8013-8112)

**ras-adapter (Week 4 NEW):**
- Direct RAS protocol integration (khorevaa/ras-client)
- Redis Pub/Sub event handlers для Worker State Machine
- REST API для external clients
- **Performance:** 30-50% latency improvement (1 network hop вместо 2)

**Подробности:** См. [1C_ADMINISTRATION_GUIDE.md](docs/1C_ADMINISTRATION_GUIDE.md)

---

## 🔧 ПЕРВОНАЧАЛЬНАЯ НАСТРОЙКА

**Prerequisites:**
- Python 3.11+, Go 1.21+, Node.js 18+
- **Native режим (WSL):** PostgreSQL, Redis через systemd (pacman -S postgresql redis)
- **Docker режим:** Docker 20.10+, Docker Compose 2.0+

**Setup:**
```bash
git clone <repo>
cd command-center-1c
cp .env.local.example .env.local
# Отредактировать .env.local:
#   DB_HOST=localhost, REDIS_HOST=localhost
#   USE_DOCKER=false  # для Native режима (WSL/Linux)
#   USE_DOCKER=true   # для Docker режима

# Python
cd orchestrator && python -m venv venv
source venv/bin/activate && pip install -r requirements.txt && cd ..

# Node.js
cd frontend && npm install && cd ..

# Go (опционально - автоматически при старте)
cd go-services/api-gateway && go mod download && cd ../..

# Start all
./scripts/dev/start-all.sh
```

**Native режим (WSL/Arch Linux):**
```bash
# Установка и включение сервисов
sudo pacman -S postgresql redis prometheus grafana
sudo systemctl enable --now postgresql redis

# Мониторинг (опционально)
sudo systemctl enable --now prometheus grafana
# Jaeger: yay -S jaeger (из AUR) или скачать бинарник
```

---

## 🧪 ТЕСТИРОВАНИЕ И ЛИНТИНГ

**Линтинг (все компоненты):**
```bash
./scripts/dev/lint.sh              # tsc + eslint + ruff + go vet
./scripts/dev/lint.sh --fix        # Авто-исправление
```

**Тесты:**
```bash
# Django
cd orchestrator && source venv/bin/activate && pytest

# Go
cd go-services/api-gateway && go test ./...

# Frontend
cd frontend && npm test
```

**Через Skill:**
```
Используй Skill: cc1c-test-runner
```

---

## 🐛 TROUBLESHOOTING

**Распространенные проблемы:**

1. **Database connection error:**
   - Native: `systemctl status postgresql`, `pg_isready -h localhost`
   - Docker: `docker ps`, `docker exec -it postgres pg_isready`

2. **Redis connection error:**
   - Native: `systemctl status redis`, `redis-cli ping`
   - Docker: `docker exec -it redis redis-cli ping`

3. **Grafana/Jaeger показывает connection_refused на System Status:**
   - Native режим: Grafana на порту **3000** (не 5000!), Jaeger требует отдельной установки
   - Проверь: `systemctl status grafana prometheus`
   - Установка Jaeger: `yay -S jaeger` или скачать с GitHub

4. **Мониторинг не запускается:**
   - `./scripts/dev/start-monitoring.sh` - запуск в зависимости от режима
   - Native: проверь `systemctl status prometheus grafana`

**Полный troubleshooting:** [LOCAL_DEVELOPMENT_GUIDE.md](docs/LOCAL_DEVELOPMENT_GUIDE.md#troubleshooting)

**Используй Skill для диагностики:**
```
Skill: cc1c-devops → автоматическая диагностика и починка
```

---

## 📖 ДОКУМЕНТАЦИЯ

**⭐ Обязательно:**
- [ROADMAP.md](docs/ROADMAP.md) - Balanced план (14-16 недель)
- [START_HERE.md](docs/START_HERE.md) - Быстрый старт (2 мин)
- [LOCAL_DEVELOPMENT_GUIDE.md](docs/LOCAL_DEVELOPMENT_GUIDE.md) - Полное руководство

**Практические гайды:**
- [1C_ADMINISTRATION_GUIDE.md](docs/1C_ADMINISTRATION_GUIDE.md) - RAS/RAC, endpoint management
- [ODATA_INTEGRATION.md](docs/ODATA_INTEGRATION.md) - Batch операции
- [DJANGO_CLUSTER_INTEGRATION.md](docs/DJANGO_CLUSTER_INTEGRATION.md) - Интеграция Django ↔ RAS

**Event-Driven Architecture:**
- [EVENT_DRIVEN_EXECUTIVE_SUMMARY.md](docs/EVENT_DRIVEN_EXECUTIVE_SUMMARY.md) - Executive Summary
- [EVENT_DRIVEN_ROADMAP.md](docs/EVENT_DRIVEN_ROADMAP.md) - Детальный roadmap (14 дней)
- [EVENT_DRIVEN_ARCHITECTURE.md](docs/architecture/EVENT_DRIVEN_ARCHITECTURE.md) - Дизайн (82KB)

**История:**
- [Sprint Progress](docs/archive/sprints/) - История спринтов
- [Roadmap Variants](docs/archive/roadmap_variants/) - MVP/Enterprise варианты (архив)

---

## 🔨 BUILD SYSTEM

**Умная автопересборка (Smart Rebuild):**
```bash
./scripts/dev/start-all.sh           # Умный запуск с автопересборкой
./scripts/dev/start-all.sh --force-rebuild  # Принудительная пересборка
./scripts/dev/restart-all.sh         # Умный перезапуск
```

**Как работает:**
1. Автоматическое определение изменений (сравнивает timestamps)
2. Выборочная пересборка ТОЛЬКО измененных сервисов
3. Проверка `go-services/shared/` → пересобирает ВСЕ если изменен
4. ВСЕГДА использует бинарники (НЕТ `go run`)

**Преимущества:**
- ✅ Windows Firewall больше НЕ спрашивает разрешение
- ✅ Правильные имена процессов (`cc1c-api-gateway.exe` вместо `main.exe`)
- ✅ Экономия 75-89% времени (пересборка только измененного)

**Формат бинарников:** `bin/cc1c-<service-name>.exe`

**Подробности:** [scripts/dev/README.md](scripts/dev/README.md)

---

**Версия:** 3.2
**Последнее обновление:** 2025-12-05

**Изменения v3.2:**
- Добавлен `./scripts/dev/lint.sh` для проверки качества кода
- Объединены секции тестирования и линтинга
- Исправлен путь в БЫСТРЫЙ СТАРТ (относительный вместо абсолютного)

**Изменения v3.1:**
- Обновлена документация для Native WSL режима (USE_DOCKER=false)
- Добавлена таблица портов мониторинга для Native vs Docker режимов
- Grafana: 3000 (native) vs 5000 (docker)
- Jaeger: требует отдельной установки в native режиме
- Обновлён troubleshooting для dual-mode setup

**Изменения v3.0:**
- Радикальное сокращение: 12.5k → ~4.5k токенов (65% reduction)
- Убран избыточный Troubleshooting → заменен ссылкой на docs/
- Детальные описания сервисов → краткая таблица
- Добавлен явный список Skills для использования через Skill tool
- Сохранена вся критичная информация для AI агентов
