# database-metadata-management-ui Specification

## Purpose
Зафиксировать `/databases` как канонический operator-facing surface для управления configuration profile и metadata snapshot выбранной ИБ и задать явный handoff из consumer surfaces.
## Requirements
### Requirement: `/databases` MUST предоставлять канонический metadata management surface для выбранной ИБ
Система ДОЛЖНА (SHALL) предоставлять на route `/databases` operator-facing surface для управления configuration profile и metadata snapshot выбранной информационной базы без использования ручного API-клиента.

Этот surface ДОЛЖЕН (SHALL) быть доступен из per-database actions existing UI и показывать как минимум:
- `config_name`;
- `config_version`;
- `config_generation_id`;
- verification status и relevant timestamps;
- `snapshot_id`;
- `resolution_mode`;
- `metadata_hash`;
- `observed_metadata_hash`;
- `publication_drift`;
- `provenance_database_id`.

Change НЕ ДОЛЖЕН (SHALL NOT) требовать отдельный top-level route, если тот же contract можно разместить как panel/drawer внутри `/databases`.

#### Scenario: Оператор открывает metadata management surface из `/databases`
- **GIVEN** оператор работает со списком баз на `/databases`
- **WHEN** он открывает metadata management controls конкретной ИБ
- **THEN** UI показывает отдельно business identity / reuse key и metadata snapshot state
- **AND** оператору не требуется переходить в `/pools/catalog` или использовать ручной API-клиент для базового осмотра состояния

### Requirement: `/databases` MUST явно разделять re-verify identity и refresh snapshot
Система ДОЛЖНА (SHALL) предоставлять в metadata management surface два разных действия:
- `Re-verify configuration identity`;
- `Refresh metadata snapshot`.

UI ДОЛЖЕН (SHALL) явно объяснять, что:
- `Re-verify configuration identity` относится к business identity / reuse key конфигурации и ведёт через async operation path;
- `Refresh metadata snapshot` относится к содержимому metadata snapshot и publication drift diagnostics;
- эти действия НЕ ДОЛЖНЫ (SHALL NOT) быть объединены под одним двусмысленным control label.

#### Scenario: Оператор запускает re-verify identity
- **GIVEN** у выбранной ИБ нужно перепроверить `config_name/config_version` и verification state
- **WHEN** оператор нажимает `Re-verify configuration identity`
- **THEN** UI запускает async flow и показывает machine-readable outcome или handoff в `/operations`
- **AND** текст UI не выдаёт этот запуск за обычный snapshot refresh

#### Scenario: Оператор запускает refresh metadata snapshot
- **GIVEN** у выбранной ИБ нужно обновить нормализованный metadata snapshot
- **WHEN** оператор нажимает `Refresh metadata snapshot`
- **THEN** UI обновляет snapshot state и drift markers
- **AND** текст UI не выдаёт это действие за перепроверку business identity конфигурации

### Requirement: `/databases` MUST показывать fail-closed state и actionable guidance
Если current profile или current snapshot отсутствует, находится в переходном состоянии или требует пользовательского вмешательства, metadata management surface ДОЛЖЕН (SHALL):
- показывать fail-closed status;
- объяснять, какой именно слой отсутствует (`configuration profile` vs `metadata snapshot`);
- подсказывать следующий допустимый action в рамках того же surface или через handoff в `/operations`.

Система НЕ ДОЛЖНА (SHALL NOT) скрывать отсутствие profile/snapshot за generic сообщением "reload metadata".

#### Scenario: UI различает отсутствие profile и отсутствие snapshot
- **GIVEN** для выбранной ИБ отсутствует verified configuration profile или отсутствует current metadata snapshot
- **WHEN** оператор открывает metadata management surface
- **THEN** UI показывает, какой именно слой недоступен
- **AND** предлагает подходящий следующий шаг вместо общего недиагностичного reload-сообщения

### Requirement: `/databases` MUST использовать canonical workspace composition для database management
Система ДОЛЖНА (SHALL) реализовать `/databases` как platform workspace, где database catalog является primary selection context, а metadata management, DBMS metadata, connection profile и extensions/manual-operation actions представлены как dedicated secondary surfaces или явные handoff paths.

Route ДОЛЖЕН (SHALL) сохранять selected database и active management context в URL-addressable state, чтобы reload, deep-link и browser back/forward не сбрасывали operator workspace silently.

Primary edit/inspection flows НЕ ДОЛЖНЫ (SHALL NOT) оставаться набором конкурирующих raw drawers/modals без общего platform shell. Для canonical management path должны использоваться `DrawerFormShell`, `ModalFormShell` или явный route handoff в canonical surface.

Desktop master pane ДОЛЖЕН (SHALL) оставаться compact database catalog, где выбор базы возможен без wide multi-column grid как основного operator path. Rich operational density, bulk-edit heavy controls и metadata-rich tables ДОЛЖНЫ (SHALL) жить в detail/secondary surfaces или включаться по явному operator intent, а не как default master-pane canvas.

#### Scenario: Оператор возвращается к выбранной ИБ и management context после reload
- **GIVEN** оператор открыл конкретную ИБ и metadata management context на `/databases`
- **WHEN** страница перезагружается или оператор использует browser back/forward
- **THEN** UI восстанавливает selected database и активный management context
- **AND** канонический workspace не возвращается молча в общий невыбранный catalog state

#### Scenario: Metadata management не конкурирует с другими raw page-level overlays
- **GIVEN** оператор работает со списком ИБ на `/databases`
- **WHEN** он открывает metadata management, DBMS metadata или connection profile flow
- **THEN** UI использует единый canonical secondary surface pattern или явный handoff
- **AND** оператор не сталкивается с несколькими конкурирующими page-level modal/drawer paradigms внутри одного route

#### Scenario: Master pane остаётся компактным каталогом баз
- **GIVEN** оператор открывает `/databases` на desktop viewport
- **WHEN** он просматривает и выбирает ИБ в master pane
- **THEN** master pane остаётся компактным catalog/selection surface
- **AND** route не требует wide grid с горизонтальным скроллом как default способ выбора базы

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

