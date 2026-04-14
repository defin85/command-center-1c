## MODIFIED Requirements

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
