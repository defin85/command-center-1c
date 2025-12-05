# Детальный План Реализации Event-Driven Интеграции

**Дата создания:** 2024-12-03
**Статус:** В планировании
**Связанный документ:** [EVENT_DRIVEN_COMPLETION_ROADMAP.md](./EVENT_DRIVEN_COMPLETION_ROADMAP.md)

---

## Общая информация

**Цель:** Перевод установки расширений (и смежных операций) на асинхронную Event-Driven модель через Redis Pub/Sub и State Machine без HTTP-блокировок.

**Текущее состояние:**
| Компонент | Готовность | Статус |
|-----------|------------|--------|
| Shared Events (Pub/Sub) | 100% | Production-Ready |
| State Machine | 100% | Код готов, не подключена |
| ras-adapter | 90% | Готов к интеграции |
| batch-service | 100% | Готов к интеграции |
| Worker DualModeProcessor | 85% | Feature flags готовы, заглушка |
| Feature Flags | 100% | 97.3% test coverage |

**Критичный GAP:** В `dual_mode.go:156-231` метод `processEventDriven()` всегда падает в HTTP Sync fallback вместо запуска State Machine.

**Общая оценка:** 4-7 рабочих дней

---

## Фаза 1: Подключение State Machine в Worker

**Цель:** Интегрировать существующую State Machine в DualModeProcessor вместо fallback на HTTP Sync.

**Оценка:** 1-2 дня

### Задачи

| # | Задача | Описание | Файлы | Зависит от | Параллельно с |
|---|--------|----------|-------|------------|---------------|
| 1.1 | Расширить TaskProcessor | Добавить поля для Publisher, Subscriber и настроить инициализацию | `processor.go`, `cmd/main.go` | — | 1.3 |
| 1.2 | Создать фабрику State Machine | Factory-функция в DualModeProcessor для создания ExtensionInstallStateMachine | `dual_mode.go` | 1.1 | — |
| 1.3 | Конфигурация из environment | Загрузка timeouts и retries из env (SM_TIMEOUT_LOCK, SM_TIMEOUT_TERMINATE, SM_TIMEOUT_INSTALL, SM_TIMEOUT_UNLOCK, SM_MAX_RETRIES) | `statemachine/config.go`, `config/config.go` | — | 1.1, 1.5 |
| 1.4 | Реализовать processEventDriven() | Раскомментировать код, убрать fallback, вызывать sm.Run() | `dual_mode.go:156-231` | 1.1, 1.2, 1.3 | — |
| 1.5 | Получение ClusterInfo | Метод для получения cluster_id и infobase_id по database_id | `dual_mode.go` или `cluster_resolver.go` | — | 1.2, 1.3 |
| 1.6 | Unit-тесты | Тесты для processEventDriven() с mock publisher/subscriber | `dual_mode_test.go` | 1.4 | — |

### Затрагиваемые файлы
- `go-services/worker/internal/processor/dual_mode.go`
- `go-services/worker/internal/processor/processor.go`
- `go-services/worker/internal/statemachine/config.go`
- `go-services/worker/internal/config/config.go`
- `go-services/worker/cmd/main.go`

### Критерии завершения (Definition of Done)
- [ ] TaskProcessor корректно инициализирует Publisher и Subscriber
- [ ] processEventDriven() создаёт и запускает State Machine без fallback
- [ ] Конфигурация State Machine загружается из environment переменных
- [ ] Unit-тесты покрывают happy path создания State Machine
- [ ] Интеграционный тест `worker/test/integration/statemachine/happy_path_test.go` проходит

### Риски и митигации
| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Subscriber не успевает зарегистрировать handlers до Run() | Средняя | Высокое | SM регистрирует handlers в конструкторе, subscriber.Run() вызывается ДО sm.Run() |
| ClusterInfo недоступен для некоторых баз | Средняя | Среднее | Fallback на HTTP Sync при ошибке получения ClusterInfo |
| Redis недоступен при инициализации | Низкая | Высокое | Publisher имеет reconnect logic, graceful degradation с логированием |

---

## Фаза 2: Каналы и Обработчики Команд/Событий

**Цель:** Обеспечить корректную маршрутизацию команд и событий между Worker State Machine, ras-adapter и batch-service через Redis Pub/Sub.

**Оценка:** 1-2 дня

### Текущие каналы

