## ADDED Requirements

### Requirement: Governed surfaces MUST route locale formatting and vendor locale wiring through the canonical i18n layer

Система ДОЛЖНА (SHALL) выражать через lint rules или эквивалентные static governance checks, что platform-governed route/page modules и platform primitives не обходят canonical i18n layer.

Governed modules НЕ ДОЛЖНЫ (SHALL NOT) как primary path:
- вызывать raw `toLocaleString()`, `toLocaleDateString()` или `toLocaleTimeString()` для user-visible formatting;
- импортировать vendor locale packs или создавать route-local `ConfigProvider locale={...}` вне canonical shell/i18n layer;
- читать translation catalogs напрямую, если этим обходится shared provider/hook contract.

#### Scenario: Lint блокирует raw locale formatting на governed route

- **GIVEN** разработчик меняет platform-governed route
- **WHEN** route-level module форматирует user-visible timestamp через raw `toLocaleString()`
- **THEN** frontend governance check сообщает явное i18n boundary нарушение
- **AND** change не проходит validation gate до возврата к canonical formatter layer

#### Scenario: Lint блокирует route-local vendor locale override

- **GIVEN** governed route пытается импортировать `antd` locale pack и установить собственный `ConfigProvider locale`
- **WHEN** запускается frontend lint
- **THEN** lint сообщает явное нарушение locale ownership boundary
- **AND** effective locale остаётся owned shared shell/i18n layer, а не конкретным route module
