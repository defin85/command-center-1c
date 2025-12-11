# Roadmap: Унификация транспорта и Saga Orchestration

> **Статус:** In Progress v2.7
> **Версия:** 2.7
> **Создан:** 2025-12-10
> **Обновлён:** 2025-12-11
> **Автор:** Claude Code
>
> ### Текущий прогресс
>
> | Фаза | Статус | Прогресс | Commits |
> |------|--------|----------|---------|
> | **Phase 0** | ✅ Done | 9/10 задач | `4bc7539`, `b57e88d` |
> | **Phase 1** | 🔄 In Progress | 6/8 задач | `23e7b75`, `2be71be` |
> | **Phase 1.5** | ⏳ Pending | 0/11 задач | - |
> | **Phase 1.6** | ⏳ Pending | 0/11 задач | - |
> | **Phase 2** | ⏳ Pending | 0/12 задач | - |
> | **Phase 3** | ⏳ Pending | 0/8 задач | - |
>
> **Следующий шаг:** Добавить lock/unlock/terminate handlers в ras-adapter (Phase 1)
>
> **Changelog v2.7:** Добавлена таблица прогресса
>
> **Changelog v2.6:** Phase 1 реализован (commit 23e7b75):
> - shared/ras: types.go, channels.go с тестами
> - ras-adapter: block_handler.go, unblock_handler.go
> - Worker: StreamClient, ResponseWaiter, dual-mode в ras_handler.go
> - Feature flag: RAS_TRANSPORT=http|streams
>
> **Changelog v2.5:** Phase 0 реализован (commit 4bc7539):
> - Django → Worker: LPUSH → XADD (redis_client.py)
> - Worker consume: BRPOP → XREADGROUP (stream_consumer.go)
> - Results: LPUSH → XADD events:worker:completed/failed
> - Django subscribe: events:worker:* via XREADGROUP
> - Удалён legacy код: consumer.go, redis.go, pool/
>
> **Changelog v2.4:** Верификация против исходного кода:
> - Фаза 0: добавлена миграция results queue (consumer.go:132 LPUSH → XADD)
> - Фаза 2: добавлена ссылка на scheduler/locks.go как базу для Resource Manager
> - Фаза 3: добавлен extension_handler.go (~372 строк) в cleanup list

---

## Цель

Унифицировать транспорт между сервисами на Redis Streams и реализовать Saga Orchestration для надёжного выполнения распределённых транзакций над 700+ базами 1С.

### Бизнес-требования

- **Много пользователей** — параллельные запросы на разные базы
- **Консистентность** — "умная транзакция" в рамках workflow
- **Isolation** — пока workflow работает с базой, другие ждут
- **Compensation** — откат при ошибке на любом шаге
- **Durability** — состояние workflow не теряется при падении

---

## Архитектура

### Полная архитектура системы

```mermaid
flowchart TB
    subgraph Frontend
        UI[React :5173]
    end

    subgraph API["API Layer"]
        GW[API Gateway :8180]
    end

    subgraph Coordination["Coordination Layer"]
        Django[Django Orchestrator :8200]
        Worker[Go Worker<br/>Saga Orchestrator]
        RM[Resource Manager]
    end

    subgraph Execution["Execution Layer"]
        RAS[ras-adapter :8188<br/>RAS операции]
        ODA[odata-adapter :8189<br/>CRUD данных]
        Batch[batch-service :8187<br/>Простые пакетные]
        Designer[designer-agent :8086<br/>Агент конфигуратора]
        Backup[backup-service :8089<br/>Backup/DR]
    end

    subgraph Storage["Storage"]
        PG[(PostgreSQL)]
        Redis[(Redis Streams)]
        S3[(S3/MinIO)]
    end

    subgraph 1C["1С Cluster"]
        RASServer[RAS Server :1545]
        ODataAPI[OData REST API]
        Bin1C[1cv8.exe CLI]
        AgentMode[1cv8.exe /AgentMode<br/>SSH :22]
        IBCMD[ibcmd]
        Bases[(1С Databases)]
    end

    UI -->|HTTP| GW
    GW -->|HTTP| Django
    Django -->|SQL| PG
    Django -->|"XADD commands:worker:*"| Redis
    Redis -->|"XREADGROUP"| Worker
    Worker --> RM
    RM -->|"Lock/Unlock"| Redis

    Worker -->|"XADD commands:ras:*"| Redis
    Worker -->|"XADD commands:odata:*"| Redis
    Worker -->|"XADD commands:batch:*"| Redis
    Worker -->|"XADD commands:designer:*"| Redis
    Worker -->|"XADD commands:backup:*"| Redis

    Redis -->|"XREADGROUP"| RAS
    Redis -->|"XREADGROUP"| ODA
    Redis -->|"XREADGROUP"| Batch
    Redis -->|"XREADGROUP"| Designer
    Redis -->|"XREADGROUP"| Backup

    RAS -->|"XADD events:ras:*"| Redis
    ODA -->|"XADD events:odata:*"| Redis
    Batch -->|"XADD events:batch:*"| Redis
    Designer -->|"XADD events:designer:*"| Redis
    Backup -->|"XADD events:backup:*"| Redis

    Redis -->|"XREADGROUP events:*"| Worker
    Worker -->|"XADD events:worker:*"| Redis
    Redis -->|"XREADGROUP"| Django

    RAS -->|"RAS Protocol"| RASServer
    ODA -->|"HTTP REST"| ODataAPI
    Batch -->|"subprocess"| Bin1C
    Designer -->|"SSH"| AgentMode
    Backup -->|"subprocess"| IBCMD
    Backup -->|"upload/download"| S3

    RASServer --> Bases
    ODataAPI --> Bases
    Bin1C --> Bases
    AgentMode --> Bases
    IBCMD --> Bases

    style Redis fill:#9f9
    style Worker fill:#9f9
    style RM fill:#ff9
    style ODA fill:#f9f
    style Designer fill:#f9f
```

