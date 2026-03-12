## 1. Contract
- [ ] 1.1 Обновить contract metadata snapshot identity: `config_name` и `config_version` означают business identity root configuration, а не имя ИБ и не `Database.version`.
- [ ] 1.2 Зафиксировать, что reuse/compatibility key включает только `config_name + config_version`.
- [ ] 1.3 Зафиксировать, что `metadata_hash`, `extensions_fingerprint`, `config_generation_id`, `database_id` и имя ИБ остаются provenance/diagnostics markers и не участвуют в compatibility key.

## 2. Source Of Truth
- [ ] 2.1 Зафиксировать Designer-based source-of-truth для business identity через root configuration export/properties.
- [ ] 2.2 Зафиксировать deterministic resolution для `config_name`: preferred `Synonym(ru)` -> first available synonym -> root `Name`.
- [ ] 2.3 Зафиксировать, что `config_version` берётся из root configuration `Version`.

## 3. Metadata Snapshot Semantics
- [ ] 3.1 Обновить metadata catalog capability на business-level shared snapshot scope.
- [ ] 3.2 Зафиксировать non-blocking `publication drift` semantics: drift должен показываться как diagnostics/warning, а не как отдельная compatibility identity.
- [ ] 3.3 Описать migration/backfill текущих snapshot/resolution данных с legacy infobase-based semantics.

## 4. Decision Compatibility And UI
- [ ] 4.1 Обновить `pool-document-policy` contract: `decision_revision` compatibility опирается только на business identity конфигурации.
- [ ] 4.2 Обновить `workflow-decision-modeling` contract: `/decisions` не скрывает compatible revisions только из-за `metadata_hash`, `extensions_fingerprint` или имени ИБ.
- [ ] 4.3 Согласовать новый contract с активными change `add-config-generation-id-metadata-snapshots` и `add-decision-revision-rollover-ui`.

## 5. Validation
- [ ] 5.1 Добавить backend tests на extraction business identity из root configuration properties.
- [ ] 5.2 Добавить backend/API tests на reuse между ИБ с разными именами, но одинаковыми `config_name + config_version`.
- [ ] 5.3 Добавить backend/API/UI tests на non-blocking publication drift при разном `metadata_hash`.
- [ ] 5.4 Прогнать `openspec validate update-business-configuration-identity-for-decision-reuse --strict --no-interactive`.
