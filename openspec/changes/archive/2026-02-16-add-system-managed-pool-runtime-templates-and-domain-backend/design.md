## Context
В текущем pool runtime есть разрыв между "логическими шагами домена" и "операционными templates":
- шаги pipeline фиксированы кодом компилятора;
- binding шага в runtime идёт через alias (`alias_latest`);
- жизненный цикл templates управляется в общей модели `/templates`.

Для pool-домена это даёт недетерминизм и высокий операционный риск: system-critical pipeline зависит от mutable alias и пользовательского write-path.

## Goals
- Сделать pool runtime templates детерминированными и system-managed.
- Развести ответственность pool execution и generic CLI executor.
- Убрать дрейф выполнения через pinned binding и fail-closed policy.
- Сохранить наблюдаемость (provenance, audit, registry health).

## Non-Goals
- Универсальный "pool driver" и command-schemas для pool шагов.
- Делегирование pool runtime templates в пользовательский self-service.
- Изменение бизнес-алгоритмов распределения.

## Decisions
### Decision 1: System-managed реестр pool runtime templates
- Вводится фиксированный registry alias для pool runtime шагов:
  - `pool.prepare_input`
  - `pool.distribution_calculation.top_down`
  - `pool.distribution_calculation.bottom_up`
  - `pool.reconciliation_report`
  - `pool.approval_gate`
  - `pool.publication_odata`
- Реестр фиксируется contract version `pool_runtime.v1`:
  - версия инвариантно задаёт required aliases и их semantics;
  - introspection обязан возвращать `contract_version` и статус по каждому required alias;
  - изменения списка alias или semantics выполняются только через новую contract version.
- Registry синхронизируется bootstrap-процедурой в unified store (`OperationExposure/OperationDefinition`).
- Эти templates помечаются как system-managed и не редактируются через публичный templates write API.

Почему:
- фиксированный whitelist устраняет "случайные" alias;
- система остаётся source-of-truth, а не ручные UI-операции.

### Decision 2: Отдельный `PoolDomainBackend`
- Runtime вводит выделенный backend, который выполняет pool domain operations через внутренние сервисы домена.
- Backend не зависит от `ibcmd_cli`/`designer_cli` command execution path.

Почему:
- pool pipeline - это доменная оркестрация, а не generic CLI-команды;
- отдельный backend упрощает контроль инвариантов, observability и retry semantics.

### Decision 3: Pinned binding обязателен для pool workflow nodes
- На этапе компиляции workflow node должен содержать `operation_ref(binding_mode=\"pinned_exposure\")` с `template_exposure_id` и `template_exposure_revision`.
- Runtime валидирует drift и работает fail-closed.

Почему:
- детерминированность исполнения run;
- исключение "тихой" смены definition после публикации alias.

### Decision 4: Fail-closed при любых несоответствиях registry/binding
- Missing alias, inactive exposure, revision mismatch, unsupported executor -> отказ до enqueue side-effects.
- Ошибки получают стабильные machine-readable коды.
- Канонический набор fail-closed кодов:
  - `POOL_RUNTIME_TEMPLATE_NOT_CONFIGURED` — required alias отсутствует в registry или не резолвится при compile-time.
  - `POOL_RUNTIME_TEMPLATE_INACTIVE` — pinned exposure найден, но неактивен/непубликован.
  - `TEMPLATE_DRIFT` — pinned revision не совпадает с текущей ревизией exposure.
  - `POOL_RUNTIME_TEMPLATE_UNSUPPORTED_EXECUTOR` — exposure ссылается на executor, не маршрутизируемый в `PoolDomainBackend`.

Почему:
- pool execution high-impact, silent fallback недопустим.

### Decision 5: Introspection и аудит обязательны
- Система должна возвращать статус registry (configured/missing/drift).
- Execution plan и audit должны фиксировать pinned provenance.

Почему:
- операторы и поддержка должны понимать, "что именно выполнялось" и "почему отказалось".

## Alternatives Considered
### Alternative A: Оставить `alias_latest` + ручное управление templates
Отклонена:
- не гарантирует детерминированность;
- оставляет риск drift и accidental edits.

### Alternative B: Pool driver + command-schemas
Отклонена в рамках этого change:
- увеличивает степень конфигурируемости там, где нужна жесткая доменная фиксация;
- усложняет контроль инвариантов через generic schema layer.

## Risks / Trade-offs
- Риск: больше "жестко зафиксированного" поведения в коде.
  - Mitigation: явный registry + introspection + versioned definitions.
- Риск: миграционная сложность при переводе существующих alias в system-managed.
  - Mitigation: bootstrap с dry-run отчетом и обратимой стратегией rollout.
- Риск: добавляется новый backend в execution routing.
  - Mitigation: отдельные routing tests и explicit backend metrics.

## Migration Plan
1. Добавить marker system-managed и registry bootstrap (dry-run + apply).
2. Синхронизировать системные pool runtime exposures/definitions.
3. Включить `PoolDomainBackend` и routing для pool runtime nodes.
4. Переключить compiler на pinned binding для новых run.
5. Добавить drift detection и fail-closed ответы в runtime.
6. Отключить mutating path системных pool templates в публичном API.
7. Выполнить тестовый rollout и мониторинг introspection/metrics.

## Open Questions
- Нужен ли временный feature flag для поэтапного включения pinned binding на production?
- Нужен ли отдельный internal endpoint для "force resync" system-managed registry?