### Execution Layer — все адаптеры

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         EXECUTION LAYER                                                │
│                                   (stateless адаптеры к 1С)                                            │
├───────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                        │
│  ras-adapter        odata-adapter       batch-service       designer-agent      backup-service        │
│  "Управление        "CRUD данных"       "Простые            "Агент              "Backup/DR"           │
│   кластером"                             пакетные"           конфигуратора"                           │
│  ✅ EXISTS          🔴 NEW              ✅ EXISTS           🔴 NEW              🔴 PLANNED            │
│  :8188              :8189               :8187               :8086               :8089                 │
│                                                                                                        │
│  • lock/unlock      • read records      • init OData        • extensions        • dump → .dt          │
│  • block/unblock    • write records     • simple cmds       • UpdateDBCfg       • restore             │
│  • terminate        • batch CRUD                            • load/dump cfg     • replicate           │
│  • get sessions     • queries                               • EPF/ERF export                          │
│                                                                                                        │
│  Протокол:          Протокол:           Инструмент:         Протокол:           Инструмент:           │
│  RAS TCP :1545      HTTP OData REST     1cv8.exe CLI        SSH → /AgentMode    ibcmd                 │
│                                                                                                        │
│  SLA: секунды       SLA: <15 сек        SLA: секунды        SLA: секунды        SLA: мин-часы         │
│                     (КРИТИЧНО!)                             (persistent conn)                          │
│                                                                                                        │
│  commands:ras:*     commands:odata:*    commands:batch:*    commands:designer:* commands:backup:*     │
│  events:ras:*       events:odata:*      events:batch:*      events:designer:*   events:backup:*       │
│                                                                                                        │
└───────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                   │
                                                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                            1С CLUSTER                                                  │
│                                                                                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ RAS Server   │  │ OData API    │  │ 1cv8.exe     │  │ 1cv8.exe     │  │ ibcmd        │             │
│  │ :1545        │  │ :80/443      │  │ CLI mode     │  │ /AgentMode   │  │ subprocess   │             │
│  │              │  │              │  │              │  │ SSH :22      │  │              │             │
│  │ Управление   │  │ CRUD данных  │  │ Простые      │  │ Конфигуратор │  │ Backup/DR    │             │
│  │ кластером    │  │ (требует     │  │ команды      │  │ persistent   │  │ Репликация   │             │
│  │              │  │  init!)      │  │              │  │              │  │              │             │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘             │
│         │                 │                 │                 │                 │                      │
│         └─────────────────┴─────────────────┴─────────────────┴─────────────────┘                      │
│                                                   │                                                    │
│                                            1С Databases                                                │
└───────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### OData: зависимость от batch-service

OData REST API базы 1С требует предварительной инициализации доступа к метаданным.

```
┌─────────────────────────────────────────────────────────────────┐
│                    OData Initialization Flow                     │
└─────────────────────────────────────────────────────────────────┘

                    1. Init OData Access
Worker ─────────────────────────────────────────► batch-service
                                                       │
                                                       ▼
                                            Запускает расширение
                                            или внешнюю обработку
                                            в базе 1С
                                                       │
                                                       ▼
                                            База открывает
                                            OData REST API
                                                       │
                    2. CRUD операции                   │
Worker ─────────────────────────────────────────► odata-adapter
                                                       │
                                                       ▼
                                            HTTP запросы к
                                            OData REST API базы
```

