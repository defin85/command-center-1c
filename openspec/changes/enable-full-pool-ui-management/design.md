## Context
Текущая реализация pool UI покрывает только часть процесса:
- каталог организаций доступен для mutating-операций;
- граф пула на `/pools/catalog` read-only;
- запуск run на `/pools/runs` не содержит явного direction-specific `run_input` для top-down стартовой суммы;
- API-контракт не содержит mutating endpoint'ов для пула/топологии.

Это нарушает целевую операционную модель «полный цикл через UI» и вынуждает операторов использовать внешние API-клиенты.

## Goals
- Обеспечить полный lifecycle работы с pool через UI без ручных HTTP-вызовов.
- Сделать запуск `top_down` run с вводимой пользователем стартовой суммой first-class контрактом.
- Сохранить tenant-safety, idempotency и текущий unified workflow runtime.

## Non-Goals
- Новый runtime для pools.
- Переработка алгоритмов распределения.
- Drag-and-drop graph editor в рамках MVP.

## Decisions
### Decision 1: Вводим mutating API для pool metadata и topology snapshot
- Добавляются mutating endpoint'ы для:
  - upsert пула (metadata);
  - upsert версии топологии как атомарного snapshot.
- Snapshot payload описывает nodes/edges и effective период.
- Валидация DAG и доменных ограничений остаётся на backend как source-of-truth.

Почему:
- Позволяет UI полноценно управлять пулом.
- Атомарный snapshot проще и безопаснее для пользователя, чем поштучное редактирование узлов/рёбер множеством запросов.

Альтернатива:
- CRUD по каждой node/edge версии.
- Отклонена для MVP из-за высокой сложности согласования и повышенного риска неконсистентности.

### Decision 2: Расширяем create-run контракт структурированным `run_input`
- В `POST /api/v2/pools/runs/` вводится `run_input` с direction-specific схемой.
- Для `top_down` обязательное поле стартовой суммы.
- Для `bottom_up` обязательный источник данных (файл/JSON payload + template binding).

Почему:
- Избавляет от неявных соглашений через `source_hash`/`validation_summary`.
- Даёт стабильный и проверяемый контракт для UI и workflow steps.

### Decision 3: Idempotency fingerprint учитывает `run_input`
- Fingerprint должен включать canonicalized `run_input`.
- Изменение стартовой суммы или входных данных должно приводить к новому idempotency key.
- `source_hash` удаляется из публичного create-run контракта и не участвует в новой формуле idempotency.

Почему:
- Предотвращает ложное переиспользование run при разных входных данных.

### Decision 4: UI остаётся в существующих точках входа
- `/pools/catalog` расширяется блоками «Pools» и «Topology editor».
- `/pools/runs` расширяется direction-specific form input и полным safe-flow контролем.

Почему:
- Минимизирует миграцию UX и переиспользует существующую навигацию/контекст.

### Decision 5: Snapshot update защищается optimistic concurrency
- Mutating update topology snapshot должен использовать optimistic concurrency через обязательный `version` token в payload.
- При конфликте версии backend возвращает `409` с доменным кодом, UI сохраняет введённые данные и предлагает перезагрузить актуальную версию.

Почему:
- Убирает риск "lost update" при параллельной работе операторов над одним пулом.

## API/Model Considerations
- API:
  - добавить mutating endpoint'ы для пула/топологии;
  - расширить `PoolRunCreateRequest` полем `run_input` и удалить из него `source_hash`.
- Model:
  - хранить `run_input` в run state (отдельным полем или каноническим под-объектом state-модели);
  - обеспечить читаемость historical runs после удаления `source_hash` из create-path API.
- Idempotency:
  - canonicalization `run_input` должна быть детерминированной (стабильный JSON + нормализация денежных полей);
  - одинаковый semantically-equivalent payload должен давать одинаковый fingerprint.
  - `source_hash` не используется в формуле нового idempotency key.
- Workflow:
  - передавать `run_input` в input_context;
  - шаги `prepare_input` и `distribution_calculation` используют его как источник данных.

## Security / Tenant
- Все новые mutating endpoint'ы требуют tenant context и должны соблюдать fail-closed поведение cross-tenant.
- Для staff-пользователя в UI сохраняется guard на mutating без active tenant.

## Risks / Trade-offs
- Риск роста сложности формы run при поддержке обеих направлений.
  - Mitigation: direction-specific UI блоки + строгая клиентская и серверная валидация.
- Риск поломки старых клиентов из-за удаления `source_hash` из публичного create-run контракта.
  - Mitigation: release notes + версия контрактов в OpenAPI + явный `400` с machine-readable ошибкой unsupported field.
- Риск потери изменений топологии при конкурентном редактировании.
  - Mitigation: optimistic concurrency (`version` token) + понятный `409` flow в UI.
- Риск регрессий в OpenAPI и generated clients.
  - Mitigation: contract-first обновление + parity tests + генерация в одном change.

## Migration Plan
1. Обновить OpenAPI и backend сериализаторы/validators (`run_input` обязателен по направлению, `source_hash` удалён из create-run контракта).
2. Реализовать mutating API для pool/topology.
3. Переключить idempotency вычисление на canonicalized `run_input` и удалить legacy ветки с `source_hash`.
4. Расширить frontend API слой и формы `/pools/catalog`, `/pools/runs`.
5. Добавить тесты (backend/frontend/browser smoke).
6. Включить feature в UI после прохождения валидации и тестов.

## Open Questions
- Нет блокирующих открытых вопросов.
- Зафиксировано: в MVP для `bottom_up` поддерживаются оба пути source input (`JSON rows` и `file artifact`) через единый `run_input`.
