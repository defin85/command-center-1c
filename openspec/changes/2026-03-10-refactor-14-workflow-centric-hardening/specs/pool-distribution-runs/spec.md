## MODIFIED Requirements
### Requirement: Pool runs UI MUST запускать распределение с direction-specific входными данными
Система ДОЛЖНА (SHALL) предоставлять на `/pools/runs` форму запуска run, которая:
- выбирает `pool`;
- выбирает явный `pool_workflow_binding`;
- запрашивает и валидирует direction-specific входные данные.

Для `top_down` система ДОЛЖНА (SHALL) требовать ввод стартовой суммы распределения пользователем.

Для `bottom_up` система ДОЛЖНА (SHALL) поддерживать выбор шаблона импорта и ввод/загрузку источника данных из UI.

Create-run payload ДОЛЖЕН (SHALL) содержать явную ссылку на binding через `pool_workflow_binding_id`.

Public operator-facing `POST /api/v2/pools/runs/` и `POST /api/v2/pools/workflow-bindings/preview/` ДОЛЖНЫ (SHALL) отклонять запрос без explicit binding reference fail-closed, даже если по selector существует ровно один кандидат.

Selector-based matching МОЖЕТ (MAY) использоваться только для UI prefill/assistive hint до submit и НЕ ДОЛЖЕН (SHALL NOT) заменять explicit binding reference на public request boundary.

Preview/create-run path ДОЛЖЕН (SHALL) резолвить binding только из canonical binding store и сохранять binding lineage snapshot на `PoolRun`/execution в момент запуска.

#### Scenario: Top-down run запускается из UI с выбранным binding и стартовой суммой
- **GIVEN** оператор выбрал pool, binding и направление `top_down`
- **WHEN** оператор вводит стартовую сумму и отправляет форму запуска
- **THEN** run создаётся через `/api/v2/pools/runs/` с explicit `pool_workflow_binding_id` и direction-specific входными данными
- **AND** запуск не требует ручного формирования payload во внешнем API-клиенте

#### Scenario: Public create-run запрос без binding reference отклоняется fail-closed
- **GIVEN** для выбранного pool существует workflow-centric binding
- **WHEN** внешний клиент отправляет `POST /api/v2/pools/runs/` без `pool_workflow_binding_id`
- **THEN** система возвращает fail-closed validation/problem-details ошибку
- **AND** runtime не пытается silently выбрать binding по selector вместо клиента

#### Scenario: Run сохраняет binding lineage snapshot из canonical store
- **GIVEN** оператор запускает run с explicit `pool_workflow_binding_id`
- **AND** canonical binding store возвращает pinned workflow revision, `decisions`, `parameters` и `role_mapping`
- **WHEN** create-run успешно создаёт execution
- **THEN** `PoolRun`/execution сохраняет lineage snapshot выбранного binding
- **AND** последующий inspect использует этот snapshot как deterministic provenance