### Двухуровневая архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                    COORDINATION LAYER                            │
│              (workflows, бизнес-логика, блокировки)              │
├─────────────────────────────────────────────────────────────────┤
│  Django         — API, валидация, состояние операций            │
│  Worker         — Saga Orchestrator, State Machines             │
│  Resource Mgr   — Distributed locks на базы данных              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Redis Streams (единый транспорт)
                              │
                              │ commands:worker:*    (Django → Worker)
                              │ commands:ras:*       (Worker → ras-adapter)
                              │ commands:odata:*     (Worker → odata-adapter)
                              │ commands:batch:*     (Worker → batch-service)
                              │ commands:designer:*  (Worker → designer-agent)
                              │ commands:backup:*    (Worker → backup-service)
                              │ events:*             (Results → Worker/Django)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EXECUTION LAYER                               │
│              (stateless адаптеры к 1С)                           │
├─────────────────────────────────────────────────────────────────┤
│  ras-adapter     — RAS операции (lock, unlock, sessions)        │
│  odata-adapter   — CRUD данных (read, write, batch, queries)    │
│  batch-service   — Простые пакетные (init OData, simple cmds)   │
│  designer-agent  — Агент конфигуратора (extensions, config)     │
│  backup-service  — Disaster Recovery (dump, restore, replicate) │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Native протоколы
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         1С CLUSTER                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Текущее состояние (проблема: 3 разных транспорта)

```mermaid
flowchart TB
    subgraph Coordination["Coordination Layer"]
        Django[Django Orchestrator :8200]
        Worker[Go Worker]
    end

    subgraph Execution["Execution Layer"]
        RAS[ras-adapter :8188]
        Batch[batch-service :8187]
    end

    subgraph Storage["Storage"]
        Redis[(Redis)]
    end

    Django -->|"❌ LPUSH (LIST)"| Redis
    Redis -->|"❌ BRPOP (LIST)"| Worker
    Worker -->|"❌ HTTP POST /api/v2/*"| RAS
    Worker -->|"❌ HTTP POST /api/install"| Batch
    Worker -->|"❌ LPUSH results (LIST)"| Redis
    Worker -->|"PUBLISH (Pub/Sub)"| Redis
    Redis -->|"BRPOP results"| Django
    Redis -->|"SUBSCRIBE + XREADGROUP"| Django

    style Django fill:#f99
    style Worker fill:#f99
    style RAS fill:#f99
    style Batch fill:#f99
```

**Проблемы:**
| Путь | Транспорт | Проблема |
|------|-----------|----------|
| Django → Worker | Redis LIST (`cc1c:operations:v1`) | At-most-once, нет retry |
| Worker → ras-adapter | HTTP REST (`/api/v2/*`) | Синхронный, blocking |
| Worker → batch-service | **HTTP REST** (`/api/install`) | Синхронный, blocking |
| Results → Django | Redis LIST | At-most-once |
| Events → Django | Pub/Sub + Streams (mixed) | Сложно, не единообразно |

### Ключевые файлы для миграции

| Путь | Файлы | Изменение |
|------|-------|-----------|
| Django → Worker | `redis_client.py`, `operations_service.py` | LPUSH → XADD |
| Worker consume | `consumer.go` | BRPOP → XREADGROUP |
| Worker → ras-adapter | `rasadapter/client.go`, `ras_handler.go` | HTTP → XADD |
| Worker → batch-service | `extension_handler.go` | HTTP → XADD |
| ras-adapter | `cmd/main.go`, новые handlers | HTTP → XREADGROUP |
| batch-service | `cmd/main.go`, новые handlers | HTTP → XREADGROUP |
| Events → Django | `event_subscriber.py`, `publisher.go` | Унификация на Streams |

---

## Redis Streams vs Redis LIST

| Аспект | LIST (сейчас) | STREAM (целевой) |
|--------|---------------|------------------|
| Гарантия | At-most-once | At-least-once |
| После чтения | Удаляется | Сохраняется |
| Consumer Groups | ❌ | ✅ |
| Acknowledge | ❌ | ✅ XACK |
| Retry failed | ❌ Потеряно | ✅ XPENDING + XCLAIM |
| История | ❌ | ✅ |
| Масштабирование | BRPOP конкуренция | Consumer Groups |

---

## Saga Pattern: Workflow как транзакция

### Пример: extension_install

