## MODIFIED Requirements
### Requirement: Decision resources MUST быть first-class authoring surface для workflow-centric document rules
Система ДОЛЖНА (SHALL) предоставлять first-class authoring/read-model surface для versioned decision resources, используемых workflow-centric `document_policy`.

Frontend surface ДОЛЖЕН (SHALL):
- использовать `/decisions` как canonical decision lifecycle surface;
- использовать business configuration identity `config_name + config_version` как primary compatibility contract для metadata-aware `document_policy` revisions;
- сохранять и показывать resolved metadata provenance/diagnostics markers для `document_policy` revisions;
- показывать `config_generation_id` как отдельный technical marker, если он доступен;
- не скрывать compatible decision revisions только из-за другого имени ИБ, `metadata_hash`, `extensions_fingerprint` или `config_generation_id`.

`/decisions` ДОЛЖЕН (SHALL) показывать publication drift как diagnostics/warning, если selected database diverges по published metadata surface от canonical business-scoped snapshot, но такой drift НЕ ДОЛЖЕН (SHALL NOT) сам по себе переводить revision в incompatible.

`/workflows` и binding editor'ы ДОЛЖНЫ (SHALL) получать decision compatibility по business configuration identity и выбирать compatible revision из `/decisions` без требования manual raw ids.

#### Scenario: `/decisions` показывает compatible revision для другой ИБ той же конфигурации
- **GIVEN** decision revision сохранена для `config_name + config_version`
- **AND** аналитик выбирает другую ИБ с той же business configuration identity, но другим именем ИБ
- **WHEN** UI загружает список compatible revisions
- **THEN** revision видна в default compatible selection
- **AND** имя ИБ не ломает compatibility filtering

#### Scenario: `/decisions` не скрывает compatible revision из-за publication drift
- **GIVEN** selected database совпадает со stored revision по `config_name + config_version`
- **AND** selected database имеет другой `metadata_hash`
- **WHEN** UI вычисляет compatibility и отображает provenance
- **THEN** revision остаётся selectable
- **AND** экран показывает warning/diagnostics о publication drift
- **AND** `metadata_hash` divergence не переводит revision в hidden incompatible state

#### Scenario: `/decisions` показывает technical provenance markers отдельно от business compatibility
- **GIVEN** аналитик открыл `document_policy` revision на `/decisions`
- **WHEN** UI показывает metadata-aware provenance этой revision
- **THEN** экран отдельно показывает business identity `config_name + config_version`
- **AND** отдельно показывает technical markers вроде `config_generation_id` и `metadata_hash`
- **AND** user-visible compatibility определяется business identity, а не technical markers
