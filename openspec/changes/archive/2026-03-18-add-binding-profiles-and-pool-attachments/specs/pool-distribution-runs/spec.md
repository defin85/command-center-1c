## MODIFIED Requirements

### Requirement: Run execution MUST быть идемпотентным для одного ключа расчёта
Система ДОЛЖНА (SHALL) использовать idempotency key для create-run на основе:
- `pool_id`;
- `period_start` / `period_end`;
- `direction`;
- `pool_workflow_binding_id`;
- `attachment revision`;
- `binding_profile_revision_id`;
- `canonicalized(run_input)`.

Система НЕ ДОЛЖНА (SHALL NOT) использовать `source_hash` как часть публичного create-run контракта или как часть новой формулы idempotency key.

Повторный запуск с тем же explicit attachment reference, тем же `attachment revision`, тем же `binding_profile_revision_id` и тем же canonicalized `run_input` ДОЛЖЕН (SHALL) обновлять существующий набор результатов/документов (upsert), а не создавать дубликаты.

Смена attachment revision или pinned `binding_profile_revision_id` ДОЛЖНА (SHALL) создавать новый idempotency fingerprint, даже если `pool_workflow_binding_id` и `run_input` остались теми же.

#### Scenario: Повторный запуск с тем же attachment и той же pinned profile revision не создаёт дубликаты
- **GIVEN** run уже выполнен для конкретного `pool_workflow_binding_id`, `attachment revision`, `binding_profile_revision_id` и canonicalized `run_input`
- **WHEN** пользователь запускает повторную обработку с теми же значениями
- **THEN** существующие записи обновляются
- **AND** новые дубликаты документов и строк распределения не появляются

#### Scenario: Repin того же attachment на новую profile revision создаёт новый fingerprint
- **GIVEN** attachment сохранил тот же `pool_workflow_binding_id`
- **AND** его `attachment revision` или pinned `binding_profile_revision_id` изменились
- **WHEN** оператор запускает create-run с тем же `run_input`
- **THEN** система вычисляет новый idempotency key
- **AND** старый run не reuse'ится поверх новой reusable логики

### Requirement: Pool runs UI MUST запускать распределение с direction-specific входными данными
Система ДОЛЖНА (SHALL) предоставлять на `/pools/runs` форму запуска run, которая:
- выбирает `pool`;
- выбирает явный `pool_workflow_binding`;
- запрашивает и валидирует direction-specific входные данные.

Для `top_down` система ДОЛЖНА (SHALL) требовать ввод стартовой суммы распределения пользователем.

Для `bottom_up` система ДОЛЖНА (SHALL) поддерживать выбор шаблона импорта и ввод/загрузку источника данных из UI.

Create-run payload ДОЛЖЕН (SHALL) содержать явную ссылку на attachment через `pool_workflow_binding_id`.

`pool_workflow_binding_id` ДОЛЖЕН (SHALL) резолвиться к pool-scoped attachment-у, который затем pinned на конкретную `binding_profile_revision_id`.

Public operator-facing `POST /api/v2/pools/runs/` и `POST /api/v2/pools/workflow-bindings/preview/` ДОЛЖНЫ (SHALL) отклонять запрос без explicit binding reference fail-closed, даже если по selector существует ровно один кандидат.

Selector-based matching МОЖЕТ (MAY) использоваться только для UI prefill/assistive hint до submit и НЕ ДОЛЖЕН (SHALL NOT) заменять explicit binding reference на public request boundary.

Preview/create-run path ДОЛЖЕН (SHALL) резолвить attachment только из canonical attachment store и сохранять attachment lineage snapshot, `attachment revision` и pinned `binding_profile_revision_id` на `PoolRun`/execution в момент запуска.

#### Scenario: Top-down run запускается из UI с выбранным attachment и стартовой суммой
- **GIVEN** оператор выбрал pool, attachment и направление `top_down`
- **WHEN** оператор вводит стартовую сумму и отправляет форму запуска
- **THEN** run создаётся через `/api/v2/pools/runs/` с explicit `pool_workflow_binding_id` и direction-specific входными данными
- **AND** runtime резолвит pinned `binding_profile_revision_id` через выбранный attachment
- **AND** запуск не требует ручного формирования payload во внешнем API-клиенте

### Requirement: Pool runs UI MUST показывать lineage binding-to-execution как primary domain context
Система ДОЛЖНА (SHALL) показывать в `/pools/runs` lineage запущенного процесса как часть primary domain read-model:
- `pool`;
- selected attachment;
- pinned `binding_profile_revision_id`;
- workflow definition/revision;
- decision snapshot или эквивалентный compiled provenance;
- link на underlying workflow execution diagnostics.

Generic workflow execution surface НЕ ДОЛЖЕН (SHALL NOT) быть обязательной точкой входа для оператора при обычном управлении pool run lifecycle.

#### Scenario: Оператор видит attachment и profile lineage без перехода в generic workflow catalog
- **GIVEN** pool run уже создан и выполняется
- **WHEN** оператор открывает inspect view на `/pools/runs`
- **THEN** экран показывает selected attachment, pinned profile revision и workflow revision
- **AND** ссылка на underlying workflow execution доступна как secondary diagnostics, а не как основной экран