```
Workflow: extension_install (User2 на DB-2, DB-5)

┌─────────────────────────────────────────────────────────────────┐
│  Step 1: acquire_locks(DB-2, DB-5)                              │
│          → compensation: release_locks()                        │
├─────────────────────────────────────────────────────────────────┤
│  Step 2: lock_scheduled_jobs()              [ras-adapter]       │
│          → compensation: unlock_scheduled_jobs()                │
├─────────────────────────────────────────────────────────────────┤
│  Step 3: terminate_sessions()               [ras-adapter]       │
│          → compensation: (none)                                 │
├─────────────────────────────────────────────────────────────────┤
│  Step 4: install_extension()                [batch-service]     │
│          → compensation: uninstall_extension()                  │
├─────────────────────────────────────────────────────────────────┤
│  Step 5: unlock_scheduled_jobs()            [ras-adapter]       │
│          → compensation: (none)                                 │
├─────────────────────────────────────────────────────────────────┤
│  Step 6: release_locks()                                        │
│          → compensation: (none)                                 │
└─────────────────────────────────────────────────────────────────┘

Если Step 4 падает → выполняем compensations:
  unlock_scheduled_jobs() → release_locks()
```

### Resource Manager: блокировки баз

```
База DB-1:
├── Owner: workflow-123 (User1)
├── Operation: update_release
├── Locked at: 2025-12-11 10:00
├── TTL: 15 минут
└── Queue: [workflow-456 (User3) waiting...]

База DB-2:
├── Owner: workflow-123 (User1)
├── Operation: update_release
└── Queue: [workflow-789 (User2) waiting...]
```

---

## Фазы миграции

### Фаза 0: Миграция Django → Worker на Streams

**Цель:** Заменить Redis LIST на Redis Streams для надёжной доставки задач.

**Изменения:**

| Компонент | Было | Станет |
|-----------|------|--------|
| Django | `LPUSH cc1c:operations:v1` | `XADD commands:worker:operations` |
| Worker | `BRPOP cc1c:operations:v1` | `XREADGROUP ... commands:worker:operations` |
| Worker (results) | `LPUSH cc1c:operations:results:v1` | `XADD events:worker:completed` |
| Django (results) | `BRPOP results` | `XREADGROUP events:worker:*` |

**Файлы для изменения:**

```
orchestrator/apps/operations/redis_client.py          # LPUSH → XADD
go-services/worker/internal/queue/consumer.go         # BRPOP → XREADGROUP
go-services/worker/cmd/main.go                        # Consumer Group setup
```

**Subtasks:**
- [x] 0.1: Создать consumer group `worker-group` при старте Worker ✅ `stream_consumer.go:EnsureConsumerGroup()`
- [x] 0.2: Заменить `BRPOP` на `XREADGROUP` в consumer.go ✅ `stream_consumer.go:Start()`
- [x] 0.3: Добавить `XACK` после успешной обработки ✅ `stream_consumer.go:ackMessage()`
- [x] 0.4: Реализовать retry через `XPENDING` + `XCLAIM` ✅ `stream_consumer.go:claimStalledMessages()`
- [x] 0.5: Заменить `LPUSH` на `XADD` в Django redis_client.py ✅ `redis_client.py:enqueue_operation_stream()`
- [x] 0.6: Обновить формат сообщения (добавить correlation_id) ✅ `redis_client.py:_create_envelope()`
- [x] 0.7: **Results queue:** Заменить `LPUSH results` на `XADD events:worker:*` ✅ `stream_consumer.go:publishCompletedResult()/publishFailedResult()`
- [x] 0.8: **Results queue:** Django подписка на `events:worker:*` вместо `BRPOP` ✅ `event_subscriber.py`
- [ ] 0.9: Integration tests ⏸️ **ОТЛОЖЕНО** — реализуем после Фазы 2 и ручной проверки работоспособности
- [x] 0.10: Мониторинг: pending messages, consumer lag ✅ `stream_consumer.go:GetStreamDepth()/GetPendingCount()`

**Критерии завершения:**
- [x] Worker читает из Stream вместо LIST
- [x] Acknowledge после успешной обработки
- [x] Retry зависших сообщений работает
- [ ] Zero message loss при restart Worker (ручная проверка, затем интеграционные тесты)

---

### Фаза 1: Миграция Worker → ras-adapter на Streams

**Цель:** Заменить HTTP вызовы на Redis Streams для async коммуникации.

**Изменения:**

| Компонент | Было | Станет |
|-----------|------|--------|
| Worker | HTTP POST к ras-adapter | `XADD commands:ras:*` |
| ras-adapter | HTTP handlers | Redis Streams consumer |

**Новые Streams:**

```
commands:ras:lock           # lock_scheduled_jobs
commands:ras:unlock         # unlock_scheduled_jobs
commands:ras:block          # block_sessions
commands:ras:unblock        # unblock_sessions
commands:ras:terminate      # terminate_sessions

events:ras:completed        # Успешные результаты
events:ras:failed           # Ошибки
```

