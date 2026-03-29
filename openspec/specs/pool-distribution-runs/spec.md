# pool-distribution-runs Specification

## Purpose
Определяет execution-centric lifecycle `PoolRun`, manual и batch-backed launch modes, publication reporting и explicit handoff из run report в factual workspace.
## Requirements
### Requirement: Distribution runs MUST поддерживать фиксированный lifecycle и режимы безопасности
Система ДОЛЖНА (SHALL) поддерживать lifecycle run в состояниях:
- `draft -> validated -> publishing -> partial_success|published|failed`.

В рамках этого change данный lifecycle фиксируется как внешний доменный контракт facade; источник исполнения и проекции статусов определяется unified runtime change.

Система ДОЛЖНА (SHALL) поддерживать режимы:
- `safe`: публикация после проверок и явного решения пользователя,
- `unsafe`: публикация без этапа ручного подтверждения.

#### Scenario: Safe run требует явного решения перед публикацией
- **GIVEN** run запущен в режиме `safe`
- **WHEN** завершена валидация и сформированы предупреждения/ошибки данных
- **THEN** переход к публикации выполняется только после явного подтверждения пользователя
- **AND** решение фиксируется в audit trail

### Requirement: Top-down algorithm MUST быть детерминируемым и учитывать ограничения рёбер
Система ДОЛЖНА (SHALL) выполнять top-down распределение с использованием ограничений ребра (`weight`, `min_amount`, `max_amount`) и `seed`.

При округлении денежный остаток ДОЛЖЕН (SHALL) переноситься на последнего child узла.

#### Scenario: Повторный run с тем же seed даёт те же суммы
- **GIVEN** одинаковые входные данные, период, структура пула и `seed`
- **WHEN** пользователь запускает top-down run повторно
- **THEN** детальные суммы распределения совпадают
- **AND** итог по узлам сходится строго

### Requirement: Bottom-up import MUST использовать файл как источник истины
Система ДОЛЖНА (SHALL) в bottom-up режиме воспринимать входной файл как источник фактических продаж и агрегировать суммы снизу-вверх до root.

Строки с неизвестным ИНН ДОЛЖНЫ (SHALL) фиксироваться как диагностические ошибки, но run НЕ ДОЛЖЕН (SHALL NOT) автоматически останавливаться.

#### Scenario: Неизвестный ИНН фиксируется без автоматического стопа run
- **GIVEN** во входном XLSX есть строка с ИНН, отсутствующим в активной версии пула
- **WHEN** выполняется импорт
- **THEN** строка помечается ошибкой в диагностике
- **AND** run продолжает обработку остальных строк

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

### Requirement: Reporting MUST предоставлять сводный и детализированный баланс
Система ДОЛЖНА (SHALL) формировать:
- сводный runtime-отчёт по узлам/уровням пула;
- детальный runtime-отчёт по парам продажа/покупка.

Система ДОЛЖНА (SHALL) рассчитывать строгую проверку сходимости сумм по выбранному периоду и отображать диагностику при разбеге.

Runtime report ДОЛЖЕН (SHALL) оставаться отчётом по расчётным/published artifact-ам конкретного run и НЕ ДОЛЖЕН (SHALL NOT) подменять centralized factual balance monitoring по реальным документам и регистрам ИБ.

Для batch-backed run система ДОЛЖНА (SHALL) показывать из run report явную ссылку или reference на соответствующий batch settlement/factual balance context.

`/pools/runs` ДОЛЖЕН (SHALL) оставаться execution-centric surface и НЕ ДОЛЖЕН (SHALL NOT) становиться primary workspace для factual monitoring, `unattributed` review или late-correction reconcile.

#### Scenario: Оператор отличает run-local отчёт от factual balance dashboard
- **WHEN** оператор открывает отчёт batch-backed run
- **THEN** доступны агрегатный и детализированный runtime режимы отчёта
- **AND** отчёт содержит явный статус сходимости сумм
- **AND** оператор видит ссылку на factual balance context, не смешивая runtime convergence с фактическим остатком в ИБ

### Requirement: Module MUST предоставить внешние API для запуска и дозаписи
Система ДОЛЖНА (SHALL) предоставить внешние endpoint'ы для:
- запуска run,
- чтения статуса/деталей run,
- повторной дозаписи failed-частей.

Фактическая реализация execution-path для этих endpoint'ов ДОЛЖНА (SHALL) быть перенесена и зафиксирована в `refactor-unify-pools-workflow-execution-core`.

#### Scenario: Внешний клиент выполняет дозапись failed-частей
- **GIVEN** run завершился в `partial_success`
- **WHEN** внешний клиент вызывает endpoint retry
- **THEN** система запускает повторную публикацию только для failed-целей
- **AND** обновляет статусы публикации в том же run

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
- передавать `batch_id` и `start_organization_id` как explicit direction-specific input на public request boundary;
- трактовать `one batch = one pool_run`;
- использовать batch-aware idempotency fingerprint, который различает batch-backed path и manual `starting_amount` path;
- сохранять batch/run lineage в read model и provenance run.

