## 1. Contract
- [x] 1.1 Обновить contract metadata snapshot identity: `config_name` и `config_version` означают business identity root configuration, а не имя ИБ и не `Database.version`.
- [x] 1.2 Зафиксировать, что reuse/compatibility key включает только `config_name + config_version`.
- [x] 1.3 Зафиксировать, что `metadata_hash`, `extensions_fingerprint`, `config_generation_id`, `database_id` и имя ИБ остаются provenance/diagnostics markers и не участвуют в compatibility key.

## 2. Source Of Truth
- [x] 2.1 Зафиксировать, что нормативный source-of-truth для business identity остаётся root configuration properties, но runtime acquisition по умолчанию идёт через persisted business profile.
- [x] 2.2 Зафиксировать deterministic resolution для `config_name`: preferred `Synonym(ru)` -> first available synonym -> root `Name`.
- [x] 2.3 Зафиксировать, что `config_version` берётся из root configuration `Version`.
- [x] 2.4 Зафиксировать, что acquisition/re-verify выполняются через существующую цепочку `workflow/operations -> worker -> driver`, а не через direct shell path в orchestrator.
- [x] 2.5 Зафиксировать reuse уже существующего schema-driven `command_id = infobase.config.generation-id` как cheap change-detection marker для re-verify, выполняемый через `ibcmd_cli`/worker path, а не как identity key.
- [x] 2.6 Зафиксировать async probe path через existing `command_id = infobase.config.export.objects` с root object selector `Configuration` и парсинг `Configuration.xml` как default bootstrap/verification mechanism внутри существующего `ibcmd_cli` execution pipeline.
- [x] 2.7 Зафиксировать operation/artifact wiring contract для `Configuration.xml` handoff, не расширяя scope change на изобретение новых `ibcmd` command ids, если они уже есть в approved `Command Schemas`.
- [x] 2.8 Зафиксировать, что full export и Designer/X11 probe не используются в hot path metadata refresh.

## 3. Metadata Snapshot Semantics
- [x] 3.1 Обновить metadata catalog capability на business-level shared snapshot scope.
- [x] 3.2 Зафиксировать non-blocking `publication drift` semantics: drift должен показываться как diagnostics/warning, а не как отдельная compatibility identity.
- [x] 3.3 Описать migration/backfill текущих snapshot/resolution данных с legacy infobase-based semantics.
- [x] 3.4 Зафиксировать profile-driven refresh semantics: при наличии валидного persisted profile runtime использует его без обязательного heavy extraction.
- [x] 3.5 Зафиксировать, как orchestrator обновляет persisted business profile по результату worker/artifact, не вводя второй runtime executor.

## 4. Decision Compatibility And UI
- [x] 4.1 Обновить `pool-document-policy` contract: `decision_revision` compatibility опирается только на business identity конфигурации.
- [x] 4.2 Обновить `workflow-decision-modeling` contract: `/decisions` не скрывает compatible revisions только из-за `metadata_hash`, `extensions_fingerprint` или имени ИБ.
- [x] 4.3 Согласовать новый contract с активным change `add-decision-revision-rollover-ui`.

## 5. Validation
- [x] 5.1 Добавить backend tests на extraction business identity из `Configuration.xml`, полученного через selective export root object.
- [x] 5.2 Добавить backend/API tests на reuse между ИБ с разными именами, но одинаковыми `config_name + config_version`.
- [x] 5.3 Добавить backend/API/UI tests на non-blocking publication drift при разном `metadata_hash`.
- [x] 5.4 Добавить backend tests на profile-driven acquisition: известный persisted profile не требует heavy probe, changed generation id требует re-verify.
- [x] 5.5 Добавить integration tests на execution chain `operations -> worker -> driver` для acquisition commands и artifact handoff.
- [x] 5.6 Прогнать `openspec validate update-business-configuration-identity-for-decision-reuse --strict --no-interactive`.
