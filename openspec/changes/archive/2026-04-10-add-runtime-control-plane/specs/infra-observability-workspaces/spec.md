## ADDED Requirements

### Requirement: `/system-status` MUST provide deep-linkable runtime control drill-down for privileged operators
Система ДОЛЖНА (SHALL) сохранять `/system-status` canonical observability route и встраивать в него runtime control drill-down для privileged operators.

Runtime drill-down ДОЛЖЕН (SHALL) поддерживать:
- один canonical route-addressable selected runtime/service context без второго независимого selector path для diagnostics и controls;
- route-addressable selected tab (`Overview`, `Controls`, `Scheduler`, `Logs`);
- route-addressable selected scheduler job context;
- responsive fallback без page-wide overflow.

Mutating controls ДОЛЖНЫ (SHALL) использовать canonical secondary surfaces и НЕ ДОЛЖНЫ (SHALL NOT) требовать raw browser prompts как primary path.

#### Scenario: Deep-link восстанавливает runtime control context
- **GIVEN** staff оператор открывает `/system-status` с выбранными `service=worker-workflows`, `tab=scheduler` и `job=pool_factual_active_sync`
- **WHEN** страница перезагружается или открывается по deep-link
- **THEN** workspace восстанавливает тот же runtime control context
- **AND** оператор может перейти между `Overview`, `Controls`, `Scheduler` и `Logs` без page-wide overflow

#### Scenario: Пользователь без runtime-control capability видит diagnostics-only workspace
- **GIVEN** аутентифицированный пользователь не имеет runtime-control capability
- **WHEN** он открывает `/system-status`
- **THEN** diagnostics surface остаётся доступной
- **AND** mutating runtime/scheduler controls скрыты или недоступны
