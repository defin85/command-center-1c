## Context
Сейчас templates живут в смешанной модели:
- `OperationExposure + OperationDefinition` уже выступают unified contract слоем;
- `OperationTemplate` остаётся legacy projection для RBAC/internal/runtime путей.

Эта двойная модель приводит к drift и усложняет сопровождение. Требуется полный cutover в один релиз (Big-bang), без растягивания на несколько релизов.

## Goals / Non-Goals
- Goals:
  - Сделать `OperationExposure(surface="template")` + `OperationDefinition` единственным источником истины для templates.
  - Перевести RBAC/runtime/internal API/operations metadata на exposure-ориентированную модель.
  - Завершить cutover в одном релизе с предсказуемым rollback.
- Non-Goals:
  - Возвращение action-catalog.
  - Переименование внешних API endpoint/field names для клиентов в рамках этого change.

## Decisions
- Decision: Big-bang migration в одном релизе, но в три внутренних фазы в одном deployment окне.
  - Фаза A (Expand+Backfill): подготовка целевых структур, перенос данных и preflight-проверки.
  - Фаза B (Switch): переключение runtime/API/RBAC чтения и записи на exposure-only.
  - Фаза C (Contract): удаление legacy projection-структур и ссылок на `OperationTemplate`.
- Decision: Target RBAC storage для templates становится exposure-ориентированным:
  - user-permissions table: `templates_operation_exposure_permissions` (`user_id`, `exposure_id`, `level`, audit fields),
  - group-permissions table: `templates_operation_exposure_group_permissions` (`group_id`, `exposure_id`, `level`, audit fields),
  - уникальность: (`user_id`,`exposure_id`) и (`group_id`,`exposure_id`).
- Decision: `BatchOperation` больше не хранит FK на `OperationTemplate`.
  - Для template-based операций metadata хранит обязательные поля:
    - `template_id` (alias exposure, string),
    - `template_exposure_id` (UUID exposure).
- Decision: wire-контракт enqueue/details для template-based операций унифицируется:
  - `template_id` обязателен для backward compatibility,
  - `template_exposure_id` обязателен для post-cutover новых записей.
- Decision: `manual_operation_template_bindings` сохраняется, но `template_id` трактуется как alias exposure.
- Alternatives considered:
  - Staged rollout на несколько релизов (меньше риск миграции, но дольше период двойной модели и drift).
  - Сохранение `OperationTemplate` как постоянной read-model (не закрывает технический долг и поддерживает лишнюю сложность).

## Target Architecture
- Templates persistence:
  - `OperationDefinition` хранит canonical execution payload.
  - `OperationExposure(surface="template")` хранит публикацию/alias/status/capability.
- RBAC:
  - Права templates резолвятся по exposure-ориентированным сущностям (через `exposure_id`), без FK на `OperationTemplate`.
  - RBAC endpoints/effective-access используют только exposure permission tables.
- Runtime:
  - Workflow operation node резолвит template по exposure alias.
  - Internal template endpoints читают/рендерят данные через exposure+definition.
- Operations:
  - `BatchOperation` и related metadata используют template reference через `template_id` (alias) + `template_exposure_id` (UUID).

## Runtime Failure Semantics (Fail-Closed)
- `template alias not found` -> ошибка `TEMPLATE_NOT_FOUND`, операция не enqueue-ится/переходит в failed без retry.
- `template exposure status != published` или `is_active=false` -> ошибка `TEMPLATE_NOT_PUBLISHED`, без auto-fallback.
- `definition payload invalid/incompatible` -> ошибка `TEMPLATE_INVALID`, без auto-repair в runtime path.
- Любая из этих ошибок НЕ ДОЛЖНА инициировать fallback на `OperationTemplate`.

## Legacy Objects: Drop/Keep Matrix
- Drop (в contract-фазе того же релиза):
  - `operation_templates`,
  - `templates_operation_template_permissions`,
  - `templates_operation_template_group_permissions`,
  - `batch_operations.template_id` FK/column + связанные индексы/constraints.
- Keep:
  - `manual_operation_template_bindings` (alias-based reference),
  - исторические записи details/metadata (читаются через exposure-based reference).

## Rollout Plan (One Release)
1. Preflight
- Alias integrity:
  - отсутствуют дубли по `(surface="template", alias)` в глобальном/tenant scope.
- Referential readiness:
  - для всех активных legacy templates найден/создаётся exposure+definition mapping.
  - для всех legacy template permissions найден exposure mapping.
- Operations readiness:
  - для `batch_operations` с template reference присутствует resolvable alias mapping.
- Code-path gate:
  - статический gate (grep/tests) подтверждает отсутствие runtime/internal/rbac dependency на `OperationTemplate` в целевых путях switch.
- Preflight thresholds:
  - critical mismatches = 0,
  - unresolved template mappings = 0,
  - unresolved permission mappings = 0.

2. Expand + Backfill
- Создание exposure-permission tables и индексов.
- Backfill user/group template permissions -> exposure permissions.
- Backfill operation metadata:
  - заполнение `template_exposure_id` по alias mapping,
  - сохранение `template_id` как alias.
- Контрольные parity-сверки до switch:
  - counts parity по permission rows (direct/group),
  - parity effective access для выборки smoke-пользователей,
  - parity resolve template для критических runtime/internal сценариев.

3. Switch
- Включение exposure-only paths в runtime, internal API, RBAC, operations metadata.
- Переключение enqueue/message contract на обязательный `template_id` + `template_exposure_id`.
- Smoke/regression в том же окне релиза по критическим сценариям:
  - workflow operation execution,
  - internal get-template/render-template,
  - rbac templates/effective-access,
  - operations details/provenance.

4. Contract
- Удаление legacy projection и всех перечисленных зависимостей из матрицы Drop/Keep.
- Повторная smoke-проверка и фиксация post-cutover состояния.

## Rollback Strategy
- Для Big-bang применяется только полный rollback релиза:
  - восстановление БД из pre-cutover backup,
  - откат application deploy до предыдущего артефакта.
- Частичный rollback (только код или только схема) не считается безопасным и не поддерживается.

## Risks / Trade-offs
- Риск потери RBAC parity при ошибке backfill.
  - Mitigation: preflight parity checks и обязательный staging dry-run.
- Риск runtime outage при пропущенной зависимости на `OperationTemplate`.
  - Mitigation: grep-based gate + integration tests по критическим путям.
- Риск долгой миграции и блокировок.
  - Mitigation: окно обслуживания, подготовленные индексы/ограничения, rehearsed runbook.
- Риск несовместимости отдельных historical metadata записей.
  - Mitigation: backward-compatible reader path (`template_id` + optional `template_exposure_id` для legacy).

## Go / No-Go Checklist
- Go:
  - preflight critical mismatches = 0,
  - RBAC parity mismatch = 0 для обязательной smoke-выборки,
  - runtime/internal template resolve failures = 0 на rehearsal,
  - staging rehearsal успешно повторяет production steps,
  - rollback rehearsal подтверждён (backup restore + previous deploy).
- No-Go:
  - найдена data inconsistency без автоматической коррекции,
  - parity mismatch в критических RBAC/runtime сценариях,
  - невозможность гарантированного restore rollback пути.

## Exit Criteria for Next Changes
- После завершения этого change новые модули (включая intercompany) используют только exposure-based template contract.
- Любой новый enqueue/details provenance обязан опираться на `template_id`(alias)+`template_exposure_id`, без зависимости на `OperationTemplate`.
