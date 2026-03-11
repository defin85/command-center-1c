## MODIFIED Requirements
### Requirement: Pool runs UI MUST запускать распределение с direction-specific входными данными
Система ДОЛЖНА (SHALL) предоставлять на `/pools/runs` форму запуска run, которая:
- выбирает `pool`;
- выбирает или детерминированно резолвит `pool_workflow_binding`;
- запрашивает и валидирует direction-specific входные данные.

Для `top_down` система ДОЛЖНА (SHALL) требовать ввод стартовой суммы распределения пользователем.

Для `bottom_up` система ДОЛЖНА (SHALL) поддерживать выбор шаблона импорта и ввод/загрузку источника данных из UI.

Create-run payload ДОЛЖЕН (SHALL) содержать ссылку на binding (`pool_workflow_binding_id` или эквивалентный канонический binding reference).

#### Scenario: Top-down run запускается из UI с выбранным binding и стартовой суммой
- **GIVEN** оператор выбрал pool, binding и направление `top_down`
- **WHEN** оператор вводит стартовую сумму и отправляет форму запуска
- **THEN** run создаётся через `/api/v2/pools/runs/` с binding reference и direction-specific входными данными
- **AND** запуск не требует ручного формирования payload во внешнем API-клиенте

#### Scenario: UI create-run payload содержит binding reference и не содержит source_hash
- **GIVEN** оператор запускает run через `/pools/runs`
- **WHEN** UI формирует payload для `POST /api/v2/pools/runs/`
- **THEN** payload содержит `run_input` и binding reference
- **AND** payload не содержит `source_hash`

#### Scenario: Bottom-up run запускается из UI с выбранным binding, шаблоном и source payload
- **GIVEN** оператор выбрал направление `bottom_up`
- **WHEN** оператор выбирает binding, schema template и задаёт источник входных данных в UI
- **THEN** run запускается через канонический endpoint
- **AND** дальнейший lifecycle доступен в том же UI без ручных API-вызовов

## ADDED Requirements
### Requirement: Pool runs UI MUST показывать lineage binding-to-execution как primary domain context
Система ДОЛЖНА (SHALL) показывать в `/pools/runs` lineage запущенного процесса как часть primary domain read-model:
- `pool`;
- selected binding;
- workflow definition/revision;
- decision snapshot или эквивалентный compiled provenance;
- link на underlying workflow execution diagnostics.

Generic workflow execution surface НЕ ДОЛЖЕН (SHALL NOT) быть обязательной точкой входа для оператора при обычном управлении pool run lifecycle.

#### Scenario: Оператор видит lineage run без перехода в generic workflow catalog
- **GIVEN** pool run уже создан и выполняется
- **WHEN** оператор открывает inspect view на `/pools/runs`
- **THEN** экран показывает binding lineage и workflow revision
- **AND** ссылка на underlying workflow execution доступна как secondary diagnostics, а не как основной экран
