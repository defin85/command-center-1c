## POOL_MASTER_DATA_GATE Runbook

Цель: быстро локализовать и устранить fail-closed ошибки master-data gate перед `pool.publication_odata`.

### Когда применять

- В execution timeline есть шаг `pool.master_data_gate` со статусом `failed`.
- `pool.publication_odata` не стартует из-за ошибок master-data resolve/sync.
- В диагностике присутствуют коды:
  - `MASTER_DATA_ENTITY_NOT_FOUND`
  - `MASTER_DATA_BINDING_AMBIGUOUS`
  - `MASTER_DATA_BINDING_CONFLICT`

### Что проверяет gate

1. Извлекает master-data токены из `field_mapping` и `table_parts_mapping`:
   - `master_data.party.<canonical_id>.<organization|counterparty>.ref`
   - `master_data.item.<canonical_id>.ref`
   - `master_data.contract.<canonical_id>.<owner_counterparty_canonical_id>.ref`
   - `master_data.tax_profile.<canonical_id>.ref`
2. Резолвит/обновляет per-infobase bindings в режиме `resolve+upsert`.
3. Сохраняет `pool_runtime_master_data_binding_artifact` и обновляет publication payload.

### Быстрая проверка (5 минут)

1. Убедиться, что флаг включён:
   - `POOL_RUNTIME_MASTER_DATA_GATE_ENABLED=true` в runtime settings/env.
2. Проверить в execution `input_context`:
   - `master_data_snapshot_ref`
   - `master_data_binding_artifact_ref`
3. Проверить payload публикации:
   - `pool_runtime.document_chains_by_database[*].documents[*].resolved_master_data_refs`
4. Проверить наличие canonical сущностей в CC:
   - `PoolMasterParty` / `PoolMasterItem` / `PoolMasterContract` / `PoolMasterTaxProfile`.
5. Проверить `metadata.ib_ref_keys` у canonical сущности для target `database_id`.

### Интерпретация кодов

- `MASTER_DATA_ENTITY_NOT_FOUND`
  - Каноническая сущность не найдена в CC для `canonical_id`.
- `MASTER_DATA_BINDING_AMBIGUOUS`
  - Найдено более одного binding для одинакового scope tuple.
- `MASTER_DATA_BINDING_CONFLICT`
  - Некорректный token scope, отсутствует `ib_ref_key` в metadata, либо конфликт валидации binding.

### Ремедиация

1. `ENTITY_NOT_FOUND`:
   - создать/исправить canonical запись в CC.
2. `BINDING_AMBIGUOUS`:
   - устранить дубликаты scope в `pool_master_data_bindings`.
3. `BINDING_CONFLICT`:
   - исправить token в document policy;
   - проверить `metadata.ib_ref_keys[database_id]` для сущности;
   - для `Contract` проверить owner-scope по конкретному counterparty.

### Retry и консистентность

- Retry обязан переиспользовать те же:
  - `master_data_snapshot_ref`
  - `master_data_binding_artifact_ref`
- При диагностике retry сначала проверяйте lineage в `execution.input_context`.
