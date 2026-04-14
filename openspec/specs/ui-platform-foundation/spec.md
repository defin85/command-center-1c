# ui-platform-foundation Specification

## Purpose
TBD - created by archiving change refactor-ui-platform-on-ant. Update Purpose after archive.
## Requirements
### Requirement: Frontend MUST стандартизовать новые admin/backoffice surfaces на Ant-based UI platform
Система ДОЛЖНА (SHALL) использовать `antd` + `@ant-design/pro-components` + project-owned thin design layer как canonical UI platform для новых или существенно переписываемых admin/backoffice surfaces.

Новые или materially rewritten surfaces ДОЛЖНЫ (SHALL) использовать thin design layer как primary path композиции, а не собирать page-level UI напрямую из raw vendor components.

Существующие legacy surfaces МОГУТ (MAY) оставаться на текущих реализациях до их целенаправленной миграции.

#### Scenario: Новый backoffice surface строится через thin design layer, legacy surface остаётся без rewrite
- **GIVEN** в приложении уже существует legacy страница на прямых `antd` imports
- **AND** команда создаёт новый admin/backoffice surface или существенно переписывает существующий
- **WHEN** новый surface реализуется в рамках approved platform direction
- **THEN** он использует canonical abstractions thin design layer поверх `antd`/`pro-components`
- **AND** legacy страница не требует обязательного одновременного rewrite

### Requirement: Ant dependency baseline MUST быть обновлён до поддерживаемой современной линии, совместимой с актуальным Pro Components
Система ДОЛЖНА (SHALL) обновить `antd` до поддерживаемой современной `5.x` линии, совместимой с актуальной линией `@ant-design/pro-components`, прежде чем thin design layer и canonical page patterns будут считаться platform baseline.

Система НЕ ДОЛЖНА (SHALL NOT) использовать неподтверждённый major jump `antd` как часть этого change, если для актуальной линии `@ant-design/pro-components` нет подтверждённого peer-окна совместимости.

#### Scenario: Platform baseline использует поддерживаемую связку Ant и Pro Components
- **GIVEN** проект внедряет canonical UI platform поверх `antd` и `@ant-design/pro-components`
- **WHEN** определяется dependency baseline для implementation этого change
- **THEN** `antd` обновляется до поддерживаемой современной `5.x` линии, совместимой с актуальной линией `@ant-design/pro-components`
- **AND** implementation не зависит от неподтверждённой major-версии `antd`

### Requirement: Thin design layer MUST задавать canonical page patterns и shared UI semantics

Система ДОЛЖНА (SHALL) централизовать в thin design layer минимум canonical patterns для `List`, `Detail`, `MasterDetail`, `DrawerForm`/`ModalForm`, `Workspace` и `Dashboard`, а также shared semantics для status, empty, error и JSON-like payload views.

Thin design layer ДОЛЖЕН (SHALL) также быть canonical owner для:
- shared locale provider bridge внутри frontend shell;
- vendor locale wiring для approved UI stack, включая `antd`;
- shared locale-aware formatters для date/time/number/list/relative time;
- translation access path для platform primitives и их common operator-facing copy.

Feature-level code НЕ ДОЛЖЕН (SHALL NOT) изобретать собственные несовместимые page shells, interaction patterns или route-local locale/provider layers как primary path для новых surfaces.

#### Scenario: Новый workspace получает page chrome и locale semantics из одного platform layer

- **GIVEN** команда реализует новый или materially rewritten admin workspace
- **WHEN** страница использует page header, empty state, timestamp formatting и secondary surfaces
- **THEN** она получает эти semantics из thin design layer
- **AND** не создаёт собственный route-local locale owner поверх canonical shell/provider path

### Requirement: Thin design layer MUST включать минимальный обязательный набор reusable primitives
Система ДОЛЖНА (SHALL) предоставить в project-owned thin design layer минимальный обязательный набор reusable primitives для новых или materially rewritten admin/backoffice surfaces.

Минимальный обязательный набор ДОЛЖЕН (SHALL) включать:
- `PageHeader`
- `MasterDetailShell`
- `EntityTable`
- `EntityDetails`
- `DrawerFormShell`
- `StatusBadge`
- `JsonBlock`

Если для реализации surface требуется отклонение от этого набора, оно ДОЛЖНО (SHALL) быть явно обосновано и не может заменяться ad-hoc page-level vendor composition по умолчанию.

