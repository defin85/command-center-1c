## ADDED Requirements
### Requirement: Runtime MUST выполнять master-data gate до `pool.publication_odata`
Система ДОЛЖНА (SHALL) перед запуском шага `pool.publication_odata` выполнять обязательный pre-publication gate:
1. извлечь ссылки на master-data из `document_plan_artifact`;
2. выполнить `resolve+upsert` этих сущностей в каждой target ИБ через canonical hub;
3. сохранить результат как `master_data_binding_artifact`;
4. только после успешного gate разрешить переход к `pool.publication_odata`.

Система НЕ ДОЛЖНА (SHALL NOT) запускать публикационный шаг, если master-data gate завершился ошибкой.

#### Scenario: Успешный master-data gate разрешает publication transition
- **GIVEN** `document_plan_artifact` валиден и master-data resolve/sync успешен по всем target ИБ
- **WHEN** runtime выполняет pre-publication sequence
- **THEN** в execution context сохраняется `master_data_binding_artifact_ref`
- **AND** run переходит к `pool.publication_odata`

#### Scenario: Ошибка master-data gate блокирует publication transition
- **GIVEN** хотя бы одна target ИБ вернула conflict/ambiguous результат resolve/sync
- **WHEN** runtime оценивает переход к `pool.publication_odata`
- **THEN** publication step не запускается
- **AND** execution завершается fail-closed с machine-readable master-data error code

### Requirement: Retry MUST переиспользовать immutable `master_data_snapshot_ref`
Система ДОЛЖНА (SHALL) фиксировать на create-run immutable `master_data_snapshot_ref`, который используется для resolve/sync и публикации.

Система ДОЛЖНА (SHALL) при retry использовать тот же `master_data_snapshot_ref` исходного run, чтобы исключить drift master-data между попытками в рамках одного run lineage.

#### Scenario: Retry публикации использует тот же snapshot master-data
- **GIVEN** исходный run уже сохранил `master_data_snapshot_ref`
- **WHEN** оператор запускает retry failed publication
- **THEN** runtime использует тот же `master_data_snapshot_ref`
- **AND** не подменяет snapshot на более новый без отдельного нового run