Для документов, создаваемых в результате batch-backed run, система ДОЛЖНА (SHALL) публиковать machine-readable comment marker, совместимый с factual balance monitoring contract.

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
- **AND** batch-backed input содержит явные `batch_id` и `start_organization_id`
- **AND** runtime сохраняет batch/run lineage и selected `start_organization`
- **AND** запуск не требует ручного формирования payload во внешнем API-клиенте

### Requirement: Pool runs UI MUST поддерживать полный операторский lifecycle run
Система ДОЛЖНА (SHALL) предоставлять в `/pools/runs` полный операторский контроль run lifecycle: создание, мониторинг статуса/provenance, safe-команды (`confirm-publication`, `abort-publication`) и retry failed-целей.

Система ДОЛЖНА (SHALL) структурировать интерфейс `/pools/runs` как stage-based workflow (create, inspect, safe actions, retry), чтобы каждый этап имел отдельный фокус и не перегружал пользователя нерелевантными controls.

Система ДОЛЖНА (SHALL) сохранять единый контекст выбранного `run` при переходе между этапами, без повторного ручного выбора на каждом шаге.

#### Scenario: Safe run проходит pre-publish и подтверждается из UI
- **GIVEN** run запущен в режиме `safe`
- **WHEN** run достигает состояния ожидания подтверждения
- **THEN** оператор подтверждает публикацию кнопкой в UI
- **AND** run продолжает публикацию без внешних HTTP-клиентов

#### Scenario: Retry failed выполняется из UI для частично успешного run
- **GIVEN** run находится в `partial_success`
- **WHEN** оператор инициирует retry failed-целей из интерфейса
- **THEN** UI вызывает retry endpoint
- **AND** обновлённый статус run отображается в том же интерфейсе

#### Scenario: UI корректно отображает ошибки create-run в Problem Details формате
- **GIVEN** backend отклонил create-run запрос
- **WHEN** ответ возвращён как `application/problem+json`
- **THEN** UI показывает `detail` оператору
- **AND** использует machine-readable `code` для привязки к конкретному полю/действию

#### Scenario: Оператор последовательно проходит этапы без перегруженного единого полотна
- **GIVEN** оператор создал run на этапе `create`
- **WHEN** оператор переходит к этапам `inspect` и `safe/retry`
- **THEN** интерфейс показывает только controls текущего этапа
- **AND** выбранный run context сохраняется между этапами

### Requirement: Pool run distribution MUST гарантировать полное покрытие активной цепочки организаций
Система ДОЛЖНА (SHALL) рассчитывать распределение для create-run path на основе активной версии DAG topology (`effective_from/effective_to`) за период run.

Система ДОЛЖНА (SHALL) обеспечивать, что распределение покрывает активную цепочку организаций, участвующую в публикации, и не оставляет нераспределённый денежный остаток вне допуска денежной точности.

#### Scenario: Top-down распределение полностью покрывает многоуровневую цепочку
- **GIVEN** активный граф пула содержит многоуровневую цепочку `root -> level1 -> level2`
- **AND** run запущен в `top_down` со стартовой суммой
- **WHEN** выполняется шаг `distribution_calculation.top_down`
- **THEN** суммы распределяются по рёбрам с учётом `weight/min_amount/max_amount`
- **AND** итоговая сумма по целевым узлам совпадает с исходной суммой в пределах денежной точности
- **AND** в runtime artifact нет gaps покрытия для активных publish-target узлов

#### Scenario: Bottom-up распределение сходится к root без потери входной суммы
- **GIVEN** run запущен в `bottom_up` и содержит валидный source payload
- **WHEN** выполняется шаг `distribution_calculation.bottom_up`
- **THEN** суммы агрегируются по активной topology до root
- **AND** `root_total` совпадает с суммой принятых входных строк в пределах денежной точности
- **AND** при несходимости run маркируется fail-closed до шага публикации

### Requirement: Create-run publication payload MUST строиться из distribution artifacts
Система ДОЛЖНА (SHALL) формировать `pool_runtime_publication_payload.documents_by_database` для create-run path из канонического runtime distribution artifact.

Система НЕ ДОЛЖНА (SHALL NOT) использовать raw `run_input` как authoritative источник итогового publication payload, если рассчитанный distribution artifact уже сформирован.

Система ДОЛЖНА (SHALL) принимать `run_input.documents_by_database` в create-run только как `provenance-only` вход для аудита/диагностики и не использовать его для переопределения расчётного payload.

