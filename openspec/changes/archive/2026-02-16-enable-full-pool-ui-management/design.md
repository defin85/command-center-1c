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
- Read endpoint topology snapshot должен возвращать актуальный `version` token для следующего update.

Почему:
- Убирает риск "lost update" при параллельной работе операторов над одним пулом.

### Decision 6: Read-контракт run фиксируется без source_hash и с явной legacy-маркировкой
- Публичный read-контракт run возвращает:
  - `run_input` (`object | null`);
  - `input_contract_version` (`run_input_v1` | `legacy_pre_run_input`).
- Публичный read-контракт не возвращает `source_hash`.

Почему:
- Убирает двусмысленность переходного состояния и делает historical runs интерпретируемыми для UI.

### Decision 7: Canonicalization run_input фиксируется как строгий профиль
- Fingerprint вычисляется по canonicalized `run_input` с профилем:
  - object keys сортируются лексикографически;
  - порядок элементов массивов сохраняется;
  - денежные поля нормализуются в строковый decimal fixed-scale формат;
  - сериализация не зависит от исходного formatting/whitespace.

Почему:
- Исключает дрейф идемпотентности между клиентами и backend реализациями.

### Decision 8: Ошибки новых endpoint'ов унифицируются через Problem Details
- Для create-run и topology mutating endpoint'ов ошибки возвращаются как `application/problem+json`.
- Минимальный обязательный набор полей: `type`, `title`, `status`, `detail`, `code`.

Почему:
- Упрощает машинную обработку ошибок в UI и повышает предсказуемость контрактов.

### Decision 9: Breaking remove source_hash сопровождается контролируемым rollout
- Изменение считается breaking в публичном API и сопровождается обновлением OpenAPI примеров/описаний.
- Перед включением в production обязательны release notes для интеграторов и проверка готовности UI-клиента на `run_input`.

Почему:
- Снижает риск внезапной поломки внешних клиентов после контракного cutover.

## API/Model Considerations
- API:
  - добавить mutating endpoint'ы для пула/топологии;
  - расширить `PoolRunCreateRequest` полем `run_input` и удалить из него `source_hash`.
  - read endpoint topology должен возвращать `version` token, обязательный для mutating update.
- Model:
  - хранить `run_input` в run state (отдельным полем или каноническим под-объектом state-модели);
  - read run-model должен включать `run_input` (nullable) и `input_contract_version`.
- Idempotency:
  - canonicalization `run_input` должна быть детерминированной (stable key order, fixed decimal normalization, format-invariant serialization);
  - одинаковый semantically-equivalent payload должен давать одинаковый fingerprint.
  - `source_hash` не используется в формуле нового idempotency key.
- Errors:
  - create-run/topology mutating ошибки возвращаются как `application/problem+json` с machine-readable `code`.
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
- Риск недетерминированной канонизации `run_input` и ложных idempotency коллизий/расхождений.
  - Mitigation: строгий canonicalization profile + unit/property tests на semantically-equivalent payload.
- Риск регрессий в OpenAPI и generated clients.
  - Mitigation: contract-first обновление + parity tests + генерация в одном change.

## Migration Plan
1. Обновить OpenAPI и backend сериализаторы/validators (`run_input` обязателен по направлению, `source_hash` удалён из create-run контракта).
2. Реализовать mutating API для pool/topology.
3. Добавить round-trip `version` token в read/update flow topology.
4. Переключить idempotency вычисление на canonicalized `run_input` и удалить legacy ветки с `source_hash`.
5. Зафиксировать read-модель historical runs (`run_input` nullable + `input_contract_version`) и исключить публичный `source_hash`.
6. Унифицировать ошибки на `application/problem+json` и обновить frontend error handling.
7. Расширить frontend API слой и формы `/pools/catalog`, `/pools/runs`.
8. Добавить тесты (backend/frontend/browser smoke).
9. Подготовить release notes breaking change и включить feature после прохождения валидации/тестов.

## Open Questions
- Нет блокирующих открытых вопросов.
- Зафиксировано: в MVP для `bottom_up` поддерживаются оба пути source input (`JSON rows` и `file artifact`) через единый `run_input`.
