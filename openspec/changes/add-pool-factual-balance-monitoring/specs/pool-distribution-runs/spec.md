## MODIFIED Requirements

### Requirement: Pool runs UI MUST запускать распределение с direction-specific входными данными
Система ДОЛЖНА (SHALL) предоставлять на `/pools/runs` форму запуска run, которая:
- выбирает `pool`;
- выбирает явный `pool_workflow_binding`;
- запрашивает и валидирует direction-specific входные данные.

Для `top_down` система ДОЛЖНА (SHALL) поддерживать два operator-facing режима запуска:
- прямой ввод стартовой суммы пользователем;
- batch-backed запуск от canonical `receipt` batch с явным выбором `start_organization`.

Для batch-backed `top_down` система ДОЛЖНА (SHALL):
- требовать явную ссылку на batch;
- требовать явную стартовую организацию из активной topology пула на период run;
- трактовать `one batch = one pool_run`;
- сохранять batch/run lineage в read model и provenance run.

Для `bottom_up` система ДОЛЖНА (SHALL) поддерживать выбор шаблона импорта и ввод/загрузку источника данных из UI.

Create-run payload ДОЛЖЕН (SHALL) содержать явную ссылку на attachment через `pool_workflow_binding_id`.

`pool_workflow_binding_id` ДОЛЖЕН (SHALL) резолвиться к pool-scoped attachment-у, который затем pinned на конкретную `binding_profile_revision_id`.

Public operator-facing `POST /api/v2/pools/runs/` и `POST /api/v2/pools/workflow-bindings/preview/` ДОЛЖНЫ (SHALL) отклонять запрос без explicit binding reference fail-closed, даже если по selector существует ровно один кандидат.

Selector-based matching МОЖЕТ (MAY) использоваться только для UI prefill/assistive hint до submit и НЕ ДОЛЖЕН (SHALL NOT) заменять explicit binding reference на public request boundary.

Preview/create-run path ДОЛЖЕН (SHALL) резолвить attachment только из canonical attachment store и сохранять attachment lineage snapshot, `attachment revision` и pinned `binding_profile_revision_id` на `PoolRun`/execution в момент запуска.

#### Scenario: Top-down run запускается от `receipt` batch и выбранной стартовой организации
- **GIVEN** оператор выбрал pool, attachment, направление `top_down`, canonical `receipt` batch и стартовую организацию
- **WHEN** оператор отправляет форму запуска
- **THEN** run создаётся через `/api/v2/pools/runs/` с explicit `pool_workflow_binding_id` и batch-backed direction-specific входными данными
- **AND** runtime сохраняет batch/run lineage и selected `start_organization`
- **AND** запуск не требует ручного формирования payload во внешнем API-клиенте

### Requirement: Reporting MUST предоставлять сводный и детализированный баланс
Система ДОЛЖНА (SHALL) формировать:
- сводный runtime-отчёт по узлам/уровням пула;
- детальный runtime-отчёт по парам продажа/покупка.

Система ДОЛЖНА (SHALL) рассчитывать строгую проверку сходимости сумм по выбранному периоду и отображать диагностику при разбеге.

Runtime report ДОЛЖЕН (SHALL) оставаться отчётом по расчётным/published artifact-ам конкретного run и НЕ ДОЛЖЕН (SHALL NOT) подменять centralized factual balance monitoring по реальным документам и регистрам ИБ.

Для batch-backed run система ДОЛЖНА (SHALL) показывать из run report явную ссылку или reference на соответствующий batch settlement/factual balance context.

#### Scenario: Оператор отличает run-local отчёт от factual balance dashboard
- **WHEN** оператор открывает отчёт batch-backed run
- **THEN** доступны агрегатный и детализированный runtime режимы отчёта
- **AND** отчёт содержит явный статус сходимости сумм
- **AND** оператор видит ссылку на factual balance context, не смешивая runtime convergence с фактическим остатком в ИБ
