# Roadmap: Завершение Event-Driven интеграции

**Цель:** довести event-driven поток (Redis Pub/Sub + State Machine) до production-ready и перевести установку расширений и смежные операции на асинхронную модель без HTTP-блокировок.

## Текущее состояние (обновлено 2025-12-03)
- ✅ Redis Pub/Sub, envelope и event-обработчики реализованы в ras-adapter и batch-service.
- ✅ Worker DualModeProcessor полностью подключен к State Machine (NO HTTP FALLBACK).
- ✅ State Machine интегрирован с watchdog, publisher/subscriber и compensation.
- ✅ Feature flags для режима работы (ENABLE_EVENT_DRIVEN).
- ✅ Prometheus метрики + Grafana dashboard для мониторинга.
- ✅ Alerting rules для timeout, compensation, queue depth.
- ✅ **ЗАВЕРШЕНО** - Event-Driven режим включен по умолчанию (100%).

## Объем (In Scope)
- Подключить State Machine к worker для операций расширений.
- Завести реальный publisher/subscriber в worker с маршрутизацией каналов `commands:*` / `events:*`.
- Завершить end-to-end happy-path и failure-path тесты (go integration + smoke via make test target).
- Включить rollout (флаги, процент, targeted DBs) и метрики/алерты по event-driven.

## Не входит (Out of Scope)
- Миграция на Kafka или замену Redis.
- Полный перевод всех типов операций (делаем расширения; остальные — отдельным треком).

## Этапы и контрольные точки

### Фаза 1: Подключение State Machine в worker (1–2 дня) ✅ COMPLETED
- [x] Инициализировать publisher/subscriber/Redis клиент в TaskProcessor и передавать в State Machine.
- [x] В DualModeProcessor `processEventDriven` вызывать StateMachine.Run (без fallback).
- [x] Прокинуть конфиг (timeouts, retries, max concurrent) из env/feature flags.
- [x] Контрольная точка: unit/integration тест `worker/test/integration/statemachine/happy_path_test.go` проходит на реальных сервисах-моках.

### Фаза 2: Каналы и обработчики команд/событий (1–2 дня) ✅ COMPLETED
- [x] Проверить/выравнять названия каналов с design doc (commands:cluster-service:*, events:batch-service:*).
- [x] В ras-adapter/batch-service включить подписки по умолчанию (feature toggle `REDIS_PUBSUB_ENABLED=true` в локале).
- [x] Добавить idempotency (SetNX) и correlation_id проверки в handlers, где пропущено.
- [x] Контрольная точка: интеграционный тест на блокировку/разблокировку + установку расширения через Pub/Sub проходит.

### Фаза 3: Наблюдаемость и флаги (1 день) ✅ COMPLETED
- [x] Метрики Prometheus: латентность публикации/доставки, количество активных state machines, error/timeout rates.
- [x] Алерты: timeout >10%, compensation rate >5%, глубина очереди >1000.
- [x] Фича-флаги: `ENABLE_EVENT_DRIVEN=true` + постепенный rollout `EVENT_DRIVEN_ROLLOUT_PERCENT` (10% → 50% → 100%).
- [x] Контрольная точка: дашборды/Grafana панели обновлены, алерты развернуты.

### Фаза 4: Rollout и валидация (1–2 дня) ✅ COMPLETED
- [x] Прогнать make test (или целевые go test ./... для worker, ras-adapter, batch-service) в event-driven режиме.
- [x] Подготовить конфигурацию rollout (.env.local.example обновлен)
- [x] Создать чеклист валидации (см. EVENT_DRIVEN_IMPLEMENTATION_PLAN.md)
- [x] ~~A/B тестирование~~ — **ПРОПУЩЕНО**: HTTP Sync никогда не работал в production, постепенный rollout не требуется.
- [x] Включен 100% Event-Driven режим по умолчанию (`RolloutPercentage = 1.0`).
- [x] Контрольная точка: конфигурация упрощена до `ENABLE_EVENT_DRIVEN=true` + `REDIS_PUBSUB_ENABLED=true`.

## Риски и смягчения
- Redis SPOF: включить Sentinel/реплики для стейджа/прода; для дев — graceful degradation + retry.
- Дубли/переупорядочивание событий: idempotency ключи + проверка допустимых переходов в State Machine.
- Зависание после lock: watchdog + компенсации (unlock) и manual action event.

## Критерии готовности (Definition of Done)
- Worker исполняет установку расширения через State Machine без HTTP fallback.
- Корректные события `...locked/closed/installed/unlocked` проходят end-to-end и обновляют Orchestrator/UI.
- Метрики/алерты включены; rollout-флаги позволяют быстро отключить event-driven.
- Интеграционные тесты happy-path и fail-path зелёные; make test не краснеет из-за новых зависимостей.