#### Scenario: Runtime игнорирует raw publication payload при наличии расчётного artifact
- **GIVEN** create-run запрос содержит `run_input` с полем `documents_by_database`
- **AND** шаги распределения успешно сформировали канонический distribution artifact
- **WHEN** runtime формирует payload для `pool.publication_odata`
- **THEN** используется payload из distribution artifact
- **AND** raw `run_input.documents_by_database` не может обойти инварианты покрытия и сходимости

#### Scenario: Raw create-run payload сохраняется только как provenance
- **GIVEN** create-run запрос содержит `run_input.documents_by_database`
- **AND** distribution шаги завершились успешно с `distribution_artifact.v1`
- **WHEN** run сохраняется и публикуется
- **THEN** raw payload сохраняется только в provenance/diagnostics контексте
- **AND** финальный publication payload формируется исключительно из `distribution_artifact.v1`

### Requirement: Pool runs diagnostics UI MUST использовать progressive disclosure
Система ДОЛЖНА (SHALL) показывать тяжёлые диагностические блоки (`Run Input`, `Validation Summary`, `Publication Summary`, `Step Diagnostics`) по запросу оператора, а не в полном виде по умолчанию.

Система ДОЛЖНА (SHALL) сохранять полноту диагностической информации и доступ к ней в один шаг из контекста выбранного run.

#### Scenario: Диагностика раскрывается по требованию оператора
- **GIVEN** оператор анализирует run в разделе inspect
- **WHEN** оператор включает отображение diagnostics
- **THEN** UI раскрывает детальные JSON-блоки
- **AND** без включения diagnostics базовый экран остаётся компактным и читаемым

#### Scenario: Retry-form остаётся доступной без визуальной конкуренции с diagnostics
- **GIVEN** оператор находится на этапе retry failed targets
- **WHEN** diagnostics блоки не требуются для текущего действия
- **THEN** retry form отображается как основной фокус экрана
- **AND** diagnostic секции не отвлекают от завершения retry операции

### Requirement: Pool runs MUST поддерживать профиль `minimal_documents_full_payload` для top-down acceptance
Система MUST предоставлять режим запуска, в котором количество публикуемых документов минимизируется до необходимого для активной цепочки, но каждый документ остаётся полно заполненным по заранее объявленному completeness profile.

#### Scenario: Оператор запускает top-down run с минимальным числом документов без потери полноты payload
- **GIVEN** активная topology и выбран профиль `minimal_documents_full_payload`
- **WHEN** оператор запускает run из UI
- **THEN** runtime формирует минимально необходимый набор документов для целевых узлов
- **AND** каждый документ проходит проверку полноты до перехода к `publication_odata`

### Requirement: Dev acceptance path MUST исполнять run lifecycle через live UI/API контур
Для приемки на dev система MUST поддерживать end-to-end сценарий `create -> confirm (safe) -> publish -> report` через реальные API endpoints без тестовых моков транспортного или run-пути.

#### Scenario: Run проходит полный lifecycle через UI и возвращает прозрачный отчёт
- **GIVEN** readiness блокеры отсутствуют
- **WHEN** оператор выполняет run lifecycle из UI
- **THEN** run достигает terminal статуса через реальный runtime path
- **AND** UI report отображает актуальные attempts, readiness и verification summary

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

### Requirement: `/pools/runs` MUST использовать stage-based platform workspace composition
Система ДОЛЖНА (SHALL) реализовать `/pools/runs` как stage-based platform workspace, где create, inspect, safe actions и retry/remediation представлены как явные operator stages с единым selected run context.

Selected run и active stage ДОЛЖНЫ (SHALL) быть URL-addressable и восстанавливаться после reload, deep-link и browser back/forward без повторного ручного выбора run.

Heavy diagnostics ДОЛЖНЫ (SHALL) оставаться progressive disclosure внутри inspect context. Route НЕ ДОЛЖЕН (SHALL NOT) возвращаться к монолитному default canvas, где create form, large diagnostics, safe actions и retry controls одновременно конкурируют как primary content.

На narrow viewport inspect и remediation flows ДОЛЖНЫ (SHALL) использовать mobile-safe secondary surface или route/state fallback без page-wide horizontal overflow.

#### Scenario: Reload сохраняет выбранный run и текущий stage
- **GIVEN** оператор работает с конкретным run на этапе inspect, safe actions или retry
- **WHEN** страница перезагружается или открывается deep-link на этот run
- **THEN** UI восстанавливает selected run и active stage
- **AND** оператор продолжает lifecycle flow без повторного ручного выбора того же run

#### Scenario: Узкий viewport не сводит lifecycle к единому перегруженному полотну
- **GIVEN** оператор открывает `/pools/runs` на narrow viewport
- **WHEN** он переходит между create, inspect и retry/remediation
- **THEN** secondary detail и diagnostics открываются в mobile-safe fallback surface или отдельном stage context
- **AND** основной lifecycle flow остаётся читаемым без page-wide horizontal scroll