**Commands (Worker → Services):**
- `commands:cluster-service:infobase:lock`
- `commands:cluster-service:infobase:unlock`
- `commands:cluster-service:sessions:terminate`
- `commands:batch-service:extension:install`

**Events (Services → Worker):**
- `events:cluster-service:infobase:locked`
- `events:cluster-service:infobase:lock-failed`
- `events:cluster-service:infobase:unlocked`
- `events:cluster-service:infobase:unlock-failed`
- `events:cluster-service:sessions:closed`
- `events:cluster-service:sessions:terminate-failed`
- `events:batch-service:extension:installed`
- `events:batch-service:extension:install-failed`
- `events:batch-service:extension:install-started`

### Задачи

| # | Задача | Описание | Файлы | Зависит от | Параллельно с |
|---|--------|----------|-------|------------|---------------|
| 2.1 | Аудит названий каналов | Проверить соответствие между State Machine, ras-adapter и batch-service | `handlers.go`, `*_handler.go` | Фаза 1 | — |
| 2.2 | Активация подписок в ras-adapter | Инициализация Subscriber, регистрация handlers, запуск subscriber.Run() | `ras-adapter/cmd/main.go` | 2.1 | 2.3, 2.5, 2.6 |
| 2.3 | Активация подписок в batch-service | Инициализация Subscriber, регистрация InstallHandler | `batch-service/cmd/main.go` | 2.1 | 2.2, 2.5, 2.6 |
| 2.4 | Feature toggle REDIS_PUBSUB_ENABLED | Переменная окружения для включения/отключения подписок (default: false) | `main.go` обоих сервисов, `.env.local.example` | 2.2, 2.3 | — |
| 2.5 | Проверка idempotency | Убедиться что все handlers используют CheckIdempotency с SetNX | `ras-adapter/internal/eventhandlers/*.go` | — | 2.2, 2.3 |
| 2.6 | Проверка correlation_id фильтрации | Убедиться что State Machine фильтрует события по correlation_id | `statemachine/state_machine.go` | — | 2.2, 2.3, 2.5 |
| 2.7 | Интеграционный тест end-to-end | Полный цикл: lock → terminate → install → unlock через Pub/Sub | `pubsub_integration_test.go` | 2.1-2.6 | — |

### Затрагиваемые файлы
- `go-services/worker/internal/statemachine/handlers.go`
- `go-services/worker/internal/statemachine/state_machine.go`
- `go-services/ras-adapter/cmd/main.go`
- `go-services/ras-adapter/internal/eventhandlers/lock_handler.go`
- `go-services/ras-adapter/internal/eventhandlers/unlock_handler.go`
- `go-services/ras-adapter/internal/eventhandlers/terminate_handler.go`
- `go-services/batch-service/cmd/main.go`
- `go-services/batch-service/internal/eventhandlers/install_handler.go`

### Критерии завершения (Definition of Done)
- [ ] Названия каналов согласованы между всеми сервисами
- [ ] ras-adapter подписан на команды lock/unlock/terminate и публикует события
- [ ] batch-service подписан на команду install и публикует события
- [ ] Все handlers имеют idempotency проверки (SetNX с TTL)
- [ ] Feature toggle REDIS_PUBSUB_ENABLED работает
- [ ] Интеграционный тест lock → unlock через Pub/Sub проходит

### Риски и митигации
| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Несовпадение payload структур между сервисами | Высокая | Среднее | Создать shared types в `go-services/shared/events/payloads.go` |
| Deadlock при одновременной обработке событий | Средняя | Высокое | Watermill router обрабатывает сообщения последовательно в consumer group |
| Дубликаты событий при Redis reconnect | Средняя | Среднее | Idempotency ключи (SetNX) уже реализованы |

---

## Фаза 3: Наблюдаемость и Feature Flags

**Цель:** Обеспечить полную наблюдаемость Event-Driven потока через метрики Prometheus, настроить алерты и подготовить постепенный rollout.

**Оценка:** 1 день

### Задачи

