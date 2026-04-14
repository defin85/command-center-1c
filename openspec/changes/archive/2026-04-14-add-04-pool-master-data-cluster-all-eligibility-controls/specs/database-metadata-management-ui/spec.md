## ADDED Requirements

### Requirement: `/databases` MUST позволять оператору управлять `cluster_all` eligibility для pool master-data sync
Система ДОЛЖНА (SHALL) предоставлять в canonical `/databases` surface operator-facing control для explicit per-database state участия в `cluster_all` pool master-data sync.

Control ДОЛЖЕН (SHALL) поддерживать состояния:
- `eligible` — база участвует в `cluster_all`;
- `excluded` — база намеренно не участвует в `cluster_all`;
- `unconfigured` — решение ещё не принято и `cluster_all` по соответствующему кластеру должен блокироваться fail-closed.

UI ДОЛЖЕН (SHALL) объяснять смысл каждого состояния без обращения к ручному API-клиенту или внестраничной документации.

#### Scenario: Оператор исключает нерелевантную базу из cluster-wide sync
- **GIVEN** оператор открыл `/databases` и выбрал базу, которая не должна участвовать в pool master-data `cluster_all`
- **WHEN** он устанавливает eligibility state `excluded` и сохраняет изменение
- **THEN** система сохраняет machine-readable non-membership state для этой базы
- **AND** последующие `cluster_all` launch'и не включают эту базу в target snapshot

#### Scenario: Legacy база остаётся блокирующей, пока решение не принято
- **GIVEN** база имеет eligibility state `unconfigured`
- **WHEN** оператор открывает `/databases`
- **THEN** UI показывает, что решение по участию в `cluster_all` ещё не принято
- **AND** оператор понимает, что это состояние блокирует cluster-wide launch до явного выбора `eligible` или `excluded`

### Requirement: `/databases` MUST показывать readiness отдельно от business eligibility
Система ДОЛЖНА (SHALL) в том же `/databases` management context показывать technical readiness summary для pool master-data sync отдельно от eligibility control.

Readiness summary МОЖЕТ (MAY) включать runtime enablement, наличие service mapping, OData profile и иные технические признаки, но НЕ ДОЛЖЕН (SHALL NOT) автоматически менять eligibility state без operator decision.

#### Scenario: Readiness warning не переписывает explicit eligibility
- **GIVEN** оператор ранее пометил базу как `eligible`
- **AND** техническая readiness summary позже показывает проблему подключения или service mapping
- **WHEN** оператор открывает `/databases`
- **THEN** UI показывает readiness warning отдельно
- **AND** ранее сохранённый eligibility state не меняется автоматически на `excluded` или `unconfigured`

### Requirement: `/databases` MUST поддерживать handoff из sync launcher к нужной базе и контексту
Система ДОЛЖНА (SHALL) позволять consumer surfaces передавать оператору handoff в `/databases` так, чтобы открывался контекст нужной базы или кластера и control eligibility был immediately actionable.

#### Scenario: Handoff из `/pools/master-data` открывает нужный database context
- **GIVEN** `Launch Sync` drawer заблокировал `cluster_all` из-за `unconfigured` базы
- **WHEN** оператор использует handoff в `/databases`
- **THEN** `/databases` открывается с восстановленным context выбранной базы или кластера
- **AND** operator-facing eligibility control доступен без дополнительного поиска по каталогу