#### Scenario: Новый data-heavy surface использует обязательные reusable primitives
- **GIVEN** команда реализует новый или materially rewritten data-heavy admin surface
- **WHEN** surface требует header, list/detail, drawer-based edit и structured payload presentation
- **THEN** реализация использует минимальный обязательный набор reusable primitives из thin design layer
- **AND** не собирает эти паттерны заново напрямую на уровне feature-page

### Requirement: MasterDetail surfaces MUST иметь narrow-viewport fallback без горизонтального overflow
Система ДОЛЖНА (SHALL) обеспечивать, что `MasterDetail` surfaces на узких viewport не зависят от фиксированного dual-column layout как единственного режима отображения.

`MasterDetail` surface ДОЛЖЕН (SHALL) переводить detail/edit в `Drawer`, off-canvas panel или отдельный route/state на narrow viewport и НЕ ДОЛЖЕН (SHALL NOT) допускать horizontal overflow как штатное mobile behaviour.

Для governed catalog/detail routes master pane ДОЛЖЕН (SHALL) оставаться compact selection surface и НЕ ДОЛЖЕН (SHALL NOT) использовать wide data grid как default primary composition path. Широкие таблицы, требующие многих колонок или горизонтального скролла, ДОЛЖНЫ (SHALL) жить в detail pane, dedicated secondary surface или explicit full-width workspace, если это оправдано самим операторским сценарием.

#### Scenario: Mobile-пользователь открывает detail без page-wide horizontal scroll
- **GIVEN** пользователь открывает `MasterDetail` surface на narrow viewport
- **WHEN** он выбирает элемент списка для просмотра detail или edit
- **THEN** detail/edit открывается в mobile-safe fallback режиме (`Drawer`, panel или отдельный route/state)
- **AND** страница не требует page-wide horizontal scroll для работы с основным контентом

#### Scenario: Desktop master pane остаётся compact selection surface
- **GIVEN** оператор открывает governed `MasterDetail` route на desktop viewport
- **WHEN** route показывает primary catalog в master pane
- **THEN** master pane остаётся scan-friendly selection surface с компактной плотностью
- **AND** route не помещает в master pane wide table с horizontal overflow как default primary path

### Requirement: Approved UI platform direction MUST быть единственной primary foundation для новых platform migrations
Система ДОЛЖНА (SHALL) использовать Ant-based platform direction как единственную primary foundation для новых platform migrations в рамках этого change.

Система НЕ ДОЛЖНА (SHALL NOT) одновременно внедрять вторую competing primary UI foundation для новых migrations без отдельного approved architectural change.

#### Scenario: Новый platform migration не создаёт вторую primary design system
- **GIVEN** команда планирует новый migration slice для admin/backoffice surface
- **WHEN** migration выполняется в рамках действующей UI platform strategy
- **THEN** он использует approved Ant-based foundation
- **AND** не вводит параллельную competing primary design system без отдельного approved change

### Requirement: Thin design layer MUST provide localized shared semantics for migrated route families and shell-backed surfaces

Система ДОЛЖНА (SHALL) держать в thin design layer locale-aware shared semantics для page chrome, empty/error/status primitives, JSON/detail helpers и shell-backed `DrawerForm`/`ModalForm` surfaces, чтобы migrated route families могли переиспользовать один canonical path вместо route-local string ownership.

Platform primitives и shell-backed surfaces НЕ ДОЛЖНЫ (SHALL NOT) требовать ad hoc route-level override tables для той operator-facing copy, которой уже владеет thin design layer как shared semantic contract.

#### Scenario: Migrated route reuses platform primitives without rebuilding shared copy ownership

- **GIVEN** команда мигрирует remaining platform-governed route family на canonical i18n path
- **WHEN** route использует `PageHeader`, `EmptyState`, `StatusBadge`, `JsonBlock`, `DrawerFormShell` или `ModalFormShell`
- **THEN** shared primitive copy и locale-aware formatting приходят из thin design layer через canonical namespaces и formatter layer
- **AND** route не создаёт новый route-local shared-copy registry только ради повторения platform semantics

#### Scenario: Shell-backed editor stays locale-consistent with the page chrome

- **GIVEN** migrated route открывает editor drawer или modal через platform shell primitive
- **WHEN** shell locale переключён между `ru` и `en`
- **THEN** page chrome и editor surface используют один и тот же effective locale и shared semantic vocabulary
- **AND** пользователь не сталкивается с mixed-language split между route header и shell-backed editor