**Файлы для создания/изменения:**

```
# Worker
go-services/worker/internal/processor/ras_handler.go     # HTTP → Stream publish
go-services/worker/internal/events/ras_subscriber.go     # NEW: подписка на events:ras:*

# ras-adapter (handlers уже есть, нужно подключить)
go-services/ras-adapter/internal/eventhandlers/block_handler.go    # NEW
go-services/ras-adapter/internal/eventhandlers/unblock_handler.go  # NEW
go-services/ras-adapter/cmd/main.go                                # Регистрация handlers
```

**Subtasks:**
- [x] 1.1: Создать block_handler.go в ras-adapter ✅ `eventhandlers/block_handler.go`
- [x] 1.2: Создать unblock_handler.go в ras-adapter ✅ `eventhandlers/unblock_handler.go`
- [x] 1.3: Зарегистрировать все handlers в main.go ✅ `cmd/main.go`
- [x] 1.4: Worker: заменить HTTP вызовы на XADD ✅ `rasadapter/stream_client.go`
- [x] 1.5: Worker: подписаться на events:ras:* для получения результатов ✅ `rasadapter/response_waiter.go`
- [x] 1.6: Добавить timeout при ожидании события ✅ 30s default, configurable
- [ ] 1.7: Unit tests для handlers ⏸️ **ОТЛОЖЕНО**
- [ ] 1.8: Integration tests Worker ↔ ras-adapter ⏸️ **ОТЛОЖЕНО**

**Дополнительно реализовано:**
- `shared/ras/types.go` - RASCommand, RASResult с валидацией
- `shared/ras/channels.go` - константы каналов
- Dual-mode в `ras_handler.go` с feature flag `RAS_TRANSPORT`
- Thread-safe StreamClient с mutex protection

**Критерии завершения:**
- [x] Block/Unblock операции работают через Streams
- [ ] Все 5 RAS операций работают через Streams (осталось: lock, unlock, terminate)
- [ ] HTTP endpoints в ras-adapter deprecated
- [ ] Latency < 100ms (p99) (требуется тестирование)
- [ ] Success rate >= 99% (требуется тестирование)

---

### Фаза 1.5: Создание odata-adapter

**Цель:** Создать адаптер для CRUD операций с данными 1С через OData REST API.

**Новый сервис:**

```
go-services/odata-adapter/
├── cmd/
│   └── main.go
├── internal/
│   ├── api/                    # Health endpoint
│   ├── eventhandlers/
│   │   ├── query_handler.go    # SELECT operations
│   │   ├── create_handler.go   # INSERT operations
│   │   ├── update_handler.go   # UPDATE operations
│   │   ├── delete_handler.go   # DELETE operations
│   │   └── batch_handler.go    # Batch operations
│   ├── odata/
│   │   ├── client.go           # HTTP client to OData API
│   │   ├── query_builder.go    # OData query construction
│   │   └── response_parser.go  # Response parsing
│   └── config/
│       └── config.go
├── Dockerfile
└── README.md
```

**Streams:**

```
# Commands
commands:odata:query          # SELECT
commands:odata:create         # INSERT
commands:odata:update         # UPDATE
commands:odata:delete         # DELETE
commands:odata:batch          # Batch CRUD

# Events
events:odata:completed        # Успешные результаты
events:odata:failed           # Ошибки
```

**Subtasks:**
- [ ] 1.5.1: Создать структуру go-services/odata-adapter/
- [ ] 1.5.2: Реализовать OData HTTP client
- [ ] 1.5.3: Реализовать query_handler.go
- [ ] 1.5.4: Реализовать create_handler.go
- [ ] 1.5.5: Реализовать update_handler.go
- [ ] 1.5.6: Реализовать delete_handler.go
- [ ] 1.5.7: Реализовать batch_handler.go
- [ ] 1.5.8: Добавить поддержку OData $filter, $select, $expand
- [ ] 1.5.9: Unit tests
- [ ] 1.5.10: Integration tests
- [ ] 1.5.11: Dockerfile + docker-compose

**Критерии завершения:**
- [ ] Все CRUD операции работают через Streams
- [ ] Поддержка batch операций (100-500 records)
- [ ] SLA < 15 секунд для транзакций
- [ ] Success rate >= 99%

---

### Фаза 1.6: Создание designer-agent (Агент конфигуратора)

**Цель:** Создать сервис для работы с 1С через режим агента конфигуратора (SSH → /AgentMode).

**Преимущества перед batch-service:**

| Аспект | batch-service (subprocess) | designer-agent (SSH) |
|--------|---------------------------|----------------------|
| Запуск | Новый процесс на команду | Persistent connection |
| Подключение к базе | Каждый раз заново | Один раз |
| Overhead | Высокий | Низкий |
| Последовательные команды | N запусков | 1 соединение, N команд |