| # | Задача | Описание | Файлы | Зависит от | Параллельно с |
|---|--------|----------|-------|------------|---------------|
| 3.1 | Метрики публикации/доставки | event_publish_duration_seconds, event_delivery_duration_seconds, event_publish_total, event_delivery_errors_total | `shared/events/metrics.go` | Фаза 2 | 3.2, 3.3, 3.6 |
| 3.2 | Метрики State Machine | state_machine_active_count, state_machine_duration_seconds, state_machine_transitions_total, state_machine_errors_total | `statemachine/compensation_metrics.go` | — | 3.1, 3.3, 3.6 |
| 3.3 | Метрики compensation/timeout | compensation_executions_total, compensation_duration_seconds, state_machine_timeout_total | `compensation_metrics.go` | — | 3.1, 3.2, 3.6 |
| 3.4 | Настройка алертов Prometheus | EventDrivenTimeoutRateHigh (>10%), CompensationRateHigh (>5%), EventQueueDepthHigh (>1000), StateMachineErrorRateHigh (>1%) | `prometheus/alerts/event_driven.yml` (новый) | 3.1-3.3 | 3.5 |
| 3.5 | Grafana dashboard | Event Flow Rate, State Machine Latency, Error Rate, Active SMs, Compensation Rate, Rollout % | `grafana/dashboards/event_driven.json` (новый) | 3.1-3.3 | 3.4 |
| 3.6 | Endpoint статистики rollout | GetRolloutStats() в FeatureFlags, admin endpoint в Worker | `feature_flags.go`, `admin_handler.go` | — | 3.1-3.5 |
| 3.7 | Документация по rollout | Описание флагов, значения по умолчанию, процедура rollout | `docs/EVENT_DRIVEN_OPERATIONS.md` | 3.6 | — |

### Пороговые значения алертов
| Алерт | Порог | Severity |
|-------|-------|----------|
| EventDrivenTimeoutRateHigh | >10% за 5 мин | warning |
| CompensationRateHigh | >5% за 5 мин | warning |
| EventQueueDepthHigh | >1000 сообщений | warning |
| StateMachineErrorRateHigh | >1% за 5 мин | critical |

### Затрагиваемые файлы
- `go-services/shared/events/metrics.go`
- `go-services/worker/internal/statemachine/compensation_metrics.go`
- `go-services/worker/internal/config/feature_flags.go`
- `infrastructure/monitoring/prometheus/alerts/event_driven.yml` (новый)
- `infrastructure/monitoring/prometheus/prometheus.yml`
- `infrastructure/monitoring/grafana/dashboards/event_driven.json` (новый)
- `docs/EVENT_DRIVEN_OPERATIONS.md` (новый)

### Критерии завершения (Definition of Done)
- [ ] Все метрики экспортируются в Prometheus (проверить через /metrics)
- [ ] Алерты созданы и работают (проверить через Prometheus UI)
- [ ] Grafana dashboard показывает данные
- [ ] Документация по rollout процедуре готова
- [ ] Feature flags endpoint доступен для мониторинга

### Риски и митигации
| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Высокая cardinality метрик | Средняя | Среднее | Ограничить labels до service, operation_type, state, error_type |
| Alert fatigue при низких порогах | Средняя | Среднее | Начать с высоких порогов, снижать после стабилизации |
| Dashboard не показывает данные | Низкая | Низкое | Проверить data source, использовать Explore для debug |

---

## Фаза 4: Rollout и Валидация

**Цель:** Провести постепенный rollout Event-Driven режима с валидацией метрик и возможностью быстрого отката.

**Оценка:** 1-2 дня (зависит от длительности наблюдения)

### Процедура Rollout

```
Staging (ROLLOUT=0%) → 10% (2-4 часа) → 50% (4-8 часов) → 100% (24-48 часов)
```

### Задачи

| # | Задача | Описание | Зависит от |
|---|--------|----------|------------|
| 4.1 | Подготовка staging | ENABLE_EVENT_DRIVEN=true, REDIS_PUBSUB_ENABLED=true, ROLLOUT_PERCENT=0 | Фазы 1-3 |
| 4.2 | Прогон test suite | `make test` или `go test ./...` с ENABLE_EVENT_DRIVEN=true | 4.1 |
| 4.3 | Smoke-тест 10% | EVENT_DRIVEN_ROLLOUT_PERCENT=0.1, несколько операций, проверка метрик | 4.2 |
| 4.4 | Сравнение метрик | Latency p50/p95/p99, error rate между режимами (2-4 часа данных) | 4.3 |
| 4.5 | Повышение до 50% | EVENT_DRIVEN_ROLLOUT_PERCENT=0.5, наблюдение 4-8 часов | 4.4 |
| 4.6 | Повышение до 100% | EVENT_DRIVEN_ROLLOUT_PERCENT=1.0, HTTP Sync остаётся fallback | 4.5 |
| 4.7 | Документирование отката | Шаги быстрого отката при проблемах | — (параллельно) |
| 4.8 | Финальная валидация | 24-48 часов стабильной работы, закрытие задач | 4.6 |

