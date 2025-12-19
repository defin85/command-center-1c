# Radical Roadmap: Единый 1C Control Plane (Worker + Drivers)

Цель: радикально упростить “контур 1С” до **единого engine (Go Worker)** с **самостоятельными драйверами доступа** (RAS/OData/CLI/Agent/ibcmd) и оставить Orchestrator как **control plane** (операции, ACL, состояние, аудит, UI-агрегация), не выполняющий интеграционные вызовы к 1С.

Текущие микросервисы (например `ras-adapter`, `batch-service`, `designer-agent`) остаются **референсом** на время миграции и будут удалены после стабилизации.

---

## Текущий прогресс (implementation status)

Дата актуальности: **2025-12-19**

### Сделано

- **Worker Driver Framework**: реестр драйверов + метрики драйверов + базовые timeline события.
  - Код: `go-services/worker/internal/drivers/registry.go`
  - Интеграция: `go-services/worker/internal/processor/processor.go`
- **Direct RAS (внутри Worker)**: добавлен прямой RAS client/driver (`rasdirect`) + использование `ras_server` из internal API.
  - Код: `go-services/worker/internal/drivers/rasdirect/client.go`
  - Internal API расширен на `ras_server`/cluster creds (референс в orchestrator).
- **Вынесение cluster/infobase info из processor** в отдельный слой `clusterinfo` (единообразный резолвинг данных кластера/ИБ для драйверов).
  - Код: `go-services/worker/internal/clusterinfo/*`
- **RAS операции перенесены в driver (`rasops`)**:
  - meta: `sync_cluster`, `discover_clusters`
  - db ops: `lock_scheduled_jobs`, `unlock_scheduled_jobs`, `block_sessions`, `unblock_sessions`, `terminate_sessions`
  - Код: `go-services/worker/internal/drivers/rasops/*`
  - Удалены старые реализации из `go-services/worker/internal/processor/*` (RAS-специфика больше не живёт в processor).

### В работе / ближайшее

- **“Единая точка ответственности по workflow”**: развести `install_extension` и `execute_workflow` (сейчас это ещё общий контур в worker/orchestrator).
- **Observability унификация UI**: довести до правила “UI читает только Prometheus” для `/system-status` и `/service-mesh`, включая внешние probes (RAS port / TCP).
- **CLI/Designer/ibcmd**: начало миграции в драйверы (см. Phase 3/5).

### Статус фаз (кратко)

- Phase 1 — Driver Framework в Worker: **DONE**
- Phase 2 — Migrating RAS operations: **DONE (core)**
- Phase 3 — Migrating Designer/Extensions: **TODO**
- Phase 4 — Migrating OData operations: **TODO**
- Phase 5 — ibcmd/ibsrv integration: **TODO**
- Phase 6 — Декомиссия сервисов: **TODO**

## Принципы

1. **Единая точка ответственности**: каждый `ActionType` принадлежит ровно одному драйверу.
2. **Orchestrator не ходит в 1С**: никаких “интеграционных” HTTP/CLI из Django.
3. **Worker = единственный engine**: одна очередь, единый lifecycle операции, единый timeline.
4. **Единая Observability/Health**: UI (`/system-status`, `/service-mesh`) читает статусы только из Prometheus (внешние зависимости — blackbox).
5. **Стабильные таймауты**: 1С транзакции < 15s; драйверы обязаны поддерживать `ctx timeout` и “видимые” подшаги в timeline.

---

## Target Architecture

```
Frontend → API Gateway → Orchestrator (control plane) → Redis Streams → Worker (engine)
                                                           └─ Drivers:
                                                              - RAS (direct)
                                                              - OData (direct)
                                                              - CLI 1cv8 (direct)
                                                              - AgentMode (SSH/SFTP)
                                                              - ibcmd/ibsrv (direct)
```

### Drivers (как “самостоятельные” модули)

Внутри `go-services/worker`:

```
internal/drivers/
  ras/      # RAS protocol/client, cluster/infobase ops
  odata/    # HTTP OData client, batch rules
  cli/      # 1cv8 DESIGNER/ENTERPRISE/CREATEINFOBASE
  agent/    # 1cv8 /AgentMode over SSH/SFTP (опционально)
  ibcmd/    # ibcmd/ibsrv (backup/restore/replicate/test)
```

Жёсткие границы:
- каждый драйвер имеет свой `Config`, `Client`, свой набор `ActionType`;
- общий код — только в `go-services/shared/` (логгер, http wrapper, retry/backoff, metrics helpers), без доменной логики.

---

## Единая модель выполнения

### Action Contract (внутренний)

Минимальный контракт для engine/driver:
- `action_type` (enum/string)
- `target` (cluster/db)
- `inputs` (map)
- `timeouts` (overall + per-external-call)
- `idempotency_key`
- `correlation_id` / `trace_id`

### Timeline Contract (единый)

Стандарт:
- `*.started`
- `*.finished`
- `*.failed`

Для внешних вызовов обязательно:
- `external.<driver>.<call>.started/finished/failed`
- лог длительности: `path + elapsed + status` для HTTP, аналогично для SSH/exec.

---

## Маппинг доменных операций → драйверы

**RAS driver**
- cluster/infobase discovery (list clusters/infobases)
- sessions ops (block/unblock/terminate)
- scheduled jobs ops (lock/unlock)
- любые RAS-only операции

**OData driver**
- CRUD/reads через OData
- batch (100–500 записей)

