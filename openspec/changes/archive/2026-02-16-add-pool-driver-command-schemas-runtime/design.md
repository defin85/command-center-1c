## Context
Система уже использует schema-driven подход для части executor (`ibcmd_cli`, `designer_cli`) через `driver + command-schemas + template editor`.

Pool runtime шаги пока остаются отдельным доменным контуром с хардкодом alias, что мешает унификации конфигурации и self-service в `/templates`.

Этот change фиксирует альтернативную архитектуру: pool runtime как еще один driver в command-schemas ecosystem.

## Goals
- Унифицировать pool runtime с существующим schema-driven контуром.
- Сделать pool шаги управляемыми как templates в `/templates`.
- Использовать единый validation/preview/provenance pipeline для всех executor kinds.
- Снизить объем "специального" кода в pool runtime.

## Non-Goals
- Введение отдельного `PoolDomainBackend`.
- Полная изоляция pool templates как system-managed read-only объектов.
- Переписывание бизнес-логики распределения.

## Decisions
### Decision 1: Новый driver `pool` в command catalogs
- Добавляется driver-level schema `pool`.
- Добавляются command schemas для обязательных шагов pool pipeline.
- Command schema становится source-of-truth для допустимых params.

Почему:
- единая схема описания команд и валидации;
- reuse существующего command-schemas tooling.

### Decision 2: Executor kind `pool_driver` в operation templates
- `OperationDefinition.executor_kind` расширяется значением `pool_driver`.
- `executor_payload` содержит `driver=pool`, `command_id`, `params`.
- Валидация через effective command schema по `driver+command_id`.

Почему:
- сохраняется единый template lifecycle;
- проще объяснять оператору поведение через существующий templates UX.

### Decision 3: Execution через schema-driven backend/adapter
- Runtime routing для `pool_driver` идёт через schema-driven backend adapter.
- Adapter переводит `command_id + params` в вызов соответствующего pool domain service.

Почему:
- pool команды включаются в общий execution path;
- уменьшается количество отдельных backend классов.

### Decision 4: Pool workflow compiler использует templates, привязанные к `pool_driver`
- Шаги workflow компилируются с alias templates, где template definition указывает `executor_kind=pool_driver`.
- Для rollout допускается `alias_latest`; policy pinned может включаться отдельно.

Почему:
- проще миграция с текущего alias-based контракта;
- сохраняется backward-compatible путь переключения.

### Decision 5: `sync from registry` использует command catalog `pool`
- Реестр шаблонов для pool runtime синхронизируется на базе `pool` command catalog.
- Каталог команд и templates остаются согласованными автоматически.

Почему:
- одна точка истины для доступных pool команд;
- снижает рассинхронизацию "код vs templates".

## Alternatives Considered
### Alternative A: System-managed templates + PoolDomainBackend + pinned binding
Отклонена в рамках этого change:
- меньше гибкости для операторских изменений;
- отдельный backend и отдельный lifecycle создают новый специализированный контур.

### Alternative B: Сохранить текущий hardcoded подход
Отклонена:
- ограниченная расширяемость;
- недостаточная прозрачность и управляемость через общий templates UX.

## Risks / Trade-offs
- Риск: увеличивается степень конфигурируемости для критичных pool шагов.
  - Mitigation: strict schema validation, RBAC, publish workflow, policy-based restrictions.
- Риск: alias-latest может приводить к drift без pinned enforcement.
  - Mitigation: отдельный runtime setting для включения обязательного pinned режима.
- Риск: pool domain semantics сложнее выразить в generic command-schemas.
  - Mitigation: добавить domain-level validators и adapter checks сверх схемы.

## Migration Plan
1. Добавить driver `pool` и command schemas в catalogs.
2. Расширить templates model/editor поддержкой `pool_driver`.
3. Создать pool runtime templates на базе новых command schemas.
4. Переключить workflow routing pool шагов на `pool_driver` backend adapter.
5. Включить monitoring и policy checks для drift/validation ошибок.
6. (Опционально) включить pinned enforcement после стабилизации.

## Open Questions
- Нужен ли запрет на редактирование части "критичных" pool commands (например `publication_odata`) даже в driver-модели?
- Должен ли `pool_driver` быть доступен всем tenant admin или только staff?