### Процедура отката (Rollback)
1. Установить `ENABLE_EVENT_DRIVEN=false` в конфигурации
2. Перезапустить worker сервис
3. Проверить метрики HTTP Sync режима
4. При необходимости также установить `REDIS_PUBSUB_ENABLED=false` в ras-adapter/batch-service

### Критерии завершения (Definition of Done)
- [ ] Все тесты проходят в Event-Driven режиме
- [ ] Метрики Event-Driven не хуже HTTP Sync (latency p95, error rate)
- [ ] 100% трафика проходит через Event-Driven
- [ ] Нет блокировок worker при длительных операциях
- [ ] Документирована процедура отката
- [ ] Стабильная работа 24-48 часов без инцидентов

### Риски и митигации
| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Деградация на production нагрузке | Средняя | Высокое | Постепенный rollout (10% → 50% → 100%), мониторинг |
| Redis SPOF при высокой нагрузке | Средняя | Высокое | Redis Sentinel/Cluster для staging/production |
| Зависание State Machine | Низкая | Высокое | Watchdog (реализован) + алерты на timeout |
| Несовместимость с некоторыми базами 1С | Низкая | Среднее | EVENT_DRIVEN_TARGET_DBS для whitelist тестирования |

---

## Сводная Таблица Зависимостей

| Фаза | Задача | Зависит от | Можно параллельно с |
|------|--------|------------|---------------------|
| 1 | 1.1 | — | 1.3 |
| 1 | 1.2 | 1.1 | — |
| 1 | 1.3 | — | 1.1, 1.5 |
| 1 | 1.4 | 1.1, 1.2, 1.3 | — |
| 1 | 1.5 | — | 1.1, 1.2, 1.3 |
| 1 | 1.6 | 1.4 | — |
| 2 | 2.1 | Фаза 1 | — |
| 2 | 2.2 | 2.1 | 2.3, 2.5, 2.6 |
| 2 | 2.3 | 2.1 | 2.2, 2.5, 2.6 |
| 2 | 2.4 | 2.2, 2.3 | — |
| 2 | 2.5 | — | 2.2, 2.3 |
| 2 | 2.6 | — | 2.2, 2.3, 2.5 |
| 2 | 2.7 | 2.1-2.6 | — |
| 3 | 3.1 | Фаза 2 | 3.2, 3.3, 3.6 |
| 3 | 3.2 | — | 3.1, 3.3, 3.6 |
| 3 | 3.3 | — | 3.1, 3.2, 3.6 |
| 3 | 3.4 | 3.1, 3.2, 3.3 | 3.5 |
| 3 | 3.5 | 3.1, 3.2, 3.3 | 3.4 |
| 3 | 3.6 | — | 3.1-3.5 |
| 3 | 3.7 | 3.6 | — |
| 4 | 4.1 | Фазы 1-3 | 4.7 |
| 4 | 4.2 | 4.1 | — |
| 4 | 4.3 | 4.2 | — |
| 4 | 4.4 | 4.3 | — |
| 4 | 4.5 | 4.4 | — |
| 4 | 4.6 | 4.5 | — |
| 4 | 4.7 | — | 4.1-4.6 |
| 4 | 4.8 | 4.6 | — |

---

## Ключевые Файлы для Изменения

### Worker
| Файл | Фаза | Изменения |
|------|------|-----------|
| `internal/processor/dual_mode.go` | 1 | Основная интеграция SM |
| `internal/processor/processor.go` | 1 | Добавление зависимостей |
| `internal/statemachine/config.go` | 1 | Загрузка из env |
| `internal/statemachine/compensation_metrics.go` | 3 | Новые метрики |
| `internal/config/feature_flags.go` | 3 | Rollout stats |
| `cmd/main.go` | 1 | Инициализация |

### ras-adapter
| Файл | Фаза | Изменения |
|------|------|-----------|
| `cmd/main.go` | 2 | Subscriber initialization |
| `internal/eventhandlers/*.go` | 2 | Idempotency checks |

