# Change: Перевести reuse metadata snapshots и decision revisions на business identity конфигурации

## Why
Сейчас shared metadata snapshot identity и compatibility `decision_revision` зависят от `config_name`, `config_version`, `extensions_fingerprint` и `metadata_hash`.

На практике это создаёт два неверных связывания:
- `config_name` фактически берётся из имени ИБ (`base_name` / `infobase_name`), а не из самой конфигурации;
- `metadata_hash` отражает published OData surface и publication state, а не business identity прикладного решения.

Из-за этого две ИБ с одной и той же конфигурацией и релизом не могут штатно переиспользовать shared metadata snapshot и `decision_revision`, если:
- у них разные имена ИБ;
- администратор доопубликовал OData composition по-разному;
- metadata payload отличается по operational причинам, а не по бизнес-составу конфигурации.

Для analyst-facing workflow/decision authoring это слишком жёсткая граница. Бизнес-требование для reuse здесь должно опираться только на конфигурацию и её релиз, например `Бухгалтерия предприятия, редакция 3.0` + `3.0.193.19`.

## What Changes
- Переопределить `config_name` и `config_version` как business-level identity конфигурации, получаемую из root configuration properties, а не из имени ИБ и не из `Database.version`.
- Зафиксировать, что shared metadata snapshot reuse и compatibility `decision_revision` опираются только на связку `config_name + config_version`.
- Явно исключить имя ИБ, `metadata_hash`, `extensions_fingerprint` и `config_generation_id` из compatibility/reuse key.
- Сохранить `metadata_hash`, `extensions_fingerprint` и `config_generation_id` как provenance/diagnostics markers publication state.
- Сделать publication drift non-blocking для authoring/reuse: он должен показываться как диагностика, а не как hard incompatibility между ИБ одной и той же конфигурации.
- Зафиксировать Designer-derived source-of-truth для business identity конфигурации через root configuration export/properties.

## Impact
- Affected specs:
  - `organization-pool-catalog`
  - `pool-document-policy`
  - `workflow-decision-modeling`
- Related active changes:
  - `add-config-generation-id-metadata-snapshots` должен остаться совместимым с новой identity semantics: `config_generation_id` остаётся technical marker и не становится частью reuse key.
  - `add-decision-revision-rollover-ui` должен использовать новый compatibility contract при выборе source revision для rollover.
- Affected code (expected):
  - `orchestrator/apps/intercompany_pools/**`
  - `orchestrator/apps/templates/workflow/**`
  - `orchestrator/apps/api_v2/views/decisions.py`
  - `frontend/src/pages/Decisions/**`
  - `contracts/orchestrator/**`

## Breaking Changes
- Да. Меняется normative compatibility contract:
  - одинаковая `config_version` больше не требует совпадения `metadata_hash` для reuse;
  - имя ИБ перестаёт участвовать в configuration identity;
  - `metadata_hash`/publication drift перестаёт быть blocking incompatibility marker для decision reuse.

## Non-Goals
- Не вводить extension-specific HTTP endpoint для имени/версии конфигурации.
- Не оставлять имя ИБ как fallback identity marker в новом контракте.
- Не делать `metadata_hash` replacement для `config_version`.
- Не строить в этом change отдельный operational readiness program для исправления неверной OData publication на стороне tenant.
