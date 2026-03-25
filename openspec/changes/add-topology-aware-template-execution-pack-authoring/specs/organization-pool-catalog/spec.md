## ADDED Requirements
### Requirement: Template-based pool assembly MUST require topology-aware reusable execution packs
Система ДОЛЖНА (SHALL) использовать в template-based pool authoring path на `/pools/catalog` следующую ownership модель:
- `topology_template_revision` задаёт reusable structural graph и `document_policy_key`;
- `pool` задаёт concrete `slot_key -> organization_id`;
- attached `execution-pack revision` задаёт reusable executable implementations через topology-aware participant aliases;
- concrete participant refs НЕ ДОЛЖНЫ (SHALL NOT) быть обязательной частью reusable execution-pack contract для новых/revised template-oriented pools.

При attach, preview или save template-based path система ДОЛЖНА (SHALL) валидировать выбранный execution pack одновременно по:
- structural slot coverage;
- topology-aware master-data readiness для topology-derived `party` / `contract` fields.

Если execution pack structurally совпадает по `slot_key`, но использует hardcoded concrete participant refs для topology-derived reusable slots, `/pools/catalog` ДОЛЖЕН (SHALL):
- fail-close'ить normal attach/preview/create-run path для такого template-oriented flow;
- показывать blocking diagnostic;
- направлять оператора в `/pools/execution-packs` и `/decisions` как canonical remediation surfaces.

Diagnostic contract ДОЛЖЕН (SHALL) использовать stable machine-readable code, чтобы `/pools/catalog` и `/pools/execution-packs` объясняли одну и ту же incompatibility одинаково.

Historical pools и historical execution packs НЕ ДОЛЖНЫ (SHALL NOT) автоматически repair'иться этим change.

#### Scenario: Оператор собирает новый pool из template без hardcoded counterparties
- **GIVEN** оператор создаёт или revises pool через template-based path
- **AND** выбирает `topology_template_revision`
- **AND** назначает concrete `slot_key -> organization_id`
- **AND** выбранная `execution-pack revision` проходит topology-aware compatibility
- **WHEN** оператор сохраняет binding/topology и запускает preview
- **THEN** shipped path не требует отдельного ввода hardcoded `organization`, `counterparty` или `contract owner` refs в reusable execution pack
- **AND** concrete participants выводятся из slot assignments и topology-aware aliases

#### Scenario: Incompatible execution pack блокирует template-based attach path
- **GIVEN** оператор выбрал `topology_template_revision` и execution pack с matched `slot_key`
- **AND** один из reusable slots использует concrete participant refs вместо topology-aware aliases
- **WHEN** оператор пытается сохранить binding, выполнить preview или стартовать run на template-based path
- **THEN** `/pools/catalog` возвращает blocking compatibility diagnostic
- **AND** normal path не продолжает attach или runtime start
- **AND** оператор получает явный handoff в `/pools/execution-packs` и `/decisions`

#### Scenario: Catalog использует stable code для reusable master-data incompatibility
- **GIVEN** template-based path заблокирован из-за execution pack с concrete participant refs
- **WHEN** `/pools/catalog` показывает blocking remediation
- **THEN** remediation использует machine-readable code `EXECUTION_PACK_TEMPLATE_INCOMPATIBLE`
- **AND** оператор видит handoff в canonical reusable execution-pack и decision surfaces