### batch-service
| Файл | Фаза | Изменения |
|------|------|-----------|
| `cmd/main.go` | 2 | Subscriber initialization |

### Shared
| Файл | Фаза | Изменения |
|------|------|-----------|
| `events/metrics.go` | 3 | Pub/Sub метрики |

### Infrastructure
| Файл | Фаза | Изменения |
|------|------|-----------|
| `monitoring/prometheus/alerts/event_driven.yml` | 3 | Новый файл |
| `monitoring/grafana/dashboards/event_driven.json` | 3 | Новый файл |

### Documentation
| Файл | Фаза | Изменения |
|------|------|-----------|
| `docs/EVENT_DRIVEN_OPERATIONS.md` | 3, 4 | Новый файл |

---

## Environment Variables

### Worker
| Переменная | Default | Описание |
|------------|---------|----------|
| ENABLE_EVENT_DRIVEN | false | Global kill switch |
| EVENT_DRIVEN_ROLLOUT_PERCENT | 0 | 0.0-1.0, процент трафика |
| EVENT_DRIVEN_TARGET_DBS | "" | Whitelist баз для раннего доступа |
| EVENT_DRIVEN_EXTENSIONS | true | Включить для операций расширений |
| EVENT_DRIVEN_MAX_CONCURRENT | 100 | Лимит параллельных SM |
| SM_TIMEOUT_LOCK | 30s | Timeout блокировки |
| SM_TIMEOUT_TERMINATE | 90s | Timeout завершения сессий |
| SM_TIMEOUT_INSTALL | 5m | Timeout установки |
| SM_TIMEOUT_UNLOCK | 30s | Timeout разблокировки |
| SM_MAX_RETRIES | 3 | Максимум повторов |

### ras-adapter / batch-service
| Переменная | Default | Описание |
|------------|---------|----------|
| REDIS_PUBSUB_ENABLED | false | Включение подписок на команды |

---

## Сводка по Фазам

| Фаза | Задач | Срок | Ключевой результат |
|------|-------|------|-------------------|
| **1** | 6 | 1-2 дня | State Machine подключена в Worker |
| **2** | 7 | 1-2 дня | Pub/Sub работает между сервисами |
| **3** | 7 | 1 день | Метрики, алерты, dashboards |
| **4** | 8 | 1-2 дня | 100% rollout, документация |
| **Итого** | **28** | **4-7 дней** | **Production Event-Driven** |

---

## Конфигурация Event-Driven

### Включение

Добавить в `.env.local`:
```bash
ENABLE_EVENT_DRIVEN=true
REDIS_PUBSUB_ENABLED=true
```

Перезапустить сервисы:
```bash
./scripts/dev/restart.sh worker
./scripts/dev/restart.sh ras-adapter
./scripts/dev/restart.sh batch-service
```

### Отключение (при проблемах)

```bash
ENABLE_EVENT_DRIVEN=false
./scripts/dev/restart.sh worker
```

### Мониторинг

**Endpoints:**
- Rollout Stats: http://localhost:9091/rollout-stats
- Prometheus Metrics: http://localhost:9091/metrics
- Grafana Dashboard: http://localhost:3000/d/ab-testing-event-driven

**Ключевые метрики:**
- `worker_state_machine_active_count` - активные SM
- `worker_state_machine_timeout_total` - timeout события
- `worker_state_machine_duration_seconds` - время выполнения

### Алерты

| Алерт | Порог | Severity |
|-------|-------|----------|
| EventDrivenTimeoutRateHigh | >10% за 5м | critical |
| EventDrivenCompensationWarning | >5% за 5м | warning |
| EventDrivenQueueDepthCritical | >1000 | critical |
| StateMachineActiveCountHigh | >100 | warning |

---

## Чеклист запуска

- [ ] Redis доступен (`redis-cli ping`)
- [ ] Worker unit тесты проходят (`go test ./internal/...`)
- [ ] ras-adapter запущен с `REDIS_PUBSUB_ENABLED=true`
- [ ] batch-service запущен с `REDIS_PUBSUB_ENABLED=true`
- [ ] Worker запущен с `ENABLE_EVENT_DRIVEN=true`
- [ ] /rollout-stats endpoint отвечает (http://localhost:9091/rollout-stats)
- [ ] Grafana dashboard загружается