**CLI driver (`1cv8`)**
- `DESIGNER` batch ops (cfg/cfe, checks, repo ops)
- `CREATEINFOBASE` (создание ИБ) где это уместно
- `/Execute` (запуск внешней обработки) при необходимости

**Agent driver (`/AgentMode`)**
- удалённые Designer операции по SSH/SFTP (если это стабильнее, чем локальный CLI)

**ibcmd driver**
- операции уровня утилиты `ibcmd` (create/backup/restore/replicate) для сценариев, где это лучше, чем RAS/CLI
- `ibsrv` — только dev/test/temporary environments (явно помечать non-prod)

---

## Набор “источников истины” для статусов

1. **Prometheus** — единственная точка истины для health.
2. **Blackbox exporter** — единственная точка истины для доступности внешних хостов/портов (RAS, DB, etc).
3. **Worker/Services metrics** — единственная точка истины для “жив/не жив” сервисов.

Запрет:
- UI не делает “свои” проверки доступности (кроме read-only чтения PromQL).

---

## Радикальная миграция: фазы

### Phase 0 — Подготовка (1–2 недели)

Deliverables:
- финализировать `ActionType` список и ownership по драйверам
- единый формат timeline событий (включая подшаги внешних вызовов)
- единые метрики: `action_duration`, `external_call_duration`, `action_failures`, `driver_ready`
- SLO/Alerts: worker lag, error rates, timeouts (≤15s)

Acceptance:
- можно “точно” сказать, где время уходит (timeline + внешние вызовы)
- `/system-status` и `/service-mesh` читают одинаковые PromQL сигналы

### Phase 1 — Driver Framework в Worker (1–2 недели)

Deliverables:
- registry `action_type -> driver`
- common middleware: retries, ctx timeouts, timeline writer, metrics/log wrappers
- “dry-run / shadow” режим (опционально): выполнение без сайд-эффектов, только наблюдение

Acceptance:
- новая операция проходит через driver pipeline end-to-end

Status: **DONE** (реестр драйверов + интеграция в processor + метрики/таймлайн для драйверов)

### Phase 2 — Migrating RAS operations (2–3 недели)

Deliverables:
- перенести RAS операции из `ras-adapter` в `worker/internal/drivers/ras`
- совместимость контрактов с текущими workflows
- параллельный запуск: `ras-adapter` остаётся, но выключается по флагу

Acceptance:
- `sync_cluster`, sessions, lock/unlock jobs работают напрямую из worker
- стабильные таймауты и понятные timeline подшаги

Status: **DONE (core)** (RAS операции живут в `internal/drivers/rasops`, direct RAS через `internal/drivers/rasdirect`, fallback через `ras-adapter`)

### Phase 3 — Migrating Designer/Extensions (3–5 недель)

Deliverables:
- `cli-driver` для `1cv8 DESIGNER` batch ops
- (опционально) `agent-driver` для `/AgentMode` SSH/SFTP
- “разнести ответственности”: `install_extension` ≠ `execute_workflow`

Acceptance:
- установка/обновление расширений без Designer Agent/Batch Service как обязательных hop’ов
- в timeline видно: download → designer apply → publish result

### Phase 4 — Migrating OData operations (2–4 недели)

Deliverables:
- `odata-driver` в worker с batch правилами (100–500)
- единые ретраи и таймауты на HTTP, логирование `path+elapsed+status`

Acceptance:
- все OData workflows не зависят от внешнего “adapter service”

### Phase 5 — ibcmd/ibsrv integration (2–4 недели, optional)

Deliverables:
- `ibcmd-driver` для: create/backup/restore/replicate (где это даёт выигрыш)
- отдельные guards: запрет запуска `ibsrv` в prod конфигурации

Acceptance:
- операции уровня “инфраструктуры баз” выполняются предсказуемо и наблюдаемо

### Phase 6 — Декомиссия сервисов (1–2 недели)

Deliverables:
- выключить `ras-adapter`, `designer-agent`, `batch-service` в default профилях
- удалить маршруты/конфиги/дашборды, которые дублируют источники истины
- удалить код сервисов после периода стабильности

Acceptance:
- прод/стейдж работают без этих сервисов N недель без регрессий

---

## Контракты и совместимость

Правило: **внешний API v2 не ломаем**. Меняем только внутреннюю реализацию.

Переходные механизмы:
- feature-flag `USE_DIRECT_RAS`, `USE_DIRECT_ODATA`, `USE_DIRECT_CLI`, `USE_DIRECT_IBCMD`
- shadow-mode на выборочных action types (сравнение результатов без применения)

---

## Риски и митигations

1. **Таймауты/зависания**: обязательные ctx timeouts + авто-очистка stuck операций + отдельные timeline подшаги.
2. **Окружение для CLI/ibcmd**: preflight проверки бинарей/версий, явные ошибки “missing dependency”.
3. **Лицензирование/правовые ограничения**: `ibsrv` строго non-prod, конфиг-гард.
4. **Нагрузочные эффекты**: ограничение параллелизма per-driver (особенно CLI) + backpressure в очереди.
5. **UI рассинхрон**: UI читает только Prometheus; никаких “вторых правд”.

---

## Definition of Done (для всего роадмапа)

- Worker выполняет 100% workflows 1С через drivers
- Orchestrator не делает вызовов к 1С
- Удалены `ras-adapter`, `designer-agent`, `batch-service` (после стабилизации)
- `/system-status` и `/service-mesh` согласованы и показывают одинаковую картину
- Для каждой операции видны: подшаги + внешние вызовы + длительности