**Новый сервис:**

```
go-services/designer-agent/
├── cmd/
│   └── main.go
├── internal/
│   ├── api/                    # Health endpoint
│   ├── eventhandlers/
│   │   ├── extension_handler.go    # Установка/удаление расширений
│   │   ├── config_handler.go       # UpdateDBCfg, load/dump cfg
│   │   ├── epf_handler.go          # Экспорт/импорт EPF/ERF
│   │   └── metadata_handler.go     # Работа с метаданными
│   ├── ssh/
│   │   ├── client.go               # SSH client (Paramiko-style)
│   │   ├── session_pool.go         # Pool соединений к агентам
│   │   └── command.go              # Command builder
│   └── config/
│       └── config.go
├── Dockerfile
└── README.md
```

**Streams:**

```
# Commands
commands:designer:extension-install   # Установка расширения
commands:designer:extension-remove    # Удаление расширения
commands:designer:config-update       # UpdateDBCfg
commands:designer:config-load         # Загрузить конфигурацию
commands:designer:config-dump         # Выгрузить конфигурацию
commands:designer:epf-export          # Экспорт внешних обработок

# Events
events:designer:completed             # Успешные результаты
events:designer:failed                # Ошибки
events:designer:progress              # Прогресс (для длительных операций)
```

**Как работает агент конфигуратора:**

```bash
# 1. Запуск агента на сервере 1С
1cv8.exe DESIGNER /IBName "база" /AgentMode /AgentSSHHostKeyAuto /AgentBaseDir "path"

# 2. designer-agent подключается по SSH
ssh user@1c-server -p 22

# 3. Выполняет команды без перезапуска
> config load-cfg --file="config.cf"
> config update-db-cfg
> config dump-ext-files --ext-file="report.erf" --file="report_xml/"
```

**Subtasks:**
- [ ] 1.6.1: Создать структуру go-services/designer-agent/
- [ ] 1.6.2: Реализовать SSH client с поддержкой connection pooling
- [ ] 1.6.3: Реализовать session_pool для нескольких баз
- [ ] 1.6.4: Реализовать extension_handler.go
- [ ] 1.6.5: Реализовать config_handler.go
- [ ] 1.6.6: Реализовать epf_handler.go
- [ ] 1.6.7: Добавить health check и metrics
- [ ] 1.6.8: Unit tests
- [ ] 1.6.9: Integration tests с mock SSH server
- [ ] 1.6.10: Dockerfile + docker-compose
- [ ] 1.6.11: Документация по настройке агента на сервере 1С

**Критерии завершения:**
- [ ] Persistent SSH соединение к агенту конфигуратора
- [ ] Поддержка пула соединений для нескольких баз
- [ ] Операции с расширениями работают через Streams
- [ ] UpdateDBCfg работает через Streams
- [ ] Success rate >= 99%

