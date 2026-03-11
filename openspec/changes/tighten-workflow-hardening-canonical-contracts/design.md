## Context
`add-refactor-14-workflow-centric-hardening` уже закрепил canonical binding store, shared metadata snapshots и repository-level acceptance evidence. Остаточные риски лежат не в доменной модели, а в delivery boundary:
- default UI path ещё может читать legacy binding payload из `pool.metadata`;
- multi-binding save моделируется как client-side loop поверх single-binding CRUD;
- metadata catalog frontend contract имеет второй typed source-of-truth;
- repository acceptance evidence не отделён формально от tenant-scoped live cutover proof.

Это cross-cutting change: он затрагивает backend API, frontend default workspace, contract/codegen и operator rollout protocol. Поэтому `design.md` нужен до implementation.

## Goals / Non-Goals
- Goals:
  - убрать legacy fallback из default binding workspace;
  - сделать multi-binding save atomic и conflict-safe на уровне коллекции;
  - закрепить generated OpenAPI contract как единственный typed source-of-truth для metadata catalog surface;
  - формализовать tenant-scoped live evidence bundle и fail-closed go/no-go gate.
- Non-Goals:
  - не менять lifecycle semantics `/decisions`;
  - не переделывать binding model или metadata snapshot model заново;
  - не требовать немедленного удаления existing single-binding CRUD, если он нужен как compatibility path.

## Decisions
### Decision 1: Использовать collection-level atomic replace для binding workspace
Default `/pools/catalog` binding workspace редактирует набор bindings как одну логическую сущность. Поэтому сохранение набора должно быть collection operation, а не клиентским циклом из `upsert/delete`.

Рекомендованный контракт:
- dedicated replace endpoint или эквивалентный action-based contract в `/api/v2/pools/workflow-bindings/*`;
- request содержит `pool_id`, полный целевой набор `workflow_bindings[]` и collection concurrency token (`expected_collection_etag` или эквивалент);
- backend внутри одной транзакции вычисляет diff, применяет create/update/delete и возвращает новый collection token;
- при любой validation/conflict ошибке операция отклоняется целиком, без partial apply.

Почему не client-side rollback:
- rollback после частично успешных `upsert/delete` усложняет failure semantics;
- optimistic concurrency на отдельных bindings не покрывает целостность всего workspace;
- UI уже мыслит binding editor как единое состояние, поэтому atomic replace лучше соответствует продуктовой модели.

Внешняя опора: RFC 9110 (`If-Match`) и JSON:API Atomic Operations показывают общий паттерн precondition-based atomic multi-resource update. Здесь используется адаптированный version-token contract, совместимый с текущим Problem Details/`409 Conflict` стилем API.

### Decision 2: Default read path должен быть strict canonical-only
После hardening cutover default shipped path не должен silently гидрировать binding workspace из `pool.metadata["workflow_bindings"]`.

Разрешённые legacy path:
- explicit backfill/import;
- dedicated compatibility tooling;
- tests/fixtures, если они не подменяют shipped default behavior.

Если canonical collection пуста, а legacy metadata присутствует, UI/оператор должен увидеть explicit import state, а не неявное “восстановление” bindings из старого payload.

### Decision 3: Generated metadata catalog contract становится единственным typed source-of-truth
Для `/api/v2/pools/odata-metadata/catalog/` и `/refresh/` нельзя держать parallel hand-written frontend DTO рядом с generated models. Это тот же класс проблемы, что и legacy binding fallback: два конкурирующих источника истины.

Решение:
- OpenAPI `contracts/orchestrator/src/**` остаётся editable source-of-truth;
- generated client/models остаются единственным shipped typed contract для frontend metadata workspace;
- hand-written mirror types не должны использоваться в default runtime path;
- drift между runtime serializer, OpenAPI bundle, generated client и frontend consumer блокирует релиз.

Это согласуется с существующей contract-first моделью проекта и снижает вероятность повторного расхождения shared snapshot markers.

### Decision 4: Нужно разделить repository acceptance evidence и tenant live cutover evidence
Repository acceptance evidence полезен как checked-in proof shipped default path, но он не заменяет tenant-specific rollout proof.

Новый delivery contract:
- checked-in repository evidence остаётся в git как proof shipped behavior;
- tenant cutover доказывается отдельным machine-readable bundle с обязательными refs и sign-off;
- go/no-go для staging/prod fail-closed блокируется, если есть только repository evidence без live bundle.

Bundle должен включать минимум:
- `schema_version`;
- `change_id`;
- `git_sha`;
- `environment`;
- `tenant_id`;
- `runbook_version`;
- `captured_at`;
- `evidence_refs[]` для preview/create-run/inspect-lineage и migration-or-noop outcome;
- `overall_status`;
- `sign_off[]`.

Schema и verifier должны жить в стабильном capability path после archive, чтобы проверка не зависела от archived change directory.

## Alternatives Considered
### Alternative A: Оставить single-binding CRUD как единственный mutating contract
Отклонено. Он не описывает атомарность workspace-save и не исключает partial apply при серии запросов.

### Alternative B: Сохранить hand-written metadata DTO, но усилить тесты
Отклонено. Тесты снизят риск, но не уберут второй typed source-of-truth на shipped path.

### Alternative C: Считать repository evidence достаточным rollout proof
Отклонено. Это доказывает только repository-local shipped behavior, но не tenant-specific operational cutover.

## Risks / Trade-offs
- Atomic replace повышает размер одного mutating запроса и делает collection diff более чувствительным к server-side validation bugs.
- Удаление silent fallback может вскрыть старые tenant'ы, где canonical store не заполнен, но metadata всё ещё содержит legacy bindings.
- Строгий evidence gate замедлит rollout, если операторские артефакты не автоматизированы.
- Сохранение single-binding CRUD как compatibility surface временно оставит два mutating path, поэтому нужно явно зафиксировать, какой из них является default.

## Migration Plan
1. Зафиксировать spec/contract для atomic replace и generated metadata catalog source-of-truth.
2. Реализовать backend collection replace path поверх canonical binding store с collection conflict token.
3. Перевести `/pools/catalog` на новый collection read/save path и убрать metadata fallback из shipped flow.
4. Перевести metadata catalog consumer на generated models и добавить parity gates.
5. Ввести schema-validated evidence bundle, verifier и fail-closed runbook steps.
6. Обновить docs/release notes/cutover notes и только после этого считать hardening fully closed.

## Open Questions
- Открытых архитектурных вопросов нет. Change сознательно не включает redesign `/decisions archive` semantics и не расширяет scope дальше source-of-truth/save/evidence boundary.
