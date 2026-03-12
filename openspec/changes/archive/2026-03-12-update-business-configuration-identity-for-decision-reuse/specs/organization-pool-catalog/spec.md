## MODIFIED Requirements
### Requirement: Metadata catalog retrieval MUST использовать persisted snapshot в БД и Redis только как ускоритель
Система ДОЛЖНА (SHALL) хранить нормализованный metadata catalog как canonical persisted snapshot, пригодный для reuse между несколькими ИБ в рамках одной tenant-scoped business configuration identity, а не как database-local current snapshot по `database_id` alone.

Canonical metadata snapshot identity ДОЛЖНА (SHALL) включать только:
- `config_name`;
- `config_version`.

`config_name` и `config_version` в рамках этого requirement:
- ДОЛЖНЫ (SHALL) описывать business-level identity конфигурации;
- НЕ ДОЛЖНЫ (SHALL NOT) вычисляться из `Database.base_name`, `Database.infobase_name`, `Database.name` или `Database.version`;
- ДОЛЖНЫ (SHALL) по смыслу резолвиться из root configuration properties, а runtime'ом по умолчанию читаться из persisted business profile, верифицированного root configuration export path.

`config_name` ДОЛЖЕН (SHALL) резолвиться в порядке:
- root configuration `Synonym` для локали `ru`;
- первый доступный synonym entry;
- root configuration `Name`.

`config_version` ДОЛЖЕН (SHALL) резолвиться из root configuration `Version`.

Runtime acquisition contract ДОЛЖЕН (SHALL) быть profile-driven:
- metadata refresh/read path ДОЛЖЕН (SHALL) использовать persisted business profile, если он уже известен и не требует re-verify;
- система ДОЛЖНА (SHALL) использовать `config_generation_id` только как cheap equal/not-equal marker, определяющий необходимость re-verify;
- если profile отсутствует или generation marker указывает на изменение конфигурации, система ДОЛЖНА (SHALL) запускать async verification/bootstrap job;
- verification/bootstrap job ДОЛЖЕН (SHALL) переиспользовать существующую execution chain `workflow/operations -> worker -> driver`;
- standalone verification/bootstrap execution ДОЛЖЕН (SHALL) использовать executor `ibcmd_cli`, а не direct shell/probe path в orchestrator;
- standalone verification/bootstrap execution ДОЛЖЕН (SHALL) использовать existing public `execute-ibcmd-cli` contract или эквивалентный operation template / workflow step, который в итоге вызывает тот же `ibcmd_cli` executor;
- если verification является частью большего maintenance flow, она ДОЛЖНА (SHALL) встраиваться как workflow step, который в итоге использует тот же `ibcmd_cli` execution path;
- default verification/bootstrap command ДОЛЖЕН (SHALL) использовать existing schema-driven `command_id = infobase.config.export.objects` с root object selector `Configuration`;
- verification job ДОЛЖЕН (SHALL) парсить `Configuration.xml` и сохранять как минимум `Name`, `Synonym`, `Vendor`, `Version`;
- worker result/artifact contract ДОЛЖЕН (SHALL) позволять orchestrator получить `Configuration.xml` или его нормализованное содержимое для обновления persisted business profile;
- hot path metadata refresh НЕ ДОЛЖЕН (SHALL NOT) требовать full configuration export, Designer/X11 invocation или обхода worker/driver chain для каждой ИБ.

Canonical snapshot identity НЕ ДОЛЖНА (SHALL NOT) включать:
- `database_id`;
- имя ИБ;
- `metadata_hash`;
- `extensions_fingerprint`;
- `config_generation_id`.

Read/refresh path МОЖЕТ (MAY) стартовать от выбранной ИБ, но:
- конкретная ИБ ДОЛЖНА (SHALL) использоваться только как auth/probe source и provenance anchor;
- ИБ с одинаковыми `config_name + config_version` ДОЛЖНЫ (SHALL) переиспользовать один canonical business-scoped snapshot;
- различие published OData metadata surface НЕ ДОЛЖНО (SHALL NOT) создавать отдельную compatibility identity.

`metadata_hash`, `extensions_fingerprint` и `config_generation_id` ДОЛЖНЫ (SHALL) сохраняться и возвращаться как provenance/diagnostics markers publication state.

Если выбранная ИБ отличается по published metadata surface от canonical business-scoped snapshot, API ДОЛЖЕН (SHALL):
- возвращать canonical business-scoped snapshot;
- сохранять provenance последней ИБ, подтвердившей этот snapshot;
- возвращать явную diagnostics indication publication drift для выбранной ИБ.

#### Scenario: Две ИБ с одинаковой конфигурацией и релизом переиспользуют один snapshot независимо от имени ИБ
- **GIVEN** в tenant есть две ИБ с разными именами
- **AND** root configuration properties у них дают одинаковые `config_name` и `config_version`
- **WHEN** оператор запрашивает metadata catalog для второй ИБ после refresh первой
- **THEN** backend возвращает тот же canonical business-scoped snapshot
- **AND** имя ИБ не участвует в compatibility identity

#### Scenario: Одинаковая business identity переиспользует snapshot при publication drift
- **GIVEN** две ИБ имеют одинаковые `config_name` и `config_version`
- **AND** состав опубликованных через OData metadata objects у них различается
- **WHEN** backend refresh'ит metadata catalog для второй ИБ
- **THEN** система не создаёт новую compatibility identity только из-за отличия `metadata_hash`
- **AND** response содержит diagnostics indication publication drift
- **AND** provenance указывает, какая ИБ подтвердила canonical business-scoped snapshot

#### Scenario: Persisted business profile используется как default runtime source
- **GIVEN** для выбранной ИБ уже сохранён persisted business profile
- **AND** `config_generation_id` не указывает на изменение конфигурации с момента последней верификации
- **WHEN** backend выполняет metadata read или refresh
- **THEN** runtime использует persisted `config_name` и `config_version`
- **AND** не требует full export, Designer invocation или direct shell execution в hot path

#### Scenario: Business identity конфигурации верифицируется selective export root object
- **GIVEN** persisted business profile отсутствует или требует re-verify после изменения generation marker
- **WHEN** backend запускает verification/bootstrap job для выбранной ИБ
- **THEN** job проходит через существующую execution chain `workflow/operations -> worker -> driver`
- **AND** использует executor `ibcmd_cli`
- **AND** использует existing `command_id = infobase.config.export.objects` с root object selector `Configuration`
- **AND** парсит `Configuration.xml`
- **AND** `config_name` берётся из root configuration `Synonym` или fallback `Name`
- **AND** `config_version` берётся из root configuration `Version`
- **AND** identity не зависит от имени ИБ

#### Scenario: Generation marker триггерит re-verify, но не становится business identity
- **GIVEN** система хранит `config_generation_id` для ранее верифицированного business profile
- **WHEN** очередной cheap probe возвращает другой `config_generation_id`
- **THEN** система помечает business profile как требующий re-verify
- **AND** запускает async verification job
- **AND** выполняет probe через existing `command_id = infobase.config.generation-id` по тому же `ibcmd_cli`/worker path
- **AND** не использует `config_generation_id` как reuse key между ИБ