**См. также:**
- [Режим агента конфигуратора](https://wonderland.v8.1c.ru/blog/rezhim-agenta-konfiguratora/)

---

### Фаза 2: Resource Manager + Saga Compensation

**Цель:** Реализовать блокировки баз и откат при ошибках.

**Компоненты:**

> **Примечание:** Существующий код `scheduler/locks.go` содержит базовые функции
> `AcquireLock`, `ReleaseLock`, `ExtendLock` — можно использовать как основу.

```
go-services/worker/internal/resourcemanager/
├── manager.go           # Acquire/Release locks (расширить scheduler/locks.go)
├── lock.go              # Lock struct, TTL, queue
└── store.go             # Redis storage for locks

go-services/worker/internal/saga/
├── orchestrator.go      # Saga execution engine
├── step.go              # Step with compensation
├── compensation.go      # Compensation executor
└── workflows/
    ├── extension_install.go
    ├── release_update.go
    ├── odata_batch.go   # OData batch workflow
    └── simple_ras.go    # lock/unlock/block/terminate
```

**Redis структуры для блокировок:**

```
# Lock на базу
resource:lock:{database_id}
├── owner: workflow-{id}
├── operation: extension_install
├── locked_at: timestamp
├── ttl: 900 (15 min)
└── correlation_id: uuid

# Очередь ожидания
resource:queue:{database_id}  # LIST of waiting workflow IDs

# Состояние workflow (для recovery)
workflow:state:{workflow_id}
├── current_step: 3
├── completed_steps: [1, 2]
├── compensation_stack: [unlock, release]
└── status: running|completed|compensating|failed
```

**Subtasks:**
- [ ] 2.1: Реализовать ResourceManager.AcquireLock()
- [ ] 2.2: Реализовать ResourceManager.ReleaseLock()
- [ ] 2.3: Реализовать очередь ожидания на базу
- [ ] 2.4: Реализовать Saga Orchestrator
- [ ] 2.5: Реализовать Compensation Executor
- [ ] 2.6: Workflow: extension_install с compensation
- [ ] 2.7: Workflow: simple_ras (обёртка для простых операций)
- [ ] 2.8: Workflow: odata_batch (OData операции с compensation)
- [ ] 2.9: Persistence состояния workflow в Redis
- [ ] 2.10: Recovery после restart Worker
- [ ] 2.11: Unit tests
- [ ] 2.12: Integration tests с имитацией failures

**Критерии завершения:**
- [ ] Конфликтующие операции на одну базу выстраиваются в очередь
- [ ] При ошибке выполняется compensation
- [ ] Состояние workflow переживает restart
- [ ] Нет deadlocks

---

### Фаза 3: Cleanup Legacy кода

**Цель:** Удалить устаревший код после стабилизации.

**Файлы для удаления:**

```
# Worker (HTTP клиенты к адаптерам)
go-services/worker/internal/rasadapter/client.go           # DELETE (~456 строк)
go-services/worker/internal/processor/ras_handler.go       # DELETE (~484 строк)
go-services/worker/internal/processor/cluster_resolver.go  # DELETE (~371 строк)
go-services/worker/internal/processor/extension_handler.go # DELETE (~372 строк) - HTTP к batch-service

# Django (старая очередь)
# Код LPUSH после миграции на XADD
```

**Subtasks:**
- [ ] 3.1: Удалить rasadapter/client.go
- [ ] 3.2: Удалить старый ras_handler.go
- [ ] 3.3: Удалить cluster_resolver.go
- [ ] 3.4: Удалить extension_handler.go (HTTP клиент к batch-service)
- [ ] 3.5: Очистить processor.go от legacy imports
- [ ] 3.6: Удалить HTTP endpoints из ras-adapter (после deprecation period)
- [ ] 3.7: Обновить документацию
- [ ] 3.8: Verify zero compilation warnings

**Критерии завершения:**
- [ ] Нет legacy HTTP paths
- [ ] Нет неиспользуемого кода
- [ ] Документация актуальна

---

## Redis Streams: Naming Convention

```
# Commands (запросы на выполнение)
commands:worker:operations     # Django → Worker

commands:ras:lock              # Worker → ras-adapter
commands:ras:unlock
commands:ras:block
commands:ras:unblock
commands:ras:terminate

commands:odata:query           # Worker → odata-adapter
commands:odata:create
commands:odata:update
commands:odata:delete
commands:odata:batch

commands:batch:init-odata      # Worker → batch-service (простые команды)

commands:designer:extension-install   # Worker → designer-agent
commands:designer:extension-remove
commands:designer:config-update
commands:designer:config-load
commands:designer:config-dump
commands:designer:epf-export

commands:backup:dump           # Worker → backup-service
commands:backup:restore
commands:backup:replicate

# Events (результаты)
events:ras:completed           # ras-adapter → Worker
events:ras:failed

events:odata:completed         # odata-adapter → Worker
events:odata:failed

events:batch:completed         # batch-service → Worker
events:batch:failed

events:designer:completed      # designer-agent → Worker
events:designer:failed
events:designer:progress

events:backup:completed        # backup-service → Worker
events:backup:failed
events:backup:progress

events:worker:completed        # Worker → Django
events:worker:failed
events:worker:progress

# Consumer Groups
worker-group                   # Workers consuming commands:worker:*
ras-adapter-group              # ras-adapter consuming commands:ras:*
odata-adapter-group            # odata-adapter consuming commands:odata:*
batch-service-group            # batch-service consuming commands:batch:*
designer-agent-group           # designer-agent consuming commands:designer:*
backup-service-group           # backup-service consuming commands:backup:*
orchestrator-group             # Django consuming events:worker:*
```

---

## Message Format

```json
{
  "id": "msg-uuid",
  "correlation_id": "workflow-uuid",
  "type": "lock_scheduled_jobs",
  "payload": {
    "database_id": "db-uuid",
    "cluster_id": "cluster-uuid",
    "infobase_id": "infobase-uuid",
    "options": {}
  },
  "metadata": {
    "created_by": "user@example.com",
    "created_at": "2025-12-11T10:00:00Z",
    "workflow_id": "workflow-uuid",
    "step": 2,
    "retry_count": 0
  }
}
```

---

## Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Message loss при миграции | Medium | High | Dual-write период, мониторинг |
| Deadlock при блокировках | Low | High | TTL на locks, timeout на acquire |
| Worker crash mid-saga | Medium | High | Persistence в Redis, recovery |
| Redis Streams unavailable | Low | Critical | Health checks, alerting |
| Compensation fails | Low | Medium | Retry compensation, manual intervention |
| OData timeout (>15 сек) | Medium | High | Batch splitting, connection pooling |

---

## Компоненты для удаления (после Фазы 3)

| Файл | Строк | Причина |
|------|-------|---------|
| `worker/internal/rasadapter/client.go` | ~456 | Заменён на Streams |
| `worker/internal/processor/ras_handler.go` | ~484 | Заменён на Saga |
| `worker/internal/processor/cluster_resolver.go` | ~371 | Не нужен |
| `worker/internal/processor/extension_handler.go` | ~372 | HTTP → Streams |
| **Итого** | **~1683** | |

---

## Диаграмма: Поток данных extension_install

```mermaid
sequenceDiagram
    participant U as User
    participant D as Django
    participant R as Redis Streams
    participant W as Worker (Saga)
    participant RM as Resource Manager
    participant RA as ras-adapter
    participant DA as designer-agent
    participant Agent as 1cv8.exe /AgentMode
    participant 1C as 1С Cluster

    U->>D: POST /api/v2/extensions/install
    D->>D: Create BatchOperation
    D->>R: XADD commands:worker:operations

    R->>W: XREADGROUP (new message)
    W->>RM: AcquireLock(DB-1, DB-2)
    RM->>R: SET resource:lock:DB-1
    RM->>R: SET resource:lock:DB-2
    RM-->>W: Locks acquired

    Note over W: Step 1: Lock scheduled jobs
    W->>R: XADD commands:ras:lock
    R->>RA: XREADGROUP
    RA->>1C: RAS: Lock infobase
    RA->>R: XADD events:ras:completed
    R->>W: Event received

    Note over W: Step 2: Terminate sessions
    W->>R: XADD commands:ras:terminate
    R->>RA: XREADGROUP
    RA->>1C: RAS: Terminate sessions
    RA->>R: XADD events:ras:completed
    R->>W: Event received

    Note over W: Step 3: Install extension (via Agent Mode)
    W->>R: XADD commands:designer:extension-install
    R->>DA: XREADGROUP
    DA->>Agent: SSH: config load-ext --file="ext.cfe"
    Agent->>1C: Install extension
    DA->>R: XADD events:designer:completed
    R->>W: Event received

    Note over W: Step 4: Unlock scheduled jobs
    W->>R: XADD commands:ras:unlock
    R->>RA: XREADGROUP
    RA->>1C: RAS: Unlock infobase
    RA->>R: XADD events:ras:completed
    R->>W: Event received

    W->>RM: ReleaseLock(DB-1, DB-2)
    RM->>R: DEL resource:lock:*

    W->>R: XADD events:worker:completed
    R->>D: XREADGROUP
    D->>D: Update BatchOperation status
    D-->>U: WebSocket: Operation completed
```

---

## Диаграмма: OData CRUD операции

```mermaid
sequenceDiagram
    participant U as User
    participant D as Django
    participant R as Redis Streams
    participant W as Worker
    participant B as batch-service
    participant O as odata-adapter
    participant 1C as 1С OData API

    U->>D: POST /api/v2/databases/{id}/data
    D->>R: XADD commands:worker:operations

    R->>W: XREADGROUP

    Note over W: Check if OData initialized
    W->>R: XADD commands:batch:init-odata
    R->>B: XREADGROUP
    B->>1C: Run extension to enable OData
    B->>R: XADD events:batch:completed
    R->>W: OData ready

    Note over W: Execute CRUD
    W->>R: XADD commands:odata:create
    R->>O: XREADGROUP
    O->>1C: POST /odata/standard.odata/...
    1C-->>O: 201 Created
    O->>R: XADD events:odata:completed
    R->>W: Event received

    W->>R: XADD events:worker:completed
    R->>D: XREADGROUP
    D-->>U: Response
```

---

## См. также

- [CURRENT_ARCHITECTURE.md](../architecture/diagrams/CURRENT_ARCHITECTURE.md) — текущая архитектура
- [EVENT_DRIVEN_ARCHITECTURE.md](../architecture/EVENT_DRIVEN_ARCHITECTURE.md) — детальный дизайн
- [ADMIN_SERVICES_ROADMAP.md](./ADMIN_SERVICES_ROADMAP.md) — backup-service, config-service
- [Saga Pattern - Microsoft](https://learn.microsoft.com/en-us/azure/architecture/patterns/saga)
- [Redis Streams](https://redis.io/docs/data-types/streams/)
