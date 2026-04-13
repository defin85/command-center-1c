## ADDED Requirements

### Requirement: Remaining operator-facing route families MUST complete migration to the canonical i18n layer

Система ДОЛЖНА (SHALL) довести до canonical frontend i18n runtime все route families из checked-in `routeGovernanceInventory`, имеющие tier `platform-governed`, если они ещё не были полностью migrated в рамках initial foundation wave.

Для migrated route family canonical path ДОЛЖЕН (SHALL) включать:
- operator-facing copy через namespace catalogs и shared translation hooks;
- user-visible date/time/number/list/relative time formatting через shared locale-aware formatter layer;
- локализованные empty/error/status/loading semantics без route-local vendor locale owner или ad hoc string registry как primary path.

#### Scenario: Remaining governed route family no longer uses ad hoc copy or raw locale formatting

- **GIVEN** route family вроде `/operations`, `/templates` или `/pools/runs` раньше не входил в pilot migration wave
- **WHEN** route family считается migrated в рамках этого rollout
- **THEN** его page entry, owned drawers/modals и user-visible helper formatting используют canonical i18n runtime и shared formatter layer
- **AND** route family не зависит от raw `toLocale*` или hardcoded locale tags как default user-facing path

### Requirement: Inventory-owned shell surfaces MUST share locale ownership with their owner route family

Система ДОЛЖНА (SHALL) мигрировать все checked-in shell-backed surfaces из `shellSurfaceGovernanceInventory` с tier `platform-governed` на тот же locale owner, translation path и formatter layer, что и их owner route family.

Shell-backed surface НЕ ДОЛЖЕН (SHALL NOT) завершать migration отдельным route-local translation runtime, дублирующим shell/platform catalogs или bypass-ящим shared locale ownership.

#### Scenario: Drawer or modal inherits the same locale semantics as the owning route

- **GIVEN** пользователь открывает drawer или modal, принадлежащий migrated route family
- **WHEN** shell locale уже установлен в `ru` или `en`
- **THEN** drawer/modal рендерит copy, empty/error states и user-visible formatting через тот же effective locale
- **AND** surface не создаёт второго locale owner поверх canonical shell/provider path

### Requirement: Full migration completion MUST explicitly close legacy-monitored operator surfaces and carry browser evidence across rollout waves

Система НЕ ДОЛЖНА (SHALL NOT) заявлять full migration complete, пока operator-facing route surface с tier `legacy-monitored` остаётся на ad hoc i18n path без отдельного approved exception.

Full migration completion ДОЛЖНА (SHALL) включать automated browser evidence как минимум по одному representative route family из каждой rollout wave, включая language switch + reload и отсутствие mixed-language regression на canonical shell path.

#### Scenario: Legacy-monitored factual surface cannot remain an implicit migration gap

- **GIVEN** `/pools/factual` или другой operator-facing route помечен как `legacy-monitored`
- **WHEN** команда заявляет full migration complete
- **THEN** этот surface либо переведён на canonical i18n/governance path
- **OR** существует отдельный approved change/exception, который явно объясняет, почему surface не входит в completion scope текущего rollout

#### Scenario: Representative browser evidence exists for every rollout wave

- **GIVEN** rollout завершает migration wave для набора route families
- **WHEN** change проходит финальную verification gate
- **THEN** browser suite содержит хотя бы один representative locale-switch + reload test для каждой wave
- **AND** acceptance не опирается только на unit/lint evidence без route-level browser proof
