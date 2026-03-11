# Change: Добавить `config_generation_id` в metadata snapshots и `/decisions`

## Why
Сейчас `Config version` в metadata snapshot/read-model фактически зависит от `Database.version`. На живых базах это поле часто пустое, а standard OData не отдаёт человекочитаемую версию конфигурации.

При этом в проекте уже есть рабочий Designer execution path, а в CLI catalog присутствует `GetConfigGenerationID`. Это даёт нам platform-level технический marker текущего metadata state без внедрения extension и без зависимости от RAS.

Нужен узкий change, который:
- добавляет auditable technical marker для metadata-aware authoring на `/decisions`;
- не подменяет им `config_version`;
- не меняет shared snapshot identity и не размывает текущий `metadata_hash`-based contract.

## What Changes
- Добавить отдельный nullable marker `config_generation_id`, получаемый через существующий Designer path командой `GetConfigGenerationID` для выбранной ИБ.
- Возвращать `config_generation_id` в metadata catalog/read-model и в decision metadata context как отдельное поле provenance, не смешивая его с canonical shared snapshot identity.
- Показывать `config_generation_id` в `/decisions` как отдельный technical marker рядом с `config_version`, а не вместо него.
- Сохранить `config_version` как отдельное optional display field; change НЕ ДОЛЖЕН подменять `config_version` значением generation id.
- Явно зафиксировать, что `config_generation_id` не вычисляется из OData, `Database.version`, RAS или extension-specific endpoint в рамках этого change.

## Impact
- Affected specs:
  - `organization-pool-catalog`
  - `pool-document-policy`
  - `workflow-decision-modeling`
- Affected code (expected):
  - `orchestrator/apps/intercompany_pools/**`
  - `orchestrator/apps/api_v2/views/decisions.py`
  - `orchestrator/apps/operations/**`
  - `frontend/src/pages/Decisions/**`
  - `contracts/orchestrator/**`

## Non-Goals
- Не получать человекочитаемую business/version string вида `11.x.x.x` из runtime.
- Не внедрять extension-based HTTP endpoint для версии конфигурации.
- Не менять canonical shared snapshot identity, основанную на configuration-scoped markers и `metadata_hash`.
- Не переводить compatibility matching на `config_generation_id` в этом change.

## Breaking Changes
- Нет. Изменения additive для API/read-model, но требуют синхронизации OpenAPI/generated clients/UI.
